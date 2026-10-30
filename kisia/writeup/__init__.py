"""라이트업 생성기 — S9 의 두 소비자 중 하나 (`SEAM_IMPLEMENTATION_MAP.md` §6).

**seam 이 아니다. telemetry 의 투영이다.** 어떤 seam 판정도 바꾸지 않고, 검사기의
술어 계층(`kisia.checker.predicates` · `kisia.checker.judge`)을 import 하지 않는다.
쓰는 것은 스트림 판독기 하나뿐이다 — 검사기와 **같은 관문**(S9.2, seq 빈틈)으로 읽어야
무효인 스트림을 유효한 것처럼 렌더하지 않는다. 파서를 두 벌 두면 조용히 갈린다.

`cost.py` ↔ `checker/pricing.py` 의 의도적 이중화(`D-49`)와 다른 자리다: 저쪽은
**검사가 자기 자신을 검사하는 것**을 막으려고 독립이어야 하고, 라이트업은 스트림을
검사하지 않고 투영하므로 그 요구가 걸리지 않는다.
"""

from kisia.writeup.model import Sufficiency, Writeup
from kisia.writeup.project import project
from kisia.writeup.render import render_markdown

__all__ = ["Sufficiency", "Writeup", "project", "render_markdown"]
