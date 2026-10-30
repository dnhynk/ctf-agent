"""스트림 → escalation 패킷. **순수 함수이고 판정에 참여하지 않는다.**

근거: `SEAM_IMPLEMENTATION_MAP.md` §6, `TELEMETRY_SCHEMA.md` §5.2,
`ADR-0003-contest-architecture.md` Decision-3.

스트림 **밖** 입력이 없다. 라이트업과 같은 자세이고 여기서는 이유가 하나 더 있다 —
정답 파일은 `spec.md` S9.4a 가 **검사기**에게만 연 스트림 밖 입력이고, 밖으로 나가는
표면을 만드는 계층이 그것을 읽으면 S8.3 이 막으려던 것을 이 계층이 직접 실어 나르게
된다.

---

**`kisia.checker.model.load_stream` 만 쓴다** (`D-59`). 술어·판정 계층을 import
하지 않는다 — 하면 패킷이 판정을 흉내 내기 시작하고, §5 예약 이벤트에는 애초에
술어가 없다(`TELEMETRY_SCHEMA.md` §5.1, `R2-15`). 검사기와 **같은 관문**으로 읽는
이유도 라이트업과 같다: 무효인 스트림(S9.2)에서 만든 패킷은 근거 없는 서사가 된다.
"""

from __future__ import annotations

from typing import Any

from kisia.checker.model import Stream
from kisia.escalation.model import (
    ANSWER_ELIDED,
    SENTINEL_PREFIX,
    Fact,
    Inference,
    Packet,
    Redaction,
    Rejection,
    Stall,
)

#: 패킷이 나르는 통제 항목. **이름으로 고른 부분집합이고 통제 블록 전체가 아니다** —
#: telemetry-only 의 조건 2(`SAFETY_SCOPE.md` Escalation egress). 밖의 모델이 막힌
#: 문제를 보려면 무엇을 푸는지가 필요하고, `host_id`·`image_digest`·`pricing_sha256`
#: 같은 우리 기반 시설의 사실은 필요하지 않다. 라이트업이 통제 블록을 통째로 싣는
#: 것과 갈리는 자리이고, 갈리는 이유는 **라이트업은 밖으로 나가지 않기 때문**이다.
CARRIED_CONTROL = ("challenge_id", "challenge_set", "provenance", "flag_format")


def compile_packet(stream: Stream) -> Packet:
    """스트림 하나를 escalation 패킷으로 컴파일한다."""
    notes: list[str] = []
    blockers: list[str] = []
    redactions: list[Redaction] = []

    answers = _answers(stream)
    finished = stream.first("attempt.finished") or {}

    stalls = _stalls(stream)
    observations = {
        str(e.get("observation_id", "")): e for e in stream.by_type("observation.recorded")
    }
    confirmed = _confirmed(stalls, observations, answers, redactions)
    inferred = _inferred(stream, answers, redactions)
    rejected = _rejected(stream, inferred, answers, redactions)
    inferred = _mark_rejected(inferred, rejected)

    named = {oid for s in stalls for oid in s.confirmed_facts}
    not_promoted = tuple(oid for oid in observations if oid not in named)

    control = {k: stream.control[k] for k in CARRIED_CONTROL if k in stream.control}
    family = next((s.attempt_family for s in stalls if s.attempt_family), None)

    _note_shape(stalls, confirmed, inferred, rejected, not_promoted, notes)
    _note_answer_scope(answers, redactions, notes)
    _check_export(confirmed, inferred, rejected, stalls, blockers)

    return Packet(
        stream_path=str(stream.path),
        run_id=stream.run_id,
        attempt_id=stream.attempt_id,
        control=control,
        attempt_family=family,
        outcome=str(finished.get("outcome", "")),
        reason=_opt_str(finished.get("reason")),
        stalls=stalls,
        confirmed=confirmed,
        inferred=inferred,
        rejected=rejected,
        not_promoted=not_promoted,
        redactions=tuple(redactions),
        export_blockers=tuple(blockers),
        notes=tuple(notes),
        reader_notes=tuple(stream.reader_notes),
    )


# ---------------------------------------------------------------------------
# 절 셋
# ---------------------------------------------------------------------------


def _stalls(stream: Stream) -> tuple[Stall, ...]:
    return tuple(
        Stall(
            seq=int(e.get("seq", 0)),
            signal=str(e.get("signal", "")),
            window_turns=_opt_int(e.get("window_turns")),
            attempt_family=_opt_str(e.get("attempt_family")),
            confirmed_facts=tuple(str(x) for x in (e.get("confirmed_facts") or ())),
        )
        for e in stream.by_type("stall.observed")
    )


def _confirmed(
    stalls: tuple[Stall, ...],
    observations: dict[str, dict[str, Any]],
    answers: frozenset[str],
    redactions: list[Redaction],
) -> tuple[Fact, ...]:
    """CONFIRMED — **`stall.observed.confirmed_facts[]` 가 정하고 이 함수가 정하지 않는다.**

    `observation.recorded` 전체에서 고르지 않는 것이 요점이다. 그 목록에는 하니스
    자신의 도구가 만든 관찰(`tool:record_hypothesis …`)과 프로브의 관찰
    (`probe:P-S5-b …`)이 섞여 있고, 무엇이 환경에서 온 것인지는 `loop.py` 의
    `_own_tools` 필터가 **이미** 갈랐다(`O-36` / 경고 13). 여기서 다시 가르면 필터가
    두 벌이 되고, 두 벌은 조용히 갈린다.

    stall 이 여러 건이면 **먼저 지목된 순서**로 합집합을 만들고 어느 stall 이
    지목했는지를 `named_by` 로 남긴다.
    """
    order: list[str] = []
    named_by: dict[str, list[int]] = {}
    for s in stalls:
        for oid in s.confirmed_facts:
            if oid not in named_by:
                named_by[oid] = []
                order.append(oid)
            named_by[oid].append(s.seq)

    out: list[Fact] = []
    for oid in order:
        e = observations.get(oid)
        if e is None:
            # stall 이 이름을 댔는데 스트림에 그 관찰이 없다. **조용히 버리지 않는다** —
            # 버리면 패킷이 "그런 사실은 없었다"고 말하게 되고, 그것은 봉투의 결손을
            # 패킷이 대신 메우는 것이다.
            out.append(
                Fact(
                    observation_id=oid,
                    seq=None,
                    source_ref=None,
                    bytes_total=None,
                    bytes_shown=None,
                    shown=None,
                    shown_digest=None,
                    truncated=False,
                    full_digest=None,
                    named_by=tuple(named_by[oid]),
                )
            )
            continue
        out.append(
            Fact(
                observation_id=oid,
                seq=int(e.get("seq", 0)),
                source_ref=_scrub(
                    _opt_str(e.get("source_ref")), f"confirmed[{oid}].source_ref",
                    answers, redactions,
                ),
                bytes_total=_opt_int(e.get("bytes_total")),
                bytes_shown=_opt_int(e.get("bytes_shown")),
                # `shown` 은 **없음과 빈 문자열이 다르다** — 기본값을 ""로 두면 접힌다.
                shown=_scrub(
                    _opt_str(e.get("shown")), f"confirmed[{oid}].shown", answers, redactions
                ),
                shown_digest=_opt_str(e.get("shown_digest")),
                truncated=bool(e.get("truncated")),
                full_digest=_opt_str(e.get("full_digest")),
                named_by=tuple(named_by[oid]),
            )
        )
    return tuple(out)


def _inferred(
    stream: Stream, answers: frozenset[str], redactions: list[Redaction]
) -> tuple[Inference, ...]:
    """INFERRED — `hypothesis.recorded`. 주장 원문을 `tool.requested` 에서 찾아 나란히 싣는다."""
    claims = _ClaimIndex(stream)
    out: list[Inference] = []
    for e in stream.by_type("hypothesis.recorded"):
        statement = str(e.get("statement", ""))
        hid = str(e.get("hypothesis_id", ""))
        args = claims.take("statement", statement)
        out.append(
            Inference(
                seq=int(e.get("seq", 0)),
                hypothesis_id=hid,
                statement=_scrub_text(
                    statement, f"inferred[{hid}].statement", answers, redactions
                ),
                confidence=_opt_float(e.get("confidence")),
                supported_by=tuple(str(x) for x in (e.get("supported_by") or ())),
                claimed_support=None if args is None else _as_ids(args.get("supported_by")),
                turn=_opt_int(e.get("turn")),
            )
        )
    return tuple(out)


def _rejected(
    stream: Stream,
    inferred: tuple[Inference, ...],
    answers: frozenset[str],
    redactions: list[Redaction],
) -> tuple[Rejection, ...]:
    """REJECTED — `hypothesis.rejected`. **실측 0건이고 그것은 '재지 못함'이 아니다.**"""
    claims = _ClaimIndex(stream)
    statements = {i.hypothesis_id: i.statement for i in inferred}
    out: list[Rejection] = []
    for e in stream.by_type("hypothesis.rejected"):
        hid = str(e.get("hypothesis_id", ""))
        args = claims.take("hypothesis_id", hid)
        out.append(
            Rejection(
                seq=int(e.get("seq", 0)),
                hypothesis_id=hid,
                refuted_by=tuple(str(x) for x in (e.get("refuted_by") or ())),
                claimed_refutation=None if args is None else _as_ids(args.get("refuted_by")),
                reason_code=_scrub_text(
                    str(e.get("reason_code", "")),
                    f"rejected[{hid}].reason_code",
                    answers,
                    redactions,
                ),
                turn=_opt_int(e.get("turn")),
                statement=statements.get(hid),
            )
        )
    return tuple(out)


def _mark_rejected(
    inferred: tuple[Inference, ...], rejected: tuple[Rejection, ...]
) -> tuple[Inference, ...]:
    """기각된 가설에 그 사실을 표시한다. **INFERRED 에서 빼지 않는다** — 무엇을 믿었다가
    무엇 때문에 버렸는지가 escalation 이 나르는 것의 절반이다.
    """
    at = {r.hypothesis_id: r.seq for r in rejected}
    return tuple(
        i if i.hypothesis_id not in at else _with_rejection(i, at[i.hypothesis_id])
        for i in inferred
    )


def _with_rejection(i: Inference, seq: int) -> Inference:
    return Inference(
        seq=i.seq,
        hypothesis_id=i.hypothesis_id,
        statement=i.statement,
        confidence=i.confidence,
        supported_by=i.supported_by,
        claimed_support=i.claimed_support,
        turn=i.turn,
        rejected_at=seq,
    )


class _ClaimIndex:
    """예약 이벤트를 낳은 도구 호출의 `args` 를 찾는다 — **모양으로 찾고 이름으로 찾지 않는다.**

    `tool.requested.tool` 이 `record_hypothesis` 라는 것은 지금 런타임의 사실이지
    계약의 사실이 아니다. 계약은 도구 이름을 열거하지 않고(`spec.md` §0.1), 열거하면
    구현 모양을 계약이 정하게 된다 — 라이트업의 `_as_argv` 가 도구 이름 대신 `args`
    의 모양으로 가르는 것과 같은 이유다.

    **소비하며 찾는다.** 같은 진술을 두 번 기록한 attempt 에서 두 이벤트가 같은
    호출문 하나를 가리키면 둘 중 하나의 주장 원문이 거짓이 된다.
    """

    def __init__(self, stream: Stream) -> None:
        self._reqs: list[dict[str, Any] | None] = [
            e.get("args") if isinstance(e.get("args"), dict) else None
            for e in stream.by_type("tool.requested")
        ]

    def take(self, key: str, value: str) -> dict[str, Any] | None:
        for n, args in enumerate(self._reqs):
            if args is None:
                continue
            # **키가 없는 호출문은 후보가 아니다.** `args.get(key, "")` 만 보면 진술이
            # 빈 가설이 그 키를 아예 갖지 않는 아무 도구 호출과 짝지어지고, 그러면 이
            # 계층이 **없는 주장 원문을 지어내게 된다.**
            if key not in args:
                continue
            if str(args[key]).strip() == value.strip():
                self._reqs[n] = None
                return args
        return None


# ---------------------------------------------------------------------------
# S8.3 — 정답은 밖으로 나가는 표면에 실리지 않는다
# ---------------------------------------------------------------------------


def _answers(stream: Stream) -> frozenset[str]:
    """이 스트림이 아는 정답 문자열 — `candidate.produced.value`.

    **스트림 밖의 정답 파일을 읽지 않는다.** 그 파일은 `spec.md` S9.4a 가 검사기에게만
    연 입력이고, 밖으로 나가는 표면을 만드는 계층이 그것을 읽으면 S8.3 이 막으려던
    것을 이 계층이 직접 실어 나른다. 스트림만으로 잡을 수 있는 것은 후보 문자열이고,
    라이트업의 `test_repro_script_never_contains_the_flag` 도 같은 것을 쓴다.

    **여기 잡히지 않는 정답이 있을 수 있다** — 후보를 한 번도 내지 않은 채 관찰
    바이트에만 정답이 있는 스트림이 그렇다. 그 한계는 패킷의 `notes` 가 적는다.
    """
    return frozenset(
        v for e in stream.by_type("candidate.produced") if (v := str(e.get("value", "")))
    )


def _scrub(
    text: str | None, where: str, answers: frozenset[str], redactions: list[Redaction]
) -> str | None:
    if text is None:
        return None
    return _scrub_text(text, where, answers, redactions)


def _scrub_text(
    text: str, where: str, answers: frozenset[str], redactions: list[Redaction]
) -> str:
    """정답 문자열을 지우고 **지운 사실을 남긴다.**

    조용히 지우면 패킷을 읽는 쪽이 그 자리에 무엇이 있었는지 모른다. `ANSWER_ELIDED`
    표시와 `Redaction` 기록이 함께 간다.
    """
    out = text
    for answer in sorted(answers, key=len, reverse=True):
        n = out.count(answer)
        if n:
            out = out.replace(answer, ANSWER_ELIDED)
            redactions.append(Redaction(where=where, reason="candidate.produced.value", count=n))
    return out


def _note_answer_scope(
    answers: frozenset[str], redactions: list[Redaction], notes: list[str]
) -> None:
    """정답 제거가 **무엇에 대해** 수행됐는지를 적는다. 침묵은 "정답이 없었다"로 읽힌다."""
    if not answers:
        notes.append(
            "이 스트림에는 `candidate.produced` 가 0건이다 — 스트림만으로 정답 문자열을 "
            "지목할 수 없으므로 S8.3 제거는 **수행되지 않았다.** '제거할 것이 없었다'와 "
            "다르다: 후보를 한 번도 내지 않은 채 관찰 바이트에만 정답이 있는 스트림은 이 "
            "계층이 잡지 못한다. 실측 8 스트림이 전부 이 모양이다(`outcome=failed`)."
        )
        return
    total = sum(r.count for r in redactions)
    notes.append(
        f"정답 문자열 {len(answers)}종을 대상으로 제거를 수행했고 {total}자리를 지웠다 "
        "(S8.3 — 패킷은 밖으로 나가는 표면이다)."
    )


def _check_export(
    confirmed: tuple[Fact, ...],
    inferred: tuple[Inference, ...],
    rejected: tuple[Rejection, ...],
    stalls: tuple[Stall, ...],
    blockers: list[str],
) -> None:
    """export 게이트가 이 패킷을 거절해야 하는 사유를 **기록한다. 중단시키지 않는다.**

    컴파일러는 export 하지 않는다(이 세션의 범위 밖). 중단은 단일 export 경로의 일이고
    (`SAFETY_SCOPE.md` 조건 1·3, `PATH_SCOPE.md` §3.7), 컴파일러가 할 수 있는 것은
    **그 경로가 볼 수 있게 사유를 패킷에 싣는 것**이다.
    """
    texts = [t for f in confirmed for t in (f.source_ref, f.shown) if t]
    texts += [i.statement for i in inferred]
    texts += [r.reason_code for r in rejected]
    hits = sum(t.count(SENTINEL_PREFIX) for t in texts)
    if hits:
        blockers.append(
            "패킷이 redaction sentinel 을 나른다 — `SAFETY_SCOPE.md` Escalation egress "
            "조건 3 과 `PATH_SCOPE.md` §3.7 에 따라 export 는 **중단**된다. "
            f"(자리 {hits}건)"
        )
    if not stalls:
        blockers.append(
            "이 attempt 에는 `stall.observed` 가 0건이다 — **막힌 것으로 관측된 적이 "
            "없다.** `SEAM_IMPLEMENTATION_MAP.md` §6 이 이 산출물을 '막힌 attempt 의 "
            "스트림에서' 만드는 것으로 명명한다. 막히지 않은 attempt 의 챌린지 유래 "
            "내용을 밖으로 보낼 근거가 없다."
        )


# ---------------------------------------------------------------------------
# 주석 — **비어 있는 것과 재지 못한 것을 접지 않는다**
# ---------------------------------------------------------------------------


def _note_shape(
    stalls: tuple[Stall, ...],
    confirmed: tuple[Fact, ...],
    inferred: tuple[Inference, ...],
    rejected: tuple[Rejection, ...],
    not_promoted: tuple[str, ...],
    notes: list[str],
) -> None:
    if not stalls:
        notes.append(
            "`stall.observed` 가 0건이다 — 이 attempt 는 막힌 것으로 **관측된 적이 "
            "없다.** 결손이 아니다."
        )
    if not inferred:
        notes.append(
            "`hypothesis.recorded` 가 0건이다 — **가설 없음**이고 '접지 안 됨'이 "
            "아니다. **왜 0건인지는 봉투가 나르지 않는다** — 도구가 표면에 올라갔는지, "
            "올라갔는데 부르지 않았는지가 스트림에 없다(`JUDGMENT.md` §2.1 이 두 경우를 "
            "다 실측했다)."
        )
    ungrounded = [i for i in inferred if not i.grounded]
    if ungrounded:
        notes.append(
            f"접지되지 않은 가설 {len(ungrounded)}건 — **결손이 아니다.** 하니스가 "
            "실재하지 않는 관찰 id 를 걸렀고 주장 원문은 `tool.requested.args` 에 그대로 "
            "남아 있다. 원인은 모델의 부주의가 아니라 구조였다(`JUDGMENT.md` §2.2): "
            "도구 응답이 `observation_id` 를 나르지 않아 모델이 실제 id 를 한 번도 본 "
            "적이 없었다."
        )
    if not rejected:
        notes.append(
            "`hypothesis.rejected` 가 0건이다. **'0'이고 '재지 못함'이 아니다** — "
            "도구를 요청까지 한 뒤에도 기각한 run 이 없었다(`JUDGMENT.md` §2)."
        )
    unresolved = [f for f in confirmed if not f.resolved]
    if unresolved:
        notes.append(
            f"`stall.observed.confirmed_facts` 가 이름을 댔는데 스트림에 관찰이 없는 것 "
            f"{len(unresolved)}건: {[f.observation_id for f in unresolved]}. 봉투의 "
            "결손이고 패킷이 대신 메우지 않는다."
        )
    if not_promoted:
        notes.append(
            f"어떤 stall 도 지목하지 않은 관찰 {len(not_promoted)}건이 스트림에 더 있다 "
            "— 패킷은 **왜** 지목되지 않았는지를 주장하지 않는다. stall 뒤에 왔거나, "
            "하니스 자신의 도구가 만들었거나(`O-36`), 프로브가 냈을 수 있고 셋은 다른 "
            "사실이다."
        )
    if len(inferred) > 1:
        notes.append(
            f"이 attempt 의 가설이 {len(inferred)}건이다 — 접지 상태가 섞일 수 있는 "
            "모양이다. 실측 6건은 전부 attempt 당 1건이었다."
        )


# ---------------------------------------------------------------------------


def _as_ids(value: Any) -> tuple[str, ...]:
    """모델이 배열 대신 문자열 하나를 줄 수 있다 — `loop.py` 의 `_as_list` 와 같은 사실."""
    if isinstance(value, list):
        return tuple(str(x) for x in value)
    if isinstance(value, str) and value:
        return (value,)
    return ()


def _opt_str(v: Any) -> str | None:
    return None if v is None else str(v)


def _opt_int(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _opt_float(v: Any) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None
