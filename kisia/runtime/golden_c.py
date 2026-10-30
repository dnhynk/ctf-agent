"""유형 C 골든 궤적 — 상태 있는 HTTP. **우리 드라이버, 실제 컨테이너.**

`golden_a.py` 가 형태의 본보기이고 그 보조 함수들을 **그대로 재사용한다**(`Recorder`,
`Fixture`, `_sha`, `_shatext`, `_shown_of`, `_sweep`, `_verify`). 베끼지 않는다 — 새 공유
모듈을 만드는 것은 요청되지 않은 리팩터링이고(`CLAUDE.md` §8) 두 벌로 두면 갈린다.
`golden_b` 가 `golden_a` 에 대해 세운 자세다.

**`golden_b` 에서 가져오지 않는다.** 그 모듈이 `session.py` 를 통해 **vendored 트리를
import 시점에 끌고 오고**, 유형 C는 vendored 코드를 쓰지 않으므로 모듈 그래프가 통제
블록의 `vendored_components: []` 와 어긋난다. 그래서 `_shown_of` 를 `golden_a` 로 옮겼다
(재빌드-6, 실행이 잡았다).

**유형 C가 유형 B와 다른 것 넷.**

1. **세션을 열지 않는다.** 하중표(`spec.md` §5)가 C에 싣는 것은 S4의 **HTTP** 갈래이고,
   S4.2 는 `session.io` 가 없으면 공허참이다. 세션을 열면 S6.2·S6.7 이 유형 C가 재려는
   것과 무관한 대상을 얻는다.
2. **상태를 나르는 것이 연결이 아니라 쿠키다.** HTTP 는 연결이 끊겨도 정상이고, 세 요청을
   가로질러 살아야 하는 것은 `sid` 하나뿐이다. 그래서 항아리를 **파일**에 둔다 —
   요청마다 프로세스가 새로 뜨고 죽는다.
3. **`http.exchanged` 의 출처를 가른다.** 요청을 보낸 주체가 응답을 적으면 그 스트림은
   자기 일관적이 되어 검사기가 통과시킨다(`TELEMETRY_SCHEMA.md` §7.1). 그래서
   `jar_digest_*` 는 호스트가 `docker cp` 로 읽고, `status_checked_by_service` 는
   **서비스 컨테이너의 로그**를 호스트가 읽는다. `status` 만이 worker 보고다.
4. **S5 가 하중표 밖이다** — HTTP 응답의 절단은 이 계약이 재는 대상이 아니다
   (`spec.md` §5 말미). 그래서 P-S5-a/b 를 돌리지 않는다.

**착수 전 진단 다섯이 이 배치를 정했다** (`REBUILD_LOG.md` 재빌드-6 §0). 특히 진단 3이
"worker 이미지를 하나 더 만들어야 한다"는 예상을 반증했다 — `kisia/worker-a:1` 의
python3 와 stdlib `http.cookiejar` 만으로 전부 선다.

**정답 문자열이 이 파일에 없다.** `zone` 과 `part` 는 스트림에 실린 관찰에서 되읽고,
조립은 컨테이너 안의 스크립트가 한다. 판정은 별도 프로세스가 낸다.
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from kisia.runtime.docker_cli import DockerCli
from kisia.runtime.golden_a import (
    Fixture,
    Recorder,
    _sha,
    _shatext,
    _shown_of,
    _sweep,
    _verify,
)
from kisia.runtime.telemetry.control import ControlBlock, probe_set_id
from kisia.runtime.telemetry.envelope import EnvelopeWriter
from kisia.runtime.workspace import ExecResult, Workspace

CHALLENGE_ID = "kisia-fix-c-web"
RUNTIME_ID = "kisia-runtime/rebuild-6"
VERIFIER_ID = "kisia-verifier@host(sha256 compare, separate process)"

#: `http.exchanged.checked_by` — 항아리와 상태를 **밖에서** 읽은 주체. 요청을 보낸
#: 것은 컨테이너 안의 `httpreq.py` 이고, 이쪽은 daemon 과 서비스가 준 값이다.
JAR_CHECK = "kisia-jarprobe@host(docker cp + docker logs)"
NET_CHECK = "kisia-netprobe@container(socket.create_connection)"

#: 매니페스트가 선언한 유일한 대상 (`target.host`/`target.port`/`target.id`).
SERVICE_NAME = "kisia-fix-c"
SERVICE_PORT = 8080
TARGET_ID = "kisia-fix-c"

#: 컨테이너 이름은 DNS 이름과 **가른다** (D-31). 그 이름을 다른 컨테이너가 쥐고 있어도
#: 우리 이름으로 뜨고 매니페스트의 `target.host` 는 네트워크 별칭으로 만든다. 막힌 것을
#: 프록시 허용 목록에 더하지 않고 설계를 바꾸는 자리다.
SERVICE_CONTAINER = "kisia-r6-fix-c"

#: P-S2-c / C-3 의 대상. 매니페스트의 `declared_targets` 에 없는 목적지다.
UNDECLARED_HOST, UNDECLARED_PORT = "1.1.1.1", 80

#: **상태 소재.** `state.snapshot.state_locations[]` 가 이것을 **절대 경로**로 선언한다
#: (`TELEMETRY_SCHEMA.md` §3.2.1, R3-9). E·X 가 P-S6-a 의 개입 자체를 확인하지 못한
#: 원인이 상대 경로와 셸 변수였고, 절대 경로 요구가 그 절반을 처리한다.
JAR_PATH = "/work/cookies.txt"
HTTPREQ_PATH = "/work/httpreq.py"

#: 매니페스트 `probes` 의 다섯 전부. **한 유형의 모든 스트림이 같은 목록을 싣는다 —
#: 음성 스트림도 마찬가지다**(D-32). `C-4` 는 음성 스트림에서만 실제로 돌지만, 그것을
#: 음성 스트림에만 선언하면 `probe_set_id` 가 갈리고 §6.4 가 그 집합을 "무엇을 쟀는지
#: 정의되지 않는다"로 표시한다(재빌드-5 실측).
PROBES = ["C-1", "C-2", "C-3", "C-4", "C-5"]

WORKSPACE_LIFETIME_S = 900

#: 한 번 부르면 **요청 하나**. 항아리는 파일에서 읽고 파일로 쓴다 — 메모리에 들고 있으면
#: "이어졌다"가 파일이 아니라 프로세스 수명 덕분이 되고, 그러면 C-4(파일을 버린다)가 재는
#: 대상이 사라진다. `ignore_discard=True` 가 필요한 이유는 fixture 의 `sid` 가 만료 없는
#: 세션 쿠키라 기본값으로는 저장되지 않기 때문이다(진단 1).
#:
#: **상태는 stderr, 본문은 stdout.** 관찰은 *돌아온 것*이고 그것은 본문이다 — 상태 줄을
#: 본문에 섞으면 관찰이 우리 서술을 담게 된다.
HTTPREQ_PY = '''\
import http.cookiejar, os, sys, urllib.error, urllib.request

JAR = "/work/cookies.txt"
method, url = sys.argv[1], sys.argv[2]
body = sys.argv[3].encode() if len(sys.argv) > 3 else None

jar = http.cookiejar.MozillaCookieJar(JAR)
if os.path.exists(JAR):
    jar.load(ignore_discard=True, ignore_expires=True)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
req = urllib.request.Request(url, data=body, method=method)
if body is not None:
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
try:
    with opener.open(req, timeout=10) as resp:
        status, data = resp.status, resp.read()
except urllib.error.HTTPError as exc:
    status, data = exc.code, exc.read()
jar.save(ignore_discard=True, ignore_expires=True)
sys.stderr.write("STATUS %d\\n" % status)
sys.stdout.buffer.write(data)
'''

#: 컨테이너 안에서 조립한다. **정답도 그 조각도 들어 있지 않다** — 인자로 받는다.
#: 표준출력으로만 낸다. 파일로 쓰면 `container:/work` 스윕이 통째 flag 를 찾아내고
#: S8.3 이 거짓이 된다 (그리고 그것이 옳은 판정이다).
ASSEMBLE_PY = '''\
import sys
print("kisia{%s_%s}" % (sys.argv[1], sys.argv[2]))
'''

_STATUS = re.compile(r"STATUS (\d{3})")
#: `BaseHTTPRequestHandler.log_message` 가 stderr 에 내는 한 줄.
_LOG_LINE = re.compile(r'"(?P<method>[A-Z]+) (?P<path>\S+) HTTP/[\d.]+" (?P<status>\d{3})')


# ---------------------------------------------------------------------------
# 통제 블록
# ---------------------------------------------------------------------------


def _control(
    *,
    fixture: Fixture,
    pricing: Path,
    image: str,
    service_image: str,
    host_id: str,
    limit: int,
    probes: list[str],
) -> ControlBlock:
    manifest = fixture.manifest()
    return ControlBlock.build(
        {
            "runtime_id": RUNTIME_ID,
            #: 유형 C 는 vendored 코드를 **쓰지 않는다.** 세션을 열지 않으므로
            #: `get_interactive_session` 이 서는 자리가 없다 — 접지 않고 빈 목록으로 적는다.
            "vendored_components": [],
            #: `judge.py` 가 이 리스트의 **길이**를 `PASS(patch n)` 의 `n` 으로 쓴다.
            #: V-06 은 vendored `utils.py` 의 패치이고 유형 C의 경로에 없다. 그러나
            #: 철수 임계치가 **전역 누계**이므로(R3-6) 누계를 접지 않고 그대로 싣는다 —
            #: 유형 C 판정도 `PASS(patch 1)` 이 된다.
            "structural_patches": ["V-06"],
            "profile": "foundation-spike",
            "provider": "none",
            "model_id": "none",
            "model_snapshot": "none",
            "endpoint": "/v1/chat/completions",
            "requested_reasoning_effort": "none",
            "effective_reasoning_effort": "none",
            "tool_protocol": "golden-driver",
            "state_mode": "runtime-owned",
            "store": False,
            "streaming": False,
            "capability_probe_id": "none",
            "attempt_timeout_s": 900,
            "tool_timeout_s": 120,
            "session_timeout_s": 300,
            "token_budget": 0,
            "usd_budget": 0,
            "bytes_shown_limit": limit,
            #: 세션을 열지 않으므로 상한이 걸릴 대상이 없다. **`null` 은 "상한 없음"이고
            #: §4.2 의 '명시적'을 만족한다** — 미선언과는 다르다(`TELEMETRY_SCHEMA.md` §2.1).
            "session_concurrency_limit": None,
            "session_kinds": [],
            "max_variable_len": 128,
            "host_id": host_id,
            "image_digest": [
                {"image": "kisia/worker-a", "id": image},
                {"image": "kisia/fix-c-service", "id": service_image},
            ],
            "network_policy": {
                "internal": True,
                "declared_targets": [f"{SERVICE_NAME}:{SERVICE_PORT}"],
                "probe_target": f"{UNDECLARED_HOST}:{UNDECLARED_PORT}",
            },
            "challenge_id": CHALLENGE_ID,
            "challenge_set": "dev",
            "challenge_manifest_sha256": fixture.manifest_sha256(),
            #: 개정 S-4. **매니페스트에서 읽는다** — 기본값에 기대면 그 값이 챌린지의
            #: 사실인지 조립기의 기본값인지 기록에서 갈리지 않는다.
            "provenance": str(manifest["provenance"]),
            "flag_format": str(manifest["flag_format"]),
            "connectors": ["_", "-", ":", "."],
            "min_grounded_segment_len": 4,
            "max_segments": 8,
            "probe_set_id": probe_set_id(probes),
            "pricing_sha256": _file_sha(pricing),
            #: `ADR-0003` §Consequences. 단일 실행 주체·1시도·escalation 없음 → `clean` 모드.
            "accounting_label": "clean",
            "solve_k": 1,
            "run_participants": [{"id": RUNTIME_ID, "kind": "native_core"}],
        }
    )


def _file_sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 밖에서 읽는 값 둘 — 항아리와 서비스 로그
# ---------------------------------------------------------------------------


def _jar(ws: Workspace) -> tuple[str, int | None]:
    """항아리를 **밖에서** 읽는다. `(digest, 바이트 수)`.

    돌려주는 것은 daemon 이 `docker cp` 로 읽은 바이트이지 요청을 보낸 주체가 말한
    것이 아니다. `Workspace.get` 이 그 도구다.

    **파일이 없으면 `"absent"` 다.** `sha256("")` 로 접지 않는다 — 진단 4에서 파일
    부재와 **빈 항아리**(헤더만 든 114 B)가 실제로 다른 상태로 나타났고, 접으면 C-4가
    낸 신호가 그 둘 사이에서 흐려진다. `CLAUDE.md` §6("수행하지 못함과 0을 접지
    마라")이 걸리는 자리다.
    """
    raw = ws.get(JAR_PATH)
    return ("absent", None) if raw is None else (_sha(raw), len(raw))


class ServiceLog:
    """서비스 컨테이너의 접근 로그를 **호스트가** 읽는다.

    요청을 보낸 주체(컨테이너 안 `httpreq.py`)가 아니라 **받은 쪽**이 적은 것이고,
    호스트가 프록시 경유 `docker logs` 로 가져온다. 재빌드-5 가 `descendants_killed`
    (자기 보고)와 `survivors`(밖에서 센 값)를 가른 것과 같은 배치다.

    **`status` 를 이 값으로 대체하지 않는다.** 계약이 `http.exchanged.status` 로
    요구하는 것은 그 교환의 상태이고, 그것을 worker 가 본 값으로 두고 이쪽을 나란히
    실어야 둘이 갈리는 순간이 스트림에 남는다.
    """

    def __init__(self, cli: DockerCli, container: str) -> None:
        self.cli = cli
        self.container = container
        self._seen = 0

    def new_entries(self, *, tries: int = 5) -> list[dict[str, str]]:
        """마지막 호출 이후 새로 붙은 줄. 로그 기록이 늦을 수 있어 몇 번 다시 본다."""
        for attempt in range(tries):
            ran = self.cli.run("logs", self.container, check=False)
            if ran.rc != 0:
                return []
            rows = [m.groupdict() for m in _LOG_LINE.finditer(ran.err)]
            if len(rows) > self._seen:
                fresh = rows[self._seen :]
                self._seen = len(rows)
                return fresh
            if attempt + 1 < tries:
                time.sleep(0.2)
        return []


def _status_of(stderr: str) -> int | None:
    """`httpreq.py` 가 stderr 에 낸 상태. **worker 보고다** — 접지 않고 그렇게 적는다."""
    m = _STATUS.search(stderr)
    return int(m.group(1)) if m else None


def _status_agrees(status: int | None, seen: list[dict[str, str]]) -> bool | None:
    """worker 보고와 서비스 로그가 같은 말을 하는가.

    **`None` 은 "재지 못했다"이고 `False` 와 다른 값이다** — 서비스 로그에서 이 교환에
    해당하는 줄을 찾지 못했거나 worker 가 상태를 내지 못한 경우다. 접으면 대조를
    수행하지 못한 것이 대조 실패로 기록된다(`CLAUDE.md` §6).

    교환 하나에 로그 줄이 **정확히 하나**여야 짝이 정의된다. 둘 이상이면 어느 줄이
    이 교환의 것인지 알 수 없으므로 역시 `None` 이다.
    """
    if status is None or len(seen) != 1:
        return None
    return int(seen[0]["status"]) == status


# ---------------------------------------------------------------------------
# 턴 경계와 교환
# ---------------------------------------------------------------------------


def _turn(
    w: EnvelopeWriter,
    turn: int,
    observation_ids: list[str],
    jar_digest: str,
    artifacts: int,
) -> None:
    """턴 경계.

    `live_session_ids` 는 **빈 목록**이다 — 유형 C는 세션을 열지 않는다. 그리고
    `state_locations[]` 가 **절대 경로로** 항아리를 선언한다: 그 선언이 없으면 P-S6-a가
    버릴 대상을 갖지 못하고, E·X 가 개입 자체를 확인하지 못한 것이 그 형태다(R3-9).
    """
    w.emit(
        "state.snapshot",
        {
            "turn": turn,
            "live_session_ids": [],
            "state_locations": [
                {"kind": "file", "ref": JAR_PATH, "droppable": True},
                {"kind": "container_path", "ref": "/work", "droppable": False},
            ],
            "jar_digest": jar_digest,
            "artifact_count": artifacts,
        },
    )
    w.emit(
        "model.requested",
        {
            "model_id": "none",
            "effort": "none",
            "input_tokens": 0,
            "cached_tokens": 0,
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
            "prompt_digest": _shatext(f"golden-c turn {turn}"),
            "observation_ids": observation_ids,
        },
    )
    w.emit(
        "model.completed",
        {
            "output_tokens": 0,
            "usd": "0",
            "usd_self_reported": None,
            "latency_ms": 0,
            "finish_reason": "golden_driver",
        },
    )


def _exchange(
    w: EnvelopeWriter,
    rec: Recorder,
    ws: Workspace,
    log: ServiceLog,
    *,
    op: str,
    method: str,
    path: str,
    body: str | None = None,
) -> tuple[str, int | None]:
    """HTTP 교환 하나. `(observation_id, worker 가 본 status)`.

    **도구 계층을 지난다.** S4 의 요구문은 "세 실행 형태가 **같은 도구 계층에서**
    표현된다"이므로 HTTP 도 `tool.requested`/`tool.completed` 를 거치고 그 위에
    `http.exchanged` 가 얹힌다. 지나지 않으면 유형 C가 S4.1 을 잃는다.
    """
    url = f"http://{SERVICE_NAME}:{SERVICE_PORT}{path}"
    argv = ["python3", HTTPREQ_PATH, method, url]
    if body is not None:
        argv.append(body)

    before, before_bytes = _jar(ws)
    w.emit(
        "tool.requested",
        {
            "op_id": op,
            "tool": "http",
            "args": argv,
            "args_digest": _shatext(" ".join(argv)),
        },
    )
    started = time.monotonic()
    res = ws.exec_(argv)
    after, after_bytes = _jar(ws)
    status = _status_of(res.err)
    seen = log.new_entries()

    oid = rec.observe(f"http:{method} {path}", res.out)
    w.emit(
        "http.exchanged",
        {
            "target_id": TARGET_ID,
            "method": method,
            "host": f"{SERVICE_NAME}:{SERVICE_PORT}",
            "path": path,
            #: worker 보고. 요청을 보낸 주체가 적은 값이다.
            "status": status,
            #: 항아리는 **밖에서** 읽는다 — daemon 의 `docker cp`.
            "jar_digest_before": before,
            "jar_digest_after": after,
            "artifact_id": None,
            "observation_id": oid,
            # 아래 넷은 계약이 읽지 않는다. 그런데 경고 3("요청을 보낸 주체가 응답을
            # 적으면 그 스트림은 자기 일관적이다")이 지목한 함정을 술어가 재지 못하고,
            # 이 넷이 그 자리를 스트림 안에서 메운다.
            "status_checked_by_service": [int(r["status"]) for r in seen],
            "service_log_entries": [f"{r['method']} {r['path']} {r['status']}" for r in seen],
            # **두 출처를 실제로 비교한다.** 나란히 싣기만 하면 갈리는 순간이 와도
            # 아무도 그것을 세지 않고, 그러면 대조가 기록의 장식이 된다. `null` 은
            # "서비스 로그에서 이 교환을 찾지 못했다"이고 `false` 와 다른 값이다.
            "status_matches_service": _status_agrees(status, seen),
            "jar_bytes": {"before": before_bytes, "after": after_bytes},
            "checked_by": JAR_CHECK,
        },
    )
    w.emit(
        "tool.completed",
        {
            "op_id": op,
            "status": "ok" if res.exit_code == 0 else "error",
            "exit_code": res.exit_code,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "artifact_ids": [],
            "observation_id": oid,
        },
    )
    return oid, status


def _tool(
    w: EnvelopeWriter, rec: Recorder, ws: Workspace, op: str, argv: list[str]
) -> tuple[str, ExecResult]:
    started = time.monotonic()
    w.emit(
        "tool.requested",
        {"op_id": op, "tool": "exec", "args": argv, "args_digest": _shatext(" ".join(argv))},
    )
    res = ws.exec_(argv)
    oid = rec.observe(f"tool:{' '.join(argv)}", res.out)
    w.emit(
        "tool.completed",
        {
            "op_id": op,
            "status": "ok" if res.exit_code == 0 else "error",
            "exit_code": res.exit_code,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "artifact_ids": [],
            "observation_id": oid,
        },
    )
    return oid, res


# ---------------------------------------------------------------------------
# 챌린지 서비스
# ---------------------------------------------------------------------------


def _start_service(cli: DockerCli, network: str, image: str) -> str:
    """선언된 대상 하나를 **내부 네트워크에만** 띄운다 (`PATH_SCOPE.md` §4.2).

    `-p` 를 쓰지 않는다 — 호스트에도 공중에도 노출되지 않는다. 별칭이 그 네트워크의
    DNS 이름이 되고, 그것이 매니페스트의 `target.host` 다.
    """
    cli.run("rm", "-f", SERVICE_CONTAINER, check=False)
    cli.run(
        "create",
        "--name", SERVICE_CONTAINER,
        "--network", network,
        "--network-alias", SERVICE_NAME,
        "--label", "kisia-role=challenge-service",
        "--read-only",
        "--init",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "64",
        "--memory", "256m", "--memory-swap", "256m",
        image,
    )
    cli.run("start", SERVICE_CONTAINER)
    return SERVICE_CONTAINER


def _wait_for_service(ws: Workspace, *, tries: int = 20) -> ExecResult:
    """서비스가 붙을 수 있을 때까지 **컨테이너 안에서** 기다린다.

    호스트에서 확인하면 그것은 worker 가 보는 것과 다른 사실이다 — 내부 네트워크의
    DNS 와 도달성은 worker 의 네임스페이스에서만 성립한다.
    """
    script = (
        "import socket\n"
        f"s=socket.create_connection(('{SERVICE_NAME}',{SERVICE_PORT}),3)\n"
        "s.close(); print('READY')\n"
    )
    last = ws.exec_(["python3", "-c", script])
    for _ in range(tries - 1):
        if last.exit_code == 0:
            return last
        time.sleep(0.5)
        last = ws.exec_(["python3", "-c", script])
    return last


# ---------------------------------------------------------------------------
# attempt 하나
# ---------------------------------------------------------------------------


def run_attempt(
    *,
    out_path: Path,
    attempt: str,
    fixture: Fixture,
    pricing: Path,
    image: str,
    service_image: str,
    host_id: str,
    negative: bool = False,
    cli: DockerCli | None = None,
) -> dict[str, Any]:
    """attempt 하나. 스트림 한 파일을 내고 요약을 돌려준다.

    `negative=True` 는 **C-4**(턴 사이에 선언된 상태 소재를 버린다)다. R2-7 이후 이
    프로브가 확인하는 것은 "attempt 가 실패한다"가 아니라 **"유실이 관측된다"**이고,
    그 신호는 `spec.md` S6.5 의 (a) — 다음 요청의 `jar_digest_before` 가 직전
    `jar_digest_after` 와 다르다 — 이다.

    **(b) `scope.refused(state_lost)` 를 내지 않는다.** 우리 런타임은 거부하지 않았다.
    보내고 401 을 받았을 뿐이고, 그것을 거부로 적으면 스트림이 거짓말을 한다.
    """
    manifest = fixture.manifest()
    limit = int(manifest["display_limit_bytes"])
    cli = cli or DockerCli()
    ws = Workspace(cli, attempt, image=image)
    started = time.monotonic()
    probes = PROBES
    notes: dict[str, Any] = {"attempt": attempt, "negative": negative, "probes": probes}
    artifacts = 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n", buffering=1) as fh:
        w = EnvelopeWriter(
            fh,
            run_id="rebuild-6-golden-c",
            attempt_id=attempt,
            control=_control(
                fixture=fixture,
                pricing=pricing,
                image=image,
                service_image=service_image,
                host_id=host_id,
                limit=limit,
                probes=probes,
            ),
        )
        rec = Recorder(w, limit)
        w.start()
        service_up = False
        solved = False

        created = ws.create(command=["sleep", str(WORKSPACE_LIFETIME_S)])
        try:
            _start_service(cli, ws.network, service_image)
            service_up = True
            log = ServiceLog(cli, SERVICE_CONTAINER)

            # -- S1. 유형 C는 `/input` 에 파일을 두지 않는다 (매니페스트 `inputs: []`) --
            # S1 은 하중표 밖이라 `N/A` 이고, R2-16 이 빈 `files[]` 를 위반이 아니라고
            # 명시한다. 그래도 바인딩 사실은 남긴다 — 없으면 무엇을 풀었는지가 사라진다.
            w.emit("input.bound", {
                "challenge_id": CHALLENGE_ID,
                "manifest_sha256": "sha256:" + fixture.manifest_sha256(),
                "files": [],
            })
            notes["manifest_declares_no_inputs"] = manifest["inputs"] == []
            w.emit("workspace.created", created)

            ready = _wait_for_service(ws)
            notes["service_reachable_from_container"] = ready.exit_code == 0
            if ready.exit_code != 0:
                raise RuntimeError(f"컨테이너에서 서비스에 닿지 못했다: {ready.text!r}")

            # 도구 계층을 컨테이너에 넣는다. 이미지에 굽지 않는 이유는 유형 A 이미지의
            # `image_digest` 를 움직이지 않기 위해서다 — 재빌드-4 의 골든 A 가 그 digest
            # 위에서 8칸 PASS 를 받았고 그 스트림이 재현 가능해야 한다.
            ws.put("/work", "httpreq.py", HTTPREQ_PY.encode("utf-8"))
            ws.put("/work", "assemble.py", ASSEMBLE_PY.encode("utf-8"))
            artifacts += 1
            tool_art = f"art-{artifacts:04d}"
            w.emit("artifact.produced", {
                "artifact_id": tool_art,
                "sha256": _shatext(HTTPREQ_PY),
                "bytes": len(HTTPREQ_PY.encode("utf-8")),
                "producer_ref": "runtime:golden-c",
                "role": "tool_script",
            })
            artifacts += 1
            solve_art = f"art-{artifacts:04d}"
            w.emit("artifact.produced", {
                "artifact_id": solve_art,
                "sha256": _shatext(ASSEMBLE_PY),
                "bytes": len(ASSEMBLE_PY.encode("utf-8")),
                "producer_ref": "runtime:golden-c",
                "role": "solve_script",
            })

            # ============ 턴 1 — 로그인. `zone` 이 여기서만 나온다 =================
            _turn(w, 1, [], _jar(ws)[0], artifacts)
            login_oid, login_status = _exchange(
                w, rec, ws, log,
                op="op-01", method="POST", path="/login",
                body="user=analyst&pass=north-42",
            )
            zone_shown = _shown_of(out_path, login_oid)
            zm = re.search(r"zone=([0-9a-z]+)", zone_shown)
            if not zm:
                raise RuntimeError(f"/login 응답에서 zone 을 얻지 못했다: {zone_shown!r}")
            zone = zm.group(1)
            notes["r1"] = {"status": login_status, "zone_observed": True}

            # ============ 턴 2 — ARM. 쿠키가 실려야만 200 이다 =====================
            _turn(w, 2, [login_oid], _jar(ws)[0], artifacts)
            arm_oid, arm_status = _exchange(
                w, rec, ws, log, op="op-02", method="POST", path="/arm"
            )
            notes["r2"] = {
                "status": arm_status,
                "armed": "ok armed" in _shown_of(out_path, arm_oid),
            }

            if negative:
                # ---- C-4 — 턴 **사이에** 선언된 상태 소재를 버린다 (음성) ----------
                # 개입을 스트림에 남긴다. 도구 계층을 지나지 않으면 "무엇이 상태를
                # 없앴는가"가 기록에서 사라지고, 그러면 유실의 원인이 우리 개입인지
                # 챌린지의 성질인지 갈리지 않는다.
                drop_oid, drop_res = _tool(w, rec, ws, "op-03", ["rm", "-f", JAR_PATH])
                dropped = _jar(ws)[0]
                notes["c4"] = {
                    "rm_exit": drop_res.exit_code,
                    "jar_after_drop": dropped,
                    "jar_gone": dropped == "absent",
                }

                # 다음 요청의 `jar_digest_before` 가 직전 `jar_digest_after` 와 갈린다.
                # 그것이 S6.5 (a)이고, 이 스트림이 유형 C에 그 프로브를 준다.
                _turn(w, 3, [arm_oid, drop_oid], dropped, artifacts)
                lost_oid, lost_status = _exchange(
                    w, rec, ws, log, op="op-04", method="GET", path="/vault"
                )
                lost_shown = _shown_of(out_path, lost_oid)
                notes["c4"]["vault_status_after_drop"] = lost_status
                notes["c4"]["vault_refused"] = "no-session" in lost_shown
                notes["c4"]["part_leaked"] = "part=" in lost_shown

                # 회복 여부는 **기록**하고 판정에 넣지 않는다(R2-7 말미). 그런데 이
                # fixture 에서는 우회로가 막혀 있어야 하고, 그것이 C-4 를 챌린지 검수로
                # 성립시키는 조건이다 — T 는 항아리를 버렸는데 에이전트가 처음부터 다시
                # 밟아 회복했고, 그래서 초안 술어가 fixture 가 아니라 술어의 결함이었다.
                _turn(w, 4, [lost_oid], _jar(ws)[0], artifacts)
                _re_oid, re_status = _exchange(
                    w, rec, ws, log,
                    op="op-05", method="POST", path="/login",
                    body="user=analyst&pass=north-42",
                )
                again_oid, again_status = _exchange(
                    w, rec, ws, log, op="op-06", method="GET", path="/vault"
                )
                again_shown = _shown_of(out_path, again_oid)
                notes["c4"]["relogin_status"] = re_status
                notes["c4"]["vault_after_relogin_status"] = again_status
                notes["c4"]["relogin_does_not_recover"] = "not-armed" in again_shown
                notes["c4"]["recovered_after_state_loss"] = "part=" in again_shown

                w.emit("answer.sweep", _sweep_surfaces(ws, fixture))
                w.emit("attempt.finished", {
                    "outcome": "failed",
                    "reason": "C-4 — 항아리를 버리면 상태도 잃는다. 재로그인은 새 sid 에 NEW 다",
                    "wall_clock_s": round(time.monotonic() - started, 3),
                })
                return notes

            # ============ 턴 3 — vault. `part` 가 여기서만 나온다 ==================
            _turn(w, 3, [arm_oid], _jar(ws)[0], artifacts)
            vault_oid, vault_status = _exchange(
                w, rec, ws, log, op="op-03", method="GET", path="/vault"
            )
            pm = re.search(r"part=([0-9a-z]+)", _shown_of(out_path, vault_oid))
            if not pm:
                raise RuntimeError("/vault 응답에서 part 를 얻지 못했다")
            part = pm.group(1)
            notes["r3"] = {"status": vault_status, "part_observed": True}

            # ============ 턴 4 — 조립. 두 관찰을 합쳐야만 나온다 ====================
            _turn(w, 4, [login_oid, vault_oid], _jar(ws)[0], artifacts)
            asm_oid, _ = _tool(
                w, rec, ws, "op-04", ["python3", "/work/assemble.py", zone, part]
            )
            candidate = _shown_of(out_path, asm_oid).strip()
            verdict = _verify(fixture.answer_path, candidate)
            w.emit("candidate.produced", {
                "value": candidate,
                # 두 조각의 출처를 **각각** 가리킨다. 단일 id 로는 파생을 표현할 수 없다
                # (R2-1 이 이 필드를 배열로 만든 이유이고, 9개 조합 전부 FAIL 의 원인이었다).
                "derived_from": [login_oid, vault_oid],
                "method": "golden_assembly",
            })
            w.emit("candidate.provenance", {
                "assembled_in_observation": asm_oid,
                "part_observations": [
                    {"observation_id": login_oid, "part": "from_login"},
                    {"observation_id": vault_oid, "part": "from_vault"},
                ],
            })
            w.emit("verification.completed", {
                "verdict": verdict,
                "verifier_id": VERIFIER_ID,
                "candidate_digest": _shatext(candidate),
            })
            # `None`("판정하지 않았다")을 `solved` 로 접지 않는다. 골든의 픽스처는
            # 언제나 정답을 선언하므로 실제로 갈리지 않지만, 갈리면 그것이 관측이다.
            solved = verdict is True
            notes["solved"] = solved

            # -- C-2 — 모든 교환의 `target_id` 가 선언된 대상 하나인가 ---------------
            # `SAFETY_SCOPE.md` 의 'Allowed targets' 확인이고 계약 술어가 아니다.
            # 스트림을 되읽어 센다 — 파이썬 변수로 세면 우리가 적은 것을 우리가 세는 것이다.
            notes["c2"] = _target_audit(out_path)

            # -- C-3 / P-S2-c — 선언되지 않은 목적지. **컨테이너 안에서** ------------
            script = (
                "import socket,sys\n"
                f"try:\n socket.create_connection(('{UNDECLARED_HOST}',{UNDECLARED_PORT}),3)\n"
                " print('CONNECTED'); sys.exit(0)\n"
                "except OSError as e:\n print(type(e).__name__, e); sys.exit(1)\n"
            )
            res = ws.exec_(["python3", "-c", script])
            notes["c3_refused"] = res.exit_code != 0
            if res.exit_code != 0:
                w.emit("scope.refused", {
                    "action": f"connect:{UNDECLARED_HOST}:{UNDECLARED_PORT}",
                    "reason_code": "network_unreachable",
                    "checked_by": NET_CHECK,
                    "attempted_from": "container",
                    "exit_code": res.exit_code,
                    "stderr": res.text.strip()[:200],
                })

            # -- C-5 (선택) — 동시 요청 둘. **시도 여부만 기록한다** (§7 유형 C) -------
            notes["c5"] = _concurrent_probe(ws, cli)

            w.emit("answer.sweep", _sweep_surfaces(ws, fixture))
            w.emit("attempt.finished", {
                "outcome": "solved" if solved else "failed",
                "reason": "verifier 판정",
                "wall_clock_s": round(time.monotonic() - started, 3),
            })
        finally:
            # 서비스가 네트워크를 붙들고 있으면 `network rm` 이 실패한다. 먼저 지운다.
            if service_up:
                cli.run("rm", "-f", SERVICE_CONTAINER, check=False)
            report = ws.destroy()
            w.emit("workspace.destroyed", {
                "surviving_processes": report.surviving_processes,
                "surviving_containers": report.surviving_containers,
                "checked_by": report.checked_by,
                "surviving_processes_self_reported": report.surviving_processes_self_reported,
            })
            notes["surviving_processes"] = report.surviving_processes

    notes["stream"] = str(out_path)
    return notes


def _target_audit(stream: Path) -> dict[str, Any]:
    """C-2 — 스트림에 실린 모든 `http.exchanged` 의 `target_id`.

    **스트림을 되읽는다.** 드라이버가 들고 있던 상수를 세면 그것은 우리가 적은 값을
    우리가 세는 것이고, "선언된 대상에만 붙었다"의 증거가 되지 못한다.
    """
    seen: dict[str, int] = {}
    hosts: dict[str, int] = {}
    with stream.open("r", encoding="utf-8") as fh:
        for raw in fh:
            e = json.loads(raw)
            if e.get("type") != "http.exchanged":
                continue
            seen[str(e.get("target_id"))] = seen.get(str(e.get("target_id")), 0) + 1
            hosts[str(e.get("host"))] = hosts.get(str(e.get("host")), 0) + 1
    return {
        "target_ids": seen,
        "hosts": hosts,
        "only_declared_target": list(seen) == [TARGET_ID]
        and list(hosts) == [f"{SERVICE_NAME}:{SERVICE_PORT}"],
    }


def _concurrent_probe(ws: Workspace, cli: DockerCli) -> dict[str, Any]:
    """C-5 — 동시 요청 둘. **판정에 넣지 않는다** (`spec.md` §7 유형 C).

    **`http.exchanged` 를 내지 않는다.** 그 이벤트는 `jar_digest_before`/`after` 를
    나르는데, 한 항아리 **파일**을 두 프로세스가 동시에 쓰는 동안 그 두 값은 어느
    요청의 것인지 정의되지 않는다. 정의되지 않은 값을 그럴듯하게 채우는 것이 정확히
    경고 3이 지목한 자기 일관성이므로, 시도했다는 사실과 밖에서 잰 항아리 상태만
    적는다.
    """
    from concurrent.futures import ThreadPoolExecutor

    before = _jar(ws)
    url = f"http://{SERVICE_NAME}:{SERVICE_PORT}/status"
    argv = ("exec", ws.container, "python3", HTTPREQ_PATH, "GET", url)
    # `DockerCli` 로 돈다 — `docker` 를 직접 띄우면 프록시 소켓 지정이 두 벌이 되고,
    # 그러면 이 프로브만 조용히 raw 소켓을 쓰게 되는 경로가 생긴다.
    with ThreadPoolExecutor(max_workers=2) as pool:
        rans = [f.result() for f in [pool.submit(cli.run, *argv, check=False) for _ in range(2)]]
    after = _jar(ws)
    return {
        "attempted": True,
        "emitted_http_exchanged": False,
        "reason": "동시 요청에 대해 jar_digest_before/after 가 정의되지 않는다",
        "bodies": [r.text.strip() for r in rans],
        "statuses": [_status_of(r.err) for r in rans],
        "jar_before": before[0],
        "jar_after": after[0],
        "jar_static_across_pair": before == after,
    }


def _sweep_surfaces(ws: Workspace, fixture: Fixture) -> dict[str, Any]:
    """S8.3 의 표면. **정답은 어디에도 통째로 나타나지 않아야 한다.**

    유형 C의 `input_files` 는 빈다 — 매니페스트가 `inputs: []` 를 선언한다. **빈 표면을
    빼지 않고 넣는다**: 표면 목록에서 빠지면 "쟀는데 0"과 "재지 않았다"가 갈리지 않는다.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        inputs = root / "input_files"
        inputs.mkdir()
        for entry in fixture.manifest()["inputs"]:
            name = str(entry["path"])
            (inputs / name).write_bytes((fixture.root / "input" / name).read_bytes())
        arts = root / "artifacts"
        arts.mkdir()
        (arts / "httpreq.py").write_text(HTTPREQ_PY, encoding="utf-8")
        (arts / "assemble.py").write_text(ASSEMBLE_PY, encoding="utf-8")
        ws.get_tree("/input", root / "c-input")
        ws.get_tree("/work", root / "c-work")
        return _sweep(
            fixture.answer_path,
            [
                ("input_files", inputs),
                ("artifacts", arts),
                ("container:/input", root / "c-input"),
                ("container:/work", root / "c-work"),
            ],
        )


def build_set(
    *,
    outdir: Path,
    fixture: Fixture,
    pricing: Path,
    image: str,
    service_image: str,
    host_id: str,
    normal: int = 4,
) -> list[dict[str, Any]]:
    """정상 `normal` 개 + 음성 1개(C-4). 하한 4는 `spec.md` R3-7 이다."""
    made = [
        run_attempt(
            out_path=outdir / f"normal-{i:02d}.jsonl",
            attempt=f"r6c-ok-{i:02d}",
            fixture=fixture,
            pricing=pricing,
            image=image,
            service_image=service_image,
            host_id=host_id,
        )
        for i in range(1, normal + 1)
    ]
    made.append(
        run_attempt(
            out_path=outdir / "negative-c4.jsonl",
            attempt="r6c-neg-01",
            fixture=fixture,
            pricing=pricing,
            image=image,
            service_image=service_image,
            host_id=host_id,
            negative=True,
        )
    )
    return made


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(prog="kisia.runtime.golden_c")
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--pricing", type=Path, default=Path("config/pricing.openai.yaml"))
    ap.add_argument("--image", required=True, help="digest 로 고정된 worker 이미지")
    ap.add_argument("--service-image", required=True, help="digest 로 고정된 fixture 서비스")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--host-id", default="kisia-integration-host")
    ap.add_argument("--normal", type=int, default=4)
    args = ap.parse_args(argv)

    made = build_set(
        outdir=args.out,
        fixture=Fixture(args.fixture),
        pricing=args.pricing,
        image=args.image,
        service_image=args.service_image,
        host_id=args.host_id,
        normal=args.normal,
    )
    print(json.dumps(made, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
