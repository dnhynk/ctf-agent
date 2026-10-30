"""봉투 조립기 — `TELEMETRY_SCHEMA.md` §7의 최소 의무와 §7.1의 실측된 경고.

§7.1이 권고가 아니라 **요구**라고 적은 성질(이름 충돌 시 죽는다)을 여기서 잰다.
"""

from __future__ import annotations

import io
import json

import pytest

from kisia.runtime.telemetry.control import ControlBlock, ControlBlockError, probe_set_id
from kisia.runtime.telemetry.envelope import EnvelopeError, EnvelopeWriter
from kisia_tests.conformance import _control


def writer() -> tuple[EnvelopeWriter, io.StringIO]:
    sink = io.StringIO()
    w = EnvelopeWriter(sink, run_id="r", attempt_id="a", control=_control(attempt="t"))
    return w, sink


def events(sink: io.StringIO) -> list[dict]:
    return [json.loads(x) for x in sink.getvalue().splitlines() if x.strip()]


# -- §7-1 : seq 와 식별자 ----------------------------------------------------


@pytest.mark.unit
def test_seq_is_allocated_at_a_single_point_from_one() -> None:
    w, sink = writer()
    w.start()
    w.emit("state.snapshot", {"turn": 1, "live_session_ids": [], "state_locations": [],
                              "jar_digest": "d", "artifact_count": 0})
    assert [e["seq"] for e in events(sink)] == [1, 2]
    assert {e["run_id"] for e in events(sink)} == {"r"}


# -- §7.1 : 가장 먼저 틀리는 자리 --------------------------------------------


@pytest.mark.unit
def test_field_name_collision_dies_rather_than_overwriting() -> None:
    """스파이크에서 `session.opened` 가 통째로 사라진 원인이 이 겹침이었다."""
    w, _ = writer()
    w.start()
    with pytest.raises(EnvelopeError, match="겹친다"):
        w.emit("scope.refused", {"action": "x", "reason_code": "y", "checked_by": "z",
                                 "attempted_from": "container", "seq": 999})


@pytest.mark.unit
def test_emit_takes_a_dict_not_keyword_arguments() -> None:
    """구조로 막는다 — 키워드 인자가 없으면 내부 인자 이름이 계약 필드와 겹칠 수 없다."""
    import inspect

    kinds = {p.kind for p in inspect.signature(EnvelopeWriter.emit).parameters.values()}
    assert inspect.Parameter.VAR_KEYWORD not in kinds


@pytest.mark.unit
def test_unknown_event_type_dies() -> None:
    w, _ = writer()
    w.start()
    with pytest.raises(EnvelopeError, match="계약에 없는 이벤트 타입"):
        w.emit("session.evicted", {})


@pytest.mark.unit
def test_missing_required_field_dies() -> None:
    w, _ = writer()
    w.start()
    with pytest.raises(EnvelopeError, match="필수 필드가 없다"):
        w.emit("session.opened", {"session_id": "s1", "kind": "pty"})


# -- §2 : 통제 블록 -----------------------------------------------------------


@pytest.mark.unit
def test_incomplete_control_block_refuses_to_open_the_stream() -> None:
    with pytest.raises(ControlBlockError, match="통제 블록에"):
        ControlBlock.build({"runtime_id": "x"})


@pytest.mark.unit
def test_null_concurrency_limit_is_explicit_but_missing_is_not() -> None:
    """`null` 은 '상한 없음'이고 §4.2의 '명시적'을 만족한다. 미선언과는 다르다."""
    base = _control(attempt="t").values
    ok = ControlBlock.build({**base, "session_concurrency_limit": None})
    assert ok.values["session_concurrency_limit"] is None
    with pytest.raises(ControlBlockError):
        ControlBlock.build({**base, "bytes_shown_limit": None})


@pytest.mark.unit
def test_probe_set_id_is_order_independent_and_membership_sensitive() -> None:
    assert probe_set_id(["A-1", "A-2"]) == probe_set_id(["A-2", "A-1", "A-1"])
    assert probe_set_id(["A-1", "A-2"]) != probe_set_id(["A-1", "A-2", "A-6"])
    assert len(probe_set_id(["A-1"])) == 12


# -- 순서와 짝짓기 (S9.3) -----------------------------------------------------


@pytest.mark.unit
def test_model_calls_are_serial_within_an_attempt() -> None:
    """봉투가 `model.*` 에 op_id 를 주지 않으므로 직렬이 아니면 짝짓기가 성립하지 않는다."""
    w, _ = writer()
    w.start()
    body = {"model_id": "m", "effort": "none", "input_tokens": 0, "cached_tokens": 0,
            "cache_write_tokens": 0, "reasoning_tokens": 0, "prompt_digest": "d",
            "observation_ids": []}
    w.emit("model.requested", body)
    with pytest.raises(EnvelopeError, match="직렬"):
        w.emit("model.requested", body)


@pytest.mark.unit
def test_tool_op_ids_must_pair() -> None:
    w, _ = writer()
    w.start()
    with pytest.raises(EnvelopeError, match="짝이 되는 요청이 없다"):
        w.emit("tool.completed", {"op_id": "nope", "status": "ok", "exit_code": 0,
                                  "duration_ms": 1, "artifact_ids": []})


@pytest.mark.unit
def test_attempt_finished_refuses_unclosed_operations() -> None:
    w, _ = writer()
    w.start()
    w.emit("tool.requested", {"op_id": "op-1", "tool": "exec", "args": [], "args_digest": "d"})
    with pytest.raises(EnvelopeError, match="닫히지 않은 연산"):
        w.emit("attempt.finished", {"outcome": "solved", "reason": "r", "wall_clock_s": 1.0})


# -- redaction sentinel (§3.2.1) ---------------------------------------------


@pytest.mark.unit
def test_redaction_comes_from_declaration_only() -> None:
    """무엇이 비밀인지 조립기가 추측하지 않는다 — 추측하면 놓치거나 과도하게 가린다."""
    base = _control(attempt="t").values
    control = ControlBlock.build({**base, "secret_refs": ["api_key"]})
    sink = io.StringIO()
    w = EnvelopeWriter(sink, run_id="r", attempt_id="a", control=control)
    w.start()
    w.emit("search.performed", {"query": "q", "results_digest": "d", "api_key": "sk-real"})
    last = events(sink)[-1]
    assert last["api_key"] == "<redacted:api_key>"
    assert "sk-real" not in sink.getvalue()
