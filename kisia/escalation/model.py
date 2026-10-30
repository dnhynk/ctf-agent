"""escalation 패킷의 자료형 — 스트림의 투영이지 판정이 아니다.

근거: `SEAM_IMPLEMENTATION_MAP.md` §6 (S9의 두 소비자 — "둘 다 seam이 아니다.
둘 다 telemetry의 투영이다"), `TELEMETRY_SCHEMA.md` §5.2 (예약 이벤트 셋의 필드),
`ADR-0003-contest-architecture.md` Decision-3 (telemetry-only).

**여기에 판정값이 없는 것이 설계다.** 라이트업(`kisia/writeup/model.py`)과 같은
이유다 — `kisia.checker.model.Verdict` 를 쓰지 않고 있음/없음과 사유 문자열만
나른다. 다만 이쪽은 한 가지가 더 걸린다: **§5 예약 이벤트에는 애초에 술어가 없다**
(`TELEMETRY_SCHEMA.md` §5.1, `R2-15`). 패킷이 판정처럼 생긴 값을 만들어 내면 예약이
예약이 아니게 되고, 그것을 `kisia_tests/test_reserved_events.py` 의
`test_the_reserved_events_carry_no_predicate` 가 잠근다.

**접지를 셋으로 가른다.** 접지됨 · 접지 안 됨 · 가설 없음. 둘로 접으면 `D-63`
("재지 못함"을 0으로 접었다)이 난 자리를 다시 만든다. 넷째 값 `MIXED` 는 일반화가
아니라 산술이다 — 한 attempt 에 가설이 둘 이상이고 그중 일부만 접지되면 앞의 셋
어디에 넣어도 거짓이 된다. 실측 6건은 attempt 당 1건이라 아직 나타난 적이 없고,
그 사실 자체를 `Packet.notes` 가 적는다.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

#: 접지 상태 넷. **문자열 상수인 이유**는 `as_json()` 이 그대로 실어야 하고, 이 값이
#: 판정이 아니라 계수의 요약이기 때문이다 — `Verdict` 처럼 seam 을 움직이지 않는다.
GROUNDED = "grounded"
UNGROUNDED = "ungrounded"
NO_HYPOTHESIS = "no_hypothesis"
MIXED = "mixed"

#: 접지 상태의 사람용 라벨. `-` 를 쓰지 않는다 — 세 상태가 서로 다른 사실이다.
GROUNDING_LABEL = {
    GROUNDED: "접지됨",
    UNGROUNDED: "접지 안 됨",
    NO_HYPOTHESIS: "가설 없음",
    MIXED: "섞임",
}

#: 정답이 제거된 자리에 남기는 표시. **조용히 지우지 않는다** — 지운 사실이 사라지면
#: 패킷을 읽는 쪽이 그 자리에 원래 무엇이 있었는지 알 수 없다.
ANSWER_ELIDED = "«정답 제거됨»"

#: redaction sentinel 의 접두 (`TELEMETRY_SCHEMA.md` §3.2.1,
#: `kisia.runtime.telemetry.envelope.redaction_sentinel` 이 `<redacted:{ref}>` 를 낸다).
#:
#: **의도적 이중화다.** import 하면 escalation 이 `kisia.runtime` 을 끌게 되고
#: (`D-42`, 라이트업이 같은 이유로 막혀 있다) 이 계층이 순수 함수가 아니게 된다.
#: `cost.py` ↔ `checker/pricing.py` 의 이중화(`D-49`)와 같은 자세이고, 문자열 하나가
#: 어긋나면 시험이 잡는다.
SENTINEL_PREFIX = "<redacted:"


@dataclass(frozen=True)
class Redaction:
    """패킷에서 무엇을 지웠는가. **지운 사실은 패킷 안에 남는다.**"""

    #: 어느 자리인가 — `confirmed[obs-0003].shown` 꼴.
    where: str
    #: 왜 지웠나. 지금은 `candidate.produced.value` 하나뿐이다.
    reason: str
    count: int

    def as_json(self) -> dict[str, Any]:
        return {"where": self.where, "reason": self.reason, "count": self.count}


@dataclass(frozen=True)
class Fact:
    """CONFIRMED 한 건 — **환경에서 바이트로 본 것** (`observation.recorded`).

    이 절의 원천은 `stall.observed.confirmed_facts[]` 이고 그 목록은 **하니스가 이미
    가른 결과**다. 하니스 자신의 도구(`record_hypothesis` 등)가 만든 관찰은 거기
    들어가지 않는다 — 관측 `O-36` / 물려받은 경고 13(*관측 장치를 관측 대상 안에
    넣지 마라*). `kisia/runtime/loop.py` 의 `_own_tools` 필터가 그 자리다.

    **컴파일러는 그 필터를 다시 만들지 않는다.** 만들면 필터가 두 벌이 되고 조용히
    갈린다 — 라이트업이 파서를 두 벌 두지 않는 것과 같은 이유다.
    """

    observation_id: str
    #: 이 id 를 가진 `observation.recorded` 의 seq. **`None` 이면 stall 이 이름을
    #: 댔는데 스트림에 그 관찰이 없다** — 조용히 버리지 않고 이 값으로 남긴다.
    seq: int | None
    source_ref: str | None
    bytes_total: int | None
    bytes_shown: int | None
    shown: str | None
    shown_digest: str | None
    truncated: bool
    full_digest: str | None
    #: 이 id 를 CONFIRMED 로 지목한 `stall.observed` 의 seq 들.
    named_by: tuple[int, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.seq is not None

    def as_json(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "seq": self.seq,
            "resolved": self.resolved,
            "source_ref": self.source_ref,
            "bytes_total": self.bytes_total,
            "bytes_shown": self.bytes_shown,
            "shown": self.shown,
            "shown_digest": self.shown_digest,
            "truncated": self.truncated,
            "full_digest": self.full_digest,
            "named_by": list(self.named_by),
        }


@dataclass(frozen=True)
class Inference:
    """INFERRED 한 건 — `hypothesis.recorded`.

    **두 값을 나란히 싣는다.** `supported_by` 는 하니스가 실재하는 관찰 id 만 남긴
    결과이고, `claimed_support` 는 모델이 실제로 댄 것(`tool.requested.args`)이다.
    출처가 다른 두 값을 접지 않는 것이 `spec.md` §0.3-3 (R2-12) 의 자세다.

    실측(`JUDGMENT.md` §2.2): `out-b-stall2` 세 run 이 전부 `obs-001` 같은 **없는
    id** 를 댔고 필터가 셋 다 걸렀다. 원인은 모델의 부주의가 아니라 구조였다 — 도구
    응답이 `observation_id` 를 나르지 않아 모델이 실제 id 를 한 번도 본 적이 없었다.
    **그래서 접지 실패는 결손이 아니다.** 그 사실을 읽으려면 두 값이 다 있어야 한다.
    """

    seq: int
    hypothesis_id: str
    statement: str
    confidence: float | None
    #: 하니스가 거른 결과.
    supported_by: tuple[str, ...]
    #: 모델의 주장 원문. **`None` 은 "주장이 비었다"가 아니라 "주장 원문을 스트림에서
    #: 찾지 못했다"** 이다 — 빈 튜플과 다른 값이다.
    claimed_support: tuple[str, ...] | None
    turn: int | None
    #: 이 가설을 기각한 `hypothesis.rejected` 의 seq. 없으면 `None`.
    rejected_at: int | None = None

    @property
    def grounded(self) -> bool:
        return bool(self.supported_by)

    @property
    def grounding(self) -> str:
        return GROUNDED if self.grounded else UNGROUNDED

    @property
    def dropped_claims(self) -> tuple[str, ...]:
        """모델이 댔는데 하니스가 거른 id. 주장 원문이 없으면 빈 튜플이다."""
        if self.claimed_support is None:
            return ()
        kept = set(self.supported_by)
        return tuple(x for x in self.claimed_support if x not in kept)

    def as_json(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "confidence": self.confidence,
            "supported_by": list(self.supported_by),
            "claimed_support": None if self.claimed_support is None else list(self.claimed_support),
            "dropped_claims": list(self.dropped_claims),
            "grounding": self.grounding,
            "turn": self.turn,
            "rejected_at": self.rejected_at,
        }


@dataclass(frozen=True)
class Rejection:
    """REJECTED 한 건 — `hypothesis.rejected`.

    **실측 0건이다.** 그것은 "재지 못함"이 아니라 `0` 이다 — 도구를 요청까지 한 뒤에도
    기각한 run 이 없었다(`JUDGMENT.md` §2). 이 자료형이 있고 비어 있는 것이 그 사실의
    기록이고, 없는 것과 다르다.
    """

    seq: int
    hypothesis_id: str
    refuted_by: tuple[str, ...]
    claimed_refutation: tuple[str, ...] | None
    reason_code: str
    turn: int | None
    #: 기각된 가설의 진술. 같은 스트림에 `hypothesis.recorded` 가 없으면 `None`.
    statement: str | None = None

    def as_json(self) -> dict[str, Any]:
        claimed = self.claimed_refutation
        return {
            "seq": self.seq,
            "hypothesis_id": self.hypothesis_id,
            "refuted_by": list(self.refuted_by),
            "claimed_refutation": None if claimed is None else list(claimed),
            "reason_code": self.reason_code,
            "turn": self.turn,
            "statement": self.statement,
        }


@dataclass(frozen=True)
class Stall:
    """`stall.observed` 한 건 — **관측이지 판정이 아니다.**

    `kisia/runtime/loop.py` 의 `_observe_stalls` 가 낸다. "멈췄다"는 추론이 아니라
    loop 이 실제로 센 값이고, 신호마다 attempt 당 한 번이다(`D-73`).
    """

    seq: int
    signal: str
    window_turns: int | None
    attempt_family: str | None
    confirmed_facts: tuple[str, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "signal": self.signal,
            "window_turns": self.window_turns,
            "attempt_family": self.attempt_family,
            "confirmed_facts": list(self.confirmed_facts),
        }


@dataclass(frozen=True)
class Packet:
    """한 attempt 의 escalation 패킷. **스트림 하나에 대한 순수 함수의 결과다.**

    `SEAM_IMPLEMENTATION_MAP.md` §6 이 이 산출물을 "막힌 attempt 의 스트림에서
    CONFIRMED / INFERRED / REJECTED 로 나뉜 패킷"으로 명명한다.
    """

    stream_path: str
    run_id: str
    attempt_id: str
    #: **통제 블록 전체가 아니라 이름으로 고른 부분집합이다** — telemetry-only 의
    #: 조건 2. 어느 필드를 왜 실었는지는 `compile.py` 의 `CARRIED_CONTROL` 에 있다.
    control: dict[str, Any]
    attempt_family: str | None
    outcome: str
    reason: str | None
    stalls: tuple[Stall, ...]
    confirmed: tuple[Fact, ...]
    inferred: tuple[Inference, ...]
    rejected: tuple[Rejection, ...]
    #: 스트림에 있으나 **어떤 stall 도 지목하지 않은** 관찰 id. 왜 지목되지 않았는지는
    #: 이 계층이 주장하지 않는다 — stall 뒤에 왔거나, 하니스 자신의 도구가 만들었거나,
    #: 프로브가 냈을 수 있다. **세 가지를 접어서 하나로 적지 않는다.**
    not_promoted: tuple[str, ...]
    redactions: tuple[Redaction, ...]
    #: export 게이트가 이 패킷을 **거절해야 하는** 사유. 컴파일러는 export 하지 않으므로
    #: 중단시키지 않고 기록한다 (`SAFETY_SCOPE.md` Escalation egress 조건 3·5).
    export_blockers: tuple[str, ...]
    notes: tuple[str, ...] = ()
    reader_notes: tuple[str, ...] = ()

    @property
    def challenge_id(self) -> str:
        return str(self.control.get("challenge_id", ""))

    @property
    def stalled(self) -> bool:
        """이 attempt 가 **막힌 것으로 관측됐는가.** escalation 은 정의상 그것의 것이다."""
        return bool(self.stalls)

    @property
    def signals(self) -> tuple[str, ...]:
        return tuple(s.signal for s in self.stalls)

    @property
    def grounding(self) -> str:
        """이 패킷의 INFERRED 가 CONFIRMED 로 이어지는가 — **셋(+1) 으로 가른다.**"""
        if not self.inferred:
            return NO_HYPOTHESIS
        n = sum(1 for i in self.inferred if i.grounded)
        if n == len(self.inferred):
            return GROUNDED
        if n == 0:
            return UNGROUNDED
        return MIXED

    @property
    def grounding_label(self) -> str:
        return GROUNDING_LABEL[self.grounding]

    @property
    def unresolved_facts(self) -> tuple[Fact, ...]:
        """stall 이 이름을 댔는데 스트림에 관찰이 없는 것."""
        return tuple(f for f in self.confirmed if not f.resolved)

    def content_json(self) -> dict[str, Any]:
        """**해시가 걸리는 것.** `stream` 이 여기 없는 것이 요점이다 (`O-48`).

        `str(stream.path)` 는 작업 디렉터리와 경로 구분자를 담으므로 **기계마다 다르다**
        (실측: 같은 바이트를 다른 경로에 두고 컴파일하면 8/8 스트림의 해시가 갈렸고,
        갈린 키는 `stream` **하나뿐**이었다). 객체 전체에 해시를 걸면 S9.5 가 두 기계를
        대조하라고 한 자리에서 같은 attempt 가 다른 값을 낸다.

        **해시를 없애서 풀지 않는다** — 없애면 재현 대조 자체가 사라진다. 신원은
        `run_id`/`attempt_id` 가 나르고 그 둘은 여기 있다.

        **새 필드는 여기에 더한다.** `as_json()` 에만 더하면 해시 밖으로 새고, 그것을
        `test_escalation_hash.py` 의 키 대조가 잡는다.
        """
        return {
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "attempt_family": self.attempt_family,
            "control": self.control,
            "outcome": self.outcome,
            "reason": self.reason,
            "stalled": self.stalled,
            "stalls": [s.as_json() for s in self.stalls],
            "confirmed": [f.as_json() for f in self.confirmed],
            "inferred": [i.as_json() for i in self.inferred],
            "rejected": [r.as_json() for r in self.rejected],
            "grounding": self.grounding,
            "not_promoted": list(self.not_promoted),
            "redactions": [r.as_json() for r in self.redactions],
            "export_blockers": list(self.export_blockers),
            "notes": list(self.notes),
            "reader_notes": list(self.reader_notes),
        }

    def content_hash(self) -> str:
        """`content_json()` 의 sha256 — **S9.5 가 두 기계에서 대조하는 값이고**
        `SAFETY_SCOPE.md` Escalation egress 조건 5 가 기록하라는 content hash 다
        (`PATH_SCOPE.md` §3.7 의 `export.log` 가 "목적지·해시·redaction 결과"를 적는다).

        정규화 방식은 `kisia.checker.judge.Judgment.digest()` 와 **같은 철자**다 —
        `sort_keys` · `ensure_ascii=False` · `separators=(",", ":")` · utf-8.
        **의도적 이중화이고** 이유는 `SENTINEL_PREFIX` 와 같다: 판정 계층을 import 하면
        `D-59` 가 막은 경계가 열린다. 두 철자가 어긋나면 시험이 잡는다.
        """
        blob = json.dumps(
            self.content_json(), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def as_json(self) -> dict[str, Any]:
        """패킷의 기계 판독형 — `PATH_SCOPE.md` §3.7 의 `packet.json`.

        **`content_json()` 에 둘을 더한 것이다.** `stream` 은 어느 파일에서 왔는지가
        사람이 읽는 쪽의 유일한 출처 표시라서 버리지 않고, `content_hash` 는 그 경로를
        **뺀** 값이라서 두 기계의 `packet.json` 이 `stream` 에서 달라도 이 한 칸은 같다.
        **이 객체 전체에 다시 해시를 걸지 마라** — `O-48` 이 난 자리다.
        """
        return {
            "stream": self.stream_path,
            **self.content_json(),
            "content_hash": self.content_hash(),
        }
