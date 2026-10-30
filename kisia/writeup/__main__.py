"""라이트업 생성기 CLI.

    python -m kisia.writeup [옵션] <stream.jsonl> ...

옵션
    --out DIR          스트림마다 `<attempt_id>.md` 와 (있으면) `<attempt_id>.repro.sh`
                       를 쓴다. 생략하면 stdout 으로 첫 스트림만 낸다
    --sufficiency      `TELEMETRY_SCHEMA.md` §4.1 의 (a)~(e) 표만 낸다. 여러 스트림을
                       한 표로 모은다
    --json             기계 판독용 (충분성 + 재현 재료)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kisia.checker.model import StreamVoidError, load_stream
from kisia.writeup.model import Writeup
from kisia.writeup.project import project
from kisia.writeup.render import render_markdown


def _write_utf8(path: Path, text: str) -> None:
    """**UTF-8 바이트로 직접 쓴다.** 검사기 `__main__` 과 같은 이유다 — Windows
    워크스테이션의 기본 인코딩은 cp949 이고, S9.5 가 대조하라고 지목한 두 기계 중
    하나가 그 워크스테이션이다(R3-8). 문서가 기계에 따라 달라지면 안 된다.
    """
    path.write_bytes(text.encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kisia.writeup", add_help=True)
    ap.add_argument("streams", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--sufficiency", action="store_true")
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args(argv)

    writeups: list[Writeup] = []
    void: list[tuple[Path, str]] = []
    for path in args.streams:
        try:
            stream = load_stream(path)
        except StreamVoidError as exc:
            # S9.2 — 빈틈이 있으면 그 attempt 의 모든 판정이 무효다. 라이트업도
            # 내지 않는다: 무효인 스트림에서 만든 풀이 기록은 근거 없는 서사가 된다.
            void.append((path, str(exc)))
            continue
        writeups.append(project(stream))

    if args.as_json:
        payload = {
            "void": [{"stream": str(p), "reason": r} for p, r in void],
            "writeups": [
                {
                    "stream": w.stream_path,
                    "attempt_id": w.attempt_id,
                    "challenge_id": w.challenge_id,
                    "outcome": w.outcome,
                    "steps": len(w.steps),
                    "solve_observations": len(w.solve_observations),
                    "probe_observations": len(w.probe_observations),
                    "sufficiency": w.sufficiency.as_json(),
                    "repro": {
                        "argv_steps": w.repro.argv_steps,
                        "solve_steps": w.repro.solve_steps,
                        "has_script": w.repro.script is not None,
                        "hash_only": [a.artifact_id for a in w.repro.hash_only],
                        "unrendered": list(w.repro.unrendered),
                    },
                    "gaps": list(w.gaps),
                }
                for w in writeups
            ],
        }
        blob = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        sys.stdout.buffer.write(blob.encode("utf-8"))
        sys.stdout.buffer.flush()
        return 1 if void else 0

    for path, reason in void:
        print(f"VOID  {path}\n      {reason}")

    if args.sufficiency:
        _sufficiency_table(writeups)
        return 1 if void else 0

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        # **`attempt_id` 는 출력 파일 이름으로 유일하지 않다.** 재빌드-6이 r4·r5의
        # attempt 를 **같은 `attempt_id` 로** 다시 돌렸으므로(`O-23` 의 골든 재실행),
        # 서로 다른 스트림 둘이 한 이름으로 떨어진다. 조용히 덮어쓰면 하나가 사라지고
        # 그것은 `TELEMETRY_SCHEMA.md` §7.1 이 금지한 모양이다 — "필드 이름 충돌 시
        # 조용히 덮어쓰지 않고 **죽어야 한다**". 여기서도 죽는다.
        taken: dict[str, str] = {}
        for w in writeups:
            stem = w.attempt_id or Path(w.stream_path).stem
            if stem in taken:
                print(
                    f"충돌  {stem}\n"
                    f"      {taken[stem]}\n"
                    f"      {w.stream_path}\n"
                    "      같은 attempt_id 를 가진 스트림이 둘이다. 조용히 덮어쓰지 않는다 "
                    "(TELEMETRY_SCHEMA §7.1). --out 을 나누어 다시 돌려라."
                )
                return 2
            taken[stem] = w.stream_path
            _write_utf8(args.out / f"{stem}.md", render_markdown(w))
            if w.repro.script:
                _write_utf8(args.out / f"{stem}.repro.sh", w.repro.script)
            print(f"{w.stream_path}  →  {args.out / (stem + '.md')}"
                  + ("  + repro.sh" if w.repro.script else "  (재현 스크립트 없음)"))
    elif writeups:
        sys.stdout.buffer.write(render_markdown(writeups[0]).encode("utf-8"))
        sys.stdout.buffer.flush()

    return 1 if void else 0


def _mark(v: bool | None) -> str:
    """`-` 는 **해당 없음**이고 `X` 와 다르다 (`CLAUDE.md` §6)."""
    if v is None:
        return "-"
    return "O" if v else "X"


def _sufficiency_table(writeups: list[Writeup]) -> None:
    print(f"{'stream':26s} {'outcome':9s}  a    b    b'   c    d")
    print("-" * 62)
    for w in writeups:
        s = w.sufficiency
        cells = "".join(
            f" {_mark(v)}   "
            for v in (
                s.a_tool_order,
                s.b_solve_steps,
                s.b_prime_solve_script,
                s.c_observations,
                s.d_success_evidence,
            )
        )
        print(f"{Path(w.stream_path).name:26s} {w.outcome or '?':9s} {cells}")
    print()
    print("O 있다 · X 없다 · - 해당 없음 (**X 와 - 를 접지 않는다**)")
    print()
    for key, label in (
        ("a_tool_order", "(a) 도구 순서"),
        ("b_solve_steps", "(b) 실행 가능한 solve 단계"),
        ("b_prime_solve_script", "(b') role=solve_script artifact"),
        ("c_observations", "(c) 무엇을 관찰했나"),
        ("d_success_evidence", "(d) 성공의 증거"),
    ):
        vals = [getattr(w.sufficiency, key) for w in writeups]
        yes = sum(1 for v in vals if v is True)
        no = sum(1 for v in vals if v is False)
        na = sum(1 for v in vals if v is None)
        print(f"{label:34s} 있다 {yes:2d} · 없다 {no:2d} · 해당 없음 {na:2d}   (전체 {len(vals)})")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
