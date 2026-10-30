"""라이트업 생성기 — 경계 · 투영의 정확성 · **이빨**.

재빌드-8, 2026-08-09. `SEAM_IMPLEMENTATION_MAP.md` §6 이 재빌드 산출물로 명명한
`writeup-generator` 의 테스트다.

---

**이것은 seam 판정이 아니다.** 생성기는 telemetry 의 투영이고 어떤 술어도 평가하지
않는다(§6 머리말). 그러므로 이 파일이 통과한다는 사실은 **어떤 seam 에 대해서도
아무것도 말하지 않는다.**

**이빨이 필요한 이유.** 라이트업은 사람이 읽는 문서라서 "그럴듯하게 비어 있는" 출력이
가장 위험하다. 실제로 재빌드-8이 그 결함을 냈다 — 세션 입출력을 도구 op 창에만
매달아 두어 도구 없이 도는 스트림(`negative-b9`)의 세션 12건이 **통째로 사라졌고**,
(b) 절이 조용히 비어 나왔다. 린트·타입·단위 테스트가 전부 통과하는 상태였고
**실행이 잡았다.** 아래 이빨은 그 실패가 돌아오면 잡는다.

`TELEMETRY_SCHEMA.md` §7.1 이 봉투 조립기의 가장 비싼 결함으로 이름 붙인 것이 정확히
이 모양이다 — "어댑터의 조용한 거짓 음성".
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from kisia.checker.model import StreamVoidError, load_stream
from kisia.writeup import project, render_markdown

ROOT = Path(__file__).resolve().parents[1]
WRITEUP = ROOT / "kisia" / "writeup"
JUDGMENTS = ROOT / "kisia_tests" / "data" / "streams"

#: 도구 호출이 0건이고 세션만 도는 스트림. 이 파일의 이빨 절반이 이것에 걸린다.
NO_TOOL_STREAM = JUDGMENTS / "2026-08-09-r6-regen-ab" / "out-b" / "negative-b9.jsonl"
#: 모델 주도 유형 A — 모든 단계가 argv 이고 저작된 solve 스크립트가 없다.
MODEL_A_STREAM = JUDGMENTS / "2026-08-09-r7-agent-ab" / "out-a" / "r7a-ok-01.jsonl"
#: 골든 유형 A — `role=solve_script` artifact 가 있으나 봉투가 바이트를 나르지 않는다.
GOLDEN_A_STREAM = JUDGMENTS / "2026-08-09-r6-regen-ab" / "out-a" / "normal-01.jsonl"

Events = list[dict[str, Any]]


def _events(path: Path) -> Events:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _rewrite(tmp_path: Path, events: Events, name: str = "shaken.jsonl") -> Path:
    """이벤트를 다시 쓰고 **`seq` 를 다시 매긴다.**

    다시 매기지 않으면 `load_stream` 의 S9.2 관문이 먼저 걸려 대상이 평가되지
    않는다 — `test_checker_teeth.py` 머리말과 같은 이유다.
    """
    for i, e in enumerate(events, start=1):
        e["seq"] = i
    out = tmp_path / name
    out.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8"
    )
    return out


def _project(path: Path) -> Any:
    return project(load_stream(path))


# ---------------------------------------------------------------------------
# 경계 — 생성기는 판정에 참여하지 않는다 (§6 머리말)
# ---------------------------------------------------------------------------


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


@pytest.mark.unit
def test_writeup_does_not_import_the_judgment_layer() -> None:
    """술어·판정을 import 하면 투영이 판정을 흉내 내기 시작한다.

    `kisia.checker.model`(스트림 판독기)만 허용한다 — 검사기와 **같은 관문**으로
    읽어야 무효 스트림을 유효한 것처럼 렌더하지 않는다.
    """
    forbidden = {"kisia.checker.predicates", "kisia.checker.judge", "kisia.checker.grounding"}
    offenders: list[str] = []
    for py in sorted(WRITEUP.rglob("*.py")):
        offenders.extend(f"{py.name}: {n}" for n in _imports(py) if n in forbidden)
    assert not offenders, (
        "라이트업 생성기가 판정 계층을 import 한다 — §6 이 가른 것이 흐려진다: "
        f"{offenders}"
    )


@pytest.mark.unit
def test_writeup_does_not_import_runtime() -> None:
    """runtime 을 끌면 vendored 트리가 딸려 오고(`D-42`) 순수 함수가 아니게 된다."""
    offenders: list[str] = []
    for py in sorted(WRITEUP.rglob("*.py")):
        offenders.extend(
            f"{py.name}: {n}" for n in _imports(py) if n.startswith("kisia.runtime")
        )
    assert not offenders, f"라이트업이 runtime 을 import 한다: {offenders}"


@pytest.mark.unit
def test_writeup_uses_only_stdlib_and_allowed_kisia() -> None:
    allowed = {"kisia.writeup", "kisia.checker.model"}
    third_party: list[str] = []
    for py in sorted(WRITEUP.rglob("*.py")):
        for name in _imports(py):
            if name.split(".")[0] in sys.stdlib_module_names:
                continue
            if any(name == a or name.startswith(a + ".") for a in allowed):
                continue
            third_party.append(f"{py.name}: {name}")
    assert not third_party, f"라이트업은 표준 라이브러리와 스트림 판독기만 쓴다: {third_party}"


@pytest.mark.unit
def test_importing_writeup_does_not_pull_runtime() -> None:
    """**별도 프로세스에서 잰다.**

    `sys.modules` 에서 `kisia.*` 를 지우고 다시 import 하는 방식은 같은 세션의 다른
    테스트를 오염시킨다 — 다시 import 된 모듈의 예외 클래스가 **다른 객체**가 되어
    모듈 수준에서 잡아 둔 참조와 `isinstance` 가 어긋난다. 재빌드-8이 실제로 그것에
    걸렸다(`test_tooth_void_stream_yields_no_writeup`). 프로세스를 가르면 격리가
    실제로 격리다.
    """
    probe = (
        "import kisia.writeup, sys; "
        "print(';'.join(sorted(m for m in sys.modules if m.startswith('kisia.runtime'))))"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, cwd=ROOT, check=True
    )
    pulled = out.stdout.strip()
    assert not pulled, f"라이트업을 import 했더니 runtime 이 딸려 왔다: {pulled}"


# ---------------------------------------------------------------------------
# 투영의 정확성
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_every_stored_stream_projects_and_renders() -> None:
    """저장된 스트림 전부에 대해 사고 없이 돌고, 빈 문서를 내지 않는다."""
    paths = sorted(JUDGMENTS.glob("*/out*/*.jsonl"))
    assert len(paths) >= 25, f"회귀 대상이 줄었다: {len(paths)}개"
    for p in paths:
        w = _project(p)
        md = render_markdown(w)
        assert md.startswith("# 라이트업 —"), p
        for label in ("## (a)", "## (b)", "## (c)", "## (d)", "## (e)"):
            assert label in md, f"{p}: {label} 절이 없다"


@pytest.mark.contract
def test_all_session_io_survives_even_without_tool_calls() -> None:
    """**이 파일의 이유.** 도구 호출 0건인 스트림의 세션 입출력이 사라지지 않는다.

    재빌드-8이 실제로 낸 결함이다 — `session.io` 를 도구 op 창에만 매달아 두었더니
    `negative-b9` 의 12건이 라이트업에서 통째로 빠졌고 (b) 가 조용히 비었다.
    """
    events = _events(NO_TOOL_STREAM)
    assert not [e for e in events if e["type"] == "tool.requested"], (
        "이 스트림은 도구 호출이 0건이어야 이 테스트가 뜻을 갖는다"
    )
    sent = [e for e in events if e["type"] == "session.io" and e.get("direction") == "out"]
    assert sent, "보낸 바이트가 있어야 한다"

    w = _project(NO_TOOL_STREAM)
    assert len(w.session_io) == len([e for e in events if e["type"] == "session.io"])
    assert w.orphan_session_io, "도구 밖 세션 입출력이 잡히지 않았다"

    md = render_markdown(w)
    for e in sent:
        payload = e["payload"]
        assert repr(payload) in md, (
            f"보낸 바이트가 라이트업에서 사라졌다: {payload!r}. "
            "도구 단계에만 매달면 이 실패가 돌아온다."
        )


@pytest.mark.contract
def test_probe_observations_are_separated_from_the_solve_path() -> None:
    """하니스 프로브를 풀이 단계로 싣지 않는다. **그러나 버리지도 않는다.**"""
    w = _project(MODEL_A_STREAM)
    assert w.probe_observations, "이 스트림에는 probe: 관찰이 있어야 한다"
    assert all(not o.from_probe for o in w.solve_observations)

    md = render_markdown(w)
    assert "부록 2. 하니스 프로브" in md
    body_c = md.split("## (c)")[1].split("## (d)")[0]
    for o in w.probe_observations:
        assert o.observation_id not in body_c, (
            f"{o.observation_id} 는 프로브인데 (c) 에 실렸다 — 라이트업이 하니스의 "
            "행동을 풀이로 보고하게 된다"
        )


@pytest.mark.contract
def test_negative_probe_candidate_is_kept_as_verifier_teeth() -> None:
    """틀린 후보(A-4)를 지우면 (d) 가 약해진다. 부록에 남는지 본다."""
    w = _project(MODEL_A_STREAM)
    assert w.probe_candidates, "A-4 가 만든 틀린 후보가 있어야 한다"
    md = render_markdown(w)
    for cnd in w.probe_candidates:
        assert cnd.value in md


@pytest.mark.contract
def test_repro_script_never_contains_the_flag() -> None:
    """재현 스크립트에 정답을 실으면 그 파일이 S8.3 스윕의 표면이 되고,
    재현 확인이 자기 자신을 확인하는 것이 된다."""
    for p in sorted(JUDGMENTS.glob("*/out*/*.jsonl")):
        w = _project(p)
        if not w.repro.script:
            continue
        for cnd in w.candidates:
            assert cnd.value not in w.repro.script, (
                f"{p}: 재현 스크립트에 후보 문자열 {cnd.value!r} 이 실렸다"
            )


@pytest.mark.contract
def test_argv_detection_is_by_shape_not_by_tool_name() -> None:
    """골든의 `exec`(리스트)와 모델 주도의 `run_command`(`{argv:[...]}`) 를 둘 다 받는다.

    도구 이름으로 가르면 계약이 열거하지 않은 것을 구현이 열거하게 된다(`spec.md` §0.1).
    """
    golden = _project(GOLDEN_A_STREAM)
    model = _project(MODEL_A_STREAM)
    assert any(s.argv for s in golden.steps), "골든의 리스트 args 가 argv 로 잡히지 않았다"
    assert any(s.argv for s in model.steps), "모델 주도의 {argv:…} 가 잡히지 않았다"
    assert {s.tool for s in golden.steps} != {s.tool for s in model.steps}


# ---------------------------------------------------------------------------
# 이빨 — 스트림의 사실 하나를 흔들면 라이트업이 알아채는가
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_tooth_missing_payload_is_reported_not_silently_empty(tmp_path: Path) -> None:
    """`session.io.payload` 를 지우면 (b) 가 **없다** 가 되고 그 자리에 부재를 적는다.

    R2-13 이 닫은 자리다. 조용히 빈 단계를 내면 라이트업이 거짓말을 한다.
    """
    events = _events(NO_TOOL_STREAM)
    shaken = 0
    for e in events:
        if e["type"] == "session.io" and e.get("direction") == "out":
            e.pop("payload", None)
            shaken += 1
    assert shaken, "흔들 대상이 없다"

    w = _project(_rewrite(tmp_path, events))
    assert w.sufficiency.b_solve_steps is False, "payload 를 지웠는데 (b) 가 있다로 나온다"
    assert any("payload" in n for n in w.sufficiency.notes)
    assert "payload 부재" in render_markdown(w)


@pytest.mark.contract
def test_tooth_missing_shown_is_reported(tmp_path: Path) -> None:
    """`observation.recorded.shown` 을 지우면 (c) 가 거짓이 된다 (A-9)."""
    events = _events(MODEL_A_STREAM)
    for e in events:
        if e["type"] == "observation.recorded":
            e.pop("shown", None)
    w = _project(_rewrite(tmp_path, events))
    assert w.sufficiency.c_observations is False
    assert "`shown` **부재**" in render_markdown(w)


@pytest.mark.contract
def test_tooth_unresolved_derived_from_is_reported(tmp_path: Path) -> None:
    """`derived_from` 이 없는 관찰을 가리키면 (d) 가 거짓이 되고 그 id 를 적는다."""
    events = _events(MODEL_A_STREAM)
    for e in events:
        if e["type"] == "candidate.produced" and not e.get("method", "").startswith("probe:"):
            e["derived_from"] = ["obs-없는-것"]
    w = _project(_rewrite(tmp_path, events))
    assert w.sufficiency.d_success_evidence is False
    assert "obs-없는-것" in render_markdown(w)


@pytest.mark.contract
def test_tooth_unpaired_tool_call_is_reported(tmp_path: Path) -> None:
    """`tool.completed` 를 하나 지우면 (a) 가 거짓이 되고 그 단계를 **미완**으로 적는다."""
    events = _events(MODEL_A_STREAM)
    for i, e in enumerate(events):
        if e["type"] == "tool.completed":
            del events[i]
            break
    w = _project(_rewrite(tmp_path, events))
    assert w.sufficiency.a_tool_order is False
    assert "**미완**" in render_markdown(w)


@pytest.mark.contract
def test_tooth_void_stream_yields_no_writeup(tmp_path: Path) -> None:
    """`seq` 에 빈틈이 있으면 라이트업을 내지 않는다 (S9.2).

    무효인 스트림에서 만든 풀이 기록은 근거 없는 서사가 된다.
    """
    events = _events(MODEL_A_STREAM)
    del events[5]  # seq 를 **다시 매기지 않는다** — 빈틈을 만드는 것이 목적이다
    bad = tmp_path / "void.jsonl"
    bad.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8"
    )
    with pytest.raises(StreamVoidError):
        load_stream(bad)


# ---------------------------------------------------------------------------
# 세 값 — "수행하지 못함"과 "0"을 접지 않는다 (`CLAUDE.md` §6)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_no_tool_stream_reports_a_as_not_applicable_not_absent() -> None:
    """도구를 부르지 않은 스트림의 (a) 는 **해당 없음**이지 **없다** 가 아니다."""
    w = _project(NO_TOOL_STREAM)
    assert w.sufficiency.a_tool_order is None
    assert "해당 없음" in render_markdown(w)


@pytest.mark.contract
def test_failed_attempt_reports_d_as_not_applicable() -> None:
    """실패한 attempt 에 성공 증거가 없는 것은 봉투의 결손이 아니다."""
    w = _project(NO_TOOL_STREAM)
    assert not w.solved
    assert w.sufficiency.d_success_evidence is None


@pytest.mark.contract
def test_model_driven_b_prime_is_not_applicable_golden_is_present() -> None:
    """(b') 의 두 얼굴 — 실측이 뒤집은 자리다.

    모델 주도에는 **저작된 solve 스크립트가 존재하지 않고** 모든 단계가 (b) 에
    원문으로 있다 → **해당 없음.** 골든에는 그 artifact 가 있으나 봉투가 `sha256`
    만 나르고 바이트를 나르지 않는다 → **있다, 그러나 재현되지 않는다.**
    """
    model = _project(MODEL_A_STREAM)
    golden = _project(GOLDEN_A_STREAM)

    assert model.sufficiency.b_prime_solve_script is None
    assert not model.repro.hash_only
    assert model.repro.script and model.repro.argv_steps > 0

    assert golden.sufficiency.b_prime_solve_script is True
    assert golden.repro.hash_only, "골든의 solve_script 가 해시 전용으로 잡히지 않았다"
    assert any("재현되지 않는다" in g for g in golden.gaps)


@pytest.mark.contract
def test_gaps_never_include_not_applicable_items() -> None:
    """해당 없음은 **채우지 못한 자리가 아니다.** gaps 에 들어가면 안 된다."""
    w = _project(MODEL_A_STREAM)
    assert w.sufficiency.b_prime_solve_script is None
    assert not any(g.startswith("(b')") for g in w.gaps), (
        f"해당 없음이 gaps 에 실렸다: {w.gaps}"
    )


@pytest.mark.contract
def test_colliding_attempt_ids_are_refused_not_silently_overwritten(tmp_path: Path) -> None:
    """`attempt_id` 가 같은 스트림 둘을 한 `--out` 에 쓰면 **죽는다.**

    실측: 재빌드-6이 r4·r5의 attempt 를 같은 `attempt_id` 로 다시 돌렸으므로
    (`O-23` 의 골든 재실행) 30개 스트림이 25개 파일로 떨어졌다 — 다섯이 조용히
    덮였다. `TELEMETRY_SCHEMA.md` §7.1 은 이름 충돌에 대해 "조용히 덮어쓰지 않고
    죽어야 한다"를 **요구되는 성질**로 적는다.
    """
    from kisia.writeup.__main__ import main

    a = JUDGMENTS / "2026-08-08-r5-golden-b" / "out" / "normal-01.jsonl"
    b = JUDGMENTS / "2026-08-09-r6-regen-ab" / "out-b" / "normal-01.jsonl"
    assert _project(a).attempt_id == _project(b).attempt_id, (
        "이 두 스트림의 attempt_id 가 같아야 이 테스트가 뜻을 갖는다"
    )
    rc = main([str(a), str(b), "--out", str(tmp_path)])
    assert rc == 2, "충돌인데 죽지 않았다 — 하나가 조용히 사라진다"
    assert len(list(tmp_path.glob("*.md"))) == 1


@pytest.mark.contract
def test_absent_self_report_renders_as_absent_not_zero() -> None:
    """`usd_self_reported` 는 **부재**다. `0` 으로 적으면 거짓 관측이다."""
    w = _project(MODEL_A_STREAM)
    usd = [s for s in w.self_reports if "usd" in s.label]
    assert usd, "model.completed 의 자기 보고 쌍이 없다"
    assert all(s.self_reported is None for s in usd)
    md = render_markdown(w)
    assert "**부재**" in md
    assert "부록 3. 자기 보고" in md
