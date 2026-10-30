#!/usr/bin/env python3
"""골든 트라젝토리와 음성 프로브를 돌린다.

    python3 run.py a          유형 A 골든
    python3 run.py b          유형 B 골든
    python3 run.py c          유형 C 골든
    python3 run.py a4         음성: 틀린 후보 (S8-a)
    python3 run.py b9         음성: 세션을 끊고 다시 붙어 이어서 시도
    python3 run.py c4         음성: 턴 사이에 쿠키 항아리를 버린다 (S6-a)
    python3 run.py all        위 여섯을 순서대로

**매 arm run 직전에 다시 돌린다**(§9.2.1). 그래서 재실행 가능해야 하고, 실제로 그렇다:
fixture 서비스는 요청/연결 스코프 상태만 들고 있어 run 사이에 남는 것이 없고, worker
컨테이너는 run 마다 새로 만들고 지운다.

**모델을 호출하지 않는다.** 이 명령의 비용은 0이다. 호출이 발생하면 설계가 틀린 것이다.
"""
import importlib.util
import json
import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE.parent / "fixtures"
RUN_ROOT = pathlib.Path(os.environ.get("KISIA_GOLDEN_RUNS", "<HOME>/runs/golden"))
WORKER_IMAGE = os.environ.get("KISIA_WORKER_IMAGE", "kisia-fix/worker:1")
NETWORK = os.environ.get("KISIA_FIXNET", "kisia-fixnet")
HOST_ID = os.environ.get("KISIA_HOST_ID", "kisia-vultr-203.0.113.10")

sys.path.insert(0, str(HERE))
from driver import Emitter, Golden  # noqa: E402

# name -> (fixture dir, 골든 스크립트, 인자, 스트림 파일명, 이 이름이 요구하는 결과)
CASES = {
    "a":  ("a-static",  "a/golden_a.py", [],       "a/stream.jsonl",      "solved"),
    "b":  ("b-session", "b/golden_b.py", [],       "b/stream.jsonl",      "solved"),
    "c":  ("c-web",     "c/golden_c.py", [],       "c/stream.jsonl",      "solved"),
    "a4": ("a-static",  "a/golden_a.py", ["--a4"], "a/negative-a4.jsonl", "rejected"),
    "b9": ("b-session", "b/golden_b.py", ["--b9"], "b/negative-b9.jsonl", "rejected"),
    "c4": ("c-web",     "c/golden_c.py", ["--c4"], "c/negative-c4.jsonl", "rejected"),
}


def load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def one(name: str) -> tuple[bool, str]:
    fixture_name, script, argv, stream_rel, expect = CASES[name]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    attempt_id = f"{name}-{stamp}"
    run_dir = RUN_ROOT / attempt_id
    stream = HERE / stream_rel

    em = Emitter(stream, run_id=f"golden-{stamp}", attempt_id=attempt_id)
    g = Golden(
        fixture_dir=FIXTURES / fixture_name,
        run_dir=run_dir,
        emitter=em,
        worker_image=WORKER_IMAGE,
        network=NETWORK,
        host_id=HOST_ID,
        arm_id=f"GOLDEN-{name.upper()}",
    )
    try:
        ok, msg = load(HERE / script).main(g, argv)
    except Exception as e:  # noqa: BLE001 - 실패도 스트림에 남긴다
        g.em.emit("attempt.finished", outcome="error", reason=f"{type(e).__name__}: {e}", wall_clock_s=0)
        ok, msg = False, f"예외: {type(e).__name__}: {e}"
    finally:
        try:
            g.destroy_workspace()
        finally:
            em.close()
    return ok, f"[{name}] {'PASS' if ok else 'FAIL'} ({expect}) — {msg}  stream={stream}"


def main(argv: list[str]) -> int:
    names = list(CASES) if argv[0] == "all" else argv
    results = []
    for n in names:
        if n not in CASES:
            print(f"모르는 이름: {n}", file=sys.stderr)
            return 2
        ok, line = one(n)
        results.append((n, ok))
        print(line, flush=True)
    print(json.dumps({"pass": [n for n, o in results if o], "fail": [n for n, o in results if not o]}))
    return 0 if all(o for _, o in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["all"]))
