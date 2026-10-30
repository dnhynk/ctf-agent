"""`vendor/` 경계 — `SEAM_IMPLEMENTATION_MAP.md` §3.1, `PATH_SCOPE.md` §3.1.

**경계는 테스트로 강제하지 않으면 샌다.** `utils.py` 는 우리가 REJECT 한 컨테이너 생성
코드(`_get_non_persistent_container`, `_get_container_mounts_list` — `:ro`·`--read-only`·
`--network` 가 없고 `ctfnet` 이 하드코딩된 바로 그 함수들)를 **같은 파일로** 들여온다.
허용 목록이 없으면 §6.3-2의 경계 침식이 정확히 거기서 일어난다.

여기 거는 것은 셋이다.

1. **바이트 대장** — vendored 5파일이 upstream `dc18a740` 의 blob 과 sha256 이 같다.
   `git diff vendor/` 가 패치 대장과 일치한다는 확인(§5-5)의 테스트 형태다. 패치를
   대장에 등재하지 않고 고치면 여기서 걸린다.
2. **심볼 허용 목록** — 제품 코드는 §3.1의 세 심볼 외 어떤 것도 import 하지 않는다.
3. **어댑터 하나** — vendored 코드에 닿는 제품 파일은 **하나뿐**이다
   (`FOUNDATION_DECISION.md` §6.2-2). 이 성질이 §6.5의 철수("`vendor/` 삭제 + 어댑터
   재작성")를 유한한 작업으로 유지한다.
"""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "swe_agent_dc18a740"
PRODUCT = ROOT / "kisia"

#: upstream `dc18a740faabd2fc625a9b018184dfc4a81cbc78` 의 blob sha256.
#: `git cat-file blob HEAD:<path>` 로 뽑았다 — 작업 트리가 아니다. `core.autocrlf=true`
#: 아래에서 작업 트리는 CRLF 로 부풀고(실측: LICENSE 1147 -> 1168 바이트), 그러면
#: upstream 과 다시 diff 할 수 없다. `.gitattributes` 의 `vendor/** -text` 가 짝이다.
UPSTREAM_BLOBS: dict[str, str] = {
    "sweagent/agent/interactive_commands.py":
        "b88da049f7211528079c1029585bd10da83447b6012ce8db4c8b5682eda0f68c",
    "sweagent/environment/utils.py":
        "fac9d12460d9c2a82dbe954795b6b1921612bd8c26821f9df4992777a5b46d12",
    "sweagent/utils/config.py":
        "6559f6c42a75e78ed4a7fcc50536ddc5f07d48fc037ed33e2b5ec9aab7ba53e8",
    "sweagent/utils/log.py":
        "d4cbb59c2ec8274d8e760a2eba375aa646cdfd1ceb0657733d34b5c83eddc309",
    "sweagent/__init__.py":
        "8bb63ccaf17f1ad7c73f52082cb1846cf1f134676174a762bcccd785bedc0008",
    "sweagent/utils/__init__.py":
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "config/commands/_connect.py":
        "a31f4a493344941fff380f45a3112f35469cd8510d6ef3b02039a84866cdcf69",
    "config/commands/server_connection.sh":
        "fd09560680017ab5991412c36fcbb932f5e281db0f7ad1c2163248a817c30907",
    # `LICENSE_MATRIX.md` §1 E 행이 독립적으로 확인한 값이다 (1147 B, 21행).
    "LICENSE": "7610ed3916f6674e34b78417894abd57ff538b3cfdda3085e3643d82acbaf31f",
}

#: **실적 패치 대장** — `REBUILD_LOG.md` 재빌드-2 §1.2 + 재빌드-5 가 정본이고 이것은 그
#: 기계 판독형이다. 값은 그 파일에 적용된 패치 **전부의** id 와 최종 sha256 이고, diff 는
#: `vendor/patches/<id>.diff` 에 하나씩 있다.
#:
#: **V-02~V-05 는 사소**(`spec.md` §6.1 R3-5 — "import 경로"), **V-06 은 구조**다.
#: 구조 패치 누계 **1**, 철수 임계치(전역 3, R3-6)까지 여유 2. 애매 판정을 구조로 세는
#: 계수에서는 3이고 그 경우 임계치에 닿는다 — 양쪽을 함께 적는 것이 §6.1 의 요구다.
PATCHED: dict[str, tuple[tuple[str, ...], str]] = {
    "sweagent/agent/interactive_commands.py": (
        ("V-02",), "4872d9cf018476d3cc2a9e9af5de5a54f2e221c0fbd4bae3de2d540fb5efd955"),
    "sweagent/environment/utils.py": (
        ("V-03", "V-06"), "5e97f07e7012c11d9e45c140871ce3bd394406e6213f40bf45018c8bcb002e5e"),
    "sweagent/utils/log.py": (
        ("V-04",), "fee2b400cec9ee200b03d4754c200d998500d02d42f7ba2d3c4d25e491f6b876"),
    "sweagent/utils/config.py": (
        ("V-05",), "d4c705982ff0706a7f1d9a1faf3d1cd61ec5596b65bc95130843c2c5fb16e43f"),
}

#: 구조 패치의 id — 계수의 근거다. `spec.md` §6.1: `PASS(patch n)` 의 `n` 이 이 수다.
STRUCTURAL: frozenset[str] = frozenset({"V-06"})

#: `SEAM_IMPLEMENTATION_MAP.md` §3.1 — 이 셋뿐이다. 늘리려면 계약을 고쳐야 하고,
#: 계약은 재빌드가 고치지 않는다 (`CLAUDE.md` §2-1).
ALLOWED_SYMBOLS: frozenset[str] = frozenset({
    "vendor.swe_agent_dc18a740.sweagent.agent.interactive_commands.InteractiveSession",
    "vendor.swe_agent_dc18a740.sweagent.environment.utils.get_interactive_session",
    "vendor.swe_agent_dc18a740.sweagent.environment.utils.read_with_timeout",
})

VENDOR_ROOT = "vendor"


@pytest.mark.unit
@pytest.mark.parametrize("relpath", sorted(UPSTREAM_BLOBS))
def test_vendored_file_matches_upstream_or_the_ledger(relpath: str) -> None:
    """**`git diff vendor/` 가 실적 대장과 일치한다**의 테스트 형태 (§5-5).

    파일은 upstream 바이트 그대로이거나, 대장에 등재된 패치 후의 값이거나, **둘 중
    하나여야 한다.** 등재 없이 고치면 여기서 걸린다 — 그것이 경계가 새는 유일한 방식이고,
    사람이 매번 diff 를 눈으로 대조하는 것에 기대지 않는다.
    """
    path = VENDOR / relpath
    assert path.is_file(), f"{relpath} 가 vendor/ 에 없다"
    got = hashlib.sha256(path.read_bytes()).hexdigest()

    if relpath in PATCHED:
        patch_ids, want = PATCHED[relpath]
        assert got == want, (
            f"{relpath} 가 대장의 {'+'.join(patch_ids)} 적용 결과와 다르다. 패치를 고쳤으면 "
            f"vendor/patches/<id>.diff 와 REBUILD_LOG 의 실적 대장을 함께 고친다."
        )
        for patch_id in patch_ids:
            assert (ROOT / "vendor" / "patches" / f"{patch_id}.diff").is_file(), (
                f"{patch_id} 의 diff 가 저장소에 없다 (§5-2)"
            )
        return

    assert got == UPSTREAM_BLOBS[relpath], (
        f"{relpath} 가 upstream 과 다른데 대장에 없다. vendored 원본은 수정 없이 "
        "들어오고, 고쳐야 하면 SEAM_IMPLEMENTATION_MAP §5 의 대장에 등재된 패치로만 한다. "
        "구조 패치 3개째에서 멈추고 보고한다 (R3-6)."
    )


@pytest.mark.unit
def test_the_ledger_is_a_subset_of_what_we_vendored() -> None:
    """대장이 반입하지 않은 파일을 가리키면 둘 중 하나가 틀린 것이다."""
    assert set(PATCHED) <= set(UPSTREAM_BLOBS)


@pytest.mark.contract
def test_structural_patch_count_is_below_the_retreat_threshold() -> None:
    """`SEAM_IMPLEMENTATION_MAP.md` §5-3 / R3-6 — **3개째에서 멈추고 보고한다.**

    임계치가 문서에만 있으면 조용히 넘어간다. 여기서 세고, 3에 닿으면 실패한다 —
    실패의 뜻은 "코드를 고쳐라"가 아니라 **"멈추고 운영자에게 보고하라"** 다.
    """
    applied = {pid for ids, _ in PATCHED.values() for pid in ids}
    unknown = STRUCTURAL - applied
    assert not unknown, f"구조로 분류됐는데 대장에 없는 패치: {sorted(unknown)}"
    assert len(STRUCTURAL) < 3, (
        f"구조 패치 누계 {len(STRUCTURAL)} — 3개째다. §6.5 의 철수 신호이고 "
        f"`CLAUDE.md` §2-5 대로 **멈추고 보고한다**: {sorted(STRUCTURAL)}"
    )


@pytest.mark.contract
def test_the_contract_file_list_and_this_ledger_agree() -> None:
    """`SEAM_IMPLEMENTATION_MAP.md` §3.1의 목록과 위 대장이 같은 아홉을 말하는가.

    **계약 문면과 그것을 강제하는 장치가 갈리는 것이 이 저장소가 실제로 겪은 결함이다** —
    O-3(두 계약 문서가 서로 다른 vendor 경로를 말했다)과 O-6(§3.1의 목록으로는 §3.1이
    선언한 허용 목록을 만족시킬 수 없었다) 둘 다 그 형태였고, 둘 다 **사람이 읽다가**
    발견됐다. 여기서 기계가 읽는다.

    깨지면 둘 중 하나다: (a) 계약이 개정됐는데 대장이 따라오지 않았다 — 대장을 고친다.
    (b) 대장이 계약에 없는 파일을 반입했다 — **멈추고 보고한다**(`CLAUDE.md` §2-1).
    """
    doc = (ROOT / "docs" / "spec" / "SEAM_IMPLEMENTATION_MAP.md").read_text(encoding="utf-8")
    try:
        section = doc.split("### 3.1 vendor하는 것")[1].split("### 3.1.a")[0]
    except IndexError:  # pragma: no cover - 문면이 통째로 바뀐 경우
        pytest.fail("§3.1 절을 찾지 못했다. 계약이 개정됐다면 이 테스트도 따라가야 한다.")

    listed = {m.group(1) for m in re.finditer(r"^\| `([^`]+\.(?:py|sh))` ", section, re.M)}
    if "`LICENSE`" in section:
        listed.add("LICENSE")

    assert listed == set(UPSTREAM_BLOBS), (
        "§3.1의 파일 목록과 이 파일의 대장이 다르다.\n"
        f"  계약에만: {sorted(listed - set(UPSTREAM_BLOBS))}\n"
        f"  대장에만: {sorted(set(UPSTREAM_BLOBS) - listed)}"
    )


@pytest.mark.unit
def test_vendor_pulls_no_third_party() -> None:
    """세 심볼을 import 해도 서드파티가 딸려 오지 않는다 — V-02~V-05 의 존재 이유다.

    반입 직후의 실측은 `ModuleNotFoundError: No module named 'simple_parsing'` /
    `'datasets'` 였다(`LICENSE_MATRIX.md` §5.4.2). 그 여덟 중 `datasets` 는 §3.2 가
    REJECT 한 nyuctf 결합 그 자체이므로, 이 성질이 무너지면 경계가 무너진 것이다.
    """
    import subprocess
    import sys

    # `-c` 는 cwd 를 sys.path 앞에 붙인다. cwd=ROOT 이므로 `vendor` 가 최상위로 보인다.
    probe = "\n".join((
        "import sys",
        "from vendor.swe_agent_dc18a740.sweagent.agent.interactive_commands"
        " import InteractiveSession",
        "from vendor.swe_agent_dc18a740.sweagent.environment.utils"
        " import get_interactive_session, read_with_timeout",
        "third = {'datasets','ghapi','git','unidiff','docker','simple_parsing','rich','config'}",
        "print(','.join(sorted({m.split('.')[0] for m in sys.modules} & third)))",
    ))
    out = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, cwd=ROOT, check=False
    )
    assert out.returncode == 0, f"세 심볼 import 가 실패한다:\n{out.stderr}"
    assert out.stdout.strip() == "", f"서드파티가 딸려 왔다: {out.stdout.strip()}"


def _vendor_imports(path: Path) -> list[tuple[str, int]]:
    """그 파일이 `vendor.` 에서 끌어오는 **완전 수식 이름**과 줄 번호."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(
                (a.name, node.lineno)
                for a in node.names
                if a.name == VENDOR_ROOT or a.name.startswith(VENDOR_ROOT + ".")
            )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level == 0 and (mod == VENDOR_ROOT or mod.startswith(VENDOR_ROOT + ".")):
                found.extend((f"{mod}.{a.name}", node.lineno) for a in node.names)
    return found


def _product_files() -> list[Path]:
    return sorted(PRODUCT.rglob("*.py"))


@pytest.mark.unit
def test_product_imports_only_the_three_allowed_symbols() -> None:
    offenders: list[str] = []
    for py in _product_files():
        for name, lineno in _vendor_imports(py):
            if name not in ALLOWED_SYMBOLS:
                offenders.append(f"{py.relative_to(ROOT)}:{lineno} {name}")
    assert not offenders, (
        "허용 목록 밖의 vendored 심볼을 import 한다 (SEAM_IMPLEMENTATION_MAP §3.1). "
        f"허용은 셋뿐이다: {sorted(ALLOWED_SYMBOLS)} / 위반: {offenders}"
    )


@pytest.mark.unit
def test_module_level_vendor_import_is_rejected() -> None:
    """`import vendor...` 형태는 심볼을 특정하지 못하므로 허용 목록을 무력화한다."""
    offenders = [
        f"{py.relative_to(ROOT)}:{lineno} import {name}"
        for py in _product_files()
        for name, lineno in _vendor_imports(py)
        if name == VENDOR_ROOT
        or (name.startswith(VENDOR_ROOT + ".") and name not in ALLOWED_SYMBOLS)
    ]
    assert not offenders, (
        "모듈 통째 import 는 어느 심볼을 쓰는지 기계적으로 알 수 없게 만든다. "
        f"`from ... import <심볼>` 로만 닿는다: {offenders}"
    )


@pytest.mark.unit
def test_only_one_product_file_touches_vendor() -> None:
    """`FOUNDATION_DECISION.md` §6.2-2 — 어댑터 **파일 하나**를 통해서만 접근한다."""
    touching = sorted(
        str(py.relative_to(ROOT)) for py in _product_files() if _vendor_imports(py)
    )
    assert len(touching) <= 1, (
        "vendored 코드에 닿는 제품 파일이 둘 이상이다. 철수 경로가 '어댑터 재작성'으로 "
        f"유지되려면 접점이 하나여야 한다 (§6.5): {touching}"
    )
