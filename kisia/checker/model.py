"""검사기의 자료형 — 판정값 여섯, seam 판정 넷, 스트림 적재와 첫 관문.

근거: `spec.md` §6.1 (seam 판정 넷), §6.2 (술어 판정 여섯),
`TELEMETRY_SCHEMA.md` §1 (공통 필드), §7-1 (첫 관문).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Verdict(Enum):
    """술어 판정값 여섯 — `spec.md` §6.2 (r1의 다섯 + R2-3).

    `counts_against_seam` 가 참인 값만 seam 을 FAIL 시킨다.
    `수행 불가` 와 `스트림 밖` 은 **세지 않는다.** 접으면 거짓 관측을 기록한다.
    """

    TRUE = ("true", "참")
    FALSE = ("false", "거짓")
    VACUOUS = ("vacuous", "공허참")
    NO_EVIDENCE = ("no_evidence", "증거 없음")
    NOT_PERFORMABLE = ("not_performable", "수행 불가")
    OUT_OF_STREAM = ("out_of_stream", "스트림 밖")

    ident: str
    label: str

    def __init__(self, ident: str, label: str) -> None:
        self.ident = ident
        self.label = label

    @property
    def satisfies(self) -> bool:
        """seam 판정에서 '만족'으로 세는가."""
        return self in (Verdict.TRUE, Verdict.VACUOUS)

    @property
    def counts_against_seam(self) -> bool:
        """이 값 하나로 seam 이 FAIL 되는가 — `spec.md` §6.2 표의 셋째 열."""
        return self in (Verdict.FALSE, Verdict.NO_EVIDENCE)

    @property
    def counted(self) -> bool:
        """seam 판정의 계산에 들어가는가. 수행 불가·스트림 밖은 들어가지 않는다."""
        return self not in (Verdict.NOT_PERFORMABLE, Verdict.OUT_OF_STREAM)


@dataclass(frozen=True)
class Result:
    """술어 하나의 판정 + 근거가 된 이벤트 seq (`spec.md` §6.5)."""

    predicate: str
    verdict: Verdict
    seqs: tuple[int, ...] = ()
    note: str = ""

    def as_json(self) -> dict[str, Any]:
        return {
            "predicate": self.predicate,
            "verdict": self.verdict.ident,
            "seqs": list(self.seqs),
            "note": self.note,
        }


class SeamVerdict(Enum):
    """seam 판정 넷 — `spec.md` §6.1."""

    # S105 는 오탐이다 — 이 둘은 비밀이 아니라 `spec.md` §6.1 의 판정 라벨이다.
    PASS = "PASS"  # noqa: S105
    PASS_PATCH = "PASS(patch n)"  # noqa: S105
    FAIL = "FAIL(Sk)"
    NA = "N/A"


@dataclass(frozen=True)
class SeamResult:
    seam: str
    verdict: SeamVerdict
    results: tuple[Result, ...]
    patches: int = 0
    #: FAIL 을 만든 술어 id 들. no-evidence 는 라벨을 달아 구분한다 (`CHECKER.md` §1.1).
    failing: tuple[str, ...] = ()
    no_evidence: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        if self.verdict is SeamVerdict.FAIL:
            body = ",".join(self.failing)
            all_ne = bool(self.failing) and set(self.failing) <= set(self.no_evidence)
            tail = "[no-evidence]" if all_ne else ""
            return f"FAIL({body}){tail}"
        if self.verdict is SeamVerdict.PASS_PATCH:
            return f"PASS(patch {self.patches})"
        return str(self.verdict.value)

    def as_json(self) -> dict[str, Any]:
        return {
            "seam": self.seam,
            "verdict": self.label,
            "patches": self.patches,
            "predicates": [r.as_json() for r in self.results],
        }


# ---------------------------------------------------------------------------
# 스트림
# ---------------------------------------------------------------------------


class StreamVoidError(Exception):
    """`spec.md` S9.2 — seq 에 빈틈이 있으면 그 attempt 의 **모든 판정이 무효**다.

    이것만이 평가를 중단시키는 조건이다. S9.1(통제 블록 결손)은 attempt 를
    폐기 대상으로 만들지만 술어 계산을 막지 않는다 — 원인을 진단할 수 있어야
    한다는 것이 검사기의 존재 이유이기 때문이다(`CHECKER.md` §1.1).
    """


@dataclass
class Stream:
    """한 attempt 의 이벤트 스트림."""

    path: Path
    events: list[dict[str, Any]]
    run_id: str
    attempt_id: str
    #: S9.1 이 거짓이라 이 attempt 의 결과가 폐기 대상인가 (`TELEMETRY_SCHEMA.md` §2).
    discarded: bool = False
    #: 검사기가 r1 스트림을 읽으려고 정규화한 자리. 판정에 쓰지 않고 보고만 한다.
    reader_notes: list[str] = field(default_factory=list)

    def by_type(self, *types: str) -> list[dict[str, Any]]:
        want = set(types)
        return [e for e in self.events if e.get("type") in want]

    def first(self, event_type: str) -> dict[str, Any] | None:
        for e in self.events:
            if e.get("type") == event_type:
                return e
        return None

    @property
    def control(self) -> dict[str, Any]:
        return self.first("attempt.started") or {}

    @property
    def outcome(self) -> str:
        fin = self.first("attempt.finished") or {}
        return str(fin.get("outcome", ""))

    @property
    def is_normal(self) -> bool:
        """정상 스트림인가 — 집합 판정에서 상시 술어가 걸리는 대상(`spec.md` §6.3)."""
        return self.outcome == "solved"

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.events)


def load_stream(path: Path) -> Stream:
    """스트림을 읽고 **첫 관문**을 통과시킨다 (`TELEMETRY_SCHEMA.md` §7-1).

    seq 가 1부터 빈틈없고 `run_id`·`attempt_id` 가 하나여야 한다. 어기면
    `StreamVoidError` — 그 attempt 의 모든 판정이 무효다(S9.2).
    """
    events: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:  # pragma: no cover - 형식 오류는 즉시 무효
            raise StreamVoidError(f"{path}:{lineno} JSON 아님: {exc}") from exc
        if not isinstance(obj, dict):
            raise StreamVoidError(f"{path}:{lineno} 이벤트가 객체가 아니다")
        events.append(obj)

    if not events:
        raise StreamVoidError(f"{path}: 이벤트가 0건이다")

    seqs = [e.get("seq") for e in events]
    expected = list(range(1, len(events) + 1))
    if seqs != expected:
        missing = sorted(set(expected) - {s for s in seqs if isinstance(s, int)})
        raise StreamVoidError(
            f"{path}: seq 가 1부터 빈틈없지 않다 (빠진 seq {missing[:10]}). "
            "S9.2 — 이 attempt 의 모든 판정이 무효다."
        )

    run_ids = {str(e.get("run_id")) for e in events}
    attempt_ids = {str(e.get("attempt_id")) for e in events}
    if len(run_ids) != 1 or len(attempt_ids) != 1:
        raise StreamVoidError(
            f"{path}: run_id {sorted(run_ids)} / attempt_id {sorted(attempt_ids)} 가 "
            "하나가 아니다. 한 attempt 는 하나를 갖는다 (TELEMETRY_SCHEMA §1)."
        )

    stream = Stream(
        path=path,
        events=events,
        run_id=run_ids.pop(),
        attempt_id=attempt_ids.pop(),
    )
    _normalise_for_reading(stream)
    return stream


def _normalise_for_reading(stream: Stream) -> None:
    """r1 시대 스트림을 **읽을 수 있게만** 만든다. 판정을 느슨하게 하지 않는다.

    유일한 정규화: `candidate.produced.derived_from` 가 문자열이면 1원소 배열로
    읽는다. r2가 이 필드를 배열로 바꿨고(`TELEMETRY_SCHEMA.md` §3.2), 문자열을
    읽지 못하면 r1 스트림이 로드 단계에서 죽어 델타를 볼 수 없다. **판정에는
    영향이 없다** — S7.2가 이 필드의 선언을 애초에 믿지 않고, S7.1(b)는 선언과
    무관하게 스스로 분할을 탐색한다.
    """
    for e in stream.events:
        if e.get("type") == "candidate.produced" and isinstance(e.get("derived_from"), str):
            e["derived_from"] = [e["derived_from"]]
            stream.reader_notes.append(
                f"seq {e.get('seq')}: candidate.produced.derived_from 이 문자열이라 "
                "1원소 배열로 읽었다 (r1 형식). 판정 입력이 아니다 — S7.2."
            )
