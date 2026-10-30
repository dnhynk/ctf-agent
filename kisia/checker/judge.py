"""하중표, seam 판정, 집합 판정, 판정 digest.

근거: `spec.md` §5 (하중표), §6.1 (seam 판정 넷), §6.3 (판정 단위와 R3-7의 하한 4),
§6.4 (`probe_set_id` 는 통제 조건이다), S9.5 (판정 digest).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from kisia.checker.fixture import Fixture
from kisia.checker.model import Result, SeamResult, SeamVerdict, Stream, Verdict
from kisia.checker.predicates import SEAM_FUNCS, Ctx
from kisia.checker.pricing import Price

SEAMS: tuple[str, ...] = ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9")

#: `spec.md` §5 하중표. 빈칸은 그 유형이 그 seam 에 하중을 싣지 않아 `N/A` 다.
LOAD_TABLE: dict[str, frozenset[str]] = {
    "A": frozenset({"S1", "S2", "S3", "S4", "S5", "S7", "S8", "S9"}),
    "B": frozenset({"S2", "S4", "S5", "S6", "S7", "S8", "S9"}),
    "C": frozenset({"S2", "S4", "S6", "S7", "S8", "S9"}),
}

#: 프로브 술어 — 집합 안의 **어느 스트림 하나**가 만족시키면 만족 (`spec.md` §6.3).
#: 나머지는 상시 술어이고 **정상 스트림 전부**가 만족시켜야 한다.
PROBE_PREDICATES: frozenset[str] = frozenset(
    {"S2.2", "S2.3", "S2.4", "S3.3", "S4.4", "S5.4", "S5.5", "S6.5", "S8.5", "S9.5"}
)

#: 유형이 **싣는** 프로브 — `spec.md` §5 하중표의 괄호 안 글자다.
#:
#: 괄호 안의 글자는 "그 유형이 추가로 싣는 프로브"이고, 싣지 않은 프로브의 부재는
#: 그 유형의 결함이 아니다. 이 표가 없으면 유형 A가 P-S2-c(유형 C의 프로브) 부재로
#: FAIL 하고, 유형 B가 P-S5-a 부재로 FAIL 한다 — 계약이 그렇게 읽히지 않는다.
#:
#: 글자 -> 술어: S2 a=S2.2 b=S2.3 c=S2.4 · S3 a=S3.3 · S4 a=S4.4 ·
#: S5 a=S5.4 b=S5.5 · S6 a=S6.5 · S8 a=S8.5 · S9 a=S9.5
#:
#: 유형 B의 S2 에 글자가 없는 것은 r1 A-4의 결과다 — B가 S2 에 싣는 하중은 쓰기
#: 거부가 아니라 프로세스 트리 정리(S2.5)이고, 그것은 프로브가 아니라 상시 술어다.
PROBE_CARRY: dict[str, frozenset[str]] = {
    "A": frozenset({"S2.2", "S2.3", "S3.3", "S5.4", "S5.5", "S8.5", "S9.5"}),
    "B": frozenset({"S4.4", "S5.5"}),
    "C": frozenset({"S2.4", "S6.5"}),
}


def carried(challenge_type: str, predicate: str) -> bool:
    """이 유형이 그 술어를 판정에 싣는가.

    상시 술어는 전부 싣는다. 프로브 술어는 `PROBE_CARRY` 가 정한다. 유형을 모르면
    (픽스처 미해결) 전부 싣는다 — 진단 모드에서 무엇도 숨기지 않기 위해서다.
    """
    if predicate not in PROBE_PREDICATES:
        return True
    table = PROBE_CARRY.get(challenge_type)
    return True if table is None else predicate in table


def _set_s5_4(all_j: list[StreamJudgment]) -> Verdict:
    """P-S5-a 결정론을 **집합 위에서** 판정한다.

    `spec.md` S5.4: "한 스트림 안의 두 관찰일 필요는 없고, **집합 안에서** 같은
    `full_digest` 를 갖는 관찰들을 대조한다." 같은 파일을 두 run 이 각각 한 번씩
    읽었으면 그것이 곧 "같은 바이트를 두 번 넣은" 것이다.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for j in all_j:
        for o in j.stream.by_type("observation.recorded"):
            digest = str(o.get("full_digest", ""))
            if digest:
                groups.setdefault(digest, []).append(o)
    pairs = [v for v in groups.values() if len(v) >= 2]
    if not pairs:
        return Verdict.NO_EVIDENCE
    for members in pairs:
        shown = {int(m.get("bytes_shown", -1) or -1) for m in members}
        sd = {str(m.get("shown_digest", "")) for m in members}
        if len(shown) != 1 or len(sd) != 1:
            return Verdict.FALSE
    return Verdict.TRUE


#: 한 스트림이 아니라 **집합**이 판정 단위인 술어. `spec.md` §6.3 이 그렇게 적은 것만.
SET_LEVEL_PREDICATES: dict[str, Callable[[list[StreamJudgment]], Verdict]] = {"S5.4": _set_s5_4}


@dataclass(frozen=True)
class StreamJudgment:
    stream: Stream
    fixture: Fixture | None
    challenge_type: str
    seams: tuple[SeamResult, ...]
    results: tuple[Result, ...]
    undecidable: tuple[str, ...]

    @property
    def probe_set_id(self) -> str:
        raw = self.stream.control.get("probe_set_id")
        return str(raw) if raw else ""

    def digest(self) -> str:
        """판정 digest — S9.5가 두 기계에서 대조하는 값.

        모든 술어 판정값·근거 seq·프로브 집합을 정규 JSON 으로 직렬화한 sha256.
        """
        payload = {
            "attempt_id": self.stream.attempt_id,
            "probe_set_id": self.probe_set_id,
            "predicates": [r.as_json() for r in self.results],
            "seams": [(s.seam, s.label) for s in self.seams],
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def as_json(self) -> dict[str, Any]:
        return {
            "stream": str(self.stream.path),
            "run_id": self.stream.run_id,
            "attempt_id": self.stream.attempt_id,
            "challenge_type": self.challenge_type,
            "outcome": self.stream.outcome,
            "normal": self.stream.is_normal,
            "probe_set_id": self.probe_set_id,
            "attempt_discarded": self.stream.discarded,
            "reader_notes": list(self.stream.reader_notes),
            "undecidable_candidates": list(self.undecidable),
            "seams": [s.as_json() for s in self.seams],
            "judgment_digest": self.digest(),
        }


def judge_stream(
    stream: Stream,
    *,
    fixture: Fixture | None = None,
    pricing: dict[str, Price] | None = None,
    pricing_digest: str = "",
) -> StreamJudgment:
    ctx = Ctx(stream=stream, fixture=fixture, pricing=pricing, pricing_digest=pricing_digest)
    challenge_type = fixture.type if fixture else ""
    loaded = LOAD_TABLE.get(challenge_type)

    all_results: list[Result] = []
    seams: list[SeamResult] = []
    patches = _structural_patch_count(stream)

    for seam in SEAMS:
        results = tuple(SEAM_FUNCS[seam](ctx))
        all_results.extend(results)
        seams.append(_seam_verdict(seam, results, loaded, patches, challenge_type))

    # S9.1 이 거짓이면 이 attempt 의 결과는 폐기 대상이다 (`TELEMETRY_SCHEMA.md` §2).
    # 술어 계산은 막지 않는다 — 원인을 진단할 수 있어야 한다.
    stream.discarded = any(
        r.predicate == "S9.1" and r.verdict is Verdict.FALSE for r in all_results
    )

    return StreamJudgment(
        stream=stream,
        fixture=fixture,
        challenge_type=challenge_type,
        seams=tuple(seams),
        results=tuple(all_results),
        undecidable=tuple(ctx.undecidable_candidates),
    )


def _structural_patch_count(stream: Stream) -> int:
    raw = stream.control.get("structural_patches")
    return len(raw) if isinstance(raw, list) else 0


def _seam_verdict(
    seam: str,
    results: tuple[Result, ...],
    loaded: frozenset[str] | None,
    patches: int,
    challenge_type: str,
) -> SeamResult:
    if loaded is not None and seam not in loaded:
        return SeamResult(seam, SeamVerdict.NA, results, patches)
    counted = [r for r in results if carried(challenge_type, r.predicate)]
    failing = tuple(r.predicate for r in counted if r.verdict.counts_against_seam)
    no_ev = tuple(r.predicate for r in counted if r.verdict is Verdict.NO_EVIDENCE)
    if failing:
        return SeamResult(seam, SeamVerdict.FAIL, results, patches, failing, no_ev)
    verdict = SeamVerdict.PASS_PATCH if patches else SeamVerdict.PASS
    return SeamResult(seam, verdict, results, patches)


# ---------------------------------------------------------------------------
# 집합 판정 — `spec.md` §6.3
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SetJudgment:
    challenge_type: str
    judgments: tuple[StreamJudgment, ...]
    seams: dict[str, str]
    insufficient: bool
    normal_count: int
    probe_set_ids: tuple[str, ...]
    notes: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "challenge_type": self.challenge_type,
            "normal_streams": self.normal_count,
            "insufficient_evidence": self.insufficient,
            "probe_set_ids": list(self.probe_set_ids),
            "seams": dict(self.seams),
            "notes": list(self.notes),
            "streams": [j.as_json() for j in self.judgments],
        }


def judge_set(judgments: list[StreamJudgment], *, minimum_normal: int = 4) -> SetJudgment:
    """유형의 스트림 집합에 대한 판정.

    - 프로브 술어는 집합 안의 어느 스트림 하나가 만족시키면 만족.
    - 상시 술어는 **정상 스트림 전부**가 만족시켜야 한다.
    - 음성 스트림의 seam FAIL 은 의도된 신호이고 상시 술어 판정에 넣지 않는다.
    - 정상 스트림이 `minimum_normal` 미만이면 **증거 부족**이고 seam 판정을 내지 않는다 (R3-7).
    """
    types = {j.challenge_type for j in judgments}
    challenge_type = types.pop() if len(types) == 1 else "?"
    normals = [j for j in judgments if j.stream.is_normal]
    probe_ids = tuple(sorted({j.probe_set_id for j in judgments}))
    notes: list[str] = []

    if len(types) > 0:
        notes.append(f"집합 안에 유형이 섞였다: {sorted(types | {challenge_type})}")
    if len(probe_ids) > 1:
        # §6.4 — probe_set_id 가 다른 스트림은 같은 집합 판정에 넣지 않는다.
        notes.append(
            f"probe_set_id 가 섞였다 {probe_ids} — §6.4에 따라 이 집합은 무엇을 쟀는지 "
            "정의되지 않는다"
        )
    insufficient = len(normals) < minimum_normal
    if insufficient:
        notes.append(
            f"정상 스트림 {len(normals)}개 < {minimum_normal} — 증거 부족 (R3-7). "
            "seam 판정을 내지 않는다"
        )

    loaded = LOAD_TABLE.get(challenge_type, frozenset())
    seams: dict[str, str] = {}
    for seam in SEAMS:
        if challenge_type and seam not in loaded:
            seams[seam] = "N/A"
            continue
        if insufficient:
            seams[seam] = "증거 부족"
            continue
        seams[seam] = _set_seam(seam, judgments, normals)
    return SetJudgment(
        challenge_type=challenge_type,
        judgments=tuple(judgments),
        seams=seams,
        insufficient=insufficient,
        normal_count=len(normals),
        probe_set_ids=probe_ids,
        notes=tuple(notes),
    )


def _set_seam(seam: str, all_j: list[StreamJudgment], normals: list[StreamJudgment]) -> str:
    predicate_ids: list[str] = []
    for j in all_j:
        for r in j.results:
            if r.predicate.startswith(seam + ".") and r.predicate not in predicate_ids:
                predicate_ids.append(r.predicate)

    failing: list[str] = []
    no_evidence: list[str] = []
    patches = max((_structural_patch_count(j.stream) for j in all_j), default=0)

    challenge_type = all_j[0].challenge_type if all_j else ""
    for pid in predicate_ids:
        if not carried(challenge_type, pid):
            continue
        if pid in SET_LEVEL_PREDICATES:
            verdict = SET_LEVEL_PREDICATES[pid](all_j)
            if verdict.counted and not verdict.satisfies:
                failing.append(pid)
                if verdict is Verdict.NO_EVIDENCE:
                    no_evidence.append(pid)
            continue
        # 프로브 술어는 음성 스트림의 증거도 쓴다. 상시 술어는 정상 스트림만.
        pool = all_j if pid in PROBE_PREDICATES else normals
        verdicts = [r.verdict for j in pool for r in j.results if r.predicate == pid]
        if not verdicts:
            continue
        if all(not v.counted for v in verdicts):
            continue  # 수행 불가 / 스트림 밖 — 세지 않는다
        counted = [v for v in verdicts if v.counted]
        satisfied = any(v.satisfies for v in counted) if pid in PROBE_PREDICATES else all(
            v.satisfies for v in counted
        )
        if not satisfied:
            failing.append(pid)
            if all(v is Verdict.NO_EVIDENCE for v in counted if not v.satisfies):
                no_evidence.append(pid)

    if failing:
        tail = "[no-evidence]" if set(failing) <= set(no_evidence) else ""
        return f"FAIL({','.join(failing)}){tail}"
    return f"PASS(patch {patches})" if patches else "PASS"
