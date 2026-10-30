"""escalation 패킷의 content hash — **두 기계가 같은 값을 내는가** (`O-48` / S9.5).

프로덕션-3 트랙 P-D, 2026-08-09.

---

**무엇이 났었나.** `Packet.as_json()` 이 `stream`(= `str(stream.path)`)을 담고, 그것은
작업 디렉터리와 경로 구분자를 담으므로 기계마다 다르다. 객체 **전체**에 해시를 걸면 같은
attempt 가 기계마다 다른 해시를 얻고, `spec.md` §9 **S9.5** 가 두 기계를 대조하라고 한
자리가 성립하지 않는다.

**반증 관측을 실제로 수행했다** (`CLAUDE.md` §5). 같은 바이트를 서로 다른 두 경로에 두고
컴파일해 정규 JSON 의 sha256 을 쟀다 — 실측 스트림 **8/8 에서 해시가 갈렸고, 갈린 키는
`stream` 하나뿐**이었다. 가설이 확인됐고, 확인된 뒤에 고쳤다.

---

**이 파일이 재는 것 — 그리고 왜 하나로는 부족한가.**

"두 경로가 같은 해시를 낸다"만 재면 **상수를 반환하는 해시도 통과한다.** 그러면 `O-48`
은 닫힌 것이 아니라 안 보이게 된다. 그래서 셋을 함께 건다:

1. **안정성** — 경로가 달라도 같다 (`O-48` 이 난 자리).
2. **비공허성** — 내용이 달라지면 해시도 달라진다. 이것이 없으면 1번이 공허하다.
3. **키 대조** — `as_json()` 에만 필드가 늘면 해시 밖으로 샌다. 그 순간을 잡는다.

`S8.3`(정답이 밖으로 나가는 표면에 실리지 않는다)과 `D-63`(세 갈래)은 `test_escalation.py`
가 잠그고 **이 파일이 그것을 약화시키지 않는다** — 여기서도 다시 확인한다.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import pytest

from kisia.checker.model import load_stream
from kisia.escalation import compile_packet, render_markdown
from kisia.escalation.model import Inference, Packet, Redaction, Rejection

#: 흔들기용 — 실측 스트림에 없는 절을 채워 넣는다. **무동작 흔들기를 막기 위한 것이고**
#: 실측을 흉내 내려는 것이 아니다.
_AN_INFERENCE = Inference(
    seq=99,
    hypothesis_id="hyp-shake",
    statement="흔들기용 가설",
    confidence=0.5,
    supported_by=(),
    claimed_support=None,
    turn=1,
)
_A_REJECTION = Rejection(
    seq=98,
    hypothesis_id="hyp-shake",
    refuted_by=(),
    claimed_refutation=None,
    reason_code="흔들기용 사유",
    turn=1,
)
_A_REDACTION = Redaction(where="confirmed[obs-shake].shown", reason="흔들기용", count=1)

ROOT = Path(__file__).resolve().parents[1]
P1 = ROOT / "kisia_tests" / "data" / "streams" / "2026-08-09-p1-publisher-agentc"
ALL_STALL = sorted(
    [
        *(P1 / "out-b-stall").glob("*.jsonl"),
        *(P1 / "out-b-stall2").glob("*.jsonl"),
        *(P1 / "out-b-stall3").glob("*.jsonl"),
    ]
)


def _packet(path: Path) -> Packet:
    return compile_packet(load_stream(path))


def _at(tmp_path: Path, src: Path, where: str) -> Packet:
    """같은 바이트를 `where` 라는 다른 자리에 두고 컴파일한다 — **두 기계의 흉내**다."""
    d = tmp_path / where
    d.mkdir(parents=True, exist_ok=True)
    dst = d / src.name
    shutil.copyfile(src, dst)
    assert dst.read_bytes() == src.read_bytes(), "입력 바이트가 같아야 관측이 성립한다"
    return _packet(dst)


# ---------------------------------------------------------------------------
# 0. 전제 — 입력이 실제로 그 모양인가
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_measured_inputs_are_what_this_file_assumes() -> None:
    assert len(ALL_STALL) == 8, ALL_STALL


# ---------------------------------------------------------------------------
# 1. 안정성 — `O-48` 이 난 자리
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_content_hash_is_the_same_from_two_different_paths(tmp_path: Path) -> None:
    """**같은 스트림이 다른 경로에 있어도 같은 해시.** 고치기 전에는 8/8 이 갈렸다.

    S9.5 가 요구하는 것이 이것이다 — 스트림을 다른 기계로 옮겨 재계산해 같은 값이 나온다.
    """
    for src in ALL_STALL:
        a = _at(tmp_path, src, "machine-A/runs")
        b = _at(tmp_path, src, "wholly-different-root-B")
        assert a.content_hash() == b.content_hash(), (
            f"{src.name}: 경로가 다르다고 해시가 갈린다 — O-48 이 다시 났다"
        )


@pytest.mark.contract
def test_the_stream_path_is_the_only_thing_that_differs_between_the_two(tmp_path: Path) -> None:
    """**갈리는 키가 `stream` 하나뿐임을 잠근다.**

    실측이 그랬고(8/8), 그 사실 위에 `content_json()` 이 서 있다. 둘째 필드가 기계마다
    달라지기 시작하면 `content_json()` 에서 `stream` 만 빼는 것으로는 부족해지고, **이
    시험이 그 순간에 깨져야 한다.**
    """
    for src in ALL_STALL:
        a = _at(tmp_path, src, "machine-A/runs").as_json()
        b = _at(tmp_path, src, "wholly-different-root-B").as_json()
        differ = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        assert differ == ["stream"], f"{src.name}: 기계마다 다른 키가 더 있다 — {differ}"


@pytest.mark.contract
def test_the_hash_survives_the_windows_and_posix_spelling_of_one_path() -> None:
    """**OS 가 다르면 같은 논리 경로가 다른 문자열이 된다.** S9.5 의 두 기계는 Ubuntu 와
    Windows 11 이다(R3-8) — 상대 경로로 맞춰도 구분자에서 갈린다.

    실측: `PurePosixPath('out/a.jsonl')` != `PureWindowsPath('out/a.jsonl')`.
    """
    posix = str(PurePosixPath("out/b-stall3/p1bs3-ok-01.jsonl"))
    windows = str(PureWindowsPath("out/b-stall3/p1bs3-ok-01.jsonl"))
    assert posix != windows, "이 시험의 전제가 깨졌다 — 두 철자가 같아졌다"

    base = _packet(ALL_STALL[0])
    assert replace(base, stream_path=posix).content_hash() == (
        replace(base, stream_path=windows).content_hash()
    ), "경로 구분자 하나로 해시가 갈린다"


# ---------------------------------------------------------------------------
# 2. 비공허성 — **이것이 없으면 1번이 공허하다**
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_hash_is_not_a_constant() -> None:
    """서로 다른 8 스트림이 서로 다른 해시를 내야 한다.

    상수를 반환하는 `content_hash()` 도 안정성 시험은 전부 통과한다. **그러면 `O-48` 은
    닫힌 것이 아니라 안 보이게 된 것이다.**
    """
    hashes = {src.name: _packet(src).content_hash() for src in ALL_STALL}
    assert len(set(hashes.values())) == len(hashes), f"서로 다른 스트림이 같은 해시다: {hashes}"


@pytest.mark.contract
def test_changing_the_content_changes_the_hash() -> None:
    """`stream` **말고** 무엇이 바뀌든 해시가 따라 바뀐다.

    필드마다 하나씩 흔든다 — 한 필드만 재면 나머지가 해시 밖에 있어도 통과한다.

    **흔들기가 실제로 값을 바꿨는지를 먼저 확인한다.** 처음 이 시험을 `out-b-stall`
    (가설 0건) 위에 세웠더니 `inferred[:-1]` 이 빈 튜플을 빈 튜플로 바꾸는 무동작이었고,
    "해시가 안 바뀐다"는 실패가 났다. **그 실패는 코드가 아니라 시험의 결함이었다** —
    무동작 흔들기는 아무것도 증명하지 않으면서 통과할 수 있다. 아래 `changed` 가드가
    그것을 구조적으로 막는다.
    """
    base = _packet(ALL_STALL[0])
    before = base.content_hash()
    shaken: list[tuple[str, Packet]] = [
        ("run_id", replace(base, run_id=base.run_id + "-x")),
        ("attempt_id", replace(base, attempt_id=base.attempt_id + "-x")),
        ("outcome", replace(base, outcome=base.outcome + "-x")),
        ("reason", replace(base, reason=(base.reason or "") + "-다른 사유")),
        ("attempt_family", replace(base, attempt_family="different-family")),
        ("control", replace(base, control={**base.control, "challenge_id": "other"})),
        ("stalls", replace(base, stalls=())),
        ("confirmed", replace(base, confirmed=())),
        ("inferred", replace(base, inferred=(_AN_INFERENCE,))),
        ("rejected", replace(base, rejected=(_A_REJECTION,))),
        ("not_promoted", replace(base, not_promoted=(*base.not_promoted, "obs-zzz"))),
        ("redactions", replace(base, redactions=(_A_REDACTION,))),
        ("export_blockers", replace(base, export_blockers=("새 사유",))),
        ("notes", replace(base, notes=("새 주석",))),
        ("reader_notes", replace(base, reader_notes=("새 판독 주석",))),
    ]
    for field_name, p in shaken:
        changed = getattr(p, field_name) != getattr(base, field_name)
        assert changed, f"{field_name}: 흔들기가 무동작이다 — 이 시험이 공허해진다"
        assert p.content_hash() != before, f"{field_name} 를 바꿨는데 해시가 그대로다 — 해시 밖이다"
    assert {name for name, _ in shaken} == set(base.content_json()) - {"grounding", "stalled"}, (
        "흔들지 않은 필드가 `content_json()` 에 있다 — 그 필드는 해시 밖일 수 있다"
    )


@pytest.mark.contract
def test_the_hash_is_a_sha256_hexdigest() -> None:
    h = _packet(ALL_STALL[0]).content_hash()
    assert len(h) == 64, h
    assert set(h) <= set("0123456789abcdef"), h


# ---------------------------------------------------------------------------
# 3. 키 대조 — 새 필드가 해시 밖으로 새는 순간을 잡는다
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_as_json_is_content_json_plus_exactly_two_keys() -> None:
    """**둘의 이유가 서로 다르다 — 접지 않는다.**

    - `stream` : 기계마다 다르므로 해시 **밖**이다 (`O-48`).
    - `content_hash` : 자기 자신이므로 해시 **대상이 될 수 없다** (자기 참조).

    새 필드를 `as_json()` 에만 더하면 해시가 그것을 덮지 못한다. 그 순간 이 시험이 깨진다.
    """
    for src in ALL_STALL:
        p = _packet(src)
        extra = set(p.as_json()) - set(p.content_json())
        assert extra == {"stream", "content_hash"}, f"{src.name}: {sorted(extra)}"
        assert set(p.content_json()) <= set(p.as_json()), f"{src.name}: content_json 에만 있는 키"


@pytest.mark.contract
def test_the_hash_payload_does_not_carry_the_stream_path() -> None:
    """경로가 **값 안 어디에도** 남지 않았는지 — 키만 보면 놓친다."""
    for src in ALL_STALL:
        p = _packet(src)
        blob = json.dumps(p.content_json(), ensure_ascii=False)
        assert p.stream_path not in blob, f"{src.name}: 해시 대상에 경로가 남았다"
        assert src.name not in blob, f"{src.name}: 해시 대상에 파일 이름이 남았다"


@pytest.mark.contract
def test_the_packet_json_carries_the_hash_so_the_exporter_can_record_it() -> None:
    """`SAFETY_SCOPE.md` Escalation egress 조건 5 / `PATH_SCOPE.md` §3.7 —
    `export.log` 가 "목적지·해시·redaction 결과"를 적는다. 그 해시가 이 값이다.
    """
    for src in ALL_STALL:
        p = _packet(src)
        assert p.as_json()["content_hash"] == p.content_hash()


@pytest.mark.contract
def test_the_rendered_packet_shows_the_hash() -> None:
    """사람이 두 기계의 패킷을 눈으로 대조할 수 있어야 한다 — 마크다운에도 있다."""
    p = _packet(ALL_STALL[0])
    assert p.content_hash() in render_markdown(p)


# ---------------------------------------------------------------------------
# 4. 기존 잠금을 약화시키지 않았는가
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_hash_did_not_reopen_s8_3() -> None:
    """정답 문자열은 해시 대상에도 실리지 않는다 (`S8.3`)."""
    for src in ALL_STALL:
        events: list[dict[str, Any]] = [
            json.loads(x) for x in src.read_text(encoding="utf-8").splitlines() if x.strip()
        ]
        answers = [
            str(e.get("value", "")) for e in events if e.get("type") == "candidate.produced"
        ]
        blob = json.dumps(_packet(src).content_json(), ensure_ascii=False)
        for answer in answers:
            if answer:
                assert answer not in blob, f"{src.name}: 해시 대상에 정답이 실렸다"


@pytest.mark.contract
def test_the_hash_did_not_fold_the_three_way_grounding() -> None:
    """`D-63` — 접지됨 / 접지 안 됨 / 가설 없음 이 해시 대상 안에서도 셋이다."""
    seen = {_packet(src).content_json()["grounding"] for src in ALL_STALL}
    assert seen == {"grounded", "ungrounded", "no_hypothesis"}, seen
