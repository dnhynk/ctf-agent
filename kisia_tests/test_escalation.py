"""escalation 패킷 컴파일러 — 경계 · 세 절의 정확성 · **이빨**.

프로덕션-2, 2026-08-09. `SEAM_IMPLEMENTATION_MAP.md` §6 이 재빌드 산출물로 명명한
`escalation-packet-compiler` 의 테스트다.

---

**이것은 seam 판정이 아니다.** 컴파일러는 telemetry 의 투영이고 어떤 술어도 평가하지
않는다(§6 머리말). 그러므로 이 파일이 통과한다는 사실은 **어떤 seam 에 대해서도
아무것도 말하지 않는다.**

**이빨이 필요한 이유가 라이트업보다 하나 더 있다.** §5 예약 이벤트에는 **술어가
없다**(`TELEMETRY_SCHEMA.md` §5.1, `R2-15`). 검사기가 이 이벤트들을 읽지 않으므로
컴파일러가 셋을 잘못 가르거나 조용히 접어도 **검사기가 잡아 주지 않는다.** 여기서
잡지 않으면 아무 데서도 잡히지 않는다.

이 파일이 재는 것:

1. **경계** — 판정 계층도 `kisia.runtime` 도 끌지 않는다 (`D-59`, 별도 프로세스 확인).
2. **셋을 가르는가** — 접지됨 / 접지 안 됨 / 가설 없음. 실측 세 디렉터리가 서로 다른
   답을 내야 한다. 셋이 같은 모양이면 컴파일러가 못 가르고 있는 것이다(`D-63`).
3. **CONFIRMED 를 다시 만들지 않는가** — 하니스가 `_own_tools` 로 이미 가른 것을 쓴다
   (`O-36` / 경고 13). 관찰 전체에서 고르면 하니스 자신의 도구가 만든 관찰이 섞인다.
4. **telemetry-only** — `input.bound.files[]` 와 `artifact.produced` 가 건너가지 않는다
   (`ADR-0003` Decision-3, `SAFETY_SCOPE.md` 조건 2).
5. **S8.3** — 밖으로 나가는 표면에 정답이 실리지 않는다.
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
from kisia.escalation import compile_packet, render_markdown
from kisia.escalation.model import (
    ANSWER_ELIDED,
    GROUNDED,
    NO_HYPOTHESIS,
    UNGROUNDED,
    Packet,
)

ROOT = Path(__file__).resolve().parents[1]
ESCALATION = ROOT / "kisia" / "escalation"
JUDGMENTS = ROOT / "kisia_tests" / "data" / "streams"

#: 프로덕션-1 이 §5 예약 이벤트를 처음으로 발행한 세 디렉터리. **셋이 서로 다른 답을
#: 내야 한다** — `JUDGMENT.md` §2 의 실측이다.
P1 = JUDGMENTS / "2026-08-09-p1-publisher-agentc"
#: 가설 0건 (도구를 노출만 했다).
STALL = sorted((P1 / "out-b-stall").glob("*.jsonl"))
#: 가설 3건, 전부 접지 실패 (모델이 없는 id 를 댔다).
STALL2 = sorted((P1 / "out-b-stall2").glob("*.jsonl"))
#: 가설 3건, 전부 접지 성공 (stall 요청이 실재하는 id 를 함께 실었다).
STALL3 = sorted((P1 / "out-b-stall3").glob("*.jsonl"))
ALL_STALL = [*STALL, *STALL2, *STALL3]

Events = list[dict[str, Any]]


def _events(path: Path) -> Events:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _rewrite(tmp_path: Path, events: Events, name: str = "shaken.jsonl") -> Path:
    """이벤트를 다시 쓰고 **`seq` 를 다시 매긴다.**

    다시 매기지 않으면 `load_stream` 의 S9.2 관문이 먼저 걸려 대상이 평가되지 않는다
    — `test_writeup.py` 와 같은 이유다. **`stall.observed.confirmed_facts` 는 id 로
    가리키므로 seq 를 다시 매겨도 지목이 깨지지 않는다.**
    """
    for i, e in enumerate(events, start=1):
        e["seq"] = i
    out = tmp_path / name
    out.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8"
    )
    return out


def _packet(path: Path) -> Packet:
    return compile_packet(load_stream(path))


def _text(p: Packet) -> str:
    """패킷이 실제로 밖으로 나르는 전부 — 마크다운과 JSON 둘 다."""
    return render_markdown(p) + json.dumps(p.as_json(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# 0. 시험의 전제 — 입력이 실제로 그 모양인가
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_measured_inputs_are_what_this_file_assumes() -> None:
    """**전제가 깨지면 아래 전부가 조용히 공허해진다.**

    실측(`JUDGMENT.md` §2): 8 스트림 · `stall.observed` 8 · `hypothesis.recorded` 6 ·
    `hypothesis.rejected` 0.
    """
    assert len(STALL) == 2, STALL
    assert len(STALL2) == 3, STALL2
    assert len(STALL3) == 3, STALL3
    packets = [_packet(p) for p in ALL_STALL]
    assert sum(len(p.stalls) for p in packets) == 8
    assert sum(len(p.inferred) for p in packets) == 6
    assert sum(len(p.rejected) for p in packets) == 0


# ---------------------------------------------------------------------------
# 1. 경계 — 컴파일러는 판정에 참여하지 않는다 (`D-59`)
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
def test_escalation_does_not_import_the_judgment_layer() -> None:
    """술어·판정을 import 하면 패킷이 판정을 흉내 내기 시작한다.

    `kisia.checker.model`(스트림 판독기)만 허용한다 — 검사기와 **같은 관문**으로 읽어야
    무효 스트림을 유효한 것처럼 컴파일하지 않는다. 라이트업의 같은 시험과 같은 형태이고
    이쪽은 이유가 하나 더 있다: §5 예약 이벤트에는 술어가 없다(`R2-15`).
    """
    forbidden = {"kisia.checker.predicates", "kisia.checker.judge", "kisia.checker.grounding"}
    offenders: list[str] = []
    for py in sorted(ESCALATION.rglob("*.py")):
        offenders.extend(f"{py.name}: {n}" for n in _imports(py) if n in forbidden)
    assert not offenders, (
        "escalation 컴파일러가 판정 계층을 import 한다 — §6 이 가른 것이 흐려진다: "
        f"{offenders}"
    )


@pytest.mark.unit
def test_escalation_does_not_import_runtime() -> None:
    """runtime 을 끌면 vendored 트리가 딸려 오고(`D-42`) 순수 함수가 아니게 된다.

    **여기서는 `SAFETY_SCOPE.md` 조건 6(코어 하류)이기도 하다** — escalation 은 worker
    안에서 돌지 않는다.
    """
    offenders: list[str] = []
    for py in sorted(ESCALATION.rglob("*.py")):
        offenders.extend(
            f"{py.name}: {n}" for n in _imports(py) if n.startswith("kisia.runtime")
        )
    assert not offenders, f"escalation 이 runtime 을 import 한다: {offenders}"


@pytest.mark.unit
def test_escalation_uses_only_stdlib_and_allowed_kisia() -> None:
    allowed = {"kisia.escalation", "kisia.checker.model"}
    third_party: list[str] = []
    for py in sorted(ESCALATION.rglob("*.py")):
        for name in _imports(py):
            if name.split(".")[0] in sys.stdlib_module_names:
                continue
            if any(name == a or name.startswith(a + ".") for a in allowed):
                continue
            third_party.append(f"{py.name}: {name}")
    assert not third_party, f"컴파일러는 표준 라이브러리와 스트림 판독기만 쓴다: {third_party}"


@pytest.mark.unit
def test_importing_escalation_does_not_pull_runtime() -> None:
    """**별도 프로세스에서 잰다.**

    `sys.modules` 를 지우고 다시 import 하는 방식은 같은 세션의 다른 테스트를 오염시킨다
    — 다시 import 된 모듈의 예외 클래스가 **다른 객체**가 되어 `isinstance` 가 어긋난다.
    재빌드-8이 실제로 그것에 걸렸다. 프로세스를 가르면 격리가 실제로 격리다.
    """
    probe = (
        "import kisia.escalation, sys; "
        "print(';'.join(sorted(m for m in sys.modules if m.startswith('kisia.runtime'))))"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, cwd=ROOT, check=True
    )
    pulled = out.stdout.strip()
    assert not pulled, f"컴파일러를 import 했더니 runtime 이 딸려 왔다: {pulled}"


@pytest.mark.unit
def test_the_compiler_does_not_attach_a_predicate_to_the_reserved_events() -> None:
    """§5.1 / `R2-15` — 검사기가 이 이름들을 알면 예약이 예약이 아니게 된다.

    `test_reserved_events.py` 의 같은 이름 시험이 검사기 쪽을 잠근다. 이쪽은 **컴파일러가
    생기면서 그 규칙이 뒤로 새지 않는지**를 잰다: 컴파일러가 예약 이벤트를 읽는 것은
    맞지만, 그 읽기가 술어 계층으로 흘러 들어가면 안 된다.
    """
    src = (ROOT / "kisia" / "checker" / "predicates.py").read_text(encoding="utf-8")
    for name in ("hypothesis.recorded", "hypothesis.rejected", "stall.observed"):
        assert name not in src, f"검사기가 {name} 를 읽는다 — §5.1 위반"
    assert "kisia.escalation" not in src, "검사기가 컴파일러를 import 한다 — §5.1 위반"


@pytest.mark.contract
def test_a_void_stream_yields_no_packet(tmp_path: Path) -> None:
    """S9.2 — 빈틈이 있으면 그 attempt 의 모든 판정이 무효다. **패킷도 내지 않는다.**"""
    events = _events(STALL3[0])
    del events[5]
    out = tmp_path / "gap.jsonl"
    out.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8"
    )
    with pytest.raises(StreamVoidError):
        _packet(out)


# ---------------------------------------------------------------------------
# 2. 셋을 가른다 — 접지됨 / 접지 안 됨 / 가설 없음 (`D-63` 이 난 자리)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_three_directories_do_not_compile_to_the_same_shape() -> None:
    """**셋이 같은 모양으로 나오면 컴파일러가 셋을 못 가르고 있는 것이다.**

    실측(`JUDGMENT.md` §2.1·§2.2):
    `out-b-stall` 가설 0 · `out-b-stall2` 접지 실패 3 · `out-b-stall3` 접지 성공 3.
    """
    assert [_packet(p).grounding for p in STALL] == [NO_HYPOTHESIS] * 2
    assert [_packet(p).grounding for p in STALL2] == [UNGROUNDED] * 3
    assert [_packet(p).grounding for p in STALL3] == [GROUNDED] * 3


@pytest.mark.contract
def test_no_hypothesis_is_not_ungrounded() -> None:
    """**둘로 접으면 `D-63` 이 난 자리를 다시 만든다.**

    "가설이 없다"와 "가설이 있는데 접지되지 않았다"는 다른 사실이고, 접으면 다음 세션이
    `out-b-stall` 을 보고 "모델이 근거 없는 가설을 냈다"고 읽는다.
    """
    none = _packet(STALL[0])
    bad = _packet(STALL2[0])
    assert none.inferred == ()
    assert len(bad.inferred) == 1
    assert none.grounding != bad.grounding
    assert "가설 없음" in render_markdown(none)
    assert "접지 안 됨" in render_markdown(bad)


@pytest.mark.contract
def test_an_ungrounded_hypothesis_carries_both_the_claim_and_the_filtered_result() -> None:
    """접지 실패는 **결손이 아니다.** 원인은 구조였고 주장 원문이 스트림에 남아 있다.

    `JUDGMENT.md` §2.2 — 도구 응답이 `observation_id` 를 나르지 않아 모델이 실제 id 를
    한 번도 본 적이 없었다. 두 값을 나란히 싣지 않으면 그 사실을 읽을 수 없다.
    """
    p = _packet(STALL2[0])
    (inf,) = p.inferred
    assert inf.supported_by == ()
    assert inf.claimed_support, "모델의 주장 원문을 `tool.requested.args` 에서 찾지 못했다"
    assert inf.dropped_claims == inf.claimed_support
    md = render_markdown(p)
    assert "모델이 실제로 댄 것" in md
    assert "하니스가 거른 id" in md


@pytest.mark.contract
def test_a_grounded_hypothesis_points_at_ids_that_are_confirmed_facts() -> None:
    """**사슬이 끝까지 이어진다:** CONFIRMED(관찰 id) ← INFERRED(`supported_by`)."""
    for path in STALL3:
        p = _packet(path)
        (inf,) = p.inferred
        assert inf.supported_by, path
        confirmed = {f.observation_id for f in p.confirmed}
        assert set(inf.supported_by) <= confirmed, (
            f"{path}: 접지된 가설이 CONFIRMED 에 없는 id 를 가리킨다"
        )


@pytest.mark.contract
def test_an_empty_rejected_section_is_zero_and_not_unmeasured() -> None:
    """`hypothesis.rejected` 0건은 **`0`이고 `재지 못함`이 아니다** (`JUDGMENT.md` §2).

    빈 절을 지우면 그 구분이 문서에서 사라진다.
    """
    for path in ALL_STALL:
        p = _packet(path)
        assert p.rejected == ()
        md = render_markdown(p)
        assert "## REJECTED" in md, f"{path}: 빈 절이 통째로 사라졌다"
        assert "재지 못함" in md


# ---------------------------------------------------------------------------
# 3. CONFIRMED 는 하니스가 이미 가른 것이다 — `O-36` / 물려받은 경고 13
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_confirmed_comes_from_the_stall_and_not_from_every_observation() -> None:
    """**관측 장치를 관측 대상 안에 넣지 마라.**

    `loop.py` 의 `_own_tools` 필터가 하니스 자신의 도구(`record_hypothesis`)가 만든
    관찰을 `_env_obs` 에서 이미 뺐고, `stall.observed.confirmed_facts[]` 가 그 결과다.
    컴파일러가 `observation.recorded` 전체에서 고르면 그 필터가 무효가 된다.

    실측: `out-b-stall2`/`3` 의 `obs-0005` 는 `tool:record_hypothesis …` 가 낸 관찰이다.
    """
    for path in [*STALL2, *STALL3]:
        p = _packet(path)
        ids = {f.observation_id for f in p.confirmed}
        total = {
            e["observation_id"] for e in _events(path) if e["type"] == "observation.recorded"
        }
        assert ids < total, f"{path}: CONFIRMED 가 관찰 전체와 같다 — 필터가 사라졌다"
        for f in p.confirmed:
            assert f.source_ref is not None
            assert "record_hypothesis" not in f.source_ref, (
                f"{path}: 하니스 자신의 도구가 만든 관찰이 CONFIRMED 에 들어갔다 (`O-36`)"
            )
        assert "obs-0005" in p.not_promoted


@pytest.mark.contract
def test_probe_observations_do_not_reach_confirmed() -> None:
    """프로브는 하니스가 술어를 평가 가능하게 만들려고 개입한 것이고 풀이 경로가 아니다.

    라이트업이 `probe:` 접두로 가르는 것과 **같은 사실을 다른 경로로** 확인한다 —
    이쪽은 접두를 보지 않고, stall 이 지목하지 않았다는 사실만으로 빠진다.
    """
    for path in ALL_STALL:
        p = _packet(path)
        for f in p.confirmed:
            assert f.source_ref is not None
            assert not f.source_ref.startswith("probe:"), f"{path}: {f.observation_id}"


@pytest.mark.contract
def test_a_named_fact_that_is_not_in_the_stream_is_reported_not_dropped() -> None:
    """stall 이 이름을 댔는데 관찰이 없으면 **조용히 버리지 않는다.**

    버리면 패킷이 "그런 사실은 없었다"고 말하게 되고, 그것은 봉투의 결손을 패킷이
    대신 메우는 것이다.
    """
    p = _packet(STALL3[0])
    assert p.unresolved_facts == ()


# ---------------------------------------------------------------------------
# 4. telemetry-only — `ADR-0003` Decision-3 / `SAFETY_SCOPE.md` 조건 2
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_packet_does_not_carry_input_files_or_artifacts() -> None:
    """**raw 챌린지 입력 파일과 artifact 는 건너가지 않는다.**

    라이트업은 둘 다 싣는다 — 그것이 옳다. 갈리는 이유는 **라이트업이 밖으로 나가지
    않기 때문**이고, 이 시험이 그 차이를 잠근다.
    """
    for path in ALL_STALL:
        p = _packet(path)
        blob = _text(p)
        events = _events(path)
        bound = next(e for e in events if e["type"] == "input.bound")
        for f in bound["files"]:
            assert f["path"] not in blob, f"{path}: 입력 파일 경로 {f['path']} 가 실렸다"
            assert f["sha256"] not in blob, f"{path}: 입력 파일 해시가 실렸다"
        for e in events:
            if e["type"] == "artifact.produced":
                assert e["sha256"] not in blob, f"{path}: artifact 해시 {e['artifact_id']}"


@pytest.mark.contract
def test_the_packet_does_not_carry_our_infrastructure() -> None:
    """통제 블록 전체를 싣지 않는다 — 밖의 모델이 막힌 문제를 보는 데 필요하지 않다."""
    for path in ALL_STALL:
        p = _packet(path)
        blob = _text(p)
        control = next(e for e in _events(path) if e["type"] == "attempt.started")
        for key in ("host_id", "pricing_sha256", "challenge_manifest_sha256"):
            assert str(control[key]) not in blob, f"{path}: {key} 가 실렸다"
        for img in control["image_digest"]:
            assert img["id"] not in blob, f"{path}: 이미지 digest 가 실렸다"


# ---------------------------------------------------------------------------
# 5. S8.3 — 밖으로 나가는 표면에 정답이 실리지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_packet_never_contains_the_candidate_value() -> None:
    """패킷에 정답을 실으면 그 파일이 S8.3 스윕의 표면이 된다.

    라이트업의 `test_repro_script_never_contains_the_flag` 와 같은 형태다. **저장된
    판정 전체에 건다** — stall 스트림에는 후보가 0건이라 그것만으로는 공허해진다.

    **이 시험 하나로는 이빨이 약하다는 것을 실측했다.** 정답 제거를 통째로 꺼도(변이
    M2) 이 시험은 통과한다 — 후보를 가진 스트림에는 `stall.observed` 가 없어 CONFIRMED
    가 비고, 그러면 대조할 챌린지 내용 자체가 패킷에 없기 때문이다. 실제로 무는 것은
    아래 `test_tooth_an_answer_inside_*` 둘이다. 그래도 이 시험을 두는 이유는 **패킷이
    지금보다 더 많이 싣게 되는 날**을 잡기 위해서다.
    """
    checked = 0
    for path in sorted(JUDGMENTS.glob("*/out*/*.jsonl")):
        try:
            p = _packet(path)
        except StreamVoidError:
            continue
        blob = _text(p)
        for e in _events(path):
            if e["type"] != "candidate.produced":
                continue
            checked += 1
            assert e["value"] not in blob, f"{path}: 패킷에 후보 문자열 {e['value']!r} 이 실렸다"
    assert checked, "후보를 가진 스트림이 하나도 없다 — 이 시험이 공허하다"


@pytest.mark.contract
def test_a_stream_without_candidates_says_so_instead_of_claiming_it_scrubbed() -> None:
    """**"제거할 것이 없었다"와 "지목할 수 없었다"를 접지 않는다.**

    후보가 0건이면 스트림만으로 정답을 지목할 수 없고, 그 한계가 패킷에 적혀야 한다.
    """
    p = _packet(STALL3[0])
    assert p.redactions == ()
    assert any("수행되지 않았다" in n for n in p.notes), p.notes


# ---------------------------------------------------------------------------
# 6. 이빨 — 스트림의 사실 하나를 흔들면 컴파일러가 알아채는가
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_tooth_an_answer_inside_an_observation_is_scrubbed(tmp_path: Path) -> None:
    """**가장 비싼 결함이 여기 있다.** 봉투는 관찰 바이트를 원문 그대로 나르고
    (`TELEMETRY_SCHEMA.md` §6), 푼 attempt 의 관찰에는 정답이 들어 있다. 패킷이 그것을
    그대로 실으면 밖으로 나가는 표면에 정답이 실린다.

    실측 8 스트림에는 후보가 0건이라 **이 자리는 변이로만 잴 수 있다.**
    """
    events = _events(STALL3[0])
    answer = "kisia{c41d_deadbeef}"
    for e in events:
        if e["type"] == "observation.recorded" and e["observation_id"] == "obs-0003":
            e["shown"] = f"READ ok -> {answer}\n"
    events.append(
        {
            "ts": "2026-08-08T21:13:59.000000Z",
            "run_id": events[0]["run_id"],
            "attempt_id": events[0]["attempt_id"],
            "seq": 0,
            "type": "candidate.produced",
            "value": answer,
            "derived_from": ["obs-0003"],
            "method": "read",
        }
    )
    p = _packet(_rewrite(tmp_path, events))
    assert answer not in _text(p), "관찰 바이트에 있던 정답이 패킷으로 그대로 나갔다"
    assert p.redactions, "지웠는데 지운 사실을 남기지 않았다"
    assert ANSWER_ELIDED in render_markdown(p), "조용히 지웠다 — 자리에 표시가 없다"


@pytest.mark.contract
def test_tooth_an_answer_inside_a_hypothesis_statement_is_scrubbed(tmp_path: Path) -> None:
    """가설의 진술은 **모델이 쓴 문장**이고 거기에 정답이 들어갈 수 있다."""
    events = _events(STALL2[0])
    answer = "kisia{c41d_deadbeef}"
    for e in events:
        if e["type"] == "hypothesis.recorded":
            e["statement"] = f"the flag is {answer}"
    events.append(
        {
            "ts": "2026-08-08T21:10:59.000000Z",
            "run_id": events[0]["run_id"],
            "attempt_id": events[0]["attempt_id"],
            "seq": 0,
            "type": "candidate.produced",
            "value": answer,
            "derived_from": [],
            "method": "guess",
        }
    )
    p = _packet(_rewrite(tmp_path, events))
    assert answer not in _text(p)
    assert any("statement" in r.where for r in p.redactions), p.redactions


@pytest.mark.contract
def test_tooth_an_empty_statement_does_not_borrow_someone_elses_claim(tmp_path: Path) -> None:
    """주장 원문은 **모양으로** 찾는다 — 그런데 빈 값끼리 맞아떨어지면 안 된다.

    `args.get("statement", "")` 로만 보면 진술이 빈 가설이 `statement` 키를 아예 갖지
    않는 아무 도구 호출과 짝지어지고, 패킷이 **없는 주장 원문을 지어낸다.** '찾지 못함'과
    '비어 있음'을 접지 않는 것이 이 자리의 요구다.
    """
    events = _events(STALL3[0])
    for e in events:
        if e["type"] == "hypothesis.recorded":
            e["statement"] = ""
    p = _packet(_rewrite(tmp_path, events))
    (inf,) = p.inferred
    assert inf.claimed_support is None, (
        f"빈 진술이 남의 호출문과 짝지어졌다: {inf.claimed_support}"
    )
    assert "찾지 못했다" in render_markdown(p)


@pytest.mark.contract
def test_tooth_an_observation_after_the_stall_does_not_grow_confirmed(tmp_path: Path) -> None:
    """CONFIRMED 를 `observation.recorded` 전체에서 고르면 이 시험이 깨진다.

    stall 뒤에 온 관찰은 그 시점에 CONFIRMED 로 승격된 적이 없다 — 승격 시점이 사실의
    일부다.
    """
    events = _events(STALL3[0])
    before = len(_packet(STALL3[0]).confirmed)
    events.append(
        {
            "ts": "2026-08-08T21:13:59.000000Z",
            "run_id": events[0]["run_id"],
            "attempt_id": events[0]["attempt_id"],
            "seq": 0,
            "type": "observation.recorded",
            "observation_id": "obs-9999",
            "source_ref": "session:later",
            "bytes_total": 3,
            "bytes_shown": 3,
            "shown": "abc",
            "shown_digest": "sha256:x",
            "truncated": False,
            "full_digest": "sha256:x",
            "artifact_id": None,
        }
    )
    p = _packet(_rewrite(tmp_path, events))
    assert len(p.confirmed) == before, "stall 이 지목하지 않은 관찰이 CONFIRMED 로 들어갔다"
    assert "obs-9999" in p.not_promoted


@pytest.mark.contract
def test_tooth_emptying_supported_by_flips_grounded_to_ungrounded(tmp_path: Path) -> None:
    """접지된 스트림의 `supported_by` 를 비우면 **접지 안 됨**이 되어야 한다.

    `가설 없음` 으로 미끄러지면 둘을 접은 것이다.
    """
    events = _events(STALL3[0])
    for e in events:
        if e["type"] == "hypothesis.recorded":
            e["supported_by"] = []
    p = _packet(_rewrite(tmp_path, events))
    assert p.grounding == UNGROUNDED
    assert len(p.inferred) == 1, "가설 자체가 사라지면 안 된다"


@pytest.mark.contract
def test_tooth_deleting_the_hypotheses_gives_no_hypothesis_not_a_gap(tmp_path: Path) -> None:
    """가설을 지우면 **가설 없음**이지 결손이 아니다."""
    events = [e for e in _events(STALL3[0]) if e["type"] != "hypothesis.recorded"]
    p = _packet(_rewrite(tmp_path, events))
    assert p.grounding == NO_HYPOTHESIS
    assert any("가설 없음" in n for n in p.notes), p.notes


@pytest.mark.contract
def test_tooth_a_stall_naming_a_missing_observation_is_reported(tmp_path: Path) -> None:
    """지목된 id 가 스트림에 없으면 **조용히 버리지 않고 그 사실을 싣는다.**"""
    events = _events(STALL3[0])
    for e in events:
        if e["type"] == "stall.observed":
            e["confirmed_facts"] = [*e["confirmed_facts"], "obs-0404"]
    p = _packet(_rewrite(tmp_path, events))
    assert [f.observation_id for f in p.unresolved_facts] == ["obs-0404"]
    assert "obs-0404" in render_markdown(p)
    assert any("obs-0404" in n for n in p.notes)


@pytest.mark.contract
def test_tooth_a_redaction_sentinel_blocks_the_export(tmp_path: Path) -> None:
    """`SAFETY_SCOPE.md` 조건 3 · `PATH_SCOPE.md` §3.7 — sentinel 을 만나면 export 는
    **중단된다.** 컴파일러는 export 하지 않으므로 중단시키지 않고 사유를 싣는다.
    """
    assert _packet(STALL3[0]).export_blockers == ()
    events = _events(STALL3[0])
    for e in events:
        if e["type"] == "observation.recorded" and e["observation_id"] == "obs-0002":
            e["shown"] = "token=<redacted:api_key>\n"
    p = _packet(_rewrite(tmp_path, events))
    assert any("sentinel" in b for b in p.export_blockers), p.export_blockers
    assert "export 되면 안 된다" in render_markdown(p)


@pytest.mark.contract
def test_tooth_a_stream_that_never_stalled_is_not_an_escalation(tmp_path: Path) -> None:
    """escalation 은 정의상 **막힌** attempt 의 것이다 (`SEAM_IMPLEMENTATION_MAP.md` §6).

    막히지 않은 attempt 의 챌린지 유래 내용을 밖으로 보낼 근거가 없다.
    """
    events = [e for e in _events(STALL3[0]) if e["type"] != "stall.observed"]
    p = _packet(_rewrite(tmp_path, events))
    assert not p.stalled
    assert p.confirmed == ()
    assert any("막힌 것으로 관측된 적이" in b for b in p.export_blockers), p.export_blockers


# ---------------------------------------------------------------------------
# 7. CLI — `python -m kisia.escalation`
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_cli_writes_utf8_and_the_three_directories_differ(tmp_path: Path) -> None:
    """**출력이 기계마다 달라지면 안 된다** (R3-8). Windows 기본 인코딩은 cp949 다."""
    out = subprocess.run(
        [sys.executable, "-m", "kisia.escalation", "--summary", *(str(p) for p in ALL_STALL)],
        capture_output=True,
        cwd=ROOT,
        check=True,
    )
    text = out.stdout.decode("utf-8")
    # **표의 행만 센다.** 범례 줄에도 세 라벨이 다 나오므로 전체를 세면 값이 하나씩
    # 부풀고, 그 부풀음이 "셋이 갈렸다"를 거짓으로 통과시킨다.
    rows = [line for line in text.splitlines() if line.startswith("p1bs")]
    assert len(rows) == 8, rows
    assert sum("가설 없음" in r for r in rows) == 2
    assert sum("접지 안 됨" in r for r in rows) == 3
    assert sum(r.count("접지됨") for r in rows) == 3


@pytest.mark.contract
def test_the_cli_refuses_to_overwrite_two_streams_with_one_name(tmp_path: Path) -> None:
    """`TELEMETRY_SCHEMA.md` §7.1 — 이름이 충돌하면 조용히 덮어쓰지 않고 **죽는다.**"""
    a = _rewrite(tmp_path, _events(STALL3[0]), "a.jsonl")
    b = _rewrite(tmp_path, _events(STALL3[0]), "b.jsonl")
    out = subprocess.run(
        [sys.executable, "-m", "kisia.escalation", "--out", str(tmp_path / "o"), str(a), str(b)],
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    assert out.returncode == 2, out.stdout.decode("utf-8")
    assert "충돌" in out.stdout.decode("utf-8")


@pytest.mark.contract
def test_the_cli_json_is_the_packet_json(tmp_path: Path) -> None:
    """`PATH_SCOPE.md` §3.7 의 `packet.json` 이 이 모양이다."""
    out = subprocess.run(
        [sys.executable, "-m", "kisia.escalation", "--json", str(STALL3[0])],
        capture_output=True,
        cwd=ROOT,
        check=True,
    )
    payload = json.loads(out.stdout.decode("utf-8"))
    assert payload["void"] == []
    (one,) = payload["packets"]
    assert one["grounding"] == GROUNDED
    assert one["attempt_id"] == "p1bs3-ok-01"
    assert len(one["confirmed"]) == 4
