"""orchestrator — 문제 하나를 solver 하나에게 배정하고, 그 산출물을 보관한다.

`ADR-0003` §Decision-1 이 채택한 경계 일곱 중 하나다. **여기서 하는 것은 셋이다.**

1. **배정.** 큐의 문제 하나에 scheduler 가 답한 rung 을 붙여 `Assignment` 을 만든다.
2. **회계 라벨을 생성 시점에 붙인다** (`ADR-0003` §Consequences). 파생 규칙은
   `_label_for` 이고 근거는 canon 이다.
3. **결과를 evidence store 에 넣는다.** 스트림 파일이 attempt 단위로 앉는다.

**하지 않는 것 — 그리고 그것이 왜 결손이 아닌가.**

- **컨테이너를 만들지 않는다.** canon 이 컨테이너 생성을 프록시를 통해 `ctf-host-user` 계정에만
  준다(`SAFETY_SCOPE.md` "Container isolation (standing)" · 재빌드 예외). 오늘 그 코드는
  `kisia/runtime/workspace.py` 이고 그것을 부르는 것은 `run_attempt` 다. 이 orchestrator
  는 그 함수를 부르므로 **격리를 우회하는 경로를 새로 만들지 않는다.**
  `CLAUDECODE_WORKER_DESIGN.md` §4-① 의 그림은 워크스페이스 수명을 orchestrator 에
  두는데, **옮기려면 `kisia/runtime/` 을 고쳐야 하고 이 트랙은 하지 않았다.**
  옮긴 척하지 않는다 — `native.py` 머리말이 같은 사실을 적는다.
- **verifier 를 직접 부르지 않는다.** 같은 이유다. S8 의 별도 프로세스 호출은
  `run_attempt` 안(`golden_a._verify`)에 있다. orchestrator 는 그 결과를 **스트림에서
  읽는다** — solver 의 notes 가 아니라.
- **race 를 하지 않는다.** `ADR-0003` 이 스케줄링 기본값을 열어 두었다.
  한 문제에 한 번에 한 attempt 다. `scheduler.py` 머리말을 보라.
- **상태를 파일로 남기지 않는다.** 재시작·복구(`CONTEST_ARCHITECTURE.md` §12)는 정해진
  적이 없고, 복구 모델 없이 직렬화 형식만 굳히지 않는다(`CLAUDE.md` §8).
- **운영 UI 가 없다** (`CONTEST_ARCHITECTURE.md` §13). `Challenge.state` 가 UI 가 읽을
  값이지만 UI 자체는 이 트랙의 범위가 아니다.
"""

from __future__ import annotations

from collections.abc import Callable

from kisia.evidence.store import EvidenceStore
from kisia.orchestrator.model import (
    CONTEST,
    FINAL_HOLDOUT,
    Assignment,
    Attempt,
    AttemptResult,
    Challenge,
)
from kisia.orchestrator.scheduler import Rung, Scheduler

#: solver 의 형태. **클래스가 아니라 호출 가능한 것 하나다** — `CLAUDE.md` §8,
#: `CLAUDECODE_WORKER_DESIGN.md` §4-⑥. 오늘 유일한 구현은
#: `kisia.orchestrator.native.NativeHarnessWorker` 다.
Solver = Callable[[Assignment], AttemptResult]


class OrchestratorError(RuntimeError):
    """배정할 수 없다."""


class ScopeRefusedError(OrchestratorError):
    """canon 또는 계약이 이 배정을 금지한다. **막히고 보고한다.**"""


class PromotionBlockedError(OrchestratorError):
    """다음 rung 이 정해지지 않아 돌릴 수 없다. **추측해서 채우지 않는다.**"""


class Orchestrator:
    """큐 하나 · scheduler 하나 · solver 하나 · evidence store 하나."""

    def __init__(
        self,
        *,
        store: EvidenceStore,
        scheduler: Scheduler,
        solver: Solver,
    ) -> None:
        self.store = store
        self.scheduler = scheduler
        self.solver = solver
        self.queue: list[Challenge] = []

    # -- 큐 ------------------------------------------------------------------
    def submit(self, challenge_id: str, *, challenge_set: str = "dev") -> Challenge:
        """문제 하나를 큐에 넣는다. 같은 id 가 이미 있으면 그것을 돌려준다."""
        for existing in self.queue:
            if existing.challenge_id == challenge_id:
                return existing
        challenge = Challenge(challenge_id=challenge_id, challenge_set=challenge_set)
        self.queue.append(challenge)
        return challenge

    # -- 배정 ----------------------------------------------------------------
    def next_rung(self, challenge: Challenge) -> Rung | None:
        """이 문제의 다음 rung. 없으면 `None`.

        직전 attempt 가 아직 안 끝났으면 배정하지 않는다 — 한 문제에 한 attempt 다.
        """
        last = challenge.last
        if last is None:
            return self.scheduler.first
        if not last.finished:
            raise OrchestratorError(
                f"{challenge.challenge_id}: 직전 attempt 가 아직 돌고 있다 "
                f"({last.assignment.attempt_id}) — 이 골격은 race 를 하지 않는다"
            )
        current = self.scheduler.by_name(last.assignment.rung_name)
        return self.scheduler.next_after(
            current,
            verified=last.verified,
            # **하니스가 관측한 것이지 모델이 말한 것이 아니다** — `stall.observed` 와
            # 되풀이된 가설은 스트림에서 읽는다 (`native.read_stream_outcome`).
            stalled=last.result is not None and last.result.stalled,
        )

    def next_assignment(self, challenge: Challenge) -> Assignment | None:
        """다음 배정. 사다리가 끝났거나 이미 풀렸으면 `None`."""
        rung = self.next_rung(challenge)
        if rung is None:
            return None
        if not rung.is_runnable:
            raise PromotionBlockedError(
                f"rung {rung.name!r} 의 reasoning_effort 가 정해지지 않았다 — "
                f"운영자가 적은 것은 {rung.trigger!r} 이고 값이 아니라 범위다. "
                "미정을 기본값으로 접지 않는다 (ADR-0003 '이 문서가 정하지 않고 열어 둔 것')"
            )
        label, solve_k = self._label_for(challenge)
        if challenge.challenge_set == FINAL_HOLDOUT and label != "clean":
            raise ScopeRefusedError(
                f"{challenge.challenge_id}: challenge_set={FINAL_HOLDOUT} 인데 "
                f"{len(challenge.attempts) + 1}번째 시도라 라벨이 {label!r} 이 된다. "
                "holdout Attempt 는 clean 라벨만 허용한다 (ADR-0003 §Consequences) — "
                "clean_solve@1 은 정의상 1시도·무재시도다 (EVAL_CONTRACT.md)"
            )
        return Assignment(
            attempt_id=f"{challenge.challenge_id}-{len(challenge.attempts) + 1:02d}",
            challenge_id=challenge.challenge_id,
            challenge_set=challenge.challenge_set,
            accounting_label=label,
            solve_k=solve_k,
            rung_name=rung.name,
            model_id=rung.model_id,
            # `is_runnable` 이 위에서 참임을 보장한다.
            effort=str(rung.reasoning_effort),
        )

    @staticmethod
    def _label_for(challenge: Challenge) -> tuple[str, int]:
        """`ADR-0003` §Consequences 의 `(accounting_label, solve_k)` 를 파생한다.

        - **`challenge_set == "contest"` 이면 언제나 `contest`.** 시도 번호와 무관하다 —
          라벨은 *"어느 계기의 숫자에 이 run 이 들어가는가"* 이고, 살아 있는 대회의 run 은
          `clean_solve@1` 의 **분자에도 분모에도 들어가지 않는다**(`MVP_SCOPE.md` §6).
          `solve@k` 로 적으면 그것이 재시도 지표의 분모로 세어지고, 그 오염을 막으려고
          `R5-9` 가 이 라벨을 만들었다.
        - **그 밖에서 첫 시도는 `clean`.** `clean_solve@1` 의 정의가 1시도·무재시도·
          무개입·단일 모델·escalation 없음이다(`EVAL_CONTRACT.md` :39, :46). 이 골격은
          단일 코어로 순차 실행하므로 첫 attempt 는 그 다섯을 만족한다.
        - **둘째부터는 `solve@k`.** 승격 재시도는 정의상 무재시도가 아니다.

        `solve_k` 는 세 갈래 전부에서 **시도 번호**다. 첫 시도가 1 이므로 `clean` 인
        attempt 는 `solve_k=1` 이고, 그것이 `agent_a._control` 이 상수로 박아 두었던 값과
        같다 — 다른 것은 **둘째부터**이고 그 자리가 `O-57` 이 가리키는 곳이다.
        """
        k = len(challenge.attempts) + 1
        if challenge.challenge_set == CONTEST:
            return CONTEST, k
        return ("clean" if k == 1 else "solve@k"), k

    # -- 실행 ----------------------------------------------------------------
    def run_one(self, challenge: Challenge) -> Attempt | None:
        """다음 attempt 하나를 돌리고 산출물을 보관한다. 배정이 없으면 `None`."""
        assignment = self.next_assignment(challenge)
        if assignment is None:
            return None
        attempt = Attempt(assignment=assignment)
        challenge.attempts.append(attempt)
        attempt.result = self.solver(assignment)
        self._file(attempt.result)
        return attempt

    def run_until_done(self, challenge: Challenge, *, max_attempts: int) -> Challenge:
        """verified solve 가 나오거나 사다리가 끝날 때까지.

        `max_attempts` 는 **필수 인자다.** 기본값을 주면 그것이 정해진 적 없는 시도
        예산이 되고, `ADR-0003` 이 열어 둔 자리를 이 함수가 닫는다.
        """
        if max_attempts < 1:
            raise OrchestratorError(f"max_attempts 는 1 이상이다: {max_attempts}")
        for _ in range(max_attempts):
            if self.run_one(challenge) is None:
                break
            if challenge.state == "solved":
                break
        return challenge

    def _file(self, result: AttemptResult) -> None:
        """스트림을 evidence store 에 넣는다. **판정·라이트업·패킷은 넣지 않는다** —
        그것들을 만드는 것은 `kisia.checker` · `kisia.writeup` · `kisia.escalation` 이고
        언제 부를지는 이 골격이 정하지 않았다. 자리는 store 가 이미 알고 있다."""
        if result.stream_path is None or not result.stream_path.is_file():
            return
        self.store.put(
            result.attempt_id,
            "stream",
            result.stream_path.name,
            result.stream_path.read_bytes(),
        )
