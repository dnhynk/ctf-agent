"""근거 있는 파생 (grounding decomposition) — `spec.md` S7 정의부, R3-1~R3-3.

S7.1(b)와 S8.2가 같은 장치를 쓴다. 다른 것은 **소스 집합**과 **추가 조건**뿐이다.

- S7.1(b): 소스 = 그 후보보다 앞선 모든 관찰의 `shown`. 추가 조건 없음.
- S8.2   : 소스 = 그 관찰보다 앞선 모든 관찰의 `shown` + `part_hits` 가 기록된
  스윕 표면. 추가 조건 = 서로 다른 소스가 **둘 이상**, 그리고 어느 단일 소스도
  `V` 를 통째로 담지 않는다.

**완전 탐색이다 (R3-3).** 분할이 존재하는데 찾지 못하는 일이 있으면 안 된다.
시간 제한·부분 탐색·휴리스틱 가지치기를 두지 않는다 — 그렇게 하면 두 검사기가
같은 스트림에 다른 판정을 낼 수 있고, 그것은 계약을 관측으로 쓰는 이유 전체를
무너뜨린다. 상한은 `max_variable_len` 하나이고, 넘으면 **판정 불가**로 보고하고
seam 판정에 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

#: `flag_format` 의 구멍을 나타내는 리터럴.
#:
#: `MANIFEST.md` §2.2 는 "구멍이 정확히 하나인 템플릿. 예 `kisia{...}`" 라고만
#: 적고 마커를 이름으로 정하지 않았다. 저장소에 있는 세 매니페스트가 전부
#: `kisia{...}` 이므로 그 예시가 유일한 명세다. 마커를 여기 한 곳에 둔다.
HOLE = "..."

DEFAULT_CONNECTORS = ("_", "-", ":", ".")
DEFAULT_MIN_GROUNDED_SEGMENT_LEN = 4
DEFAULT_MAX_SEGMENTS = 8
DEFAULT_MAX_VARIABLE_LEN = 128


class FlagFormatError(ValueError):
    """`flag_format` 에 구멍이 정확히 하나가 아니다."""


@dataclass(frozen=True)
class Source:
    """파생의 소스 하나. `origin` 은 근거 보고에 쓴다."""

    ident: str
    text: str
    origin: str = ""


@dataclass(frozen=True)
class Segment:
    text: str
    is_connector: bool
    source_id: str | None = None


@dataclass(frozen=True)
class Decomposition:
    segments: tuple[Segment, ...]

    @property
    def sources_used(self) -> tuple[str, ...]:
        seen: list[str] = []
        for s in self.segments:
            if s.source_id is not None and s.source_id not in seen:
                seen.append(s.source_id)
        return tuple(seen)

    def describe(self) -> str:
        parts = []
        for s in self.segments:
            parts.append(s.text if s.is_connector else f"{s.text}<-{s.source_id}")
        return " ".join(parts)


def split_flag_format(flag_format: str) -> tuple[str, str]:
    """`flag_format` 을 구멍 앞 접두사 `P` 와 구멍 뒤 접미사 `S` 로 가른다 (R3-1)."""
    if flag_format.count(HOLE) != 1:
        raise FlagFormatError(
            f"flag_format {flag_format!r} 에 구멍({HOLE!r})이 정확히 하나가 아니다 "
            "(MANIFEST §2.2)"
        )
    prefix, suffix = flag_format.split(HOLE, 1)
    return prefix, suffix


def variable_part(candidate: str, flag_format: str) -> str | None:
    """후보 `c` 의 가변부 `V(c)` — R3-1.

    `c` 가 `P` 로 시작하고 `S` 로 끝나며 `|c| > |P| + |S|` 이면 그 사이가 `V(c)` 다.
    **하나라도 어긋나면 `V(c)` 는 정의되지 않고 `None` 을 돌려준다.** 부르는 쪽은
    그것을 `거짓`으로 다루어야 한다 — 형식에 맞지 않는 문자열은 이 챌린지의
    flag 가 아니다. `없음` 이나 `판정 불가` 로 접지 않는다.
    """
    prefix, suffix = split_flag_format(flag_format)
    if not candidate.startswith(prefix) or not candidate.endswith(suffix):
        return None
    if len(candidate) <= len(prefix) + len(suffix):
        return None
    end = len(candidate) - len(suffix) if suffix else len(candidate)
    return candidate[len(prefix) : end]


# ---------------------------------------------------------------------------
# 완전 탐색
# ---------------------------------------------------------------------------

#: 소스 상태 — 'none' / ('one', src_id) / 'two+'.
#:
#: S8.2의 "서로 다른 소스가 둘 이상"을 탐색 안에서 만족시키기 위해 필요하다.
#: 상태 밖에서 사후 필터로 처리하면 완전성이 깨진다 — 조건을 만족하지 않는
#: 분할 하나를 먼저 찾고 멈추면 만족하는 다른 분할을 놓친다.
#: 탐색 상태 — (pos, k, last_is_connector, source_state).
State = tuple[int, int, bool, tuple[str, ...]]

SourceState = tuple[str, ...]
_NONE: SourceState = ("none",)
_TWO_PLUS: SourceState = ("two+",)


def find_decomposition(
    variable: str,
    sources: list[Source],
    *,
    connectors: tuple[str, ...] = DEFAULT_CONNECTORS,
    min_grounded_segment_len: int = DEFAULT_MIN_GROUNDED_SEGMENT_LEN,
    max_segments: int = DEFAULT_MAX_SEGMENTS,
    require_distinct_sources: int = 1,
) -> Decomposition | None:
    """`variable` 의 근거 있는 파생을 찾는다. 없으면 `None`.

    `require_distinct_sources` 가 2면 S8.2의 추가 조건("서로 다른 소스가 둘
    이상")을 탐색 안에서 강제한다.

    상태는 `(pos, k, last_is_connector, source_state)` 이고, `source_state` 는
    `none` / `one:<id>` / `two+` 셋 중 하나다. 상태 수는
    `O(|V| x max_segments x 2 x |S|)`, 상태당 전이는 `O(|V| x |S|)` 이므로
    전체가 다항이고 어떤 가지치기도 필요 없다.

    connector 배치 규칙 (R3-2): 연속한 두 connector 금지, 첫 조각과 마지막
    조각은 connector 일 수 없다. 두 규칙이 없으면 임의의 문자열을 잘게 썰어
    `k` 를 늘리는 우회가 생긴다.
    """
    n = len(variable)
    if n == 0:
        return None
    conn = {c for c in connectors if len(c) == 1}

    # 조각 길이 하한을 만족하는 위치쌍마다 그것을 담은 소스를 먼저 모은다.
    # (i, j) -> 그 부분문자열을 문자 그대로 담은 소스 id 들.
    grounded: dict[tuple[int, int], tuple[str, ...]] = {}
    for i in range(n):
        for j in range(i + min_grounded_segment_len, n + 1):
            piece = variable[i:j]
            holders = tuple(s.ident for s in sources if piece in s.text)
            if holders:
                grounded[(i, j)] = holders

    start: State = (0, 0, False, _NONE)
    # 상태 -> (이전 상태, 그 전이가 만든 Segment)
    back: dict[State, tuple[State, Segment] | None] = {start: None}
    frontier: list[State] = [start]

    accepted: State | None = None
    while frontier and accepted is None:
        nxt: list[State] = []
        for state in frontier:
            pos, k, last_conn, src_state = state
            if k >= max_segments:
                continue

            # (1) connector 한 글자.
            if pos > 0 and pos < n and not last_conn and variable[pos] in conn:
                cand: State = (pos + 1, k + 1, True, src_state)
                if cand not in back:
                    back[cand] = (state, Segment(variable[pos], True, None))
                    nxt.append(cand)

            # (2) 근거 있는 조각.
            for j in range(pos + min_grounded_segment_len, n + 1):
                holders = grounded.get((pos, j)) or ()
                if not holders:
                    continue
                for holder in holders:
                    new_src: SourceState
                    if src_state == _NONE:
                        new_src = ("one", holder)
                    elif src_state == _TWO_PLUS:
                        new_src = _TWO_PLUS
                    else:
                        new_src = src_state if src_state[1] == holder else _TWO_PLUS
                    nxt_state: State = (j, k + 1, False, new_src)
                    if nxt_state not in back:
                        back[nxt_state] = (state, Segment(variable[pos:j], False, holder))
                        nxt.append(nxt_state)

        for state in nxt:
            pos, k, last_conn, src_state = state
            if pos != n or last_conn or k > max_segments:
                continue
            if src_state == _NONE:
                continue  # 근거 있는 조각이 하나도 없다
            if require_distinct_sources >= 2 and src_state != _TWO_PLUS:
                continue
            accepted = state
            break
        frontier = nxt

    if accepted is None:
        return None

    segments: list[Segment] = []
    cursor: State = accepted
    while True:
        step = back[cursor]
        if step is None:
            break
        prev, seg = step
        segments.append(seg)
        cursor = prev
    segments.reverse()
    return Decomposition(tuple(segments))


def quoted_by(candidate: str, sources: list[Source]) -> list[str]:
    """후보 문자열을 **문자 그대로** 담은 소스 id 들 — S7.1(a)의 인용."""
    return [s.ident for s in sources if candidate in s.text]
