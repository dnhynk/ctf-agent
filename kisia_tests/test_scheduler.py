"""scheduler — 승격 축의 시험.

**여기서 재는 것은 축이지 정책이 아니다.** 운영자의 승격 조건(*"새 증거 없이 3회 반복"*
등)은 이 저장소가 잰 적이 없고 코드에 술어로 들어가 있지 않다 — 그 사실 자체를
`test_operator_ladder_carries_triggers_as_text` 가 잠근다.
"""

from __future__ import annotations

import pytest

from kisia.orchestrator.scheduler import (
    OPERATOR_LADDER,
    Rung,
    Scheduler,
    SchedulerError,
)


@pytest.mark.unit
def test_operator_ladder_is_the_six_the_operator_wrote() -> None:
    """`NEXT_SESSION.md` §3.5 의 여섯 줄 그대로. 전사이지 결정이 아니다."""
    assert [(r.model_id, r.reasoning_effort) for r in OPERATOR_LADDER] == [
        ("gpt-5.6-luna", "medium"),
        ("gpt-5.6-terra", "high"),
        ("gpt-5.6-terra", "medium"),
        ("gpt-5.6-terra", "xhigh"),
        ("gpt-5.6-sol", None),
        ("gpt-5.6-sol", None),
    ]


@pytest.mark.unit
def test_the_two_undecided_rungs_are_not_runnable() -> None:
    """운영자가 rung 5·6 을 **범위와 선택지**로 적었다. 미정을 기본값으로 접지 않는다
    (`CLAUDE.md` §6)."""
    runnable = [r.name for r in OPERATOR_LADDER if r.is_runnable]
    blocked = [r.name for r in OPERATOR_LADDER if not r.is_runnable]
    assert runnable == ["triage", "plan", "execute", "deepen"]
    assert blocked == ["escalate", "final"]


@pytest.mark.unit
def test_operator_ladder_carries_triggers_as_text() -> None:
    """승격 조건은 **문자열**이지 술어가 아니다. 임계값을 코드에 넣으면 재지 않은 값이
    기본값이 된다 — `ADR-0003` 이 `calibration@1` 뒤로 묶은 그 자리다."""
    assert all(isinstance(r.trigger, str) and r.trigger for r in OPERATOR_LADDER)
    assert "3회" in OPERATOR_LADDER[3].trigger


@pytest.mark.unit
def test_ladder_must_not_be_empty_or_have_duplicate_names() -> None:
    with pytest.raises(SchedulerError, match="비어"):
        Scheduler(())
    twin = Rung("a", "m", "low", "t")
    with pytest.raises(SchedulerError, match="겹친다"):
        Scheduler((twin, twin))


@pytest.mark.unit
def test_verified_stops_the_ladder() -> None:
    """`CONTEST_ARCHITECTURE.md` §4 — 첫 verified solve 가 승자다."""
    s = Scheduler(OPERATOR_LADDER)
    assert s.next_after(s.first, verified=True) is None


@pytest.mark.unit
def test_unverified_walks_the_ladder_then_ends() -> None:
    s = Scheduler(OPERATOR_LADDER)
    walked: list[str] = [s.first.name]
    cur: Rung | None = s.first
    while cur is not None:
        cur = s.next_after(cur, verified=False)
        if cur is not None:
            walked.append(cur.name)
    assert walked == [r.name for r in OPERATOR_LADDER]


@pytest.mark.unit
def test_a_rung_from_another_ladder_is_refused() -> None:
    s = Scheduler(OPERATOR_LADDER)
    with pytest.raises(SchedulerError, match="없는 rung"):
        s.next_after(Rung("elsewhere", "m", "low", "t"), verified=False)


@pytest.mark.unit
def test_by_name_round_trips() -> None:
    s = Scheduler(OPERATOR_LADDER)
    assert s.by_name("deepen").reasoning_effort == "xhigh"
