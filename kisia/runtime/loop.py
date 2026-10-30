"""agent loop — 모델이 도구를 고른다. 단일 executor.

`spec.md` §0.2 가 loop 의 형태를 정하지 않고 `SEAM_IMPLEMENTATION_MAP.md` §8-3 이
그것을 재빌드의 판단으로 남겼다. **플래너를 두지 않는다** — gate 1(Responses
transport)과 `N_open`(모델이 도구를 쓰기로 고르는가) 어느 것도 플래너를 요구하지
않고, 요구되지 않은 구조는 `CLAUDE.md` §8 이 금지한다.

**이 모듈이 재는 것은 배관이 아니라 통합이다.** `SEAM_IMPLEMENTATION_MAP.md` §4 가
재빌드에 지운 책임 셋이 여기 있다 — 도구 표면을 **매 턴** 프롬프트에 싣고(§4-1),
선언된 대상의 host·port 를 채운 **완성된 호출문**을 싣고(§4-2), 통합이 성립했는지를
telemetry 로 잰다(§4-3). 셋째가 `N_open` 이다.

---

**모델 이벤트 둘을 응답이 돌아온 **뒤에** 쓴다.** `TELEMETRY_SCHEMA.md` §3 이
`input_tokens`·`cached_tokens`·`cache_write_tokens`·`reasoning_tokens` 를
`model.requested` 에 두는데 **넷 다 응답에서 온다.** 보내는 시점에는 알 수 없으므로
둘 다 응답 뒤에 쓴다. `seq` 는 §3.2.1 이 정한 대로 **쓰기 순서**이고 발생 순서가
아니며, 걸린 시간은 `model.completed.latency_ms` 가 나른다.

**대화는 항목 배열로 자란다.** 재빌드-7 진단 6c: 문자열로 보내면 접두가 같아도 꼬리가
다르면 캐시가 빗나가고, 항목을 append 하면 맞는다. cache write 는 입력의 1.25배
요율이라 이 차이가 실행 비용을 10배 가른다.

---

**§5 예약 이벤트의 발행자가 여기 있다** (`O-38`, `D-70`). `TELEMETRY_SCHEMA.md` §5.2
가 셋을 필드까지 정의하고 조립기가 허용 목록에 실었는데 **발행하는 코드가 없었고**,
컴파일러를 먼저 지으면 입력이 0건이다. 발행 주체를 **사실의 출처**로 가른다:

- `hypothesis.recorded` · `hypothesis.rejected` — **모델이 부르는 도구.** `statement`
  와 `confidence` 는 정의상 모델의 진술이고 하니스가 추론해 채우면 날조다.
- `stall.observed` — **하니스.** 다섯 신호는 이 loop 이 이미 쥔 계수에서 나온다.
  모델에게 물으면 자기 보고가 되고 `CLAUDE.md` §6 이 그것을 증거로 쓰지 말라고 한다.

**술어를 붙이지 않는다** (`TELEMETRY_SCHEMA.md` §5.1, `R2-15`). 이 이벤트들은
`spec.md` §2 의 어떤 술어에도 등장하지 않으므로 어떤 seam 판정도 움직이지 않고,
비어 있다는 이유로 FAIL 이 나지 않는다.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from kisia.runtime.golden_a import Recorder, _sha, _shatext
from kisia.runtime.model import ModelCall, ResponsesClient, tool_schema
from kisia.runtime.telemetry.envelope import EnvelopeWriter

#: stall 신호를 재는 창(턴). 계약이 값을 정하지 않았다 — `D-72`.
STALL_WINDOW_TURNS = 3

#: `budget_burn` 이 **관측되는** 지점. "예산을 낭비했다"는 판정이 아니라 "예산의 이
#: 비율을 넘긴 것을 봤다"는 관측이다 (`R2-7` 이 P-S6-a 에 세운 자세).
BUDGET_BURN_FRACTION = Decimal("0.5")

#: `confidence_collapse` — 최고치 대비 이 비율 이하로 떨어진 것을 봤다.
CONFIDENCE_COLLAPSE_RATIO = 0.5

#: 같은 (도구, args_digest) 가 창 안에서 이 횟수 이상 나타났다.
REPEATED_ACTION_MIN = 2

#: 연속으로 실패한 도구 호출의 수.
TOOL_ERROR_STREAK_MIN = 2

#: stall 요청에 실을 관찰 id 의 최대 개수. 넘으면 **잘렸다는 사실을 함께 적는다** —
#: 조용히 자르면 모델이 목록을 전부로 읽는다.
STALL_REQUEST_MAX_IDS = 20


class TrackingRecorder(Recorder):
    """관찰 id 를 순서대로 쥐고 있는 `Recorder`.

    모델이 낸 후보의 `derived_from[]` 을 채우려면 **그 모델이 실제로 본 관찰**의
    목록이 필요하다. 검사기는 그 선언을 믿지 않고 스스로 파생을 찾지만(S7.2), 선언이
    비어 있으면 라이트업 소비자가 (c)를 잃는다(`TELEMETRY_SCHEMA.md` §4.1).
    """

    def __init__(self, writer: EnvelopeWriter, limit: int) -> None:
        super().__init__(writer, limit)
        self.ids: list[str] = []

    def observe(
        self, source_ref: str, full: bytes, *, artifact_id: str | None = None
    ) -> str:
        oid = super().observe(source_ref, full, artifact_id=artifact_id)
        self.ids.append(oid)
        return oid


@dataclass
class ToolOutcome:
    """도구 하나의 결과. **관찰은 바이트다** — 도구가 요약해서 주지 않는다."""

    output: bytes
    exit_code: int
    #: 모델에게 돌려줄 문자열. 비우면 관찰의 `shown` 을 쓴다.
    reply: str | None = None
    artifact_ids: list[str] = field(default_factory=list)
    #: 도구가 **이미 만든** 관찰의 id. 이것을 주면 loop 이 관찰을 또 만들지 않고
    #: `tool.completed` 에 이 id 를 잇는다. 없으면 S4.1 이 "출력 연결이 없다"로
    #: 거짓이 된다 — 유형 B 첫 실행의 `session_open` 이 실제로 그랬다.
    observation_id: str | None = None
    #: 이 호출이 attempt 를 끝내는가 (제출 등).
    terminal: bool = False
    #: 관찰로 기록하지 않는다 — 제출처럼 환경을 읽지 않는 도구.
    observe: bool = True


@dataclass
class Tool:
    name: str
    description: str
    properties: dict[str, Any]
    required: list[str]
    run: Callable[[dict[str, Any]], ToolOutcome]

    def schema(self) -> dict[str, Any]:
        return tool_schema(self.name, self.description, self.properties, self.required)


@dataclass
class LoopReport:
    turns: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    #: **이 loop 이 여는 세션의 수가 아니라, 모델이 열기로 고른 수다.**
    sessions_opened: int = 0
    usd: Decimal = Decimal(0)
    stop_reason: str = ""
    #: provider 가 되돌려 준 effort 가 **우리가 보낸 값**과 다르다 (조용한 강등·승격).
    degraded: bool = False
    #: provider 가 되돌려 준 effort 가 **통제 블록이 선언한 값**과 다르다.
    #: 음성 대조에서 참이 된다. ADR-0001 무결성 규칙 1 이 이 run 을 **실패 처리**하라고
    #: 적으므로, `attempt.finished.outcome` 이 `failed` 가 되는 근거다 — flag 를
    #: 맞혔는지와 별개의 사실이다.
    effort_mismatch: bool = False
    #: 모델이 도구를 하나도 부르지 않고 끝낸 턴의 수. 통합 실패의 다른 얼굴이다.
    turns_without_tool_call: int = 0
    #: 모델이 발행한 §5 예약 이벤트의 수.
    hypotheses_recorded: int = 0
    hypotheses_rejected: int = 0
    #: 하니스가 **관측한** stall 신호. 신호마다 attempt 당 한 번이다.
    stall_signals: list[str] = field(default_factory=list)
    #: **계기가 없어 재지 못한** 신호. `CLAUDE.md` §6 — "수행하지 못함"과 "0"은
    #: 다른 값이고 접으면 거짓 관측을 기록한다(`D-63` 이 같은 자리에서 났다).
    #: 이 목록이 비어 있지 않은데 `stall_signals` 가 비어 있으면 "멈추지 않았다"가
    #: 아니라 "재지 못했다"이다.
    stall_signals_not_evaluated: list[str] = field(default_factory=list)
    #: 가설 도구가 표면에 올라간 턴. `None` 이면 끝까지 올라가지 않았다 — 그 run 은
    #: 막히지 않았다는 뜻이고, 가설이 0건인 것이 정상이다.
    hypothesis_tools_exposed_at_turn: int | None = None


class AgentLoop:
    """모델 · 도구 · 봉투를 잇는다. 챌린지 유형을 모른다."""

    def __init__(
        self,
        *,
        writer: EnvelopeWriter,
        #: **`Recorder` 가 아니라 `TrackingRecorder` 다.** 예약 이벤트의
        #: `supported_by[]`·`confirmed_facts[]` 를 하니스가 채우려면 **실제로
        #: 기록된** 관찰 id 목록이 필요하고 그것을 쥔 것은 이 하위형뿐이다.
        recorder: TrackingRecorder,
        client: ResponsesClient,
        tools: list[Tool],
        system_prompt: str,
        task_prompt: str,
        max_turns: int,
        usd_budget: Decimal,
        state_locations: Callable[[], list[dict[str, Any]]],
        live_session_ids: Callable[[], list[str]] | None = None,
        jar_digest: Callable[[], str | None] | None = None,
        artifact_count: Callable[[], int] | None = None,
        #: 음성 대조 전용. 통제 블록이 선언한 값과 **다른** effort 로 보낸다.
        send_effort: str | None = None,
        fail_on_degradation: bool = True,
        #: **턴이 시작되기 전에 하니스가 개입한다.** `state.snapshot` 보다 **앞에서**
        #: 불리므로 그 스냅숏이 개입 뒤의 상태를 싣는다 — `golden_c` 의 C-4 가
        #: `drop → _turn(...)` 순서인 것과 같다. P-S6-a(선언된 상태 소재를 턴 사이에
        #: 버린다)가 모델 주도 run 에서 설 수 있는 유일한 자리다.
        on_turn: Callable[[int], None] | None = None,
        #: 같은 문제에 대한 시도 묶음의 식별자 (`TELEMETRY_SCHEMA.md` §5.2).
        #: **주지 않으면 §5 예약 이벤트를 발행하지 않는다** — 스키마가 두
        #: 이벤트에서 이 필드를 요구하므로 값 없이 발행하면 결손이다. 계약이 값을
        #: 정하지 않았고 저장소 어디에도 출처가 없었다(`D-71`).
        attempt_family: str | None = None,
    ) -> None:
        self.w = writer
        self.rec = recorder
        self.client = client
        self.tools = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self.task_prompt = task_prompt
        self.max_turns = max_turns
        self.usd_budget = usd_budget
        self._state_locations = state_locations
        self._live = live_session_ids or (lambda: [])
        self._jar = jar_digest or (lambda: None)
        self._artifacts = artifact_count or (lambda: 0)
        self.send_effort = send_effort
        self.fail_on_degradation = fail_on_degradation
        self._on_turn = on_turn
        self.attempt_family = attempt_family

        self._items: list[dict[str, Any]] = []
        self._op = 0
        self._artifact_n = 0
        self._pending_observations: list[str] = []
        self.report = LoopReport()

        # -- §5 예약 이벤트의 상태 -------------------------------------------
        self._turn = 0
        self._hyp_n = 0
        #: hypothesis_id → 기록 시점의 사실. `rejected` 는 두 번 기각을 막는다.
        self._hyps: dict[str, dict[str, Any]] = {}
        #: (턴, confidence). 기록한 것만 들어간다 — null 은 값이 아니다.
        self._confidences: list[tuple[int, float]] = []
        #: **환경에서 온** 관찰의 id. 하니스 자신의 도구가 만든 관찰은 세지 않는다 —
        #: `O-36`/경고 13: 관측 장치를 관측 대상 안에 넣으면 값이 조용히 틀린다.
        #: 넣으면 `record_hypothesis` 를 부를 때마다 관찰이 하나 생겨
        #: `no_new_observation` 이 영원히 뜨지 않는다.
        self._env_obs: list[str] = []
        #: 턴 시작 시점의 `len(self._env_obs)`.
        self._obs_at_turn: dict[int, int] = {}
        #: (턴, 도구, args_digest).
        self._actions: list[tuple[int, str, str]] = []
        self._error_streak = 0
        self._error_streak_turn = 0
        #: 이미 발행한 신호. 신호마다 attempt 당 한 번이다 (`D-73`).
        self._signals_seen: set[str] = set()
        #: 하니스 자신의 도구 이름. 위 `_env_obs` 의 판별에 쓴다.
        self._own_tools: set[str] = set()
        #: **stall 이 관측되기 전까지 표면에 올리지 않는다** (`D-74`). 실측이 근거다 —
        #: 항상 노출했더니 유형 B 4 run 중 2 run 에서 모델이 세션을 둘로 갈랐고
        #: `S4.2` 가 거짓이 됐다(대조군은 같은 날 4/4 참, 여유 5~6). 얻은 것은 없었다:
        #: 14 attempt 에서 모델이 이 도구를 **한 번도 부르지 않았다.** 막히지 않은
        #: 모델은 가설을 적을 이유가 없고, escalation 은 정의상 **막힌** attempt 의
        #: 것이다(`SEAM_IMPLEMENTATION_MAP.md` §6).
        self._latent_tools: list[Tool] = (
            self._hypothesis_tools(attempt_family) if attempt_family is not None else []
        )
        for t in self._latent_tools:
            self._own_tools.add(t.name)

    # -- 프롬프트 -------------------------------------------------------------

    def _tool_surface(self) -> str:
        """§4-1·§4-2 — 도구가 있다는 것을 **매 턴** 싣고, 완성된 호출문을 함께 싣는다.

        스파이크가 잰 차이가 이것이다: 설명문만으로는 모델이 세션을 열지 않았고
        (X 0/4), 완성된 호출 문장을 매 턴 실은 arm 만 4/4 로 열었다
        (`SEAM_IMPLEMENTATION_MAP.md` §3.3).
        """
        lines = ["Tools available this turn:"]
        for t in self.tools.values():
            lines.append(f"- {t.name}: {t.description}")
        return "\n".join(lines)

    # -- §5 예약 이벤트: 모델이 발행하는 둘 -------------------------------------

    def _hypothesis_tools(self, family: str) -> list[Tool]:
        """`hypothesis.recorded` · `hypothesis.rejected` 를 내는 도구 둘.

        **`supported_by[]`·`refuted_by[]` 는 모델의 주장이 아니라 하니스가 거른
        결과다.** 모델이 존재하지 않는 관찰 id 를 대면 그 자리는 비고, 주장 원문은
        `tool.requested.args` 에 그대로 남는다 — 출처가 다른 두 값이 한 스트림에
        나란히 있게 되고, 그것이 `CLAUDE.md` §6 이 요구하는 형태다. 검사기가 선언을
        믿지 않고 스스로 파생을 찾는 S7.2 와 같은 자세이기도 하다.

        **두 도구 다 관찰을 만든다** (`ToolOutcome.observe` 기본값). S4.1 이 모든
        `tool.completed` 에 출력 연결을 요구하므로 끄면 지금 참인 술어가 거짓이
        된다 — `submit_flag` 가 실제로 그 자리에서 잡혔다.
        """

        def record(args: dict[str, Any]) -> ToolOutcome:
            self._hyp_n += 1
            hid = f"hyp-{self._hyp_n:02d}"
            statement = str(args.get("statement", "")).strip()
            confidence = _as_confidence(args.get("confidence"))
            if confidence is not None:
                self._confidences.append((self._turn, confidence))
            claimed = [str(x) for x in _as_list(args.get("supported_by"))]
            known = set(self.rec.ids)
            grounded = [oid for oid in claimed if oid in known]
            self.w.emit(
                "hypothesis.recorded",
                {
                    "hypothesis_id": hid,
                    "statement": statement,
                    "confidence": confidence,
                    "supported_by": grounded,
                    "attempt_family": family,
                    "turn": self._turn,
                },
            )
            self._hyps[hid] = {"statement": statement, "rejected": False}
            self.report.hypotheses_recorded += 1
            dropped = len(claimed) - len(grounded)
            reply = f"recorded {hid}"
            if dropped:
                reply += f" ({dropped} unobserved id(s) dropped from supported_by)"
            return ToolOutcome(reply.encode("utf-8"), 0, reply=reply)

        def reject(args: dict[str, Any]) -> ToolOutcome:
            hid = str(args.get("hypothesis_id", "")).strip()
            entry = self._hyps.get(hid)
            if entry is None:
                # 없는 가설을 기각한 것으로 만들지 않는다. 이벤트를 내지 않고
                # 오류로 돌려준다 — `tool.requested` 에 시도가 남는다.
                reply = f"no such hypothesis: {hid or '(empty)'}"
                return ToolOutcome(reply.encode("utf-8"), 1, reply=reply)
            if entry["rejected"]:
                reply = f"{hid} is already rejected"
                return ToolOutcome(reply.encode("utf-8"), 1, reply=reply)
            claimed = [str(x) for x in _as_list(args.get("refuted_by"))]
            known = set(self.rec.ids)
            grounded = [oid for oid in claimed if oid in known]
            self.w.emit(
                "hypothesis.rejected",
                {
                    "hypothesis_id": hid,
                    "refuted_by": grounded,
                    "reason_code": str(args.get("reason_code", "")).strip(),
                    "turn": self._turn,
                },
            )
            entry["rejected"] = True
            self.report.hypotheses_rejected += 1
            dropped = len(claimed) - len(grounded)
            reply = f"rejected {hid}"
            if dropped:
                reply += f" ({dropped} unobserved id(s) dropped from refuted_by)"
            return ToolOutcome(reply.encode("utf-8"), 0, reply=reply)

        return [
            Tool(
                name="record_hypothesis",
                description=(
                    "State a hypothesis about the challenge and which observations "
                    "support it. Example: record_hypothesis("
                    'statement="the flag is built from the TAGSEL tag and a ledger sum", '
                    'confidence=0.6, supported_by=["obs-003"])'
                ),
                properties={
                    "statement": {"type": "string", "description": "the hypothesis"},
                    "confidence": {
                        "type": "number",
                        "description": "0.0 to 1.0, or omit if you cannot say",
                    },
                    "supported_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "observation ids you actually read",
                    },
                },
                required=["statement"],
                run=record,
            ),
            Tool(
                name="reject_hypothesis",
                description=(
                    "Reject a hypothesis you recorded earlier, with what refuted it. "
                    'Example: reject_hypothesis(hypothesis_id="hyp-01", '
                    'reason_code="observation_contradicts", refuted_by=["obs-007"])'
                ),
                properties={
                    "hypothesis_id": {"type": "string", "description": "e.g. hyp-01"},
                    "reason_code": {"type": "string", "description": "short code"},
                    "refuted_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "observation ids that refuted it",
                    },
                },
                required=["hypothesis_id", "reason_code"],
                run=reject,
            ),
        ]

    # -- §5 예약 이벤트: 하니스가 발행하는 하나 ---------------------------------

    def _observe_stalls(self, turn: int) -> None:
        """다섯 신호를 재고, 처음 관측된 것만 발행한다.

        **"멈췄다"를 추론해 싣지 않는다.** 각 신호는 이 loop 이 실제로 센 것이고,
        `stall.observed` 는 그것을 봤다는 기록이지 attempt 에 대한 판정이 아니다.
        어떤 술어도 이 이벤트를 읽지 않는다(§5.1).
        """
        if self.attempt_family is None:
            return
        self._obs_at_turn[turn] = len(self._env_obs)
        w = STALL_WINDOW_TURNS

        # ① 창 안에서 **환경** 관찰이 하나도 늘지 않았다.
        if turn > w and self._obs_at_turn[turn] == self._obs_at_turn.get(turn - w):
            self._emit_stall("no_new_observation", w)

        # ② 같은 (도구, args_digest) 가 창 안에서 되풀이됐다.
        if turn > w:
            recent = Counter(
                (name, digest) for t, name, digest in self._actions if t >= turn - w
            )
            if recent and max(recent.values()) >= REPEATED_ACTION_MIN:
                self._emit_stall("repeated_action", w)

        # ③ 예산의 절반을 넘겨 썼다. 창은 지금까지의 턴이다.
        if self.usd_budget > 0 and self.client.usd_total >= (
            self.usd_budget * BUDGET_BURN_FRACTION
        ):
            self._emit_stall("budget_burn", turn)

        # ④ 도구 호출이 연달아 실패했다.
        if self._error_streak >= TOOL_ERROR_STREAK_MIN:
            self._emit_stall("tool_error_loop", max(1, turn - self._error_streak_turn))

        # ⑤ 모델이 낸 confidence 가 최고치 대비 떨어졌다. **모델이 confidence 를
        #    한 번도 싣지 않으면 이 신호는 재지 못한 것이지 '붕괴 없음'이 아니다** —
        #    그 사실은 `LoopReport.stall_signals_not_evaluated` 가 나른다.
        if len(self._confidences) >= 2:
            peak_turn, peak = max(self._confidences, key=lambda tc: tc[1])
            last_turn, last = self._confidences[-1]
            if last <= peak * CONFIDENCE_COLLAPSE_RATIO:
                self._emit_stall("confidence_collapse", max(1, last_turn - peak_turn))

    def _emit_stall(self, signal: str, window_turns: int) -> None:
        if signal in self._signals_seen:
            return
        self._signals_seen.add(signal)
        self._expose_hypothesis_tools(signal)
        self.w.emit(
            "stall.observed",
            {
                "signal": signal,
                "window_turns": window_turns,
                # CONFIRMED 로 승격된 사실 = **환경에서 바이트로 본 것**. 가설은
                # INFERRED 이고 여기 들어가지 않는다 — 그 셋이 escalation 패킷의
                # 분할이다 (`SEAM_IMPLEMENTATION_MAP.md` §6).
                "confirmed_facts": list(self._env_obs),
                "attempt_family": self.attempt_family,
            },
        )
        self.report.stall_signals.append(signal)

    def _expose_hypothesis_tools(self, signal: str) -> None:
        """첫 stall 에서 한 번만. 이후 턴의 도구 표면에 함께 실린다 (§4-1).

        **요청을 한 번 싣는다.** 노출만으로는 부족하다는 것이 실측이다 — 두 run 에서
        도구가 올라간 뒤 모델이 네 턴을 더 썼고 **한 번도 부르지 않았다.**

        그래서 `hypotheses_recorded` 는 **모델의 성질에 대한 값이 아니다.** 요청해서
        얻은 것이고, 이 수를 "모델이 스스로 가설을 세운다"의 증거로 쓰면
        `ADR-0001` 의 `not_valid_for` 와 같은 종류의 오독이다. 그러나 이 이벤트의
        용도는 측정이 아니라 **escalation 패킷의 INFERRED 절**을 채우는 것이고
        (§5.3, `SEAM_IMPLEMENTATION_MAP.md` §6), 요청하지 않으면 그 절이 빈다.

        **`N_open` 과 다른 자리다.** 저쪽은 통합을 재는 값이라 지시하면 재는 것이
        프롬프트가 되지만(`agent_b` 머리말), 이쪽은 어떤 술어도 읽지 않는
        예약 이벤트다(§5.1).

        **접두 캐시가 여기서 한 번 빗나간다** — 도구 스키마가 요청의 앞쪽에 있으므로
        목록이 바뀌면 그 뒤가 다시 써진다(재빌드-7 진단 6c). attempt 당 한 번이고,
        막힌 run 에서만 일어난다.
        """
        if not self._latent_tools:
            return
        for t in self._latent_tools:
            self.tools[t.name] = t
        self._latent_tools = []
        self.report.hypothesis_tools_exposed_at_turn = self._turn
        # **무엇을 봤는지만 말하고 무엇을 결론하라고 말하지 않는다** (§3.1-3).
        #
        # **관찰 id 를 함께 싣는다.** 싣지 않으면 모델이 접지할 수가 없다 — 도구
        # 응답은 출력 바이트만 나르고 `observation_id` 는 봉투에만 있다. 실측에서
        # 세 run 이 전부 `obs-001` 같은 **없는 id 를 지어냈고** 필터가 셋 다 걸러
        # `supported_by` 가 비었다. 지어낸 것을 거른 것은 옳지만, 그 상태로는
        # escalation 패킷의 INFERRED 가 CONFIRMED 에 이어지지 않는다.
        #
        # **모든 도구 응답에 id 를 붙이지 않는다** — 그러면 매 턴의 프롬프트가 바뀌고
        # `D-74` 가 막은 궤적 이동이 되돌아온다. 이 메시지 하나에만 싣는다.
        shown = self._env_obs[-STALL_REQUEST_MAX_IDS:]
        dropped = len(self._env_obs) - len(shown)
        listing = ", ".join(shown) if shown else "(none recorded yet)"
        if dropped:
            listing += f"  (+{dropped} earlier, not listed)"
        self._items.append(
            {
                "role": "user",
                "content": (
                    f"Progress check — the harness observed: {signal}.\n"
                    "Two tools are now available. Call record_hypothesis with your "
                    "current best hypothesis about this challenge and your confidence. "
                    "For supported_by, use only ids from this list of observations "
                    f"actually recorded so far: {listing}. "
                    "Ids that are not in the stream are dropped. If an earlier "
                    "hypothesis is now refuted, call reject_hypothesis with what "
                    "refuted it. Then continue working."
                ),
            }
        )

    def _stall_signals_not_evaluated(self) -> list[str]:
        """계기가 없어 **재지 못한** 신호. 0 과 접지 않기 위해 따로 낸다."""
        out: list[str] = []
        if self.attempt_family is None:
            return ["*"]
        if self.report.turns <= STALL_WINDOW_TURNS:
            out += ["no_new_observation", "repeated_action"]
        if len(self._confidences) < 2:
            out.append("confidence_collapse")
        return [s for s in out if s not in self._signals_seen]

    # -- 실행 -----------------------------------------------------------------

    def run(self) -> LoopReport:
        try:
            return self._run()
        finally:
            # **재지 못한 신호를 0 으로 접지 않는다** (`CLAUDE.md` §6). loop 이 어떻게
            # 끝나든 이 값은 채워진다.
            self.report.stall_signals_not_evaluated = self._stall_signals_not_evaluated()

    def _run(self) -> LoopReport:
        self._items = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.task_prompt},
        ]
        for turn in range(1, self.max_turns + 1):
            self.report.turns = turn
            self._turn = turn
            if self.client.usd_total >= self.usd_budget:
                self.report.stop_reason = "usd_budget"
                return self.report

            if self._on_turn is not None:
                # 개입은 스냅숏 **앞**이다. 뒤에 두면 그 턴의 스냅숏이 개입 전 상태를
                # 싣고, 그러면 "무엇이 언제 바뀌었나"가 한 턴 어긋나 기록된다.
                self._on_turn(turn)
            self.w.emit(
                "state.snapshot",
                {
                    "turn": turn,
                    "live_session_ids": self._live(),
                    "state_locations": self._state_locations(),
                    "jar_digest": self._jar(),
                    "artifact_count": self._artifacts(),
                },
            )
            self._observe_stalls(turn)
            # **턴마다 다시 만든다** — `_observe_stalls` 가 도구를 더할 수 있다.
            # 한 번만 만들면 새로 올린 도구의 스키마가 요청에 실리지 않아 모델이
            # 표면에서 이름만 보고 부를 수 없는 도구를 보게 된다.
            schemas = [t.schema() for t in self.tools.values()]
            # 도구 표면은 **매 턴** 새로 실린다. 앞 턴의 것을 지우지 않고 덧붙이면
            # 접두가 유지되어 캐시가 맞는다.
            self._items.append({"role": "user", "content": self._tool_surface()})

            call = self._one_model_call(schemas)
            if call is None:
                return self.report

            calls = call.function_calls()
            self._items.extend(call.output)
            if not calls:
                self.report.turns_without_tool_call += 1
                text = call.text().strip()
                if not text:
                    self.report.stop_reason = "empty_turn"
                    return self.report
                # 도구를 안 불렀다. 끝났다고 보지 않고 한 번 더 묻되, 그 사실을 센다.
                self._items.append(
                    {
                        "role": "user",
                        "content": (
                            "That was not a tool call. Use one of the tools to make "
                            "progress, or call the submit tool if you have the answer."
                        ),
                    }
                )
                continue

            if self._dispatch(calls):
                self.report.stop_reason = "submitted"
                return self.report

        self.report.stop_reason = "max_turns"
        return self.report

    def _one_model_call(self, schemas: list[dict[str, Any]]) -> ModelCall | None:
        try:
            call = self.client.call(self._items, tools=schemas, effort=self.send_effort)
        except Exception as exc:
            self.w.emit(
                "model.requested",
                {
                    "model_id": self.client.model_id,
                    "effort": self.send_effort or self.client.effort,
                    "input_tokens": 0,
                    "cached_tokens": 0,
                    "cache_write_tokens": 0,
                    "reasoning_tokens": 0,
                    "prompt_digest": _shatext(json.dumps(self._items, ensure_ascii=False)),
                    "observation_ids": list(self._pending_observations),
                },
            )
            self.w.emit(
                "model.failed",
                {"reason": f"{type(exc).__name__}: {exc}"[:500]},
            )
            self.report.stop_reason = "model_error"
            return None

        self.report.model_calls += 1
        self.report.usd = self.client.usd_total
        u = call.usage
        self.w.emit(
            "model.requested",
            {
                "model_id": call.model_id,
                "effort": call.requested_effort,
                "input_tokens": u.input_tokens,
                "cached_tokens": u.cached_tokens,
                "cache_write_tokens": u.cache_write_tokens,
                "reasoning_tokens": u.reasoning_tokens,
                "prompt_digest": _shatext(json.dumps(self._items, ensure_ascii=False)),
                "observation_ids": list(self._pending_observations),
                # S3.4 — 경계를 넘겼으면 그 사실이 이벤트에 있어야 한다.
                "long_context_repriced": call.long_context_repriced,
            },
        )
        self._pending_observations = []
        self.w.emit(
            "model.completed",
            {
                "output_tokens": u.output_tokens,
                "usd": str(call.usd),
                # provider 가 비용을 보고하지 않는다. **0 이 아니라 부재다** —
                # `spec.md` §6.2 의 선언 채널 표가 이 부재를 선언으로 읽는다.
                "usd_self_reported": None,
                "latency_ms": call.latency_ms,
                "finish_reason": call.finish_reason,
                # 관측이지 선언이 아니다. S3.5 가 통제 블록과 견준다.
                "effective_reasoning_effort_observed": call.observed_effort,
                "model_snapshot_observed": call.model_snapshot,
            },
        )
        if call.observed_effort not in (None, self.client.effort):
            # 통제 블록이 선언한 값과 관측이 갈렸다. ADR-0001 무결성 규칙 1.
            self.report.effort_mismatch = True
        if call.degraded:
            self.report.degraded = True
            if self.fail_on_degradation:
                self.report.stop_reason = "silent_degradation"
                return None
        return call

    def _dispatch(self, calls: list[dict[str, Any]]) -> bool:
        terminal = False
        for fc in calls:
            self._op += 1
            op_id = f"op-{self._op:02d}"
            name = str(fc.get("name", ""))
            raw_args = str(fc.get("arguments", "{}"))
            try:
                args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                args = {}
            args_digest = _shatext(raw_args)
            self.w.emit(
                "tool.requested",
                {
                    "op_id": op_id,
                    "tool": name,
                    "args": args,
                    "args_digest": args_digest,
                },
            )
            self._actions.append((self._turn, name, args_digest))
            tool = self.tools.get(name)
            if tool is None:
                # 모르는 도구. 지어내지 않고 오류로 돌려준다.
                self.w.emit(
                    "tool.completed",
                    {
                        "op_id": op_id,
                        "status": "error",
                        "exit_code": 127,
                        "duration_ms": 0,
                        "artifact_ids": [],
                    },
                )
                self._reply(fc, f"no such tool: {name}")
                self._count_tool_error(127)
                continue

            outcome = tool.run(args)
            self.report.tool_calls += 1
            self._count_tool_error(outcome.exit_code)
            artifact_ids = list(outcome.artifact_ids)
            oid: str | None = outcome.observation_id
            if oid is not None:
                self._pending_observations.append(oid)
            elif outcome.observe:
                # **한도를 넘는 관찰에는 artifact 가 있어야 한다** (S5.1), 그리고 그
                # id 에 대응하는 `artifact.produced` 가 있어야 한다 (S5.2). 골든은
                # 절단이 일어나는 자리를 각본으로 알아 손으로 붙였지만, 모델이 고르는
                # 경로에서는 **어느 도구 호출이 한도를 넘길지 미리 알 수 없다** —
                # 그래서 여기서 일반으로 처리한다. 이 결함은 같은 코드가 한 run 은
                # 통과하고 다음 run 은 실패하는 형태로 드러났다.
                aid: str | None = None
                if len(outcome.output) > self.rec.limit:
                    self._artifact_n += 1
                    aid = f"art-tool-{self._artifact_n:03d}"
                    self.w.emit(
                        "artifact.produced",
                        {
                            "artifact_id": aid,
                            "sha256": _sha(outcome.output),
                            "bytes": len(outcome.output),
                            "producer_ref": f"tool:{name}",
                            "role": "truncated_output",
                        },
                    )
                    artifact_ids.append(aid)
                oid = self.rec.observe(
                    f"tool:{name} {raw_args}", outcome.output, artifact_id=aid
                )
                self._pending_observations.append(oid)
            body: dict[str, Any] = {
                "op_id": op_id,
                "status": "ok" if outcome.exit_code == 0 else "error",
                "exit_code": outcome.exit_code,
                "duration_ms": 0,
                "artifact_ids": artifact_ids,
            }
            if oid:
                body["observation_id"] = oid
                if name not in self._own_tools:
                    # **환경에서 온 것만 센다** — 경고 13 / `O-36`.
                    self._env_obs.append(oid)
            self.w.emit("tool.completed", body)
            reply = outcome.reply
            if reply is None:
                reply = outcome.output.decode("utf-8", "replace")[: self.rec.limit]
            self._reply(fc, reply)
            terminal = terminal or outcome.terminal
        return terminal

    def _count_tool_error(self, exit_code: int) -> None:
        """연속 실패의 길이. 끊기면 0 이다 — 누계가 아니라 연속이다."""
        if exit_code != 0:
            if self._error_streak == 0:
                self._error_streak_turn = self._turn
            self._error_streak += 1
        else:
            self._error_streak = 0

    def _reply(self, fc: dict[str, Any], text: str) -> None:
        self._items.append(
            {
                "type": "function_call_output",
                "call_id": fc.get("call_id"),
                "output": text,
            }
        )


def _as_list(value: Any) -> list[Any]:
    """모델이 배열 대신 문자열 하나를 줄 수 있다. 지어내지 않고 받아 준다."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        return [value]
    return []


def _as_confidence(value: Any) -> float | None:
    """**부재는 0 이 아니라 null 이다** (`TELEMETRY_SCHEMA.md` §5.2).

    모델이 값을 안 싣거나 숫자가 아닌 것을 실으면 `null` 이고, 그 사실이
    `confidence_collapse` 를 재지 못하게 만든다 — 그것이 옳다.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0.0, min(1.0, float(value)))
