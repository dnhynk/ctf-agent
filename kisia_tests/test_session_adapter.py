"""§4 어댑터 — `kisia/runtime/session.py`.

**여기서 잠그는 것과 잠그지 못하는 것을 먼저 적는다.**

잠그는 것: 호스트 `/proc` 파싱, 컨테이너 안/밖 판별, 거부 셋(§4.2·§4.3·S6.3),
`newline` 의 **바이트 동일성**(§4.1-1), 종류 선언의 성질.

잠그지 **못하는** 것: `read` 의 `closed`·`timed_out`, `close` 의 sid 정리, `snapshot` 의
`live`. 이 셋은 실제 컨테이너와 호스트 `/proc` 을 요구한다. **그것이 이 파일의 결함이
아니라 `CLAUDE.md` §6.1 의 순서다** — 1급 테스트는 계약 술어이고 단위 테스트가 통과한다는
사실은 아무것도 증명하지 않는다(프로토타입 693개가 [ev §8]의 다섯 결함을 품고 통과했다).

`read` 쪽 테스트는 POSIX 에서만 돈다 — `select` 가 Windows 에서 파이프를 받지 못한다.
**워크스테이션에서 건너뛰는 테스트는 호스트에서 돌린다**(재빌드-5 §4 의 실행 기록).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

from kisia.runtime.session import (
    KINDS,
    Refusal,
    Session,
    SessionRegistry,
    host_proc_table,
)

POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="select() 가 Windows 에서 파이프를 받지 못한다. 호스트에서 돈다.",
)


# ---------------------------------------------------------------------------
# 가짜 /proc — 밖에서 보는 눈의 파서
# ---------------------------------------------------------------------------


def write_proc(root: Path, pid: int, *, state: str, ppid: int, sid: int,
               cmdline: str, nspid: list[int] | None, comm: str = "python3",
               pgid: int | None = None) -> None:
    d = root / str(pid)
    d.mkdir(parents=True)
    # /proc/<pid>/stat: pid (comm) state ppid pgrp session ...
    (d / "stat").write_text(
        f"{pid} ({comm}) {state} {ppid} {pgid if pgid is not None else pid} {sid} 0 0 0 0\n",
        encoding="utf-8",
    )
    (d / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode() + b"\0")
    status = "Name:\tpython3\n"
    if nspid is not None:
        status += "NSpid:\t" + "\t".join(str(x) for x in nspid) + "\n"
    (d / "status").write_text(status, encoding="utf-8")


@pytest.mark.unit
def test_proc_table_parses_state_ppid_sid_and_nspid(tmp_path: Path) -> None:
    write_proc(tmp_path, 100, state="S", ppid=7, sid=100,
               cmdline="python3 -c pty kisia-session=a-s1", nspid=[100, 8])
    write_proc(tmp_path, 101, state="Z", ppid=100, sid=100, cmdline="sleep 300", nspid=[101, 9])
    (tmp_path / "notapid").mkdir()

    table = host_proc_table(tmp_path)

    assert set(table) == {100, 101}
    assert table[100].sid == 100
    assert table[100].ppid == 7
    assert table[100].in_container is True
    assert table[100].container_pid == 8
    assert table[100].zombie is False
    assert table[101].zombie is True


@pytest.mark.unit
def test_proc_table_survives_comm_with_spaces_and_parens(tmp_path: Path) -> None:
    """`comm` 에 공백·괄호가 들어가면 필드를 앞에서 세는 파서가 조용히 틀린다.

    그러면 sid 가 엉뚱한 값이 되고, sid 로 거른 생존자 수가 **거짓 0** 이 된다.
    """
    write_proc(tmp_path, 200, state="R", ppid=1, sid=42, cmdline="x",
               nspid=[200, 3], comm="bad (name) here")

    assert host_proc_table(tmp_path)[200].sid == 42


@pytest.mark.unit
def test_pgid_and_sid_are_read_from_different_stat_fields(tmp_path: Path) -> None:
    """`stat` 의 pgrp(5번)와 session(6번)은 이웃한 필드다. 바꿔 읽어도 대부분의
    프로세스에서는 두 값이 같아 **아무 일도 일어나지 않는다.**

    갈리는 것은 tty job control 아래 `&` 로 띄운 잡뿐이고, 정확히 그때
    `pgid_only_would_have_killed` 가 의미를 잃는다 — [ev §8.1] 이 재려는 그 차이다.
    """
    write_proc(tmp_path, 400, state="S", ppid=1, sid=100, pgid=222,
               cmdline="sleep 300", nspid=[400, 17])

    row = host_proc_table(tmp_path)[400]

    assert (row.pgid, row.sid) == (222, 100)


@pytest.mark.unit
def test_our_docker_exec_client_is_not_mistaken_for_the_container_process(tmp_path: Path) -> None:
    """토큰은 우리 클라이언트의 argv 에도 있다. **`NSpid` 길이가 가른다**(진단 2 의 A)."""
    token = "kisia-session=a-s1"
    write_proc(tmp_path, 300, state="S", ppid=9, sid=300,
               cmdline=f"docker exec -i ctr python3 {token}", nspid=[300])
    write_proc(tmp_path, 301, state="S", ppid=8, sid=301,
               cmdline=f"python3 -c pty {token}", nspid=[301, 8])

    table = host_proc_table(tmp_path)
    inside = [p for p in table.values() if token in p.cmdline and p.in_container]

    assert [p.pid for p in inside] == [301]


# ---------------------------------------------------------------------------
# 종류 선언 — 수행 불가 면제의 근거 (R3-9)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_two_input_accepting_kinds_so_the_newline_probe_is_not_exempt() -> None:
    """§4.1-1 은 **입력을 받는 종류의 모든 쌍**에 평가된다(R2-9).

    종류가 하나면 B-2 가 *수행 불가* 가 되고 — X 가 그랬다 — 그것은 통과가 아니다.
    """
    accepting = [k for k in KINDS.values() if k.accepts_input]

    assert len(accepting) >= 2, "입력을 받는 종류가 둘 미만이면 §4.1-1 을 시험할 대상이 없다"


@pytest.mark.contract
def test_exactly_one_kind_declares_itself_signalable() -> None:
    """§4.3 의 두 갈래가 **둘 다** 행사되려면 signalable 이 하나는 참, 하나는 거짓이다."""
    flags = {k.kind: k.signalable for k in KINDS.values()}

    assert flags["tty"] is True
    assert flags["connect"] is False, (
        "`_connect.py` 를 signalable 로 선언하면 §4.3 의 '프롬프트 복귀'를 그 종류에서도 "
        "보여야 하고, 그것이 (예정) V-01 이 예상됐던 이유다. 순수 소켓 선언이 그 패치를 "
        "불필요하게 만든다 — 선언을 바꾸면 그 결정이 뒤집힌다."
    )


@pytest.mark.contract
def test_declaration_carries_the_fields_the_control_block_needs() -> None:
    reg = _registry()

    for entry in reg.declaration():
        assert set(entry) == {"kind", "accepts_input", "signalable"}


# ---------------------------------------------------------------------------
# 거부 셋 — 거부는 만족이고 이벤트로 남는다
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_unknown_kind_is_refused_not_guessed() -> None:
    reg = _registry()

    got = reg.open(kind="gdb")

    assert isinstance(got, Refusal)
    assert got.reason_code == "unknown_kind"


@pytest.mark.contract
def test_over_the_limit_is_refused_never_queued_or_evicted() -> None:
    """§4.2 / R2-8 — 상한 초과는 **거부**다. 대기도 조용한 축출도 아니다.

    X 는 관측 상한에서 세션을 조용히 버렸고, 그것은 거부도 대기도 아닌 세 번째 동작이다.
    """
    reg = _registry(limit=2)
    for i in (1, 2):
        reg.sessions[f"s{i}"] = _stub_session(f"s{i}", kind="tty")

    got = reg.open(kind="tty")

    assert isinstance(got, Refusal)
    assert got.reason_code == "concurrency_limit"
    # 축출되지 않았다 — 둘 다 그대로 살아 있다.
    assert reg.live_ids() == ["s1", "s2"]


@pytest.mark.contract
def test_unknown_session_id_is_refused_and_no_session_is_created() -> None:
    """S6.3 — "조용히 새 세션을 만들지 않는다." 상태 유실을 성공처럼 보이게 하는 경로다."""
    reg = _registry()

    got = reg.get("nope")

    assert isinstance(got, Refusal)
    assert got.reason_code == "unknown_session"
    assert reg.sessions == {}


@pytest.mark.contract
def test_a_closed_session_is_refused_too() -> None:
    reg = _registry()
    dead = _stub_session("s1", kind="tty")
    dead.closed = True
    reg.sessions["s1"] = dead

    assert isinstance(reg.get("s1"), Refusal)
    assert reg.live_ids() == []


@pytest.mark.contract
def test_interrupt_on_a_pure_socket_kind_is_refused() -> None:
    """§4.3 — 시그널 의미가 없는 종류에서는 **명시적 거부이고 거부는 만족이다.**"""
    session = _stub_session("s1", kind="connect")

    got = session.interrupt()

    assert isinstance(got, Refusal)
    assert got.reason_code == "kind_not_signalable"


# ---------------------------------------------------------------------------
# §4.1-1 — newline 의 바이트 동일성
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.parametrize("kind", sorted(KINDS))
def test_newline_appends_exactly_one_lf_in_every_kind(kind: str) -> None:
    """§4.1-1 — "pty 세션에서는 지켜지고 소켓 세션에서는 조용히 무시되는 구현은 계약
    위반이다" [ev §8.5]. 두 종류가 **같은 바이트**를 써야 한다.
    """
    read_fd, write_fd = os.pipe()
    try:
        session = _stub_session("s1", kind=kind, stdin_fd=write_fd)
        session.send(b"HELO kisia", newline=True)
        assert os.read(read_fd, 64) == b"HELO kisia\n"
    finally:
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.contract
@pytest.mark.parametrize("kind", sorted(KINDS))
def test_newline_false_appends_nothing_in_every_kind(kind: str) -> None:
    read_fd, write_fd = os.pipe()
    try:
        session = _stub_session("s1", kind=kind, stdin_fd=write_fd)
        session.send(b"raw", newline=False)
        assert os.read(read_fd, 64) == b"raw"
    finally:
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.contract
def test_send_advances_the_session_seq_and_the_transcript() -> None:
    read_fd, write_fd = os.pipe()
    try:
        session = _stub_session("s1", kind="tty", stdin_fd=write_fd)
        assert session.send(b"a") == 1
        assert session.send(b"b") == 2
        assert bytes(session.transcript) == b"a\nb\n"
        assert session.bytes_out == 4
        os.read(read_fd, 64)
    finally:
        os.close(read_fd)
        os.close(write_fd)


@pytest.mark.contract
def test_interrupt_writes_the_line_discipline_byte_not_a_signal() -> None:
    """E 의 `pkill -SIGINT` 는 세션을 죽였다(exit 130). 우리는 pty 에 `0x03` 을 쓴다."""
    read_fd, write_fd = os.pipe()
    try:
        session = _stub_session("s1", kind="tty", stdin_fd=write_fd)
        assert session.interrupt() == 1
        assert os.read(read_fd, 8) == b"\x03"
    finally:
        os.close(read_fd)
        os.close(write_fd)


# ---------------------------------------------------------------------------
# read — POSIX 에서만
# ---------------------------------------------------------------------------


@POSIX_ONLY
@pytest.mark.contract
def test_read_stops_at_max_bytes() -> None:
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"0123456789")
        session = _stub_session("s1", kind="tty", stdout_fd=read_fd)
        got = session.read(timeout_ms=500, max_bytes=4)
        assert got.data == b"0123"
        assert got.closed is False
    finally:
        os.close(read_fd)
        os.close(write_fd)


@POSIX_ONLY
@pytest.mark.contract
def test_read_reports_closed_on_eof_instead_of_raising() -> None:
    """`read_with_timeout` 은 이 경우 `RuntimeError` 를 던진다 — `closed` 를 값으로 낼 수
    없다는 것이 그 함수를 쓰지 않는 이유 중 하나다(§3.4 의 REWRITE).
    """
    read_fd, write_fd = os.pipe()
    try:
        os.close(write_fd)
        session = _stub_session("s1", kind="tty", stdout_fd=read_fd)
        got = session.read(timeout_ms=300, max_bytes=64)
        assert got.closed is True
        assert got.data == b""
    finally:
        os.close(read_fd)


@POSIX_ONLY
@pytest.mark.contract
def test_read_with_no_bytes_times_out_but_partial_output_does_not() -> None:
    """`timed_out` 을 "조용해졌다"로 정의하면 **모든** read 가 타임아웃이 된다."""
    read_fd, write_fd = os.pipe()
    try:
        session = _stub_session("s1", kind="tty", stdout_fd=read_fd)
        assert session.read(timeout_ms=120, max_bytes=64).timed_out is True

        os.write(write_fd, b"hi")
        got = session.read(timeout_ms=120, max_bytes=64)
        assert got.data == b"hi"
        assert got.timed_out is False
    finally:
        os.close(read_fd)
        os.close(write_fd)


# ---------------------------------------------------------------------------


class _StubProc:
    """`docker exec` 클라이언트 자리의 대역. **`poll()` 은 쓰이지 않아야 한다.**

    `snapshot().live` 가 이 값을 보면 §4.1-4 위반이다. 여기서 `None` 을 돌려 두는 것은
    편의가 아니라 그 성질을 깨뜨리기 쉽게 만들어 두는 것이다.
    """

    def __init__(self, stdin_fd: int, stdout_fd: int) -> None:
        self.stdin = _Fd(stdin_fd)
        self.stdout = _Fd(stdout_fd)
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return None


class _Fd:
    def __init__(self, fd: int) -> None:
        self._fd = fd

    def fileno(self) -> int:
        return self._fd

    def close(self) -> None:
        return None


class _StubVendored:
    def __init__(self, proc: _StubProc) -> None:
        self.session_process = proc


def _registry(*, limit: int | None = 2) -> SessionRegistry:
    """`init_pid` 는 거부 경로에 닿지 않는다 — 거부는 `open` 이 vendored 코드를 부르기
    **전에** 일어난다. 그래서 이 테스트들이 컨테이너 없이 돈다.
    """
    cli: Any = object()
    return SessionRegistry(cli, "c", init_pid=1, limit=limit)


def _stub_session(
    session_id: str, *, kind: str, stdin_fd: int = 1, stdout_fd: int = 0
) -> Session:
    proc = _StubProc(stdin_fd, stdout_fd)
    cli: Any = object()
    return Session(
        session_id=session_id,
        kind=KINDS[kind],
        token=f"kisia-session={session_id}",
        vendored=_StubVendored(proc),
        container="c",
        cli=cli,
        leader_host_pid=1234,
        leader_container_pid=8,
        session_sids=(1234,),
    )
