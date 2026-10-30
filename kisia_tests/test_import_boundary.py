"""경계 테스트 — `kisia.checker` 는 스트림에 대한 순수 함수다.

`spec.md` S9.5(P-S9-a)가 요구하는 성질이고, `PATH_SCOPE.md` §4.3이 재빌드의 첫
구간을 호스트 없이 가능하게 만드는 것과 같은 성질이다. 검사기가 조립기를 import
하면 그 성질이 조립기 버전에 묶인다.

`vendor/` 의 심볼 허용 목록 테스트(`SEAM_IMPLEMENTATION_MAP.md` §3.1)와 같은 장치이고,
같은 이유로 존재한다 — **경계는 테스트로 강제하지 않으면 샌다.**
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "kisia" / "checker"

#: 검사기가 import 해도 되는 최상위 모듈. 표준 라이브러리와 자기 자신뿐이다.
ALLOWED_ROOTS = {"kisia.checker"}
FORBIDDEN_ROOTS = {"kisia.runtime", "kisia.verifier"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


@pytest.mark.unit
def test_checker_does_not_import_runtime() -> None:
    offenders: list[str] = []
    for py in sorted(CHECKER.rglob("*.py")):
        for name in _imports(py):
            if any(name == r or name.startswith(r + ".") for r in FORBIDDEN_ROOTS):
                offenders.append(f"{py.name}: {name}")
    assert not offenders, (
        "검사기가 runtime 을 import 한다 — 순수 함수가 아니게 된다: " + str(offenders)
    )


@pytest.mark.unit
def test_checker_imports_only_stdlib_and_itself() -> None:
    third_party: list[str] = []
    for py in sorted(CHECKER.rglob("*.py")):
        for name in _imports(py):
            root = name.split(".")[0]
            if root in sys.stdlib_module_names:
                continue
            if any(name == a or name.startswith(a + ".") for a in ALLOWED_ROOTS):
                continue
            third_party.append(f"{py.name}: {name}")
    assert not third_party, (
        "검사기는 표준 라이브러리만 쓴다 — 다른 기계로 옮겨 재계산할 수 있어야 한다 "
        f"(S9.5): {third_party}"
    )


@pytest.mark.unit
def test_importing_checker_does_not_pull_runtime() -> None:
    for mod in [m for m in sys.modules if m.startswith("kisia.")]:
        del sys.modules[mod]
    import kisia.checker.judge  # noqa: F401

    pulled = sorted(m for m in sys.modules if m.startswith("kisia.runtime"))
    assert not pulled, f"검사기를 import 했더니 runtime 이 딸려 왔다: {pulled}"
