"""유형 B 골든 궤적 — 세션. **우리 드라이버, 실제 컨테이너.**

`golden_a.py` 가 형태의 본보기이고 그 보조 함수들을 **그대로 재사용한다**(`Recorder`,
`_sha`, `_verify`, `_sweep`, `Fixture`). 베끼지 않는다 — 새 공유 모듈을 만드는 것은
요청되지 않은 리팩터링이고(`CLAUDE.md` §8) 두 벌로 두면 갈린다.

**유형 B가 유형 A와 다른 것 넷** (부팅 프롬프트 §3.3).

1. 세션이 `model.completed` 셋을 가로질러 **살아 있어야** 한다 (S4.2).
2. `session.io` 가 `payload` 를 싣는다 — 라이트업 (b)가 유형 B에서만 깨졌고 원인은
   `session.io` 가 바이트 **수**만 실었기 때문이다 (R2-13).
3. `session.closed` 가 `descendants_killed` 와 `survivors` 를 **다른 출처에서** 갈라
   싣는다. 같은 출처면 스트림이 자기 일관적이 되어 검사기가 통과시킨다
   (`TELEMETRY_SCHEMA.md` §7.1).
4. 하중표가 B에 싣는 프로브는 **S4.4·S5.5 둘뿐이다**(`judge.py` `PROBE_CARRY`).
   그래서 P-S2-a/b 를 돌리지 않는다 — 유형 B의 S2 하중은 쓰기 거부가 아니라
   **프로세스 트리 정리**(S2.5)이고 그것은 프로브가 아니라 상시 술어다(r1 A-4).

**정답 문자열이 이 파일에 없다.** `zone` 과 `part` 는 스트림에 실린 관찰에서 되읽고,
조립은 컨테이너 안의 스크립트가 한다. 판정은 별도 프로세스가 낸다. 드라이버가 정답을
들고 있으면 S8.3 의 스윕이 무엇을 재는지 정의되지 않는다.
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
from kisia.runtime.session import Refusal, Session, SessionRegistry, kind_declarations
from kisia.runtime.telemetry.control import ControlBlock, probe_set_id
from kisia.runtime.telemetry.envelope import EnvelopeWriter
from kisia.runtime.workspace import ExecResult, Workspace

CHALLENGE_ID = "kisia-fix-b-session"
RUNTIME_ID = "kisia-runtime/rebuild-5"
VERIFIER_ID = "kisia-verifier@host(sha256 compare, separate process)"
#: `session.closed.checked_by` — S4.4 가 이 이름이 **정리 주체와 다를 것**을 요구한다.
#: 정리는 컨테이너 안의 `kill` 이 하고, 세는 것은 호스트의 `/proc` 스캔이다.
SESSION_CHECK = "kisia-sidprobe@host(/proc session-id scan)"
NET_CHECK = "kisia-netprobe@container(socket.create_connection)"

#: 매니페스트가 선언한 유일한 대상 (`target.host`/`target.port`). **DNS 이름이다.**
SERVICE_NAME = "kisia-fix-b"
SERVICE_PORT = 9101

#: 컨테이너 이름은 따로 둔다. 그 이유는 실측이다 — 스파이크의 정지된 컨테이너가
#: `kisia-fix-b` 라는 이름을 여전히 쥐고 있고(라벨 `kisia-spike=1`), 프록시는 우리
#: 라벨이 아닌 대상의 `rm` 을 **정확히 거부한다**. 소유권 규칙이 제대로 도는 것이지
#: 결함이 아니므로, 남의 것을 지우는 대신 우리 이름을 쓰고 **네트워크 별칭**으로
#: 매니페스트의 DNS 이름을 만든다. 계약이 요구하는 것은 worker 가 `kisia-fix-b:9101`
#: 에 닿는 것이지 컨테이너의 이름이 아니다.
SERVICE_CONTAINER = "kisia-r5-fix-b"

#: P-S2-c 의 대상. 매니페스트의 `declared_targets` 에 없는 목적지다.
UNDECLARED_HOST, UNDECLARED_PORT = "1.1.1.1", 80

#: 유형 B 표의 프로브 전부 + C-3. 켜지 않은 프로브의 부재는 그 유형의 FAIL 이
#: 아니다(D-8) — 그래서 무엇을 켰는지가 `probe_set_id` 로 통제 조건이 된다(§6.4).
#:
#: **한 유형의 모든 스트림이 같은 목록을 싣는다. 음성 스트림도 마찬가지다.**
#: `B-9` 는 음성 스트림에서만 실제로 돌지만, 그것을 음성 스트림에만 선언하면
#: `probe_set_id` 가 갈리고 §6.4 가 그 집합을 "무엇을 쟀는지 정의되지 않는다"로
#: 표시한다(실측: 첫 판이 그랬다). 프로브 집합은 스트림의 서술이 아니라 **run 의
#: 통제 조건**이다 — 재빌드-4 가 `A-4`(음성)를 모든 유형 A 스트림에 선언한 것과 같다.
PROBES = [
    "B-1", "B-2", "B-3", "B-4", "B-5", "B-6", "B-7", "B-8", "B-9", "B-10", "B-11", "C-3",
]

WORKSPACE_LIFETIME_S = 900

#: §4.2 는 동시 세션 **2개 이상**을 요구하고 상한이 명시적일 것을 요구한다. 2 로 두는
#: 이유는 그 하한에서 B-10(상한 초과 → 거부)을 실제로 행사할 수 있기 때문이다 —
#: 상한을 크게 두면 초과를 만들 수 없고 그러면 §4.2 의 거부 갈래가 시험되지 않는다.
SESSION_LIMIT = 2

#: 컨테이너 안에서 조립한다. **정답도 그 조각도 들어 있지 않다** — 인자로 받는다.
#: 표준출력으로만 낸다. 파일로 쓰면 `container:/work` 스윕이 통째 flag 를 찾아내고
#: S8.3 이 거짓이 된다 (그리고 그것이 옳은 판정이다).
ASSEMBLE_PY = '''\
import sys
print("kisia{%s_%s}" % (sys.argv[1], sys.argv[2]))
'''


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
    return ControlBlock.build(
        {
            "runtime_id": RUNTIME_ID,
            #: 유형 B 는 vendored 코드를 **실제로 쓴다** — 유형 A 와 갈리는 자리다.
            "vendored_components": [
                {
                    "component": "swe-agent",
                    "commit": "dc18a740faabd2fc625a9b018184dfc4a81cbc78",
                    "symbols": ["get_interactive_session", "InteractiveSession"],
                    #: 허용 목록의 세 번째 심볼을 **쓰지 않는다** — 접지 않고 적는다.
                    "allowed_but_unused": ["read_with_timeout"],
                }
            ],
            #: `judge.py` 가 이 리스트의 **길이**를 `PASS(patch n)` 의 `n` 으로 쓴다.
            #: V-06 하나이므로 유형 B 판정은 `PASS(patch 1)` 이 된다.
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
            "session_concurrency_limit": SESSION_LIMIT,
            #: R3-9 — 선언은 자유 서술이 아니라 통제 블록의 필드다. 그리고 선언은
            #: 관측으로 반증된다(§6.2 말미).
            "session_kinds": kind_declarations(),
            "max_variable_len": 128,
            "host_id": host_id,
            "image_digest": [
                {"image": "kisia/worker-b", "id": image},
                {"image": "kisia/fix-b-service", "id": service_image},
            ],
            "network_policy": {
                "internal": True,
                "declared_targets": [f"{SERVICE_NAME}:{SERVICE_PORT}"],
                "probe_target": f"{UNDECLARED_HOST}:{UNDECLARED_PORT}",
            },
            "challenge_id": CHALLENGE_ID,
            "challenge_set": "dev",
            "challenge_manifest_sha256": fixture.manifest_sha256(),
            "flag_format": "kisia{...}",
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
# 턴 경계와 세션 입출력
# ---------------------------------------------------------------------------


def _turn(
    w: EnvelopeWriter,
    turn: int,
    observation_ids: list[str],
    registry: SessionRegistry,
    artifacts: int,
) -> None:
    """턴 경계. **`live_session_ids` 는 레지스트리에서 온다** — 손으로 적으면 S6.7 이
    재는 것이 우리 문자열이 되고, 조용한 축출이 스트림에서 보이지 않는다.
    """
    locations: list[dict[str, Any]] = [
        {"kind": "container_path", "ref": "/work", "droppable": False}
    ]
    for sid in registry.live_ids():
        s = registry.sessions[sid]
        locations.append(
            {
                "kind": "process_object",
                "ref": f"session:{sid}@container:pid{s.leader_container_pid}",
                "droppable": False,
            }
        )
    w.emit(
        "state.snapshot",
        {
            "turn": turn,
            "live_session_ids": registry.live_ids(),
            "state_locations": locations,
            "jar_digest": None,
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
            "prompt_digest": _shatext(f"golden-b turn {turn}"),
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


def _io(w: EnvelopeWriter, session: Session, direction: str, payload: bytes) -> None:
    """`session.io` — **`payload` 를 원문 그대로 싣는다** (`TELEMETRY_SCHEMA.md` §6).

    합성 챌린지이므로 원문 정책이 적용된다. 이 필드가 없으면 라이트업 (b)("실행 가능한
    solve 단계")가 유형 B에서 깨진다 — 관찰은 **돌아온 것**만 담고 보낸 것을 담지 않는다.
    """
    w.emit(
        "session.io",
        {
            "session_id": session.session_id,
            "session_seq": session.seq,
            "direction": direction,
            "bytes": len(payload),
            "payload": payload.decode("utf-8", "replace"),
            "payload_digest": _sha(payload),
        },
    )


def _exchange(
    w: EnvelopeWriter,
    rec: Recorder,
    session: Session,
    line: bytes,
    *,
    timeout_ms: int = 6000,
    max_bytes: int = 1 << 16,
    source_ref: str | None = None,
    artifact_id: str | None = None,
    artifact_role: str = "probe_output",
) -> tuple[str, bytes]:
    """세션에 한 줄 보내고 응답을 **관찰 하나**로 만든다. `(observation_id, 바이트)`.

    `artifact_id` 가 주어지면 관찰 **앞에** `artifact.produced` 를 낸다. 한도를 넘는
    관찰마다 `artifact_id` 가 있어야 하고(S5.1) 그 id 에 대응하는 `artifact.produced`
    가 있어야 한다(S5.2). 관찰을 둘로 나눠 하나에만 artifact 를 붙이면 나머지 하나가
    S5.1 을 깬다 — 첫 판이 실제로 그랬다.
    """
    session.send(line, newline=True)
    _io(w, session, "out", line + b"\n")
    got = session.read(timeout_ms=timeout_ms, max_bytes=max_bytes)
    _io(w, session, "in", got.data)
    if artifact_id is not None:
        w.emit("artifact.produced", {
            "artifact_id": artifact_id,
            "sha256": _sha(got.data),
            "bytes": len(got.data),
            "producer_ref": f"session:{session.session_id}",
            "role": artifact_role,
        })
    oid = rec.observe(
        source_ref or f"session:{session.session_id}", got.data, artifact_id=artifact_id
    )
    return oid, got.data


def _close_session(
    w: EnvelopeWriter,
    session: Session,
    *,
    transcript_artifact_id: str,
    reason: str,
    reap: bool = True,
) -> dict[str, Any]:
    """`session.closed`. **`survivors` 는 리스트다** — 검사기가 `!= []` 로 본다(S4.4).

    개수로 접으면 근거가 사라지고, 그러면 "0" 과 "못 셌다"를 가를 수 없다.
    """
    res = session.close(reason=reason, reap=reap)
    w.emit(
        "artifact.produced",
        {
            "artifact_id": transcript_artifact_id,
            "sha256": _sha(res.transcript),
            "bytes": len(res.transcript),
            "producer_ref": f"session:{session.session_id}",
            "role": "session_transcript",
        },
    )
    w.emit(
        "session.closed",
        {
            "session_id": session.session_id,
            "transcript_artifact_id": transcript_artifact_id,
            "exit_status": res.exit_status,
            # 정리를 **수행한** 쪽의 반환값.
            "descendants_killed": res.descendants_killed,
            # 그 뒤 **밖에서** 센 값. 둘의 출처가 다르다.
            "survivors": list(res.survivor_host_pids),
            "survivors_self_reported": res.survivors_self_reported,
            "grace_used_ms": res.grace_used_ms,
            "reason": res.reason,
            "checked_by": SESSION_CHECK,
            # 아래 둘은 계약이 읽지 않는다. 그런데 §4.1-2·3 이 요구하는 성질은 술어가
            # 재지 못하고(계약은 관측만 지정한다), 이 둘이 그 자리를 스트림 안에서
            # 메운다 — `reuse/S2.md` §4 가 적은 한계와 같은 형태다.
            "zombies_excluded": list(res.zombies_excluded),
            "pgid_only_would_have_killed": list(res.pgid_only_would_have_killed),
        },
    )
    return {
        "session": session.session_id,
        "descendants_killed": res.descendants_killed,
        "survivors": list(res.survivor_host_pids),
        "survivors_self_reported": res.survivors_self_reported,
        "zombies_excluded": list(res.zombies_excluded),
        "pgid_only_would_have_killed": list(res.pgid_only_would_have_killed),
        "grace_used_ms": res.grace_used_ms,
        "reaped": reap,
    }


# ---------------------------------------------------------------------------
# 챌린지 서비스
# ---------------------------------------------------------------------------


def _start_service(
    cli: DockerCli,
    network: str,
    image: str,
    *,
    container: str = SERVICE_CONTAINER,
    alias: str = SERVICE_NAME,
) -> str:
    """선언된 대상 하나를 **내부 네트워크에만** 띄운다 (`PATH_SCOPE.md` §4.2).

    `-p` 를 쓰지 않는다 — 호스트에도 공중에도 노출되지 않는다. 이름이 그 네트워크의
    DNS 이름이 되고, 그것이 매니페스트의 `target.host` 다.

    `container`·`alias` 의 기본값은 이 모듈의 상수다 — 골든의 호출은 한 글자도 바뀌지
    않는다. 대회 챌린지는 자기 `target.host` 와 자기 컨테이너 이름을 넘긴다
    (`agent_b.run_attempt` 의 `service_container` 주석).
    """
    cli.run("rm", "-f", container, check=False)
    cli.run(
        "create",
        "--name", container,
        "--network", network,
        # 매니페스트의 `target.host` 는 여기서 온다. 컨테이너 이름이 아니라 별칭이다.
        "--network-alias", alias,
        "--label", "kisia-role=challenge-service",
        "--read-only",
        "--init",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "64",
        "--memory", "256m", "--memory-swap", "256m",
        image,
    )
    cli.run("start", container)
    return container


def _wait_for_service(
    ws: Workspace,
    *,
    host: str = SERVICE_NAME,
    port: int = SERVICE_PORT,
    tries: int = 20,
) -> ExecResult:
    """서비스가 붙을 수 있을 때까지 **컨테이너 안에서** 기다린다.

    호스트에서 확인하면 그것은 worker 가 보는 것과 다른 사실이다 — 내부 네트워크의
    DNS 와 도달성은 worker 의 네임스페이스에서만 성립한다.

    `host`·`port` 의 기본값은 이 모듈의 상수다 — 골든의 호출은 바뀌지 않는다.
    """
    script = (
        "import socket,sys\n"
        f"s=socket.create_connection(('{host}',{port}),3)\n"
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
    reap: bool = True,
    cli: DockerCli | None = None,
) -> dict[str, Any]:
    """attempt 하나. 스트림 한 파일을 내고 요약을 돌려준다.

    `negative=True` 는 **B-9**(끊고 다시 붙어 이어서 시도)다 — 챌린지가 세션 유지를
    강제하는지 묻는 fixture 검수이고, 통과하면 사람 검수를 따로 두지 않는다(§7 말미).

    `reap=False` 는 **음성 대조**다. §4.1-2 를 거짓으로 만들어 S4.4 가 갈리는지 본다.
    판정에 넣는 스트림은 언제나 기본값으로 돈다.
    """
    manifest = fixture.manifest()
    limit = int(manifest["display_limit_bytes"])
    cli = cli or DockerCli()
    ws = Workspace(cli, attempt, image=image)
    started = time.monotonic()
    probes = PROBES
    notes: dict[str, Any] = {
        "attempt": attempt,
        "negative": negative,
        "reap": reap,
        "probes": probes,
        "closed": [],
    }
    artifacts = 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n", buffering=1) as fh:
        w = EnvelopeWriter(
            fh,
            run_id="rebuild-5-golden-b",
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

        created = ws.create(command=["sleep", str(WORKSPACE_LIFETIME_S)])
        # 레지스트리는 컨테이너가 선 **뒤에** 만든다 — 리더를 찾는 단서가 컨테이너
        # init 의 호스트 pid 이고, 그 값은 `create` 전에는 존재하지 않는다.
        registry = SessionRegistry(
            cli, ws.container, init_pid=ws.init_pid, limit=SESSION_LIMIT, attempt=attempt
        )
        try:
            _start_service(cli, ws.network, service_image)
            service_up = True

            # -- S1. 매니페스트가 선언한 입력물 둘을 넣고 **되읽어** 바인딩한다 --------
            bound: list[dict[str, Any]] = []
            for entry in manifest["inputs"]:
                name = str(entry["path"])
                ws.put("/input", name, (fixture.root / "input" / name).read_bytes())
                got = ws.get(f"/input/{name}")
                if got is None:
                    raise RuntimeError(f"/input/{name} 을 되읽지 못했다")
                bound.append(
                    {"path": f"/input/{name}", "sha256": _sha(got), "bytes": len(got)}
                )
            w.emit("input.bound", {
                "challenge_id": CHALLENGE_ID,
                "manifest_sha256": "sha256:" + fixture.manifest_sha256(),
                "files": bound,
            })
            notes["inputs_match_manifest"] = [
                b["sha256"] == "sha256:" + str(e["sha256"])
                for b, e in zip(bound, manifest["inputs"], strict=True)
            ]
            w.emit("workspace.created", created)

            ready = _wait_for_service(ws)
            notes["service_reachable_from_container"] = ready.exit_code == 0
            if ready.exit_code != 0:
                raise RuntimeError(f"컨테이너에서 서비스에 닿지 못했다: {ready.text!r}")

            # ============ 턴 1 — 세션을 열고 배너와 nonce ==========================
            _turn(w, 1, [], registry, artifacts)
            opened = registry.open(kind="connect", cwd="/work")
            if isinstance(opened, Refusal):
                raise RuntimeError(f"세션을 열지 못했다: {opened}")
            s1 = registry.sessions[opened.session_id]
            banner_oid = rec.observe(f"session:{s1.session_id}#banner", opened.banner)
            w.emit("session.opened", {
                "session_id": s1.session_id,
                "kind": s1.kind.kind,
                "accepts_input": s1.kind.accepts_input,
                "banner_observation_id": banner_oid,
                # **배너가 살아 있는 것은 패치 V-06 때문이다.** upstream 은 시작 출력을
                # 읽고 버렸다 — 접지 않고 스트림에 적는다.
                "banner_bytes": len(opened.banner),
                "leader_container_pid": opened.leader_container_pid,
                "signalable": s1.kind.signalable,
            })
            notes["banner_bytes"] = len(opened.banner)

            # 선언된 대상에 붙는다. 서비스 배너에 `zone=` 이 한 번만 나온다.
            zone_oid, _ = _exchange(w, rec, s1, f"connect {SERVICE_NAME} {SERVICE_PORT}".encode())
            zone_shown = _shown_of(out_path, zone_oid)
            zm = re.search(r"zone=([0-9a-z]+)", zone_shown)
            if not zm:
                raise RuntimeError(f"서비스 배너에서 zone 을 얻지 못했다: {zone_shown!r}")
            zone = zm.group(1)
            notes["zone_observed"] = True

            nonce_oid, _ = _exchange(w, rec, s1, b"sendline HELO kisia")
            nm = re.search(r"nonce=([0-9a-f]+)", _shown_of(out_path, nonce_oid))
            if not nm:
                raise RuntimeError("HELO 응답에서 nonce 를 얻지 못했다")
            nonce = nm.group(1)

            if negative:
                # ---- B-9 — 끊고 다시 붙어 **이어서** 시도한다 (음성) --------------
                artifacts += 1
                notes["closed"].append(_close_session(
                    w, s1, transcript_artifact_id=f"art-{artifacts:04d}",
                    reason="probe:B-9 세션을 끊는다",
                ))
                _turn(w, 2, [nonce_oid], registry, artifacts)
                again = registry.open(kind="connect", cwd="/work")
                if isinstance(again, Refusal):
                    raise RuntimeError(f"재접속 세션을 열지 못했다: {again}")
                s2 = registry.sessions[again.session_id]
                b2 = rec.observe(f"session:{s2.session_id}#banner", again.banner)
                w.emit("session.opened", {
                    "session_id": s2.session_id, "kind": s2.kind.kind,
                    "accepts_input": s2.kind.accepts_input, "banner_observation_id": b2,
                    "signalable": s2.kind.signalable,
                })
                _exchange(w, rec, s2, f"connect {SERVICE_NAME} {SERVICE_PORT}".encode())
                _turn(w, 3, [b2], registry, artifacts)
                # 다시 인사한다. 인사를 건너뛰면 서버가 `not-greeted` 로 답하는데,
                # 그것은 "nonce 가 이어지지 않는다"가 아니라 "인사가 이어지지 않는다"의
                # 증거다 — 다른 사실이고 접으면 B-9 가 무엇을 물었는지 흐려진다.
                greet_oid, _ = _exchange(w, rec, s2, b"sendline HELO kisia")
                fresh = re.search(r"nonce=([0-9a-f]+)", _shown_of(out_path, greet_oid))
                notes["b9_new_nonce_is_different"] = fresh is not None and fresh.group(1) != nonce
                # **묵은** nonce 로 ARM 한다. 이것이 B-9 의 질문이다.
                arm_oid, _ = _exchange(w, rec, s2, f"sendline ARM {nonce[::-1]}".encode())
                arm_shown = _shown_of(out_path, arm_oid)
                _turn(w, 4, [arm_oid], registry, artifacts)
                read_oid, _ = _exchange(w, rec, s2, b"sendline READ")
                read_shown = _shown_of(out_path, read_oid)
                notes["b9_stale_nonce_rejected"] = "bad-code" in arm_shown
                notes["b9_read_refused"] = "not-armed" in read_shown
                notes["b9_part_leaked"] = "part=" in read_shown
                artifacts += 1
                notes["closed"].append(_close_session(
                    w, s2, transcript_artifact_id=f"art-{artifacts:04d}",
                    reason="attempt 종료",
                ))
                w.emit("answer.sweep", _sweep_surfaces(ws, fixture))
                w.emit("attempt.finished", {
                    "outcome": "failed",
                    "reason": "B-9 — 새 연결은 새 nonce 를 뽑는다. 이어서 풀 수 없다",
                    "wall_clock_s": round(time.monotonic() - started, 3),
                })
                return notes

            # ============ 턴 2 — ARM ==============================================
            _turn(w, 2, [nonce_oid], registry, artifacts)
            arm_oid, _ = _exchange(w, rec, s1, f"sendline ARM {nonce[::-1]}".encode())
            notes["armed"] = "OK armed" in _shown_of(out_path, arm_oid)

            # ============ 턴 3 — READ =============================================
            _turn(w, 3, [arm_oid], registry, artifacts)
            read_oid, _ = _exchange(w, rec, s1, b"sendline READ")
            pm = re.search(r"part=([0-9a-z]+)", _shown_of(out_path, read_oid))
            if not pm:
                raise RuntimeError("READ 응답에서 part 를 얻지 못했다")
            part = pm.group(1)

            # ============ 턴 4 — 조립. 두 관찰을 합쳐야만 나온다 ====================
            _turn(w, 4, [zone_oid, read_oid], registry, artifacts)
            ws.put("/work", "assemble.py", ASSEMBLE_PY.encode("utf-8"))
            artifacts += 1
            solve_art = f"art-{artifacts:04d}"
            w.emit("artifact.produced", {
                "artifact_id": solve_art,
                "sha256": _shatext(ASSEMBLE_PY),
                "bytes": len(ASSEMBLE_PY.encode("utf-8")),
                "producer_ref": "runtime:golden-b",
                "role": "solve_script",
            })
            asm_oid = _tool(w, rec, ws, "op-01", ["python3", "/work/assemble.py", zone, part])
            candidate = _shown_of(out_path, asm_oid).strip()
            solved = _verify(fixture.answer_path, candidate)
            w.emit("candidate.produced", {
                "value": candidate,
                # 두 조각의 출처를 **각각** 가리킨다. 단일 id 로는 파생을 표현할 수 없다
                # (R2-1 이 이 필드를 배열로 만든 이유이고, 9개 조합 전부 FAIL 의 원인이었다).
                "derived_from": [zone_oid, read_oid],
                "method": "golden_assembly",
            })
            w.emit("candidate.provenance", {
                "assembled_in_observation": asm_oid,
                "part_observations": [
                    {"observation_id": zone_oid, "part": "from_service_banner"},
                    {"observation_id": read_oid, "part": "from_read_response"},
                ],
            })
            w.emit("verification.completed", {
                "verdict": solved,
                "verifier_id": VERIFIER_ID,
                "candidate_digest": _shatext(candidate),
            })
            notes["solved"] = solved

            # ============ 턴 5 — 둘째 세션. B-2 · B-6 · B-10 · B-11 ===============
            _turn(w, 5, [asm_oid], registry, artifacts)
            tty = registry.open(kind="tty", cwd="/work")
            if isinstance(tty, Refusal):
                raise RuntimeError(f"tty 세션을 열지 못했다: {tty}")
            s2 = registry.sessions[tty.session_id]
            tty_banner = rec.observe(f"session:{s2.session_id}#banner", tty.banner)
            w.emit("session.opened", {
                "session_id": s2.session_id,
                "kind": s2.kind.kind,
                "accepts_input": s2.kind.accepts_input,
                "banner_observation_id": tty_banner,
                "banner_bytes": len(tty.banner),
                "leader_container_pid": tty.leader_container_pid,
                "signalable": s2.kind.signalable,
            })

            # -- B-10 — 상한 초과는 **거부**다. 대기도 조용한 축출도 아니다 (R2-8) ----
            third = registry.open(kind="tty", cwd="/work")
            notes["b10_refused"] = isinstance(third, Refusal)
            if isinstance(third, Refusal):
                w.emit("scope.refused", {
                    "action": third.action,
                    "reason_code": third.reason_code,
                    "checked_by": SESSION_CHECK,
                    "attempted_from": "runtime",
                    "declared_limit": registry.limit,
                    "live_sessions": registry.live_ids(),
                })
            notes["b10_no_eviction"] = sorted(registry.live_ids()) == sorted(
                [s1.session_id, s2.session_id]
            )

            # -- B-2 — **같은 바이트**를 입력 가능한 두 종류에 (§4.1-1) ---------------
            same = b"echo TESTLINE"
            tty_oid, _ = _exchange(w, rec, s2, same)
            con_oid, _ = _exchange(w, rec, s1, same)
            notes["b2_line_delivered"] = {
                "tty": "TESTLINE" in _shown_of(out_path, tty_oid),
                "connect": "TESTLINE" in _shown_of(out_path, con_oid),
            }

            # -- B-6 — 두 세션을 번갈아 읽는다. 바이트가 섞이지 않는다 (§4.2) --------
            a_oid, _ = _exchange(w, rec, s2, b"echo MARK-TTY-A")
            b_oid, _ = _exchange(w, rec, s1, b"sendline MARK-CON-B")
            c_oid, _ = _exchange(w, rec, s2, b"echo MARK-TTY-C")
            shown = {k: _shown_of(out_path, k) for k in (a_oid, b_oid, c_oid)}
            notes["b6_no_byte_mixing"] = (
                "MARK-TTY-A" in shown[a_oid] and "MARK-CON-B" not in shown[a_oid]
                and "MARK-CON-B" in shown[b_oid] and "MARK-TTY" not in shown[b_oid]
                and "MARK-TTY-C" in shown[c_oid] and "MARK-CON-B" not in shown[c_oid]
            )

            # -- B-11 / P-S5-b — **하니스가** 세션 경로로 절단을 강제한다 (R2-5) ------
            # `source_ref` 가 `probe:P-S5-b` 로 시작해야 한다 — 에이전트가 고른 도구가
            # 우연히 절단을 낸 것과 하니스가 강제한 것은 다른 사실이고, 검사기가 그
            # 접두로 둘을 가른다(S5.5).
            artifacts += 1
            big_oid, big = _exchange(
                w, rec, s2,
                b"python3 -c \"print('B'*20000)\"",
                timeout_ms=15000,
                max_bytes=1 << 20,
                source_ref=f"probe:P-S5-b session:{s2.session_id}",
                artifact_id=f"art-{artifacts:04d}",
            )
            notes["b11_bytes"] = len(big)
            notes["b11_truncated"] = len(big) > limit

            # ============ 턴 6 — B-7 · B-3 · B-4, 그리고 close ====================
            _turn(w, 6, [big_oid], registry, artifacts)

            # -- B-7 — 장시간 명령을 interrupt. 판정은 **종료 코드**로 한다 (§4.3) ----
            s2.send(b"sleep 240", newline=True)
            _io(w, s2, "out", b"sleep 240\n")
            time.sleep(1.0)
            hit = s2.interrupt()
            notes["b7_interrupt_accepted"] = isinstance(hit, int)
            int_res = s2.read(timeout_ms=4000, max_bytes=1 << 16)
            _io(w, s2, "in", int_res.data)
            rec.observe(f"session:{s2.session_id}#interrupt", int_res.data)
            rc_oid, _ = _exchange(w, rec, s2, b"echo RC=$?")
            rc_shown = _shown_of(out_path, rc_oid)
            notes["b7_exit_code_130"] = "RC=130" in rc_shown
            notes["b7_session_alive"] = s2.snapshot().live

            # -- B-7 의 나머지 절반 — 순수 소켓에서는 **명시적 거부**다 (§4.3) --------
            refused = s1.interrupt()
            notes["b7_socket_refused"] = isinstance(refused, Refusal)
            if isinstance(refused, Refusal):
                w.emit("scope.refused", {
                    "action": refused.action,
                    "reason_code": refused.reason_code,
                    "checked_by": SESSION_CHECK,
                    "attempted_from": "runtime",
                    "declared_signalable": s1.kind.signalable,
                })

            # -- B-3 — tty 의 job control 아래 백그라운드 잡 (§4.1-2) ----------------
            bg_oid, _ = _exchange(w, rec, s2, b"sh /input/spawn_bg.sh")
            notes["b3_spawned"] = "spawned background sleep" in _shown_of(out_path, bg_oid)
            # -- B-4 — 즉시 종료하는 자식. **좀비는 생존자가 아니다** (§4.1-3) --------
            zb_oid, _ = _exchange(w, rec, s2, b"sh /input/spawn_zombie.sh &")
            notes["b4_started"] = _shown_of(out_path, zb_oid) != ""
            time.sleep(1.5)

            # 정리 **전에** 밖에서 세어 둔다 — "정리했다"와 "정리할 것이 있었다"는
            # 다른 사실이고, 재빌드-4 의 `surviving_processes = 0` 이 후자를 갖지
            # 못해 정리 능력의 증거가 되지 못했다(경고 2).
            before = s2.survivor_pids()
            notes["b3_b4_host_pids_before_close"] = before
            artifacts += 1
            notes["closed"].append(_close_session(
                w, s2, transcript_artifact_id=f"art-{artifacts:04d}",
                reason="probe:B-3/B-4 close", reap=reap,
            ))

            # ============ 턴 7 — B-8 · B-5 · C-3 ==================================
            _turn(w, 7, [bg_oid, zb_oid], registry, artifacts)

            # -- B-8 — 닫힌 `session_id` 를 참조한다 → S6.3 -------------------------
            dead = registry.get(s2.session_id)
            notes["b8_refused"] = isinstance(dead, Refusal)
            if isinstance(dead, Refusal):
                # 참조 자체를 스트림에 남긴다. 그러지 않으면 S6.3 이 "죽은 세션을
                # 참조한 사례가 없다"로 공허해지고, 프로브를 돌린 사실이 사라진다.
                w.emit("session.io", {
                    "session_id": s2.session_id,
                    "session_seq": s2.seq,
                    "direction": "out",
                    "bytes": len(b"echo AFTER-CLOSE\n"),
                    "payload": "echo AFTER-CLOSE\n",
                    "payload_digest": _sha(b"echo AFTER-CLOSE\n"),
                })
                w.emit("scope.refused", {
                    "action": dead.action,
                    "reason_code": dead.reason_code,
                    "checked_by": SESSION_CHECK,
                    "attempted_from": "runtime",
                })

            # -- B-5 — 상태 0 종료와 실행 중을 가른다 (§4.1-4) ----------------------
            probe = registry.open(kind="tty", cwd="/work")
            if isinstance(probe, Refusal):
                raise RuntimeError(f"B-5 세션을 열지 못했다: {probe}")
            s3 = registry.sessions[probe.session_id]
            b3o = rec.observe(f"session:{s3.session_id}#banner", probe.banner)
            w.emit("session.opened", {
                "session_id": s3.session_id, "kind": s3.kind.kind,
                "accepts_input": s3.kind.accepts_input, "banner_observation_id": b3o,
                "banner_bytes": len(probe.banner),
                "leader_container_pid": probe.leader_container_pid,
                "signalable": s3.kind.signalable,
            })
            live_running = s3.snapshot(ask_container=True)
            s3.send(b"exit", newline=True)
            _io(w, s3, "out", b"exit\n")
            time.sleep(1.5)
            live_exited = s3.snapshot(ask_container=True)
            notes["b5"] = {
                "running_live": live_running.live,
                "running_live_self_reported": live_running.live_self_reported,
                "exited_live": live_exited.live,
                "exited_live_self_reported": live_exited.live_self_reported,
                # §4.1-4 가 금지한 추론을 함께 잰다. 상태 0 이 "정상 종료"이자 "아직
                # 살아 있음"이라는 것이 [ev §8.3] 이고, 그 애매함이 실제로 나타나는지를
                # 적어 두지 않으면 "우리는 그렇게 하지 않았다"가 주장으로만 남는다.
                "running_naive": live_running.naive_live_from_status_only,
                "exited_naive": live_exited.naive_live_from_status_only,
                # 실행 중인 세션과 상태 0 으로 끝난 세션이 **갈렸는가**. 이것이
                # §4.1-4 가 요구하는 관측이다 — waitpid 상태값 0 만으로는 갈리지 않는다.
                "distinguished": live_running.live and not live_exited.live,
            }
            artifacts += 1
            notes["closed"].append(_close_session(
                w, s3, transcript_artifact_id=f"art-{artifacts:04d}",
                reason="probe:B-5 정상 종료 확인 뒤",
            ))
            notes["b5_exit_status"] = notes["closed"][-1].get("survivors")

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

            # -- 첫 세션을 닫는다. S6.2 의 대상 턴(5)을 이미 지났다 ------------------
            artifacts += 1
            notes["closed"].append(_close_session(
                w, s1, transcript_artifact_id=f"art-{artifacts:04d}",
                reason="attempt 종료",
            ))

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
            notes["host_pids_before_destroy"] = len(report.host_pids_before)

    notes["stream"] = str(out_path)
    return notes


def _tool(
    w: EnvelopeWriter, rec: Recorder, ws: Workspace, op: str, argv: list[str]
) -> str:
    started = time.monotonic()
    w.emit("tool.requested", {
        "op_id": op, "tool": "exec", "args": argv,
        "args_digest": _shatext(" ".join(argv)),
    })
    res = ws.exec_(argv)
    oid = rec.observe(f"tool:{' '.join(argv)}", res.out)
    w.emit("tool.completed", {
        "op_id": op,
        "status": "ok" if res.exit_code == 0 else "error",
        "exit_code": res.exit_code,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "artifact_ids": [],
        "observation_id": oid,
    })
    return oid


def _sweep_surfaces(ws: Workspace, fixture: Fixture) -> dict[str, Any]:
    """S8.3 의 네 표면. **정답은 어디에도 없어야 한다** (`PATH_SCOPE.md` §2.4)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        inputs = root / "input_files"
        inputs.mkdir()
        for entry in fixture.manifest()["inputs"]:
            name = str(entry["path"])
            (inputs / name).write_bytes((fixture.root / "input" / name).read_bytes())
        ws.get_tree("/input", root / "c-input")
        ws.get_tree("/work", root / "c-work")
        return _sweep(
            fixture.answer_path,
            [
                ("input_files", inputs),
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
    """정상 `normal` 개 + 음성 1개(B-9). 하한 4는 `spec.md` R3-7 이다."""
    made = [
        run_attempt(
            out_path=outdir / f"normal-{i:02d}.jsonl",
            attempt=f"r5b-ok-{i:02d}",
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
            out_path=outdir / "negative-b9.jsonl",
            attempt="r5b-neg-01",
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

    ap = argparse.ArgumentParser(prog="kisia.runtime.golden_b")
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--pricing", type=Path, default=Path("config/pricing.openai.yaml"))
    ap.add_argument("--image", required=True, help="digest 로 고정된 worker-b 이미지")
    ap.add_argument("--service-image", required=True, help="digest 로 고정된 fixture 서비스")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--host-id", default="kisia-integration-host")
    ap.add_argument("--normal", type=int, default=4)
    ap.add_argument(
        "--negative-control",
        choices=["no-reap"],
        help="세션 정리를 하지 않아 §4.1-2 를 거짓으로 만든다. **판정에 인용할 수 없다**",
    )
    args = ap.parse_args(argv)

    if args.negative_control:
        made = [
            run_attempt(
                out_path=args.out / f"control-{args.negative_control}.jsonl",
                attempt="r5b-ctl-noreap",
                fixture=Fixture(args.fixture),
                pricing=args.pricing,
                image=args.image,
                service_image=args.service_image,
                host_id=args.host_id,
                reap=False,
            )
        ]
        print(json.dumps(made, ensure_ascii=False, indent=2))
        return 0

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
