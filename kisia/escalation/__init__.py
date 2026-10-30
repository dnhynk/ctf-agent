"""escalation 패킷 컴파일러 — S9 의 두 소비자 중 하나 (`SEAM_IMPLEMENTATION_MAP.md` §6).

**seam 이 아니다. telemetry 의 투영이다.** 어떤 seam 판정도 바꾸지 않고, 검사기의
술어 계층(`kisia.checker.predicates` · `kisia.checker.judge` · `kisia.checker.grounding`)
을 import 하지 않는다(`D-59`). 쓰는 것은 스트림 판독기 하나뿐이다 — 검사기와 **같은
관문**(S9.2, seq 빈틈)으로 읽어야 무효인 스트림을 유효한 것처럼 컴파일하지 않는다.

**§5 예약 이벤트에는 술어가 없다** (`TELEMETRY_SCHEMA.md` §5.1, `R2-15`). 이 계층이
붙이지도 않는다. 붙이는 순간 예약이 예약이 아니게 되고
`kisia_tests/test_reserved_events.py::test_the_reserved_events_carry_no_predicate` 가
그것을 잠근다.

입력은 `stall.observed` · `hypothesis.recorded` · `hypothesis.rejected` 셋이고,
프로덕션-1 이 그 발행자를 `kisia/runtime/loop.py` 에 넣기 전까지 저장된 48 스트림에서
**0건**이었다(`O-38`).

---

## `ADR-0003` Decision-3 의 6조건에 이 코드가 어디까지 닿는가

조건 원문은 `docs/canon/SAFETY_SCOPE.md` "Escalation egress" :82-97 이다.
**이 세션의 범위는 컴파일과 직렬화까지이고 전송(egress)은 아니다.** 그러므로 여섯 중
셋은 이 코드의 것이 아니고, 그 사실을 적어 두는 것이 다음 세션의 입력이다.

**1. 단일 경로** — 챌린지 유래 내용은 export 함수 하나로만 나간다.
**미충족 · 범위 밖.** 이 계층에 egress 가 없다. 네트워크를 열지 않고 `kisia.runtime`
도 import 하지 않는다(시험이 잠근다). 파일은 CLI 의 `--out` 만 쓰고, 그 자리는
`PATH_SCOPE.md` §3.7 이 정한 `packet.json` 이다.

**2. 컴파일된 것이지 raw 가 아니다** — 관측·가설·상태의 투영만 건너간다.
**충족.** `compile.py` 는 `stall.observed` · `hypothesis.*` · 그 stall 이 지목한
`observation.recorded` 만 읽는다. `input.bound.files[]` 도 `artifact.produced` 도
패킷에 없고, 통제 블록은 `CARRIED_CONTROL` 넷으로 좁힌다.

**3. 비밀 제거** — sentinel 을 실어 보내느니 export 를 중단한다.
**부분 충족.** 정답 문자열(`candidate.produced.value`)은 제거하고 지운 사실을
`Packet.redactions` 로 남긴다(S8.3). redaction sentinel 을 만나면 **중단하지 않고**
`Packet.export_blockers` 에 기록한다 — 중단은 export 하는 쪽의 동작이고 이 계층은
export 하지 않는다. **한계 하나를 명시한다:** 후보를 한 번도 내지 않은 채 관찰
바이트에만 정답이 있는 스트림은 이 계층이 잡지 못하고, 패킷의 `notes` 가 그것을 적는다.

**4. 목적지가 named** — 활성 설정에 이름 있는 endpoint 로만.
**미충족 · 범위 밖.** 이 계층은 목적지를 **알지 못한다.** 그 자체가 기여이기도 하다 —
모델이 호출 시점에 목적지를 지정할 표면이 없다.

**5. 기록** — 목적지·content hash·redaction 결과·attempt 를 남긴다.
**부분 충족.** `Packet.as_json()` 이 hash 대상이고 redaction 결과는 `redactions` 와
`export_blockers` 가 나른다. **목적지와 로그 파일(`export.log`)은 export 하는 쪽의
것이다.**

**6. 코어 하류** — worker 안에서 돌지 않는다.
**충족.** 저장된 스트림에 대한 순수 함수이고 호스트 쪽이다. `kisia.runtime` 을 import
하지 않는 것을 **별도 프로세스에서** 재는 시험이 있다.

**미충족 셋(1·4·5의 나머지)은 결손이 아니라 다음 세션의 일이다.** `ADR-0003` 자신이
"어디로 보내는가"를 이 층이 아니라 export 게이트에 두었고, `SAFETY_SCOPE.md` 의
`allow_external_ai` 아래에서도 그 경로는 **현재 비활성**이다(`PATH_SCOPE.md` §3.7).
"""

from kisia.escalation.compile import compile_packet
from kisia.escalation.model import (
    Fact,
    Inference,
    Packet,
    Redaction,
    Rejection,
    Stall,
)
from kisia.escalation.render import render_markdown

__all__ = [
    "Fact",
    "Inference",
    "Packet",
    "Redaction",
    "Rejection",
    "Stall",
    "compile_packet",
    "render_markdown",
]
