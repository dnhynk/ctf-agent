"""검사기를 스파이크의 골든 6개와 적합성 스트림에 대고 잠근다.

두 종류가 있고 성격이 다르다.

- **골든 6개**는 r1 시대의 산출물이다. r5 아래에서 통제 블록이 12/36 이므로 6개
  전부 S9 FAIL 이고 attempt 폐기 대상이다. 여기 잠그는 값은 "계약이 만족됐다"가
  아니라 **"델타가 이 모양이다"** 이고, `docs/rebuild/judgments/` 의 델타표와 같은
  값이어야 한다. 값이 움직이면 검사기가 조용히 달라졌다는 뜻이다.
- **적합성 스트림**은 조립기가 낸 r3 적합 스트림이다. 유형 A의 하중 8칸이 전부
  PASS 여야 한다. **어떤 seam 이 작동한다는 증거가 아니다** —
  `kisia_tests/conformance.py` 머리말이 그 한계를 적는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kisia.checker.fixture import resolve_by_sha256
from kisia.checker.judge import judge_set, judge_stream
from kisia.checker.model import load_stream
from kisia.checker.pricing import load_pricing, pricing_sha256
from kisia_tests.conformance import build_set

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "docs" / "spike" / "golden"
FIXTURES = ROOT / "docs" / "spike" / "fixtures"
PRICING = ROOT / "config" / "pricing.openai.yaml"

#: r3 아래의 유형별 집합 판정. 하한 4를 낮춘 **진단** 값이다 (계약 판정은 '증거 부족').
GOLDEN_DELTA = {
    "a": {
        "S1": "PASS",
        # R4-1 이후. 골든의 `/etc/probe` 거부에 host_check_file_exists 가 없고,
        # `/input` 쓰기는 더 이상 S2.2 의 후보가 아니다.
        "S2": "FAIL(S2.2)[no-evidence]",
        "S3": "FAIL(S3.5)[no-evidence]", "S4": "FAIL(S4.1)",
        "S5": "FAIL(S5.5)[no-evidence]", "S6": "N/A", "S7": "PASS",
        "S8": "FAIL(S8.1,S8.3)", "S9": "FAIL(S9.1,S9.3)",
    },
    "b": {
        "S1": "N/A", "S2": "PASS", "S3": "N/A", "S4": "FAIL(S4.1,S4.4)",
        "S5": "FAIL(S5.5)[no-evidence]", "S6": "PASS", "S7": "PASS",
        "S8": "FAIL(S8.1,S8.3)", "S9": "FAIL(S9.1,S9.3)",
    },
    "c": {
        "S1": "N/A", "S2": "FAIL(S2.4)[no-evidence]", "S3": "N/A", "S4": "FAIL(S4.1)",
        "S5": "N/A", "S6": "PASS", "S7": "PASS",
        "S8": "FAIL(S8.1,S8.3)", "S9": "FAIL(S9.1,S9.3)",
    },
}
NEGATIVES = {"a": "negative-a4", "b": "negative-b9", "c": "negative-c4"}


def _fixture_roots() -> list[Path]:
    return sorted(p for p in FIXTURES.iterdir() if (p / "manifest.json").is_file())


def _judge(paths: list[Path]) -> list:
    pricing = load_pricing(PRICING)
    digest = pricing_sha256(PRICING)
    roots = _fixture_roots()
    out = []
    for p in paths:
        stream = load_stream(p)
        fixture = resolve_by_sha256(roots, str(stream.control.get("challenge_manifest_sha256", "")))
        out.append(
            judge_stream(stream, fixture=fixture, pricing=pricing, pricing_digest=digest)
        )
    return out


@pytest.mark.contract
@pytest.mark.parametrize("kind", ["a", "b", "c"])
def test_golden_delta_is_locked(kind: str) -> None:
    judged = _judge([GOLDEN / kind / "stream.jsonl", GOLDEN / kind / f"{NEGATIVES[kind]}.jsonl"])
    result = judge_set(judged, minimum_normal=1)
    assert result.seams == GOLDEN_DELTA[kind]


@pytest.mark.contract
@pytest.mark.parametrize("kind", ["a", "b", "c"])
def test_golden_streams_are_discarded_under_r3(kind: str) -> None:
    """통제 블록이 12/36 이므로 r5 아래에서 그 attempt 의 결과는 폐기된다 (§2)."""
    for j in _judge([GOLDEN / kind / "stream.jsonl", GOLDEN / kind / f"{NEGATIVES[kind]}.jsonl"]):
        assert j.stream.discarded


@pytest.mark.contract
@pytest.mark.parametrize("kind", ["a", "b", "c"])
def test_golden_set_is_insufficient_under_the_contract(kind: str) -> None:
    """정상 스트림 하한 4 (R3-7). 골든은 유형마다 정상 1~2개뿐이다."""
    judged = _judge([GOLDEN / kind / "stream.jsonl", GOLDEN / kind / f"{NEGATIVES[kind]}.jsonl"])
    assert judge_set(judged).insufficient


@pytest.mark.contract
def test_judgment_digest_is_stable(tmp_path: Path) -> None:
    """P-S9-a 가 요구하는 것은 검사기가 스트림에 대한 순수 함수라는 성질이다."""
    first = _judge([GOLDEN / "a" / "stream.jsonl"])[0].digest()
    copied = tmp_path / "moved.jsonl"
    copied.write_bytes((GOLDEN / "a" / "stream.jsonl").read_bytes())
    assert _judge([copied])[0].digest() == first


@pytest.mark.contract
def test_conformance_set_passes_every_loaded_cell(tmp_path: Path) -> None:
    result = judge_set(_judge(build_set(tmp_path)))
    assert not result.insufficient
    assert result.normal_count == 4
    assert result.seams == {
        "S1": "PASS", "S2": "PASS", "S3": "PASS", "S4": "PASS", "S5": "PASS",
        "S6": "N/A", "S7": "PASS", "S8": "PASS", "S9": "PASS",
    }


@pytest.mark.contract
def test_conformance_exercises_the_predicates_r1_goldens_cannot(tmp_path: Path) -> None:
    """r2·r3가 신설한 술어가 **참**으로 행사됐는지 확인한다.

    골든에서 이것들이 증거 없음인 것은 골든이 r1 산출물이기 때문이지 술어가 평가
    불가능해서가 아니다. 그 구분이 이 테스트의 존재 이유다.
    """
    judged = _judge(build_set(tmp_path))[0]
    by_id = {r.predicate: r for r in judged.results}
    for pid in ("S5.5", "S9.1", "S9.3", "S8.2", "S8.3", "S3.2", "S3.5", "S4.1"):
        assert by_id[pid].verdict.ident == "true", f"{pid} = {by_id[pid].verdict.label}"
