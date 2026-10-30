"""§5 예약 이벤트의 **발행자** — `TELEMETRY_SCHEMA.md` §5.2, `O-38`, `D-70`.

**어떤 술어도 이 이벤트를 읽지 않는다**(§5.1, `R2-15`). 그래서 검사기가 결손을 잡아
주지 않고, 여기서 잡지 않으면 아무 데서도 잡히지 않는다. 이 파일이 재는 것 다섯:

1. **발행되는가** — 아홉 세션 동안 스키마와 허용 목록에만 있고 발행자가 없었다.
2. **접히지 않는가** — 재지 못한 신호가 0 으로 접히면 거짓 관측이다(`D-63`).
3. **관측 장치가 관측 대상에 들어가지 않는가** — 하니스 자신의 도구가 만든 관찰을
   세면 `no_new_observation` 이 영원히 뜨지 않는다(`O-36`/경고 13).
4. **S4.1 이 그대로 참인가** — 새 도구의 `tool.completed` 에 출력 연결이 없으면 지금
   참인 술어가 거짓이 된다. `submit_flag` 가 실제로 그 자리에서 잡혔다.
5. **막히기 전에는 표면에 없는가** (`D-74`) — 항상 노출했더니 유형 B 4 run 중 2 run
   에서 모델이 세션을 둘로 갈라 `S4.2` 가 거짓이 됐고(대조군은 같은 날 4/4 참),
   14 attempt 에서 모델이 이 도구를 **한 번도 부르지 않았다.** 실측이 근거다.
"""

from __future__ import annotations

import io
import json
from decimal import Decimal
from typing import Any

import pytest

from kisia.runtime.loop import AgentLoop, Tool, ToolOutcome, TrackingRecorder
from kisia.runtime.model import ModelCall, Usage
from kisia.runtime.telemetry.envelope import EnvelopeError, EnvelopeWriter
from kisia_tests.conformance import _control

FAMILY = "kisia-fix-a-static"


# ---------------------------------------------------------------------------
# 하네스 — 모델도 네트워크도 없다. 각본이 정한 도구 호출만 되돌려 준다.
# ---------------------------------------------------------------------------


class FakeClient:
    """`ResponsesClient` 의 자리. loop 이 실제로 쓰는 표면만 갖는다."""

    model_id = "gpt-5.6-luna"
    effort = "none"

    def __init__(self, turns: list[list[dict[str, Any]]], usd_per_call: str = "0") -> None:
        self._turns = turns
        self._n = 0
        self.usd_total = Decimal(0)
        self._per_call = Decimal(usd_per_call)
        #: 턴마다 **실제로 받은** 도구 스키마의 이름. 표면에만 있고 스키마에 없으면
        #: 모델은 그 도구를 부를 수 없다.
        self.seen_tools: list[list[str]] = []

    def call(self, items: Any, *, tools: Any = None, effort: Any = None) -> ModelCall:
        self.seen_tools.append([t["name"] for t in (tools or [])])
        turn = self._turns[self._n] if self._n < len(self._turns) else []
        self._n += 1
        self.usd_total += self._per_call
        return ModelCall(
            model_id=self.model_id,
            requested_effort=self.effort,
            model_snapshot=self.model_id,
            observed_effort=self.effort,
            usage=Usage(),
            usd=self._per_call,
            long_context_repriced=False,
            latency_ms=1,
            finish_reason="stop",
            output=turn or [_say("done")],
        )


def _fc(name: str, **args: Any) -> dict[str, Any]:
    return {
        "type": "function_call",
        "name": name,
        "call_id": f"c{abs(hash((name, json.dumps(args, sort_keys=True)))) % 9999}",
        "arguments": json.dumps(args),
    }


def _say(text: str) -> dict[str, Any]:
    return {"type": "message", "content": [{"text": text}]}


def _env(n: int, *, fail: bool = False) -> dict[str, Any]:
    return _fc("run_command", argv=(["fail", str(n)] if fail else ["ls", str(n)]))


#: **stall 을 강제하는 준비 턴 둘.** 서로 다른 argv 로 연달아 실패시키면
#: `repeated_action` 은 뜨지 않고 `tool_error_loop` 만 뜬다 — 셋째 턴 머리에서
#: 관측되고 그 자리에서 가설 도구가 표면에 올라간다.
STALL: list[list[dict[str, Any]]] = [[_env(1, fail=True)], [_env(2, fail=True)]]


def _after_stall(*turns: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """준비 턴 둘 뒤에 이어 붙인다 — 가설 도구는 그 뒤에야 표면에 있다."""
    return [*STALL, *turns]


def _run(
    turns: list[list[dict[str, Any]]],
    *,
    family: str | None = FAMILY,
    env_tool: Tool | None = None,
    usd_per_call: str = "0",
    usd_budget: str = "1.00",
) -> tuple[list[dict[str, Any]], Any, FakeClient]:
    """loop 하나를 돌리고 (이벤트들, report, client) 를 낸다."""
    sink = io.StringIO()
    w = EnvelopeWriter(sink, run_id="r", attempt_id="a", control=_control(attempt="t"))
    rec = TrackingRecorder(w, 4096)
    w.start()

    calls = {"n": 0}

    def default_run(args: dict[str, Any]) -> ToolOutcome:
        calls["n"] += 1
        argv = args.get("argv") or []
        if argv and argv[0] == "fail":
            return ToolOutcome(f"boom {calls['n']}".encode(), 1)
        return ToolOutcome(f"env output {calls['n']}".encode(), 0)

    tool = env_tool or Tool(
        name="run_command",
        description="run one command",
        properties={"argv": {"type": "array", "items": {"type": "string"}}},
        required=["argv"],
        run=default_run,
    )
    client = FakeClient(turns, usd_per_call=usd_per_call)
    loop = AgentLoop(
        writer=w,
        recorder=rec,
        client=client,  # type: ignore[arg-type]
        tools=[tool],
        system_prompt="s",
        task_prompt="t",
        max_turns=len(turns),
        usd_budget=Decimal(usd_budget),
        state_locations=lambda: [],
        attempt_family=family,
    )
    report = loop.run()
    events = [json.loads(x) for x in sink.getvalue().splitlines() if x.strip()]
    return events, report, client


def _of(events: list[dict[str, Any]], type_: str) -> list[dict[str, Any]]:
    return [e for e in events if e.get("type") == type_]


def events_of(sink: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(x) for x in sink.getvalue().splitlines() if x.strip()]


# ---------------------------------------------------------------------------
# 1. 막히기 전에는 표면에 없다 — `D-74`, 실측이 근거인 규칙
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_hypothesis_tools_are_absent_until_a_stall_is_observed() -> None:
    """**호스트 실측이 이 규칙을 요구했다.**

    항상 노출했더니 유형 B 4 run 중 2 run 에서 모델이 세션을 둘로 갈라 `S4.2` 가
    거짓이 됐다. 같은 날 발행자만 끈 대조군은 4/4 참이었고 여유도 5~6 이었다.
    """
    _, report, client = _run(_after_stall(*[[_env(3)]] * 3))
    assert client.seen_tools[0] == ["run_command"]
    assert client.seen_tools[1] == ["run_command"]
    # 셋째 턴 머리에서 tool_error_loop 이 관측된다 → 그 턴부터 올라간다.
    assert "record_hypothesis" in client.seen_tools[2]
    assert report.hypothesis_tools_exposed_at_turn == 3


@pytest.mark.unit
def test_the_request_is_carried_once_and_names_the_signal_not_the_answer() -> None:
    """노출만으로는 부족했다 — 실측에서 모델이 네 턴을 더 쓰고 한 번도 안 불렀다.

    **요청은 무엇을 봤는지만 말한다.** 챌린지에 대해 무엇을 결론하라고 말하면 그
    뒤의 가설은 모델의 것이 아니라 하니스의 것이 된다.
    """
    sent: list[str] = []

    class Recording(FakeClient):
        def call(self, items: Any, *, tools: Any = None, effort: Any = None) -> ModelCall:
            sent.append(json.dumps(items, ensure_ascii=False))
            return super().call(items, tools=tools, effort=effort)

    sink = io.StringIO()
    w = EnvelopeWriter(sink, run_id="r", attempt_id="a", control=_control(attempt="t"))
    rec = TrackingRecorder(w, 4096)
    w.start()
    turns = _after_stall(*[[_env(3)]] * 3)
    loop = AgentLoop(
        writer=w,
        recorder=rec,
        client=Recording(turns),  # type: ignore[arg-type]
        tools=[
            Tool(
                name="run_command",
                description="run one command",
                properties={"argv": {"type": "array", "items": {"type": "string"}}},
                required=["argv"],
                run=lambda a: ToolOutcome(
                    b"boom", 1 if (a.get("argv") or [""])[0] == "fail" else 0
                ),
            )
        ],
        system_prompt="s",
        task_prompt="t",
        max_turns=len(turns),
        usd_budget=Decimal("1.00"),
        state_locations=lambda: [],
        attempt_family=FAMILY,
    )
    loop.run()
    assert "Progress check" not in sent[0]
    assert sent[-1].count("Progress check") == 1, "요청이 매 턴 실리면 안 된다"
    assert "tool_error_loop" in sent[-1]
    # **실재하는 관찰 id 를 함께 싣는다.** 싣지 않으면 모델이 접지할 수가 없고,
    # 실측에서 세 run 이 전부 없는 id 를 지어냈다.
    real = [e["observation_id"] for e in _of(events_of(sink), "observation.recorded")]
    assert real, "준비 턴이 관찰을 만들지 않았다 — 시험 전제가 깨졌다"
    assert real[0] in sent[-1]


@pytest.mark.unit
def test_a_run_that_never_stalls_never_exposes_them() -> None:
    """막히지 않은 run 에서 가설이 0건인 것은 결손이 아니다."""
    _, report, client = _run([[_env(i)] for i in range(1, 7)])
    assert report.stall_signals == []
    assert report.hypothesis_tools_exposed_at_turn is None
    assert all(names == ["run_command"] for names in client.seen_tools)
    assert report.hypotheses_recorded == 0


@pytest.mark.unit
def test_calling_the_tool_before_exposure_emits_nothing() -> None:
    """표면에 없는 것을 불러도 지어내지 않는다 — 모르는 도구로 되돌려 준다."""
    events, report, _ = _run([[_fc("record_hypothesis", statement="too early")]])
    assert _of(events, "hypothesis.recorded") == []
    assert report.hypotheses_recorded == 0


@pytest.mark.unit
def test_the_exposed_tool_reaches_the_model_as_a_schema_not_only_as_a_surface() -> None:
    """스키마를 턴마다 다시 만들지 않으면 표면에만 뜨고 부를 수 없는 도구가 된다."""
    _, _, client = _run(_after_stall([_env(3)]))
    assert set(client.seen_tools[-1]) == {
        "run_command",
        "record_hypothesis",
        "reject_hypothesis",
    }


# ---------------------------------------------------------------------------
# 2. 발행되는가 — `O-38` 이 잰 것은 "0 건"이었다
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_publisher_actually_emits_what_the_schema_reserved() -> None:
    """이 저장소는 아홉 세션 동안 이 셋을 한 번도 발행하지 않았다(`O-38`)."""
    events, _, _ = _run(
        _after_stall(
            [_fc("record_hypothesis", statement="the flag is in /work", confidence=0.7)],
            [_env(4)],
            [
                _fc(
                    "reject_hypothesis",
                    hypothesis_id="hyp-01",
                    reason_code="observation_contradicts",
                )
            ],
        )
    )
    assert len(_of(events, "hypothesis.recorded")) == 1
    assert len(_of(events, "hypothesis.rejected")) == 1
    rec = _of(events, "hypothesis.recorded")[0]
    assert rec["hypothesis_id"] == "hyp-01"
    assert rec["attempt_family"] == FAMILY
    assert rec["confidence"] == pytest.approx(0.7)
    assert _of(events, "hypothesis.rejected")[0]["hypothesis_id"] == "hyp-01"


@pytest.mark.unit
def test_without_an_attempt_family_nothing_reserved_is_emitted() -> None:
    """스키마가 두 이벤트에서 `attempt_family` 를 요구한다 — 없으면 발행하지 않는다."""
    events, report, _ = _run(_after_stall(*[[_env(i)] for i in range(3, 7)]), family=None)
    assert _of(events, "hypothesis.recorded") == []
    assert _of(events, "stall.observed") == []
    # **"발행하지 않았다"를 "신호가 없다"로 접지 않는다.**
    assert report.stall_signals == []
    assert report.stall_signals_not_evaluated == ["*"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("type_", "body"),
    [
        ("hypothesis.recorded", {"hypothesis_id": "h", "statement": "s"}),
        ("hypothesis.rejected", {"hypothesis_id": "h"}),
        ("stall.observed", {"signal": "budget_burn"}),
    ],
)
def test_an_incomplete_reserved_event_dies_at_the_envelope(
    type_: str, body: dict[str, Any]
) -> None:
    """검사기가 이 셋을 읽지 않으므로(§5.1) 발행 지점이 유일한 관문이다."""
    sink = io.StringIO()
    w = EnvelopeWriter(sink, run_id="r", attempt_id="a", control=_control(attempt="t"))
    w.start()
    with pytest.raises(EnvelopeError, match="필수 필드가 없다"):
        w.emit(type_, body)


# ---------------------------------------------------------------------------
# 3. 접지 — 모델의 주장과 하니스가 거른 결과가 스트림에 나란히 남는가
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_unobserved_ids_are_dropped_but_the_claim_survives_in_the_stream() -> None:
    """`supported_by[]` 는 모델의 주장이 아니라 하니스가 거른 결과다.

    거른 사실 자체가 사라지면 안 된다 — 주장 원문은 `tool.requested.args` 에 남고
    거른 결과는 `hypothesis.recorded` 에 남는다. **출처가 다른 두 값이 나란히 있다.**
    """
    probe = _run(STALL)  # 준비 턴이 실제로 낸 관찰 id 를 읽는다 — 형식을 박지 않는다
    real_id = _of(probe[0], "observation.recorded")[0]["observation_id"]
    assert real_id, "준비 턴이 관찰을 만들지 않았다 — 시험 전제가 깨졌다"

    events, _, _ = _run(
        _after_stall(
            [
                _fc(
                    "record_hypothesis",
                    statement="derived",
                    supported_by=[real_id, "obs-999-never-happened"],
                )
            ]
        )
    )
    rec = _of(events, "hypothesis.recorded")[0]
    assert rec["supported_by"] == [real_id]
    assert "obs-999-never-happened" not in rec["supported_by"]

    claim = next(e for e in _of(events, "tool.requested") if e["tool"] == "record_hypothesis")
    assert claim["args"]["supported_by"] == [real_id, "obs-999-never-happened"]


@pytest.mark.unit
def test_a_missing_confidence_is_null_and_not_zero() -> None:
    """`TELEMETRY_SCHEMA.md` §5.2 — `0.0~1.0 또는 null`. 부재는 0 이 아니다."""
    events, _, _ = _run(_after_stall([_fc("record_hypothesis", statement="no number given")]))
    assert _of(events, "hypothesis.recorded")[0]["confidence"] is None


@pytest.mark.unit
def test_rejecting_an_unknown_hypothesis_emits_nothing() -> None:
    """없는 가설을 기각한 것으로 만들지 않는다. 시도는 `tool.requested` 에 남는다."""
    events, report, _ = _run(
        _after_stall([_fc("reject_hypothesis", hypothesis_id="hyp-77", reason_code="guess")])
    )
    assert _of(events, "hypothesis.rejected") == []
    assert report.hypotheses_rejected == 0
    attempt = next(e for e in _of(events, "tool.requested") if e["tool"] == "reject_hypothesis")
    assert attempt["args"]["hypothesis_id"] == "hyp-77"


@pytest.mark.unit
def test_the_same_hypothesis_is_not_rejected_twice() -> None:
    events, report, _ = _run(
        _after_stall(
            [_fc("record_hypothesis", statement="s")],
            [_fc("reject_hypothesis", hypothesis_id="hyp-01", reason_code="a")],
            [_fc("reject_hypothesis", hypothesis_id="hyp-01", reason_code="b")],
        )
    )
    assert len(_of(events, "hypothesis.rejected")) == 1
    assert report.hypotheses_rejected == 1


# ---------------------------------------------------------------------------
# 4. stall — 관측이지 판정이 아니다
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_recording_hypotheses_does_not_count_as_observing_the_environment() -> None:
    """**`O-36`/경고 13 의 회귀 시험.**

    두 도구는 S4.1 때문에 관찰을 만든다. 그 관찰을 환경 관찰로 세면 모델이 가설만
    늘어놓는 동안 `no_new_observation` 이 **영원히 뜨지 않는다** — 관측 장치를 관측
    대상 안에 넣은 것이고, 값이 조용히 틀린다.
    """
    turns = _after_stall(*[[_fc("record_hypothesis", statement=f"guess {i}")] for i in range(1, 7)])
    events, report, _ = _run(turns)
    assert "no_new_observation" in report.stall_signals
    stall = [e for e in _of(events, "stall.observed") if e["signal"] == "no_new_observation"]
    assert len(stall) == 1
    # 준비 턴 둘이 만든 환경 관찰만 CONFIRMED 다. 가설 기록이 만든 것은 아니다.
    assert len(stall[0]["confirmed_facts"]) == 2
    assert len(_of(events, "observation.recorded")) == 8


@pytest.mark.unit
def test_repeated_identical_actions_are_observed() -> None:
    _, report, _ = _run([[_env(1)] for _ in range(6)])
    assert "repeated_action" in report.stall_signals


@pytest.mark.unit
def test_distinct_actions_are_not_reported_as_repetition() -> None:
    _, report, _ = _run([[_env(i)] for i in range(1, 7)])
    assert "repeated_action" not in report.stall_signals


@pytest.mark.unit
def test_consecutive_tool_failures_are_observed() -> None:
    _, report, _ = _run([[_env(i, fail=True)] for i in range(1, 5)])
    assert "tool_error_loop" in report.stall_signals


@pytest.mark.unit
def test_a_broken_streak_is_not_a_streak() -> None:
    """연속이지 누계가 아니다."""
    turns = [[_env(i, fail=(i % 2 == 1))] for i in range(1, 8)]
    _, report, _ = _run(turns)
    assert "tool_error_loop" not in report.stall_signals


@pytest.mark.unit
def test_budget_burn_is_observed_once_past_the_fraction() -> None:
    events, report, _ = _run(
        [[_env(i)] for i in range(1, 5)], usd_per_call="0.30", usd_budget="1.00"
    )
    assert "budget_burn" in report.stall_signals
    assert len(_of(events, "stall.observed")) == len(set(report.stall_signals))


@pytest.mark.unit
def test_a_signal_is_observed_at_most_once_per_attempt() -> None:
    events, report, _ = _run([[_env(1)] for _ in range(10)])
    signals = [e["signal"] for e in _of(events, "stall.observed")]
    assert len(signals) == len(set(signals))
    assert sorted(signals) == sorted(report.stall_signals)


# ---------------------------------------------------------------------------
# 5. 재지 못한 것과 0 을 접지 않는가 — `D-63` 이 난 자리
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_confidence_collapse_is_unevaluated_when_the_model_never_gives_a_number() -> None:
    """**계기가 없으면 '붕괴 없음'이 아니라 '재지 못함'이다.**

    이 구분이 없으면 다음 세션이 빈 목록을 보고 "멈춘 적이 없다"로 읽는다.
    """
    turns = _after_stall(*[[_fc("record_hypothesis", statement=f"g{i}")] for i in range(1, 5)])
    _, report, _ = _run(turns)
    assert "confidence_collapse" not in report.stall_signals
    assert "confidence_collapse" in report.stall_signals_not_evaluated


@pytest.mark.unit
def test_confidence_collapse_is_observed_when_the_number_actually_falls() -> None:
    turns = _after_stall(
        [_fc("record_hypothesis", statement="strong", confidence=0.9)],
        [_env(4)],
        [_fc("record_hypothesis", statement="weak", confidence=0.2)],
        [_env(5)],
    )
    _, report, _ = _run(turns)
    assert "confidence_collapse" in report.stall_signals
    assert "confidence_collapse" not in report.stall_signals_not_evaluated


@pytest.mark.unit
def test_a_short_run_reports_the_window_signals_as_unevaluated() -> None:
    """창이 차기 전에 끝난 run 에서 신호가 없는 것은 '멈추지 않았다'가 아니다."""
    _, report, _ = _run([[_env(1)]])
    assert report.stall_signals == []
    assert "no_new_observation" in report.stall_signals_not_evaluated
    assert "repeated_action" in report.stall_signals_not_evaluated


# ---------------------------------------------------------------------------
# 6. S4.1 이 그대로 참인가 — 발행자가 술어를 깨뜨리지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_new_tools_do_not_break_s4_1() -> None:
    """S4.1 의 조건 그대로: 모든 `tool.completed` 에 exit_code 와 출력 연결이 있다."""
    events, _, _ = _run(
        _after_stall(
            [_fc("record_hypothesis", statement="s", confidence=0.5)],
            [_fc("reject_hypothesis", hypothesis_id="hyp-01", reason_code="r")],
            [_fc("reject_hypothesis", hypothesis_id="nope", reason_code="r")],
            [_env(6)],
        )
    )
    comps = _of(events, "tool.completed")
    assert comps
    for e in comps:
        assert "exit_code" in e
        assert e.get("observation_id") or e.get("artifact_ids"), e


@pytest.mark.unit
def test_the_reserved_events_carry_no_predicate() -> None:
    """§5.1 / `R2-15` — 검사기가 이 이름들을 알면 예약이 예약이 아니게 된다."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "kisia" / "checker" / "predicates.py"
    text = src.read_text(encoding="utf-8")
    for name in ("hypothesis.recorded", "hypothesis.rejected", "stall.observed"):
        assert name not in text, f"검사기가 {name} 를 읽는다 — §5.1 위반"
