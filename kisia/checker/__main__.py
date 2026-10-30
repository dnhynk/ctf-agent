"""검사기 CLI.

    python -m kisia.checker [옵션] <stream.jsonl> ...

옵션
    --pricing PATH        `config/pricing.openai.yaml`. S3.2의 판정 입력
    --fixtures-root DIR   챌린지 픽스처가 든 디렉터리. 스트림의
                          `challenge_manifest_sha256` 으로 고른다 (기본
                          `docs/spike/fixtures`)
    --set                 유형 단위 집합 판정 (`spec.md` §6.3)
    --json                기계 판독용 출력
    --quiet               술어 단위 상세를 줄이고 판정만
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kisia.checker.fixture import Fixture, FixtureError, resolve_by_sha256
from kisia.checker.judge import SetJudgment, StreamJudgment, judge_set, judge_stream
from kisia.checker.model import StreamVoidError, load_stream
from kisia.checker.pricing import Price, load_pricing, matches_pin, pricing_sha256

DEFAULT_FIXTURES_ROOT = Path("docs/spike/fixtures")


def _fixture_roots(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    if (root / "manifest.json").is_file():
        return [root]
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "manifest.json").is_file())


def _resolve(stream_control: dict[str, object], roots: list[Path]) -> tuple[Fixture | None, str]:
    want = str(stream_control.get("challenge_manifest_sha256", ""))
    if not want:
        return None, "통제 블록에 challenge_manifest_sha256 이 없다"
    try:
        fixture = resolve_by_sha256(roots, want)
    except FixtureError as exc:
        return None, str(exc)
    if fixture is None:
        return None, f"매니페스트 {want[:20]}… 를 가진 픽스처를 찾지 못했다"
    return fixture, ""


def _pricing_mismatch(
    stream_control: dict[str, object], pricing_path: Path | None, digest: str
) -> str:
    """스트림이 지목한 단가표와 실제로 주어진 단가표가 다른가 (`spec.md` S9.4a).

    **어긋나면 판정을 내지 않는다** — `TELEMETRY_SCHEMA.md` §2. 픽스처 쪽과 같은
    규칙이되 형태가 다르다: 픽스처는 여러 후보에서 해시로 **고르므로** 어긋난 것을
    애초에 집지 않지만, 단가표는 `--pricing` 하나뿐이라 명시적으로 막아야 한다.

    지목이 **없는** 경우는 막지 않는다. 그 attempt 는 통제 블록 결손으로 S9.1 이
    이미 거짓이고 폐기 대상인데, 여기서 함께 무효로 만들면 폐기된 attempt 를
    진단할 수 없게 된다 — 폐기는 결과를 쓰지 않는다는 뜻이지 진단하지 말라는 뜻이
    아니다(`REBUILD_LOG.md` D-7, `CHECKER.md` §1.1).
    """
    pin = str(stream_control.get("pricing_sha256", ""))
    if not pin or not digest:
        return ""
    if matches_pin(pin, digest):
        return ""
    return (
        f"스트림이 지목한 단가표가 아니다 (S9.4a). "
        f"스트림 {pin.removeprefix('sha256:')[:16]}… != {pricing_path} {digest[:16]}…. "
        "대조에 실패하면 판정을 내지 않는다 (TELEMETRY_SCHEMA §2)."
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kisia.checker", add_help=True)
    ap.add_argument("streams", nargs="+", type=Path)
    ap.add_argument("--pricing", type=Path, default=None)
    ap.add_argument("--fixtures-root", type=Path, default=DEFAULT_FIXTURES_ROOT)
    ap.add_argument("--set", dest="as_set", action="store_true")
    ap.add_argument(
        "--set-minimum",
        type=int,
        default=4,
        help="집합 판정의 정상 스트림 하한. 계약 판정은 4다 (spec.md R3-7). "
        "낮추면 그 출력은 계약 판정이 아니라 진단이다.",
    )
    ap.add_argument("--json", dest="as_json", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    pricing: dict[str, Price] | None = None
    pricing_digest = ""
    if args.pricing is not None:
        pricing = load_pricing(args.pricing)
        pricing_digest = pricing_sha256(args.pricing)

    roots = _fixture_roots(args.fixtures_root)
    judgments: list[StreamJudgment] = []
    void: list[tuple[Path, str]] = []

    for path in args.streams:
        try:
            stream = load_stream(path)
        except StreamVoidError as exc:
            void.append((path, str(exc)))
            continue
        mismatch = _pricing_mismatch(stream.control, args.pricing, pricing_digest)
        if mismatch:
            void.append((path, mismatch))
            continue
        fixture, why = _resolve(stream.control, roots)
        if fixture is None and why:
            stream.reader_notes.append(f"픽스처 미해결: {why}")
        judgments.append(
            judge_stream(stream, fixture=fixture, pricing=pricing, pricing_digest=pricing_digest)
        )

    if args.as_json:
        payload: dict[str, object] = {
            "void": [{"stream": str(p), "reason": r} for p, r in void],
            "streams": [j.as_json() for j in judgments],
        }
        if args.as_set:
            payload["set_minimum"] = args.set_minimum
            payload["sets"] = [s.as_json() for s in _grouped(judgments, args.set_minimum)]
        # **UTF-8 바이트로 직접 쓴다.** `json.dump(..., sys.stdout)` 은 stdout 의 로케일
        # 인코딩을 거치는데, Windows 워크스테이션의 기본은 cp949 라 비ASCII 판정 note 를
        # 만나면 `UnicodeEncodeError` 로 죽거나 리다이렉트된 파일이 cp949 로 깨진다.
        # S9.5(P-S9-a)가 대조하라고 이름으로 지목한 두 기계 중 하나가 그 워크스테이션이므로
        # (R3-8), 기계 판독용 출력이 기계에 따라 달라지면 그 술어를 행사할 수 없다.
        blob = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        sys.stdout.buffer.write(blob.encode("utf-8"))
        sys.stdout.buffer.flush()
    else:
        _render(
            judgments,
            void,
            as_set=args.as_set,
            quiet=args.quiet,
            set_minimum=args.set_minimum,
        )

    return 1 if void else 0


def _grouped(judgments: list[StreamJudgment], minimum: int = 4) -> list[SetJudgment]:
    by_type: dict[str, list[StreamJudgment]] = {}
    for j in judgments:
        by_type.setdefault(j.challenge_type, []).append(j)
    return [judge_set(v, minimum_normal=minimum) for _, v in sorted(by_type.items())]


def _render(
    judgments: list[StreamJudgment],
    void: list[tuple[Path, str]],
    *,
    as_set: bool,
    quiet: bool,
    set_minimum: int = 4,
) -> None:
    for path, reason in void:
        print(f"VOID  {path}\n      {reason}")

    for j in judgments:
        flags = []
        if j.stream.discarded:
            flags.append("폐기(S9.1)")
        if not j.stream.is_normal:
            flags.append(f"음성/비정상(outcome={j.stream.outcome or '?'})")
        head = f"{j.stream.path}  [유형 {j.challenge_type or '?'}]"
        if flags:
            head += "  " + " ".join(flags)
        print(head)
        for seam in j.seams:
            print(f"  {seam.seam:<3} {seam.label}")
            if quiet:
                continue
            for r in seam.results:
                seqs = f" seq{list(r.seqs)}" if r.seqs else ""
                note = f"  — {r.note}" if r.note else ""
                print(f"        {r.predicate:<5} {r.verdict.label}{seqs}{note}")
        for n in j.stream.reader_notes:
            print(f"  · {n}")
        for u in j.undecidable:
            print(f"  · 판정 불가 후보: {u}")
        print(f"  judgment_digest sha256:{j.digest()}")
        print()

    if as_set:
        if set_minimum != 4:
            print(
                f"!! --set-minimum={set_minimum} 이다. 계약 판정의 하한은 4다 (spec.md R3-7).\n"
                "!! 아래는 계약 판정이 아니라 **술어 대조표**이고, 어떤 seam 판정으로도\n"
                "!! 인용할 수 없다. 이 모드가 필요한 이유와 그 한계는 spec.md §6.3 (R4-2).\n"
            )
        for s in _grouped(judgments, set_minimum):
            print(f"=== 집합 판정 · 유형 {s.challenge_type or '?'} "
                  f"(정상 {s.normal_count}, 전체 {len(s.judgments)}) ===")
            for note in s.notes:
                print(f"  ! {note}")
            for name, verdict in s.seams.items():
                print(f"  {name:<3} {verdict}")
            print()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
