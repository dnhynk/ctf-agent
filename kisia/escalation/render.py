"""패킷 → 사람이 읽는 마크다운.

`SEAM_IMPLEMENTATION_MAP.md` §6 이 이 산출물의 내용을 셋으로 적는다:
**CONFIRMED / INFERRED / REJECTED.** 절 이름을 그 셋에 맞춘다.

**빈 절을 지우지 않는다.** REJECTED 는 실측 0건이고, 절을 지우면 읽는 쪽이 "그런
것을 재지 않았다"로 읽는다. `CLAUDE.md` §6 — "수행하지 못함"과 "0"은 다른 값이다.
"""

from __future__ import annotations

from typing import Any

from kisia.escalation.model import Fact, Inference, Packet

#: 관찰 본문을 패킷에 실을 때의 상한. 봉투의 `bytes_shown_limit`(계약 값)과 다른
#: 것을 뜻한다 — 이쪽은 문서의 가독성이다. 넘기면 잘랐다고 적고 `shown_digest` 로
#: 원본을 지목한다. 라이트업의 `RENDER_LIMIT` 과 같은 자리이고 값도 같다.
RENDER_LIMIT = 1200


def render_markdown(p: Packet) -> str:
    out: list[str] = []
    _head(p, out)
    _confirmed(p, out)
    _inferred(p, out)
    _rejected(p, out)
    _appendix(p, out)
    return "\n".join(out).rstrip() + "\n"


def _head(p: Packet, out: list[str]) -> None:
    c = p.control
    out.append(f"# escalation 패킷 — {p.challenge_id or '(challenge_id 없음)'} / `{p.attempt_id}`")
    out.append("")
    out.append(
        "**이 문서는 스트림 하나의 투영이다. 판정에 참여하지 않는다** — "
        "`SEAM_IMPLEMENTATION_MAP.md` §6 이 escalation 패킷 컴파일러를 seam 이 아니라 "
        "telemetry 의 소비자로 명명하고, §5 예약 이벤트에는 애초에 술어가 없다 "
        "(`TELEMETRY_SCHEMA.md` §5.1, `R2-15`). 여기 있는 값은 전부 봉투에서 왔고, "
        "봉투에 없는 것은 **부재**라고 적는다 — `0` 이 아니다."
    )
    out.append("")
    out.append(
        "**telemetry-only** (`ADR-0003` Decision-3): raw 챌린지 바이너리·캡처·입력 파일은 "
        "이 패킷에 없다. `input.bound.files[]` 도 `artifact.produced` 도 싣지 않는다."
    )
    out.append("")
    out.append(f"대상 스트림: `{p.stream_path}`")
    out.append("")
    out.append("| | |")
    out.append("|---|---|")
    out.append(f"| challenge | `{c.get('challenge_id')}` (`{c.get('challenge_set')}`) |")
    out.append(f"| provenance | `{c.get('provenance')}` |")
    out.append(f"| flag_format | `{c.get('flag_format')}` |")
    out.append(f"| run / attempt | `{p.run_id}` / `{p.attempt_id}` |")
    # 위의 `대상 스트림` 은 기계마다 다르다(`O-48`). 이 줄은 그 경로를 뺀 값이라
    # **두 기계에서 같아야 하고**, S9.5 의 대조를 사람이 눈으로 할 수 있게 한다.
    out.append(f"| content hash | `{p.content_hash()}` |")
    out.append(f"| attempt_family | `{p.attempt_family or '부재'}` |")
    out.append(f"| outcome | **`{p.outcome or '(없음)'}`** — {p.reason or '사유 부재'} |")
    out.append(
        f"| 절 | CONFIRMED {len(p.confirmed)} · INFERRED {len(p.inferred)} "
        f"({p.grounding_label}) · REJECTED {len(p.rejected)} |"
    )
    out.append("")
    _stalls(p, out)
    if p.export_blockers:
        out.append("> **이 패킷은 그대로 export 되면 안 된다.**")
        out.append(">")
        for b in p.export_blockers:
            out.append(f"> - {b}")
        out.append("")


def _stalls(p: Packet, out: list[str]) -> None:
    out.append("## 왜 이 패킷이 있는가 — 관측된 stall")
    out.append("")
    if not p.stalled:
        out.append(
            "`stall.observed` 가 **0건**이다. 이 attempt 는 막힌 것으로 관측된 적이 "
            "없고, 그것은 결손이 아니다. escalation 은 정의상 막힌 attempt 의 것이므로 "
            "(`SEAM_IMPLEMENTATION_MAP.md` §6) 이 패킷에는 보낼 근거가 없다."
        )
        out.append("")
        return
    out.append(
        "**하니스가 센 것이지 판정이 아니다** — `stall.observed` 는 loop 이 실제로 센 "
        "값을 봤다는 기록이고, 신호마다 attempt 당 한 번이다(`D-73`). "
        "**여기 없는 신호가 '없었다'는 뜻은 아니다** — 계기가 없어 재지 못한 신호는 "
        "스트림이 아니라 `LoopReport.stall_signals_not_evaluated` 가 나른다."
    )
    out.append("")
    out.append("| seq | signal | window_turns | CONFIRMED 로 지목한 관찰 |")
    out.append("|---|---|---|---|")
    for s in p.stalls:
        out.append(
            f"| {s.seq} | `{s.signal}` | {_num(s.window_turns)} | "
            f"{len(s.confirmed_facts)}건 |"
        )
    out.append("")


def _confirmed(p: Packet, out: list[str]) -> None:
    out.append("## CONFIRMED — 환경에서 바이트로 본 것")
    out.append("")
    out.append(
        "출처는 `stall.observed.confirmed_facts[]` 이고 **컴파일러가 고른 것이 아니다.** "
        "하니스 자신의 도구가 만든 관찰은 그 목록에 들어가지 않는다 — 관측 `O-36`, "
        "물려받은 경고 13(*관측 장치를 관측 대상 안에 넣지 마라*). 가르는 자리는 "
        "`kisia/runtime/loop.py` 의 `_own_tools` 필터이고 컴파일러는 그것을 다시 만들지 "
        "않는다."
    )
    out.append("")
    if not p.confirmed:
        out.append(
            "지목된 사실이 **0건**이다."
            + ("" if p.stalled else " 이 스트림에는 `stall.observed` 자체가 없다.")
        )
        out.append("")
        return
    for f in p.confirmed:
        _fact(f, out)


def _fact(f: Fact, out: list[str]) -> None:
    if not f.resolved:
        out.append(
            f"**`{f.observation_id}`** — stall(seq {list(f.named_by)})이 이름을 댔는데 "
            "**스트림에 이 관찰이 없다.** 봉투의 결손이고 패킷이 대신 메우지 않는다."
        )
        out.append("")
        return
    head = f"**`{f.observation_id}`** (seq {f.seq}) — 출처 `{f.source_ref}`"
    head += " · **잘림** " if f.truncated else " · "
    head += f"{_num(f.bytes_shown)}/{_num(f.bytes_total)} B"
    out.append(head)
    out.append("")
    if f.shown is None:
        out.append("`shown` **부재** — 봉투가 보인 바이트를 나르지 않는다 (A-9 이 닫은 자리).")
        out.append("")
        return
    body = f.shown
    clipped = len(body) > RENDER_LIMIT
    if clipped:
        body = body[:RENDER_LIMIT]
    out.append("```")
    out.append(body)
    out.append("```")
    if clipped:
        out.append(
            f"*({RENDER_LIMIT}자에서 잘랐다. 봉투가 나르는 원문은 `shown_digest` "
            f"`{f.shown_digest}` 가 지목한다. 계약의 `bytes_shown_limit` 과 무관하다.)*"
        )
    out.append(f"`shown_digest` `{f.shown_digest or '부재'}`")
    out.append("")


def _inferred(p: Packet, out: list[str]) -> None:
    out.append("## INFERRED — 가설")
    out.append("")
    out.append(
        "`hypothesis.recorded` 다. **`supported_by[]` 는 모델의 주장이 아니라 하니스가 "
        "거른 결과이고**, 주장 원문은 `tool.requested.args` 에 그대로 남는다. 둘을 "
        "나란히 싣는다 — 출처가 다른 두 값을 접지 않는 것이 `spec.md` §0.3-3 (R2-12) "
        "의 자세다."
    )
    out.append("")
    if not p.inferred:
        out.append(
            "가설이 **0건**이다. **접지 안 됨이 아니라 가설 없음이고, 둘은 다른 사실이다.** "
            "**왜 0건인지를 이 스트림은 말하지 않는다** — 가설 도구가 표면에 올라갔는지, "
            "올라갔는데 모델이 부르지 않았는지는 봉투가 나르지 않는다. 저장소의 실측으로 "
            "둘 다 있었다: 노출만 한 2 run 은 네 번의 기회에 0회, 노출 시점에 요청을 한 번 "
            "실은 3 run 은 3/3 이 기록했다(`JUDGMENT.md` §2.1)."
        )
        out.append("")
        return
    out.append(f"이 패킷의 접지 상태: **{p.grounding_label}** (`{p.grounding}`).")
    out.append("")
    for i in p.inferred:
        _inference(i, out)


def _inference(i: Inference, out: list[str]) -> None:
    head = f"### `{i.hypothesis_id}` (seq {i.seq}, turn {_num(i.turn)}) — **{_g(i)}**"
    if i.rejected_at is not None:
        head += f" · seq {i.rejected_at} 에서 기각됨"
    out.append(head)
    out.append("")
    out.append("> " + i.statement.replace("\n", "\n> "))
    out.append("")
    out.append(f"- confidence: {_num(i.confidence)}  ← **모델의 진술이다.** 하니스가 재지 않는다")
    if i.supported_by:
        out.append(f"- `supported_by` (하니스가 거른 결과): {list(i.supported_by)}")
    else:
        out.append(
            "- `supported_by` (하니스가 거른 결과): **비었다** — 이 가설은 CONFIRMED 로 "
            "이어지지 않는다"
        )
    if i.claimed_support is None:
        out.append(
            "- 모델의 주장 원문: **찾지 못했다** — `tool.requested.args` 에서 이 진술을 "
            "낸 호출을 짝짓지 못했다. '주장이 비었다'와 다른 값이다"
        )
    else:
        out.append(f"- 모델이 실제로 댄 것 (`tool.requested.args`): {list(i.claimed_support)}")
    if i.dropped_claims:
        out.append(
            f"- 하니스가 거른 id: {list(i.dropped_claims)} — **스트림에 없는 관찰이다.** "
            "필터가 옳게 동작한 것이고 모델의 부주의가 아니다: 도구 응답이 "
            "`observation_id` 를 나르지 않아 모델이 실제 id 를 본 적이 없었다 "
            "(`JUDGMENT.md` §2.2)"
        )
    out.append("")


def _rejected(p: Packet, out: list[str]) -> None:
    out.append("## REJECTED — 기각된 가설")
    out.append("")
    if not p.rejected:
        out.append(
            "이 attempt 의 `hypothesis.rejected` 는 **0건이다. `0` 이고 `재지 못함` 이 "
            "아니다** — 봉투는 기각 이벤트를 나를 자리를 갖고 있고 그 자리가 비어 있다. "
            "저장소의 실측도 같다: 기각 도구를 요청까지 한 뒤에도 기각한 run 이 없었다"
            "(`JUDGMENT.md` §2). **이 절을 지우면 그 구분이 사라진다.**"
        )
        out.append("")
        return
    for r in p.rejected:
        out.append(f"### `{r.hypothesis_id}` (seq {r.seq}, turn {_num(r.turn)})")
        out.append("")
        if r.statement:
            out.append("> " + r.statement.replace("\n", "\n> "))
            out.append("")
        else:
            out.append(
                "이 스트림에 대응하는 `hypothesis.recorded` 가 없다 — 진술은 **부재**다."
            )
            out.append("")
        out.append(f"- `reason_code`: `{r.reason_code or '부재'}`")
        out.append(f"- `refuted_by` (하니스가 거른 결과): {list(r.refuted_by)}")
        if r.claimed_refutation is None:
            out.append("- 모델의 주장 원문: **찾지 못했다**")
        else:
            out.append(f"- 모델이 실제로 댄 것: {list(r.claimed_refutation)}")
        out.append("")


def _appendix(p: Packet, out: list[str]) -> None:
    out.append("---")
    out.append("")
    out.append("## 부록 1. 이 패킷이 싣지 않은 것")
    out.append("")
    out.append(
        "**telemetry-only** — `ADR-0003` Decision-3 과 `SAFETY_SCOPE.md` Escalation "
        "egress 조건 2. 넘어가지 않는 것: raw 챌린지 바이너리 · 캡처 · `input.bound.files[]` · "
        "`artifact.produced` 의 바이트와 해시 · 통제 블록 전체(호스트 id, 이미지 digest, "
        "단가표 해시는 밖의 모델이 막힌 문제를 보는 데 필요하지 않다)."
    )
    out.append("")
    if p.not_promoted:
        out.append(
            f"그리고 **어떤 stall 도 지목하지 않은 관찰 {len(p.not_promoted)}건**이 "
            f"스트림에 더 있다: {list(p.not_promoted)}. **왜 지목되지 않았는지를 이 "
            "패킷은 주장하지 않는다** — stall 뒤에 왔거나, 하니스 자신의 도구가 만들었거나 "
            "(`O-36`), 프로브가 냈을 수 있고 셋은 다른 사실이다."
        )
        out.append("")
    if p.redactions:
        out.append("## 부록 2. 제거한 것 — S8.3")
        out.append("")
        out.append(
            "패킷은 밖으로 나가는 표면이므로 **정답이 실리면 안 된다.** 지운 자리에는 "
            "표시가 남는다 — 조용히 지우면 읽는 쪽이 그 자리에 무엇이 있었는지 모른다."
        )
        out.append("")
        out.append("| 자리 | 사유 | 건수 |")
        out.append("|---|---|---|")
        for r in p.redactions:
            out.append(f"| `{r.where}` | `{r.reason}` | {r.count} |")
        out.append("")
    if p.notes:
        out.append("## 부록 3. 이 패킷이 접지 않은 구분")
        out.append("")
        for n in p.notes:
            out.append(f"- {n}")
        out.append("")
    if p.reader_notes:
        out.append("## 부록 4. 스트림 판독 주석")
        out.append("")
        for n in p.reader_notes:
            out.append(f"- {n}")
        out.append("")


# ---------------------------------------------------------------------------


def _g(i: Inference) -> str:
    return "접지됨" if i.grounded else "접지 안 됨"


def _num(v: Any) -> str:
    return "부재" if v is None else str(v)
