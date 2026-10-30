#!/usr/bin/env python3
"""매니페스트를 봉인한다 — `manifest.src.json` + 실제 `input/` -> `manifest.json`.

S1의 술어가 "`/input`의 모든 파일이 `files[]`에 sha256과 바이트 수로 나열된다"이므로,
매니페스트의 `inputs[]`는 손으로 쓰지 않고 디스크에서 읽어 채운다. 손으로 쓰면 입력물이
바뀌었을 때 조용히 어긋나고, 그 어긋남은 S1 FAIL과 구분되지 않는다.

`challenge_manifest_sha256`은 이 파일이 만든 `manifest.json` 바이트열의 sha256이며,
드라이버가 `attempt.started`의 통제 블록에 그대로 싣는다.

    python3 seal.py <fixture_dir>
"""
import hashlib
import json
import pathlib
import sys


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    fixture = pathlib.Path(sys.argv[1]).resolve()
    src = json.loads((fixture / "manifest.src.json").read_text(encoding="utf-8"))

    indir = fixture / "input"
    files = []
    for p in sorted(indir.rglob("*")):
        if p.is_file():
            files.append(
                {
                    "path": str(p.relative_to(indir)).replace("\\", "/"),
                    "sha256": sha256_file(p),
                    "bytes": p.stat().st_size,
                }
            )
    src["inputs"] = files

    # nyuctf challenge.json 의 files[] 는 아카이브 이름 목록이다. 같은 출처에서 채운다.
    if "nyuctf" in src:
        src["nyuctf"]["challenge_json"]["files"] = [f["path"] for f in files]

    out = json.dumps(src, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    (fixture / "manifest.json").write_text(out, encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest": str(fixture / "manifest.json"),
                "challenge_manifest_sha256": hashlib.sha256(out.encode()).hexdigest(),
                "inputs": len(files),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
