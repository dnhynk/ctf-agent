# ADR-0001 — Foundation spike reasoning-effort normalization

## Status

**Accepted for the `foundation-spike` profile only.** 운영자 결정 2026-08-07, 세션 D.

이 결정은 **`EVAL_CONTRACT.md`의 통제 조건을 영구히 바꾸지 않는다.** 제품·성능 평가
프로파일은 `Responses API + reasoning_effort=medium`을 유지하며, 아래 §Follow-up gate가
그것을 검증할 별도 관문이다.

## Context

세션 D가 T의 provider 어댑터를 고친 뒤(T-04), **나가는 HTTP 요청 본문을 가로채** 확인한
결과 `reasoning_effort=medium`은 실제로 요청에 실렸으나 API가 거부했다:

```
400 Function tools with reasoning_effort are not supported for gpt-5.6-terra in
    /v1/chat/completions. To use function tools, use /v1/responses or set
    reasoning_effort to 'none'.
```

추측을 배제하기 위해 여섯 칸을 실측했다. 원본은
`docs/spike/arms/T/capability-probes/openai-gpt-5.6-terra-chat-tools-effort-2026-08-07.json`.

| endpoint | tools | reasoning_effort | 결과 |
|---|---|---|---|
| `/v1/chat/completions` | 있음 | `medium` | **FAIL** |
| `/v1/chat/completions` | 있음 | `none` | OK |
| `/v1/chat/completions` | 있음 | **부재** | **FAIL** |
| `/v1/chat/completions` | 없음 | `medium` | OK |
| `/v1/responses` | 있음 | `medium` | OK |
| `/v1/responses` | 있음 | `none` | OK |

세 가지가 여기서 확정된다.

1. **T와 E는 medium을 표현할 수 없다.** 둘 다 `/v1/chat/completions`를 쓰고 도구 계층이 곧
   function calling이다.
2. **effort 부재도 실패한다.** 즉 T는 T-04 이전에 이 모델로 도구를 쓰는 호출을 **한 번도**
   할 수 없었다. 세션 A가 관측한 `max_tokens` 실패는 두 관문 중 첫째였을 뿐이다.
3. **X(Codex CLI)는 `wire_api=responses`라 medium이 가능하다**(`REPRO_MATRIX.md` §2.3).
   따라서 이 제약은 모델 품질 문제가 아니라 **endpoint × parameter 조합의 capability 문제**다.

### 왜 지금 Responses로 이식하지 않는가

이 스파이크의 목적은 API 전송 계층을 다시 쓰는 것이 아니라 **OSS 하니스의 구조·도구 루프·
실행 가능성을 비교하는 것**이다. T·E만 `/v1/responses`로 옮기면 다음이 동시에 바뀐다:
function tool 요청·응답 형식, `call_id` 연결 방식, 스트리밍 이벤트 모델, 상태 유지 방식,
reasoning item 보존, 캐싱 동작, 오류 처리 경로. URL 교체가 아니라 **새 transport 구현**이다.

더 중요한 것은 **Responses가 중립적 전송 계층이 아니라는 점**이다. OpenAI는 같은 프롬프트와
설정에서도 reasoning 모델을 Responses로 실행하면 내부 SWE-bench가 개선되고 캐시 효율에도
차이가 있다고 밝힌다. 한 arm만 Responses로 바꾸면 **하니스 효과와 API 효과를 분리할 수
없다** — 이 스파이크가 재려는 것과 정확히 반대다.

실무적으로도 이 이식은 T의 남은 구조 패치 예산 1개를 여기서 소진시킨다. §11이 그 예산이
필요하리라 예측한 곳은 유형 B의 세션 계층이다(`ARM_T_REPORT.md` §9).

### 왜 모델을 다시 고르지 않는가

관측된 것은 모델 능력 문제가 아니라 endpoint 조합의 capability 문제다. 모델을 바꾸면
**모델 능력이라는 더 큰 교란 변수**가 추가된다.

## Decision

### 프로파일 1 — `foundation-spike`

**`endpoint` 는 2026-08-09에 옮겨졌다 — 아래 §Correction (재빌드-7).** 이 yaml 은
**스파이크가 실제로 돌린 값**의 기록이고 그대로 둔다.

```yaml
profile: foundation-spike
provider: openai
model_alias: gpt-5.6-terra          # A-5/P-S3-a 프로브에서만 gpt-5.6-luna
endpoint: /v1/chat/completions      # T·E. X 는 /v1/responses (아래 §Scope)
                                    # → 재빌드-7이 §Follow-up gate 1대로 /v1/responses 로
                                    #   옮겼다. §Correction
reasoning_effort:
  requested: none
  required_effective: none
fixture: trivial-by-design (자작 합성 3종)

purpose:
  - tool invocation correctness
  - terminal round-trip
  - state propagation
  - failure handling
  - telemetry correctness
  - fixture completion

not_valid_for:
  - CTF solve capability ranking
  - final model selection
  - production reasoning quality claims
```

**이 결과로 판단할 수 있는 것:** 하니스가 실제로 실행되는가, 도구 호출과 결과 반환이
정상인가, 상태와 로그를 잃지 않는가, 통합 비용이 얼마인가, 반복 실행이 안정적인가.

**이 결과만으로 판단하면 안 되는 것:** 어느 하니스가 어려운 CTF를 더 잘 푸는가, medium에서
어느 하니스가 더 강한가, 실제 대회 성능, 최종 foundation 우승자.

### 프로파일 2 — `target-performance` (최종 후보 1~2개로 줄인 뒤)

```yaml
profile: target-performance
endpoint: /v1/responses
reasoning_effort:
  requested: medium
  required_effective: medium
fixture:
  difficulty: nontrivial
  private_or_clean: true

purpose:
  - clean solve accuracy
  - time-to-flag
  - cost per solve
  - tool-loop reliability
  - long-horizon state retention
```

## Scope and limits

**endpoint가 arm마다 다르다.** T·E는 `/v1/chat/completions`, X는 `/v1/responses`다.
`effort=none`으로 맞춰도 이 차이는 남는다. 따라서 이 스파이크의 결과를 부르는 이름은:

| 허용되는 표현 | 허용되지 않는 표현 |
|---|---|
| 원형에 가까운 전체 OSS stack 비교 | 순수한 orchestration 품질 비교 |
| as-integrated system comparison | 동일 transport에서의 harness-only 비교 |

이 스파이크는 OSS를 **원형에 가깝게** 평가하는 것이므로 endpoint 차이를 그대로 두는 것이
맞다. 다만 그 결과는 **전체 스택의 적합성 결과**이지 agent loop만 격리한 비교가 아니다.
최종 후보끼리는 공통 Responses 어댑터 아래에서 transport-normalized 비교를 한 번 더 한다.

이 결정은 **trivial foundation fixture에 대해서만 유효**하며 CTF solve accuracy나 제품
모델 품질에 관한 어떤 주장도 뒷받침하지 못한다.

## Integrity rules — 계약에 넣는다

1. **조용한 강등 금지.** 지원하지 않는 조합을 자동으로 `none`으로 낮추지 않는다.
   `requested_reasoning_effort`와 `effective_reasoning_effort`가 다르면 **실행을 실패
   처리한다**(fail-fast). `medium`을 요청했는데 내부에서 `none`으로 돌면 벤치마크가 오염된다.
2. **effective effort는 선언이 아니라 관측이다.** `usage.completion_tokens_details
   .reasoning_tokens`로 판정한다 — 0이면 추론이 일어나지 않은 것이다. 세션 D가 이 값이
   실제로 보고됨을 확인했다.
   **경로가 endpoint마다 다르다 (정정 2026-08-09, §Correction).** 위 이름은
   `/v1/chat/completions`의 것이고, `/v1/responses`에서는
   `usage.output_tokens_details.reasoning_tokens`다. **규칙 자체는 그대로다.**
   그리고 "0이면 추론이 일어나지 않은 것이다"를 **"0이면 effort가 none이다"로 읽지
   마라** — 그 오독을 `ARM_E_REPORT.md` §3.3이 실측으로 막았고(11토큰 프로브),
   `spec.md` S3.5가 그것을 인용한다.
3. **아래를 모든 실행 결과에 기록한다.**

```json
{
  "profile": "foundation-spike",
  "provider": "openai",
  "model_alias": "gpt-5.6-terra",
  "model_snapshot": "<응답이 되돌려 준 값>",
  "endpoint": "/v1/chat/completions",
  "requested_reasoning_effort": "none",
  "effective_reasoning_effort": "none",
  "tool_protocol": "chat-completions-function-tools",
  "state_mode": "manual-transcript",
  "store": false,
  "streaming": false,
  "capability_probe_id": "openai-gpt-5.6-terra-chat-tools-effort-2026-08-07"
}
```

4. **capability probe는 메모가 아니라 artifact다.**
   `docs/spike/arms/T/capability-probes/<probe-id>.json`에 원본을 남기고
   `capability_probe_id`로 결과에서 참조한다.

이 필드들은 `SEAM_CONTRACT.md` §1.2 통제 블록에 **더한 것**이고 요구 항목을 뺀 것이 아니다.
계약이 "최소 집합"을 정한다는 전제 위에서 세션 B가 §4.2로 한 것과 같은 자리다.

## Follow-up gate — foundation 채택 전 필수

1. shortlist된 후보에 대해 Responses transport를 구현하거나 검증한다.
2. **모든 결선 후보를 nontrivial clean fixture에서 `medium`으로 돌린다.**
3. solve rate, latency, cost, tool reliability, variance를 비교한다.
4. **foundation-spike 결과만으로 foundation을 승격하지 않는다.**

이 관문을 통과하기 전의 foundation 결정은 **provisional**이다.

## Consequences

- 이 스파이크는 **어떤 arm도 medium에서 재지 않았다.** `FOUNDATION_DECISION.md` §12.2-7에
  기재한다.
- `none`은 **배관·통합 스파이크를 공정하게 끝내기 위한 임시 공통분모**이지 "우리 에이전트는
  앞으로 reasoning을 none으로 쓴다"는 결정이 아니다.
- Responses 이식은 이 세션의 작업이 아니라 **shortlisted candidate에 대한 별도 필수
  작업으로 등록**된다.

## Correction (재빌드-7, 2026-08-09) — 운영자 승인

**§Follow-up gate 1이 닫혔다. 그 결과 이 문서의 두 곳이 낡았고 그 자리에 표시를 달았다.**
본문은 덮어쓰지 않았다 — `ADR-0002`가 `O-14`에 대해 한 것과 같은 자세다. 이 ADR은
스파이크가 무엇을 관측했는지의 **이력**이고, 그것을 사후에 고치면 이 프로젝트가 막으려는
바로 그 일이 된다.

**무엇이 바뀌었나.**

| 자리 | 이 문서가 적은 것 | 2026-08-09의 사실 |
|---|---|---|
| §Decision 프로파일 1 `endpoint` | `/v1/chat/completions` | **`/v1/responses`.** 재빌드-7이 §Follow-up gate 1대로 옮겼다 |
| §Integrity rules 2 의 usage 경로 | `usage.completion_tokens_details.reasoning_tokens` | Responses 에서는 `usage.output_tokens_details.reasoning_tokens` |

**여섯 칸 표를 `/v1/responses`에서 다시 쟀고 두 칸이 갈렸다.** 원본은
`docs/rebuild/capability-probes/openai-responses-tools-effort-2026-08-09.json`(12칸,
terra·luna).

| 조합 | `/v1/chat/completions` (이 문서) | `/v1/responses` (재빌드-7) |
|---|---|---|
| tools + `medium` | **FAIL** | **OK** |
| tools + effort **부재** | **FAIL** | **OK — 서버가 `medium`으로 채운다** |

**둘째가 이 ADR의 무결성 규칙 1에 새 구멍을 낸다.** chat/completions에서는 effort를
빠뜨리면 요청이 죽어 실수가 드러났다. Responses에서는 200이 오고, 통제 블록이 `none`이라
적는 동안 medium이 돈다 — **조용한 강등이 아니라 조용한 승격**이고 규칙 1이 막으려는
오염과 방향만 반대다. 그래서 재빌드-7의 어댑터는 `reasoning.effort`를 **절대 생략하지
않는다**(`REBUILD_LOG.md` 재빌드-7 `D-46`).

**정정하지 않은 것.** `not_valid_for`의 네 항목은 그대로다 — 특히 `final model selection`.
재빌드-7이 낸 수치(terra $0.0075/attempt, luna $0.0009/attempt)는 **trivial fixture 위의
것**이고 모델 선정의 근거가 되지 못한다. §Follow-up gate 2·3은 성능 단계 그대로이고
(로드맵 결정 F), gate 2가 요구하는 nontrivial clean fixture는 `HOLDOUT.md` §6-1대로 아직
존재하지 않는다.

**§Status는 움직이지 않는다.** 이 결정은 여전히 `foundation-spike` 프로파일 전용이고,
`EVAL_CONTRACT.md`의 통제 조건을 바꾸지 않는다.

---

## References

- `docs/spike/ARM_T_REPORT.md` §2 (여섯 칸 관측과 그 경위)
- `docs/spike/FOUNDATION_DECISION.md` §9.1 (통제 조건), §12.2-7 (알려진 공백)
- `docs/canon/EVAL_CONTRACT.md` (변경하지 않았다)
- `docs/spike/REPRO_MATRIX.md` §2.1 (T의 보류 패치), §2.3 (X의 responses 경로)
- OpenAI, "Migrate to the Responses API" — https://platform.openai.com/docs/guides/migrate-to-responses
