"""S3 — 회계와 전송 계층. **네트워크를 쓰지 않는다.**

두 갈래다.

1. **`kisia/runtime/cost.py` 가 `kisia/checker/pricing.py` 와 같은 값을 낸다.**
   둘은 일부러 독립 구현이다(`cost.py` 머리말) — 런타임이 검사기의 함수로 `usd` 를
   계산하면 S3.2 가 자기 자신을 검사하게 되기 때문이다. 독립이면 **조용히 갈릴** 수
   있으므로, 갈리는 것을 판정 시점이 아니라 여기서 잡는다.
2. **`kisia/runtime/model.py` 가 없는 것을 0 으로 접지 않는다.** `cache_write_tokens`
   가 없으면 S3.2 의 재계산이 성립하지 않고(r1 A-1), 그것을 0 으로 접으면 `usd` 가
   조용히 작아진 채 술어를 통과한다.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from kisia.checker.pricing import load_pricing, price_call
from kisia.runtime.cost import CostError, load_rates, repriced, usd_for_call
from kisia.runtime.model import ModelCall, ModelError, Usage, _usage_of, tool_schema

ROOT = Path(__file__).resolve().parents[1]
PRICING = ROOT / "config" / "pricing.openai.yaml"

#: 요율 넷을 전부 밟고, 재과금 경계의 위·아래를 각각 지나는 조합.
CASES = [
    # (input, cached, cache_write, output)
    (0, 0, 0, 0),
    (11, 0, 0, 5),
    (11212, 0, 11209, 5),  # 진단 e-cache1 의 실측
    (11232, 11213, 16, 6),  # 진단 items turn2 의 실측
    (1_000, 400, 300, 250),
    (272_000, 0, 0, 10),  # 경계와 같다 — 넘지 않았다
    (272_001, 0, 0, 10),  # 한 토큰 넘겼다 — 요청 **전체**가 다시 매겨진다
    (400_000, 100_000, 50_000, 20_000),
]


@pytest.fixture(scope="module")
def tables() -> tuple[dict, dict]:
    return load_rates(PRICING), load_pricing(PRICING)


def test_the_two_pricing_readers_see_the_same_models(tables) -> None:
    rates, prices = tables
    assert set(rates) == set(prices)
    assert rates, "단가표에서 모델을 하나도 읽지 못했다"


@pytest.mark.parametrize("case", CASES)
def test_runtime_and_checker_agree_on_usd(tables, case) -> None:
    """독립 구현 둘이 같은 값을 낸다. 갈리면 S3.2 가 실행 중에 갈리기 전에 여기서 깨진다."""
    rates, prices = tables
    input_, cached, write, output = case
    for model in sorted(rates):
        mine = usd_for_call(
            rates[model],
            input_tokens=input_,
            cached_tokens=cached,
            cache_write_tokens=write,
            output_tokens=output,
        )
        theirs = price_call(
            prices[model],
            input_tokens=input_,
            cached_tokens=cached,
            cache_write_tokens=write,
            output_tokens=output,
        )
        assert mine == theirs, f"{model} {case}: 런타임 {mine} != 검사기 {theirs}"


def test_the_repricing_boundary_comes_from_the_table_not_a_constant(tables) -> None:
    """`spec.md` S3.4 의 272,000 은 상수가 아니라 단가표에서 읽는 값이다(§2.1)."""
    rates, _ = tables
    terra = rates["gpt-5.6-terra"]
    assert terra.threshold == 272_000
    assert not repriced(terra, 272_000)
    assert repriced(terra, 272_001)


def test_crossing_the_boundary_reprices_the_whole_request(tables) -> None:
    rates, _ = tables
    terra = rates["gpt-5.6-terra"]
    below = usd_for_call(
        terra, input_tokens=272_000, cached_tokens=0, cache_write_tokens=0, output_tokens=0
    )
    above = usd_for_call(
        terra, input_tokens=272_001, cached_tokens=0, cache_write_tokens=0, output_tokens=0
    )
    # 초과분 한 토큰이 아니라 전체가 2배 요율로 간다.
    assert above > below * Decimal("1.9")


def test_a_negative_uncached_count_is_not_folded_to_zero(tables) -> None:
    """`cached + write > input` 은 관측이 어긋났다는 뜻이다. 0 으로 깎으면 그 사실이 사라진다."""
    rates, _ = tables
    with pytest.raises(CostError):
        usd_for_call(
            rates["gpt-5.6-luna"],
            input_tokens=10,
            cached_tokens=8,
            cache_write_tokens=8,
            output_tokens=0,
        )


def test_a_model_row_without_a_cache_write_rate_dies(tmp_path: Path) -> None:
    """단가표 머리말이 `gpt-5.3-codex` 를 일부러 뺀 이유와 같다 — 없는 요율을 지어내지 않는다."""
    bad = tmp_path / "p.yaml"
    bad.write_text(
        "schema_version: 1\nprices:\n"
        "  - model: fake\n"
        '    usd_per_million_input: "1.0"\n'
        '    usd_per_million_cached_input: "0.1"\n'
        '    usd_per_million_output: "3.0"\n',
        encoding="utf-8",
    )
    with pytest.raises(CostError, match="cache_write"):
        load_rates(bad)


# ---------------------------------------------------------------------------
# 전송 계층 — 응답을 읽는 자리
# ---------------------------------------------------------------------------


def _usage_payload(**over) -> dict:
    body = {
        "usage": {
            "input_tokens": 100,
            "input_tokens_details": {"cached_tokens": 40, "cache_write_tokens": 57},
            "output_tokens": 12,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 112,
        }
    }
    body["usage"].update(over)
    return body


def test_usage_is_read_from_the_responses_shape() -> None:
    """`completion_tokens_details` 가 아니다 — 그것은 chat/completions 의 모양이다."""
    u = _usage_of(_usage_payload())
    assert (u.input_tokens, u.cached_tokens, u.cache_write_tokens) == (100, 40, 57)
    assert (u.output_tokens, u.reasoning_tokens) == (12, 0)


def test_a_missing_cache_write_count_stops_the_call() -> None:
    body = _usage_payload(input_tokens_details={"cached_tokens": 40})
    with pytest.raises(ModelError, match="cache_write_tokens"):
        _usage_of(body)


def test_a_missing_reasoning_token_count_stops_the_call() -> None:
    body = _usage_payload(output_tokens_details={})
    with pytest.raises(ModelError, match="reasoning_tokens"):
        _usage_of(body)


def test_a_response_without_usage_stops_the_call() -> None:
    with pytest.raises(ModelError, match="usage"):
        _usage_of({"model": "gpt-5.6-terra"})


def _call(**over) -> ModelCall:
    base = dict(
        model_id="gpt-5.6-terra",
        requested_effort="none",
        model_snapshot="gpt-5.6-terra",
        observed_effort="none",
        usage=Usage(),
        usd=Decimal(0),
        long_context_repriced=False,
        latency_ms=1,
        finish_reason="completed",
        output=[],
    )
    base.update(over)
    return ModelCall(**base)  # type: ignore[arg-type]


def test_a_silent_upgrade_is_visible_as_degraded() -> None:
    """진단 1 — effort 를 안 실으면 서버가 medium 으로 채운다. 그 어긋남이 보여야 한다."""
    assert _call(observed_effort="medium").degraded
    assert not _call(observed_effort="none").degraded
    # provider 가 값을 안 주면 이 축으로는 아무 주장도 하지 않는다.
    assert not _call(observed_effort=None).degraded


def test_function_calls_and_text_are_read_from_output_items() -> None:
    call = _call(
        output=[
            {"type": "reasoning", "summary": []},
            {"type": "function_call", "name": "run", "call_id": "c1", "arguments": "{}"},
            {"type": "message", "content": [{"type": "output_text", "text": "hi"}]},
        ]
    )
    assert [c["call_id"] for c in call.function_calls()] == ["c1"]
    assert call.text() == "hi"


def test_the_tool_declaration_is_flat() -> None:
    """Responses 의 function tool 은 `function` 아래 중첩되지 않는다 (진단 4)."""
    schema = tool_schema("run", "d", {"argv": {"type": "string"}}, ["argv"])
    assert schema["type"] == "function"
    assert schema["name"] == "run"
    assert "function" not in schema
    assert schema["parameters"]["additionalProperties"] is False
