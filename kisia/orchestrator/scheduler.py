"""scheduler — 승격 정책의 **축**만 세운다. 기본값은 세우지 않는다.

`ADR-0003` "이 문서가 정하지 않고 열어 둔 것" 이 **스케줄링 기본값을 `calibration@1`
뒤로 묶었다.** 그러므로 이 모듈이 정하는 것과 정하지 않는 것을 먼저 가른다.

**정하는 것 — 축 하나.**

1. 사다리는 **순서 있는 rung 의 열**이다.
2. **verified solve 가 나오면 멈춘다** (`CONTEST_ARCHITECTURE.md` §4: *"첫 verified
   solve 가 승자"*, *"첫 verified solve 가 나오면 나머지 attempt 를 중단한다"*).
3. 아니면 다음 rung 으로 간다. 사다리 끝이면 더 없다.

**정하지 않는 것 — 넷. 재지 않았으므로 코드가 값을 갖지 않는다.**

- **승격 조건의 임계값.** 운영자의 사다리는 rung 4 를 *"새 증거 없이 3회 반복 / 같은
  가설 2회"*, rung 5 를 *"exploit branch 2개 실패"* 로 적는다. **이 저장소는 그 셋 중
  어느 것도 잰 적이 없다.** 그래서 `Rung.trigger` 는 **문자열로 나르고 술어로 만들지
  않는다** — 임계값을 코드에 넣는 순간 재지 않은 값이 기본값이 된다.

  **예선 MVP 가 그중 rung 4 하나를 술어로 잇는다** (`MVP_SCOPE.md` §4-D: *"승격 사다리를
  실제로 도는 코드가 없다"*). 그러나 **새 숫자를 고르지 않았다** — 쓰는 것은 운영자가
  적은 둘뿐이다: 창 3턴은 이미 `loop.STALL_WINDOW_TURNS` 가 세고 있고(`stall.observed`
  의 발행자), 같은 가설 2회는 `native.SAME_HYPOTHESIS_MIN` 이다. 그리고 그 이음은
  **이 상수가 아니라 `Scheduler(stall_rung=...)` 라는 인자로 들어온다** — 사다리는
  전사 그대로 남고, 정책은 호출자가 고른다. `stall_rung` 을 주지 않은 scheduler 는
  이 모듈이 원래 하던 그대로 순서대로만 오른다.
- **rung 5·6 의 승격 조건**(*"exploit branch 2개 실패"*)은 여전히 술어가 아니다.
  두 rung 은 effort 가 미정이라 애초에 돌지 않으므로(아래) 이을 자리도 없다.
- **Native-first 순차인가 speculative race 인가.** `ADR-0003` 이 열어 둔 것이다.
  이 골격은 **순차로만 돈다** — race 를 구현하지 않는다. 안 정한 것을 코드로 정하지
  않기 위해서이고, race 가 필요해지면 그때가 그 결정의 자리다.
- **head-start T · 카테고리 라우팅.** `ADR-0003` §4 · `EVAL_CONTRACT.md` :96.
  능력 계층이 없어 카테고리는 지금 측정 불가다.
- **quota 반영.** `CLAUDECODE_WORKER_DESIGN.md` §4-⑦: 한도·소진 신호·재설정 주기를
  하나도 재지 않았다. **자기 보고 달러(`total_cost_usd`)를 판정에 쓰지 않는다**
  (`CLAUDE.md` §6).

**두 rung 은 지금 돌릴 수 없고, 그 사실을 `None` 이 나른다.** 운영자가 rung 5 를
*"Sol high~xhigh"*, rung 6 을 *"Sol standard/max 또는 pro/xhigh (A/B)"* 로 **범위와
선택지로** 적었다. 하나를 고르는 것은 이 세션이 할 수 없는 결정이므로
`reasoning_effort=None` 으로 두고 `is_runnable` 이 거짓이 된다. **"미정"과 "medium"을
접지 않는다** (`CLAUDE.md` §6). rung 6 의 `pro` 쪽 가지는 그와 별개로 **전송 계층이
보낼 수 없다** — `kisia/runtime/model.py` 의 페이로드가 `{"effort": ...}` 하나다(실측,
`NEXT_SESSION.md` §3.5-2).

**사다리 1~3 과 4~6 은 읽는 결이 다르다.** 1~3(*"분류·파일 조사" → "최초 공격 계획" →
"계획에 따른 반복 실행"*)은 한 attempt 안의 **국면**으로 읽히고, 4~6 은 막혔을 때의
**재시도 승격**으로 읽힌다. 운영자는 그것을 한 사다리 여섯으로 적었다
(`NEXT_SESSION.md` §3.5). **이 모듈은 그 원문을 그대로 여섯으로 나르고, 국면인지
재시도인지는 해석하지 않는다** — 해석하면 운영자가 적지 않은 것을 코드가 정하게 된다.
`Scheduler` 가 실제로 쓰는 성질은 "순서"뿐이다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rung:
    """사다리의 한 칸. **모델과 effort 는 여기서만 정해진다.**

    `config/models.yaml` 의 `roles` 와 겹치지만 같은 것이 아니다 — 저쪽은 역할별 배정
    (`R5-8`)이고 이쪽은 승격 순서다. `D-80` 이 그 둘을 한 필드에 싣지 말라고 적었고,
    같은 이유로 이 모듈은 `models.yaml` 을 **읽지 않는다**: 읽으면 `fallbacks` 와
    승격이 한 파일에서 두 뜻이 된다.
    """

    #: 사다리 안에서 유일한 이름. attempt 기록이 이것을 나른다.
    name: str
    model_id: str
    #: **`None` 은 "미정"이지 "기본값"이 아니다.** 머리말의 rung 5·6 을 보라.
    reasoning_effort: str | None
    #: 운영자가 적은 승격 조건의 **원문**. 술어가 아니다 — 머리말을 보라.
    trigger: str

    @property
    def is_runnable(self) -> bool:
        """이 rung 으로 attempt 를 시작할 수 있는가."""
        return self.reasoning_effort is not None


#: 운영자의 승격 정책 여섯 (`NEXT_SESSION.md` §3.5, `REBUILD_LOG.md` 프로덕션-2 §7).
#: **전사이지 결정이 아니다.** `Scheduler` 는 사다리를 인자로 받고 이 상수를 기본값으로
#: 쓰지 않는다 — 기본값으로 두면 `ADR-0003` 이 열어 둔 자리를 import 한 번이 닫는다.
OPERATOR_LADDER: tuple[Rung, ...] = (
    Rung("triage", "gpt-5.6-luna", "medium", "분류·파일 조사"),
    Rung("plan", "gpt-5.6-terra", "high", "최초 공격 계획"),
    Rung("execute", "gpt-5.6-terra", "medium", "계획에 따른 반복 실행"),
    Rung("deepen", "gpt-5.6-terra", "xhigh", "새 증거 없이 3회 반복 / 같은 가설 2회"),
    Rung(
        "escalate",
        "gpt-5.6-sol",
        None,
        "exploit branch 2개 실패 / 핵심 난제 잔존 (Sol high~xhigh)",
    ),
    Rung(
        "final",
        "gpt-5.6-sol",
        None,
        "마지막 quality-first 시도 (Sol standard/max 또는 pro/xhigh, A/B)",
    ),
)


class SchedulerError(ValueError):
    """사다리를 세울 수 없다."""


class Scheduler:
    """사다리 하나를 쥐고 다음 rung 을 답한다. **그것이 전부다.**

    큐 순서·병렬성·slot 배정은 여기 없다. `CONTEST_ARCHITECTURE.md` §5 가 그것들을
    묻지만 `ADR-0003` 이 답을 `calibration@1` 뒤로 묶었고, 답이 없는 질문에 코드를
    먼저 쓰지 않는다(`CLAUDE.md` §8).
    """

    def __init__(self, ladder: tuple[Rung, ...], *, stall_rung: str | None = None) -> None:
        """`stall_rung` 을 주면 **그 rung 부터는 stall 이 관측돼야 오른다.**

        운영자가 rung 4 를 *"새 증거 없이 3회 반복 / 같은 가설 2회"* 로 적었다 — 그것은
        순서가 아니라 **조건**이다. 조건을 무시하고 순서로만 오르면 막히지 않은 attempt
        도 xhigh 로 올라가고, 반대로 조건만 보고 순서를 버리면 1·2·3 국면을 건너뛴다.
        그래서 규칙은 하나다: **평소에는 순서대로, stall 이 관측되면 이 rung 으로
        건너뛴다. 관측되지 않았으면 이 rung 앞에서 사다리가 끝난다.**

        **기본값은 `None` 이다** — 주지 않으면 이 모듈은 순서만 아는 원래의 축이다.
        정책을 상수로 박으면 `ADR-0003` 이 열어 둔 자리를 import 한 번이 닫는다.
        """
        if not ladder:
            raise SchedulerError("사다리가 비어 있다 — 시작할 rung 이 없다")
        names = [r.name for r in ladder]
        if len(set(names)) != len(names):
            raise SchedulerError(f"rung 이름이 겹친다: {names}")
        self.ladder = ladder
        self.stall_rung = stall_rung
        self._stall_at = None if stall_rung is None else self.index_of(stall_rung)

    @property
    def first(self) -> Rung:
        return self.ladder[0]

    def index_of(self, name: str) -> int:
        for i, candidate in enumerate(self.ladder):
            if candidate.name == name:
                return i
        raise SchedulerError(f"이 사다리에 없는 rung 이다: {name!r}")

    def by_name(self, name: str) -> Rung:
        """이름으로 되찾는다. 배정 기록은 rung 객체가 아니라 이름을 나르므로
        (`model.Assignment.rung_name`) 되찾는 자리가 하나 필요하다."""
        return self.ladder[self.index_of(name)]

    def next_after(self, rung: Rung, *, verified: bool, stalled: bool = False) -> Rung | None:
        """직전 attempt 의 결과를 받아 다음 rung 을 답한다. 없으면 `None`.

        **`verified` 도 `stalled` 도 solver 의 자기 보고가 아니다** — 둘 다 스트림에서
        읽은 값이고, 그 판독은 `kisia.orchestrator.native.read_stream_outcome` 이 한다.
        `stalled` 는 `stall_rung` 을 주지 않은 scheduler 에서는 아무 일도 하지 않는다.
        """
        if verified:
            return None
        nxt = self.index_of(rung.name) + 1
        if self._stall_at is not None:
            if stalled:
                # 건너뛴다. **되돌리지는 않는다** — 이미 그보다 위에 있으면 순서가 이긴다.
                nxt = max(nxt, self._stall_at)
            elif nxt == self._stall_at:
                # **문은 이 칸 하나에만 달려 있다.** 그 위의 rung 들은 운영자가 다른
                # 조건(*"exploit branch 2개 실패"*)을 적었고 그것은 잰 적이 없으므로,
                # 여기서 stall 을 그 조건의 대역으로 쓰지 않는다 — 쓰면 재지 않은
                # 술어를 하나 더 만드는 것이 된다.
                return None
        return self.ladder[nxt] if nxt < len(self.ladder) else None
