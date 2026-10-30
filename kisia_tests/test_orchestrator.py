"""orchestrator + NativeHarnessWorker.

**모델도 컨테이너도 부르지 않았다.** `run_attempt` 를 실제로 돌리려면 `OPENAI_API_KEY`
와 docker 와 호스트 접근이 필요하고 이 세션에는 셋 다 없다. 그래서 두 갈래로 잰다.

- **판독기는 진짜 스트림에 대고 잰다.** `EnvelopeWriter` 가 낸 봉투를
  `read_stream_outcome` 이 읽는다 — 손으로 만든 jsonl 이 아니다.
- **기본 결선이 껍데기가 아니라는 것은 시그니처로 잰다.** `inspect.signature(...).bind()`
  가 이 워커의 키워드 인자를 `agent_a.run_attempt` 가 실제로 받는지 호출 없이 확인한다.

**이 파일은 어떤 seam 판정도 인용하지 못한다** (`CLAUDE.md` §6.1-3).
"""

from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from kisia.evidence import EvidenceStore
from kisia.orchestrator import (
    OPERATOR_LADDER,
    Assignment,
    Attempt,
    AttemptResult,
    Orchestrator,
    OrchestratorError,
    PromotionBlockedError,
    Rung,
    Scheduler,
    ScopeRefusedError,
)
from kisia.orchestrator.native import (
    DEFAULT_RUN_ATTEMPT,
    NativeHarnessWorker,
    NativeWorkerError,
    read_stream_outcome,
)
from kisia.runtime import agent_a
from kisia.runtime.telemetry.control import ControlBlock
from kisia.runtime.telemetry.envelope import EnvelopeWriter
from kisia_tests.conformance import _control

#: 사다리 앞 넷만. rung 5·6 은 effort 가 미정이라 배정될 수 없고, 그것을 따로 잰다.
RUNNABLE = tuple(r for r in OPERATOR_LADDER if r.is_runnable)


# ---------------------------------------------------------------------------
# 진짜 봉투 하나 — 판독기가 대고 잴 대상
# ---------------------------------------------------------------------------


def _write_stream(
    path: Path,
    *,
    attempt: str,
    outcome: str,
    verdicts: tuple[bool, ...],
    label: str | None = None,
) -> Path:
    block = _control(attempt=attempt)
    if label is not None:
        block = ControlBlock.build({**block.values, "accounting_label": label})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        w = EnvelopeWriter(fh, run_id="test-orchestrator", attempt_id=attempt, control=block)
        w.start()
        for i, verdict in enumerate(verdicts, start=1):
            w.emit(
                "verification.completed",
                {
                    "verdict": verdict,
                    "verifier_id": "kisia-verifier@host(sha256 compare, separate process)",
                    "candidate_digest": f"sha256:{i:064d}",
                },
            )
        w.emit("attempt.finished", {"outcome": outcome, "reason": "test", "wall_clock_s": 0.1})
    return path


@pytest.mark.contract
def test_read_stream_outcome_reads_a_real_envelope(tmp_path: Path) -> None:
    stream = _write_stream(
        tmp_path / "a.jsonl", attempt="a01", outcome="solved", verdicts=(False, True)
    )
    read = read_stream_outcome(stream)
    assert (read.outcome, read.verdicts, read.accounting_label) == (
        "solved",
        (False, True),
        "clean",
    )
    # 이 스트림에는 §5 예약 이벤트도 모델 호출도 없다. **0 과 "재지 못함"을 가르는 것은
    # `model_calls` 다** — 0 원이 "안 불렀다"인지 "불렀는데 0"인지 접히지 않는다.
    assert (read.stall_signals, read.repeated_hypotheses, read.candidates) == ((), (), ())
    assert (read.usd_total, read.model_calls) == ("0", 0)


@pytest.mark.contract
def test_an_unfinished_stream_is_not_a_failed_one(tmp_path: Path) -> None:
    """"끝나지 않았다"와 "실패했다"는 다른 값이다 (`CLAUDE.md` §6)."""
    path = tmp_path / "b.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        EnvelopeWriter(
            fh, run_id="r", attempt_id="b01", control=_control(attempt="b01")
        ).start()
    assert read_stream_outcome(path).outcome == "unfinished"


# ---------------------------------------------------------------------------
# NativeHarnessWorker
# ---------------------------------------------------------------------------


def _assignment(**over: Any) -> Assignment:
    base: dict[str, Any] = {
        "attempt_id": "a01",
        "challenge_id": "ch",
        "challenge_set": "dev",
        "accounting_label": "clean",
        "solve_k": 1,
        "rung_name": "plan",
        "model_id": "gpt-5.6-terra",
        "effort": "high",
    }
    base.update(over)
    return Assignment(**base)


@pytest.mark.contract
def test_native_worker_reads_the_stream_not_the_self_report(tmp_path: Path) -> None:
    """`effort_mismatch` 인 run 은 flag 를 맞혀도 실패 처리다 (`ADR-0001` 무결성 규칙 1).
    그 사실은 `attempt.finished.outcome` 에만 있고 `notes["solved"]` 에는 없다."""
    seen: dict[str, Any] = {}

    def fake_run_attempt(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        out = Path(kwargs["out_path"])
        _write_stream(
            out, attempt=str(kwargs["attempt"]), outcome="failed", verdicts=(True,)
        )
        return {"solved": True, "stream": str(out)}

    worker = NativeHarnessWorker(
        out_dir=tmp_path, fixed={"image": "kisia/worker-a"}, run_attempt=fake_run_attempt
    )
    result = worker(_assignment())

    assert seen["model_id"] == "gpt-5.6-terra"
    assert seen["effort"] == "high"
    assert seen["image"] == "kisia/worker-a"
    # 두 값을 나란히 싣고 접지 않는다.
    assert result.solver_self_reported_solved is True
    assert result.verdicts == (True,)
    assert result.outcome == "failed"
    assert result.verified is False


@pytest.mark.contract
def test_native_worker_refuses_a_run_that_left_no_stream(tmp_path: Path) -> None:
    worker = NativeHarnessWorker(
        out_dir=tmp_path, fixed={}, run_attempt=lambda **_: {"solved": False}
    )
    with pytest.raises(NativeWorkerError, match="스트림"):
        worker(_assignment())


@pytest.mark.unit
def test_fixed_may_not_shadow_the_assignment(tmp_path: Path) -> None:
    """`fixed` 가 `model_id` 를 덮으면 배정이 조용히 무시된다."""
    with pytest.raises(NativeWorkerError, match="model_id"):
        NativeHarnessWorker(out_dir=tmp_path, fixed={"model_id": "gpt-5.6-luna"})


@pytest.mark.unit
def test_the_default_wiring_is_agent_a_and_it_accepts_our_kwargs() -> None:
    """**껍데기가 아니라는 것을 호출 없이 잰다.**

    `agent_a.run_attempt` 는 컨테이너·모델·키를 요구하므로 이 기계에서 부를 수 없다.
    그러나 시그니처는 부를 수 있다 — 이 워커가 보내는 키워드를 그 함수가 실제로
    받는지가 여기서 갈린다. 인자 이름이 바뀌면 이 시험이 먼저 깨진다.
    """
    assert DEFAULT_RUN_ATTEMPT is agent_a.run_attempt
    inspect.signature(agent_a.run_attempt).bind(
        # 워커가 배정에서 뽑아 넘기는 넷.
        out_path=Path("out.jsonl"),
        attempt="a01",
        model_id="gpt-5.6-terra",
        effort="high",
        # `fixed` 로 넘어가야 하는 나머지 — 배치의 사실이고 배정이 아니다.
        fixture=object(),
        pricing=Path("config/pricing.openai.yaml"),
        image="kisia/worker-a",
        host_id="h",
        api_key="k",
        capability_probe=Path("p.json"),
        capability_probe_id="cap-1",
        usd_budget=Decimal("1.00"),
        # **기본값이 없다** — `control.DEFAULTS` 말미. 호출자가 선언해야 한다.
        # 이 워커가 `Assignment` 에서 뽑아 넘기는 것은 별도 트랙의 일이고, 여기서
        # 재는 것은 그 함수가 이 키워드를 **받는다**는 사실뿐이다.
        accounting_label="clean",
        solve_k=1,
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class StubSolver:
    """배정을 받아 미리 정한 처분을 돌려준다. **스트림을 만들지 않는다** —
    큐·라벨·사다리 논리만 재는 자리다."""

    def __init__(self, outcomes: list[str]) -> None:
        self.outcomes = outcomes
        self.seen: list[Assignment] = []

    def __call__(self, assignment: Assignment) -> AttemptResult:
        self.seen.append(assignment)
        outcome = self.outcomes[len(self.seen) - 1]
        return AttemptResult(
            attempt_id=assignment.attempt_id,
            outcome=outcome,
            verdicts=(outcome == "solved",),
            control_accounting_label=assignment.accounting_label,
            stream_path=None,
            solver_self_reported_solved=(outcome == "solved"),
            # 스트림을 만들지 않는 solver 다 — 스트림에서만 읽는 값들은 비어 있다.
            # stall 이 없으므로 `stall_rung` 을 준 scheduler 에서는 승격이 멈춘다.
            stall_signals=(),
            repeated_hypotheses=(),
            candidates=(),
            usd_total="0",
            model_calls=0,
        )


def _orchestrator(tmp_path: Path, solver: Any, ladder: Any = RUNNABLE) -> Orchestrator:
    return Orchestrator(
        store=EvidenceStore(tmp_path / "evidence"),
        scheduler=Scheduler(ladder),
        solver=solver,
    )


@pytest.mark.unit
def test_a_queued_challenge_has_no_attempts(tmp_path: Path) -> None:
    orc = _orchestrator(tmp_path, StubSolver([]))
    ch = orc.submit("ch-01")
    assert ch.state == "queued"
    assert orc.submit("ch-01") is ch, "같은 id 를 두 번 넣어도 하나다"


@pytest.mark.unit
def test_first_verified_solve_stops_the_ladder(tmp_path: Path) -> None:
    solver = StubSolver(["failed", "solved"])
    orc = _orchestrator(tmp_path, solver)
    ch = orc.submit("ch-01")

    orc.run_until_done(ch, max_attempts=4)

    assert [a.assignment.rung_name for a in ch.attempts] == ["triage", "plan"]
    assert ch.state == "solved"
    assert orc.next_assignment(ch) is None


@pytest.mark.unit
def test_the_label_is_clean_on_the_first_attempt_and_solve_at_k_after(tmp_path: Path) -> None:
    """`ADR-0003` §Consequences — 라벨은 생성 시점에 붙는다."""
    solver = StubSolver(["failed"] * 4)
    orc = _orchestrator(tmp_path, solver)
    ch = orc.submit("ch-01")

    orc.run_until_done(ch, max_attempts=4)

    assert [a.assignment.accounting_label for a in ch.attempts] == [
        "clean",
        "solve@k",
        "solve@k",
        "solve@k",
    ]
    assert ch.state == "unsolved"
    assert orc.next_assignment(ch) is None, "사다리가 끝났다"


@pytest.mark.unit
def test_holdout_gets_exactly_one_attempt(tmp_path: Path) -> None:
    """holdout Attempt 는 clean 라벨만 허용한다 (`ADR-0003` §Consequences).
    `clean_solve@1` 이 정의상 1시도·무재시도이므로 승격 자체가 범위 밖이다."""
    solver = StubSolver(["failed"])
    orc = _orchestrator(tmp_path, solver)
    ch = orc.submit("ch-01", challenge_set="final-holdout")

    orc.run_one(ch)
    assert ch.attempts[0].assignment.accounting_label == "clean"

    with pytest.raises(ScopeRefusedError, match="final-holdout"):
        orc.next_assignment(ch)


@pytest.mark.unit
def test_an_undecided_rung_blocks_instead_of_guessing(tmp_path: Path) -> None:
    """rung 5 의 effort 는 *"Sol high~xhigh"* 다 — 값이 아니라 범위."""
    solver = StubSolver(["failed"] * 4)
    orc = _orchestrator(tmp_path, solver, ladder=OPERATOR_LADDER)
    ch = orc.submit("ch-01")

    orc.run_until_done(ch, max_attempts=4)
    assert len(ch.attempts) == 4

    with pytest.raises(PromotionBlockedError, match="escalate"):
        orc.next_assignment(ch)


@pytest.mark.unit
def test_a_second_attempt_is_refused_while_the_first_is_running(tmp_path: Path) -> None:
    """이 골격은 race 를 하지 않는다 — `ADR-0003` 이 그 기본값을 열어 두었다."""
    orc = _orchestrator(tmp_path, StubSolver([]))
    ch = orc.submit("ch-01")
    ch.attempts.append(
        Attempt(assignment=_assignment(attempt_id="ch-01-01", rung_name="triage"))
    )

    assert ch.state == "running"
    with pytest.raises(OrchestratorError, match="race"):
        orc.next_assignment(ch)


@pytest.mark.unit
def test_max_attempts_has_no_default(tmp_path: Path) -> None:
    """시도 예산은 정해진 적이 없다 — 기본값을 주면 이 함수가 그것을 정하게 된다."""
    sig = inspect.signature(Orchestrator.run_until_done)
    assert sig.parameters["max_attempts"].default is inspect.Parameter.empty


@pytest.mark.contract
def test_the_stream_is_filed_into_the_evidence_store(tmp_path: Path) -> None:
    stream = _write_stream(
        tmp_path / "runs" / "ch-01-01.jsonl",
        attempt="ch-01-01",
        outcome="solved",
        verdicts=(True,),
    )

    def solver(assignment: Assignment) -> AttemptResult:
        read = read_stream_outcome(stream)
        return AttemptResult(
            attempt_id=assignment.attempt_id,
            outcome=read.outcome,
            verdicts=read.verdicts,
            control_accounting_label=read.accounting_label,
            stream_path=stream,
            solver_self_reported_solved=True,
            stall_signals=read.stall_signals,
            repeated_hypotheses=read.repeated_hypotheses,
            candidates=read.candidates,
            usd_total=read.usd_total,
            model_calls=read.model_calls,
        )

    orc = _orchestrator(tmp_path, solver)
    ch = orc.submit("ch-01")
    orc.run_one(ch)

    records = orc.store.records("ch-01-01")
    assert [r.role for r in records] == ["stream"]
    assert (orc.store.root / records[0].path).read_bytes() == stream.read_bytes()


@pytest.mark.unit
def test_a_label_disagreement_is_visible_rather_than_silent(tmp_path: Path) -> None:
    """`agent_a._control` 이 `accounting_label` 을 `"clean"` 으로 박아 두었으므로
    승격된 재시도의 스트림은 여전히 `clean` 을 적는다. 고치는 것은 `kisia/runtime/`
    편집이고 이 트랙의 범위가 아니다 — **보이게 두는 것이 지금 할 수 있는 것이다.**"""

    def solver(assignment: Assignment) -> AttemptResult:
        return AttemptResult(
            attempt_id=assignment.attempt_id,
            outcome="failed",
            verdicts=(),
            control_accounting_label="clean",  # 스트림이 적은 값
            stream_path=None,
            solver_self_reported_solved=False,
            stall_signals=(),
            repeated_hypotheses=(),
            candidates=(),
            usd_total="0",
            model_calls=0,
        )

    orc = _orchestrator(tmp_path, solver)
    ch = orc.submit("ch-01")
    orc.run_one(ch)
    orc.run_one(ch)

    assert ch.attempts[0].label_disagreement is False
    assert ch.attempts[1].assignment.accounting_label == "solve@k"
    assert ch.attempts[1].label_disagreement is True


@pytest.mark.unit
def test_an_unknown_accounting_label_is_refused() -> None:
    with pytest.raises(ValueError, match="accounting_label"):
        _assignment(accounting_label="probably-clean")


@pytest.mark.unit
def test_scheduler_and_orchestrator_agree_on_rung_names(tmp_path: Path) -> None:
    """배정은 rung 객체가 아니라 이름을 나른다 — 그 이름이 사다리에서 되찾아져야 한다."""
    solver = StubSolver(["failed"])
    orc = _orchestrator(tmp_path, solver)
    ch = orc.submit("ch-01")
    orc.run_one(ch)
    found: Rung = orc.scheduler.by_name(ch.attempts[0].assignment.rung_name)
    assert found.model_id == ch.attempts[0].assignment.model_id
