"""호출 단위 비용 회계 — S3.2. **검사기의 `pricing.py` 와 독립이다.**

`kisia/checker/pricing.py` 에 같은 일을 하는 코드가 이미 있다. 그것을 import 하지
않는 이유는 하나다 — **런타임이 검사기의 함수로 `usd` 를 계산하면 S3.2 는 자기
자신을 검사하게 되고 어떤 회계 오류도 잡지 못한다.** 잡히는 것은 스트림에 적힌
토큰 수가 틀린 경우뿐이고, 요율을 잘못 매기는 경우는 양쪽이 함께 틀려 통과한다.
`CLAUDE.md` §6 의 "검사가 언제나 같은 값을 내면 그 검사를 의심하라"가 정확히 이
자리이고, `spec.md` §0.3-3 의 "자기 보고는 증거가 아니다"도 같은 것을 말한다.

그래서 **읽기와 산술을 둘 다 따로 쓴다.** 두 구현이 조용히 갈리는 위험은
`kisia_tests/test_cost.py` 가 둘을 같은 입력에 대고 맞춰 보는 것으로 막는다 —
갈리면 판정 시점이 아니라 테스트 시점에 드러난다.

단가표(`config/pricing.openai.yaml`)는 **읽기 전용 입력**이다(`PATH_SCOPE.md` §3.6).
재과금 경계도 코드가 아니라 그 파일에서 읽는다(`TELEMETRY_SCHEMA.md` §2.1) —
상수를 박으면 모델이 바뀔 때 술어가 조용히 틀린다.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

#: 단가표가 모델 행마다 반드시 갖춰야 하는 요율 넷. 하나라도 없으면 죽는다 —
#: 없는 요율을 0 으로 접으면 `usd` 가 조용히 작아지고 S3.2 가 그것을 통과시킨다.
_BASE_KEYS = (
    "usd_per_million_input",
    "usd_per_million_cached_input",
    "usd_per_million_cache_write",
    "usd_per_million_output",
)
_LONG_KEYS = tuple(k + "_long" for k in _BASE_KEYS)


class CostError(ValueError):
    """단가표를 읽을 수 없거나 요청된 모델의 행이 없다."""


@dataclass(frozen=True)
class Rates:
    """한 모델의 요율. 경계 위·아래를 한 객체에 담는다."""

    model: str
    base: tuple[Decimal, Decimal, Decimal, Decimal]
    threshold: int | None
    long: tuple[Decimal, Decimal, Decimal, Decimal] | None


def _blocks(text: str) -> list[dict[str, str]]:
    """`prices:` 아래의 항목들을 블록으로 자른다.

    검사기 쪽은 줄 단위 상태 기계다. 여기서는 **`- model:` 을 경계로 잘라** 블록마다
    `key: value` 를 모은다 — 같은 파일을 다른 방법으로 읽는 것이 이 모듈의 요점이다.
    """
    out: list[dict[str, str]] = []
    cur: dict[str, str] | None = None
    seen_prices = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        if line.startswith("prices:"):
            seen_prices = True
            continue
        if not line.startswith(" "):
            # 다른 최상위 키(`schema_version` 등)를 만나면 `prices` 블록을 벗어난다.
            seen_prices = False
            continue
        if not seen_prices:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            cur = {}
            out.append(cur)
            stripped = stripped[2:]
        if cur is None or ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        cur[key.strip()] = val.strip().strip('"')
    return out


def load_rates(path: Path) -> dict[str, Rates]:
    text = path.read_text(encoding="utf-8")
    table: dict[str, Rates] = {}
    for block in _blocks(text):
        name = block.get("model")
        if not name:
            raise CostError(f"{path}: model 이름이 없는 단가 행이 있다")
        missing = [k for k in _BASE_KEYS if k not in block]
        if missing:
            raise CostError(f"{path}: {name} 행에 {' '.join(missing)} 가 없다")
        base = tuple(Decimal(block[k]) for k in _BASE_KEYS)
        raw_threshold = block.get("long_context_threshold_tokens")
        threshold = int(raw_threshold) if raw_threshold else None
        long_: tuple[Decimal, ...] | None = None
        if threshold is not None:
            long_missing = [k for k in _LONG_KEYS if k not in block]
            if long_missing:
                raise CostError(
                    f"{path}: {name} 은 재과금 경계를 선언하는데 "
                    + " ".join(long_missing)
                    + " 가 없다"
                )
            long_ = tuple(Decimal(block[k]) for k in _LONG_KEYS)
        table[name] = Rates(
            model=name,
            base=base,  # type: ignore[arg-type]
            threshold=threshold,
            long=long_,  # type: ignore[arg-type]
        )
    if not table:
        raise CostError(f"{path}: 단가 행을 하나도 읽지 못했다")
    return table


def repriced(rates: Rates, input_tokens: int) -> bool:
    """이 호출이 재과금 경계를 넘겼는가 — S3.4 가 이벤트에 표시되기를 요구하는 사실."""
    return rates.threshold is not None and input_tokens > rates.threshold


def usd_for_call(
    rates: Rates,
    *,
    input_tokens: int,
    cached_tokens: int,
    cache_write_tokens: int,
    output_tokens: int,
) -> Decimal:
    """호출 하나의 비용.

    `cache_write` 는 보고된 input 의 **부분집합**이다 — 별도 수량이 아니다. 재빌드-7의
    진단이 `/v1/responses` 에서도 `cached + cache_write + 3 == input` 을 실측했다
    (단가표 머리말이 `/v1/chat/completions` 여섯 호출로 적은 관계와 같다).

    경계를 넘으면 **초과분이 아니라 요청 전체**가 다시 매겨진다.
    """
    if repriced(rates, input_tokens) and rates.long is not None:
        r_in, r_cached, r_write, r_out = rates.long
    else:
        r_in, r_cached, r_write, r_out = rates.base
    plain = input_tokens - cached_tokens - cache_write_tokens
    if plain < 0:
        # 접지 않는다. 음수는 관측이 어긋났다는 뜻이고, 0 으로 깎으면 그 사실이 사라진다.
        raise CostError(
            "cached + cache_write 가 input 보다 크다: "
            f"input={input_tokens} cached={cached_tokens} write={cache_write_tokens}"
        )
    total = (
        Decimal(plain) * r_in
        + Decimal(cached_tokens) * r_cached
        + Decimal(cache_write_tokens) * r_write
        + Decimal(output_tokens) * r_out
    )
    return total / Decimal(1_000_000)
