"""제품 골격 — orchestrator · solver · scheduler.

`ADR-0003` §Decision-1 이 채택한 컴포넌트 경계 일곱(orchestrator · solver(들) ·
evidence store · verifier · scheduler · escalation exporter · 운영 UI) 중 셋이 여기
있고, evidence store 는 `kisia.evidence` 다. 나머지 넷의 자리:

| 컴포넌트 | 어디에 |
|---|---|
| verifier | `kisia.runtime.verifier` — 이미 있다. 별도 프로세스(S8) |
| escalation exporter | `kisia.escalation` 이 **컴파일**까지. egress 는 없다 |
| 운영 UI | 없다. 이 트랙의 범위가 아니다 |
| 둘째 solver (ClaudeCodeWorker) | **없다.** `CLAUDECODE_WORKER_DESIGN.md` §3.1 의 연역이 미실측 |

**`scheduler.py` 는 `kisia/scheduler/` 가 아니라 여기 있다.** 호출자가
`Orchestrator` 하나뿐이고, 백 줄짜리 모듈에 최상위 패키지를 하나 더 여는 것은
포장 수준의 조기 일반화다(`CLAUDE.md` §8). 둘째 호출자가 생기는 시점이 옮기는
시점이다.

**`kisia.evidence` 는 여기 있지 않다.** 그쪽은 `kisia.runtime` 을 import 하지 않는다는
성질을 시험으로 잠그는데(다른 기계에서 증거를 열 수 있어야 한다, `PATH_SCOPE.md` §4.3),
이 패키지는 `kisia.runtime.agent_a` 를 부르는 것이 일이다. 한 패키지에 두면 그 경계가
이름에서 사라진다.
"""

from kisia.orchestrator.model import (
    Assignment,
    Attempt,
    AttemptResult,
    Challenge,
)
from kisia.orchestrator.orchestrator import (
    Orchestrator,
    OrchestratorError,
    PromotionBlockedError,
    ScopeRefusedError,
    Solver,
)
from kisia.orchestrator.scheduler import OPERATOR_LADDER, Rung, Scheduler, SchedulerError

__all__ = [
    "OPERATOR_LADDER",
    "Assignment",
    "Attempt",
    "AttemptResult",
    "Challenge",
    "Orchestrator",
    "OrchestratorError",
    "PromotionBlockedError",
    "Rung",
    "Scheduler",
    "SchedulerError",
    "ScopeRefusedError",
    "Solver",
]
