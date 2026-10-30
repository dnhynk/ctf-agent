"""유형 A — **모델이 도구를 고르는** attempt. 골든 드라이버가 아니다.

`golden_a.py` 는 드라이버가 모델 자리에서 다음 명령을 골랐고 토큰이 전부 0 이라
S3.2 가 공허참이었다. 이 모듈은 그 자리에 실제 모델을 넣는다 — `spec.md` §5 하중표가
S3 을 유형 A에만 싣고, 그래서 **S3.1~S3.5 가 실제 값을 갖는 자리가 여기뿐**이다.

**골든을 대체하지 않는다.** 골든의 목적은 §7 의 셋(챌린지 건전성·술어 검증·진단)이고
그 판정은 `judgments/2026-08-09-r6-regen-ab/` 에 남아 있다. 이 스트림 집합은 켜진
프로브가 달라 `probe_set_id` 가 다르고, §6.4 대로 **같은 집합에 넣지 않는다.**

**하니스가 내는 프로브는 그대로 하니스가 낸다.** P-S2-a/b/c(격리 거부), P-S5-b(표시
한도 강제), `answer.sweep` 은 모델의 선택과 무관하게 돌아야 하는 것들이다
(`TELEMETRY_SCHEMA.md` §3.1: "arm 이 아니라 하니스가 낸다"). 모델이 고르는 것은
A-1 의 풀이 경로다.

**골든과 프로브 집합이 다른 이유.** `A-2`(표시 한도를 넘는 파일을 읽는다)는
골든이 **각본으로** 행사하던 것이고 모델이 그 경로를 고를지는 이 모듈이 정하지 않는다.
그래서 뺐고, S5 는 하니스가 내는 `A-6`(P-S5-b)이 덮는다. `A-5`(모델 id 교체)는
반대로 **처음 켜진다** — 모델을 부르므로 전제가 성립한다.

`A-4`(틀린 후보)는 **하니스가 낸다.** 처음 판은 이것도 껐는데, 모델이 넷 다 첫
시도에 맞히자 S8.5 가 `증거 없음` 이 되어 S8 이 FAIL 했다. 그것은 모델의 성질이
아니라 프로브가 꺼져 있었다는 사실이므로 골든과 같은 자리에 되살렸다 — 값은 관찰에서
오고(`D-24`) `method` 가 프로브 이름을 나른다.
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
from kisia.runtime.golden_a import (
    Fixture,
    _refusals,
    _sha,
    _shatext,
    _sweep_surfaces,
    _verify,
)
from kisia.runtime.loop import AgentLoop, Tool, ToolOutcome, TrackingRecorder
from kisia.runtime.model import ENDPOINT, TOOL_PROTOCOL, ResponsesClient
from kisia.runtime.telemetry.control import ControlBlock, probe_set_id
from kisia.runtime.telemetry.envelope import EnvelopeWriter
from kisia.runtime.workspace import Workspace

#: **`CHALLENGE_ID` 상수는 없앴다** (`O-57`). fixture 의 id 였고 대회 챌린지에서는
#: 틀린다 — 값은 이제 매니페스트에서 온다(`run_attempt`). 상수로 남겨 두면 다음
#: 호출자가 같은 자리에 다시 묶인다.
RUNTIME_ID = "kisia-runtime/rebuild-7"
VERIFIER_ID = "kisia-verifier@host(sha256 compare, separate process)"

#: `A-5`(모델 id 교체)가 **처음으로 켜진다** — 모델을 부르므로 전제가 성립한다.
#: `A-2` 만 꺼져 있고 이유는 위 머리말이다. 골든의 집합과 다른 id 가 나오고, 그것이
#: §6.4 가 요구하는 바다.
PROBES = ["A-1", "A-3", "A-4", "A-5", "A-6", "C-3"]

WORKSPACE_LIFETIME_S = 900

SYSTEM_PROMPT = """\
You are solving an isolated capture-the-flag style challenge inside a Linux container.

Rules of the environment:
- The only way to affect the container is by calling the tools you are given.
- /input is read-only and holds the challenge input. /work is writable and is where you
  should extract and build things. The root filesystem is read-only.
- There is no network access. Do not try to fetch anything.
- Command output shown back to you may be truncated. If you need the whole thing,
  process it inside the container instead of printing it.

Work in small steps: look first, then act. When you are confident you have the flag,
call submit_flag exactly once with the flag string.
"""

#: **챌린지 서술은 매니페스트에서 온다.** 여기 직접 쓰지 않는다 — 골든 드라이버는
#: 조립 규칙을 각본으로 알고 있었지만 모델은 챌린지가 말해 주는 것만 안다. 첫 실행이
#: 그것 때문에 14턴을 쓰고 제출하지 못했다: `manifest.description` 이
#: "flag 는 kisia{<tag>_<sum>}" 이라고 적는데 프롬프트가 그것을 나르지 않았다.
#: `MANIFEST.md` §2 의 `description` 이 챌린지 서술이고, S1 이 매니페스트를 러너의
#: 입력에 바인딩하라고 하는 것이 이 자리다.
TASK_PROMPT = """\
{description}

The challenge input is mounted at /input/bundle.tar.gz. Extract it into /work.
The flag has the format {flag_format}.

Completed example of a tool call you can make right now:
  run_command(argv=["sh", "-c", "tar xzf /input/bundle.tar.gz -C /work && ls -l /work"])

When you have the flag, call submit_flag with it.
"""


def _control(
    *,
    fixture: Fixture,
    pricing: Path,
    image: str,
    image_name: str,
    host_id: str,
    limit: int,
    model_id: str,
    model_snapshot: str,
    effort: str,
    capability_probe_id: str,
    token_budget: int,
    usd_budget: str,
    #: **챌린지에서 온다.** 모듈 상수로 박아 두면 대회 챌린지의 스트림이 fixture 의
    #: id 와 flag 형식을 적는다 — 통제 블록이 다른 챌린지를 재구성하게 된다 (`O-57`).
    challenge_id: str,
    flag_format: str,
    #: 켠 프로브의 실제 목록. 모듈 상수를 그대로 쓰면 **끈 프로브를 켰다고 적는다** —
    #: `probe_set_id` 는 §6.4 의 동치 규칙이고 거짓이면 섞지 말아야 할 것을 섞는다.
    probes: list[str],
    challenge_set: str,
    provenance: str,
    accounting_label: str,
    solve_k: int,
) -> ControlBlock:
    return ControlBlock.build(
        {
            "runtime_id": RUNTIME_ID,
            "vendored_components": [],
            "structural_patches": [],
            "profile": "foundation-spike",
            "provider": "openai",
            "model_id": model_id,
            # 요청에 보낸 `model_id` 가 아니다 — capability probe artifact 가 관측한
            # `response.model` 이다 (`TELEMETRY_SCHEMA.md` §2.1). 매 호출의 관측은
            # `model.completed.model_snapshot_observed` 가 따로 나른다.
            "model_snapshot": model_snapshot,
            # **후속 gate 1** — `SEAM_IMPLEMENTATION_MAP.md` §7.1-1.
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
            "session_concurrency_limit": 2,
            "session_kinds": [],
            "max_variable_len": 128,
            "host_id": host_id,
            "image_digest": [{"image": image_name, "id": image}],
            "network_policy": {
                "internal": True,
                "declared_targets": [],
                "probe_target": "1.1.1.1:80",
            },
            "challenge_id": challenge_id,
            "challenge_set": challenge_set,
            "challenge_manifest_sha256": fixture.manifest_sha256(),
            "provenance": provenance,
            "flag_format": flag_format,
            "connectors": ["_", "-", ":", "."],
            "min_grounded_segment_len": 4,
            "max_segments": 8,
            "probe_set_id": probe_set_id(probes),
            "pricing_sha256": hashlib.sha256(pricing.read_bytes()).hexdigest(),
            #: `ADR-0003` §Consequences. **기본값이 없다** — 라벨의 기본값은 지표 전체를
            #: 오염시킨다(`control.DEFAULTS` 말미). 호출자가 선언한 것을 그대로 싣고,
            #: 라벨은 모드이고 `challenge_set` 이 계기의 갈래를 가른다 (§Decision-2).
            "accounting_label": accounting_label,
            "solve_k": solve_k,
            "run_participants": [{"id": RUNTIME_ID, "kind": "native_core"}],
            "search_tool_exposed": False,
        }
    )


def probe_snapshot(probe_path: Path, model_id: str) -> str:
    """capability probe artifact 에서 그 모델의 `response.model` 을 읽는다.

    상수로 박지 않는 이유는 ADR-0001 §4 다 — probe 는 메모가 아니라 artifact 이고,
    통제 블록은 그것을 `capability_probe_id` 로 가리킨다. 그 모델의 칸이 없으면
    **죽는다**: 프로브 없이 새 모델을 돌리면 `model_snapshot` 이 관측이 아니라 추측이
    된다.
    """
    data = json.loads(probe_path.read_text(encoding="utf-8"))
    for cell in data.get("cells", []):
        if cell.get("model_id") == model_id and cell.get("observed_model"):
            return str(cell["observed_model"])
    raise SystemExit(
        f"capability probe {probe_path.name} 에 model_id={model_id!r} 의 칸이 없다 — "
        "프로브를 먼저 돌려라 (ADR-0001 §4)"
    )


# ---------------------------------------------------------------------------
# 도구 — 모델에게 노출되는 표면
# ---------------------------------------------------------------------------


def _build_tools(
    *,
    w: EnvelopeWriter,
    rec: TrackingRecorder,
    ws: Workspace,
    fixture: Fixture,
    state: dict[str, Any],
) -> list[Tool]:
    def run_command(args: dict[str, Any]) -> ToolOutcome:
        argv = args.get("argv")
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            return ToolOutcome(b"argv must be a list of strings", 2)
        res = ws.exec_([str(a) for a in argv])
        # 실패했는데 stdout 만 돌려주면 모델이 오류를 못 본다. 붙여서 돌려준다.
        blob = res.out
        if res.exit_code != 0:
            blob = blob + b"\n[stderr]\n" + res.err.encode("utf-8", "replace")
        return ToolOutcome(blob, res.exit_code)

    def write_file(args: dict[str, Any]) -> ToolOutcome:
        path = str(args.get("path", ""))
        content = str(args.get("content", ""))
        if not path.startswith("/work/") or "/.." in path:
            return ToolOutcome(b"write_file only accepts paths under /work/", 2)
        name = path.rsplit("/", 1)[-1]
        data = content.encode("utf-8")
        try:
            ws.put("/work", name, data)
        except Exception as exc:
            return ToolOutcome(f"write failed: {exc}".encode(), 1)
        aid = f"art-w{len(state['artifacts']) + 1:03d}"
        state["artifacts"].append(aid)
        w.emit(
            "artifact.produced",
            {
                "artifact_id": aid,
                "sha256": _sha(data),
                "bytes": len(data),
                "producer_ref": f"model:write_file {path}",
                "role": "solve_script",
            },
        )
        return ToolOutcome(
            f"wrote {len(data)} bytes to /work/{name}".encode(),
            0,
            artifact_ids=[aid],
            observe=False,
        )

    def submit_flag(args: dict[str, Any]) -> ToolOutcome:
        value = str(args.get("value", "")).strip()
        state["submitted"].append(value)
        w.emit(
            "candidate.produced",
            {
                # 선언은 모델이 본 관찰 전부다. 검사기는 이 선언을 믿지 않고 스스로
                # 파생을 찾는다 (S7.2) — 그래서 좁혀 적을 근거가 우리에게 없다.
                "value": value,
                "derived_from": list(rec.ids),
                "method": "model_submission",
            },
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
                # solver 와 다른 주체가, 다른 프로세스에서 판정한다 (S8).
                "verifier_id": VERIFIER_ID,
                "candidate_digest": _shatext(value),
            },
        )
        state["solved"] = state["solved"] or verdict
        reply = "correct" if verdict else "incorrect"
        # **관찰로 남긴다.** 처음에는 `observe=False` 였고 S4.1 이 그것을 잡았다 —
        # `tool.completed` 에 출력 연결이 없으면 그 도구 호출은 증거로 인용될 수 없다.
        # 검사기가 옳았고 런타임을 고쳤다.
        # **틀렸다고 끝내지 않는다.** 끝내면 S8.5 를 행사한 run 이 전부 1회로 끝난다.
        return ToolOutcome(reply.encode(), 0, reply=reply, terminal=bool(verdict))

    return [
        Tool(
            name="run_command",
            description=(
                "Run one command inside the container and get its output. "
                'Example: run_command(argv=["ls", "-l", "/work"])'
            ),
            properties={
                "argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "argv vector; argv[0] is the program",
                }
            },
            required=["argv"],
            run=run_command,
        ),
        Tool(
            name="write_file",
            description=(
                "Write a text file under /work so you can run it. "
                'Example: write_file(path="/work/solve.py", content="print(1)")'
            ),
            properties={
                "path": {"type": "string", "description": "absolute path under /work/"},
                "content": {"type": "string", "description": "file contents"},
            },
            required=["path", "content"],
            run=write_file,
        ),
        Tool(
            name="submit_flag",
            description=(
                "Submit the flag once you have it. "
                'Example: submit_flag(value="kisia{...}")'
            ),
            properties={"value": {"type": "string", "description": "the full flag"}},
            required=["value"],
            run=submit_flag,
        ),
    ]


def _answer_is_known(fixture: Fixture) -> bool:
    """정답이 있는가를 **verifier 에게 묻는다** — 러너가 `answer.json` 을 열지 않는다.

    러너가 직접 파일을 읽어 `flag` 키를 보면 그 순간 평문 정답이 solver 프로세스 안에
    들어온다. E 가 그렇게 했고 그것이 S8 이 REWRITE 인 이유다(`verifier.py` 머리말,
    `PATH_SCOPE.md` §1). 빈 후보 하나를 태워 `n/a` 가 오는지만 본다 — 통로로 넘어가는
    것은 여전히 후보 문자열이고 돌아오는 것은 verdict 하나다.

    이 호출은 어떤 이벤트도 내지 않는다. 후보가 아니라 **모드 질의**다.
    """
    return _verify(fixture.answer_path, "") is not None


def _negative_candidate(
    w: EnvelopeWriter, rec: TrackingRecorder, ws: Workspace, fixture: Fixture
) -> bool:
    """A-4 — 틀린 후보 하나를 **환경에서** 만들어 verifier 에 태운다 (S8.5).

    골든이 `solve.py flag-off-by-one` 으로 하던 것과 같다. 값을 지어내지 않는 것이
    요점이다(`D-24`) — 관찰에서 뽑은 tag 와 합계를 그대로 쓰고 마지막 자리만
    어긋나게 한다. 모델의 후보와 섞이지 않도록 `method` 가 프로브 이름을 나른다.
    """
    res = ws.exec_(["sh", "-c", "strings -n 8 /work/notes.bin | grep TAGSEL"])
    tag = ""
    if res.exit_code == 0:
        head = res.text.strip().split("TAGSEL:")
        tag = head[1].strip().split()[0] if len(head) > 1 else ""
    if not tag:
        return False
    ws.put("/work", "_probe_a4.py", _A4_PY.encode("utf-8"))
    res = ws.exec_(["python3", "/work/_probe_a4.py", tag])
    if res.exit_code != 0:
        return False
    wrong = res.text.strip()
    oid = rec.observe("probe:A-4 environment-derived wrong candidate", res.out)
    w.emit(
        "candidate.produced",
        {"value": wrong, "derived_from": [oid], "method": "probe:A-4"},
    )
    w.emit(
        "verification.completed",
        {
            "verdict": _verify(fixture.answer_path, wrong),
            "verifier_id": VERIFIER_ID,
            "candidate_digest": _shatext(wrong),
        },
    )
    return True


#: A-4 의 계산. **정답 문자열이 들어 있지 않다** — ledger 를 읽어 합을 내고 그 합을
#: 하나 어긋나게 한다. 들어 있으면 S8.3 의 `container:/work` 스윕이 그것을 잡고,
#: 그것이 옳은 동작이다.
_A4_PY = '''\
import sys

tag = sys.argv[1]
total = 0
with open("/work/ledger.csv") as fh:
    next(fh)
    for line in fh:
        _id, g, v = line.rstrip("\\n").split(",")
        if g == tag:
            total += int(v)
print("kisia{%s_%d}" % (tag, total + 1))
'''


# ---------------------------------------------------------------------------
# attempt
# ---------------------------------------------------------------------------


def run_attempt(
    *,
    out_path: Path,
    attempt: str,
    fixture: Fixture,
    pricing: Path,
    image: str,
    host_id: str,
    api_key: str,
    model_id: str,
    effort: str,
    capability_probe: Path,
    capability_probe_id: str,
    #: **기본값이 없다.** `control.DEFAULTS` 말미가 이유를 적는다 — 라벨의 기본값은
    #: 지표 전체를 오염시킨다. 호출자가 선언하지 않으면 attempt 가 시작조차 못 한다.
    accounting_label: str,
    solve_k: int,
    #: 통제 블록의 나머지 두 갈래. 기본값은 지금까지 박혀 있던 값 그대로다.
    challenge_set: str = "dev",
    provenance: str = "synthetic",
    #: `image_digest[].image` 의 이름. 매니페스트에 없고 digest 에서 되찾을 수도 없어서
    #: (실측: `image` 는 `sha256:…` 뿐이다) 인자로 받는다.
    image_name: str = "kisia/worker-a",
    max_turns: int = 14,
    usd_budget: Decimal = Decimal("1.00"),
    token_budget: int = 400_000,
    cli: DockerCli | None = None,
    send_effort: str | None = None,
    fail_on_degradation: bool = True,
    #: **세션마다 다르다.** 박아 두면 다음 세션의 스트림이 앞 세션의 run 으로
    #: 기록되고 §10-1 의 판정 원본 귀속이 어긋난다.
    #: 빈 문자열이면 §5 예약 이벤트를 끈다 — 발행자를 대조군으로 빼기 위한
    #: 유일한 통로다. 기본값은 챌린지 id (`D-71`).
    attempt_family: str | None = None,
    run_id: str = "rebuild-7-agent-a",
) -> dict[str, Any]:
    """attempt 하나. `send_effort` 를 주면 **음성 대조**다 — 통제 블록이 선언한 값과
    다른 effort 로 실제 요청을 보내 S3.5 가 그 어긋남을 잡는지 잰다."""
    manifest = fixture.manifest()
    limit = int(manifest["display_limit_bytes"])
    # **챌린지의 사실은 챌린지에서 읽는다** (`O-57`). 모듈 상수는 fixture 의 값이었고
    # 대회 챌린지에서는 틀린다. `MANIFEST.md` §2.1·§2.2 가 둘 다 필수 필드로 적는다.
    challenge_id = str(manifest["challenge_id"])
    flag_format = str(manifest["flag_format"])
    rates = load_rates(pricing)
    if model_id not in rates:
        raise SystemExit(f"단가표에 {model_id!r} 행이 없다 — CONFIG_INVALID_PRICING")
    snapshot = probe_snapshot(capability_probe, model_id)

    # **정답이 있는지 먼저 묻는다.** A-4 와 S8.3 스윕은 대조할 정답이 있어야 성립하고,
    # 없으면 `PROBES` 가 그것을 켰다고 적어서는 안 된다 (§6.4).
    answer_known = _answer_is_known(fixture)
    probes = PROBES if answer_known else [p for p in PROBES if p != "A-4"]

    cli = cli or DockerCli()
    ws = Workspace(cli, attempt, image=image)
    started = time.monotonic()
    notes: dict[str, Any] = {"attempt": attempt, "model_id": model_id, "effort": effort}
    state: dict[str, Any] = {"artifacts": [], "submitted": [], "solved": False}

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
                probes=probes,
                challenge_set=challenge_set,
                provenance=provenance,
                accounting_label=accounting_label,
                solve_k=solve_k,
            ),
        )
        rec = TrackingRecorder(w, limit)
        w.start()
        created = ws.create(command=["sleep", str(WORKSPACE_LIFETIME_S)])

        try:
            ws.put("/input", "bundle.tar.gz", fixture.bundle.read_bytes())
            in_bytes = ws.get("/input/bundle.tar.gz")
            if in_bytes is None:
                raise RuntimeError("/input 에 넣은 파일을 되읽지 못했다")
            w.emit(
                "input.bound",
                {
                    "challenge_id": challenge_id,
                    "manifest_sha256": "sha256:" + fixture.manifest_sha256(),
                    "files": [
                        {
                            "path": "/input/bundle.tar.gz",
                            "sha256": _sha(in_bytes),
                            "bytes": len(in_bytes),
                        }
                    ],
                },
            )
            w.emit("workspace.created", created)

            client = ResponsesClient(
                api_key=api_key,
                model_id=model_id,
                effort=effort,
                rates=rates[model_id],
                # 같은 챌린지의 attempt 들이 접두 캐시를 공유한다. `usd` 는 그만큼
                # 달라지고 그것이 기록된다 — 재는 값은 아무것도 바뀌지 않는다.
                cache_key=f"kisia-{challenge_id}",
            )
            loop = AgentLoop(
                writer=w,
                recorder=rec,
                client=client,
                tools=_build_tools(w=w, rec=rec, ws=ws, fixture=fixture, state=state),
                system_prompt=SYSTEM_PROMPT,
                task_prompt=TASK_PROMPT.format(
                    description=str(manifest.get("description", "")).strip(),
                    flag_format=str(manifest.get("flag_format", "")),
                ),
                max_turns=max_turns,
                usd_budget=usd_budget,
                state_locations=lambda: [
                    {"kind": "container_path", "ref": "/work", "droppable": False}
                ],
                artifact_count=lambda: len(state["artifacts"]),
                send_effort=send_effort,
                fail_on_degradation=fail_on_degradation,
                # §5 예약 이벤트를 켠다. 계약이 이 값의 출처를 정하지 않았고
                # 저장소 어디에도 없었다 — 챌린지 id 를 쓴다 (`D-71`).
                attempt_family=(
                    challenge_id if attempt_family is None else (attempt_family or None)
                ),
            )
            report = loop.run()
            notes["loop"] = {
                "turns": report.turns,
                "model_calls": report.model_calls,
                "tool_calls": report.tool_calls,
                "sessions_opened": report.sessions_opened,
                "turns_without_tool_call": report.turns_without_tool_call,
                "stop_reason": report.stop_reason,
                "degraded": report.degraded,
                "usd": str(report.usd),
                "hypotheses_recorded": report.hypotheses_recorded,
                "hypotheses_rejected": report.hypotheses_rejected,
                "stall_signals": report.stall_signals,
                # **"재지 못함"과 "0"은 다른 값이다** — 둘을 나란히 적는다.
                "stall_signals_not_evaluated": report.stall_signals_not_evaluated,
            }

            # -- 하니스가 내는 것 — 모델의 선택과 무관하다 -------------------------
            # P-S5-b (A-6): 표시 한도를 넘는 관찰을 **하니스가** 강제 생산한다.
            ledger = ws.get("/work/ledger.csv")
            if ledger is not None:
                w.emit(
                    "artifact.produced",
                    {
                        "artifact_id": "art-probe-01",
                        "sha256": _sha(ledger),
                        "bytes": len(ledger),
                        "producer_ref": "probe:P-S5-b",
                        "role": "probe_output",
                    },
                )
                rec.observe(
                    "probe:P-S5-b forced truncation of /work/ledger.csv",
                    ledger,
                    artifact_id="art-probe-01",
                )
                state["artifacts"].append("art-probe-01")
            notes["p_s5_b_fired"] = ledger is not None

            # A-4: **틀린 후보도 환경에서 온다** (`D-24`). 하니스가 골든과 같은
            # 계산을 off-by-one 으로 돌려 낸다 — 값을 지어내지 않는다. 모델이 첫
            # 시도에 맞히면 S8.5 를 행사할 사례가 없어 `증거 없음` 이 되고, 그것은
            # 이 프로브가 켜져 있는지의 문제이지 모델의 성질이 아니다.
            # **무정답 모드에서는 통째로 건너뛴다** — 대조할 정답이 없다. 건너뛴 것을
            # `False`("돌았는데 못 냈다")로 접지 않는다(`CLAUDE.md` §6): 다른 값이다.
            if answer_known:
                notes["a4_fired"] = _negative_candidate(w, rec, ws, fixture)
            else:
                notes["a4_fired"] = None
                notes["a4_skipped"] = "no-answer mode — 대조할 정답이 없다"

            # P-S2-a/b/c (A-3, C-3): 격리 모델이 거부한다.
            notes["refusals_fired"] = _refusals(w, ws)

            # S8.3 스윕 — 표면을 실체화해 별도 프로세스가 센다. **무정답이면 돌지
            # 않는다**: `MANIFEST.md` §2.3.a 가 *"S8.3 의 스윕은 돌지 않는다. 대조할
            # `parts` 가 없다"* 로 그 자리를 정한다. 이벤트를 내지 않는 것이 그 사실이다.
            notes["sweep_ran"] = answer_known
            if answer_known:
                w.emit("answer.sweep", _sweep_surfaces(ws, fixture, ledger or b""))

            w.emit(
                "attempt.finished",
                {
                    # **effort 가 어긋난 run 은 flag 를 맞혔어도 실패 처리다** —
                    # ADR-0001 무결성 규칙 1, `spec.md` S3.5. 두 사실을 접지 않는다:
                    # `solved` 는 notes 에 그대로 남고 여기 적히는 것은 run 의 처분이다.
                    "outcome": (
                        "solved"
                        if state["solved"] and not report.effort_mismatch
                        else "failed"
                    ),
                    "reason": (
                        "effort mismatch — run failure-processed (S3.5)"
                        if report.effort_mismatch
                        else report.stop_reason
                    ),
                    "wall_clock_s": round(time.monotonic() - started, 3),
                },
            )
        finally:
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
    notes["submitted"] = state["submitted"]
    notes["stream"] = str(out_path)
    return notes


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    ap = argparse.ArgumentParser(description="유형 A — 모델 주도 attempt")
    ap.add_argument("--fixture", required=True, type=Path)
    ap.add_argument("--pricing", required=True, type=Path)
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--capability-probe", required=True, type=Path)
    ap.add_argument("--capability-probe-id", required=True)
    ap.add_argument("--model", default="gpt-5.6-terra")
    ap.add_argument("--effort", default="none")
    ap.add_argument("--normal", type=int, default=4)
    ap.add_argument("--attempt-family", default=None,
                    help="§5 예약 이벤트의 attempt_family. 빈 문자열이면 끈다")
    ap.add_argument("--run-id", default="rebuild-7-agent-a")
    ap.add_argument("--prefix", default="r7a")
    ap.add_argument("--max-turns", type=int, default=14)
    ap.add_argument("--usd-budget", default="1.00")
    ap.add_argument("--host-id", default=os.uname().nodename if hasattr(os, "uname") else "?")
    # 음성 대조 — 선언과 다른 effort 로 실제 요청을 보낸다.
    ap.add_argument("--negative-effort", default=None)
    args = ap.parse_args(argv)

    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        print("OPENAI_API_KEY 가 비어 있다 (REBUILD_LOG 재빌드-2 §0.2)")
        return 2

    fixture = Fixture(args.fixture)
    args.out.mkdir(parents=True, exist_ok=True)
    all_notes: list[dict[str, Any]] = []

    plan: list[tuple[str, dict[str, Any]]] = [
        (f"{args.prefix}-ok-{i:02d}", {}) for i in range(1, args.normal + 1)
    ]
    if args.negative_effort:
        plan.append(
            (
                f"{args.prefix}-neg-effort",
                {"send_effort": args.negative_effort, "fail_on_degradation": False},
            )
        )

    for name, extra in plan:
        print(f"-- {name} ...", flush=True)
        notes = run_attempt(
            out_path=args.out / f"{name}.jsonl",
            attempt=name,
            fixture=fixture,
            pricing=args.pricing,
            image=args.image,
            host_id=args.host_id,
            api_key=key,
            model_id=args.model,
            effort=args.effort,
            capability_probe=args.capability_probe,
            capability_probe_id=args.capability_probe_id,
            max_turns=args.max_turns,
            run_id=args.run_id,
            attempt_family=args.attempt_family,
            usd_budget=Decimal(args.usd_budget),
            **extra,
        )
        all_notes.append(notes)
        print(f"   {json.dumps(notes.get('loop', {}), ensure_ascii=False)}")
        print(f"   solved={notes['solved']} submitted={notes['submitted']}")

    (args.out / "notes.json").write_text(
        json.dumps(all_notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
