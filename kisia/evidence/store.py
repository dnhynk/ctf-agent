"""attempt 산출물의 보관. 머리말은 `kisia/evidence/__init__.py` 다."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

#: 보관하는 다섯. **여섯째를 지금 만들지 않는다** (`CLAUDE.md` §8) — orchestrator 의
#: 배정 기록(어느 rung·어느 라벨)은 `kisia.orchestrator` 가 메모리에 쥐고 있고,
#: 그것을 파일로 남기는 형태는 `CONTEST_ARCHITECTURE.md` §12(재시작·복구)가 정해질 때
#: 함께 정해진다. 지금 정하면 복구 모델 없이 직렬화 형식만 굳는다.
ROLES: frozenset[str] = frozenset(
    {
        #: S9 봉투 스트림 (`kisia.runtime.telemetry.envelope` 가 낸 jsonl).
        "stream",
        #: 검사기 판정 (`kisia.checker` 의 `--json`). **이 계층이 만들지 않는다.**
        "judgment",
        #: 라이트업 (`kisia.writeup`).
        "writeup",
        #: escalation 패킷 (`kisia.escalation`). 자리는 `PATH_SCOPE.md` §3.7 이 정한다.
        "escalation_packet",
        #: solver 가 디스크에 남긴 전사본. `O-47`.
        "transcript",
    }
)

#: `PATH_SCOPE.md` §3.7 이 이름으로 적은 둘. `export.log` 는 export 게이트의 것이므로
#: 이 계층은 쓰지 않지만, **경로를 아는 것과 쓰는 것은 다르므로** 이름은 여기 둔다 —
#: 다른 이름으로 escalation 디렉터리에 파일이 생기면 §3.7 이 정한 단일 경로가 흐려진다.
ESCALATION_NAMES: frozenset[str] = frozenset({"packet.json", "export.log"})

#: 경로 요소로 쓸 수 있는 이름. attempt_id 는 밖에서 오고(챌린지 id 에서 파생),
#: 파일 이름도 밖에서 온다. 둘 다 경로 구분자·`..` 를 담을 수 있으면 저장 루트 밖에
#: 쓸 수 있게 된다.
_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

_INDEX = "index.jsonl"


class EvidenceError(RuntimeError):
    """보관할 수 없다. **조용히 넘어가지 않는다.**"""


@dataclass(frozen=True)
class Record:
    """무엇이 어떤 바이트로 들어왔는가. 이것이 대장의 한 줄이다."""

    attempt_id: str
    role: str
    name: str
    #: 저장 루트 기준 상대 경로 (posix). 루트가 옮겨져도 대장이 따라간다.
    path: str
    sha256: str
    bytes: int
    #: 이동해 들어온 경우 원본이 어디에 있었는가. 복사면 `None`.
    #: **`None` 과 빈 문자열을 접지 않는다** — 전자는 복사, 후자는 값이 될 수 없다.
    moved_from: str | None = None


class EvidenceStore:
    """한 저장 루트를 소유한다. attempt 단위로 나눈다.

    ```
    <root>/attempts/<attempt_id>/index.jsonl        이 attempt 의 대장
    <root>/attempts/<attempt_id>/<role>/<name>      stream · judgment · writeup · transcript
    <root>/escalation/<attempt_id>/packet.json      PATH_SCOPE.md §3.7 이 정한 자리
    ```

    **덮어쓰지 않는다.** 같은 (attempt, role, name) 이 두 번 들어오면 죽는다. 앞의
    증거를 조용히 지우는 보관소는 증거를 나르지 않는다 — `CLAUDE.md` §6 의 "자기 보고는
    증거가 아니다" 와 같은 자리에서 오는 요구다.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    # -- 넣기 ----------------------------------------------------------------
    def put(self, attempt_id: str, role: str, name: str, data: bytes) -> Record:
        """바이트를 그대로 보관하고 대장에 한 줄 남긴다."""
        target = self.path_for(attempt_id, role, name)
        if target.exists():
            raise EvidenceError(
                f"이미 있다: {self._relative(target)} — 증거를 덮어쓰지 않는다"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        record = Record(
            attempt_id=attempt_id,
            role=role,
            name=name,
            path=self._relative(target),
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),
        )
        self._append(record)
        return record

    def ingest(self, attempt_id: str, role: str, src: Path, *, name: str | None = None) -> Record:
        """파일 하나를 **복사해** 보관한다. 원본은 그대로 둔다."""
        if not src.is_file():
            raise EvidenceError(f"보관할 파일이 없다: {src}")
        return self.put(attempt_id, role, name or src.name, src.read_bytes())

    def ingest_transcript(self, attempt_id: str, src: Path, *, name: str | None = None) -> Record:
        """전사본을 **옮긴다.** `O-47` 이 요구하는 형태다.

        solver 의 홈에 평문으로 남은 전사본은 챌린지 콘텐츠를 담을 수 있으므로 복사로는
        부족하다 — 원본이 남으면 그 계정의 홈이 챌린지 자료의 두 번째 사본이 된다.

        **해시를 확인한 뒤에만 지운다.** 확인 전에 지우면 옮기다 실패했을 때 증거가
        사라지고, 그 실패는 "전사본이 없었다"와 구분되지 않는다.
        """
        record = self.ingest(attempt_id, "transcript", src, name=name)
        stored = self.path_for(attempt_id, "transcript", record.name)
        if hashlib.sha256(stored.read_bytes()).hexdigest() != record.sha256:
            raise EvidenceError(f"옮긴 바이트가 원본과 다르다 — 원본을 지우지 않았다: {src}")
        src.unlink()
        if src.exists():  # pragma: no cover - unlink 가 성공하면 도달하지 않는다
            raise EvidenceError(f"원본이 지워지지 않았다: {src}")
        moved = replace(record, moved_from=str(src))
        self._rewrite_last(moved)
        return moved

    # -- 읽기 ----------------------------------------------------------------
    def records(self, attempt_id: str) -> list[Record]:
        """이 attempt 의 대장.

        **빈 목록은 "산출물이 0건"이지 "그런 attempt 가 없다"가 아니다.** 이 계층은
        둘을 가르지 못하고, 가르는 것은 orchestrator 가 쥔 attempt 목록이다
        (`CLAUDE.md` §6: "수행하지 못함"과 "0"을 접지 마라).
        """
        index = self._index_path(attempt_id)
        if not index.is_file():
            return []
        out: list[Record] = []
        for line in index.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(_record_from(json.loads(line)))
        return out

    def path_for(self, attempt_id: str, role: str, name: str) -> Path:
        """그 산출물이 앉을 자리. 파일이 있는지는 보지 않는다."""
        _check(attempt_id, "attempt_id")
        _check(name, "name")
        if role not in ROLES:
            raise EvidenceError(f"role 은 {sorted(ROLES)} 중 하나다: {role!r}")
        if role == "escalation_packet":
            if name not in ESCALATION_NAMES:
                raise EvidenceError(
                    f"escalation 디렉터리에는 {sorted(ESCALATION_NAMES)} 만 온다 "
                    f"(PATH_SCOPE.md §3.7): {name!r}"
                )
            return self.root / "escalation" / attempt_id / name
        return self.root / "attempts" / attempt_id / role / name

    # -- 내부 ----------------------------------------------------------------
    def _index_path(self, attempt_id: str) -> Path:
        _check(attempt_id, "attempt_id")
        return self.root / "attempts" / attempt_id / _INDEX

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _append(self, record: Record) -> None:
        index = self._index_path(record.attempt_id)
        index.parent.mkdir(parents=True, exist_ok=True)
        with index.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False, sort_keys=False) + "\n")

    def _rewrite_last(self, record: Record) -> None:
        """방금 쓴 줄을 갱신한다. `ingest_transcript` 의 `moved_from` 하나에만 쓴다 —
        원본을 지운 것은 `put` 이 끝난 **뒤**의 사실이므로 그때 적을 수 없었다."""
        index = self._index_path(record.attempt_id)
        lines = index.read_text(encoding="utf-8").splitlines()
        lines[-1] = json.dumps(asdict(record), ensure_ascii=False, sort_keys=False)
        index.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _record_from(raw: dict[str, Any]) -> Record:
    """대장 한 줄을 되읽는다. **필드를 이름으로 집는다** — `**raw` 로 풀면 대장에
    낯선 키가 섞였을 때 조용히 죽거나 조용히 통과한다."""
    moved = raw.get("moved_from")
    return Record(
        attempt_id=str(raw["attempt_id"]),
        role=str(raw["role"]),
        name=str(raw["name"]),
        path=str(raw["path"]),
        sha256=str(raw["sha256"]),
        bytes=int(raw["bytes"]),
        moved_from=None if moved is None else str(moved),
    )


def _check(value: str, what: str) -> None:
    if not _SAFE.match(value) or ".." in value:
        raise EvidenceError(
            f"{what} 로 쓸 수 없는 이름이다 — 경로 구분자와 '..' 는 저장 루트 밖을 "
            f"가리킬 수 있다: {value!r}"
        )
