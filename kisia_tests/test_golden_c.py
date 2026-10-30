"""유형 C 골든 드라이버 — 단위·계약 테스트.

**이 파일이 통과한다는 사실은 유형 C가 옳다는 증거가 아니다**(`CLAUDE.md` §6.1-3).
근거는 실제 컨테이너 위의 집합 판정이고, 그 원본은
`docs/rebuild/judgments/2026-08-09-r6-golden-c/` 다.

**잠그는 것**

1. 항아리가 **프로세스를 가로질러** 이어진다 — `HTTPREQ_PY` 를 두 번 **따로** 띄워
   확인한다. 이것이 유형 C 전체가 서 있는 사실이고, `ignore_discard=True` 하나를
   빠뜨리면 조용히 무너진다(fixture 의 `sid` 는 만료 없는 세션 쿠키다).
2. 항아리 **파일을 지우면 상태를 잃는다** — C-4 가 재는 것.
3. `state_locations[]` 가 선언하는 경로와 도구가 **실제로 쓰는** 경로가 같다. 갈리면
   C-4 가 아무것도 읽지 않는 파일을 지우고, 프로브는 통과한 것처럼 보인다.
4. 항아리 digest 가 **요청 주체가 아니라 밖에서** 온다 (`Workspace.get`).
5. `probe_set_id` 가 정상·음성에서 **하나다** (D-32).

**잠그지 못하는 것 — 접지 않고 적는다**

- 위 1·2는 `HTTPREQ_PY` 의 항아리 경로 상수를 임시 경로로 **바꿔** 돌린다. 실제 실행이
  쓰는 경로 상수 자체는 3번이 따로 잠근다.
- 서비스 로그 대조(`status_checked_by_service`)의 **정합**은 여기서 재지 않는다.
  로그를 내는 것은 실제 서비스 컨테이너이고, 그 대조는 판정 스트림에만 있다.
- 프록시 경유 `docker cp`/`docker logs` 의 도달성. 그것은 호스트의 사실이다.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from kisia.runtime.golden_a import Fixture, _shown_of
from kisia.runtime.golden_c import (
    HTTPREQ_PY,
    JAR_PATH,
    PROBES,
    TARGET_ID,
    ServiceLog,
    _control,
    _jar,
    _status_of,
    _target_audit,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs" / "spike" / "fixtures" / "c-web"
PRICING = ROOT / "config" / "pricing.openai.yaml"

SID = "0123456789abcdef0123456789abcdef"


class _Handler(BaseHTTPRequestHandler):
    """`c-web` 의 상태 규칙만 옮긴 최소 서비스. fixture 자체가 아니다."""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def _sid(self) -> str | None:
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "sid":
                return v
        return None

    def _send(self, code: int, body: str, cookie: str | None = None) -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
        # 만료를 주지 않는다 — fixture 와 같은 **세션 쿠키**다. 이것이 요점이다.
        self._send(200, "ok zone=7a2e\n", cookie=f"sid={SID}; Path=/; HttpOnly")

    def do_GET(self) -> None:
        if self._sid() == SID:
            self._send(200, "ok part=d0416b93\n")
        else:
            self._send(401, "err no-session\n")


@pytest.fixture
def service() -> str:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    srv.daemon_threads = True
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def _script(tmp_path: Path) -> tuple[Path, Path]:
    """`HTTPREQ_PY` 의 항아리 경로만 임시 경로로 바꾼 사본. 나머지는 원문 그대로다."""
    jar = tmp_path / "cookies.txt"
    src = HTTPREQ_PY.replace(f'"{JAR_PATH}"', repr(jar.as_posix()))
    assert f'"{JAR_PATH}"' not in src, "항아리 경로를 바꾸지 못했다 — 상수 표기가 달라졌다"
    path = tmp_path / "httpreq.py"
    path.write_text(src, encoding="utf-8")
    return path, jar


def _run(script: Path, *argv: str) -> tuple[int | None, str]:
    """스크립트를 **따로 띄운다.** 한 프로세스 안에서 부르면 항아리가 이어진 이유가
    파일이 아니라 프로세스 수명일 수 있고, 그러면 이 테스트가 아무것도 재지 않는다.
    """
    proc = subprocess.run(
        [sys.executable, str(script), *argv], capture_output=True, check=True
    )
    return _status_of(proc.stderr.decode()), proc.stdout.decode("utf-8", "replace")


@pytest.mark.contract
def test_jar_carries_the_cookie_across_separate_processes(
    tmp_path: Path, service: str
) -> None:
    """진단 1 — 유형 C 전체가 이 사실 위에 선다."""
    script, jar = _script(tmp_path)

    status, body = _run(script, "POST", f"{service}/login", "user=analyst&pass=north-42")
    assert status == 200
    assert "zone=7a2e" in body
    assert jar.is_file(), "항아리 파일이 만들어지지 않았다"

    status, body = _run(script, "GET", f"{service}/vault")
    assert status == 200, "새 프로세스가 쿠키를 싣지 못했다 — ignore_discard 를 잃었는가"
    assert "part=d0416b93" in body


@pytest.mark.contract
def test_dropping_the_jar_file_loses_the_state(tmp_path: Path, service: str) -> None:
    """진단 4 / C-4 — 버릴 대상이 실제로 있고, 버리면 유실이 관측된다 (S6.5 (a))."""
    script, jar = _script(tmp_path)
    _run(script, "POST", f"{service}/login", "user=analyst&pass=north-42")
    before = jar.read_bytes()

    jar.unlink()
    status, body = _run(script, "GET", f"{service}/vault")
    assert status == 401
    assert "no-session" in body

    # 그리고 **파일 부재와 빈 항아리는 다른 상태다** — 요청 뒤 빈 항아리가 다시 생긴다.
    assert jar.is_file()
    assert jar.read_bytes() != before
    assert b"sid" not in jar.read_bytes()


@pytest.mark.unit
def test_the_declared_state_location_is_the_path_the_tool_uses() -> None:
    """선언과 구현이 갈리면 C-4 는 아무것도 읽지 않는 파일을 지운다.

    그러면 프로브는 통과한 것처럼 보이고 유실은 다른 이유로 일어난다 — 재빌드-5 경고 6
    ("문면과 구현이 같은 구멍을 공유하면 리뷰로는 잡히지 않는다")이 걸리는 자리다.
    """
    assert f'"{JAR_PATH}"' in HTTPREQ_PY
    assert JAR_PATH.startswith("/"), "R3-9 는 파일 소재를 **절대 경로**로 요구한다"


@pytest.mark.unit
def test_jar_digest_comes_from_outside_and_absent_is_not_empty() -> None:
    """항아리 digest 는 `Workspace.get` 이 준다 — 요청을 보낸 주체가 아니다."""

    class _Ws:
        def __init__(self, raw: bytes | None) -> None:
            self.raw = raw
            self.asked: list[str] = []

        def get(self, path: str) -> bytes | None:
            self.asked.append(path)
            return self.raw

    missing = _Ws(None)
    assert _jar(missing) == ("absent", None)
    assert missing.asked == [JAR_PATH]

    empty = _Ws(b"")
    digest, size = _jar(empty)
    assert size == 0
    assert digest != "absent", "부재와 빈 파일을 접지 않는다 (CLAUDE.md §6)"


@pytest.mark.unit
def test_service_log_returns_only_the_new_entries() -> None:
    """밖에서 본 상태를 요청과 짝지으려면 **새로 붙은 줄만** 세야 한다."""
    lines = [
        '172.20.0.2 - - [08/Aug/2026 15:46:23] "POST /login HTTP/1.1" 200 -',
        '172.20.0.2 - - [08/Aug/2026 15:46:23] "POST /arm HTTP/1.1" 200 -',
        '172.20.0.2 - - [08/Aug/2026 15:46:24] "GET /vault HTTP/1.1" 401 -',
    ]

    class _Ran:
        def __init__(self, err: str) -> None:
            self.rc = 0
            self.err = err

    class _Cli:
        def __init__(self) -> None:
            self.n = 0

        def run(self, *args: str, check: bool = True) -> _Ran:
            return _Ran("\n".join(lines[: self.n]) + "\n")

    cli = _Cli()
    log = ServiceLog(cli, "svc")

    cli.n = 1
    assert [r["status"] for r in log.new_entries(tries=1)] == ["200"]
    cli.n = 3
    fresh = log.new_entries(tries=1)
    assert [(r["method"], r["path"], r["status"]) for r in fresh] == [
        ("POST", "/arm", "200"),
        ("GET", "/vault", "401"),
    ]
    assert log.new_entries(tries=1) == []


@pytest.mark.unit
def test_status_of_reads_the_worker_report() -> None:
    assert _status_of("STATUS 403\n") == 403
    assert _status_of("") is None


@pytest.mark.unit
def test_target_audit_reads_the_stream_not_a_constant(tmp_path: Path) -> None:
    """C-2 — 우리가 적은 상수를 우리가 세면 '선언된 대상에만 붙었다'의 증거가 아니다."""
    stream = tmp_path / "s.jsonl"
    rows = [
        {"type": "http.exchanged", "target_id": TARGET_ID, "host": "kisia-fix-c:8080"},
        {"type": "http.exchanged", "target_id": TARGET_ID, "host": "kisia-fix-c:8080"},
        {"type": "state.snapshot", "turn": 1},
    ]
    stream.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8", newline="\n"
    )
    audit = _target_audit(stream)
    assert audit["only_declared_target"] is True
    assert audit["target_ids"] == {TARGET_ID: 2}

    rows.append({"type": "http.exchanged", "target_id": "elsewhere", "host": "1.1.1.1:80"})
    stream.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8", newline="\n"
    )
    assert _target_audit(stream)["only_declared_target"] is False


@pytest.mark.unit
def test_control_block_declares_no_sessions_and_carries_provenance() -> None:
    block = _control(
        fixture=Fixture(FIXTURE),
        pricing=PRICING,
        image="sha256:worker",
        service_image="sha256:service",
        host_id="test",
        limit=4096,
        probes=PROBES,
    )
    values = block.values
    # 유형 C는 세션을 열지 않는다. `null` 은 "상한 없음"이고 미선언과 다르다 (§2.1).
    assert values["session_concurrency_limit"] is None
    assert values["session_kinds"] == []
    # 개정 S-4 — 매니페스트에서 읽는다. 조립기 기본값에 기대지 않는다.
    assert values["provenance"] == "synthetic"
    assert values["flag_format"] == "kisia{...}"
    # 철수 임계치는 **전역 누계**다 (R3-6). 유형 C의 경로에 V-06 이 없어도 접지 않는다.
    assert values["structural_patches"] == ["V-06"]


@pytest.mark.unit
def test_probe_set_id_is_one_for_the_type() -> None:
    """D-32 — 프로브 집합은 스트림의 서술이 아니라 run 의 통제 조건이다.

    음성 스트림에만 `C-4` 를 선언하면 `probe_set_id` 가 갈리고 §6.4 가 그 집합을
    "무엇을 쟀는지 정의되지 않는다"로 표시한다(재빌드-5 실측).
    """
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["probes"] == PROBES
    assert "C-4" in PROBES


@pytest.mark.contract
def test_golden_c_does_not_import_the_vendored_tree() -> None:
    """유형 C는 vendored 코드를 쓰지 않는다 — 통제 블록이 `vendored_components: []` 다.

    `golden_b` 에서 무엇을 가져오면 그 모듈이 `session.py` 를 통해 vendored 트리를
    **import 시점에** 끌고 오고, 그러면 선언과 모듈 그래프가 어긋난다.

    **실행이 잡은 결함이다** — 첫 판이 호스트에서 `ModuleNotFoundError: vendor` 로
    죽었다. 린트·타입·워크스테이션 테스트가 전부 통과하는 상태였다(경고 6).

    **별개 프로세스에서 본다.** 이 파일이 이미 다른 모듈을 열어 두었으면 `sys.modules`
    가 오염돼 아무것도 재지 못한다.
    """
    probe = (
        "import sys, kisia.runtime.golden_c;"
        "print([m for m in sys.modules if m.split('.')[0] == 'vendor'])"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, check=True, cwd=ROOT
    )
    assert proc.stdout.decode().strip() == "[]"


@pytest.mark.unit
def test_shown_of_picks_the_named_observation(tmp_path: Path) -> None:
    """재빌드-6 이 `golden_b` 에서 `golden_a` 로 옮긴 함수. 동작은 그대로여야 한다."""
    stream = tmp_path / "s.jsonl"
    rows = [
        {"type": "observation.recorded", "observation_id": "obs-0001", "shown": "zone=7a2e"},
        {"type": "observation.recorded", "observation_id": "obs-0002", "shown": "ok armed"},
    ]
    stream.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8", newline="\n"
    )
    assert _shown_of(stream, "obs-0001") == "zone=7a2e"
    assert _shown_of(stream, "obs-0002") == "ok armed"
    assert _shown_of(stream, "obs-0009") == ""
