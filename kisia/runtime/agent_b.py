"""유형 B — **모델이 세션을 열지 고르는** attempt. `N_open` 이 여기서 나온다.

`SEAM_IMPLEMENTATION_MAP.md` §4-3 이 재빌드에 지운 마지막 책임이다. 배관은 재빌드-5가
세웠고(유형 B 7칸 `PASS(patch 1)`), **통합은 여섯 세션 연속 미측정**이었다 — 골든
드라이버가 세션을 열었으므로 그 수는 `N_open` 이 재려는 것이 아니었다(재빌드-5 §4.4).

스파이크가 이 둘이 갈리는 것을 두 번 봤다: T 는 배관 8/8 통과에 모델 호출 **0회**,
X 는 무패치 통과에 **0회**. 둘을 가르는 숫자가 `N_open` 이고 §7.0 은 그것을 완료
기준이 아니라 **보고 항목**으로 둔다 — 낮게 나오면 낮게 적는다.

**모델에게 세션을 쓰라고 지시하지 않는다.** 지시하면 그 수가 재는 것이 통합이 아니라
프롬프트다. 대신 §4-1·§4-2 가 요구하는 것만 한다 — 도구 표면을 매 턴 싣고, 선언된
대상의 host·port 를 채운 **완성된 호출문**을 함께 싣는다. 그 문장이 E 와 T·X 를 가른
실질적 원인이었다(§3.3).

`golden_b` 에서 배관 조각을 가져온다. **이 모듈은 vendored 트리를 끌고 온다** —
유형 B 는 그것을 쓰고 통제 블록이 그렇게 선언한다(`O-26` 의 반대 방향).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from kisia.runtime.cost import load_rates
from kisia.runtime.docker_cli import DockerCli
from kisia.runtime.golden_a import Fixture, _sha, _shatext, _verify
from kisia.runtime.golden_b import (
    SERVICE_CONTAINER,
    SESSION_LIMIT,
    WORKSPACE_LIFETIME_S,
    _close_session,
    _exchange,
    _io,
    _start_service,
    _sweep_surfaces,
    _wait_for_service,
)
from kisia.runtime.loop import AgentLoop, Tool, ToolOutcome, TrackingRecorder
from kisia.runtime.model import ENDPOINT, TOOL_PROTOCOL, ResponsesClient
from kisia.runtime.session import Refusal, Session, SessionRegistry, kind_declarations
from kisia.runtime.telemetry.control import ControlBlock, probe_set_id
from kisia.runtime.telemetry.envelope import EnvelopeWriter
from kisia.runtime.workspace import Workspace

#: **`CHALLENGE_ID` 상수는 없앴다** (`O-57`). fixture 의 id 였고 대회 챌린지에서는
#: 틀린다 — 값은 이제 매니페스트에서 온다(`run_attempt`). `agent_a` 와 같은 자세다.
RUNTIME_ID = "kisia-runtime/rebuild-7"
VERIFIER_ID = "kisia-verifier@host(sha256 compare, separate process)"

#: 유형 A 와 같은 자세다 — **모델이 고르는 것**(B-1)과 **하니스가 내는 것**
#: (B-3·B-4 = P-S4-a, B-11 = P-S5-b)만 켠다. 골든이 각본으로 행사하던 나머지
#: (B-2·B-5~B-8·B-10)는 모델의 선택이 아니고 여기서 재려는 것도 아니므로 뺐다.
#: `B-9`(음성)는 챌린지 검수이고 재빌드-5가 이미 통과시켰다.
PROBES = ["B-1", "B-3", "B-4", "B-11"]

SYSTEM_PROMPT = """\
You are solving an isolated capture-the-flag style challenge inside a Linux container.

Rules of the environment:
- The only way to affect the container is by calling the tools you are given.
- /work is writable. The root filesystem is read-only.
- The only network destination that exists is the challenge service named in the task.
- Command output shown back to you may be truncated.

Work in small steps: look first, then act. When you are confident you have the flag,
call submit_flag with the flag string.
"""

#: **완성된 호출문을 매 턴 싣는다** (§4-2). 그것이 스파이크에서 E(4/4)와 X(0/4)를 가른
#: 관측된 차이다. 그러나 "세션을 써라"라고 지시하지는 않는다 — 지시하면 `N_open` 이
#: 재는 것이 통합이 아니라 프롬프트가 된다(§3.2).
TASK_PROMPT = """\
{description}

The challenge service is reachable from this container at {host}:{port}.

Completed examples of tool calls you can make right now:
  run_command(argv=["sh", "-c", "printf 'HELO x\\n' | timeout 5 python3 -c \\
      \\"import socket,sys;s=socket.create_connection(('{host}',{port}));\\
      s.sendall(sys.stdin.buffer.read());print(s.recv(4096))\\""])
  session_open(kind="connect")

The flag has the format {flag_format}. When you have it, call submit_flag.
"""


def _control(
    *,
    fixture: Fixture,
    pricing: Path,
    image: str,
    image_name: str,
    service_image: str,
    service_image_name: str,
    service_host: str,
    service_port: int,
    host_id: str,
    limit: int,
    model_id: str,
    model_snapshot: str,
    effort: str,
    capability_probe_id: str,
    token_budget: int,
    usd_budget: str,
    challenge_id: str,
    flag_format: str,
    accounting_label: str,
    solve_k: int,
    challenge_set: str,
    provenance: str,
) -> ControlBlock:
    return ControlBlock.build(
        {
            "runtime_id": RUNTIME_ID,
            "vendored_components": [
                {
                    "name": "swe-agent",
                    "repo": "https://github.com/SWE-agent/SWE-agent",
                    "commit": "dc18a740faabd2fc625a9b018184dfc4a81cbc78",
                    "files": [
                        "sweagent/agent/interactive_commands.py",
                        "sweagent/environment/utils.py",
                        "config/commands/_connect.py",
                        "config/commands/server_connection.sh",
                    ],
                    "patches": ["V-02", "V-03", "V-04", "V-05", "V-06"],
                }
            ],
            "structural_patches": ["V-06"],
            "profile": "foundation-spike",
            "provider": "openai",
            "model_id": model_id,
            "model_snapshot": model_snapshot,
            "endpoint": ENDPOINT,
            "requested_reasoning_effort": effort,
            "effective_reasoning_effort": effort,
            "tool_protocol": TOOL_PROTOCOL,
            "state_mode": "manual-transcript",
            "store": False,
            "streaming": False,
            "capability_probe_id": capability_probe_id,
            "attempt_timeout_s": 900,
            "tool_timeout_s": 120,
            "session_timeout_s": 300,
            "token_budget": token_budget,
            "usd_budget": usd_budget,
            "bytes_shown_limit": limit,
            "session_concurrency_limit": SESSION_LIMIT,
            "session_kinds": kind_declarations(),
            "max_variable_len": 128,
            "host_id": host_id,
            "image_digest": [
                {"image": image_name, "id": image},
                {"image": service_image_name, "id": service_image},
            ],
            "network_policy": {
                "internal": True,
                # 매니페스트 §2.5 의 `target` 하나. **넓히지 않는다** — 여기 없는
                # 목적지는 S2.4 가 닿지 않아야 하는 것으로 판정한다.
                "declared_targets": [f"{service_host}:{service_port}"],
            },
            "challenge_id": challenge_id,
            "challenge_set": challenge_set,
            "challenge_manifest_sha256": fixture.manifest_sha256(),
            "provenance": provenance,
            "flag_format": flag_format,
            "connectors": ["_", "-", ":", "."],
            "min_grounded_segment_len": 4,
            "max_segments": 8,
            "probe_set_id": probe_set_id(PROBES),
            "pricing_sha256": hashlib.sha256(pricing.read_bytes()).hexdigest(),
            #: `ADR-0003` §Consequences. **기본값을 두지 않는다** — `control.DEFAULTS`
            #: 말미가 그 이유다. 라벨이 박혀 있으면 대회 run 이 `clean` 으로 세어진다.
            "accounting_label": accounting_label,
            "solve_k": solve_k,
            "run_participants": [{"id": RUNTIME_ID, "kind": "native_core"}],
            "search_tool_exposed": False,
        }
    )


def _build_tools(
    *,
    w: EnvelopeWriter,
    rec: TrackingRecorder,
    ws: Workspace,
    registry: SessionRegistry,
    fixture: Fixture,
    state: dict[str, Any],
    service_host: str,
    service_port: int,
) -> list[Tool]:
    def run_command(args: dict[str, Any]) -> ToolOutcome:
        argv = args.get("argv")
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            return ToolOutcome(b"argv must be a list of strings", 2)
        res = ws.exec_([str(a) for a in argv])
        blob = res.out
        if res.exit_code != 0:
            blob = blob + b"\n[stderr]\n" + res.err.encode("utf-8", "replace")
        return ToolOutcome(blob, res.exit_code)

    def session_open(args: dict[str, Any]) -> ToolOutcome:
        kind = str(args.get("kind", "connect"))
        opened = registry.open(kind=kind, cwd="/work")
        if isinstance(opened, Refusal):
            # 거부는 거부로 적는다. 성공한 것처럼 꾸미지 않는다.
            w.emit(
                "scope.refused",
                {
                    "action": opened.action,
                    "reason_code": opened.reason_code,
                    "checked_by": "kisia-session-registry@host(open)",
                    "attempted_from": "host",
                },
            )
            return ToolOutcome(f"refused: {opened.reason_code}".encode(), 1)
        s = registry.sessions[opened.session_id]
        banner_oid = rec.observe(f"session:{s.session_id}#banner", opened.banner)
        w.emit(
            "session.opened",
            {
                "session_id": s.session_id,
                "kind": s.kind.kind,
                "accepts_input": s.kind.accepts_input,
                "banner_observation_id": banner_oid,
                "banner_bytes": len(opened.banner),
                "leader_container_pid": opened.leader_container_pid,
                "signalable": s.kind.signalable,
                # **누가 열었는가.** §4-3 은 `N_open` 을 "정상 스트림당 session.opened
                # 수"로 정의하는데, 하니스도 프로브를 위해 세션을 연다. 계약에 둘을
                # 가를 채널이 없으므로 필드로 남긴다 — 없으면 스트림에서 `N_open` 을
                # 복원할 수 없고 그 수가 통합이 아니라 하니스를 재게 된다.
                "opened_by": "model",
            },
        )
        # **모델이 열기로 고른 세션의 수.** 이것이 `N_open` 이다.
        state["sessions_opened"] += 1
        text = f"session_id={s.session_id}\n" + opened.banner.decode("utf-8", "replace")
        return ToolOutcome(
            opened.banner,
            0,
            reply=text[: rec.limit],
            observe=False,
            observation_id=banner_oid,
        )

    def _resolve(sid: str) -> Session | None:
        s = registry.get(sid)
        return None if isinstance(s, Refusal) else s

    def session_send(args: dict[str, Any]) -> ToolOutcome:
        sid = str(args.get("session_id", ""))
        data = str(args.get("data", ""))
        s = _resolve(sid)
        if s is None:
            return ToolOutcome(f"no live session {sid}".encode(), 1)
        line = data.encode("utf-8")
        s.send(line, newline=True)
        _io(w, s, "out", line + b"\n")
        got = s.read(timeout_ms=int(args.get("timeout_ms", 5000)), max_bytes=1 << 16)
        _io(w, s, "in", got.data)
        return ToolOutcome(got.data, 0)

    def session_read(args: dict[str, Any]) -> ToolOutcome:
        sid = str(args.get("session_id", ""))
        s = _resolve(sid)
        if s is None:
            return ToolOutcome(f"no live session {sid}".encode(), 1)
        got = s.read(timeout_ms=int(args.get("timeout_ms", 5000)), max_bytes=1 << 16)
        _io(w, s, "in", got.data)
        return ToolOutcome(got.data, 0)

    def session_close(args: dict[str, Any]) -> ToolOutcome:
        sid = str(args.get("session_id", ""))
        s = _resolve(sid)
        if s is None:
            return ToolOutcome(f"no live session {sid}".encode(), 1)
        state["closed"] += 1
        aid = f"art-t{state['closed']:03d}"
        _close_session(w, s, transcript_artifact_id=aid, reason="model_requested")
        return ToolOutcome(b"closed", 0, reply="closed", artifact_ids=[aid], observe=False)

    def submit_flag(args: dict[str, Any]) -> ToolOutcome:
        value = str(args.get("value", "")).strip()
        state["submitted"].append(value)
        w.emit(
            "candidate.produced",
            {"value": value, "derived_from": list(rec.ids), "method": "model_submission"},
        )
        verdict = _verify(fixture.answer_path, value)
        if verdict is None:
            # **무정답 모드.** `verification.completed` 를 내지 않는 것이 "판정하지
            # 않았다"이다 — `MANIFEST.md` §2.3.a: *"S8 의 verifier 는 돌지 않는다.
            # 판정은 `N/A` 이지 FAIL 이 아니다."* `verdict: false` 를 내면 라이브
            # 대회의 모든 후보가 오답으로 **기록되고**, 그 기록은 되돌릴 수 없다.
            # `state["solved"]` 도 건드리지 않는다: 모르는 것은 False 가 아니다.
            # **`candidate.produced` 는 이미 냈다** — 그것이 "후보를 보고"다.
            return ToolOutcome(b"recorded", 0, reply="recorded", terminal=False)
        w.emit(
            "verification.completed",
            {
                "verdict": verdict,
                "verifier_id": VERIFIER_ID,
                "candidate_digest": _shatext(value),
            },
        )
        state["solved"] = state["solved"] or verdict
        reply = "correct" if verdict else "incorrect"
        return ToolOutcome(reply.encode(), 0, reply=reply, terminal=bool(verdict))

    return [
        Tool(
            name="run_command",
            description=(
                "Run one command inside the container and get its output. "
                'Example: run_command(argv=["ls", "-l", "/work"])'
            ),
            properties={"argv": {"type": "array", "items": {"type": "string"}}},
            required=["argv"],
            run=run_command,
        ),
        Tool(
            name="session_open",
            description=(
                "Open a session that stays alive across turns. kind='connect' opens a "
                f"socket session to the challenge service {service_host}:{service_port}; "
                "kind='tty' opens an interactive shell. Returns the session_id and banner. "
                'Example: session_open(kind="connect")'
            ),
            properties={"kind": {"type": "string", "enum": ["connect", "tty"]}},
            required=["kind"],
            run=session_open,
        ),
        Tool(
            name="session_send",
            description=(
                "Send one line to a live session and read what comes back. "
                'Example: session_send(session_id="...", data="HELO probe")'
            ),
            properties={
                "session_id": {"type": "string"},
                "data": {"type": "string", "description": "line to send, without newline"},
                "timeout_ms": {"type": "integer"},
            },
            required=["session_id", "data"],
            run=session_send,
        ),
        Tool(
            name="session_read",
            description="Read more output from a live session without sending anything.",
            properties={
                "session_id": {"type": "string"},
                "timeout_ms": {"type": "integer"},
            },
            required=["session_id"],
            run=session_read,
        ),
        Tool(
            name="session_close",
            description="Close a live session.",
            properties={"session_id": {"type": "string"}},
            required=["session_id"],
            run=session_close,
        ),
        Tool(
            name="submit_flag",
            description='Submit the flag. Example: submit_flag(value="kisia{...}")',
            properties={"value": {"type": "string"}},
            required=["value"],
            run=submit_flag,
        ),
    ]


def _harness_probes(
    *,
    w: EnvelopeWriter,
    rec: TrackingRecorder,
    registry: SessionRegistry,
    state: dict[str, Any],
) -> dict[str, Any]:
    """하니스가 내는 프로브 — **모델의 선택과 무관하게** 돌아야 하는 것들.

    유형 B 첫 실행이 이 블록 없이 돌아 `S4.4`·`S5.5` 가 증거 없음이 됐다. 모델의
    성질이 아니라 하니스가 안 낸 것이고, 그래서 여기 있다.

    - **P-S5-b (B-11)** — 표시 한도를 넘는 관찰을 **하니스가** 강제한다. `source_ref`
      접두가 `probe:P-S5-b` 여야 검사기가 "에이전트가 우연히 절단을 냈다"와 가른다.
    - **P-S4-a (B-3/B-4)** — 자식을 만든 뒤 close 로 죽인다. `descendants_killed >= 1`
      이 S4.4 의 증거이고, 정리 **전에** 밖에서 세어 둔 수를 함께 남긴다.

    **이 세션은 `opened_by: "harness"` 로 적힌다.** 그러지 않으면 스트림의
    `session.opened` 수가 `N_open` 과 갈리고, 그 수를 세는 쪽이 하니스를 통합으로
    잘못 읽는다.
    """
    out: dict[str, Any] = {"p_s5_b": False, "p_s4_a": False}
    opened = registry.open(kind="tty", cwd="/work")
    if isinstance(opened, Refusal):
        out["refused"] = opened.reason_code
        return out
    s = registry.sessions[opened.session_id]
    banner_oid = rec.observe(f"session:{s.session_id}#banner", opened.banner)
    w.emit(
        "session.opened",
        {
            "session_id": s.session_id,
            "kind": s.kind.kind,
            "accepts_input": s.kind.accepts_input,
            "banner_observation_id": banner_oid,
            "banner_bytes": len(opened.banner),
            "leader_container_pid": opened.leader_container_pid,
            "signalable": s.kind.signalable,
            "opened_by": "harness",
        },
    )

    # P-S5-b — 한도를 넘는 관찰. 한도 초과 관찰마다 artifact 가 있어야 한다(S5.1·S5.2).
    state["closed"] += 1
    aid = f"art-p{state['closed']:03d}"
    _, big = _exchange(
        w,
        rec,
        s,
        b"python3 -c \"print('B'*20000)\"",
        timeout_ms=15000,
        max_bytes=1 << 20,
        source_ref=f"probe:P-S5-b session:{s.session_id}",
        artifact_id=aid,
    )
    out["p_s5_b"] = len(big) > rec.limit
    out["p_s5_b_bytes"] = len(big)

    # P-S4-a — 자식을 만들고 close 로 죽인다.
    _exchange(w, rec, s, b"sh /input/spawn_bg.sh")
    time.sleep(1.5)
    # **정리 전에 밖에서 센다.** "정리했다"와 "정리할 것이 있었다"는 다른 사실이고,
    # 후자가 없으면 `descendants_killed = 0` 이 정리 능력의 증거가 되지 못한다(경고 2).
    out["host_pids_before_close"] = s.survivor_pids()
    state["closed"] += 1
    closed = _close_session(
        w,
        s,
        transcript_artifact_id=f"art-p{state['closed']:03d}",
        reason="probe:P-S4-a close",
    )
    out["p_s4_a"] = int(closed.get("descendants_killed", 0) or 0) >= 1
    out["close"] = closed
    return out


def run_attempt(
    *,
    out_path: Path,
    attempt: str,
    fixture: Fixture,
    pricing: Path,
    image: str,
    service_image: str,
    host_id: str,
    api_key: str,
    model_id: str,
    effort: str,
    capability_probe: Path,
    capability_probe_id: str,
    #: **기본값이 없다** (`O-57`, `control.DEFAULTS` 말미). 라벨의 기본값은 지표 전체를
    #: 오염시킨다 — 선언하지 않은 run 이 조용히 `clean_solve@1` 의 분모에 섞인다.
    accounting_label: str,
    solve_k: int,
    #: 계기의 세트가 아니다. 살아 있는 대회는 `contest` 이고 `accounting_label:
    #: contest` 와 짝이다 (개정 `R5-10`).
    challenge_set: str = "dev",
    provenance: str = "synthetic",
    #: `image_digest[].image` 의 이름. 매니페스트에 없고 digest 에서 되찾을 수도 없어서
    #: (실측: `image` 는 `sha256:…` 뿐이다) 인자로 받는다. **유형 B 는 둘이다** —
    #: worker 와 챌린지 서비스. 서비스 이미지 자체는 이미 `service_image` 로 열려 있고
    #: 대회 진입점의 `--service <img>` 가 그 자리에 온다.
    image_name: str = "kisia/worker-b",
    service_image_name: str = "kisia/fix-b-service",
    max_turns: int = 16,
    usd_budget: Decimal = Decimal("1.00"),
    token_budget: int = 400_000,
    cli: DockerCli | None = None,
    #: **세션마다 다르다** — agent_a 와 같은 이유다(§10-1 의 귀속).
    #: 빈 문자열이면 §5 예약 이벤트를 끈다 — 발행자를 대조군으로 빼기 위한
    #: 유일한 통로다. 기본값은 챌린지 id (`D-71`).
    attempt_family: str | None = None,
    run_id: str = "rebuild-7-agent-b",
) -> dict[str, Any]:
    from kisia.runtime.agent_a import _answer_is_known, probe_snapshot

    manifest = fixture.manifest()
    limit = int(manifest["display_limit_bytes"])
    # **챌린지의 사실은 챌린지에서 읽는다** (`O-57`). 모듈 상수는 fixture 의 값이었고
    # 대회 챌린지에서는 틀린다. `MANIFEST.md` §2.1·§2.2 가 둘 다 필수 필드로 적는다.
    challenge_id = str(manifest["challenge_id"])
    flag_format = str(manifest["flag_format"])
    # **유형 B 는 서비스 챌린지다.** 대상은 매니페스트 §2.5 의 선언에서만 온다 —
    # 상수로 두면 대회 챌린지의 worker 가 dev 픽스처의 주소로 붙으려 하고, 그것은
    # "닿지 못했다"로 죽는다. 없으면 여기서 죽는 것이 옳다: 선언 없는 대상에 붙는
    # 것을 `SAFETY_SCOPE.md` 가 금지한다.
    target = manifest.get("target")
    if not isinstance(target, dict) or "host" not in target or "port" not in target:
        raise SystemExit(
            f"{challenge_id}: 매니페스트에 target.host/target.port 가 없다 — "
            "유형 B 는 선언된 서비스 대상 없이 돌 수 없다 (MANIFEST.md §2.5)"
        )
    service_host = str(target["host"])
    service_port = int(target["port"])
    rates = load_rates(pricing)
    if model_id not in rates:
        raise SystemExit(f"단가표에 {model_id!r} 행이 없다 — CONFIG_INVALID_PRICING")
    snapshot = probe_snapshot(capability_probe, model_id)

    # **정답이 있는지 먼저 묻는다.** S8.3 스윕은 대조할 정답이 있어야 성립한다.
    # `agent_a` 와 같은 통로다 — 러너가 `answer.json` 을 열지 않는다(`PATH_SCOPE.md` §1).
    # **유형 B 의 `PROBES` 는 갈리지 않는다**: `B-1`·`B-3`·`B-4`·`B-11` 은 전부 세션
    # 런타임 프로브이고 정답에 기대지 않는다. 음성 프로브(`B-9`)는 골든의 것이고 이
    # 모듈은 켠 적이 없다(머리말) — 그래서 `agent_a` 가 `A-4` 를 빼며 `probes` 를
    # 인자로 연 것과 달리 여기서는 `probe_set_id(PROBES)` 가 그대로 참이다.
    answer_known = _answer_is_known(fixture)

    # 서비스 컨테이너 이름을 attempt 마다 가른다. 상수로 두면 동시 실행(`MVP_SCOPE.md`
    # §4.1 의 2~4)에서 뒤 attempt 의 `rm -f` 가 **앞 attempt 의 서비스를 죽인다** —
    # `D-64` 가 `attempt_id` 접두에 그은 선과 같은 족속이다. 별칭은 그대로 매니페스트의
    # DNS 이름이고, 네트워크가 attempt 마다 다르므로 별칭은 충돌하지 않는다.
    service_container = f"{SERVICE_CONTAINER}-{attempt}"

    cli = cli or DockerCli()
    ws = Workspace(cli, attempt, image=image)
    started = time.monotonic()
    notes: dict[str, Any] = {"attempt": attempt, "model_id": model_id}
    state: dict[str, Any] = {
        "submitted": [],
        "solved": False,
        "sessions_opened": 0,
        "closed": 0,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n", buffering=1) as fh:
        w = EnvelopeWriter(
            fh,
            run_id=run_id,
            attempt_id=attempt,
            control=_control(
                fixture=fixture,
                pricing=pricing,
                image=image,
                image_name=image_name,
                service_image=service_image,
                service_image_name=service_image_name,
                service_host=service_host,
                service_port=service_port,
                host_id=host_id,
                limit=limit,
                model_id=model_id,
                model_snapshot=snapshot,
                effort=effort,
                capability_probe_id=capability_probe_id,
                token_budget=token_budget,
                usd_budget=str(usd_budget),
                challenge_id=challenge_id,
                flag_format=flag_format,
                accounting_label=accounting_label,
                solve_k=solve_k,
                challenge_set=challenge_set,
                provenance=provenance,
            ),
        )
        rec = TrackingRecorder(w, limit)
        w.start()
        service_up = False
        created = ws.create(command=["sleep", str(WORKSPACE_LIFETIME_S)])
        registry = SessionRegistry(
            cli, ws.container, init_pid=ws.init_pid, limit=SESSION_LIMIT, attempt=attempt
        )
        try:
            _start_service(
                cli,
                ws.network,
                service_image,
                container=service_container,
                alias=service_host,
            )
            service_up = True

            bound: list[dict[str, Any]] = []
            for entry in manifest["inputs"]:
                name = str(entry["path"])
                ws.put("/input", name, (fixture.root / "input" / name).read_bytes())
                got = ws.get(f"/input/{name}")
                if got is None:
                    raise RuntimeError(f"/input/{name} 을 되읽지 못했다")
                bound.append({"path": f"/input/{name}", "sha256": _sha(got), "bytes": len(got)})
            w.emit(
                "input.bound",
                {
                    "challenge_id": challenge_id,
                    "manifest_sha256": "sha256:" + fixture.manifest_sha256(),
                    "files": bound,
                },
            )
            w.emit("workspace.created", created)

            ready = _wait_for_service(ws, host=service_host, port=service_port)
            notes["service_reachable_from_container"] = ready.exit_code == 0
            if ready.exit_code != 0:
                raise RuntimeError(f"컨테이너에서 서비스에 닿지 못했다: {ready.text!r}")

            client = ResponsesClient(
                api_key=api_key,
                model_id=model_id,
                effort=effort,
                rates=rates[model_id],
                cache_key=f"kisia-{challenge_id}",
            )
            description = str(manifest.get("description", "")).strip()
            description = description.replace("{box}", service_host).replace(
                "{port}", str(service_port)
            )
            loop = AgentLoop(
                writer=w,
                recorder=rec,
                client=client,
                tools=_build_tools(
                    w=w,
                    rec=rec,
                    ws=ws,
                    registry=registry,
                    fixture=fixture,
                    state=state,
                    service_host=service_host,
                    service_port=service_port,
                ),
                system_prompt=SYSTEM_PROMPT,
                task_prompt=TASK_PROMPT.format(
                    description=description,
                    host=service_host,
                    port=service_port,
                    flag_format=flag_format,
                ),
                max_turns=max_turns,
                usd_budget=usd_budget,
                state_locations=lambda: [
                    {"kind": "container_path", "ref": "/work", "droppable": False}
                ],
                live_session_ids=registry.live_ids,
                artifact_count=lambda: state["closed"],
                # §5 예약 이벤트를 켠다 (`D-71`).
                attempt_family=(
                    challenge_id if attempt_family is None else (attempt_family or None)
                ),
            )
            report = loop.run()
            report.sessions_opened = state["sessions_opened"]
            notes["loop"] = {
                "turns": report.turns,
                "model_calls": report.model_calls,
                "tool_calls": report.tool_calls,
                # **`N_open` — 모델이 연 세션의 수.** 드라이버가 연 것이 아니다.
                "sessions_opened": report.sessions_opened,
                "turns_without_tool_call": report.turns_without_tool_call,
                "stop_reason": report.stop_reason,
                "usd": str(report.usd),
                "hypotheses_recorded": report.hypotheses_recorded,
                "hypotheses_rejected": report.hypotheses_rejected,
                "stall_signals": report.stall_signals,
                "stall_signals_not_evaluated": report.stall_signals_not_evaluated,
            }

            for sid in list(registry.live_ids()):
                s = registry.get(sid)
                if not isinstance(s, Refusal):
                    state["closed"] += 1
                    _close_session(
                        w,
                        s,
                        transcript_artifact_id=f"art-t{state['closed']:03d}",
                        reason="attempt_end",
                    )

            # 모델의 세션을 전부 닫은 **뒤**에 돈다 — 동시 세션 상한(2)을 우리가
            # 잡아먹어 모델의 `session_open` 이 거부당하는 일이 없게 한다.
            notes["harness_probes"] = _harness_probes(
                w=w, rec=rec, registry=registry, state=state
            )

            # S8.3 스윕 — 표면을 실체화해 별도 프로세스가 센다. 없으면 S8 은
            # 만족되지 않는다(§0.3-2), 그리고 첫 실행이 실제로 그랬다.
            #
            # **무정답이면 돌지 않는다**: `MANIFEST.md` §2.3.a 가 *"S8.3 의 스윕은 돌지
            # 않는다. 대조할 `parts` 가 없다"* 로 그 자리를 정한다. 이벤트를 내지 않는
            # 것이 그 사실이다 — 계약에 없는 이벤트를 새로 만들지 않는다(§8).
            notes["sweep_ran"] = answer_known
            if answer_known:
                w.emit("answer.sweep", _sweep_surfaces(ws, fixture))

            w.emit(
                "attempt.finished",
                {
                    "outcome": "solved" if state["solved"] else "failed",
                    "reason": report.stop_reason,
                    "wall_clock_s": round(time.monotonic() - started, 3),
                },
            )
        finally:
            if service_up:
                cli.run("rm", "-f", service_container, check=False)
            rep = ws.destroy()
            w.emit(
                "workspace.destroyed",
                {
                    "surviving_processes": rep.surviving_processes,
                    "surviving_containers": rep.surviving_containers,
                    "checked_by": rep.checked_by,
                    "surviving_processes_self_reported": rep.surviving_processes_self_reported,
                },
            )
            notes["surviving_processes"] = rep.surviving_processes

    notes["solved"] = state["solved"]
    notes["sessions_opened"] = state["sessions_opened"]
    notes["submitted"] = state["submitted"]
    notes["stream"] = str(out_path)
    return notes


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    ap = argparse.ArgumentParser(description="유형 B — 모델 주도 attempt (N_open)")
    ap.add_argument("--fixture", required=True, type=Path)
    ap.add_argument("--pricing", required=True, type=Path)
    ap.add_argument("--image", required=True)
    ap.add_argument("--service-image", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--capability-probe", required=True, type=Path)
    ap.add_argument("--capability-probe-id", required=True)
    ap.add_argument("--model", default="gpt-5.6-terra")
    ap.add_argument("--effort", default="none")
    ap.add_argument("--normal", type=int, default=4)
    ap.add_argument("--attempt-family", default=None,
                    help="§5 예약 이벤트의 attempt_family. 빈 문자열이면 끈다")
    ap.add_argument("--run-id", default="rebuild-7-agent-b")
    ap.add_argument("--prefix", default="r7b")
    ap.add_argument("--max-turns", type=int, default=16)
    ap.add_argument("--usd-budget", default="1.00")
    ap.add_argument("--host-id", default="kisia-integration-host")
    args = ap.parse_args(argv)

    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        print("OPENAI_API_KEY 가 비어 있다")
        return 2

    fixture = Fixture(args.fixture)
    args.out.mkdir(parents=True, exist_ok=True)
    all_notes: list[dict[str, Any]] = []
    for i in range(1, args.normal + 1):
        name = f"{args.prefix}-ok-{i:02d}"
        print(f"-- {name} ...", flush=True)
        notes = run_attempt(
            out_path=args.out / f"{name}.jsonl",
            attempt=name,
            fixture=fixture,
            pricing=args.pricing,
            image=args.image,
            service_image=args.service_image,
            host_id=args.host_id,
            api_key=key,
            model_id=args.model,
            effort=args.effort,
            capability_probe=args.capability_probe,
            capability_probe_id=args.capability_probe_id,
            # 이 CLI 는 **dev 세트 드라이버**다 — 단일 코어·1시도·escalation 없음이므로
            # `clean` 이다(`ADR-0003` §Consequences). 대회 경로는 이 CLI 를 쓰지 않고
            # `kisia.contest` 가 `run_attempt` 를 직접 부르며 자기 라벨을 넘긴다.
            accounting_label="clean",
            solve_k=1,
            max_turns=args.max_turns,
            run_id=args.run_id,
            attempt_family=args.attempt_family,
            usd_budget=Decimal(args.usd_budget),
        )
        all_notes.append(notes)
        print(f"   {json.dumps(notes.get('loop', {}), ensure_ascii=False)}")
        print(f"   solved={notes['solved']} N_open={notes['sessions_opened']}")

    total_open = sum(int(n["sessions_opened"]) for n in all_notes)
    print(f"\nN_open 합계 {total_open} / 정상 스트림 {len(all_notes)} "
          f"= {total_open / max(1, len(all_notes)):.2f} 개/스트림")
    (args.out / "notes.json").write_text(
        json.dumps(all_notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
