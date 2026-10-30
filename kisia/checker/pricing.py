"""단가표 읽기와 비용 재계산 — `spec.md` S3.2, S3.4.

`config/pricing.openai.yaml` 은 **읽기 전용 입력**이다(`PATH_SCOPE.md` §3.6,
운영자 결정 2026-08-08). 검사기는 이 파일을 읽고 고치지 않는다.

표준 라이브러리만 쓰기 위해 YAML 전체가 아니라 **이 파일이 실제로 쓰는 형태**만
읽는다: 최상위 스칼라와 `prices:` 아래의 평평한 맵 리스트. 그 밖의 구조를 만나면
조용히 무시하지 않고 죽는다 — 조용히 무시하면 단가가 빠진 채로 `usd` 가 0으로
재계산되고, S3.2가 그것을 통과시킨다.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

_ITEM = re.compile(r"^  - (?P<key>[A-Za-z_][A-Za-z0-9_]*): (?P<val>.*)$")
_FIELD = re.compile(r"^    (?P<key>[A-Za-z_][A-Za-z0-9_]*): (?P<val>.*)$")
_TOP = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*):(?P<val>.*)$")


class PricingError(ValueError):
    """단가표를 읽을 수 없거나 요청된 모델의 행이 없다."""


def pricing_sha256(path: Path) -> str:
    """단가표 **파일 바이트**의 sha256 — `attempt.started.pricing_sha256` 이 지목하는 값.

    파싱한 결과가 아니라 바이트다. `TELEMETRY_SCHEMA.md` §2 가 그렇게 적는다 —
    파싱 결과를 해시하면 이 읽기가 다루지 않는 줄이 값을 바꾸지 않는다.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matches_pin(pin: str, digest: str) -> bool:
    """스트림이 지목한 값과 실제 해시가 같은가 (`spec.md` S9.4a).

    `sha256:` 접두사는 붙어도 되고 안 붙어도 된다 — 저장소의 두 표기가 섞여 있다
    (통제 블록은 접두사 없이, `input.bound.manifest_sha256` 은 붙여서).
    """
    return pin.removeprefix("sha256:").strip().lower() == digest.strip().lower()


@dataclass(frozen=True)
class Price:
    model: str
    input_: Decimal
    cached_input: Decimal
    cache_write: Decimal
    output: Decimal
    long_context_threshold_tokens: int | None
    input_long: Decimal | None
    cached_input_long: Decimal | None
    cache_write_long: Decimal | None
    output_long: Decimal | None


def _scalar(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    return raw


def load_pricing(path: Path) -> dict[str, Price]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_prices = False

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = _TOP.match(line)
        if top:
            in_prices = top.group("key") == "prices"
            current = None
            continue
        if not in_prices:
            raise PricingError(f"{path}:{lineno} prices 블록 밖의 들여쓴 줄: {line!r}")
        item = _ITEM.match(line)
        if item:
            current = {item.group("key"): _scalar(item.group("val"))}
            rows.append(current)
            continue
        field = _FIELD.match(line)
        if field:
            if current is None:
                raise PricingError(f"{path}:{lineno} 리스트 항목 밖의 필드: {line!r}")
            current[field.group("key")] = _scalar(field.group("val"))
            continue
        raise PricingError(f"{path}:{lineno} 이 읽기가 다루지 않는 형태: {line!r}")

    table: dict[str, Price] = {}
    for row in rows:
        try:
            threshold = row.get("long_context_threshold_tokens")
            table[row["model"]] = Price(
                model=row["model"],
                input_=Decimal(row["usd_per_million_input"]),
                cached_input=Decimal(row["usd_per_million_cached_input"]),
                cache_write=Decimal(row["usd_per_million_cache_write"]),
                output=Decimal(row["usd_per_million_output"]),
                long_context_threshold_tokens=int(threshold) if threshold else None,
                input_long=_opt(row, "usd_per_million_input_long"),
                cached_input_long=_opt(row, "usd_per_million_cached_input_long"),
                cache_write_long=_opt(row, "usd_per_million_cache_write_long"),
                output_long=_opt(row, "usd_per_million_output_long"),
            )
        except KeyError as exc:
            raise PricingError(f"{path}: {row.get('model')} 행에 {exc} 가 없다") from exc
    return table


def _opt(row: dict[str, str], key: str) -> Decimal | None:
    raw = row.get(key)
    return Decimal(raw) if raw else None


def price_call(
    price: Price,
    *,
    input_tokens: int,
    cached_tokens: int,
    cache_write_tokens: int,
    output_tokens: int,
) -> Decimal:
    """호출 하나의 비용을 재계산한다.

    `cache_write` 는 보고된 input 의 **부분집합**이지 별도 수량이 아니다 —
    단가표 머리말이 실측으로 그렇게 적었다(`cached + cache_write + 3 == input`).
    따라서 uncached = input - cached - cache_write 에 기본 요율을,
    나머지 둘에 각자의 요율을 매긴다.

    재과금 경계를 넘으면 **초과분이 아니라 요청 전체**가 다시 매겨진다.
    """
    long_ = (
        price.long_context_threshold_tokens is not None
        and input_tokens > price.long_context_threshold_tokens
        and price.input_long is not None
    )
    r_in = price.input_long if long_ else price.input_
    r_cached = price.cached_input_long if long_ else price.cached_input
    r_write = price.cache_write_long if long_ else price.cache_write
    r_out = price.output_long if long_ else price.output
    assert r_in is not None and r_cached is not None and r_write is not None and r_out is not None

    uncached = max(0, input_tokens - cached_tokens - cache_write_tokens)
    million = Decimal(1_000_000)
    return (
        Decimal(uncached) * r_in
        + Decimal(cached_tokens) * r_cached
        + Decimal(cache_write_tokens) * r_write
        + Decimal(output_tokens) * r_out
    ) / million
