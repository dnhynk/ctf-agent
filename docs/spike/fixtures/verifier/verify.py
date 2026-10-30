#!/usr/bin/env python3
"""fixture 3종 공용 flag verifier.

S8이 요구하는 두 가지를 구조로 만족시킨다.

1. **solver 밖에서 돈다.** 이 파일은 worker 이미지에 들어가지 않고 어떤 컨테이너에도
   마운트되지 않는다. 호스트에서 별도 프로세스로 실행되고, 후보/드라이버는 종료 코드와
   stdout의 판정만 받는다.
2. **정답이 solver의 도달 범위 밖에 있다.** 정답은 `<fixture>/answer/answer.json`에만
   있고 그 경로는 `/input`·`/work`·서비스 응답 어디에도 나타나지 않는다.

후보에게 돌려주는 것은 `verdict` 하나다. 정답도, 정답의 해시도 돌려주지 않는다 —
`candidate_digest`는 **후보** 문자열의 해시이지 정답의 해시가 아니다.

    python3 verify.py --answer <fixture>/answer/answer.json --candidate '<str>'
"""
import argparse
import hashlib
import hmac
import json
import pathlib
import sys

VERIFIER_ID = "kisia-fix-verifier/1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answer", required=True, type=pathlib.Path)
    ap.add_argument("--candidate", required=True)
    a = ap.parse_args()

    answer = json.loads(a.answer.read_text(encoding="utf-8"))["flag"]
    verdict = hmac.compare_digest(answer, a.candidate)

    json.dump(
        {
            "verifier_id": VERIFIER_ID,
            "verdict": verdict,
            "candidate_digest": "sha256:" + hashlib.sha256(a.candidate.encode()).hexdigest(),
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
