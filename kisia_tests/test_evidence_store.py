"""evidence store — 보관 계약의 시험.

**단위 시험이 통과한다는 사실은 아무것도 증명하지 않는다** (`CLAUDE.md` §6.1-3).
여기서 증명하는 것은 좁다: 바이트가 그대로 앉고, 대장이 그것을 되읽고, 경로가
`PATH_SCOPE.md` §3.7 을 어기지 않고, 전사본 이동이 확인 뒤에만 원본을 지운다는 것.
**어떤 seam 판정도 이 파일로 인용할 수 없다.**
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from kisia.evidence import EvidenceError, EvidenceStore

EVIDENCE = Path(__file__).resolve().parents[1] / "kisia" / "evidence"


@pytest.mark.unit
def test_put_records_bytes_and_hash(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    data = b'{"seq": 1}\n'
    rec = store.put("ch-01", "stream", "ch-01.jsonl", data)

    assert rec.sha256 == hashlib.sha256(data).hexdigest()
    assert rec.bytes == len(data)
    assert rec.moved_from is None
    assert (tmp_path / rec.path).read_bytes() == data
    assert store.records("ch-01") == [rec]


@pytest.mark.unit
def test_records_is_empty_for_an_unknown_attempt(tmp_path: Path) -> None:
    """빈 목록은 "산출물 0건"이고 "그런 attempt 가 없다"가 아니다 — 머리말 그대로."""
    assert EvidenceStore(tmp_path).records("never-ran") == []


@pytest.mark.unit
def test_escalation_packet_sits_where_path_scope_says(tmp_path: Path) -> None:
    """`PATH_SCOPE.md` §3.7: `<루트>/escalation/<attempt_id>/packet.json`."""
    store = EvidenceStore(tmp_path)
    rec = store.put("ch-01", "escalation_packet", "packet.json", b"{}")
    assert rec.path == "escalation/ch-01/packet.json"
    assert (tmp_path / "escalation" / "ch-01" / "packet.json").is_file()
    # 대장은 attempt 아래 하나뿐이다 — 산출물이 두 트리에 나뉘어도 한 번에 읽힌다.
    assert [r.role for r in store.records("ch-01")] == ["escalation_packet"]


@pytest.mark.unit
def test_escalation_directory_refuses_other_names(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    with pytest.raises(EvidenceError, match="PATH_SCOPE"):
        store.put("ch-01", "escalation_packet", "notes.json", b"{}")


@pytest.mark.unit
def test_unknown_role_is_refused(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    with pytest.raises(EvidenceError, match="role"):
        store.put("ch-01", "screenshot", "a.png", b"")


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["../escape", "a/b", ".hidden", ""])
def test_path_traversal_is_refused(tmp_path: Path, bad: str) -> None:
    store = EvidenceStore(tmp_path)
    with pytest.raises(EvidenceError):
        store.put(bad, "stream", "s.jsonl", b"x")
    with pytest.raises(EvidenceError):
        store.put("ch-01", "stream", bad, b"x")


@pytest.mark.unit
def test_overwrite_is_refused(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    store.put("ch-01", "stream", "s.jsonl", b"first")
    with pytest.raises(EvidenceError, match="덮어쓰지"):
        store.put("ch-01", "stream", "s.jsonl", b"second")
    assert (tmp_path / "attempts" / "ch-01" / "stream" / "s.jsonl").read_bytes() == b"first"


@pytest.mark.unit
def test_ingest_copies_and_leaves_the_source(tmp_path: Path) -> None:
    src = tmp_path / "judgment.json"
    src.write_bytes(b'{"verdict": "PASS"}')
    store = EvidenceStore(tmp_path / "store")

    rec = store.ingest("ch-01", "judgment", src)

    assert src.is_file(), "ingest 는 복사다 — 원본을 지우지 않는다"
    assert rec.moved_from is None
    assert (store.root / rec.path).read_bytes() == src.read_bytes()


@pytest.mark.unit
def test_ingest_transcript_moves_and_records_where_it_came_from(tmp_path: Path) -> None:
    """`O-47` — 전사본은 평문으로 solver 의 홈에 남는다. 회수는 이동이다."""
    home = tmp_path / "home" / "ccworker" / ".claude" / "projects" / "ns"
    home.mkdir(parents=True)
    src = home / "session-01.jsonl"
    payload = b'{"role":"assistant","content":"challenge content"}\n'
    src.write_bytes(payload)
    store = EvidenceStore(tmp_path / "store")

    rec = store.ingest_transcript("ch-01", src)

    assert not src.exists(), "원본이 남으면 챌린지 자료의 두 번째 사본이 된다"
    assert rec.moved_from == str(src)
    assert (store.root / rec.path).read_bytes() == payload
    # 대장에도 이동 사실이 남는다 — 되읽어서 확인한다.
    assert store.records("ch-01")[0].moved_from == str(src)


@pytest.mark.unit
def test_ingest_of_a_missing_file_is_refused(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path / "store")
    with pytest.raises(EvidenceError, match="없다"):
        store.ingest_transcript("ch-01", tmp_path / "nope.jsonl")


# ---------------------------------------------------------------------------
# 경계 — `kisia.evidence` 는 `kisia.runtime` 을 모른다
# ---------------------------------------------------------------------------


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
def test_evidence_imports_only_stdlib_and_itself() -> None:
    """보관된 증거는 다른 기계에서 열려야 한다 — 검사기에 걸린 것과 같은 성질
    (`PATH_SCOPE.md` §4.3, S9.5). runtime 을 import 하면 그 성질이 docker·모델
    설치에 묶인다."""
    outside: list[str] = []
    for py in sorted(EVIDENCE.rglob("*.py")):
        for name in _imports(py):
            root = name.split(".")[0]
            if root in sys.stdlib_module_names:
                continue
            if name == "kisia.evidence" or name.startswith("kisia.evidence."):
                continue
            outside.append(f"{py.name}: {name}")
    assert not outside, f"evidence store 가 밖을 import 한다: {outside}"


@pytest.mark.unit
def test_importing_evidence_does_not_pull_runtime() -> None:
    """AST 만으로는 부족하다 — 실제로 import 해 보고 무엇이 딸려 오는지 센다.
    별도 프로세스에서 재는 이유는 다른 시험이 이미 runtime 을 올려 두었을 수 있어서다."""
    code = (
        "import sys, kisia.evidence; "
        "print([m for m in sys.modules if m.startswith('kisia.runtime')])"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        check=True,
        cwd=str(EVIDENCE.parents[1]),
    )
    assert proc.stdout.decode().strip() == "[]", proc.stdout.decode()
