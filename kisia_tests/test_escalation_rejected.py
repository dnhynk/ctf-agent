"""REJECTED 절을 **실제로 채워** 시험한다 — 합성 스트림으로.

프로덕션-3 트랙 P-D, 2026-08-09.

---

**왜 이 파일이 있나.** `NEXT_SESSION.md` §7.4 가 두 세션째 적는다: `hypothesis.rejected`
**0건** — 기각이 나오는 궤적을 아직 관측하지 못했고, 그래서 escalation 컴파일러의
REJECTED 절이 **빈 절로만** 시험됐다. 빈 절만 통과한 코드는 채워졌을 때 무엇을 할지
아무것도 보장하지 않는다.

**0 은 재지 못함이 아니다.** 실측이 0인 것은 사실이고 이 파일이 그 사실을 바꾸지
않는다 — `test_escalation.py::test_an_empty_rejected_section_is_zero_and_not_unmeasured`
가 계속 실측 스트림에 대해 0 을 잠근다. 여기서 채우는 것은 **합성 스트림**이고, 그
사실을 흐리지 않기 위해 파일을 나눴다.

**왜 합성으로 채울 수 있나.** 컴파일러는 스트림에 대한 순수 함수다. 기각 이벤트가
어디서 왔든 컴파일러가 보는 것은 봉투뿐이므로, 봉투를 직접 지으면 모델 지출 없이 절을
채울 수 있다. 궤적 쪽 분석은 `docs/rebuild/HYPOTHESIS_REJECTED_DESIGN.md` 다.

**이 파일이 재는 것.**

1. 채워진 절이 실제로 채워지는가 — seq · `reason_code` · 진술 역참조.
2. **기각된 가설이 INFERRED 에서 빠지지 않는가** (`_mark_rejected`). 무엇을 믿었다가
   무엇 때문에 버렸는지가 escalation 이 나르는 것의 절반이다.
3. **두 값을 접지 않는가** — `refuted_by`(하니스가 거른 결과)와 `claimed_refutation`
   (모델의 주장 원문)은 출처가 다르다 (`spec.md` §0.3-3 / R2-12).
4. **`S8.3`** — 기각 사유에 정답이 섞여도 밖으로 나가지 않는다.
5. 절이 차면 "0건" 주석이 **사라지는가.** 남으면 패킷이 거짓을 적는다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kisia.checker.model import load_stream
from kisia.escalation import compile_packet, render_markdown
from kisia.escalation.model import Packet

ROOT = Path(__file__).resolve().parents[1]
P1 = ROOT / "kisia_tests" / "data" / "streams" / "2026-08-09-p1-publisher-agentc"
#: 가설 3건이 전부 접지된 디렉터리 — 기각을 얹을 바탕으로 가장 알맞다.
STALL3 = sorted((P1 / "out-b-stall3").glob("*.jsonl"))

Events = list[dict[str, Any]]


def _events(path: Path) -> Events:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _rewrite(tmp_path: Path, events: Events, name: str = "rejected.jsonl") -> Path:
    """`test_escalation.py` 의 같은 이름 도우미와 같은 이유로 **`seq` 를 다시 매긴다** —
    다시 매기지 않으면 `load_stream` 의 S9.2 관문이 먼저 걸려 대상이 평가되지 않는다.
    """
    # **봉투의 신원을 물려준다.** `w.emit` 이 모든 이벤트에 `run_id`/`attempt_id` 를
    # 찍으므로 합성 이벤트도 같아야 한다 — 다르면 `load_stream` 이 "한 attempt 는
    # 하나씩 갖는다"(TELEMETRY_SCHEMA §1)로 스트림을 무효 처리하고, 그러면 대상이
    # 평가되지 못한 채 시험이 붉어진다(실측).
    head = events[0]
    for i, e in enumerate(events, start=1):
        e["seq"] = i
        e.setdefault("run_id", head.get("run_id"))
        e.setdefault("attempt_id", head.get("attempt_id"))
    out = tmp_path / name
    out.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8"
    )
    return out


def _insert_before_finish(events: Events, new: Events) -> Events:
    """`attempt.finished` **앞**에 끼워 넣는다 — 뒤에 두면 봉투 순서가 거짓이 된다."""
    at = next(i for i, e in enumerate(events) if e["type"] == "attempt.finished")
    return [*events[:at], *new, *events[at:]]


def _reject_event(hid: str, refuted: list[str], reason: str = "observation_contradicts") -> dict:
    """`kisia/runtime/loop.py` 의 `reject` 가 내는 것과 **같은 모양**.

    `refuted_by` 는 하니스가 이미 거른 결과다 — 여기서도 실재하는 id 만 담는다.
    """
    return {
        "type": "hypothesis.rejected",
        "hypothesis_id": hid,
        "refuted_by": refuted,
        "reason_code": reason,
        "turn": 5,
    }


def _reject_request(hid: str, claimed: list[str]) -> dict:
    """그 기각을 낳은 도구 호출문. **모델의 주장 원문**이 여기 남는다."""
    return {
        "type": "tool.requested",
        "tool": "reject_hypothesis",
        "args": {"hypothesis_id": hid, "refuted_by": claimed, "reason_code": "x"},
        "turn": 5,
    }


def _one_rejection(tmp_path: Path, **kw: Any) -> tuple[Packet, str, str]:
    """실측 스트림 하나에 기각 한 건을 얹는다. 첫 가설을 대상으로 한다."""
    src = STALL3[0]
    events = _events(src)
    rec = next(e for e in events if e["type"] == "hypothesis.recorded")
    hid = str(rec["hypothesis_id"])
    observed = [str(e["observation_id"]) for e in events if e["type"] == "observation.recorded"]
    refuted = kw.get("refuted", observed[:1])
    claimed = kw.get("claimed", refuted)
    extra: Events = []
    if kw.get("with_request", True):
        extra.append(_reject_request(kw.get("claim_hid", hid), claimed))
    extra.append(
        _reject_event(
            kw.get("hid", hid), refuted, kw.get("reason", "observation_contradicts")
        )
    )
    path = _rewrite(tmp_path, _insert_before_finish(events, extra))
    return compile_packet(load_stream(path)), hid, str(rec["statement"])


# ---------------------------------------------------------------------------
# 0. 전제 — 바탕 스트림이 실제로 그 모양인가
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_base_stream_has_no_rejection_of_its_own() -> None:
    """**전제가 깨지면 아래 전부가 공허해진다.** 실측은 0건이고 우리가 얹는다."""
    assert len(STALL3) == 3, STALL3
    base = compile_packet(load_stream(STALL3[0]))
    assert base.rejected == (), "바탕 스트림에 이미 기각이 있다 — 이 파일의 전제가 틀렸다"
    assert base.inferred, "바탕 스트림에 가설이 없다 — 기각을 얹을 대상이 없다"


# ---------------------------------------------------------------------------
# 1. 절이 실제로 채워지는가
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_a_filled_rejected_section_is_actually_filled(tmp_path: Path) -> None:
    p, hid, statement = _one_rejection(tmp_path)
    assert len(p.rejected) == 1, p.rejected
    (r,) = p.rejected
    assert r.hypothesis_id == hid
    assert r.reason_code == "observation_contradicts"
    assert r.seq > 0
    assert r.turn == 5
    # 진술은 같은 스트림의 `hypothesis.recorded` 에서 역참조된다.
    assert r.statement == statement


@pytest.mark.contract
def test_the_rejected_hypothesis_stays_in_inferred(tmp_path: Path) -> None:
    """**INFERRED 에서 빼지 않는다.** 무엇을 믿었다가 왜 버렸는지가 절반이다."""
    p, hid, _ = _one_rejection(tmp_path)
    match = [i for i in p.inferred if i.hypothesis_id == hid]
    assert len(match) == 1, (
        f"기각된 가설이 INFERRED 에서 사라졌다: {[i.hypothesis_id for i in p.inferred]}"
    )
    assert match[0].rejected_at == p.rejected[0].seq, "기각 표시가 붙지 않았다"
    # 기각되지 않은 나머지는 표시가 없어야 한다 — 전부에 붙으면 구분이 사라진다.
    others = [i for i in p.inferred if i.hypothesis_id != hid]
    assert all(i.rejected_at is None for i in others), "기각하지 않은 가설에 표시가 붙었다"


@pytest.mark.contract
def test_a_rejection_of_a_hypothesis_that_is_not_in_the_stream_keeps_the_absence(
    tmp_path: Path,
) -> None:
    """진술을 찾지 못하면 **`None` 이고 빈 문자열이 아니다** — 없는 것과 빈 것은 다르다."""
    p, _, _ = _one_rejection(tmp_path, hid="hyp-99", claim_hid="hyp-99")
    (r,) = p.rejected
    assert r.hypothesis_id == "hyp-99"
    assert r.statement is None, r.statement
    assert "부재" in render_markdown(p)


# ---------------------------------------------------------------------------
# 2. 두 값을 접지 않는가 (`spec.md` §0.3-3 / R2-12)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_claim_and_the_filtered_result_are_carried_side_by_side(tmp_path: Path) -> None:
    """모델이 **없는 id** 를 하나 더 댔다 — 하니스는 걸렀고 주장 원문은 남는다.

    접지 실패에서 실제로 났던 모양이다(`JUDGMENT.md` §2.2): 원인은 모델의 부주의가
    아니라 도구 응답이 id 를 나르지 않은 구조였다. 기각 쪽도 같은 자리를 갖는다.
    """
    events = _events(STALL3[0])
    real = next(str(e["observation_id"]) for e in events if e["type"] == "observation.recorded")
    p, _, _ = _one_rejection(tmp_path, refuted=[real], claimed=[real, "obs-does-not-exist"])
    (r,) = p.rejected
    assert r.refuted_by == (real,), r.refuted_by
    assert r.claimed_refutation == (real, "obs-does-not-exist"), r.claimed_refutation
    assert r.refuted_by != r.claimed_refutation, "두 값이 접혔다"
    blob = json.dumps(p.as_json(), ensure_ascii=False)
    assert "obs-does-not-exist" in blob, "모델의 주장 원문이 패킷에서 사라졌다"


@pytest.mark.contract
def test_a_rejection_with_no_tool_call_says_not_found_not_empty(tmp_path: Path) -> None:
    """호출문을 찾지 못하면 `None` 이다 — **빈 튜플과 다른 값이다.**

    빈 튜플은 "모델이 아무것도 대지 않았다"이고 `None` 은 "주장 원문을 스트림에서 찾지
    못했다"이다. 접으면 거짓 관측을 기록한다.
    """
    p, _, _ = _one_rejection(tmp_path, with_request=False)
    (r,) = p.rejected
    assert r.claimed_refutation is None, r.claimed_refutation
    assert "찾지 못했다" in render_markdown(p)


# ---------------------------------------------------------------------------
# 3. `S8.3` — 채워진 절도 밖으로 나가는 표면이다
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_an_answer_inside_a_reason_code_is_scrubbed(tmp_path: Path) -> None:
    """**기존 시험을 약화시키지 않는다 — 새로 채운 절에도 같은 이빨을 건다.**"""
    src = STALL3[0]
    events = _events(src)
    rec = next(e for e in events if e["type"] == "hypothesis.recorded")
    hid = str(rec["hypothesis_id"])
    answer = "kisia{synthetic-rejected-answer}"
    events = _insert_before_finish(
        events,
        [
            {"type": "candidate.produced", "value": answer, "derived_from": [], "method": "x"},
            _reject_event(hid, [], reason=f"refuted because the flag is {answer}"),
        ],
    )
    p = compile_packet(load_stream(_rewrite(tmp_path, events)))
    assert len(p.rejected) == 1
    blob = render_markdown(p) + json.dumps(p.as_json(), ensure_ascii=False)
    assert answer not in blob, "기각 사유를 타고 정답이 밖으로 나갔다"
    assert p.redactions, "지웠는데 지운 사실을 남기지 않았다"
    assert any("rejected[" in r.where for r in p.redactions), [r.where for r in p.redactions]
    # 해시 대상에도 없어야 한다.
    assert answer not in json.dumps(p.content_json(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# 4. 절이 차면 "0건" 주석이 사라지는가
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_zero_note_disappears_when_the_section_is_filled(tmp_path: Path) -> None:
    """빈 절의 주석이 채워진 절에도 남으면 **패킷이 거짓을 적는다.**"""
    empty = compile_packet(load_stream(STALL3[0]))
    assert any("`hypothesis.rejected` 가 0건이다" in n for n in empty.notes), empty.notes

    p, _, _ = _one_rejection(tmp_path)
    assert not any("`hypothesis.rejected` 가 0건이다" in n for n in p.notes), p.notes
    md = render_markdown(p)
    assert "0건이다. `0` 이고 `재지 못함` 이 아니다" not in md
    assert "## REJECTED — 기각된 가설" in md


@pytest.mark.contract
def test_two_rejections_are_two_and_not_folded(tmp_path: Path) -> None:
    """가설 둘을 각각 기각한다 — 절이 하나로 접히지 않는지."""
    events = _events(STALL3[0])
    recs = [e for e in events if e["type"] == "hypothesis.recorded"]
    if len(recs) < 2:
        # 바탕이 1건이면 하나를 더 지어 얹는다. **전제를 조용히 넘기지 않는다.**
        recs = [
            *recs,
            {
                "type": "hypothesis.recorded",
                "hypothesis_id": "hyp-90",
                "statement": "두 번째 가설",
                "confidence": 0.3,
                "supported_by": [],
                "attempt_family": "b",
                "turn": 4,
            },
        ]
        events = _insert_before_finish(events, [recs[-1]])
    hids = [str(r["hypothesis_id"]) for r in recs[:2]]
    events = _insert_before_finish(events, [_reject_event(h, []) for h in hids])
    p = compile_packet(load_stream(_rewrite(tmp_path, events)))
    assert [r.hypothesis_id for r in p.rejected] == hids, p.rejected
    assert len({r.seq for r in p.rejected}) == 2, "두 기각이 같은 seq 다"
    for h in hids:
        (i,) = [x for x in p.inferred if x.hypothesis_id == h]
        assert i.rejected_at is not None, f"{h} 에 기각 표시가 없다"


# ---------------------------------------------------------------------------
# 5. 채워진 절이 해시에 들어가는가 (`O-48` 과 맞물리는 자리)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_filled_section_changes_the_content_hash(tmp_path: Path) -> None:
    """기각을 얹으면 content hash 가 달라져야 한다 — 절이 해시 밖이면 안 된다."""
    before = compile_packet(load_stream(STALL3[0])).content_hash()
    p, _, _ = _one_rejection(tmp_path)
    assert p.content_hash() != before
