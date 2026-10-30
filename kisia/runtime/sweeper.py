"""S8.3 — `answer.sweep`. **runtime 이 내되 실행 주체가 내지 않는다** (r1 A-3, R3-10).

verifier 와 같은 이유로 별도 프로세스다: 스윕은 정답을 **알아야** 하는 유일한 연산이고,
그것을 드라이버 프로세스 안에서 하면 드라이버가 정답 문자열을 들고 있게 된다. 여기서는
정답이 들어오고 **개수만** 나간다.

    python3 -m kisia.runtime.sweeper --answer <answer.json> \
        --surface input_files=<dir> --surface artifacts=<dir> ...
    stdout: answer.sweep 의 필드 (surfaces / method / checked_by)

`part` 는 정답 파일 `parts` 의 **키**만 싣는다. 값 자체를 실으면 스트림 자신이 스윕
대상이 된다(`TELEMETRY_SCHEMA.md` §3.2.1).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CHECKED_BY = "kisia-sweeper@host(byte scan)"
METHOD = "raw byte substring count over materialised surfaces"


def _blobs(root: Path) -> list[bytes]:
    if root.is_file():
        return [root.read_bytes()]
    if not root.is_dir():
        return []
    return [p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()]


def _count(blobs: list[bytes], needle: str) -> int:
    raw = needle.encode("utf-8")
    return sum(b.count(raw) for b in blobs)


def sweep(answer_path: Path, surfaces: list[tuple[str, Path]]) -> dict[str, object]:
    answer = json.loads(answer_path.read_text(encoding="utf-8"))
    whole = str(answer["flag"])
    parts: dict[str, str] = {str(k): str(v) for k, v in dict(answer.get("parts", {})).items()}

    rows = []
    for name, path in surfaces:
        blobs = _blobs(path)
        rows.append(
            {
                "surface": name,
                "whole_hits": _count(blobs, whole),
                # **개수가 0 인 part 도 싣는다.** "0 건"과 "보지 않았다"는 다른 사실이고
                # 접으면 거짓 관측이 된다(`TELEMETRY_SCHEMA.md` §7.1).
                "part_hits": [
                    {"part": pid, "count": _count(blobs, text)}
                    for pid, text in sorted(parts.items())
                ],
            }
        )
    return {"surfaces": rows, "method": METHOD, "checked_by": CHECKED_BY}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kisia.runtime.sweeper")
    ap.add_argument("--answer", type=Path, required=True)
    ap.add_argument("--surface", action="append", default=[], metavar="NAME=PATH")
    args = ap.parse_args(argv)

    surfaces: list[tuple[str, Path]] = []
    for raw in args.surface:
        name, _, path = str(raw).partition("=")
        surfaces.append((name, Path(path)))

    print(json.dumps(sweep(args.answer, surfaces), ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
