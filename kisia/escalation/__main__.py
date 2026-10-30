"""escalation 패킷 컴파일러 CLI.

    python -m kisia.escalation [옵션] <stream.jsonl> ...

옵션
    --out DIR      스트림마다 `<attempt_id>.packet.md` 와 `<attempt_id>.packet.json`
                   을 쓴다. 생략하면 stdout 으로 첫 패킷만 낸다
    --summary      스트림마다 한 줄 — stall 신호 · CONFIRMED · INFERRED(접지 상태) ·
                   REJECTED. **여러 스트림이 서로 다른 모양인지 눈으로 보는 자리다**
    --json         기계 판독용. `PATH_SCOPE.md` §3.7 의 `packet.json` 이 이 모양이다

**이 CLI 는 아무것도 보내지 않는다.** 전송은 `SAFETY_SCOPE.md` 의 단일 export 경로가
하는 일이고 현재 비활성이다(`PATH_SCOPE.md` §3.7).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kisia.checker.model import StreamVoidError, load_stream
from kisia.escalation.compile import compile_packet
from kisia.escalation.model import Packet
from kisia.escalation.render import render_markdown


def _write_utf8(path: Path, text: str) -> None:
    """**UTF-8 바이트로 직접 쓴다.** 라이트업 `__main__` 과 같은 이유다 — Windows
    워크스테이션의 기본 인코딩은 cp949 이고, S9.5 가 대조하라고 지목한 두 기계 중
    하나가 그 워크스테이션이다(R3-8). 문서가 기계에 따라 달라지면 안 된다.
    """
    path.write_bytes(text.encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kisia.escalation", add_help=True)
    ap.add_argument("streams", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args(argv)

    packets: list[Packet] = []
    void: list[tuple[Path, str]] = []
    for path in args.streams:
        try:
            stream = load_stream(path)
        except StreamVoidError as exc:
            # S9.2 — 빈틈이 있으면 그 attempt 의 모든 판정이 무효다. 패킷도 내지 않는다:
            # 무효인 스트림에서 만든 escalation 은 근거 없는 요청이 된다.
            void.append((path, str(exc)))
            continue
        packets.append(compile_packet(stream))

    if args.as_json:
        payload = {
            "void": [{"stream": str(p), "reason": r} for p, r in void],
            "packets": [p.as_json() for p in packets],
        }
        _emit(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 1 if void else 0

    for path, reason in void:
        _say(f"VOID  {path}\n      {reason}")

    if args.summary:
        _summary(packets)
        return 1 if void else 0

    if args.out:
        return _write_all(packets, args.out) or (1 if void else 0)
    if packets:
        _emit(render_markdown(packets[0]))
    return 1 if void else 0


def _emit(text: str) -> None:
    """**stdout 에도 UTF-8 바이트로 직접 쓴다.** `print` 를 쓰면 Windows 워크스테이션에서
    stdout 인코딩이 cp949 가 되어 이 CLI 의 출력이 기계마다 달라지고, 한글이 섞인 줄은
    아예 `UnicodeEncodeError` 로 죽는다(실측). `_write_utf8` 과 같은 이유이고 같은 근거다
    (R3-8, S9.5 가 대조하라고 지목한 두 기계 중 하나가 그 워크스테이션이다).
    """
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


def _say(line: str = "") -> None:
    _emit(line + "\n")


def _write_all(packets: list[Packet], out: Path) -> int:
    """**`attempt_id` 는 출력 파일 이름으로 유일하지 않다.** 재빌드-6이 r4·r5의 attempt 를
    같은 `attempt_id` 로 다시 돌렸으므로(`O-23`) 서로 다른 스트림 둘이 한 이름으로
    떨어질 수 있다. 조용히 덮어쓰면 하나가 사라지고 그것은 `TELEMETRY_SCHEMA.md` §7.1
    이 금지한 모양이다 — "필드 이름 충돌 시 조용히 덮어쓰지 않고 **죽어야 한다**".
    """
    out.mkdir(parents=True, exist_ok=True)
    taken: dict[str, str] = {}
    for p in packets:
        stem = p.attempt_id or Path(p.stream_path).stem
        if stem in taken:
            _say(
                f"충돌  {stem}\n"
                f"      {taken[stem]}\n"
                f"      {p.stream_path}\n"
                "      같은 attempt_id 를 가진 스트림이 둘이다. 조용히 덮어쓰지 않는다 "
                "(TELEMETRY_SCHEMA §7.1). --out 을 나누어 다시 돌려라."
            )
            return 2
        taken[stem] = p.stream_path
        _write_utf8(out / f"{stem}.packet.md", render_markdown(p))
        _write_utf8(
            out / f"{stem}.packet.json",
            json.dumps(p.as_json(), ensure_ascii=False, indent=2) + "\n",
        )
        blocked = "  ⚠ export 차단 사유 있음" if p.export_blockers else ""
        _say(f"{p.stream_path}  →  {out / (stem + '.packet.md')}{blocked}")
    return 0


def _summary(packets: list[Packet]) -> None:
    """**세 절의 계수를 스트림마다 한 줄로.** 셋이 같은 모양으로 나오면 컴파일러가 셋을
    못 가르고 있는 것이다.
    """
    _say(f"{'stream':22s} {'stall':16s} CONF  INF  접지        REJ  blockers")
    _say("-" * 78)
    for p in packets:
        signals = ",".join(p.signals) or "(없음)"
        _say(
            f"{Path(p.stream_path).name:22s} {signals:16s} "
            f"{len(p.confirmed):4d} {len(p.inferred):4d}  {p.grounding_label:10s} "
            f"{len(p.rejected):3d}  {len(p.export_blockers)}"
        )
    _say()
    _say(
        "접지: **접지됨 / 접지 안 됨 / 가설 없음** 을 접지 않는다 — 셋은 다른 사실이다 "
        "(`D-63` 이 난 자리)."
    )
    _say()
    for label, n in (
        ("stall 이 관측된 스트림", sum(1 for p in packets if p.stalled)),
        ("가설이 접지된 스트림", sum(1 for p in packets if p.grounding == "grounded")),
        ("가설이 접지되지 않은 스트림", sum(1 for p in packets if p.grounding == "ungrounded")),
        ("가설이 0건인 스트림", sum(1 for p in packets if p.grounding == "no_hypothesis")),
        ("기각이 있는 스트림", sum(1 for p in packets if p.rejected)),
    ):
        _say(f"{label:34s} {n:3d}   (전체 {len(packets)})")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
