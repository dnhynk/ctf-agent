"""`NativeHarnessWorker` — 지금 있는 유일한 solver 구현.

`ADR-0003` §Decision-1 이 solver 를 *"공통 계약 하나를 만족하는 교체 가능한 실행자"* 로
적었지만, **그 계약을 클래스로 세우지 않는다.** `CLAUDECODE_WORKER_DESIGN.md` §4-⑥ 이
같은 이유로 미뤘다 — *"`NativeHarnessWorker` 가 유일한 구현인 동안 'worker contract'
클래스를 세우는 것은 `CLAUDE.md` §8 위반이다."* 여기서 계약은 **호출 가능한 것 하나**
(`Assignment` → `AttemptResult`)이고, 그 이상은 둘째 구현이 생기는 시점의 일이다.

**이 워커가 새로 만드는 실행 능력은 없다.** `kisia/runtime/agent_a.py` 의 `run_attempt`
가 이미 워크스페이스를 세우고 `AgentLoop` 을 돌리고 verifier 를 부르고 스트림을 낸다.
이 모듈이 더하는 것은 셋뿐이다:

1. **`Assignment` 을 그 함수의 인자로 옮긴다** — 어느 모델·어느 effort·어느 attempt id.
2. **결과를 스트림에서 읽는다.** `run_attempt` 가 돌려주는 notes 딕셔너리의 `solved` 를
   그대로 쓰지 않는다. 그 값은 `effort_mismatch` 를 모른다(실측: `LoopReport` 에는
   있고 `notes["loop"]` 에는 없다) — `ADR-0001` 무결성 규칙 1 이 실패 처리하라고 한
   run 이 `notes["solved"]=True` 로 나온다. 판정은 스트림의 `attempt.finished.outcome`
   에서 읽고, **자기 보고는 나란히 싣는다**(`CLAUDE.md` §6).
3. 배정한 라벨과 스트림이 적은 라벨을 **대조할 수 있게** 통제 블록의
   `accounting_label` 을 함께 읽는다 (`model.Attempt.label_disagreement`).

**워크스페이스 생성/파기는 이 트랙이 orchestrator 로 옮기지 않았다.**
`CLAUDECODE_WORKER_DESIGN.md` §4-① 의 그림은 그것을 orchestrator 에 두는데, 오늘 그
코드는 `run_attempt` 안에 있다(`agent_a.py`: `ws.create(...)` … `finally: ws.destroy()`).
옮기려면 `kisia/runtime/` 을 고쳐야 하고 이 트랙은 그것을 하지 않는다.
**옮긴 척하지 않는다** — 이 워커는 그 함수를 부르고, 워크스페이스의 수명은 그 함수의
것이다. verifier 호출(S8)도 같은 자리에 있다(`golden_a._verify`, 별도 프로세스).

**모델을 부르지 않고 컨테이너를 만들지 않는 검증은 어디까지 되는가.** 이 세션은
`run_attempt` 를 실제로 돌리지 않았다(`OPENAI_API_KEY` 없음 · docker 없음 · 호스트 접근
금지). 대신 두 가지를 잰다 — ① 판독기(`read_stream_outcome`)는 스트림에 대한 순수
함수이므로 그대로 시험한다. ② 기본 결선이 껍데기가 아니라는 것은
`inspect.signature(...).bind()` 로 잰다: 이 워커가 보내는 키워드 인자를 `run_attempt`
가 **실제로 받는지**를 호출 없이 확인한다.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from kisia.orchestrator.model import Assignment, AttemptResult
from kisia.runtime import agent_a

#: 기본 결선. **유형 A 하나뿐이다** — 유형 B 는 `service_image` 를, 유형 C 는 다른
#: 인자를 더 받는다(실측: 세 `run_attempt` 의 시그니처가 다르다). 셋을 하나로 덮는
#: 디스패처를 지금 만들지 않는다(`CLAUDE.md` §8): 호출자가 어느 것을 쓸지 알고 있고,
#: 여분 인자는 `fixed` 로 그대로 넘어간다.
DEFAULT_RUN_ATTEMPT: Callable[..., dict[str, Any]] = agent_a.run_attempt

#: 이 워커가 `Assignment` 에서 뽑아 넘기는 키워드. 나머지는 전부 `fixed` 에서 온다.
#: **`accounting_label`·`solve_k` 가 여기 있는 것이 `O-57` 이다** — 라벨의 출처를
#: `agent_a._control` 의 상수에서 배정으로 옮긴다. 옮기지 않으면 승격된 재시도의
#: 스트림이 계속 `clean` 을 적고(`PRODUCT_SKELETON.md` §5-a), `ADR-0003` 이 막으려던
#: 오염이 승격 경로로 들어온다.
ASSIGNED_KWARGS: tuple[str, ...] = (
    "out_path",
    "attempt",
    "model_id",
    "effort",
    "accounting_label",
    "solve_k",
)

#: 같은 진술이 몇 번 기록되면 *"같은 가설"* 로 세는가. **운영자가 rung 4 의 조건으로
#: 적은 숫자 그대로다** — *"새 증거 없이 3회 반복 / 같은 가설 2회"*
#: (`scheduler.OPERATOR_LADDER[3].trigger`). 다른 숫자를 고르지 않는다.
SAME_HYPOTHESIS_MIN = 2

#: 대회 후보에서 빼는 후보의 `method` 접두. `A-4` 는 하니스가 **일부러 어긋나게** 만든
#: 값이고(`agent_a._negative_candidate`), 운영자에게 올리면 틀린 것을 제출하게 된다.
PROBE_METHOD_PREFIX = "probe:"


class NativeWorkerError(RuntimeError):
    """attempt 를 돌릴 수 없거나 그 결과를 읽을 수 없다."""


@dataclass(frozen=True)
class StreamOutcome:
    """스트림에서 읽은 사실. **판정이 아니라 판독이다.**"""

    outcome: str
    verdicts: tuple[bool, ...]
    accounting_label: str | None
    #: `stall.observed.signal` 을 발행 순서대로.
    stall_signals: tuple[str, ...]
    #: `SAME_HYPOTHESIS_MIN` 회 이상 나온 `hypothesis.recorded.statement`.
    repeated_hypotheses: tuple[str, ...]
    #: 프로브가 아닌 `candidate.produced.value`.
    candidates: tuple[str, ...]
    usd_total: str
    model_calls: int


def read_stream_outcome(path: Path) -> StreamOutcome:
    """스트림에서 orchestrator 가 다음 rung 을 정하는 데 쓰는 값들을 읽는다. 순수 함수다.

    **검사기가 아니다.** S9 유효성(seq 빈틈·짝짓기)은 `kisia.checker` 의 일이고 판정
    원본은 evidence store 의 `judgment` 자리에 들어간다.

    `attempt.finished` 가 없으면 `outcome` 은 **빈 문자열이 아니라 `"unfinished"`** 다 —
    "끝나지 않았다"와 "실패했다"는 다른 값이고 접으면 거짓 관측이 된다(`CLAUDE.md` §6).
    같은 이유로 `usd_total` 옆에 `model_calls` 를 둔다: `0` 원이 "부르지 않았다"인지
    "불렀는데 0 이었다"인지 한 값으로 접히지 않게 한다.
    """
    outcome = "unfinished"
    verdicts: list[bool] = []
    label: str | None = None
    stalls: list[str] = []
    statements: Counter[str] = Counter()
    candidates: list[str] = []
    usd = Decimal(0)
    model_calls = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event: dict[str, Any] = json.loads(line)
        kind = event.get("type")
        if kind == "attempt.started":
            raw = event.get("accounting_label")
            label = None if raw is None else str(raw)
        elif kind == "verification.completed":
            verdicts.append(bool(event.get("verdict")))
        elif kind == "stall.observed":
            stalls.append(str(event.get("signal", "")))
        elif kind == "hypothesis.recorded":
            statements[str(event.get("statement", "")).strip()] += 1
        elif kind == "candidate.produced":
            if not str(event.get("method", "")).startswith(PROBE_METHOD_PREFIX):
                candidates.append(str(event.get("value", "")))
        elif kind == "model.completed":
            model_calls += 1
            usd += _usd(event.get("usd"))
        elif kind == "attempt.finished":
            outcome = str(event.get("outcome", "unfinished"))
    return StreamOutcome(
        outcome=outcome,
        verdicts=tuple(verdicts),
        accounting_label=label,
        stall_signals=tuple(stalls),
        repeated_hypotheses=tuple(
            s for s, n in statements.items() if s and n >= SAME_HYPOTHESIS_MIN
        ),
        candidates=tuple(candidates),
        usd_total=str(usd),
        model_calls=model_calls,
    )


def _usd(raw: Any) -> Decimal:
    """`model.completed.usd` 하나. **읽을 수 없으면 0 으로 접지 않고 죽는다** — 조용히
    0 이 되면 `--max-usd` 상한이 값을 잃고 잔고가 소진될 때까지 멈추지 않는다."""
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise NativeWorkerError(f"model.completed.usd 를 읽을 수 없다: {raw!r}") from exc


class NativeHarnessWorker:
    """`Assignment` 하나를 `run_attempt` 한 번으로 옮긴다.

    `fixed` 는 `Assignment` 에 담기지 않는 것 전부다 — fixture · pricing · image ·
    host_id · api_key · capability_probe 등. **`Assignment` 에 넣지 않는 이유**는
    `ADR-0003` §Decision-1 이 *"인증/provider 는 그 계약에 들어가지 않는다"* 로 적은
    그 경계다. 배정은 "어느 문제를 어느 모델로"이고, 키와 이미지는 배치의 사실이다.
    """

    def __init__(
        self,
        *,
        out_dir: Path,
        fixed: Mapping[str, Any],
        run_attempt: Callable[..., dict[str, Any]] = DEFAULT_RUN_ATTEMPT,
    ) -> None:
        overlap = sorted(set(fixed) & set(ASSIGNED_KWARGS))
        if overlap:
            raise NativeWorkerError(
                f"fixed 가 배정 인자를 덮어쓴다: {overlap} — 배정이 조용히 무시된다"
            )
        self.out_dir = out_dir
        self.fixed = dict(fixed)
        self._run_attempt = run_attempt

    def __call__(self, assignment: Assignment) -> AttemptResult:
        out_path = self.out_dir / f"{assignment.attempt_id}.jsonl"
        notes = self._run_attempt(
            out_path=out_path,
            attempt=assignment.attempt_id,
            model_id=assignment.model_id,
            effort=assignment.effort,
            # `O-57` — 라벨은 배정에서 온다. `agent_a._control` 의 상수가 아니다.
            accounting_label=assignment.accounting_label,
            solve_k=assignment.solve_k,
            **self.fixed,
        )
        stream = Path(str(notes["stream"])) if "stream" in notes else out_path
        if not stream.is_file():
            raise NativeWorkerError(
                f"solver 가 스트림을 남기지 않았다: {stream} — 판정할 대상이 없다"
            )
        read = read_stream_outcome(stream)
        self_reported = notes.get("solved")
        return AttemptResult(
            attempt_id=assignment.attempt_id,
            outcome=read.outcome,
            verdicts=read.verdicts,
            control_accounting_label=read.accounting_label,
            stream_path=stream,
            solver_self_reported_solved=(
                None if self_reported is None else bool(self_reported)
            ),
            stall_signals=read.stall_signals,
            repeated_hypotheses=read.repeated_hypotheses,
            candidates=read.candidates,
            usd_total=read.usd_total,
            model_calls=read.model_calls,
        )
