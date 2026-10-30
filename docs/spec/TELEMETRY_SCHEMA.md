# TELEMETRY_SCHEMA — S9 봉투, 확정판 (r2)

작성일 2026-08-08. `docs/spike/SEAM_CONTRACT.md` §1(개정 r1)의 확정판이고,
`FOUNDATION_DECISION.md` §13.1-4가 요구한 문서다. `spec.md`의 모든 술어가 이 스키마 위에서
쓰인다.

**S9는 별도 seam이면서 동시에 나머지 여덟 개의 관측 수단이다.** 봉투가 어떤 사실을 나르지
않으면 그 사실에 대한 술어는 평가 대상 자체를 잃는다. 스파이크에서 이 문장이 실제로
값을 바꾼 사례가 여섯이다(r1의 A-1·A-2·A-3·A-6·A-9, 그리고 E의 `session.opened` 소실).

이 문서가 먹여야 하는 소비자는 셋이다:

1. **검사기** — `spec.md` §2의 술어 (seam 판정)
2. **라이트업 생성기** — `SEAM_IMPLEMENTATION_MAP.md` §6, S9의 소비자이지 seam이 아니다
3. **escalation 패킷 컴파일러** — 같은 곳, 같은 성격

---

## 1. 모든 이벤트의 공통 필드

```
ts          UTC, 발생 순서를 보존
run_id      run 식별자
attempt_id  attempt 식별자
seq         attempt 안에서 1부터 빈틈없이 증가
type        §3 목록 중 하나
```

`seq`가 빈틈없다는 것은 "아무것도 유실되지 않았다"를 확인하는 유일한 방법이다. 빈틈이
있으면 그 attempt의 **모든 판정이 무효**다(S9.2).

**한 attempt는 하나의 `run_id`·`attempt_id`를 갖는다.** 검사기의 첫 관문이다.

---

## 2. 통제 블록 — `attempt.started`에 1회

`EVAL_CONTRACT.md`가 요구하는 항목 전부와, 그 뒤 스파이크가 필요하다고 확인한 것들이다.
**이 블록만으로 run을 재구성할 수 없으면 S9 FAIL이고, 그 attempt의 결과는 폐기된다.**

```
# 실행 주체
runtime_id, vendored_components[{name, repo, commit, files[], patches[]}]
structural_patches[]                 vendored 코드에 가한 구조 패치 id 목록

# 모델 — ADR-0001의 무결성 규칙 (S3.5)
profile                              foundation-spike | target-performance
provider, model_id, model_snapshot
endpoint                             /v1/chat/completions | /v1/responses
requested_reasoning_effort, effective_reasoning_effort
tool_protocol, state_mode, store, streaming
capability_probe_id

# 예산과 한도
attempt_timeout_s, tool_timeout_s, session_timeout_s
token_budget, usd_budget
bytes_shown_limit                    S5의 표시 한도. 값은 자유, 결정론은 필수
session_concurrency_limit            §4.2. 명시적이어야 한다
session_kinds[{kind, accepts_input, signalable}]
                                     §4.1-1·§4.3의 수행 불가 선언 채널 (R3-9)
max_variable_len                     기본 128. S7 완전 탐색의 상한 (R3-3)

# 환경
host_id, image_digest[]
network_policy                       허용 목적지 목록

# 챌린지
challenge_id, challenge_set          dev | regression-private | final-holdout | calibration
                                     | contest (개정 R5-10 — 살아 있는 대회. 계기의 세트가
                                     아니고 `accounting_label: contest` 와 짝이다)
challenge_manifest_sha256
provenance                           synthetic | contest-derived. 기본 synthetic (개정 S-4).
                                     S7·S8·S8.3이 왜 침묵했는지를 기록에서 재구성하는 근거다
flag_format                          구멍이 하나인 템플릿. S7·S8이 가변부를 여기서 얻는다
connectors[]                         S7의 connector 집합. 기본 ["_", "-", ":", "."]
min_grounded_segment_len             기본 4
max_segments                         기본 8

# 판정 조건 (개정 R2-4)
probe_set_id                         이 attempt에서 켜진 프로브 집합의 식별자

# 지표 회계 (개정 R5-9 / ADR-0003 §Consequences·§Decision-2)
accounting_label                     clean | solve@k | contest. **기본값이 없다 — 선언하지
                                     않으면 조립기가 스트림을 열지 않는다.** 라벨은 **모드**
                                     이고 세트가 아니다: clean_solve@1 은 이 라벨과
                                     challenge_set == final-holdout 이 **함께** 참일 때다.
                                     holdout Attempt 는 clean 라벨만 허용한다
solve_k                              양의 정수. solve@k 의 k. clean 이면 1이어야 한다
run_participants[{id, kind}]         **run 의 참여자이고 attempt 의 참여자가 아니다** —
                                     G-1 이 "ClaudeCode 가 참여한 run" 이라고 적는다.
                                     비어 있을 수 없다

# 스트림 밖 고정 입력의 지목 (개정 R5-2 / spec.md S9.4a)
pricing_sha256                       단가표 파일 바이트의 sha256
                                     challenge_manifest_sha256 이 픽스처 쪽 지목이다
```

**검사기가 쓸 수 있는 스트림 밖 입력은 그 둘뿐이다**(`spec.md` S9.4a). 둘 다 위 두 해시로
지목되고, 검사기는 대조에 실패하면 판정을 내지 않는다. 이 규칙이 없으면 P-S9-a(S9.5)의
"다른 기계로 옮겨 같은 값"이 무엇을 함께 옮기는지가 정의되지 않는다.

**`EVAL_CONTRACT.md`의 6개 통제 항목과의 대응** — S9.1이 이 대응을 검사한다.

| EVAL_CONTRACT | 이 블록의 필드 |
|---|---|
| model (id and reasoning effort) | `model_id`, `model_snapshot`, `requested_`·`effective_reasoning_effort` |
| per-attempt timeout | `attempt_timeout_s` |
| token budget | `token_budget` |
| hardware and container image (by digest) | `host_id`, `image_digest[]` |
| network policy | `network_policy` |
| challenge snapshot (by content hash) | `challenge_manifest_sha256` |

**`probe_set_id`가 통제 블록에 있는 이유**는 `spec.md` §6.4다 — 프로브의 존재가 술어의
평가 가능성을 바꿔 점수를 움직이므로, 프로브 집합이 다른 두 결과는 비교 가능하지 않다.

### 2.1 값의 형식 — 개정 r3가 채운 자리

r2는 필드 이름만 정하고 값의 형식을 비워 둔 곳이 여럿이었다. 형식이 없으면 두 구현이
같은 필드에 다른 것을 넣고, 그러면 통제 조건 비교가 성립하지 않는다.

| 필드 | 형식 | 근거 |
|---|---|---|
| `probe_set_id` | 켜진 프로브 id를 **정렬해 콤마로 이은 문자열의 sha256 앞 12자**. 프로브 하나를 더하거나 빼면 다른 id다 | 동치 규칙이 없으면 §6.4의 "다르면 섞지 않는다"를 기계적으로 판정할 수 없다 |
| `model_snapshot` | provider 응답이 돌려주는 모델 식별자 원문(`response.model`). **요청에 보낸 `model_id`가 아니다** | S3.3이 "둘 다 바뀌면 통과"를 요구한다. 둘이 같은 출처면 그 술어가 공허해진다 |
| `bytes_shown_limit` | 양의 정수(바이트). 매니페스트의 `display_limit_bytes`에서 온다 | `MANIFEST.md` §2.6 |
| `session_concurrency_limit` | 양의 정수 또는 `null`(상한 없음). **`null`은 §4.2의 "명시적"을 만족한다** | 상한 없음과 상한 미선언은 다르다 |
| `session_kinds[].kind` | 구현이 정하는 문자열. **값 집합을 계약이 열거하지 않는다** — 다만 그 목록이 통제 블록에 있어야 하고 `session.opened.kind`가 그 안의 값이어야 한다 | 종류를 계약이 열거하면 구현 모양을 계약이 정하게 된다(§0.1) |
| `accounting_label` | `clean` \| `solve@k` \| `contest` 셋의 **닫힌 집합**. `k`를 라벨 문자열에 넣지 않는다 | `"solve@2"`를 라벨로 쓰면 라벨이 열린 집합이 되어 같은 회계 갈래를 등호로 묶을 수 없다 — `probe_set_id`가 동치 규칙을 요구한 것과 같은 이유다(§6.4) |
| `run_participants[].kind` | `native_core` \| `second_core` \| `external_model` 의 **닫힌 집합**. `id`는 구현이 정하는 문자열로 **열린 집합**(`session_kinds[].kind`와 같은 자세) | **G-1을 이름이 아니라 이 종류로 판정한다.** 이름으로 판정하면 다르게 부른 둘째 코어가 조용히 `clean`으로 빠져나간다. `id`를 함께 싣는 이유는 §2의 "이 블록만으로 run을 재구성할 수 없으면 S9 FAIL"이다 — 종류만으로는 어느 둘째 코어였는지 재구성되지 않는다 |
| 재과금 경계 | 통제 블록이 아니라 **`config/pricing.openai.yaml`에서 읽는다.** `spec.md` S3.4의 272,000은 `gpt-5.6-*` / `/v1/chat/completions`의 값이고 모델·엔드포인트마다 다르다 | 상수를 계약에 박으면 모델이 바뀔 때 술어가 조용히 틀린다 |

**`config/pricing.openai.yaml`의 지위** (운영자 결정 2026-08-08): **재사용하되 읽기 전용
입력이다.** 단가표는 구현이 아니라 데이터이고, S3.2가 이름으로 지목하는 판정 입력이다.
재빌드는 이 파일을 읽고 고치지 않는다. 경로 권한은 `PATH_SCOPE.md` §3.

---

## 3. 이벤트 목록

굵은 필드는 개정 r1 또는 r2가 더한 것이고, 전부 "그 필드가 없으면 어떤 소비자가 평가
대상을 잃는다"는 관측에서 나왔다.

| type | 필드 | 어느 소비자 |
|---|---|---|
| `attempt.started` | §2 통제 블록 | S9 · 라이트업 · 패킷 |
| `attempt.finished` | outcome, reason, wall_clock_s | S9 · OBJECTIVE 2순위 |
| `input.bound` | challenge_id, manifest_sha256, files[{path, sha256, bytes}] | S1 |
| `workspace.created` | container_id, image_digest, mounts[{path, mode}], network | S2 |
| `workspace.destroyed` | surviving_processes, surviving_containers, checked_by, **surviving_processes_self_reported** | S2 |
| `model.requested` | model_id, effort, input_tokens, cached_tokens, **cache_write_tokens**, **reasoning_tokens**, prompt_digest, observation_ids[] | S3 S5 S6 |
| `model.completed` | output_tokens, usd, **usd_self_reported**, latency_ms, finish_reason | S3 |
| `tool.requested` | **op_id**, tool, **args**, args_digest | S4 · 라이트업 (b) |
| `tool.completed` | **op_id**, status, exit_code, duration_ms, artifact_ids[] | S4 |
| `observation.recorded` | observation_id, source_ref, bytes_total, bytes_shown, **shown**, **shown_digest**, truncated, full_digest, artifact_id | S5 S7 S8 · 라이트업 (c) |
| `artifact.produced` | artifact_id, sha256, bytes, producer_ref, **role** | S5 · 라이트업 (b') |
| `session.opened` | session_id, **kind**, **accepts_input**, banner_observation_id | S4 S6 |
| `session.io` | session_id, session_seq, direction, bytes, **payload**, **payload_digest** | S4 · 라이트업 (b) |
| `session.closed` | session_id, transcript_artifact_id, exit_status, descendants_killed, survivors, **survivors_self_reported**, **grace_used_ms**, **reason** | S2 S4 §4.1 |
| `http.exchanged` | target_id, method, host, path, status, jar_digest_before, jar_digest_after, artifact_id | S4 S6 |
| `state.snapshot` | turn, live_session_ids[], **state_locations[]**, jar_digest, artifact_count | S6 |
| `candidate.produced` | value, **derived_from[]**, method | S7 |
| `candidate.provenance` | assembled_in_observation, part_observations[{observation_id, part}] | **참고 자료.** R2-2 이후 판정 입력이 아니다 |
| `verification.completed` | verdict, verifier_id, candidate_digest | S8 |
| `answer.sweep` | surfaces[{surface, whole_hits, **part_hits[{part, count}]**}], method, checked_by | S8 |
| `scope.refused` | action, reason_code, checked_by, **attempted_from** | S2 S6 |
| `search.performed` | query (원문), results_digest | EVAL_CONTRACT |
| **`hypothesis.recorded`** | (§5 예약) | escalation 패킷 |
| **`hypothesis.rejected`** | (§5 예약) | escalation 패킷 |
| **`stall.observed`** | (§5 예약) | escalation 트리거 |

### 3.1 r1이 더한 것과 그 근거 (요약, 전문은 `CHECKER.md` §4)

- **`cache_write_tokens`** (A-1) — cache write에 별도 요율이 있어 `input_tokens`·
  `cached_tokens`만으로는 `usd`를 재계산할 수 없다.
- **`op_id`** (A-2) — 짝짓기를 개수로 확인하면 동시 세션에서 무력하다.
- **`answer.sweep`** (A-3) — S8의 세 표면은 봉투가 내용을 나르지 않는다. **arm이 아니라
  하니스가 낸다.**
- **`candidate.provenance`** (A-6) — S7/S8 충돌 판정의 입력이었다. **R2-2가 판정 입력에서
  뺐고**, 이제 사람이 읽는 참고 자료다.
- **`observation.recorded.shown` / `shown_digest`** (A-9) — 표시된 바이트 자체가 없으면
  S7·S8·P-S5-a가 평가 대상을 잃는다.
- **`checked_by`** (A-7) — 누가 확인했는지가 없으면 "자기 보고는 증거가 아니다"를 평가할
  수 없다. 형태는 `<구성요소>@<위치>(<방법>)`.

### 3.2 r2가 더한 것과 그 근거

| 필드 | 왜 | 관측 |
|---|---|---|
| `candidate.produced.derived_from[]` (배열화) | S7이 **파생**을 표현해야 한다. 단일 id로는 두 조각을 가리킬 수 없다 | 9개 조합 전부 FAIL (`spec.md` §3) |
| `answer.sweep.part_hits[]` | S8(i)가 챌린지 입력 표면을 소스로 쓴다 | T의 `A: S8` FAIL — 한 명령으로 두 입력을 읽은 정당한 trajectory |
| `session.io.payload` / `payload_digest` | 라이트업 (b)가 유형 B에서만 깨졌다 — 세션에 **무엇을 보냈는지**가 봉투에 없다 | `CHECKER.md` §7.1-1. G의 스트림도 같은 공백 |
| `artifact.produced.role` | 골든 스크립트를 `role=solve_script`로 실어야 라이트업 (b')가 성립 | `CHECKER.md` §7.1-2 |
| `session.opened.kind` / `accepts_input` | §4.1-1의 적용 범위(R2-9)가 "입력 가능한 종류의 쌍"이다. 구현이 자기 종류를 선언해야 한다 | X의 파이프 세션은 stdin이 닫혀 있다 |
| `session.closed.reason` | 세션이 live 집합을 떠나는 모든 경로에 이벤트가 필요하다(R2-8) | X의 조용한 축출 |
| `state.snapshot.state_locations[]` | P-S6-a(R2-7)가 개입할 대상을 런타임이 선언해야 한다 | E·X에서 개입 자체를 확인하지 못했다 — 상태가 셸 변수에 있으면 버릴 대상이 없다 |
| `*_self_reported` 3종 | 자기 보고를 **판정에 쓰지 않되 기록은 한다**(§0.3-3, R2-12) | T 46%·E 5.6~6.75배 과대, E의 close 자기 보고가 틀렸다 |
| `model.requested.reasoning_tokens` | effective effort는 선언이 아니라 관측이다(S3.5) | E-06이 이것으로 폐기 run을 잡았다 |
| `tool.completed.exit_code` | S4.1이 exit code를 요구하는데 r1의 필드 목록에 없었다 | 계약 내부의 누락 |

### 3.2.1 r3가 채운 이벤트 쪽 형식

| 대상 | 형식 | 근거 |
|---|---|---|
| **`seq`의 직렬화** | 이벤트를 **스트림에 쓰는 시점**에 단일 지점에서 매긴다. 동시 세션의 이벤트도 그 지점을 통과하므로 `seq`는 **쓰기 순서**이지 발생 순서가 아니다. 발생 순서는 `ts`가 나른다. **인과 순서를 `seq`로 주장하려면 `op_id`로 짝지어야 한다** | S9.2는 빈틈없음을, §4.2는 동시 세션을 요구한다. 두 요구가 만나는 자리에 규칙이 없었다 |
| **`op_id`** | **attempt 안에서** 유일. run 전체가 아니다. `attempt_id`와 함께 읽으면 전역 유일해진다 | 판정 단위가 attempt이고 폐기·재실행이 attempt 단위다 |
| **`checked_by` / `verifier_id`** | `<구성요소>@<위치>(<방법>)`. **토큰 경계는 `@ ( ) . / - _ 공백`이고 비교는 대소문자를 구분하지 않는다.** `<구성요소>`가 그 일을 한 주체의 id와 같지 않고, 그 id가 토큰으로 나타나지도 않아야 한다 | r1 A-7이 문자 포함 검사를 버렸는데 토큰 경계를 정하지 않았다 |
| **`state.snapshot.state_locations[]`** | `{kind, ref, droppable}`. `kind ∈ {file, container_path, process_object, remote}`, `ref`는 그 종류에서 유일하게 지시하는 문자열(파일이면 **절대 경로**), `droppable`은 P-S6-a가 개입할 수 있는지 | E·X에서 개입을 확인하지 못한 원인이 **상대 경로**와 **셸 변수**였다. 절대 경로 요구와 `droppable=false` 선언이 그 둘을 각각 처리한다 |
| **`answer.sweep.part_hits[].part`** | 매니페스트 옆 정답 파일 `parts`의 **키**(`part_id`)다. 값 자체를 싣지 않는다 — 스트림에 정답 조각을 쓰면 S8.3의 스윕 대상이 스트림 자신이 된다 | `MANIFEST.md` §2.3 |
| **`search.performed`** | 도구를 노출하지 않아 검색이 **불가능**한 경우, 그 사실을 통제 블록의 `tool_protocol`과 함께 `attempt.finished.reason`이 아니라 **`attempt.started`의 `search_tool_exposed: false`**로 남긴다. 이벤트 0건과 도구 부재는 다른 사실이다 | `EVAL_CONTRACT.md`가 검색 유래 flag를 실패로 규정하므로, "안 했다"와 "못 한다"를 구분해야 한다 |
| **redaction sentinel** | 값이 아니라 **타입**이다. 봉투 조립기는 통제 블록의 `secret_refs[]`에 등재된 이름의 값을 만나면 그 자리에 `"<redacted:{ref}>"`를 넣는다. 무엇이 비밀인지는 조립기가 추측하지 않고 **선언에서만** 온다 | `SAFETY_SCOPE.md`가 sentinel을 요구하는데 판정 기준이 없었다. 추측으로 판정하면 놓치거나 과도하게 가린다 |

### 3.3 `artifact.produced`가 별도 이벤트인 이유

프로토타입은 `tool.completed`가 artifact **id만** 실어 해시가 어떤 이벤트에도 없었고,
그래서 artifact를 증거로 인용할 수 없었다 [ev §8.4]. **생산 사실과 해시를 나르는 이벤트가
반드시 따로 있어야 한다.**

### 3.4 `search.performed`는 차단이 아니라 기록이다

`EVAL_CONTRACT.md`가 검색으로 얻은 flag를 실패로 규정하므로, 막아 버리면 그 행동을 관측할
기회를 잃는다. 스파이크의 세 arm 모두 이 이벤트가 0건이었고(E의 명령 집합에는 웹 검색
도구가 없다), 우리 런타임에서도 도구를 노출하지 않는다면 그 사실을 기록한다.

---

## 4. 두 소비자의 충분성 — S9-SUFFICIENCY

`FOUNDATION_DECISION.md` §13.1-4가 요구한 확인이다. 세션 C가 골든 스트림 3개에 대해
실측했고(`CHECKER.md` §7), 그 결과가 남긴 공백을 r2가 닫는다.

### 4.1 라이트업 생성기가 필요로 하는 것

| 요소 | 세션 C의 실측 (A / B / C) | r2 이후 |
|---|---|---|
| (a) 사용한 도구의 순서 | 참 / 참 / 참 | 유지. `tool.*`의 `op_id` 짝 |
| (b) 실행 가능한 solve 단계 | 참 / **거짓** / 참 | **닫힘** — `session.io.payload` (R2-13). B가 깨진 이유는 `session.io`가 바이트 **수**만 실었기 때문이다 |
| (b') 골든 스크립트 artifact | 증거 없음 ×3 | **닫힘** — `artifact.produced.role=solve_script` (R2-14) |
| (c) 무엇을 관찰해 답에 이르렀나 | 참 / 참 / 참 | 유지. `shown`·`shown_digest` + **R2-1의 파생 검증이 근거를 더 정확하게 만든다** |
| (d) 성공의 증거 | 참 / 참 / 참 | 유지 |
| (e) 재현 절차 | P-S9-a에서 7/7 일치 | 유지 |

**(b)의 공백은 유형 B에서만 났고 원인이 구조적이었다.** 유형 A·C의 모든 행위는
`tool.requested.args`를 거치지만 세션은 그렇지 않다. 관찰(`shown`)은 **돌아온 것**을 담고
**보낸 것**은 담지 않는다. `payload`가 그 자리를 채운다.

### 4.2 escalation 패킷 컴파일러가 필요로 하는 것

패킷은 **CONFIRMED / INFERRED / REJECTED**를 나눈다.

| 등급 | 현재 봉투에서 | 상태 |
|---|---|---|
| CONFIRMED | `observation.recorded` + `verification.completed` + R2-1의 파생 검증 | **투영 가능** |
| INFERRED | 해당 이벤트 타입 없음 | **§5의 예약 필드** |
| REJECTED | 해당 이벤트 타입 없음 | **§5의 예약 필드** |

`spec.md` §7의 단일 경로 챌린지는 가설이 없어 이 이벤트를 행사하지 못한다. 그래서 세션 C가
계약에 넣지 않고 문서 세션으로 넘겼고, 이 문서가 §5의 형태로 받는다.

---

## 5. 예약 필드 — escalation과 stall

`FOUNDATION_DECISION.md` §13.1.a-2가 요구한 항목이다.

### 5.1 예약의 규칙 — 술어를 붙이지 않는다 (R2-15)

이 저장소의 원칙은 **"행사되지 않은 계약은 계약이 아니다"**이고(§0.3-2, §9.2.1), 예약
필드는 그 원칙과 충돌할 수 있다. 충돌을 이렇게 푼다:

> **예약 필드는 스키마에 자리를 갖되 `spec.md` §2의 어떤 술어에도 등장하지 않는다.**
> 따라서 어떤 seam 판정도 바꾸지 않고, 비어 있다는 이유로 FAIL이 나지 않는다.
> escalation 계층이 실제로 만들어질 때 그 계층의 명세가 술어를 붙인다.

자리를 지금 잡는 이유는 하나다: **계약이 언 뒤에 봉투를 넓히는 비용이 seam-first 규칙이
존재하는 이유 그 자체**다. 필드 이름과 이벤트 경계를 지금 고정해 두면, escalation이
얹힐 때 이미 쌓인 telemetry가 소급해서 쓸모없어지지 않는다.

### 5.2 이벤트

```
hypothesis.recorded
    hypothesis_id            attempt 안에서 유일
    statement                가설의 진술 (원문)
    confidence               0.0~1.0 또는 null
    supported_by[]           observation_id 목록. 비어 있을 수 있다
    attempt_family           같은 문제에 대한 시도 묶음의 식별자
    turn

hypothesis.rejected
    hypothesis_id            앞선 hypothesis.recorded 를 가리킨다
    refuted_by[]             observation_id 목록
    reason_code
    turn

stall.observed
    signal                   no_new_observation | repeated_action | budget_burn |
                             confidence_collapse | tool_error_loop
    window_turns             신호가 관측된 턴 폭
    confirmed_facts[]        그 시점까지 CONFIRMED 로 승격된 사실의 id 목록
    attempt_family
```

### 5.3 예약 필드가 어느 seam에 요구를 거는가

`FOUNDATION_DECISION.md` §13.1.a-4가 이 문서에 고정하라고 한 것이다. **상세 설계는 재빌드
이후다.**

| 요구 | 어느 seam | 무엇을 뜻하는가 |
|---|---|---|
| 패킷의 소재 | **S9 소비** | 패킷은 telemetry의 투영이다. 새 seam이 아니다 |
| 외부 모델로의 export | **S2 export 경계** | 챌린지 유래 콘텐츠는 **하나의 게이트된, 비밀 제거된, scope 검사된 export**를 통해서만 나간다. `SAFETY_SCOPE.md`의 예외가 필요하고 그 제안은 `docs/proposals/CANON_EDITS_2026-08-08.md` |
| 답신의 재주입 | **S6 재주입** | 외부에서 온 내용이 상태로 들어올 때 그 출처가 관찰로 기록되어야 한다. 그러지 않으면 S7의 파생 검사에서 근거 없는 조각이 된다 |

**주의 하나를 명시한다.** escalation이 가져온 문자열이 flag의 조각이 되면, S7의 소스
집합에 "외부 모델이 준 것"이 들어간다. `clean_solve@1`은 그 경로를 허용하지 않고
`contest_solve`는 허용하므로, **두 지표는 S7의 소스 집합이 서로 다르다.** 이 구분이
`EVAL_CONTRACT.md`에 들어가야 하는 이유이고, 제안은 같은 파일에 있다.

---

## 6. 원문 기록 정책

- **합성 챌린지:** `observation.recorded.shown`, `tool.requested.args`,
  `session.io.payload`를 **원문 그대로** 기록한다. S7의 파생 검증과 S8의 조립 검증이
  바이트를 요구하고, 출처 확인이 이 계약의 존재 이유다.
- **대회 유래 챌린지:** 같은 정책을 쓸지는 별도 결정이다(`spec.md` §9-5). 현재
  `SAFETY_SCOPE.md`의 `allow_vps=false` 아래에서는 대회 유래 입력이 호스트에 들어올 수
  없으므로 이 결정은 아직 필요하지 않다. **필요해지는 시점은 그 권한이 바뀌는 시점이다.**
- **비밀 값:** 어떤 경우에도 원문을 싣지 않는다. redaction sentinel을 싣고, export는
  sentinel을 만나면 중단한다(`SAFETY_SCOPE.md`).

---

## 7. 봉투를 내는 쪽의 최소 의무

`CHECKER.md` §8이 세션 D에 넘긴 목록을 재빌드용으로 옮긴 것이다. 순서는 검사기가 걸리는
순서다.

1. **`seq`가 1부터 빈틈없고 `run_id`·`attempt_id`가 하나.**
2. **`attempt.started`에 §2 통제 블록 전부.** 하나라도 빠지면 S9 FAIL이고 그 attempt는
   폐기된다.
3. **`observation.recorded`에 `shown`·`shown_digest`.** 없으면 S7·S8·P-S5-a가 평가 대상을
   잃는다.
4. **`answer.sweep`은 러너가 낸다** — 실행 주체가 아니다. surfaces, `whole_hits`,
   `part_hits`, `checked_by` 필요.
5. **`model.requested.cache_write_tokens`·`reasoning_tokens`.** 없으면 S3.2·S3.5가 거짓이
   된다.
6. **`checked_by`/`verifier_id`는 `<구성요소>@<위치>(<방법>)` 꼴**, 구성요소가 그 일을 한
   주체와 다를 것.
7. **`op_id`는 필수**(R2-17).
8. **세션을 열거나 닫을 때마다 `session.opened`/`session.closed`를 반드시 낸다.**
9. **유형 C의 S2를 PASS로 만들려면** `scope.refused{action:"connect:<host>:<port>",
   reason_code:…, attempted_from:"container"}`가 필요하다.

### 7.1 봉투를 조립하는 코드가 가장 먼저 틀리는 자리 — 실측된 경고

**어댑터의 조용한 거짓 음성이 스파이크에서 가장 비싼 결함이었다.** 봉투 조립기의 내부
키워드 인자 이름이 계약 필드 이름(`kind`)과 겹쳐 `session.opened`가 **통째로 사라졌고**,
검사기는 그것을 S6.3으로 정확히 잡았지만 **원인은 실행 주체가 아니라 우리였다.**

따라서 봉투 조립기는 **필드 이름 충돌 시 조용히 덮어쓰지 않고 죽어야 한다.** 이것은 권고가
아니라 이 문서가 요구하는 성질이다.

같은 종류의 경고 둘:

- **"수행하지 못함"과 "0"을 접지 마라.** 항아리 `absent`(그 시점에 파일이 없었다)와
  `null`(볼 위치를 특정할 수 없었다)은 다른 값이다. 접으면 **거짓 관측**을 기록한다.
- **`descendants_killed`는 실행 주체의 반환값이고 `survivors`는 밖에서 읽은 값이다.**
  둘을 같은 출처에서 만들면 스트림이 자기 일관적이 되어 검사기가 통과시킨다.

---

## 부록 A. 참조

- `docs/spec/spec.md` — 이 스키마 위에서 쓰인 술어 전부
- `docs/spike/CHECKER.md` §4 (r1 개정의 근거), §5 (P-S9-a), §7 (S9-SUFFICIENCY), §8 (최소 형태)
- `docs/spike/FIXTURES.md` §4.2 (골든이 §1.3에서 벗어난 세 가지)
- `docs/spike/ARM_E_REPORT.md` §15.1 (봉투 조립기의 조용한 거짓 음성), §16 (자기 회계 대조)
- `docs/canon/EVAL_CONTRACT.md` — 통제 블록의 출처
- `docs/evidence/2026-08-07-phase-b-evidence.md` §8.4 — `artifact.produced`가 따로 있는 이유
