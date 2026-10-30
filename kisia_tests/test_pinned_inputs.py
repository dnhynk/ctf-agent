"""스트림 밖 고정 입력 둘 — 개정 R5-2 / `spec.md` S9.4a.

검사기가 쓸 수 있는 스트림 밖 입력은 단가표와 챌린지 픽스처뿐이고, **각각을 스트림이
해시로 지목한다.** 픽스처 쪽(`challenge_manifest_sha256`)은 재빌드-1이 이미 대조하고
있었고(`REBUILD_LOG.md` D-2), 이 파일이 잠그는 것은 r5가 더한 단가표 쪽이다.

**대조에 실패하면 판정을 내지 않는다**(`TELEMETRY_SCHEMA.md` §2). "FAIL 을 낸다"가
아니라 "내지 않는다"이므로, 관문은 술어가 아니라 CLI 에 있고 그 스트림은 `void` 로
보고된다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kisia.checker.__main__ import main
from kisia.checker.pricing import matches_pin, pricing_sha256
from kisia.runtime.telemetry.control import REQUIRED_FIELDS, ControlBlock, ControlBlockError
from kisia_tests.conformance import build_set

ROOT = Path(__file__).resolve().parents[1]
PRICING = ROOT / "config" / "pricing.openai.yaml"


@pytest.mark.unit
def test_control_block_requires_the_pricing_pin() -> None:
    """지목이 없으면 조립기가 스트림을 열지 않는다 (`TELEMETRY_SCHEMA.md` §2)."""
    assert "pricing_sha256" in REQUIRED_FIELDS
    # r5 는 36항이었고, 개정 S-4 가 `provenance` 를 §2에 더해 37항이 됐다.
    # 프로덕션-3 이 `ADR-0003` §Consequences 의 라벨 셋을 더해 40항이 됐다.
    assert len(REQUIRED_FIELDS) == 40, (
        "r5 + 개정 S-4 + ADR-0003 라벨 3항 아래의 통제 블록은 40항이다"
    )
    assert "provenance" in REQUIRED_FIELDS

    from kisia_tests.conformance import _control

    values = dict(_control(attempt="t").values)
    del values["pricing_sha256"]
    with pytest.raises(ControlBlockError, match="pricing_sha256"):
        ControlBlock.build(values)


@pytest.mark.unit
def test_the_two_control_field_lists_agree() -> None:
    """**발행 쪽과 검사기 쪽이 같은 목록을 봐야 한다.**

    갈리면 두 방향으로 조용히 깨진다. 검사기 쪽이 더 크면 우리 조립기가 내는 스트림이
    전부 `FAIL(S9.1)` 이 되고, 발행 쪽이 더 크면 계약이 요구하는 항목을 검사기가 봐주게
    된다.

    **재빌드-6이 이 둘을 한 세션 안에서 갈랐다가 다시 붙였다.** `S-4` 가 `provenance` 를
    §2에 더했을 때 검사기 쪽에 그것을 넣으면 그 필드 이전에 발행된 유형 A·B 스트림
    10개가 전부 무효가 됐다. 골든 셋을 다시 돌려 해소했고(`O-23`), 그 경위 때문에 이
    테스트가 있다 — **다음에 §2에 항목이 더해지면 같은 일이 반복된다.**
    """
    from kisia.checker.predicates import CONTROL_FIELDS

    assert set(CONTROL_FIELDS) == set(REQUIRED_FIELDS)


@pytest.mark.unit
def test_matches_pin_accepts_both_spellings() -> None:
    digest = pricing_sha256(PRICING)
    assert matches_pin(digest, digest)
    assert matches_pin("sha256:" + digest.upper(), digest)
    assert not matches_pin("0" * 64, digest)


def _run(streams: list[Path], pricing: Path, capsys: pytest.CaptureFixture[str]) -> dict:
    rc = main([*(str(p) for p in streams), "--pricing", str(pricing), "--json"])
    # `--json` 은 stdout 의 **바이트 스트림**에 UTF-8 로 쓴다 (로케일 독립, S9.5).
    return {"rc": rc, **json.loads(capsys.readouterr().out)}


@pytest.mark.contract
def test_json_output_is_utf8_regardless_of_locale(tmp_path: Path) -> None:
    """기계 판독용 출력이 기계에 따라 달라지면 P-S9-a 를 행사할 수 없다.

    실측 2026-08-08: Windows 워크스테이션에서 `--json > file` 이 cp949 로 나가
    `UnicodeEncodeError` 로 죽거나 파일이 깨졌다. S9.5(R3-8)가 대조하라고 지목한 두
    기계 중 하나가 그 워크스테이션이다.
    """
    import subprocess
    import sys

    out = tmp_path / "j.json"
    with out.open("wb") as fh:
        rc = subprocess.run(
            [sys.executable, "-m", "kisia.checker", "--pricing", str(PRICING), "--json",
             *(str(p) for p in build_set(tmp_path)[:1])],
            stdout=fh, cwd=ROOT, check=False,
        ).returncode
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["streams"][0]["judgment_digest"]


@pytest.mark.contract
def test_matching_pin_is_judged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = _run(build_set(tmp_path)[:1], PRICING, capsys)
    assert out["void"] == []
    assert len(out["streams"]) == 1
    assert out["rc"] == 0


@pytest.mark.contract
def test_mismatched_pin_is_not_judged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """다른 단가표를 주면 **판정이 나오지 않는다.**

    주석 한 줄을 더한 사본이다 — `load_pricing` 은 주석을 건너뛰므로 **파싱 결과는
    같고 바이트만 다르다.** 그래서 이 시험은 "해시를 실제로 파일 바이트에 대고
    쟀는가"를 정확히 가른다.
    """
    tampered = tmp_path / "pricing.copy.yaml"
    tampered.write_bytes(PRICING.read_bytes() + "\n# 같은 표, 다른 바이트\n".encode())
    assert pricing_sha256(tampered) != pricing_sha256(PRICING)

    out = _run(build_set(tmp_path)[:1], tampered, capsys)
    assert out["streams"] == [], "어긋난 단가표로 판정을 내면 안 된다 (S9.4a)"
    assert len(out["void"]) == 1
    assert "S9.4a" in out["void"][0]["reason"]
    assert out["rc"] == 1


@pytest.mark.contract
def test_s9_4a_is_out_of_stream_and_moves_no_seam(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """S9.4a 는 검사기의 성질이지 스트림의 성질이 아니다 — S9.4 와 같은 자리다.

    따라서 `스트림 밖`이고 어떤 seam 판정도 움직이지 않는다(`spec.md` §6.2).
    """
    out = _run(build_set(tmp_path), PRICING, capsys)
    seen = 0
    for stream in out["streams"]:
        for seam in stream["seams"]:
            for r in seam["predicates"]:
                if r["predicate"] == "S9.4a":
                    seen += 1
                    assert r["verdict"] == "out_of_stream"
                    assert "단가표: 지목과 일치" in r["note"]
                    assert "픽스처: 지목과 일치" in r["note"]
    assert seen == len(out["streams"]) == 5

    assert all(s["seams"][-1]["verdict"] == "PASS" for s in out["streams"] if s["normal"])
