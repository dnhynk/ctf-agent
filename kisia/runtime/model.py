"""S3 — provider 어댑터. `/v1/responses` 전송 계층.

`SEAM_IMPLEMENTATION_MAP.md` §7.1-1 의 후속 gate 1 이고, §7.0-② 가 재빌드 단계의
완료 조건으로 지목한 것이다. 스파이크의 T·E 는 `/v1/chat/completions` 에서 돌았고
(ADR-0001), 그 조합은 도구를 쓰는 호출에서 `reasoning_effort=medium` 을 표현할 수
없었다.

**표준 라이브러리만 쓴다.** `openai` SDK 는 프로토타입 의존성이고, SDK 를 끼우면
ADR-0001 §4 가 artifact 로 남기라고 한 **wire 원문**이 우리 손을 떠난다.

---

**진단이 바꾼 것 셋** (재빌드-7, 2026-08-09. 원본은 `<HOME>/r7/probe-out/`).

1. **`reasoning.effort` 를 생략하면 서버가 `medium` 으로 채운다.** 200 이 오고
   응답의 `reasoning.effort` 가 `medium` 이라고 적힌다. `/v1/chat/completions` 에서는
   부재가 **FAIL** 이었으므로(ADR-0001 표 3행) 같은 실수가 여기서는 조용히 지나간다.
   그래서 이 모듈은 **언제나 명시적으로 싣는다.**
2. **응답이 되돌려 주는 `reasoning.effort` 는 요청의 메아리가 아니다** — 안 보냈는데
   `medium` 이 왔다. 즉 **effective effort 의 관측 채널**이고, S3.5 가 요구하는
   "선언이 아니라 관측"의 직접 근거다. `reasoning_tokens` 는 그 옆의 행동 증거다.
3. **접두 캐시는 입력의 모양에 달렸다.** 문자열로 보내면 접두 11k 가 같아도 꼬리가
   다르면 빗나가고, **항목 배열로 append 하면 맞는다**(turn2 에서 `cached=11213`).
   cache write 는 입력의 1.25배 요율이므로 이것이 비용을 10배 가른다.

`usage` 의 경로도 계약 문면과 다르다 — ADR-0001 이 이름으로 지목한
`usage.completion_tokens_details.reasoning_tokens` 는 `/v1/chat/completions` 의
모양이고, Responses 는 `usage.output_tokens_details.reasoning_tokens` 다.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from kisia.runtime.cost import Rates, repriced, usd_for_call

#: 통제 블록의 `endpoint` 가 나르는 값과 같은 문자열이다.
ENDPOINT = "/v1/responses"
BASE_URL = "https://api.openai.com"

#: 통제 블록의 `tool_protocol`. chat/completions 의 function tools 와 모양이 다르다 —
#: Responses 의 도구 선언은 평평하고(`{"type":"function","name":...}`) 결과는
#: `function_call_output` 항목으로 돌아간다.
TOOL_PROTOCOL = "responses-function-tools"

#: 재시도하는 상태 코드. 400 은 **우리 요청이 틀린 것**이므로 재시도하지 않는다 —
#: 재시도하면 같은 오류를 세 번 내고 원인이 지연된다.
_RETRY_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})


class ModelError(RuntimeError):
    """provider 호출이 실패했다. 본문을 그대로 나른다 — 요약하지 않는다."""


class SilentDegradationError(ModelError):
    """요청한 effort 와 관측된 effort 가 다르다 (ADR-0001 무결성 규칙 1, S3.5).

    조용히 낮추거나 높이지 않는다. `medium` 을 요청했는데 내부에서 `none` 으로
    돌면 벤치마크가 오염되고, 그 반대도 같다.
    """


@dataclass
class Usage:
    input_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass
class ModelCall:
    """한 호출의 관측. **요청한 값과 관측한 값을 나란히 나른다.**"""

    model_id: str
    requested_effort: str
    #: 응답이 되돌려 준 모델 식별자 원문(`response.model`). 요청에 보낸 `model_id` 가
    #: 아니다 — `TELEMETRY_SCHEMA.md` §2.1 이 그렇게 정한다.
    model_snapshot: str
    #: 응답이 되돌려 준 `reasoning.effort`. 관측이지 선언이 아니다.
    observed_effort: str | None
    usage: Usage
    usd: Decimal
    long_context_repriced: bool
    latency_ms: int
    finish_reason: str
    output: list[dict[str, Any]] = field(default_factory=list)
    response_id: str = ""

    @property
    def degraded(self) -> bool:
        return self.observed_effort is not None and self.observed_effort != self.requested_effort

    def function_calls(self) -> list[dict[str, Any]]:
        return [i for i in self.output if i.get("type") == "function_call"]

    def text(self) -> str:
        parts: list[str] = []
        for item in self.output:
            if item.get("type") != "message":
                continue
            for chunk in item.get("content", []):
                if isinstance(chunk, dict) and chunk.get("text"):
                    parts.append(str(chunk["text"]))
        return "\n".join(parts)


class ResponsesClient:
    """`/v1/responses` 하나만 안다. 라우팅도 fallback 도 여기 없다.

    provider 이름이 **제어 흐름**에 박히지 않게 한다(S3 의 FAIL 조건) — 모델을 바꾸는
    것은 `model_id` 하나를 바꾸는 것이고, 단가표에 행을 더하는 것은 제어 흐름이 아니다.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model_id: str,
        effort: str,
        rates: Rates,
        cache_key: str | None = None,
        timeout: float = 300.0,
        retries: int = 2,
        retry_sleep_s: float = 3.0,
        base_url: str = BASE_URL,
    ) -> None:
        if not api_key:
            raise ModelError("API 키가 비어 있다 (REBUILD_LOG 재빌드-2 §0.2)")
        if rates.model != model_id:
            raise ModelError(f"단가표 행({rates.model})과 model_id({model_id}) 가 다르다")
        self._key = api_key
        self.model_id = model_id
        self.effort = effort
        self.rates = rates
        self.cache_key = cache_key
        self.timeout = timeout
        self.retries = retries
        self.retry_sleep_s = retry_sleep_s
        self.url = base_url.rstrip("/") + ENDPOINT
        #: 이 클라이언트가 낸 호출의 누계. 예산 감시는 호출자가 한다.
        self.calls = 0
        self.usd_total = Decimal(0)

    # -- 전송 ---------------------------------------------------------------

    def _post(self, body: dict[str, Any]) -> tuple[int, str]:
        raw = json.dumps(body).encode("utf-8")
        # S310 — URL 은 `base_url + ENDPOINT` 로 이 모듈 안에서만 만들어지고 스킴은
        # 언제나 https 다. 모델 응답이나 스트림에서 온 문자열이 여기 닿지 않는다.
        req = urllib.request.Request(  # noqa: S310
            self.url,
            data=raw,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
            return resp.status, resp.read().decode("utf-8")

    def _post_with_retry(self, body: dict[str, Any]) -> dict[str, Any]:
        last = ""
        for attempt in range(self.retries + 1):
            try:
                _status, payload = self._post(body)
                parsed = json.loads(payload)
                if not isinstance(parsed, dict):
                    raise ModelError(f"응답이 객체가 아니다: {payload[:200]}")
                return parsed
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")
                last = f"HTTP {exc.code}: {detail[:600]}"
                if exc.code not in _RETRY_STATUS or attempt == self.retries:
                    raise ModelError(last) from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = f"{type(exc).__name__}: {exc}"
                if attempt == self.retries:
                    raise ModelError(last) from exc
            time.sleep(self.retry_sleep_s)
        raise ModelError(last)

    # -- 호출 ---------------------------------------------------------------

    def call(
        self,
        items: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        effort: str | None = None,
    ) -> ModelCall:
        """대화 항목 배열을 보내고 관측을 돌려준다.

        `effort` 를 따로 주면 그것으로 요청한다 — **음성 대조 전용**이다. 통제 블록이
        선언한 값과 실제로 보낸 값을 갈라 S3.5 가 그 어긋남을 잡는지 재기 위한 것이고,
        정상 스트림은 이 인자를 쓰지 않는다.
        """
        sent_effort = effort or self.effort
        body: dict[str, Any] = {
            "model": self.model_id,
            "input": items,
            # 진단 1 — 생략하면 서버가 medium 으로 채운다. 언제나 명시한다.
            "reasoning": {"effort": sent_effort},
            "store": False,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
        if self.cache_key:
            body["prompt_cache_key"] = self.cache_key

        started = time.monotonic()
        data = self._post_with_retry(body)
        latency_ms = int((time.monotonic() - started) * 1000)

        if data.get("error"):
            raise ModelError(f"응답이 error 를 실었다: {json.dumps(data['error'])[:600]}")

        usage = _usage_of(data)
        usd = usd_for_call(
            self.rates,
            input_tokens=usage.input_tokens,
            cached_tokens=usage.cached_tokens,
            cache_write_tokens=usage.cache_write_tokens,
            output_tokens=usage.output_tokens,
        )
        self.calls += 1
        self.usd_total += usd
        return ModelCall(
            model_id=self.model_id,
            requested_effort=sent_effort,
            model_snapshot=str(data.get("model", "")),
            observed_effort=_observed_effort(data),
            usage=usage,
            usd=usd,
            long_context_repriced=repriced(self.rates, usage.input_tokens),
            latency_ms=latency_ms,
            finish_reason=_finish_reason(data),
            output=list(data.get("output") or []),
            response_id=str(data.get("id", "")),
        )


def _usage_of(data: dict[str, Any]) -> Usage:
    """`usage` 를 읽는다. **없는 필드를 0 으로 접지 않고 죽는다.**

    `cache_write_tokens` 가 없으면 S3.2 가 `usd` 를 재계산할 수 없다(r1 A-1). 그것을
    0 으로 접으면 `usd` 가 조용히 작아지고 술어가 그 값을 통과시킨다 — "수행하지 못함과
    0 을 접지 마라"가 걸리는 자리다.
    """
    usage = data.get("usage")
    if not isinstance(usage, dict):
        raise ModelError("응답에 usage 가 없다 — 회계를 세울 수 없다")
    in_details = usage.get("input_tokens_details")
    out_details = usage.get("output_tokens_details")
    if not isinstance(in_details, dict) or "cache_write_tokens" not in in_details:
        raise ModelError(
            "usage.input_tokens_details.cache_write_tokens 가 없다 — "
            "S3.2 의 재계산이 성립하지 않는다 (r1 A-1)"
        )
    if not isinstance(out_details, dict) or "reasoning_tokens" not in out_details:
        raise ModelError(
            "usage.output_tokens_details.reasoning_tokens 가 없다 — "
            "effective effort 를 관측할 수 없다 (S3.5)"
        )
    return Usage(
        input_tokens=int(usage.get("input_tokens", 0)),
        cached_tokens=int(in_details.get("cached_tokens", 0)),
        cache_write_tokens=int(in_details["cache_write_tokens"]),
        output_tokens=int(usage.get("output_tokens", 0)),
        reasoning_tokens=int(out_details["reasoning_tokens"]),
    )


def _observed_effort(data: dict[str, Any]) -> str | None:
    block = data.get("reasoning")
    if not isinstance(block, dict):
        return None
    value = block.get("effort")
    return str(value) if value is not None else None


def _finish_reason(data: dict[str, Any]) -> str:
    """Responses 는 `finish_reason` 을 주지 않는다 — 상태와 미완 사유로 만든다."""
    incomplete = data.get("incomplete_details")
    if isinstance(incomplete, dict) and incomplete.get("reason"):
        return f"incomplete:{incomplete['reason']}"
    return str(data.get("status", "unknown"))


def tool_schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    """Responses 의 function tool 선언. chat/completions 처럼 `function` 아래 중첩하지 않는다."""
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }
