"""S4 §4 — `InteractiveSession` 어댑터. **vendored 코드에 닿는 유일한 제품 파일이다.**

`kisia_tests/test_vendor_boundary.py::test_only_one_product_file_touches_vendor` 가 그
성질을 강제한다 (`FOUNDATION_DECISION.md` §6.2-2). 철수가 "vendor 삭제 + 이 파일
재작성"으로 유지되는 이유가 그것이다(§6.5).

`SEAM_IMPLEMENTATION_MAP.md` §3.4 가 여섯 연산 중 **둘만 온전하다**고 적었고 이 파일이
나머지 넷과 레지스트리를 만든다.

    open       WRAP     vendored `get_interactive_session` + session_id 부여 + 배너
    send       REWRITE  read 와 분리. 융합된 형태로는 max_bytes·timed_out·closed 를 못 낸다
    read       REWRITE  독립 read(timeout_ms, max_bytes), **raw 바이트**
    interrupt  REWRITE  pty 회선 규율에 0x03. E 의 `pkill -SIGINT` 는 세션을 죽였다
    snapshot   REWRITE  진실은 호스트 /proc 의 **컨테이너 안 프로세스**다
    close      REWRITE  sid 기반 정리 + 밖에서 센 survivors
    §4.2       REWRITE  레지스트리·상한·식별자·수명이 전부 우리 것이다

`read_with_timeout` 을 **쓰지 않는다.** 허용 목록(§3.1)에 있지만 §3.4 는 "쓸 수 있다"이고
의무가 아니다. 그 함수는 `\\r\\n`→`\\n` 으로 정규화한 `str` 을 주고(`utils.py:187`),
`max_bytes` 인자가 없고, 세션이 죽거나 타임아웃이면 **던진다**(`utils.py:180-185`) —
계약이 `read` 에 요구하는 `bytes`·`max_bytes`·`closed`·`timed_out` 중 하나도 그것으로
표현되지 않는다. **그 결과 vendored 표면이 §3.5 가 적은 것보다 또 작아진다는 사실을
숨기지 않는다** — 근거는 `docs/rebuild/reuse/S4.md`.

**자기 보고를 판정에 쓰지 않는다** (`spec.md` §0.3-3). 이 파일에서 그 규칙이 걸리는
자리는 셋이다.

1. `snapshot().live` 는 `session_process.poll()` **이 아니다.** 그것은 호스트 쪽
   `docker exec` 클라이언트를 보는 값이고 §4.1-4 가 이름으로 금지한다. 진실은 호스트
   `/proc` 에서 본 **컨테이너 안 리더 프로세스**다.
2. `descendants_killed` 는 정리를 **수행한** 쪽의 반환값이고, `survivors` 는 그 뒤
   호스트 `/proc` 에서 **밖에서** 센 값이다. 둘을 같은 출처에서 만들면 스트림이 자기
   일관적이 되어 검사기가 통과시킨다(`TELEMETRY_SCHEMA.md` §7.1).
3. 컨테이너가 스스로 센 생존자는 `survivors_self_reported` 로 나란히 싣는다.

**sid 회계의 실측 근거** (재빌드-5 진단 2, `REBUILD_LOG.md` 재빌드-5 §1).

- `docker exec` 로 띄운 프로세스는 컨테이너 init 의 자식이 **아니다** — containerd-shim
  쪽에 달린다. 그래서 재빌드-4 의 `_descendants(init_pid)` 로는 **보이지 않는다.**
- `pty.spawn` 이 `setsid` 하므로 세션 sid 는 리더가 아니라 **그 자식(bash)** 의 것이다.
- `sh -c 'sleep 300 &'` 로 만든 고아는 init 에 재부모화되지만 **sid 는 유지된다.**
  그래서 전역 `/proc` 을 sid 로 걸러면 살아 있는 식구와 재부모화된 고아가 **둘 다** 잡힌다.
  §4.1-2 가 경계를 커널 세션으로 잡고 `open` 에서 리더를 정하라고 한 이유가 이것이다.
- **선언하는 한계:** 세션 안의 프로세스가 스스로 `setsid` 하면 이 회계를 벗어난다.
  §4.1-2 의 경계가 sid 이므로 계약의 경계 밖이지만, 접지 않고 적는다.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import select
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kisia.runtime.docker_cli import DockerCli
from vendor.swe_agent_dc18a740.sweagent.environment.utils import get_interactive_session

#: argv 끝에 붙는 표식. 호스트 `/proc/<pid>/cmdline` 에만 남고, 이것으로 리더를
#: **컨테이너의 협조 없이** 특정한다. 환경 변수로는 안 된다 — `/proc/<pid>/environ` 은
#: root 소유 프로세스에 대해 `ctf-host-user` 가 읽지 못한다(실측).
#: S105 는 오탐이다 — 비밀이 아니라 `/proc` 에 드러내려고 만든 공개 표식이고,
#: 비밀은 통제 블록의 `secret_refs[]` 로만 다룬다(`TELEMETRY_SCHEMA.md` §3.2.1).
TOKEN_PREFIX = "kisia-session"  # noqa: S105

#: `/dev/ptmx` 를 쓰는 pty 셸. `-t` 를 붙일 수 없으므로(vendored 함수가 argv 를
#: 하드코딩한다) pty 를 **컨테이너 안에서** 만든다. 실측으로 job control 과 `^C` 가
#: 둘 다 선다(진단 2 의 B·E).
TTY_ARGV: tuple[str, ...] = (
    "python3", "-c", "import pty; pty.spawn(['/bin/bash','-i'])",
)

#: `PATH_SCOPE.md` §2.3 이 이미지에 굽게 한 vendored 자산. E 의 통합을 성립시킨 것이
#: 이 셸이다(`SEAM_IMPLEMENTATION_MAP.md` §3.3).
CONNECT_ARGV: tuple[str, ...] = ("python3", "/opt/kisia/session/_connect.py")


class SessionError(RuntimeError):
    """어댑터가 요구를 만족시킬 수 없다. **조용히 넘어가지 않는다.**"""


@dataclass(frozen=True)
class Refusal:
    """거부. §4.2·§4.3·S6.3 에서 거부는 **만족**이고 이벤트로 남는다.

    이 객체를 예외로 던지지 않는 이유: 호출자가 `scope.refused` 를 내야 하고, 예외로
    만들면 그 경로가 정상 흐름과 갈려 이벤트를 빼먹기 쉽다(R2-8 의 '조용한 축출'이
    정확히 그 형태였다).
    """

    action: str
    reason_code: str


@dataclass(frozen=True)
class SessionKind:
    """종류의 **선언**. `TELEMETRY_SCHEMA.md` §2.1 의 `session_kinds[]` 가 이것이다.

    `accepts_input` 과 `signalable` 은 편의 필드가 아니라 **수행 불가 면제의 근거**다
    (`spec.md` §6.2 R3-9: 선언은 통제 블록의 필드여야 한다). 그리고 선언은 관측으로
    반증된다 — `signalable=False` 를 선언하고 interrupt 가 통하면 그 선언이 거짓이다.
    """

    kind: str
    accepts_input: bool
    signalable: bool
    argv: tuple[str, ...]
    #: 정상 종료를 먼저 시도할 때 보내는 줄. 없으면 stdin 을 닫는 것으로 시작한다.
    exit_command: str | None

    def as_declaration(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "accepts_input": self.accepts_input,
            "signalable": self.signalable,
        }


#: 종류 **둘**이다. 하나면 §4.1-1(newline 일관성)이 *수행 불가* 가 되고 — X 가 그랬다 —
#: tty 가 없으면 §4.1-2 의 job control 과 §4.3 의 프롬프트 복귀를 시험할 대상이 없다.
KINDS: dict[str, SessionKind] = {
    "tty": SessionKind(
        kind="tty",
        accepts_input=True,
        signalable=True,
        argv=TTY_ARGV,
        exit_command="exit",
    ),
    #: **순수 소켓이다.** `_connect.py` 의 `cmdloop()` 은 `KeyboardInterrupt` 를 잡지
    #: 않아 `pkill -SIGINT` 에 exit 130 으로 죽는다(E 의 실측). 우리는 그 신호를 보내지
    #: 않고 §4.3 의 나머지 갈래를 쓴다 — **시그널 의미가 없는 종류에서는 명시적 거부이고
    #: 거부는 만족이다.** 그래서 `(예정) V-01` 이 필요하지 않다(운영자 결정 2026-08-08).
    "connect": SessionKind(
        kind="connect",
        accepts_input=True,
        signalable=False,
        argv=CONNECT_ARGV,
        exit_command="quit",
    ),
}


# ---------------------------------------------------------------------------
# 호스트 /proc — 밖에서 보는 눈
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HostProc:
    pid: int
    state: str
    ppid: int
    #: 프로세스 **그룹**. 정리 경계로는 쓰지 않는다 — 경계는 sid 다(§4.1-2). 그런데
    #: "프로세스 그룹만 정리하는 구현은 이 술어를 통과하지 못한다"가 계약의 문장이므로,
    #: 그 구현이 **무엇을 놓쳤을지**를 관측으로 남기려면 이 값이 필요하다 [ev §8.1].
    pgid: int
    sid: int
    cmdline: str
    #: `NSpid`. 항목이 둘 이상이면 그 프로세스는 **다른 pid 네임스페이스 안**에 있다 —
    #: 즉 컨테이너 안이다. 이것으로 우리 `docker exec` 클라이언트와 갈린다(진단 2 의 A).
    nspid: tuple[int, ...]

    @property
    def in_container(self) -> bool:
        return len(self.nspid) > 1

    @property
    def container_pid(self) -> int | None:
        return self.nspid[-1] if self.in_container else None

    @property
    def zombie(self) -> bool:
        return self.state == "Z"


def host_proc_table(root: Path | None = None) -> dict[int, HostProc]:
    """호스트 `/proc` 전체. **컨테이너 안에서 세지 않는다** — 그것은 자기 보고다."""
    base = root or Path("/proc")
    out: dict[int, HostProc] = {}
    if not base.is_dir():
        return out
    for entry in base.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # 우리가 읽는 사이에 사라졌다
        # comm 에 공백·괄호가 들어갈 수 있어 마지막 ')' 뒤부터 자른다.
        tail = stat.rpartition(")")[2].split()
        if len(tail) < 4:
            continue
        cmdline = ""
        with contextlib.suppress(OSError):
            cmdline = (
                (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
            ).strip()
        nspid: tuple[int, ...] = ()
        with contextlib.suppress(OSError, ValueError):
            for line in (entry / "status").read_text(errors="replace").splitlines():
                if line.startswith("NSpid:"):
                    nspid = tuple(int(x) for x in line.split()[1:])
                    break
        out[int(entry.name)] = HostProc(
            pid=int(entry.name),
            state=tail[0],
            ppid=int(tail[1]),
            pgid=int(tail[2]),
            sid=int(tail[3]),
            cmdline=cmdline,
            nspid=nspid,
        )
    return out


# ---------------------------------------------------------------------------
# 연산의 반환값 — 계약의 서명 그대로
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpenResult:
    session_id: str
    banner: bytes
    #: 호스트 시야의 리더 pid. 스트림에는 컨테이너 시야를 싣는다(§4.1-4).
    leader_host_pid: int
    leader_container_pid: int | None
    session_sids: tuple[int, ...]


@dataclass(frozen=True)
class ReadResult:
    data: bytes
    closed: bool
    timed_out: bool


@dataclass(frozen=True)
class Snapshot:
    live: bool
    #: **컨테이너 안의** pid. 호스트 pid 는 `host_pid` 로 나란히 싣는다.
    pid: int | None
    host_pid: int
    seq_high: int
    bytes_since_open: int
    #: 컨테이너가 자기 프로세스 표에서 본 값. 판정에 쓰지 않는다(§0.3-3).
    live_self_reported: bool | None = None
    #: **§4.1-4 가 금지한 추론을 일부러 함께 잰다.** `poll()` 은 호스트 쪽
    #: `docker exec` 클라이언트를 보고, 그 상태값 0 은 "정상 종료"이자 "아직 살아
    #: 있음"이다 [ev §8.3]. 이 값과 `live` 가 갈리는 순간이 그 금지의 근거이므로,
    #: 적어 두지 않으면 "우리는 그렇게 하지 않았다"가 주장으로만 남는다.
    naive_live_from_status_only: bool | None = None


@dataclass(frozen=True)
class CloseResult:
    exit_status: int | None
    #: 정리를 **수행한** 쪽이 돌려준 수. 자기 보고다.
    descendants_killed: int
    #: 그 뒤 호스트 `/proc` 에서 **밖에서** 센 수. 판정에 쓰이는 것은 이 값이다.
    survivors: int
    survivors_self_reported: int | None
    grace_used_ms: int
    reason: str
    transcript: bytes
    #: 남은 것이 있으면 근거로 남긴다 — "0" 과 "못 셌다"를 접지 않기 위해.
    survivor_host_pids: tuple[int, ...] = ()
    #: **좀비는 생존자가 아니다** (§4.1-3). **정리 직전에** 센 값이다 — 정리 뒤에 세면
    #: 부모가 죽으면서 좀비가 init 에 거둬진 뒤라 언제나 비고, 그 0 은 "없었다"가 아니라
    #: "사라진 뒤에 봤다"이다. 접으면 이 요구를 행사했는지가 기록에서 사라진다.
    zombies_excluded: tuple[int, ...] = ()
    #: **프로세스 그룹만 정리하는 구현이 무엇을 놓쳤을지** [ev §8.1]. 계약이 그런 구현은
    #: 통과하지 못한다고 적으므로, 우리가 sid 를 고른 것이 값을 바꾼다는 것을 관측으로
    #: 남긴다. 이 목록이 `survivor_host_pids` 정리 대상보다 **작으면** 그 차이가 근거다.
    pgid_only_would_have_killed: tuple[int, ...] = ()


# ---------------------------------------------------------------------------
# 세션 하나
# ---------------------------------------------------------------------------


@dataclass
class Session:
    session_id: str
    kind: SessionKind
    token: str
    vendored: Any
    container: str
    cli: DockerCli
    leader_host_pid: int
    leader_container_pid: int | None
    session_sids: tuple[int, ...]
    #: 같은 세션을 **컨테이너 시야**의 sid 로. `open` 에서 잡아 둔다 — 정리가 끝난 뒤에는
    #: 호스트 표에 남은 것이 없어 옮길 근거가 사라지고, 그러면 컨테이너에 "몇 개 남았나"를
    #: 물을 수조차 없어 자기 보고가 `null` 이 된다. **`null` 과 `0` 은 다른 값이다.**
    container_sids: tuple[int, ...] = ()
    seq: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    closed: bool = False
    #: 보낸 것과 받은 것을 순서대로. `session.closed.transcript_artifact_id` 의 바이트다.
    transcript: bytearray = field(default_factory=bytearray)

    # -- 저수준 입출력 -------------------------------------------------------
    @property
    def _proc(self) -> Any:
        return self.vendored.session_process

    def _stdin_fd(self) -> int:
        return int(self._proc.stdin.fileno())

    def _stdout_fd(self) -> int:
        return int(self._proc.stdout.fileno())

    # -- §4 의 여섯 중 넷 ----------------------------------------------------
    def send(self, data: bytes, *, newline: bool = True) -> int:
        """`send(session_id, data, newline) -> session_seq`.

        **`newline` 은 종류와 무관하게 동일하게 지켜진다** (§4.1-1). 두 종류 모두
        정확히 `b"\\n"` 하나를 덧붙이고, 그 뒤 아무것도 하지 않는다 — pty 에서는 회선
        규율이, `_connect.py` 에서는 `cmd.Cmd` 의 줄 읽기가 그것을 받는다.

        **텍스트 계층을 우회해 `os.write` 로 쓴다.** vendored 함수가 `text=True,
        bufsize=1` 로 `Popen` 을 만들지만(`utils.py:445`), 그 래퍼로 쓰면 인코딩과
        줄바꿈 변환이 끼어들어 `newline` 의 바이트 동일성을 보장할 수 없다.
        """
        if self.closed:
            raise SessionError(f"{self.session_id} 는 이미 닫혔다")
        payload = data + (b"\n" if newline else b"")
        remaining = payload
        while remaining:
            remaining = remaining[os.write(self._stdin_fd(), remaining) :]
        self.seq += 1
        self.bytes_out += len(payload)
        self.transcript += payload
        return self.seq

    def read(self, *, timeout_ms: int, max_bytes: int, quiet_ms: int = 250) -> ReadResult:
        """`read(session_id, timeout_ms, max_bytes) -> observation_id, bytes, closed, timed_out`.

        `observation_id` 는 호출자가 붙인다 — 그것은 봉투의 일이고 이 파일은 봉투를
        모른다.

        의미를 **선언한다** (계약이 정하지 않았다):

        - `closed`  : stdout 이 EOF 를 냈다. 세션 프로세스가 끝났다는 뜻이다.
        - `timed_out`: `timeout_ms` 가 다 지났고 `closed` 도 `max_bytes` 도 아니다.
          바이트를 좀 받고 조용해진 경우는 타임아웃이 **아니다** — 그러면 모든 read 가
          타임아웃이 되어 술어가 무의미해진다.

        **`quiet_ms` 는 G 참조 구현과의 대조에서 채택했다**(`reuse/S4.md` §2). 첫
        판은 `select` 가 한 번 비면 곧장 돌아왔는데, 응답이 두 조각으로 나뉘고 그
        사이가 50ms 만 벌어져도 **부분 읽기**가 된다. 그러면 `nonce=`·`part=` 를
        간헐적으로 놓치고, 그 실패는 배관 결함과 구분되지 않는다.
        """
        if self.closed:
            return ReadResult(b"", closed=True, timed_out=False)
        fd = self._stdout_fd()
        deadline = time.monotonic() + timeout_ms / 1000.0
        buf = bytearray()
        hit_eof = False
        last = time.monotonic()
        while len(buf) < max_bytes:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            if select.select([fd], [], [], min(0.05, left))[0]:
                chunk = os.read(fd, min(65536, max_bytes - len(buf)))
                if not chunk:
                    hit_eof = True
                    break
                buf += chunk
                last = time.monotonic()
            elif buf and (time.monotonic() - last) * 1000 >= quiet_ms:
                # 받을 것을 받고 `quiet_ms` 동안 조용했다. 더 기다리면 매 read 가
                # `timeout_ms` 를 전부 태운다.
                break
        data = bytes(buf)
        self.bytes_in += len(data)
        self.transcript += data
        timed_out = (
            not hit_eof and len(data) < max_bytes and time.monotonic() >= deadline and not data
        )
        return ReadResult(data, closed=hit_eof, timed_out=timed_out)

    def interrupt(self, *, signal_name: str = "SIGINT") -> int | Refusal:
        """`interrupt(session_id, signal) -> session_seq`.

        §4.3 의 두 갈래를 그대로 쓴다.

        - 시그널 의미가 있는 종류(tty): pty 에 `0x03` 을 쓴다. **회선 규율이 전경
          프로세스 그룹에만 SIGINT 를 보내므로 세션이 산다.** 실측: `^C` 뒤 세션 생존,
          다음 명령의 `$?` = 130(진단 2 의 E). `pkill -SIGINT` 를 쓰지 않는다 — E 가
          그것으로 세션을 죽였고 §4.3 이 "세션을 죽이는 것은 위반"이라고 적는다.
        - 없는 종류(순수 소켓): **명시적 거부.** 거부는 만족이다.
        """
        if self.closed:
            return Refusal(f"interrupt:{self.session_id}", "session_closed")
        if not self.kind.signalable:
            return Refusal(f"interrupt:{self.session_id}", "kind_not_signalable")
        if signal_name != "SIGINT":
            return Refusal(f"interrupt:{self.session_id}:{signal_name}", "signal_not_supported")
        os.write(self._stdin_fd(), b"\x03")
        self.seq += 1
        return self.seq

    def snapshot(self, *, ask_container: bool = False) -> Snapshot:
        """`snapshot(session_id) -> live, pid, seq_high, bytes_since_open`.

        **`live` 를 `session_process.poll()` 로 만들지 않는다.** 그 값은 호스트 쪽
        `docker exec` 클라이언트를 보고, §4.1-4 는 그 구현이 "두 값이 우연히 일치하는
        동안에만 맞는다"고 적는다. 여기서 보는 것은 호스트 `/proc` 에 비친 **컨테이너
        안 리더 프로세스**다 — 같은 프로세스를 다른 네임스페이스에서 본 것이므로
        컨테이너의 프로세스 표와 같은 사실이고, 컨테이너에게 묻지 않는다.

        **좀비는 살아 있지 않다** (§4.1-3 과 같은 자세). 상태 0 이 "정상 종료"이자
        "아직 살아 있음"인 waitpid 의 애매함(§4.1-4)은 여기서 발생하지 않는다 —
        프로세스의 존재와 상태를 직접 본다.
        """
        table = host_proc_table()
        me = table.get(self.leader_host_pid)
        live = me is not None and not me.zombie
        self_reported: bool | None = None
        if ask_container and self.leader_container_pid is not None:
            ran = self.cli.run(
                "exec", self.container, "sh", "-c",
                f"test -d /proc/{self.leader_container_pid} && echo live || echo gone",
                check=False,
            )
            self_reported = ran.text.strip() == "live"
        naive = self._proc.poll()
        return Snapshot(
            live=live,
            pid=self.leader_container_pid,
            host_pid=self.leader_host_pid,
            seq_high=self.seq,
            bytes_since_open=self.bytes_in + self.bytes_out,
            live_self_reported=self_reported,
            # `poll()` 이 `None` 이면 "아직 안 거뒀다", 0 이면 "상태 0". 상태값만으로
            # live 를 정하면 두 경우가 같은 값이 된다 — 그것이 [ev §8.3] 이다.
            naive_live_from_status_only=None if naive is None else (naive != 0),
        )

    # -- close --------------------------------------------------------------
    def survivor_pids(self) -> list[int]:
        """**밖에서** 센다. sid 집합으로 걸러 좀비를 뺀다.

        재부모화된 고아도 sid 를 유지하므로 여기 잡힌다(진단 2 의 C). 그것이 §4.1-2 가
        경계를 커널 세션으로 잡은 이유다.
        """
        table = host_proc_table()
        return sorted(
            p.pid
            for p in table.values()
            if p.sid in self.session_sids and not p.zombie
        )

    def close(
        self, *, grace_ms: int = 5000, reason: str = "requested", reap: bool = True
    ) -> CloseResult:
        """`close(session_id, grace_ms) -> transcript_artifact_id, exit_status,
        descendants_killed, survivors`.

        순서는 **부드러운 것부터**다. 그리고 각 단계가 무엇을 남기는지 실측이 정해 줬다
        (진단 2 의 F·G).

        1. 종류의 exit 명령 → stdin 닫기. 이것만으로는 **아무것도 정리되지 않는다** —
           순진한 close 뒤 생존자 3 을 봤다.
        2. 컨테이너 **안에서** sid 로 SIGTERM. 밖에서 죽일 수 없는 이유는 `ctf-host-user` 가
           root 소유 프로세스에 시그널을 보낼 수 없기 때문이고, 컨테이너 안은 uid 0
           끼리라 `--cap-drop ALL` 아래에서도 통한다.
        3. grace 를 기다린 뒤 남은 것에 SIGKILL. **대화형 bash 는 SIGTERM 을 무시한다** —
           2단계만 두면 `killed=3` 인데 생존자가 1 이었다.
        4. `survivors` 를 호스트 `/proc` 에서 다시 센다. 2단계가 돌려준 수를 쓰지 않는다.

        **`reap=False` 는 음성 대조 전용이다.** 2·3 단계를 건너뛰어 §4.1-2 가 거짓인
        스트림을 만든다 — 술어에 이빨이 있는지 재려면 정리를 한 군데 풀고 갈리는지
        봐야 한다. 기본값이 계약의 자세이고, 대조 전용 **경로**를 만들지 않는 것이
        재빌드-4 의 `D-24` 와 같은 이유다 — 갈라 두면 대조가 재는 것이 정리 능력이
        아니라 코드 차이가 된다. 이 인자가 참이 아닌 스트림은 진단이지 증거가 아니다.
        """
        if self.closed:
            raise SessionError(f"{self.session_id} 는 이미 닫혔다")
        started = time.monotonic()

        # 정리 **전에** 두 경계를 함께 잰다. 프로세스 그룹만 정리하는 구현이 무엇을
        # 놓쳤을지가 여기서만 관측된다 — 죽인 뒤에는 둘 다 비어 보인다.
        table = host_proc_table()
        leader = table.get(self.leader_host_pid)
        in_session = [p for p in table.values() if p.sid in self.session_sids]
        pgid_only = (
            tuple(sorted(p.pid for p in in_session if p.pgid == leader.pgid))
            if leader is not None
            else ()
        )
        # **정리 전에** 센다. 정리 뒤에 세면 부모가 죽으면서 좀비가 init 에 거둬진
        # 뒤라 언제나 빈 목록이 나오고, 그 0 은 "좀비가 없었다"가 아니라 "이미
        # 사라진 뒤에 봤다"이다 — 접으면 §4.1-3 을 행사했는지가 기록에서 사라진다.
        zombies = tuple(sorted(p.pid for p in in_session if p.zombie))

        # 1. 부드럽게.
        if self.kind.exit_command:
            with contextlib.suppress(OSError, ValueError):
                self.send(self.kind.exit_command.encode(), newline=True)
        with contextlib.suppress(OSError, ValueError):
            self._proc.stdin.close()
        deadline = started + grace_ms / 1000.0 / 2
        while time.monotonic() < deadline and self.survivor_pids():
            time.sleep(0.05)

        # 2·3. 컨테이너 안에서 sid 로 거둔다.
        killed = 0
        self_reported: int | None = None
        if reap and self.survivor_pids():
            killed = self._reap("TERM")
            deadline = started + grace_ms / 1000.0
            while time.monotonic() < deadline and self.survivor_pids():
                time.sleep(0.05)
            if self.survivor_pids():
                killed += self._reap("KILL")
                time.sleep(0.2)
        self_reported = self._count_in_container()

        # 4. 밖에서 다시 센다. **전송을 끊기 전에** 센다 — 끊은 뒤에 다시 세면
        #    `docker exec` 이 사라지면서 딸려 죽은 것까지 정리 성공으로 세게 되고,
        #    그러면 이 값이 재는 것이 우리 정리가 아니라 전송의 소멸이다.
        #    (G 참조 구현은 끊은 뒤 다시 센다. 그 선택을 채택하지 않았다 —
        #     `reuse/S4.md` §3.)
        final = host_proc_table()
        left = sorted(
            p.pid for p in final.values() if p.sid in self.session_sids and not p.zombie
        )
        self.closed = True
        with contextlib.suppress(Exception):
            self._proc.wait(timeout=2)
        return CloseResult(
            exit_status=self._proc.returncode,
            descendants_killed=killed,
            survivors=len(left),
            survivors_self_reported=self_reported,
            grace_used_ms=int((time.monotonic() - started) * 1000),
            reason=reason,
            transcript=bytes(self.transcript),
            survivor_host_pids=tuple(left),
            zombies_excluded=zombies,
            pgid_only_would_have_killed=pgid_only,
        )

    def _container_sids(self) -> list[int]:
        """호스트 sid 집합을 **컨테이너 시야의** sid 로 옮긴다.

        컨테이너 안에서 kill 하려면 컨테이너의 pid 공간으로 말해야 한다. 옮기는 근거는
        `NSpid` 이고, 그 값은 컨테이너가 아니라 **호스트 커널**이 준다.

        지금 옮길 수 없으면 `open` 에서 잡아 둔 것을 쓴다 — 정리가 끝난 뒤에는 옮길
        대상이 없고, 그때 빈 목록을 돌려주면 "물어봤더니 0" 과 "물을 수 없었다" 가
        같은 값이 된다.
        """
        table = host_proc_table()
        out: set[int] = set()
        for p in table.values():
            if p.sid in self.session_sids and p.in_container:
                leader = table.get(p.sid)
                if leader is not None and leader.container_pid is not None:
                    out.add(leader.container_pid)
        return sorted(out) if out else list(self.container_sids)

    def _reap(self, signal_name: str) -> int:
        """컨테이너 안에서 sid 로 신호를 보내고 **보낸 개수**를 돌려받는다.

        이 값이 `descendants_killed` 다 — **수행한 쪽의 자기 보고**이고, 그래서
        `survivors` 를 이것으로 만들지 않는다.
        """
        sids = self._container_sids()
        if not sids:
            return 0
        wanted = "|".join(str(s) for s in sids)
        script = (
            "n=0; self=$$; "
            'for p in /proc/[0-9]*; do pid=${p#/proc/}; '
            "[ \"$pid\" = \"$self\" ] && continue; "
            "s=$(awk '{i=index($0,\") \"); split(substr($0,i+2),f,\" \"); print f[4]}' "
            "\"$p/stat\" 2>/dev/null) || continue; "
            f'case "|{wanted}|" in *"|$s|"*) '
            f"kill -{signal_name} \"$pid\" 2>/dev/null && n=$((n+1));; esac; "
            "done; echo $n"
        )
        ran = self.cli.run("exec", self.container, "sh", "-c", script, check=False)
        try:
            return int(ran.text.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return 0

    def _count_in_container(self) -> int | None:
        """컨테이너가 자기 표에서 센 생존자. `survivors_self_reported` 로만 쓴다."""
        sids = self._container_sids()
        if not sids:
            return None
        wanted = "|".join(str(s) for s in sids)
        script = (
            "n=0; self=$$; "
            'for p in /proc/[0-9]*; do pid=${p#/proc/}; '
            "[ \"$pid\" = \"$self\" ] && continue; "
            "s=$(awk '{i=index($0,\") \"); split(substr($0,i+2),f,\" \"); "
            "print f[4]\" \"f[1]}' \"$p/stat\" 2>/dev/null) || continue; "
            "set -- $s; "
            f'case "|{wanted}|" in *"|$1|"*) '
            '[ "$2" = "Z" ] || n=$((n+1));; esac; '
            "done; echo $n"
        )
        ran = self.cli.run("exec", self.container, "sh", "-c", script, check=False)
        try:
            return int(ran.text.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return None


# ---------------------------------------------------------------------------
# 레지스트리 — §4.2. 전부 우리 것이다
# ---------------------------------------------------------------------------


class SessionRegistry:
    """`spec.md` §4.2 — 상한·식별자·수명이 우리 것이다.

    **vendored 구현의 상한 1 은 따라오지 않는다.** 그 슬롯은 `swe_env.py:210` 에 있고
    우리는 그 파일을 vendor 하지 않는다(R2-10). 계약이 요구하는 배치가 정확히 이것이다 —
    세션 **객체 하나**를 vendored 구현에서 받고 그 집합을 우리가 관리한다.

    **상한 초과는 거부이고 대기도 조용한 축출도 아니다** (R2-8). 축출이 왜 금지인지는
    X 가 보여 줬다 — 관측 상한 64 에서 세션을 조용히 버렸고, 그것은 거부도 대기도 아닌
    세 번째 동작이었다.
    """

    def __init__(
        self,
        cli: DockerCli,
        container: str,
        *,
        init_pid: int,
        limit: int | None = 2,
        attempt: str = "attempt",
    ) -> None:
        """`init_pid` 는 컨테이너 init 의 **호스트** pid 다 (`Workspace.init_pid`).

        그것으로 이 컨테이너의 containerd-shim 을 찾고, exec 된 세션 리더가 그 shim 의
        자식으로 달린다 — 리더를 특정하는 유일한 외부 단서다. 근거는 §머리말의 sid
        회계 항목과 재빌드-5 진단 3.
        """
        self.cli = cli
        self.container = container
        self.init_pid = init_pid
        self.limit = limit
        self.attempt = attempt
        self.sessions: dict[str, Session] = {}
        self._opened = 0

    # -- 선언 ---------------------------------------------------------------
    def declaration(self) -> list[dict[str, Any]]:
        """통제 블록의 `session_kinds[]`. 선언 없이는 수행 불가 면제가 없다(R3-9)."""
        return kind_declarations()

    def live_ids(self) -> list[str]:
        return sorted(sid for sid, s in self.sessions.items() if not s.closed)

    def get(self, session_id: str) -> Session | Refusal:
        """S6.3 — 모르는 `session_id` 면 거부한다. **조용히 새 세션을 만들지 않는다.**

        계약이 이것을 "상태 유실을 성공처럼 보이게 만드는 주된 경로"라고 적는다.
        """
        found = self.sessions.get(session_id)
        if found is None or found.closed:
            return Refusal(f"session.use:{session_id}", "unknown_session")
        return found

    # -- open ---------------------------------------------------------------
    def open(
        self,
        *,
        kind: str,
        command: Sequence[str] | None = None,
        cwd: str = "/work",
        env: Mapping[str, str] | None = None,
        term: str = "xterm-256color",
        settle_s: float = 5.0,
        banner_timeout_ms: int = 10000,
    ) -> OpenResult | Refusal:
        """`open(command, cwd, env, term, kind) -> session_id, banner_observation_id`.

        vendored `get_interactive_session` 이 하는 일은 argv 조립·`Popen`·시작 지연이고,
        **`session_id` 부여와 배너 보존은 우리 것이다**(`SEAM_IMPLEMENTATION_MAP.md`
        §3.4 의 WRAP). 배너가 살아 있는 것은 패치 **V-06** 때문이다 — upstream 은
        시작 출력을 읽고 버렸다.
        """
        if kind not in KINDS:
            return Refusal(f"session.open:{kind}", "unknown_kind")
        if self.limit is not None and len(self.live_ids()) >= self.limit:
            # 대기도 축출도 아니다.
            return Refusal(f"session.open:{kind}", "concurrency_limit")

        spec = KINDS[kind]
        self._opened += 1
        session_id = f"{self.attempt}-s{self._opened}"
        token = f"{TOKEN_PREFIX}={session_id}"

        # `env` 와 `term` 은 `docker exec -e` 로 줄 수 없다(vendored argv 가 고정이다).
        # 컨테이너 안에서 `env` 로 감싸 같은 결과를 낸다.
        prefix = ["env", f"TERM={term}"] + [f"{k}={v}" for k, v in (env or {}).items()]
        body = list(command) if command else list(spec.argv)
        argv = [*prefix, *body, token]

        # 리더는 **띄우기 전후의 차집합**으로 찾는다. 토큰만으로는 안 된다 —
        # `_connect.py:16` 의 `setproctitle("connect")` 가 `/proc/<pid>/cmdline` 을
        # 덮어써 토큰을 지운다(진단 3 에서 실측). 토큰은 남겨 두되 보조 단서다.
        before = set(host_proc_table())
        vendored = get_interactive_session(self.container, cwd, session_id, argv[0], *argv[1:])
        proc = vendored.session_process
        if proc.poll() is not None:
            # V-06 이 없앤 `RuntimeError` 를 여기서 대신 낸다.
            raise SessionError(
                f"{session_id} 가 시작 직후 죽었다 (rc={proc.returncode}). argv={argv}"
            )

        leader, sids = self._locate(before, settle_s)
        table = host_proc_table()
        container_sids = tuple(
            sorted(
                {
                    p.container_pid
                    for s in sids
                    if (p := table.get(s)) is not None and p.container_pid is not None
                }
            )
        )
        session = Session(
            session_id=session_id,
            kind=spec,
            token=token,
            vendored=vendored,
            container=self.container,
            cli=self.cli,
            leader_host_pid=leader.pid,
            leader_container_pid=leader.container_pid,
            session_sids=sids,
            container_sids=container_sids,
        )
        self.sessions[session_id] = session
        banner = session.read(timeout_ms=banner_timeout_ms, max_bytes=1 << 16).data
        return OpenResult(
            session_id=session_id,
            banner=banner,
            leader_host_pid=leader.pid,
            leader_container_pid=leader.container_pid,
            session_sids=sids,
        )

    def _locate(self, before: set[int], settle_s: float) -> tuple[HostProc, tuple[int, ...]]:
        """세션 리더와 sid 집합을 정한다. **`open` 에서 정한다** (§4.1-2).

        close 시점에 이름으로 찾으면 이미 늦고 고아만 남는다 — E-07 의 진단이 그것이고
        (`ARM_E_REPORT.md` §14.1) 계약이 그 문장을 그대로 옮겼다.

        **찾는 규칙: 이 컨테이너의 shim 아래 새로 생긴 컨테이너 안 프로세스.**
        `docker exec` 로 띄운 프로세스는 컨테이너 init 의 자식이 아니라 containerd-shim
        의 자식으로 달린다(진단 2·3 실측). shim 은 init 의 부모이므로 컨테이너마다
        유일하게 특정되고, 그래서 이 규칙은 다른 컨테이너의 프로세스를 집지 않는다.

        cmdline 의 토큰으로 찾지 **않는다** — `_connect.py` 가 `setproctitle` 로 자기
        cmdline 을 `connect` 로 덮어써 토큰이 사라진다(진단 3). 컨테이너에게 자기 pid 를
        묻지도 않는다 — 그것은 자기 보고다.
        """
        table = host_proc_table()
        me = table.get(self.init_pid)
        if me is None:
            raise SessionError(
                f"컨테이너 init(pid {self.init_pid})이 호스트 /proc 에 없다. "
                "밖에서 볼 수 없으면 §4.1-2·4 를 만족시킬 방법이 없다 (§0.3-2)."
            )
        shim = me.ppid

        deadline = time.monotonic() + settle_s
        leader: HostProc | None = None
        while time.monotonic() < deadline:
            table = host_proc_table()
            fresh = [
                p
                for p in table.values()
                if p.ppid == shim and p.in_container and p.pid not in before
            ]
            if len(fresh) == 1:
                leader = fresh[0]
                kids = [p for p in table.values() if p.ppid == leader.pid]
                sids = {leader.sid} | {k.sid for k in kids}
                # pty 종류는 자식(bash)이 `setsid` 로 새 세션을 연다. 그 자식이 아직
                # 안 떴으면 sid 집합이 리더 하나뿐이고, 그러면 정리가 새어 나간다.
                if len(sids) > 1 or not kids:
                    return leader, tuple(sorted(sids))
            elif len(fresh) > 1:
                raise SessionError(
                    f"shim {shim} 아래 새 프로세스가 둘 이상이다 — 세션을 특정할 수 없다: "
                    f"{[(p.pid, p.cmdline[:40]) for p in fresh]}"
                )
            time.sleep(0.05)
        if leader is None:
            raise SessionError(
                f"shim {shim} 아래에서 세션 리더를 찾지 못했다. 호스트 /proc 을 읽을 수 "
                "없거나 세션이 뜨지 못했다 — 접어서 0 으로 적지 않는다."
            )
        return leader, (leader.sid,)


def kind_declarations() -> list[dict[str, Any]]:
    """통제 블록의 `session_kinds[]` — 레지스트리 **인스턴스가 없어도** 답할 수 있다.

    통제 블록은 컨테이너가 서기 전에 조립되고(그 블록이 스트림의 첫 이벤트다),
    레지스트리는 컨테이너 init 의 pid 를 알아야 만들어진다. 선언은 종류의 성질이지
    인스턴스의 성질이 아니므로 여기 둔다.
    """
    return [k.as_declaration() for k in KINDS.values()]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
