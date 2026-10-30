"""챌린지 픽스처 — 스트림이 해시로 지목하는 판정 입력.

`MANIFEST.md` 가 정한 `kisia.fixture/1` 스키마를 읽는다. 검사기가 이 파일을
필요로 하는 이유는 `kisia/checker/__init__.py` 머리말에 있다.

**해시를 대조하지 않으면 읽지 않는다.** `attempt.started.challenge_manifest_sha256`
과 실제 `manifest.json` 의 sha256 이 다르면 그 픽스처는 이 스트림의 것이 아니고,
그것으로 내린 판정은 무엇을 잰 것인지 정의되지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kisia.checker.grounding import (
    DEFAULT_CONNECTORS,
    DEFAULT_MAX_SEGMENTS,
    DEFAULT_MIN_GROUNDED_SEGMENT_LEN,
)


class FixtureError(ValueError):
    """픽스처를 읽을 수 없거나 스트림이 지목한 것과 다르다."""


@dataclass(frozen=True)
class Fixture:
    root: Path
    manifest: dict[str, Any]
    manifest_sha256: str
    answer: dict[str, Any] | None

    # -- MANIFEST.md §2.1 -----------------------------------------------
    @property
    def challenge_id(self) -> str:
        return str(self.manifest.get("challenge_id", ""))

    @property
    def type(self) -> str:
        """유형 A/B/C — `spec.md` §5 하중표의 행을 고른다."""
        return str(self.manifest.get("type", ""))

    # -- MANIFEST.md §2.2 -----------------------------------------------
    @property
    def flag_format(self) -> str:
        return str(self.manifest.get("flag_format", ""))

    @property
    def connectors(self) -> tuple[str, ...]:
        raw = self.manifest.get("connectors")
        if isinstance(raw, list) and raw:
            return tuple(str(c) for c in raw)
        return DEFAULT_CONNECTORS

    @property
    def min_grounded_segment_len(self) -> int:
        raw = self.manifest.get("min_grounded_segment_len")
        return int(raw) if isinstance(raw, int) else DEFAULT_MIN_GROUNDED_SEGMENT_LEN

    @property
    def max_segments(self) -> int:
        raw = self.manifest.get("max_segments")
        return int(raw) if isinstance(raw, int) else DEFAULT_MAX_SEGMENTS

    # -- MANIFEST.md §2.3 -----------------------------------------------
    @property
    def flag(self) -> str | None:
        return str(self.answer["flag"]) if self.answer and "flag" in self.answer else None

    @property
    def parts(self) -> dict[str, str]:
        """`{part_id: 문자열}` — S8.2의 `part_hits` 가 검색하는 **유일한** 근거."""
        if not self.answer:
            return {}
        raw = self.answer.get("parts")
        return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}

    # -- MANIFEST.md §2.4 / §2.6 ---------------------------------------
    @property
    def inputs(self) -> list[dict[str, Any]]:
        raw = self.manifest.get("inputs")
        return [dict(x) for x in raw] if isinstance(raw, list) else []

    @property
    def display_limit_bytes(self) -> int | None:
        raw = self.manifest.get("display_limit_bytes")
        return int(raw) if isinstance(raw, int) else None

    @property
    def declared_targets(self) -> list[str]:
        ws = self.manifest.get("workspace")
        if isinstance(ws, dict):
            raw = ws.get("declared_targets")
            if isinstance(raw, list):
                return [str(t) for t in raw]
        return []


def load_fixture(root: Path, *, expect_sha256: str | None = None) -> Fixture:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FixtureError(f"{root}: manifest.json 이 없다")
    raw = manifest_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()

    if expect_sha256 is not None:
        want = expect_sha256.removeprefix("sha256:").strip().lower()
        if want and want != digest:
            raise FixtureError(
                f"{manifest_path}: 스트림이 지목한 매니페스트가 아니다. "
                f"스트림 {want} != 실제 {digest}"
            )

    manifest = json.loads(raw.decode("utf-8"))
    answer = _load_answer(root, manifest)
    return Fixture(root=root, manifest=manifest, manifest_sha256=digest, answer=answer)


def _load_answer(root: Path, manifest: dict[str, Any]) -> dict[str, Any] | None:
    block = manifest.get("answer")
    location = block.get("location") if isinstance(block, dict) else None
    if not isinstance(location, str):
        return None
    path = root / location
    if not path.is_file():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return dict(loaded) if isinstance(loaded, dict) else None


def resolve_by_sha256(roots: list[Path], manifest_sha256: str) -> Fixture | None:
    """여러 후보 디렉터리에서 스트림이 지목한 매니페스트를 찾는다."""
    want = manifest_sha256.removeprefix("sha256:").strip().lower()
    for root in roots:
        candidate = root / "manifest.json"
        if not candidate.is_file():
            continue
        if hashlib.sha256(candidate.read_bytes()).hexdigest() == want:
            return load_fixture(root, expect_sha256=want)
    return None
