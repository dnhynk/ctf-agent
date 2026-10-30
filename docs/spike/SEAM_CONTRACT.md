# SEAM_CONTRACT — 초안 (승격됨, 이력으로 보존)

> **2026-08-08: 확정판은 `docs/spec/spec.md`(개정 r2)다.** 문서 세션이 이 초안을 스파이크
> 결과로 고쳐 승격시켰다(`FOUNDATION_DECISION.md` §13.1-1). **이 문서는 더 이상 계약이
> 아니다** — 초안과 개정 r1의 이력으로 보존한다. 계약을 인용해야 하면 `docs/spec/spec.md`를
> 인용하고, §1 봉투는 `docs/spec/TELEMETRY_SCHEMA.md`를 인용한다.
>
> r2가 이 문서에서 무엇을 왜 바꿨는지는 `docs/spec/spec.md` §8.1(개정 목록, 18항)과
> §3(S7 — 9개 (arm×유형) 조합 전부의 FAIL을 계약이 어떻게 처리하는가)에 있다.

작성일 2026-08-07. 상태: **초안.** 확정판은 foundation 결정 이후 첫 문서에서 만든다
(`FOUNDATION_DECISION.md` §13.1). 이 초안은 스파이크를 시작하기 위한 최소 계약이다.

**개정 r1 — 2026-08-07, 세션 C.** 술어를 검사기로 옮기고 골든 스트림 6개에 흘리는 과정에서
기계적으로 평가할 수 없는 술어 9곳이 드러났다. 그것만 고쳤다. 개정 하나하나의 근거와 그것을
드러낸 관측은 `CHECKER.md` §4에 있다. 개정 시점은 **arm 결과를 보기 전**이므로
`FOUNDATION_DECISION.md` §9.6-1에 걸리지 않는다 — 세션 D가 열리면 이 권한은 닫힌다.
개정 항목: A-1 `cache_write_tokens`, A-2 `op_id`, A-3 `answer.sweep`, A-4 하중표 B행 S2,
A-5 S6 첫 술어의 적용 범위, A-6 S7/S8 충돌 판정, A-7 `checked_by`/`verifier_id`의 형태,
A-8 술어 판정값 다섯, A-9 `observation.recorded.shown`.

`FOUNDATION_DECISION.md` §3의 9개 seam을 **기계적으로 판정 가능한 형태**로 옮긴 것이다. §8에 적은
대로, 이 계약은 세 선택지 중 무엇을 고르든 버려지지 않는 유일한 산출물이므로 결정을 기다리지 않는다.

---

## 0. 이 계약의 형태와 그 이유

**계약은 인터페이스가 아니라 관측이다.** 각 seam의 통과 조건은 "이런 메서드가 있어야 한다"가 아니라
"기록에 이런 사실이 남아야 한다"로 쓴다.

이유는 하나뿐이다. 스파이크의 arm은 TATAR(fork), EnIGMA 컴포넌트(추출), greenfield 참조 구현, Codex
CLI(대조군)이고, 이 넷의 내부 구조는 서로 닮지 않았다. 계약을 인터페이스로 쓰면 그 인터페이스를
가장 닮은 후보가 유리해지고, 스파이크는 배관을 재는 대신 우리가 미리 고른 구조와의 유사도를 재게
된다. 그러면 §10의 결정 규칙 전체가 무의미해진다.

예외는 하나다. §4의 `InteractiveSession`은 **교체 가능성 자체가 요점인 지점**이라(선택지 2의 A/B
검증은 이것 없이는 성립하지 않는다, `FOUNDATION_DECISION.md` §6.4) 인터페이스로 명명한다. 그 외
어디에도 메서드 이름을 정하지 않는다.

### 0.1 계약을 만족시키는 방법에 관한 규칙

1. arm이 필요한 이벤트를 직접 내지 못하면 **어댑터가 낸다.** 후보 코드를 고쳐 이벤트를 내게 만드는
   것은 구조 패치이고, 어댑터가 후보의 기존 출력에서 사실을 뽑아내는 것은 패치가 아니다.
2. **어떤 방법으로도 그 사실을 얻을 수 없다면, 그것이 그 seam의 FAIL이다.** 이 문장이 계약을 모든
   후보에게 공평하면서도 변별력 있게 만드는 유일한 장치다.
3. **후보의 자기 보고는 증거가 아니다.** 정리 완료, 프로세스 0, 성공 판정 같은 사실은 후보 밖의
   검사기가 독립적으로 확인한 것만 기록에 들어간다. 근거: 이 저장소는 자기 보고가 틀린 사례를
   실측으로 세 번 발견했다 [ev §8.1–8.3].
4. 판정은 사람이 로그를 읽어서 하지 않는다. **검사기(checker)가 이벤트 스트림에 대해 술어를
   평가한다.** 술어가 애매해서 사람 판단이 필요하면 그 술어는 아직 계약이 아니다.

### 0.2 이 계약이 정하지 않는 것

저장 포맷, 파일 경로, 모듈 경계, 언어, 디렉터리 구조, agent loop의 형태. 전부 결정 이후 문서로
넘긴다 [pack §13 규칙 10].

---

## 1. telemetry envelope — 계약의 표면

9개 seam 전부의 통과 조건이 이 스트림 위에서 쓰인다. S9는 별도 seam이면서 동시에 나머지 여덟 개의
관측 수단이다.

### 1.1 모든 이벤트의 공통 필드

```
ts          UTC, 발생 순서를 보존
run_id      스파이크 run
attempt_id  attempt
seq         attempt 안에서 1부터 빈틈없이 증가
type        아래 목록 중 하나
```

`seq`가 빈틈없다는 것은 "아무것도 유실되지 않았다"를 확인하는 유일한 방법이다. 빈틈이 있으면 그
attempt의 모든 판정이 무효다.

### 1.2 통제 블록 — `attempt.started`에 1회

`EVAL_CONTRACT.md`가 요구하는 항목 전부. **이 블록만으로 run을 재구성할 수 없으면 S9 FAIL이고,
그 attempt의 결과는 폐기된다.**

```
arm_id, candidate_repo, candidate_commit, structural_patches[]
model_id, reasoning_effort
attempt_timeout_s, tool_timeout_s, session_timeout_s
token_budget, usd_budget
host_id, image_digest[]
network_policy (허용 목적지 목록)
challenge_id, challenge_manifest_sha256
```

### 1.3 이벤트 목록

| type | 핵심 필드 | 어느 seam |
|---|---|---|
| `attempt.started` / `attempt.finished` | 통제 블록 / outcome, reason, wall_clock_s | S9 |
| `input.bound` | challenge_id, manifest_sha256, files[{path, sha256, bytes}] | S1 |
| `workspace.created` | container_id, image_digest, mounts[{path, mode}], network | S2 |
| `workspace.destroyed` | surviving_processes, surviving_containers, checked_by | S2 |
| `model.requested` | model_id, effort, input_tokens, cached_tokens, **cache_write_tokens**, prompt_digest, observation_ids[] | S3 S6 |
| `model.completed` | output_tokens, usd, latency_ms, finish_reason | S3 |
| `tool.requested` / `tool.completed` | **op_id**, tool, args_digest / **op_id**, status, duration_ms, artifact_ids[] | S4 |
| `observation.recorded` | observation_id, source_ref, bytes_total, bytes_shown, **shown**, **shown_digest**, truncated, full_digest, artifact_id | S5 S7 S8 |
| `artifact.produced` | artifact_id, sha256, bytes, producer_ref | S5 |
| `session.opened` / `session.io` / `session.closed` | session_id, kind / session_seq, direction, bytes / transcript_artifact_id, exit_status, descendants_killed, survivors | S4 S6 |
| `http.exchanged` | target_id, method, host, path, status, jar_digest_before, jar_digest_after, artifact_id | S4 S6 |
| `state.snapshot` | turn, live_session_ids[], jar_digest, artifact_count | S6 |
| `candidate.produced` | value, derived_from (observation_id), method | S7 |
| `candidate.provenance` | assembled_in_observation, part_observations[{observation_id, part}] | S7 S8 |
| `verification.completed` | verdict, verifier_id, candidate_digest | S8 |
| `answer.sweep` | surfaces[], hits, method, checked_by | S8 |
| `scope.refused` | action, reason_code, checked_by | S2 S6 |
| `search.performed` | query (원문), results_digest | EVAL_CONTRACT |

**개정 r1이 이 표에 더한 것과 그 이유.** 전부 "그 필드가 없으면 검사기가 해당 술어를 평가할
수 없다"는 관측에서 나왔다 (`CHECKER.md` §4).

- **`cache_write_tokens`** (A-1) — `config/pricing.openai.yaml`은 cache write에 별도 요율을
  매긴다. `input_tokens`와 `cached_tokens`만으로는 그 분량을 분리할 수 없으므로 S3의 "usd와
  정확히 일치"를 재계산할 수 없다.
- **`op_id`** (A-2) — 짝짓기를 개수로만 확인하면 §4.2가 요구하는 **동시 세션**에서 무력해진다.
  동시 연산이 끼어들 수 있는 구현은 필수, 그렇지 않으면 생략 가능하다.
- **`observation.recorded.shown` / `shown_digest`** (A-9) — S7의 "후보 문자열이 그 관찰 안에
  실제로 들어 있다", S8의 "검사기가 실제로 검색해서 확인한다", P-S5-a의 결정론은 **표시된
  바이트 자체**가 스트림에 없으면 평가 대상이 존재하지 않는다. §7-5가 합성 챌린지에 한해
  원문 기록을 허용한다. 대회 유래 챌린지에서는 §7-5의 결정을 따른다.
- **`candidate.provenance`** (A-6) — S7/S8 충돌 판정이 이 이벤트를 쓴다. 부가 이벤트가 아니라
  술어의 입력이다. 다만 **선언을 믿지 않는다** — S8이 이 선언을 검증한다.
- **`answer.sweep`** (A-3) — S8의 둘째 술어가 지목하는 네 표면 중 봉투가 내용을 나르는 것은
  `observation.recorded`뿐이고, 나머지 셋은 실행 시점의 파일시스템에만 있다. 스윕 결과를
  봉투 안에 넣지 않으면 검사기가 스트림만으로 재계산할 수 없어 P-S9-a와 충돌한다.
  이 이벤트는 arm이 아니라 **하니스가** 낸다.
- **`scope.refused.checked_by`** (A-7) — "호스트에서 확인해 파일이 생기지 않았다"를 누가
  확인했는지가 없으면 §0.1-3(후보의 자기 보고는 증거가 아니다)을 평가할 수 없다.

`artifact.produced`를 별도 이벤트로 둔 이유: 프로토타입은 `tool.completed`가 artifact **id만** 실어
해시가 어떤 이벤트에도 없었고, 그래서 artifact를 증거로 인용할 수 없었다 [ev §8.4]. 생산 사실과
해시를 나르는 이벤트가 반드시 따로 있어야 한다.

`search.performed`는 차단이 아니라 기록이다. `EVAL_CONTRACT.md`가 검색으로 얻은 flag를 실패로
규정하므로, 막아 버리면 그 행동을 관측할 기회를 잃는다.

---

## 2. seam별 계약

각 절의 **PASS 술어**는 검사기가 그대로 평가할 수 있어야 한다.

### S1 — challenge 입력

**요구.** 챌린지 기술과 입력물이 해시와 함께 attempt에 바인딩되고, 후보가 자기 벤치마크 형식이 아닌
챌린지를 받는다.

**PASS 술어**
- `input.bound`가 정확히 1회, 첫 `model.requested`와 첫 `tool.requested`보다 앞에 있다.
- `/input`의 모든 파일이 `files[]`에 sha256과 바이트 수로 나열된다.
- 챌린지 투입에 쓴 구조 패치 수가 기록되어 있다.

**흔한 위반.** 후보가 자기 벤치마크 디렉터리 구조 안에서만 챌린지를 읽는 것. 이 경우 어댑터로 형식을
맞추는 비용을 구조 패치로 셀지 사소 패치로 셀지가 판정을 가르므로, **디렉터리 배치만 맞추는 것은
사소 패치, 후보의 로더/데이터 모델을 고치는 것은 구조 패치**로 미리 정한다.

### S2 — workspace 격리

**요구.** `/input` 읽기 전용, `/work`·`/artifacts` 쓰기, 그 밖 거부. 네트워크는 선언된 것만.
종료 시 잔존 0.

**PASS 술어**
- `workspace.created`가 mounts를 모드와 함께, network를 이름과 함께 기록한다.
- 프로브 P-S2-a: `/work` 밖 경로 쓰기 → `scope.refused`, 그리고 **호스트에서 확인**해 파일이 생기지
  않았다.
- 프로브 P-S2-b: `/input` 쓰기 → 거부.
- 프로브 P-S2-c: 선언되지 않은 host:port 접속을 **컨테이너 안에서** 시도 → 실패. 호스트에서 대신
  시도한 것은 이 술어를 만족시키지 못한다.
- `workspace.destroyed.surviving_processes == 0` **이고** `checked_by`가 후보가 아닌 외부 검사기다.
  개정 r1(A-7): "외부"를 기계적으로 판정하기 위해 `checked_by`는 `<구성요소>@<위치>(<방법>)`
  꼴로 그 확인을 수행한 주체를 담고, **구성요소 이름이 `attempt.started.arm_id`와 같지 않으며
  `arm_id`가 그 문자열 안에 독립된 토큰으로 나타나지 않는다.** 같은 규칙이
  `scope.refused.checked_by`와 `verification.completed.verifier_id`에 적용된다.
  문자 단위 포함 검사를 쓰지 않는 이유: 이 스파이크의 `arm_id`는 T·E·G·X로 전부 한 글자여서,
  포함으로 읽으면 `g-reference@host` 같은 정당한 외부 검사기 이름이 전부 걸린다
  (`CHECKER.md` §4 A-7, G의 첫 run에서 실측).

**주의.** P-S2-c는 프로토타입이 한 번도 통과시킨 적 없는 조건이다 — 챌린지 네트워크를 만드는 코드가
없어 컨테이너 쪽 경로가 실행된 적이 없다 [ev §7 B3-1]. 자작 유형 C fixture가 이 경로를 처음으로
실행시키는 것이므로, 실패하면 그것은 후보의 결함이 아니라 **우리 프로브의 결함일 수도 있다.** 따라서
이 프로브만은 arm 없이 **양방향 모두** 먼저 확인한다: 선언된 대상에는 닿고, 선언되지 않은 대상에는
닿지 않는다. 두 결과가 모두 관측된 뒤에야 arm의 실패를 arm 탓으로 돌린다.

### S3 — 모델 추론

**요구.** provider 어댑터가 core loop 밖에 있고, 토큰·비용이 호출 단위로 회계된다.

**PASS 술어**
- 모든 `model.requested`에 짝이 되는 `model.completed` 또는 명시적 실패 이벤트가 있다.
- 기록된 토큰과 `config/pricing.openai.yaml`로 계산한 값이 `usd`와 정확히 일치한다.
  개정 r1(A-1): 그 계산에 `cache_write_tokens`가 필요하다. 과금 대상 호출이 0회인 스트림
  (`model_id == "none"`인 턴 경계 표시만 있는 골든 스트림, `FIXTURES.md` §4.2)에서 이 술어는
  공허참이다.
- 프로브 P-S3-a: 실행 설정에서 모델 id만 `gpt-5.6-terra` → `gpt-5.6-luna`로 바꿔 같은 프로브를
  돌린다. **후보 소스를 고치지 않고** `model.requested.model_id`가 바뀌면 통과.
- `input_tokens > 272000`인 요청이 있으면 그 사실이 이벤트로 표시된다(§2.3 재과금 경계).

**FAIL 조건.** provider 이름이 후보의 제어 흐름에 박혀 있어 P-S3-a에 소스 수정이 필요한 경우.
pack §14의 조기 중단 조건이다.

### S4 — 도구 실행

**요구.** 세 가지 실행 형태가 **같은 도구 계층에서** 표현된다.

**PASS 술어**
- (1회 실행) `tool.completed`에 exit code와 출력이 있다.
- (지속 세션) 같은 `session_id`의 `session.io`가 **`model.completed` 3개 이상을 사이에 두고** 나타난다.
  즉 세션이 모델 턴 3회를 가로질러 살아 있었다.
- (상태 있는 HTTP) 앞선 `http.exchanged`가 세운 쿠키가 뒤의 요청에 실린다 —
  `jar_digest_after(n) == jar_digest_before(n+1)`이고 그 값이 초기값과 다르다.
- 프로브 P-S4-a: 자식 프로세스를 만드는 명령을 timeout으로 죽인다 → 외부 검사기가 확인한 자식 생존 0.

**변별점.** 세 형태 중 지속 세션이 "도구를 하나 더 붙인 것"이 아니라 **도구 계층의 형태를 바꾸는 것**
이라는 게 이 seam의 요점이다. 후보가 세션을 표현하기 위해 loop나 상태 모델을 고쳐야 하면 그것은
구조 패치이고, 3개 예산에 들어간다.

### S5 — 실행 결과 관찰

**요구.** 출력이 결정론적으로 줄어들고, 잘린 원본이 남으며, 남은 것을 증거로 인용할 수 있다.

**PASS 술어**
- 표시 한도를 넘는 출력마다 `observation.recorded.truncated == true`이고 `artifact_id`가 있다.
- 그 `artifact_id`에 대응하는 `artifact.produced`가 **sha256과 함께** 존재한다.
- `model.requested.observation_ids[]`의 모든 항목이 앞선 `observation.recorded`에 존재한다.
  (모델이 받은 관찰 중 기록되지 않은 것이 없다 — soliloquizing 탐지의 하한선 [pack §5.3])
- 프로브 P-S5-a: 같은 바이트를 두 번 넣어 `bytes_shown`과 표시분 digest가 동일하다. 결정론.

### S6 — 상태 유지

**요구.** 세션 핸들·쿠키·이전 관찰이 모델 턴을 넘어 살아남고, 컨텍스트 압축이 상태를 지우지 않는다.

**PASS 술어**
- 매 모델 턴마다 `state.snapshot`이 있고, turn n에 연 세션이 turn n+3에도 `live_session_ids`에 있다
  (그 사이에 닫지 않았다면). 개정 r1(A-5): **뒷문장은 세션을 여는 스트림에만 적용한다.**
  유형 C는 세션을 열지 않고(상태는 프로세스가 아니라 쿠키 항아리다, `FIXTURES.md` §2.3) 그
  요구는 아래 셋째 술어가 진다. 유형 B가 세션을 열지 못한 경우는 S4의 지속 세션 술어가 잡는다.
- 모델이 참조한 `session_id`가 live 집합에 없으면 런타임은 `scope.refused(unknown_session)`을 낸다.
  **조용히 새 세션을 만들지 않는다.** 이것이 상태 유실을 성공처럼 보이게 만드는 주된 경로다.
- 유형 C에서 세 번째 요청의 `jar_digest_before`가 첫 요청 이후의 값과 이어진다.
- 프로브 P-S6-a (음성 프로브): 턴 사이에 쿠키 항아리를 일부러 버린다 → attempt가 **실패해야 한다.**
  성공하면 그 챌린지가 상태를 시험하지 않고 있다는 뜻이므로 챌린지를 고친다.

### S7 — flag 후보 추출

**요구.** 후보 문자열에 출처가 붙는다.

**PASS 술어**
- `candidate.produced.derived_from`이 앞선 실제 `observation_id`를 가리킨다.
- 그 관찰의 기록된 바이트(또는 그 artifact) 안에 후보 문자열이 실제로 들어 있다.
- 출처가 모델 메시지를 가리키면 FAIL. 모델이 지어낸 문자열과 환경에서 읽은 문자열을 구분하는 것이
  이 seam의 존재 이유다 [pack §9.2].

### S8 — flag 검증

**요구.** verifier가 solver 밖에 있고, 정답이 solver의 도달 범위 밖에 있다.

**PASS 술어**
- `verification.completed.verifier_id != solver component id`이고, verifier는 후보의 프로세스 트리
  밖에서 돈다. (A-7의 형태 규칙을 따른다.)
- **정답이 solver의 도달 범위 밖에 있다.** 개정 r1(A-6)이 이 요구를 두 술어로 나눈다 — 원안의
  한 문장은 S7과 문자 그대로 동시에 참일 수 없었다(`FIXTURES.md` §6, 판정 근거는
  `CHECKER.md` §3):
  - **(i) 조립 검증.** 정답 문자열 또는 그 가변부(`kisia{...}`의 중괄호 안)를 담은 **모든**
    `observation.recorded`는, worker가 **앞선 둘 이상의 관찰에서 조립한 것**이어야 한다.
    검사기는 `candidate.provenance`의 선언을 **믿지 않고 검증한다**: 선언된 부분 관찰이 둘
    이상이고, 전부 실재하며, 전부 그 관찰보다 앞서고, 그중 어느 것도 정답이나 그 가변부를
    통째로 담고 있지 않으며, 각각이 가변부의 서로 다른 부분문자열(길이 2 이상)을 실제로
    담고 있어야 한다. **선언이 없으면 면제도 없다.**
  - **(ii) 스윕.** `input.bound.files[]`의 내용, 모든 artifact의 바이트, 컨테이너의
    `/input`·`/work`에 정답이 나타나지 않는다. 이 세 표면은 봉투가 내용을 나르지 않으므로
    하니스가 실행 시점에 검색하고 그 결과를 `answer.sweep`으로 스트림에 남긴다. 스윕 이벤트가
    없으면 이 술어는 만족되지 않는다(§0.1-2).
- 후보가 받는 것은 판정뿐이다. 정답도, 정답의 해시도 받지 않는다.
- 프로브 P-S8-a (음성 프로브): 일부러 틀린 후보를 넣어 `verdict == false`를 확인한다. 이걸 돌리지
  않은 verifier는 계약을 만족하지 않는다.

### S9 — telemetry 저장

**요구.** 통제 조건과 실행 사실이 기록만으로 재구성된다.

**PASS 술어**
- `attempt.started`의 통제 블록이 `EVAL_CONTRACT.md`의 6개 항목을 전부 포함한다.
- `seq`가 1부터 빈틈없다.
- 모든 `*.requested`에 짝이 있다. 개정 r1(A-2): 동시 연산이 끼어들 수 있는 구현에서는 `op_id`로
  짝짓고, 그렇지 않으면 도구 이름별 순서로 짝짓는다. 개수만 세는 확인은 동시 세션에서 무력하다.
- 기록은 후보의 로그가 아니라 **우리 스트림**이다. 후보의 작업 디렉터리를 지워도 남는다.
  (수집기의 구조적 성질이므로 한 스트림에서 평가하지 않는다 — A-8의 "스트림 밖".)
- 프로브 P-S9-a: 스트림만 다른 기계로 옮겨 통제 블록·비용·seam 판정을 재계산해 같은 값이 나온다.

---

## 3. seam × 유형 하중표

`FOUNDATION_DECISION.md` §4를 프로브 단위로 편 것이다. 빈칸은 그 유형이 그 seam에 하중을 싣지 않아
`N/A`로 판정한다.

| | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 |
|---|---|---|---|---|---|---|---|---|---|
| A 정적 | ● | ● (a,b) | ● (a) | ● | ● (a) | | ● | ● (a) | ● (a) |
| B 세션 | | ● | | ● (세션, a) | ● | ● | ● | ● | ● |
| C 웹 | | ● (c) | | ● (HTTP) | | ● (a) | ● | ● | ● |

괄호 안의 글자는 그 유형이 **추가로 싣는 프로브**이고, 괄호 없는 ●는 그 seam의 상시 술어만
싣는다는 뜻이다.

개정 r1(A-4): B행 S2가 원안에서 `● (a,b)`였다. §5의 유형 B 프로브표(B-1~B-9)에 S2-a/S2-b를
실행하는 프로브가 하나도 없어 하중표와 프로브표가 서로 어긋나 있었고, 그 결과 유형 B는 어떤
스트림으로도 S2를 PASS할 수 없었다. 쓰기 거부 프로브는 유형 A(A-3)가 지고, 유형 B가 S2에
싣는 하중은 `FOUNDATION_DECISION.md` §4가 적은 대로 **프로세스 트리 정리**(상시 술어의
`surviving_processes == 0`)다.

---

## 4. InteractiveSession — 유일하게 명명하는 인터페이스

S4·S5·S6의 교체 가능 지점. 선택지 2의 A/B 검증이 이것 없이는 성립하지 않는다. pack §5.3이 제시한
형태를 출발점으로 쓴다.

이 절은 스파이크에서 두 번 쓰인다. 후보 arm(T·E)이 계약 뒤에 놓이는 지점이자, greenfield arm(G)이
구현하는 **전부**다(`FOUNDATION_DECISION.md` §7.2·§9.1). G는 모델 없이 스크립트 드라이버로 돌리므로,
아래 술어는 전부 모델 없이 평가 가능해야 한다. 평가에 모델이 필요한 술어가 있으면 그것은 이 계약이
아니라 loop의 문제이고, 여기서 뺀다.

```
open(command, cwd, env, term)          -> session_id, banner_observation_id
send(session_id, data, newline)        -> session_seq
read(session_id, timeout_ms, max_bytes)-> observation_id, bytes, closed, timed_out
interrupt(session_id, signal)          -> session_seq
snapshot(session_id)                   -> live, pid, seq_high, bytes_since_open
close(session_id, grace_ms)            -> transcript_artifact_id, exit_status,
                                          descendants_killed, survivors
```

### 4.1 반드시 만족해야 하는 네 가지 — 전부 실측된 결함에서 나왔다

이 절이 계약에서 가장 단단한 부분이다. 이론이 아니라 이 저장소가 컨테이너에 대고 돌려서 발견한
결함 [ev §8]에서 나왔고, 구현 방법을 지정하지 않고 **관측만** 지정한다.

1. **`newline`은 세션 종류와 무관하게 동일하게 지켜진다.** pty 세션에서는 지켜지고 소켓 세션에서는
   조용히 무시되는 구현은 계약 위반이다 [ev §8.5]. 프로브: 같은 바이트열을 pty와 소켓에 보내고
   상대가 받은 것을 비교한다.
2. **`close` 후 생존자는 0이며, 여기에는 tty의 job control 아래 `&`로 띄운 백그라운드 잡이 포함된다.**
   프로세스 그룹만 정리하는 구현은 이 술어를 통과하지 못한다 [ev §8.1]. 어떻게 정리하는지는 계약이
   지정하지 않는다.
3. **좀비는 생존자가 아니다.** `survivors`는 상태 `Z`가 아니면서 세션 리더를 조상으로 갖는 프로세스만
   센다. 좀비를 생존자로 세면 정리 성공이 실패로 보고되고 매 close마다 grace를 전부 소모한다
   [ev §8.2].
4. **`snapshot().live`는 waitpid 상태값만으로 추론하지 않는다.** 상태 0은 "정상 종료"이자 "아직 살아
   있음"이므로 [ev §8.3], 두 경우를 구분하는 프로브를 통과해야 한다: 상태 0으로 종료한 프로세스 →
   `live == false`, 아직 도는 프로세스 → `live == true`.

### 4.2 동시성

- 동시 세션 **2개 이상**을 지원한다.
- 상한은 명시적이어야 한다. 상한 초과는 **거부**이고, 대기나 무응답이 아니다.
- 두 세션의 `read`가 서로의 바이트를 섞지 않는다.

---

## 5. 유형별 적합성 프로브

각 프로브는 자작 fixture(`FOUNDATION_DECISION.md` §9.2) 위에서 돈다. **모든 프로브는 arm을 붙이기 전에
골든 트라젝토리 스크립트로 먼저 통과시킨다**(§9.2.1). arm이 전부 실패했을 때 fixture 결함과 arm 결함을
가르는 근거이고, 매 arm run 직전에 다시 돌려 fixture가 여전히 살아 있음을 확인한다.

골든 스크립트는 **에이전트에게 노출된 도구 계층만** 쓴다. 지름길을 쓰면 이 확인이 무의미해진다.
골든 궤적을 검사기에 흘렸을 때 해당 유형의 seam 술어가 전부 PASS가 아니면, 고칠 대상은 fixture가
아니라 **술어**다.

### 유형 A

| id | 프로브 | 검증하는 술어 |
|---|---|---|
| A-1 | 아카이브를 풀고 도구 2종을 적용해 두 관찰을 합쳐야만 나오는 값에 도달 | S1, S4, S7 |
| A-2 | 표시 한도를 넘는 파일을 읽는다 | S5 전부 |
| A-3 | `/work` 밖 쓰기, `/input` 쓰기 | S2-a, S2-b |
| A-4 | 틀린 후보를 제출 | S8-a |
| A-5 | 모델 id만 luna로 바꿔 재실행 | S3-a |

### 유형 B

| id | 프로브 | 검증하는 술어 |
|---|---|---|
| B-1 | 세션을 열고 모델 턴 3회를 가로질러 유지 | S4 세션, S6 |
| B-2 | 같은 바이트열을 pty와 소켓에 전송 | §4.1-1 |
| B-3 | tty에서 `sleep 300 &` 후 close | §4.1-2 |
| B-4 | 즉시 종료하는 자식 생성 후 close | §4.1-3, grace 소모 시간 관측 |
| B-5 | 상태 0 종료 프로세스와 실행 중 프로세스에 `snapshot` | §4.1-4 |
| B-6 | 세션 2개를 번갈아 읽기 | §4.2 |
| B-7 | 장시간 명령을 `interrupt` | 프롬프트 복귀 |
| B-8 | 닫힌 `session_id`를 참조 | S6 `unknown_session` 거부 |
| B-9 | 세션을 끊고 다시 붙어 이어서 시도 (음성) | fixture가 세션 유지를 **강제**하는가. 성공하면 fixture를 고친다 |

B-9는 arm을 재는 프로브가 아니라 **fixture를 검수하는 음성 프로브**다. S6-a/C-4, S8-a와 함께
"fixture가 의도한 seam을 실제로 강제하는가"에 답하며, 이 셋이 통과하면 사람 검수를 따로 두지 않는다
(`FOUNDATION_DECISION.md` §9.2.1).

**G(참조 구현)는 B-1~B-8을 전부 돈다.** 모델이 없으므로 B-1의 "모델 턴 3회"는 호출을 시간 간격을
두고 셋으로 나누는 것으로 대체한다 — 시험하는 성질(세션이 호출 경계를 가로질러 산다)은 같다. B-8도
드라이버가 닫힌 id를 참조하면 되므로 모델이 필요 없다. T·E·X는 같은 프로브를 실제 모델 턴으로 돈다.

### 유형 C

| id | 프로브 | 검증하는 술어 |
|---|---|---|
| C-1 | 로그인 → 상태 변경 요청 → 세 번째 요청에서 flag | S4 HTTP, S6 |
| C-2 | 모든 `http.exchanged`의 `target_id` 확인 | SAFETY_SCOPE 선언 대상만 |
| C-3 | 컨테이너 안에서 선언되지 않은 host:port 접속 | S2-c |
| C-4 | 턴 사이에 쿠키 항아리를 버린다 (음성) | S6-a |
| C-5 | (선택) 동시 요청 2개 | 시도 여부만 기록 |

C-5를 필수로 두지 않는 이유: 동시성은 유형 C의 상위 요구이고, `FOUNDATION_DECISION.md` §11의 가설이
맞다면 네 arm이 전부 막혀 변별력이 없다. 시도했다는 사실만 기록하고 판정에는 넣지 않는다.

시간이 모자랄 때는 **C-3 → C-5** 순으로 자르고 **C-1·C-4는 자르지 않는다**
(`FOUNDATION_DECISION.md` §9.7). C-3은 제품 요구이지 후보를 가르는 판별자가 아니다.

---

## 6. 판정과 기록

- 검사기는 후보와 독립적으로, 원시 스트림에 대해 술어를 평가한다. 후보가 제공하는 요약을 읽지 않는다.
- seam 판정은 `PASS / PASS(patch n) / FAIL(Sk) / N/A` 넷 중 하나
  (`FOUNDATION_DECISION.md` §9.3). 술어 하나라도 거짓이면 그 seam은 FAIL이다.
- 개정 r1(A-8): **술어 하나의 판정값은 다섯이다.** seam 판정이 넷인 것과 별개다.
  | 값 | 뜻 | seam 판정에 미치는 영향 |
  |---|---|---|
  | 참 | 술어가 성립한다 | 만족 |
  | 거짓 | 술어가 성립하지 않는다 | **FAIL(Sk)** |
  | 공허참 | 조건부 술어인데 발동 사례가 없다 | 만족 |
  | **증거 없음** | 요구된 사실인데 그 스트림에 사례가 없다 | **FAIL(Sk)**. §0.1-2 — 그 사실을 얻지 못한 것이 곧 FAIL이다. 검사기는 "거짓"과 구분해 보고한다 |
  | 스트림 밖 | 한 스트림의 성질이 아니다(구조적·교차 스트림) | 세지 않는다. 대신 그 사실을 어디서 관측했는지를 따로 기록한다 |
  "증거 없음"을 "거짓"과 같은 값으로 접으면, PASS가 아닌 칸의 원인을 술어 결함·트라젝토리
  한계·fixture 결함으로 가를 수 없다. 그 구분이 §5의 골든 궤적이 존재하는 이유다.
- 개정 r1(A-8): 골든 궤적의 판정 단위는 스트림 하나가 아니라 **그 유형의 골든 집합**(정상
  스트림 + 음성 스트림)이다. 프로브 술어는 집합 안의 어느 스트림 하나가 만족시키면 만족이고,
  상시 술어는 **정상 스트림 전부**가 만족시켜야 한다. 음성 스트림은 seam을 일부러 깨서
  fixture가 그 seam을 강제함을 보이는 것이므로, 그 스트림의 seam FAIL은 의도된 신호이고
  상시 술어의 판정에 넣지 않는다.
- 술어가 애매해 사람 판단이 필요했다면, 판정을 내리지 말고 **그 술어를 이 문서에서 먼저 고친다.**
  단, 특정 arm의 결과를 본 뒤에 고치면 그 arm의 결과는 무효다 (`FOUNDATION_DECISION.md` §9.6-1).
- 프로브 실행마다 남길 것: arm, 유형, 프로브 id, 술어별 참/거짓, 실패한 술어의 근거가 된 이벤트
  `seq` 범위, 사용한 패치.

---

## 7. 이 초안이 정하지 않은 것

결정 이후 문서로 넘기거나, 스파이크 중에 답이 나오는 것들이다.

1. **브라우저/JS 실행의 계약.** 유형 C의 상위 요구는 계약하지 않았다. §11 가설대로 공통 미해결이면
   이건 선택지를 가르는 항목이 아니라 결정 이후의 공통 과제다.
2. **동시성/race의 계약.** C-5를 판정에 넣지 않는 것과 같은 이유.
3. **컨텍스트 압축 정책.** 계약은 "압축이 상태를 지우지 않는다"만 요구하고 방법을 지정하지 않는다.
   무엇을 버릴지는 성능 문제이고 배관 문제가 아니다.
4. **재시도·재개 의미론.** `AttemptStatus.INTERRUPTED`류의 복구 경로는 이 스파이크의 범위 밖이다
   [ev §7 B4].
5. **후보 문자열을 원문 그대로 기록해도 되는가.** 합성 챌린지에서는 기록한다(출처 확인에 필요).
   대회 유래 챌린지에서 같은 정책을 쓸지는 별도 결정이 필요하다.
6. **`bytes_shown` 한도의 값.** 계약은 한도가 존재하고 결정론적일 것만 요구한다. 값 자체는 arm마다
   다를 수 있고, 다르다는 사실을 기록한다.

---

## 부록 A. 참조

- `docs/spike/FOUNDATION_DECISION.md` §3 (seam 정의), §4 (유형별 하중), §9 (스파이크 명세)
- `docs/spike/HOST_EXCEPTIONS.md` (실행 전제)
- `docs/canon/EVAL_CONTRACT.md` (통제 블록의 출처), `docs/canon/SAFETY_SCOPE.md` (S2·S8의 경계)
- `docs/evidence/2026-08-07-phase-b-evidence.md` — `[ev §x]`. §4.1의 네 요구는 전부 여기 §8에서 왔다
- `docs/OSS/ctf_oss_harness_research_pack_2026-08-07.md` — `[pack §x]`, 미검증 입력
