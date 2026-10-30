"""검사기가 **눈감지 않는가** — 술어마다 거짓이 되는 스트림을 만들어 확인한다.

재빌드-6, 2026-08-09. 남은 가설 1("적합성 스트림이 검사기의 오류를 가릴 수 있다")이
지목한 다섯 seam — **S1·S5·S7·S8·S9** — 을 덮는다. 나머지 넷(S2·S3·S4·S6)은 실제
컨테이너 위의 음성 대조가 이미 갈랐다.

---

**이것은 음성 대조가 아니다. 두 계기를 섞지 마라.**

| | 음성 대조 (`D-24`) | 이 파일 |
|---|---|---|
| 무엇을 흔드나 | **런타임의 행동** — 격리 플래그 하나, 세션 정리 하나 | **스트림의 사실 하나** |
| 어디서 도나 | 실제 컨테이너, 호스트 | 워크스테이션, docker 없이 |
| 무엇을 증명하나 | 런타임이 그 성질을 실제로 갖는다 | **검사기가 그 성질의 부재를 잡는다** |
| 증명하지 못하는 것 | — | **어떤 seam 도 작동한다는 것.** 모든 바이트를 이 저장소가 심었다 |

`conformance.py` 머리말이 그 한계를 이미 적는다 — 여기 나오는 스트림은 **어떤 seam
판정으로도 인용할 수 없다.** 인용할 수 있는 것은 "검사기가 이 결함을 잡는다" 하나다.

**그래도 이것이 필요한 이유.** `test_checker_golden.py` 는 술어가 **참**으로 행사되는
것만 확인한다. 술어가 언제나 참을 내는 구현이어도 그 테스트는 통과한다 —
`CLAUDE.md` §6("검사가 언제나 같은 값을 내면 그 검사를 의심하라")이 걸리는 자리다.

**흔드는 것은 한 번에 하나다.** 둘을 흔들면 어느 것이 술어를 갈랐는지 알 수 없다.
그리고 이벤트를 지우면 `seq` 를 다시 매긴다 — 그러지 않으면 S9.2 가 먼저 걸려 대상
술어가 평가되지 않는다.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from kisia.checker.fixture import resolve_by_sha256
from kisia.checker.judge import judge_set, judge_stream
from kisia.checker.model import StreamVoidError, load_stream
from kisia.checker.pricing import load_pricing, pricing_sha256
from kisia_tests.conformance import FLAG, RUNTIME_ID, build_set

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "docs" / "spike" / "fixtures"
PRICING = ROOT / "config" / "pricing.openai.yaml"

Events = list[dict[str, Any]]


# ---------------------------------------------------------------------------
# 도구
# ---------------------------------------------------------------------------


def _judge_paths(paths: list[Path]) -> list:
    pricing = load_pricing(PRICING)
    digest = pricing_sha256(PRICING)
    roots = sorted(p for p in FIXTURES.iterdir() if (p / "manifest.json").is_file())
    out = []
    for p in paths:
        stream = load_stream(p)
        fixture = resolve_by_sha256(
            roots, str(stream.control.get("challenge_manifest_sha256", ""))
        )
        out.append(judge_stream(stream, fixture=fixture, pricing=pricing, pricing_digest=digest))
    return out


def _read(path: Path) -> Events:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _write(path: Path, events: Events, *, renumber: bool = True) -> None:
    """되쓴다. **기본은 `seq` 재부여다** — 지운 자리를 그대로 두면 S9.2 가 먼저 걸린다."""
    if renumber:
        for i, e in enumerate(events, start=1):
            e["seq"] = i
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _first(events: Events, kind: str) -> dict[str, Any]:
    for e in events:
        if e.get("type") == kind:
            return e
    raise AssertionError(f"{kind} 이 스트림에 없다 — 적합성 조립기가 바뀌었다")


def _verdicts(paths: list[Path]) -> dict[str, str]:
    """정상 스트림 하나의 술어 -> 판정값. 상시 술어를 보는 자리다."""
    judged = _judge_paths(paths)
    return {r.predicate: r.verdict.ident for r in judged[0].results}


@pytest.fixture
def clean(tmp_path: Path) -> list[Path]:
    return build_set(tmp_path)


def _shake(
    paths: list[Path], mutate: Callable[[Events], None], *, renumber: bool = True
) -> dict[str, str]:
    """**첫 정상 스트림 하나만** 흔들고 그 스트림의 술어 판정을 돌려준다."""
    events = _read(paths[0])
    mutate(events)
    _write(paths[0], events, renumber=renumber)
    return _verdicts(paths)


# ---------------------------------------------------------------------------
# 기준선 — 흔들기 전에는 전부 참이어야 한다
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_baseline_is_true_for_every_predicate_we_shake(clean: list[Path]) -> None:
    """**이것이 없으면 아래 전부가 무의미하다.** 원래 거짓인 술어를 흔들어 거짓을 얻는
    것은 아무것도 재지 않는다.
    """
    v = _verdicts(clean)
    for pid in (
        "S1.1", "S1.2", "S5.1", "S5.2", "S5.3", "S5.5",
        "S7.1", "S8.1", "S8.3", "S8.4", "S9.1", "S9.3",
    ):
        assert v[pid] == "true", f"{pid} 이 기준선에서 참이 아니다: {v[pid]}"


# ---------------------------------------------------------------------------
# S1 — challenge 입력
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_s1_1_catches_binding_after_the_first_model_request(clean: list[Path]) -> None:
    """`input.bound` 가 첫 `model.requested` 뒤로 밀리면 잡는다."""

    def mutate(events: Events) -> None:
        bound = _first(events, "input.bound")
        events.remove(bound)
        first_req = events.index(_first(events, "model.requested"))
        events.insert(first_req + 1, bound)

    assert _shake(clean, mutate)["S1.1"] == "false"


@pytest.mark.contract
def test_s1_1_catches_a_missing_binding(clean: list[Path]) -> None:
    def mutate(events: Events) -> None:
        events.remove(_first(events, "input.bound"))

    assert _shake(clean, mutate)["S1.1"] in ("false", "no_evidence")


@pytest.mark.contract
def test_s1_2_catches_an_input_file_dropped_from_the_binding(clean: list[Path]) -> None:
    """매니페스트가 선언한 입력물이 `files[]` 에서 빠지면 잡는다."""

    def mutate(events: Events) -> None:
        bound = _first(events, "input.bound")
        assert bound["files"], "적합성 조립기가 입력물을 싣는다"
        bound["files"] = []

    assert _shake(clean, mutate)["S1.2"] == "false"


@pytest.mark.contract
def test_s1_2_catches_a_binding_that_lies_about_the_hash(clean: list[Path]) -> None:
    """**존재만 보지 않는다** — `files[]` 의 sha256 을 매니페스트의 봉인값과 대조한다.

    이름만 맞춰 두고 다른 바이트를 넣은 스트림이 통과하면 S1 이 재는 것이 "입력물이
    해시와 함께 바인딩됐다"가 아니라 "그렇게 적혀 있다"가 된다.
    """

    def mutate(events: Events) -> None:
        _first(events, "input.bound")["files"][0]["sha256"] = "sha256:" + "0" * 64

    assert _shake(clean, mutate)["S1.2"] == "false"


@pytest.mark.contract
def test_s1_2_catches_a_binding_that_lies_about_the_byte_count(clean: list[Path]) -> None:
    def mutate(events: Events) -> None:
        _first(events, "input.bound")["files"][0]["bytes"] = 1

    assert _shake(clean, mutate)["S1.2"] == "false"


# ---------------------------------------------------------------------------
# S5 — 실행 결과 관찰
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_s5_1_catches_an_oversize_observation_claiming_it_was_not_truncated(
    clean: list[Path],
) -> None:
    """한도를 넘었는데 `truncated=false` 라고 적으면 잡는다 — 스트림의 거짓말이다."""

    def mutate(events: Events) -> None:
        for e in events:
            if e.get("type") == "observation.recorded" and e.get("truncated") is True:
                e["truncated"] = False
                return
        raise AssertionError("절단된 관찰이 없다")

    assert _shake(clean, mutate)["S5.1"] == "false"


@pytest.mark.contract
def test_s5_2_catches_an_artifact_id_with_no_artifact_produced(clean: list[Path]) -> None:
    """절단 원본을 가리키는 `artifact_id` 에 대응하는 `artifact.produced` 가 없으면 잡는다."""

    def mutate(events: Events) -> None:
        art = _first(events, "artifact.produced")
        events.remove(art)

    assert _shake(clean, mutate)["S5.2"] == "false"


@pytest.mark.contract
def test_s5_3_catches_a_model_reading_an_observation_that_was_never_recorded(
    clean: list[Path],
) -> None:
    """soliloquizing 탐지의 하한선. 기록되지 않은 관찰을 모델이 받았다고 적으면 잡는다."""

    def mutate(events: Events) -> None:
        for e in events:
            if e.get("type") == "model.requested" and e.get("observation_ids"):
                e["observation_ids"] = [*e["observation_ids"], "obs-9999"]
                return
        raise AssertionError("관찰을 참조하는 model.requested 가 없다")

    assert _shake(clean, mutate)["S5.3"] == "false"


@pytest.mark.contract
def test_s5_5_catches_a_missing_harness_forced_truncation(clean: list[Path]) -> None:
    """P-S5-b 는 **하니스가** 낸다. `source_ref` 의 프로브 접두가 사라지면 증거가 없다."""

    def mutate(events: Events) -> None:
        for e in events:
            ref = str(e.get("source_ref", ""))
            if e.get("type") == "observation.recorded" and ref.startswith("probe:P-S5-b"):
                e["source_ref"] = "tool:cat /input/big"
                return
        raise AssertionError("P-S5-b 관찰이 없다")

    assert _shake(clean, mutate)["S5.5"] == "no_evidence"


@pytest.mark.contract
def test_s5_4_catches_nondeterministic_display_across_the_set(clean: list[Path]) -> None:
    """같은 `full_digest` 인데 `shown_digest` 가 다르면 잡는다. **집합 위의 술어다.**"""
    events = _read(clean[0])
    for e in events:
        if e.get("type") == "observation.recorded" and e.get("full_digest"):
            e["shown_digest"] = "sha256:" + "0" * 64
            break
    _write(clean[0], events)
    result = judge_set(_judge_paths(clean))
    assert "S5.4" in result.seams["S5"], result.seams["S5"]


# ---------------------------------------------------------------------------
# S7 — flag 후보 추출
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_s7_1_catches_a_candidate_that_did_not_come_from_the_environment(
    clean: list[Path],
) -> None:
    """**이 seam 의 존재 이유다** — 지어낸 문자열과 환경에서 읽은 문자열을 가른다.

    형식은 맞지만(그래서 `V(c)` 가 정의된다) 어느 관찰에도 없는 조각으로 바꾼다.
    형식까지 깨면 S7.1 이 다른 이유로 거짓이 되어 무엇을 쟀는지 흐려진다.
    """

    def mutate(events: Events) -> None:
        for e in events:
            if e.get("type") == "candidate.produced" and e.get("value") == FLAG:
                e["value"] = "kisia{qqqq_wwwwwww}"
                return
        raise AssertionError("정답 후보가 없다")

    assert _shake(clean, mutate)["S7.1"] == "false"


@pytest.mark.contract
def test_s7_2_does_not_believe_the_declaration(clean: list[Path]) -> None:
    """선언을 지워도 검사기가 **스스로 파생을 찾아** 참을 낸다 (S7.2).

    이것은 이빨이 아니라 **반대 방향의 확인**이다 — 검사기가 선언에 기대고 있다면
    여기서 거짓이 나온다.
    """

    def mutate(events: Events) -> None:
        for e in events:
            if e.get("type") == "candidate.produced" and e.get("value") == FLAG:
                e["derived_from"] = []
                e["method"] = "model_message"
                return
        raise AssertionError("정답 후보가 없다")

    assert _shake(clean, mutate)["S7.1"] == "true"


# ---------------------------------------------------------------------------
# S8 — flag 검증
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_s8_1_catches_a_verifier_inside_the_solver(clean: list[Path]) -> None:
    """`verifier_id` 가 solver 의 id 를 토큰으로 담으면 잡는다 (S2.5의 형태 규칙)."""

    def mutate(events: Events) -> None:
        for e in events:
            if e.get("type") == "verification.completed":
                e["verifier_id"] = f"{RUNTIME_ID}@host(sha256 compare)"
        assert any(e.get("type") == "verification.completed" for e in events)

    assert _shake(clean, mutate)["S8.1"] == "false"


@pytest.mark.contract
def test_s8_3_catches_the_answer_sitting_on_a_swept_surface(clean: list[Path]) -> None:
    """스윕이 정답을 통째로 찾았다고 적으면 잡는다."""

    def mutate(events: Events) -> None:
        sweep = _first(events, "answer.sweep")
        sweep["surfaces"][0]["whole_hits"] = 1

    assert _shake(clean, mutate)["S8.3"] == "false"


@pytest.mark.contract
def test_s8_3_catches_a_sweep_run_by_the_solver_itself(clean: list[Path]) -> None:
    """스윕을 solver 가 돌렸다고 적으면 잡는다 — 자기 보고는 증거가 아니다."""

    def mutate(events: Events) -> None:
        _first(events, "answer.sweep")["checked_by"] = f"{RUNTIME_ID}@host(grep -F)"

    assert _shake(clean, mutate)["S8.3"] == "false"


@pytest.mark.contract
def test_s8_3_catches_a_missing_sweep(clean: list[Path]) -> None:
    """스윕 이벤트가 없으면 만족되지 않는다 (§0.3-2)."""

    def mutate(events: Events) -> None:
        events.remove(_first(events, "answer.sweep"))

    assert _shake(clean, mutate)["S8.3"] == "no_evidence"


@pytest.mark.contract
def test_s8_4_catches_the_answer_hash_leaking_to_the_solver(clean: list[Path]) -> None:
    """solver 가 받는 것은 판정뿐이다 — 정답의 **해시**도 받지 않는다."""
    import hashlib

    ahash = hashlib.sha256(FLAG.encode("utf-8")).hexdigest()

    def mutate(events: Events) -> None:
        for e in events:
            if e.get("type") == "verification.completed" and e.get("verdict") is False:
                e["expected_digest"] = ahash
                return
        raise AssertionError("음성 판정이 없다")

    assert _shake(clean, mutate)["S8.4"] == "false"


@pytest.mark.contract
def test_s8_5_catches_a_verifier_never_shown_a_wrong_candidate(clean: list[Path]) -> None:
    """음성 프로브를 돌리지 않은 verifier 는 계약을 만족하지 않는다."""

    def mutate(events: Events) -> None:
        for e in events:
            if e.get("type") == "verification.completed" and e.get("verdict") is False:
                e["verdict"] = True
                return
        raise AssertionError("음성 판정이 없다")

    assert _shake(clean, mutate)["S8.5"] in ("false", "no_evidence")


# ---------------------------------------------------------------------------
# S9 — telemetry 저장
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_s9_1_catches_a_control_block_missing_one_item(clean: list[Path]) -> None:
    """**재빌드-6이 `provenance` 로 실측한 그 경로다.** 한 항목이 빠지면 attempt 는 폐기다."""

    def mutate(events: Events) -> None:
        del _first(events, "attempt.started")["provenance"]

    assert _shake(clean, mutate)["S9.1"] == "false"


@pytest.mark.contract
def test_s9_1_failure_discards_the_attempt(clean: list[Path]) -> None:
    """S9.1 이 거짓이면 그 attempt 의 **결과가 폐기된다** — 판정값과 별개의 사실이다."""
    events = _read(clean[0])
    del _first(events, "attempt.started")["token_budget"]
    _write(clean[0], events)
    assert _judge_paths(clean)[0].stream.discarded


@pytest.mark.contract
def test_s9_2_voids_the_stream_when_seq_has_a_gap(clean: list[Path]) -> None:
    """빈틈이 있으면 그 attempt 의 **모든 판정이 무효**다 — 검사기의 첫 관문이다.

    **`seq` 를 다시 매기지 않는다.** 재부여하면 빈틈이 사라져 아무것도 재지 않는다.
    """
    events = _read(clean[0])
    events.remove(_first(events, "artifact.produced"))
    _write(clean[0], events, renumber=False)
    with pytest.raises(StreamVoidError):
        load_stream(clean[0])


@pytest.mark.contract
def test_s9_3_catches_a_tool_request_with_no_completion(clean: list[Path]) -> None:
    """`op_id` 로 짝짓는다. 개수만 세는 확인은 동시 세션에서 무력하다."""

    def mutate(events: Events) -> None:
        events.remove(_first(events, "tool.completed"))

    assert _shake(clean, mutate)["S9.3"] == "false"


@pytest.mark.contract
def test_s9_3_catches_a_tool_event_with_no_op_id(clean: list[Path]) -> None:
    def mutate(events: Events) -> None:
        del _first(events, "tool.requested")["op_id"]

    assert _shake(clean, mutate)["S9.3"] == "false"


@pytest.mark.contract
def test_s9_4a_refuses_to_judge_when_the_pinned_pricing_disagrees(clean: list[Path]) -> None:
    """스트림이 지목한 단가표와 실제로 준 것이 다르면 **판정을 내지 않는다.**

    "FAIL 을 낸다"가 아니라 "내지 않는다"이므로 관문은 술어가 아니라 CLI 에 있다.
    """
    from kisia.checker.__main__ import main

    events = _read(clean[0])
    _first(events, "attempt.started")["pricing_sha256"] = "0" * 64
    _write(clean[0], events)
    rc = main(
        [
            "--pricing", str(PRICING),
            "--fixtures-root", str(FIXTURES),
            "--quiet",
            str(clean[0]),
        ]
    )
    assert rc != 0
