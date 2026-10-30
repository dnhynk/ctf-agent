"""근거 있는 파생 — `spec.md` S7 정의부, R3-1 · R3-2 · R3-3.

이 술어가 계약의 최대 변경이므로(§3) 규칙 하나하나를 따로 잰다.
"""

from __future__ import annotations

import pytest

from kisia.checker.grounding import (
    FlagFormatError,
    Source,
    find_decomposition,
    split_flag_format,
    variable_part,
)

FMT = "kisia{...}"


def src(ident: str, text: str) -> Source:
    return Source(ident=ident, text=text)


# -- R3-1 : V(c) 추출 -------------------------------------------------------


@pytest.mark.unit
def test_split_flag_format() -> None:
    assert split_flag_format(FMT) == ("kisia{", "}")


@pytest.mark.unit
def test_flag_format_must_have_exactly_one_hole() -> None:
    for bad in ("kisia{}", "kisia{...}{...}"):
        with pytest.raises(FlagFormatError):
            split_flag_format(bad)


@pytest.mark.unit
def test_variable_part() -> None:
    assert variable_part("kisia{5o9v_1472742}", FMT) == "5o9v_1472742"


@pytest.mark.unit
def test_variable_part_undefined_is_none_not_a_guess() -> None:
    """형식에 어긋나면 `V(c)` 는 정의되지 않는다. 부르는 쪽이 **거짓**으로 다룬다."""
    assert variable_part("flag{abc}", FMT) is None  # 접두사 불일치
    assert variable_part("kisia{abc", FMT) is None  # 접미사 불일치
    assert variable_part("kisia{}", FMT) is None  # |c| == |P| + |S|


# -- 파생 탐색 ---------------------------------------------------------------


@pytest.mark.unit
def test_finds_two_part_derivation() -> None:
    found = find_decomposition(
        "5o9v_1472742", [src("o1", "TAGSEL:5o9v"), src("o2", "SUM=1472742")]
    )
    assert found is not None
    assert found.sources_used == ("o1", "o2")


@pytest.mark.unit
def test_hallucination_has_no_derivation() -> None:
    """`kisia{deadbeef}` 를 환각한 모델은 조각도 어떤 관찰에도 없으므로 여전히 FAIL."""
    assert find_decomposition("deadbeef", [src("o1", "TAGSEL:5o9v"), src("o2", "SUM=1")]) is None


@pytest.mark.unit
def test_segment_shorter_than_minimum_is_not_grounded() -> None:
    """`min_grounded_segment_len` 미만이면 아무 스트림에서나 주워 맞출 수 있다 (§3.5)."""
    assert find_decomposition("abc_def", [src("o1", "abc"), src("o2", "def")]) is None
    assert (
        find_decomposition(
            "abc_def", [src("o1", "abc"), src("o2", "def")], min_grounded_segment_len=3
        )
        is not None
    )


@pytest.mark.unit
def test_max_segments_blocks_pathological_slicing() -> None:
    variable = "_".join(["abcd"] * 6)  # 조각 6 + connector 5 = 11 > 8
    sources = [src("o1", "abcd")]
    assert find_decomposition(variable, sources, max_segments=8) is None
    assert find_decomposition(variable, sources, max_segments=12) is not None


# -- R3-2 : connector 배치 규칙 ---------------------------------------------


@pytest.mark.unit
def test_connector_cannot_be_first_or_last() -> None:
    assert find_decomposition("_abcd", [src("o1", "abcd")]) is None
    assert find_decomposition("abcd_", [src("o1", "abcd")]) is None


@pytest.mark.unit
def test_two_connectors_cannot_be_adjacent() -> None:
    sources = [src("o1", "abcd"), src("o2", "efgh")]
    assert find_decomposition("abcd__efgh", sources) is None
    assert find_decomposition("abcd_efgh", sources) is not None


@pytest.mark.unit
def test_a_decomposition_of_only_connectors_is_rejected() -> None:
    """근거 있는 조각이 하나 이상 있어야 한다."""
    assert find_decomposition("___", [src("o1", "___")]) is None


# -- S8.2 의 추가 조건 -------------------------------------------------------


@pytest.mark.unit
def test_require_two_distinct_sources() -> None:
    one = [src("o1", "abcd_efgh")]
    two = [src("o1", "abcd"), src("o2", "efgh")]
    assert find_decomposition("abcd_efgh", one, require_distinct_sources=2) is None
    assert find_decomposition("abcd_efgh", two, require_distinct_sources=2) is not None


@pytest.mark.unit
def test_search_is_complete_when_a_greedy_choice_would_fail() -> None:
    """앞에서부터 긴 조각을 먼저 집는 탐욕 탐색이면 놓치는 경우.

    `abcdefgh_ij` 에서 `abcdefgh` 를 통째로 집으면 나머지 `ij` 가 하한 미만이라
    막힌다. 완전 탐색은 되짚어 `abcd`+`efgh_ij` 를 찾아야 한다.
    """
    sources = [src("o1", "abcdefgh"), src("o2", "abcd"), src("o3", "efgh_ijkl")]
    found = find_decomposition("abcdefgh_ijkl", sources)
    assert found is not None
