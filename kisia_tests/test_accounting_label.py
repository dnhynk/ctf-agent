"""지표 회계 라벨 — `ADR-0003` §Decision-2 (G-1) · §Consequences.

ADR 이 *"모든 Attempt 는 생성 시점에 clean / solve@k / contest 라벨이 붙어야 하고,
holdout Attempt 는 clean 라벨만 허용한다"* 고 적고, *"이것 없이는 '우리 시스템이
낫다'가 오염된 숫자 위에 선다"* 고 이유를 적는다. **런타임에 그 필드가 없었다.**

**여기서 재는 것은 강제이지 판정이 아니다.** 라벨은 통제 블록 필드이지 계약 술어가
아니므로(`TELEMETRY_SCHEMA.md` §2), 검사기는 S9.1 로 **존재만** 본다. 값의 정합 —
G-1, 단일 모델, holdout — 은 **조립기가 발행 시점에** 강제하고 그것이 ADR 이 "생성
시점에" 라고 적은 것의 기계적 형태다. 스트림이 난 뒤에 라벨을 고치면 이미 난 숫자를
되돌릴 수 없다.
"""

from __future__ import annotations

import io
import json

import pytest

from kisia.runtime.telemetry.control import (
    ACCOUNTING_LABELS,
    DEFAULTS,
    REQUIRED_FIELDS,
    ControlBlock,
    ControlBlockError,
)
from kisia.runtime.telemetry.envelope import EnvelopeWriter
from kisia_tests.conformance import _control

LABEL_FIELDS = ("accounting_label", "solve_k", "run_participants")
NATIVE = {"id": "kisia-runtime/test", "kind": "native_core"}
CLAUDE_CODE = {"id": "ClaudeCodeWorker", "kind": "second_core"}
OUTSIDE = {"id": "manual-escalation/chatgpt", "kind": "external_model"}


def base() -> dict:
    return dict(_control(attempt="t").values)


# -- 기본값 정책 --------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("field", LABEL_FIELDS)
def test_the_label_has_no_default_so_an_undeclared_run_never_opens(field: str) -> None:
    """**기본값을 주면 오염된 run 이 조용히 그 값으로 세어진다.**

    `build()` 가 `dict(DEFAULTS)` 를 먼저 병합하므로 기본값은 곧 자동 부여다.
    `clean` 을 기본값으로 주면 `ADR-0003` 이 막으려는 해악 그 자체이고, `contest` 를
    줘도 선언하지 않은 run 이 목표 지표에 섞인다. **미선언과 어떤 값도 접지 않는다**
    (`TELEMETRY_SCHEMA.md` §7.1).
    """
    assert field in REQUIRED_FIELDS
    assert field not in DEFAULTS
    values = base()
    del values[field]
    with pytest.raises(ControlBlockError, match=field):
        ControlBlock.build(values)


# -- G-1 --------------------------------------------------------------------


@pytest.mark.unit
def test_g1_a_second_core_in_the_run_cannot_be_labelled_clean() -> None:
    """`ADR-0003` §Decision-2 — ClaudeCode 가 참여한 run 은 `clean_solve@1` 로 세지
    않는다. `clean_solve@1` 은 정의상 단일 모델이다."""
    with pytest.raises(ControlBlockError, match="second_core"):
        ControlBlock.build(
            {**base(), "accounting_label": "clean", "solve_k": 2,
             "run_participants": [NATIVE, CLAUDE_CODE]}
        )


@pytest.mark.unit
def test_g1_is_judged_by_declared_kind_not_by_worker_name() -> None:
    """**이름이 아니라 선언된 종류로 판정한다.**

    열린 이름 집합에 문자열 대조를 걸면 `ClaudeCodeWorker` 를 다르게 부른 run 이
    조용히 clean 으로 빠져나간다 — 그것이 이 트랙이 막으려는 해악과 같은 모양이다.
    """
    renamed = {"id": "cc-worker-2", "kind": "second_core"}
    with pytest.raises(ControlBlockError, match="second_core"):
        ControlBlock.build(
            {**base(), "accounting_label": "clean", "solve_k": 1,
             "run_participants": [renamed]}
        )


@pytest.mark.unit
def test_a_race_of_two_native_cores_is_not_clean_either() -> None:
    """canon 이 요구하는 것은 "one model" 이다 — 둘째가 무엇이든 clean 이 아니다."""
    with pytest.raises(ControlBlockError, match="참여자가 2"):
        ControlBlock.build(
            {**base(), "accounting_label": "clean", "solve_k": 2,
             "run_participants": [NATIVE, {"id": "other-core", "kind": "native_core"}]}
        )


@pytest.mark.unit
def test_clean_requires_k_of_one() -> None:
    """`clean_solve@1` 은 1시도·무재시도다 (`EVAL_CONTRACT.md` Reporting unit)."""
    with pytest.raises(ControlBlockError, match="solve_k=3"):
        ControlBlock.build(
            {**base(), "accounting_label": "clean", "solve_k": 3, "run_participants": [NATIVE]}
        )


@pytest.mark.unit
def test_escalation_forces_the_contest_label() -> None:
    """escalation 을 쓴 run 은 `contest_solve` 로 센다 — `solve@k` 로도 세지 않는다."""
    with pytest.raises(ControlBlockError, match="external_model"):
        ControlBlock.build(
            {**base(), "accounting_label": "solve@k", "solve_k": 2,
             "run_participants": [NATIVE, OUTSIDE]}
        )
    ok = ControlBlock.build(
        {**base(), "accounting_label": "contest", "solve_k": 2,
         "run_participants": [NATIVE, OUTSIDE]}
    )
    assert ok.values["accounting_label"] == "contest"


# -- holdout ------------------------------------------------------------------


@pytest.mark.unit
def test_holdout_allows_only_the_clean_label() -> None:
    """holdout 은 한 번 열면 세트째 내려간다(`HOLDOUT.md` §1.1). 그 한 번을 race 로
    쓰면 계기의 유일한 측정이 `solve@k` 가 되어 버려진다(`ADR-0003` §Decision-2)."""
    with pytest.raises(ControlBlockError, match="final-holdout"):
        ControlBlock.build(
            {**base(), "challenge_set": "final-holdout", "accounting_label": "solve@k",
             "solve_k": 2, "run_participants": [NATIVE, CLAUDE_CODE]}
        )
    ok = ControlBlock.build(
        {**base(), "challenge_set": "final-holdout", "accounting_label": "clean",
         "solve_k": 1, "run_participants": [NATIVE]}
    )
    assert ok.values["challenge_set"] == "final-holdout"


@pytest.mark.unit
def test_the_label_is_a_mode_and_the_set_decides_inclusion() -> None:
    """**`clean` 라벨과 `clean_solve@1` 은 같은 것이 아니다.**

    ADR 은 "holdout Attempt 는 clean 라벨만" 이라고 한 방향으로만 적는다. 반대 방향을
    읽으면 dev 위의 단일 코어 run 이 라벨을 달 수 없게 되고, 그러면 `run_participants`
    가 어디에도 실리지 않아 G-1 이 행사되지 않는다. 계기의 숫자는 **라벨과 세트가
    함께** 참일 때다(`ADR-0003` §Decision-2, `HOLDOUT.md` §1.0.a).
    """
    for challenge_set in ("dev", "regression-private", "calibration"):
        block = ControlBlock.build(
            {**base(), "challenge_set": challenge_set, "accounting_label": "clean",
             "solve_k": 1, "run_participants": [NATIVE]}
        )
        assert block.values["accounting_label"] == "clean"


# -- 값의 형식 ----------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "patch",
    [
        {"accounting_label": "clean_solve@1"},
        {"accounting_label": "solve@2"},
        {"solve_k": 0},
        {"solve_k": True},
        {"run_participants": []},
        {"run_participants": [{"id": "x"}]},
        {"run_participants": [{"id": "", "kind": "native_core"}]},
        {"run_participants": [{"id": "x", "kind": "claude_code"}]},
        {"run_participants": ["native_core"]},
    ],
)
def test_malformed_accounting_values_die(patch: dict) -> None:
    """`solve@2` 가 라벨이 아닌 이유: k 를 문자열에 넣으면 라벨이 열린 집합이 되고
    같은 회계 갈래를 등호로 묶을 수 없다. k 는 `solve_k` 에 앉는다."""
    with pytest.raises(ControlBlockError):
        ControlBlock.build({**base(), **patch})


@pytest.mark.unit
def test_the_label_values_are_the_three_the_adr_names() -> None:
    assert {"clean", "solve@k", "contest"} == ACCOUNTING_LABELS


# -- 실제로 스트림에 실리는가 --------------------------------------------------


@pytest.mark.unit
def test_attempt_started_actually_carries_the_three_fields() -> None:
    """**이 트랙의 산출물.** 필드가 목록에만 있고 봉투에 실리지 않으면 회계는 여전히
    없다. `attempt.started` 를 실제로 읽어 확인한다."""
    sink = io.StringIO()
    EnvelopeWriter(sink, run_id="r", attempt_id="a", control=_control(attempt="t")).start()
    started = json.loads(sink.getvalue().splitlines()[0])
    assert started["type"] == "attempt.started"
    assert started["accounting_label"] == "clean"
    assert started["solve_k"] == 1
    assert [p["kind"] for p in started["run_participants"]] == ["native_core"]
