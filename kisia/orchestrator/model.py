"""Challenge · Attempt 의 상태 모델.

`CONTEST_ARCHITECTURE.md` §6 이 이름으로 요구한다: *"Challenge 전체의 상태와 각 Attempt
의 상태가 섞이면 안 된다."* 그래서 **`Challenge.state` 는 저장하지 않고 attempt 목록에서
파생시킨다** — 두 상태를 따로 저장하면 그것들이 어긋나는 경로가 생기고, §6 이 막으려는
것이 정확히 그 어긋남이다. 파생이면 어긋날 자리가 없다.

**`accounting_label` 은 attempt 가 만들어지는 시점에 붙는다** (`ADR-0003` §Consequences:
*"모든 Attempt 는 생성 시점에 clean / solve@k / contest 라벨이 붙어야 하고, holdout
Attempt 는 clean 라벨만 허용한다"*). 값 집합은 `kisia.runtime.telemetry.control` 에서
가져온다 — **여기서 다시 적지 않는다.** 두 벌 두면 갈리고, 갈리면 어느 쪽이 canon 을
나르는지 알 수 없게 된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kisia.runtime.telemetry.control import ACCOUNTING_LABELS

#: 봉인된 세트. 이 값에서만 `ADR-0003` §Consequences 의 홀드아웃 규칙이 발동한다.
#: **네 값의 어휘는 `TELEMETRY_SCHEMA.md` §2 가 이미 적었고**
#: (`dev | regression-private | final-holdout | calibration`) 여기서 다시 적지 않는다 —
#: 두 벌 두면 갈린다. 이 모듈이 아는 것은 넷 중 **하나의 이름**뿐이면 충분하다.
FINAL_HOLDOUT = "final-holdout"

#: 살아 있는 대회. `R5-10` 이 `challenge_set` 열거에 더한 값이고, `R5-9` 의
#: `accounting_label: contest` 와 짝이다. **이 세트의 run 은 `clean_solve@1` 의 분자에도
#: 분모에도 들어가지 않는다**(`MVP_SCOPE.md` §6) — 그 격리를 나르는 것이 라벨이므로
#: `Orchestrator._label_for` 가 이 값을 보고 라벨을 정한다.
CONTEST = "contest"

#: `Challenge` 가 가질 수 있는 넷. **attempt 목록에서만 파생된다.**
#: `unsolved` 는 "사다리가 끝났다"가 아니다 — 그것은 scheduler 의 사실이고 여기서
#: 알 수 없다. 여기서 아는 것은 "끝난 attempt 가 있고 그중 verified 가 없다"뿐이다.
CHALLENGE_STATES: frozenset[str] = frozenset({"queued", "running", "solved", "unsolved"})


@dataclass(frozen=True)
class Assignment:
    """orchestrator 가 solver 에게 넘기는 것. **문제 하나 · solver 하나 · 시도 하나.**

    `CONTEST_ARCHITECTURE.md` §4 의 *"문제 하나를 solver 하나에 통째로 할당한다"* 다.
    """

    attempt_id: str
    challenge_id: str
    challenge_set: str
    #: `clean` | `solve@k` | `contest`. 파생 규칙은 `Orchestrator._label_for` 다.
    accounting_label: str
    #: 이 문제에 대한 **몇 번째 시도인가**. 라벨과 함께 통제 블록으로 내려간다
    #: (`TELEMETRY_SCHEMA.md` §2 의 `solve_k`). `agent_a._control` 이 `1` 을 박아 둔
    #: 자리를 배정이 대신 채운다 — `O-57`.
    solve_k: int
    #: `Rung` 을 통째로 담지 않는다 — 배정된 사실은 값 셋이고, rung 객체를 담으면
    #: 사다리가 바뀔 때 지난 배정의 뜻이 함께 바뀐다.
    rung_name: str
    model_id: str
    effort: str

    def __post_init__(self) -> None:
        if self.accounting_label not in ACCOUNTING_LABELS:
            raise ValueError(
                f"accounting_label 은 {sorted(ACCOUNTING_LABELS)} 중 하나다 "
                f"(ADR-0003 §Consequences): {self.accounting_label!r}"
            )
        if self.solve_k < 1:
            raise ValueError(f"solve_k 는 1 이상이다 (첫 시도가 1): {self.solve_k}")


@dataclass(frozen=True)
class AttemptResult:
    """attempt 하나가 끝나고 **스트림에서 읽은** 사실.

    **solver 의 자기 보고와 스트림에서 읽은 값을 나란히 싣고 접지 않는다**
    (`CLAUDE.md` §6, `spec.md` §0.3-3). 둘이 갈리는 것이 사실이면 그 사실이 기록에
    남아야 하고, 한 필드로 접으면 남지 않는다.
    """

    attempt_id: str
    #: `attempt.finished.outcome`. `solved` | `failed`.
    outcome: str
    #: 이 attempt 의 모든 `verification.completed.verdict`. **verifier 는 별도
    #: 프로세스다**(S8, `PATH_SCOPE.md` §1).
    verdicts: tuple[bool, ...]
    #: 스트림의 통제 블록이 **실제로 적은** 라벨. 배정한 것과 다를 수 있고, 다르면
    #: 그것이 기록돼야 한다 — `Attempt.label_disagreement`.
    control_accounting_label: str | None
    stream_path: Path | None
    #: solver 가 자기 notes 에 적은 값. **판정에 쓰지 않는다.**
    solver_self_reported_solved: bool | None
    #: 이 attempt 에서 하니스가 **관측한** stall 신호(`stall.observed.signal`).
    #: 모델의 자기 보고가 아니다 — 발행자는 `kisia/runtime/loop.py::_observe_stalls` 이고
    #: 다섯 신호 전부 loop 이 이미 쥔 계수에서 나온다(실측 2026-08-09).
    stall_signals: tuple[str, ...]
    #: 같은 진술이 `SAME_HYPOTHESIS_MIN` 회 이상 기록된 가설. 운영자가 rung 4 의 조건으로
    #: 적은 *"같은 가설 2회"* 가 이 값이다.
    repeated_hypotheses: tuple[str, ...]
    #: 이 attempt 가 낸 후보 flag. **하니스의 음성 프로브(`method: probe:*`)가 낸 것은
    #: 빠져 있다** — 그것은 일부러 틀리게 만든 값이고 대회 후보로 올리면 운영자가 틀린
    #: 것을 제출한다.
    candidates: tuple[str, ...]
    #: 스트림의 `model.completed.usd` 합. **`model_calls` 와 나란히 둔다** — 0 원이
    #: "안 불렀다"인지 "불렀는데 0 이었다"인지를 한 값으로 접지 않기 위해서다.
    usd_total: str
    model_calls: int

    @property
    def stalled(self) -> bool:
        """rung 4(deepen)로의 승격 조건이 관측됐는가.

        **두 숫자만 쓴다** — 창 3턴(`loop.STALL_WINDOW_TURNS`)과 같은 가설 2회
        (`native.SAME_HYPOTHESIS_MIN`). 운영자가 적은 것이 *"새 증거 없이 3회 반복 /
        같은 가설 2회"* 이고, 다른 숫자를 넣으면 재지 않은 값이 기본값이 된다
        (`scheduler.py` 머리말).
        """
        return bool(self.stall_signals) or bool(self.repeated_hypotheses)

    @property
    def verified(self) -> bool:
        """이 attempt 가 verified solve 인가.

        **`verdicts` 에 참이 있다는 것만으로는 아니다.** `ADR-0001` 무결성 규칙 1 이
        effort 가 어긋난 run 을 실패 처리하라고 적고, `agent_a` 가 그것을
        `attempt.finished.outcome` 에 반영한다 — flag 를 맞혔는지와 run 의 처분은
        다른 사실이다. 그래서 처분을 읽는다. 맞힌 사실은 `verdicts` 가 따로 나른다.
        """
        return self.outcome == "solved"


@dataclass
class Attempt:
    """배정 하나와 그 결과. **결과가 `None` 이면 아직 돌고 있다.**"""

    assignment: Assignment
    result: AttemptResult | None = None

    @property
    def finished(self) -> bool:
        return self.result is not None

    @property
    def verified(self) -> bool:
        return self.result is not None and self.result.verified

    @property
    def label_disagreement(self) -> bool:
        """배정한 라벨과 스트림이 적은 라벨이 갈렸는가.

        **지금 이 값은 참이 될 수 있고, 그것은 결함이 아니라 관측이다.**
        `agent_a._control` 이 `accounting_label` 을 `"clean"` 으로 박아 두었으므로
        (실측 2026-08-09, `kisia/runtime/agent_a.py`), 승격된 재시도(rung 2 이상)를
        이 orchestrator 로 돌리면 스트림에는 여전히 `clean` 이 적힌다. 고치는 것은
        `kisia/runtime/` 편집이고 이 트랙의 범위가 아니다 — **조용히 넘기지 않고 여기서
        보이게 한다.**
        """
        if self.result is None or self.result.control_accounting_label is None:
            return False
        return self.result.control_accounting_label != self.assignment.accounting_label


@dataclass
class Challenge:
    """문제 하나와 그것에 대한 시도들."""

    challenge_id: str
    challenge_set: str = "dev"
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def state(self) -> str:
        if not self.attempts:
            return "queued"
        if any(not a.finished for a in self.attempts):
            return "running"
        if any(a.verified for a in self.attempts):
            return "solved"
        return "unsolved"

    @property
    def last(self) -> Attempt | None:
        return self.attempts[-1] if self.attempts else None
