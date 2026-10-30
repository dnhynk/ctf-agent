"""S8 — verifier. **별도 프로세스이고 runtime 의 트리 밖에서 돈다.**

`PATH_SCOPE.md` §1 이 배치를 규정한다: runtime 과는 통로 하나로만 말하고, 넘어가는
것은 **후보 문자열**, 돌아오는 것은 **verdict 하나**다. 정답도 정답의 해시도 넘어가지
않는다. `spec.md` §0.4 가 인정한 한계("술어는 이름 규칙만 검사한다")를 메우는 것이
이 배치이지 이름이 아니다.

    python3 -m kisia.runtime.verifier --answer <answer.json>
    stdin  : 후보 한 줄에 하나
    stdout : true|false|n/a 한 줄에 하나

E 가 정답을 solver 프로세스 **안**에 넣고 틀린 제출마다 로그로 흘린 것이
`SEAM_IMPLEMENTATION_MAP.md` §2 의 S8 행이 REWRITE 인 이유다. 그 자리를 다시 열지
않으려면 정답이 이 프로세스 밖으로 나가지 않아야 한다.

**무정답 모드 — `n/a`.** 라이브 대회에서 우리는 정답을 모른다. `--answer` 가 가리키는
파일이 없거나 그 안에 `flag` 키가 없으면(`MANIFEST.md` §2.3.a 의
`verification: deferred-manual`) 이 프로세스는 **판정하지 않고** 후보마다 `n/a` 를 낸다.
**`false` 로 접지 않는다** — "모른다"와 "틀렸다"는 다른 값이고, 접으면 거짓 관측을
기록한다(`spec.md` R2-3, `CLAUDE.md` §6). 판정은 `N/A` 이지 FAIL 이 아니다
(`MANIFEST.md` §2.3.a).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _wanted_digest(answer: Path) -> str | None:
    """대조할 정답의 sha256. **무정답이면 `None`** 이고 그것이 `n/a` 의 근거다.

    두 갈래로 무정답이 된다 — 파일이 아예 없거나(대회 챌린지에는 `answer/` 가 없다),
    있는데 `flag` 키가 없거나(`MANIFEST.md` §2.3.a 의 `deferred-manual`). 둘 다
    "정답을 모른다"이고, 여기서 `False` 를 만들면 그 사실이 사라진다.
    """
    if not answer.is_file():
        return None
    loaded = json.loads(answer.read_text(encoding="utf-8"))
    flag = loaded.get("flag") if isinstance(loaded, dict) else None
    if flag is None:
        return None
    return hashlib.sha256(str(flag).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kisia.runtime.verifier")
    ap.add_argument("--answer", type=Path, required=True)
    args = ap.parse_args(argv)

    want = _wanted_digest(args.answer)

    for line in sys.stdin:
        candidate = line.rstrip("\n")
        if want is None:
            # 판정하지 않았다는 것을 그대로 적는다. 후보는 그래도 한 줄을 받는다 —
            # 줄 수가 어긋나면 호출자가 어느 후보의 답인지 잃는다.
            sys.stdout.write("n/a\n")
            sys.stdout.flush()
            continue
        got = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        # 해시끼리 비교한다. 평문 정답이 이 프로세스의 어떤 출력에도 닿지 않는다.
        sys.stdout.write("true\n" if got == want else "false\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
