"""`python -m kisia.contest` 의 진입점. **계약은 `run.py` 머리말이다.**

여기 로직을 두지 않는다 — 큐가 부르는 것은 이 모듈이고, 시험이 부르는 것은
`run.run_contest` 다. 둘이 같은 코드를 지나게 하려면 이 파일이 얇아야 한다.
"""

from __future__ import annotations

import sys

from kisia.contest.run import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
