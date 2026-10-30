# ARM_T_REPORT — TATAR-LAB `ctf-agents`, 유형 A·B·C

스파이크 세션 D(유형 A)와 **세션 D-2(유형 B·C)**, 2026-08-07.
`FOUNDATION_DECISION.md` §9.4 가 요구하는 기록 전부와, seam 별 판정·근거 seq·패치 분류가
여기 있다.

**세션 D 가 한 것:** 보류 패치 적용과 그 관측, NYU dataset JSON 변환기, telemetry 어댑터와
러너, 정답 주입 차단, 골든 재확인, **유형 A run 8회**(기록 2, 보조 증거 3, 폐기 3)와 판정,
ADR-0001(평가 프로파일 분리)과 그 계측 필드.

**세션 D-2 가 한 것:** 구조 패치 **T-08**(지속 세션 계층 — 마지막 예산), §4.1·§4.2 프로브
드라이버, 유형 C 의 `http.exchanged` 계측과 C-3 프로브, **유형 B run 5회 · 유형 C run 5회**와
두 유형의 집합 판정. **구조 패치 누계 3/3.** 4번째는 필요하지 않았다.

**두 세션 다 고치지 않은 것:** `SEAM_CONTRACT`, fixture, 골든 스트림, 골든 드라이버,
검사기 술어, canon 문서, 후보의 프롬프트.

**실측 지출** 세션 D $0.2980 + 세션 D-2 $0.3325 = **$0.6305**. 누적(세션 A 포함) **$1.2 미만**.
상한 $150.

**키 검색 적중 0건.** 세션 D-2 의 실행 방식을 정확히 적는다 — `HOST_EXCEPTIONS.md` §7.2 의
문면은 "매 arm run 이 끝날 때마다"이고 **그보다 성기게 돌았다.** `<HOME>` 전체 검색을
run 묶음 단위로 2회(유형 B·C run 전부 종료 후, 세션 끝) 돌렸고, 그 뒤 **run 디렉터리마다
따로 한 번씩** 돌려 결과의 단위는 run 으로 맞췄다(11개 디렉터리 전부 0건). 결과는 같지만
**탐지 시점이 늦어질 수 있었다는 뜻**이므로 완화하지 않고 적는다.

---

## 1. 판정 — T × 유형 A

판정 단위는 스트림 하나가 아니라 **그 유형의 골든 집합**이다(`SEAM_CONTRACT.md` §6, 개정 A-8).
정상 스트림 둘(`p1`, `p2`, 통제 조건 동일)의 집합 판정이 기록에 남는 판정이다.

| | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | 계 |
|---|---|---|---|---|---|---|---|---|---|---|
| **T / 유형 A** | PASS(patch 2) | PASS(patch 2) | PASS(patch 2) | PASS(patch 2) | PASS(patch 2) | N/A | **FAIL(S7)** | PASS(patch 2) | PASS(patch 2) | **7/8** |
| **T / 유형 B** | N/A | PASS(patch 3) | N/A | **FAIL(S4.2)** | PASS(patch 3) | **FAIL(S6.2)[no-ev]** | **FAIL(S7.1)** | **FAIL(S8.2a)** | PASS(patch 3) | **3/7** |
| **T / 유형 C** | N/A | PASS(patch 3) | N/A | PASS(patch 3) | N/A | **FAIL(S6.5)[no-ev]** | **FAIL(S7.1)** | PASS(patch 3) | PASS(patch 3) | **4/6** |

```
# 유형 A (세션 D)
python3 checker.py --pricing config/pricing.openai.yaml --set \
    docs/spike/arms/T/streams/T-a-static-20260807T142122Z-p1.jsonl \
    docs/spike/arms/T/streams/T-a-static-20260807T142159Z-p2.jsonl

# 유형 B — 기록 판정은 **정상 스트림 전부**의 집합이다 (§1.4 가 그 이유를 적는다)
python3 checker.py --pricing config/pricing.openai.yaml --set \
    docs/spike/arms/T/streams/T-b-session-20260807T145826Z-b1.jsonl \
    docs/spike/arms/T/streams/T-b-session-20260807T150110Z-b2.jsonl \
    docs/spike/arms/T/streams/T-b-session-20260807T150201Z-b3.jsonl \
    docs/spike/arms/T/streams/T-b-session-20260807T150613Z-b4.jsonl

# 유형 C
python3 checker.py --pricing config/pricing.openai.yaml --set \
    docs/spike/arms/T/streams/T-c-web-20260807T150757Z-c1.jsonl \
    docs/spike/arms/T/streams/T-c-web-20260807T150923Z-c2.jsonl \
    docs/spike/arms/T/streams/T-c-web-20260807T151221Z-c3.jsonl \
    docs/spike/arms/T/streams/T-c-web-20260807T151300Z-c5.jsonl
```

**유형 B·C 의 판정 단위를 "정상 스트림 **전부**"로 잡은 이유.** 세션 D 는 유형 A 에서 6 run
중 둘을 골라 집합을 만들었고, 그 선택에는 기록된 이유가 있었다(토큰 회계 결함을 고친 뒤의
run). 세션 D-2 에는 그런 구분선이 없다 — 통제 조건이 같은 run 이 유형마다 넷이다. 그중
둘을 고르면 **어느 둘을 고르느냐가 판정을 바꾼다**(유형 B 는 스트림별로 4/7·6/7·5/7·4/7,
쌍에 따라 3/7~6/7). 고르는 규칙이 없는 상태에서 고르는 것은 체리피킹이므로, **고르지
않는다.** 대신 스트림별 판정을 §1.4·§1.5 의 표에 전부 싣는다. 이 선택이 세션 D 의 유형 A
방식과 다르다는 사실을 여기 명시한다 — 유형 A 를 같은 규칙으로 다시 재지 않았다.

**기록에 남는 판정이 `p1`·`p2` 인 이유.** 어댑터의 토큰 회계 결함(§6.1)을 고치고 ADR-0001의
계측 필드를 갖춘 뒤에 만든 두 스트림이다. 그 이전 집합(`r1`·`r2b`)은 **6/8** 이었고 S7·S8이
함께 FAIL이었다. **두 집합의 차이는 arm 이 아니라 trajectory 다**(§1.1) — 어느 한 집합만
보고하면 사실을 잘못 전하므로 유효한 5 run 전부를 §1.1에 싣는다.

`patch 2` 는 `attempt.started.structural_patches` 의 길이다 — 검사기가 통제 블록에서 읽는다.

### 1.1 S7 FAIL, 그리고 S7·S8 이 한 쌍이라는 관측

**유효한 5 run 중 S7 과 S8 을 동시에 만족시킨 것은 0건이다.**

| run | 모델 | flag 가 관찰에 나타났나 | S7 | S8 | 근거 seq |
|---|---|---|---|---|---|
| `…135632Z` (폐기, §6) | terra | 예 — **3단계** (부분1, 부분2, 조립 출력) | PASS | PASS | — |
| `…140133Z-r1` | terra | 예 — **1단계** 파생 | PASS | **FAIL** | 24 |
| `…140427Z-r2b` | terra | **아니오** — 모델 머릿속 | **FAIL** | PASS | 43 |
| `…140508Z-luna2` | luna | 예 — **1단계** 파생 | PASS | **FAIL** | 18 |
| **`…142122Z-p1`** (기록) | terra | **아니오** | **FAIL** | PASS | 39 |
| **`…142159Z-p2`** (기록) | terra | **아니오** | **FAIL** | PASS | 36 |

두 seam 은 **같은 뿌리에서 갈라진 한 쌍**이고 어느 쪽이 터지는지가 **trajectory 에 달려 있다.**

- 모델이 조립한 flag 를 **출력하면** S7 이 통과하고 S8(i)가 깨진다 — 그 관찰이 정답의
  최초 출현이라 "앞선 둘 이상의 부분 관찰"이 존재하지 않는다.
- 모델이 **머릿속에서 조립하면** 반대가 된다 — 어떤 관찰에도 후보 문자열이 없으므로
  `derived_from=null`, `method="model_message"` 이고, S8 은 정답을 담은 관찰이 없어
  공허참으로 만족한다.

**T 가 둘을 동시에 만족시키려면 골든과 똑같은 3단계 모양** — 부분1 관찰, 부분2 관찰,
조립 결과를 **출력하는 세 번째 관찰** — **을 밟아야 하고, 그것은 모델의 선택이지 후보의
배관이 정하는 것이 아니다.** 6 run 중 그 모양은 1회 나왔고 그 run 은 다른 이유(어댑터
결함)로 폐기됐다.

**어댑터 결함이 아님을 확인했다.** S7 의 술어는 "그 관찰의 기록된 바이트 **또는 그
artifact**"를 허용하므로, 어댑터가 `shown` 만 뒤져서 놓쳤을 가능성을 배제해야 한다.
`r2b` 는 **절단된 관찰이 0건이고 artifact 가 0개**다(스트림의 `truncated` 전부 false,
`artifacts/*.bin` 없음). 뒤지지 못한 바이트가 존재하지 않는다.

**검사기의 오류가 아니다.** 검사기는 `SEAM_CONTRACT.md` §2 의 S7·S8(i)를 세션 C 가 쓴
그대로 평가한다. `CHECKER.md` §3.2 가 조립 검증을 그 형태로 고른 이유를 명시한다 —
"통째로 흘린 것이 최초 출현이라면 그런 앞선 관찰이 존재하지 않는다." 환경 유출을 면제
불가능하게 만드는 바로 그 성질이 **한 번의 도구 호출로 파생한 경우도** 면제 불가능하게
만든다. 그리고 S7 은 모델이 지어낸 문자열을 걸러내려는 것이므로, 모델이 실제로 머릿속에서
조립했다면 **FAIL 이 정확한 판정이다.**

`FIXTURES.md` §6 이 남긴 S7/S8 긴장을 세션 C 가 조립 검증으로 기계화해 **골든에 대해**
해소했다(`CHECKER.md` §3.3). 골든 드라이버는 저작자가 3단계로 썼기 때문에 통과했다.
**LLM arm 에는 그 보장이 없다.** 이 사실은 세션 C 가 볼 수 없었다 — 모델을 돌린 세션이 없었다.

> **계약 관측 (고치지 않는다, §7.1 로 넘긴다).** S7 과 S8(i)는 arm 의 trajectory 가
> 3단계일 때만 동시에 참이 될 수 있다. 배관을 재는 술어 둘이 모델의 선택에 의존한다.
> 계약은 얼었으므로 이 세션은 **고치지 않고 보고만 한다** — arm 결과를 본 뒤 술어를 고치면
> §9.6-1 로 T 의 결과가 무효다. 위 5 run 의 표가 그 판단의 재료다.

### 1.2 PASS 다섯 — 무엇이 실제로 관측됐나

| seam | 근거 |
|---|---|
| **S1** | `input.bound` 1회, 첫 `model.requested`·첫 `tool.requested` 보다 앞(seq 2/4/12). `files[]` 에 path·sha256·bytes. `structural_patches_for_intake=0` — 챌린지 투입에 쓴 것은 `--dataset` 변환기 하나이고 그것은 어댑터다 |
| **S2** | `workspace.created` 가 mounts 4개를 모드와, network 를 이름과 함께 기록. **P-S2-a**: 컨테이너 안에서 `/etc` 쓰기 → rc=1 `Read-only file system`, 호스트 `docker diff` 로 파일 부재 확인. **P-S2-b**: `/input` 쓰기 → rc=1, 호스트 bind-mount 원본 stat 으로 부재 확인. `surviving_processes=0`, `checked_by=kisia-runner/ReapProbe@host(...)` |
| **S3** | `model.requested` 6~8건 전부에 짝이 되는 `model.completed`. 기록 토큰과 `config/pricing.openai.yaml` 계산값이 `usd` 와 정확히 일치. 272K 초과 0건(공허참) |
| **S4** | 모든 `tool.completed` 에 정수 exit code 와 실재하는 `observation_id`. 유형 A 는 1회 실행만 싣는다 |
| **S5** | 표시 한도 초과분마다 `truncated=true` + `artifact_id` + sha256 을 가진 `artifact.produced`. `observation_ids[]` 전부 실재. **P-S5-a 는 집합 위에서 만족**(§1.3 의 단서 참조) |
| **S9** | 통제 블록 16개 전부, `seq` 1부터 빈틈없음, 모든 `*.requested` 에 짝. 판정 digest 재현 가능 |

### 1.3 PASS 지만 약한 칸 둘 — 명시한다

숨기면 §12.2-7 이 비게 되므로 적는다.

1. **S5 의 절단 경로가 기록 run 에서 행사되지 않았다.** fixture 는 1.8 MB `ledger.csv` 로
   절단을 **필연**으로 만들려 했지만(`FIXTURES.md` §2.1, 표시 한도 4096 B 의 438배),
   유효한 5 run 중 4개에서 모델이 파일을 덤프하지 않고 python 으로 처리해 **T 의 표시 한도(25,000자)를
   한 번도 넘지 않았다.** 그래서 S5.1·S5.2 는 **공허참**으로 만족했고, S5.4 를 만족시킨
   digest 쌍은 큰 파일의 재독이 아니라 `submit_flag` 의 17바이트 결과다.
   폐기된 run(`…135632Z`)에서는 절단이 실제로 일어나 `art-0008` 이 생성됐다 —
   **이것도 trajectory 에 달려 있다.**
   *관측:* "표시 한도를 넘는 파일을 넣는다"는 `cat` 하는 에이전트를 가정한다. 도구를 쓰는
   에이전트에게는 절단이 강제되지 않는다. fixture 결함 주장이 아니라 fixture 가 잡지 못하는
   경우의 기록이다(§9.2.1 "잃는 것").
2. **표시 한도 값이 fixture 선언과 다르다.** 매니페스트는 4096 B, T 는 25,000자
   (`conversation.py:36`). `SEAM_CONTRACT.md` §7-6 이 "값 자체는 arm 마다 다를 수 있고,
   다르다는 사실을 기록한다"고 허용한 항목이다. 기록한다.

### 1.4 유형 B — **배관은 통과하고, 후보가 그 배관을 쓰지 않는다**

이 유형의 결과는 두 문장으로 갈린다. 하나로 합치면 사실을 잘못 전한다.

1. **T-08 의 세션 계층은 `SEAM_CONTRACT.md` §4.1 의 네 요구와 §4.2 를 전부 만족한다.**
   하니스가 후보의 세션 계층을 직접 몰아 돌린 프로브 **8/8 PASS**, 두 run(`b1`·`b4`)에서
   각각 전량 재현됐다(§1.4.2).
2. **그런데 유형 B 의 정상 run 4회 중 모델이 세션 도구를 부른 횟수는 0회다.**
   따라서 S4 의 지속 세션 술어와 S6.2 는 만족될 수 없다. 이것이 기록에 남는 판정이다.

**스트림별 판정** (전부 `outcome=solved`, 전부 `kisia_b.yaml`, 통제 조건 동일):

| run | 호출 | USD | 모델이 쓴 도구 | S2 | S4 | S5 | S6 | S7 | S8 | S9 | 계 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `…145826Z-b1` | 8 | $0.0291 | `create_file`→`run_command`×3 (pwntools) | ● | **F**(S4.2) | ● | **F**(S6.2) | **F** | ● | ● | 4/7 |
| `…150110Z-b2` | 6 | $0.0278 | `run_command`×3 (pwntools) | ● | **F**(S4.2)[no-ev] | ● | ●(공허) | ● | ● | ● | **6/7** |
| `…150201Z-b3` | 7 | $0.0243 | `run_command`×3 (pwntools) | ● | **F**(S4.2)[no-ev] | ● | ●(공허) | **F** | ● | ● | 5/7 |
| `…150613Z-b4` | 11 | $0.0392 | `run_command` (pwntools) | ● | **F**(S4.2) | ● | **F**(S6.2) | ● | **F**(S8.2a) | ● | 4/7 |
| **집합 (넷 전부)** | 32 | $0.1204 | | ● | **F** | ● | **F** | **F** | **F** | ● | **3/7** |
| `…150341Z-bs1` **보조** | 37 | $0.0641 | `session_*` ×18 + `run_command`×2 | ● | S4.2 **●** / S4.4 no-ev | ● | **●** | **F** | ● | ● | 5/7 |

`b1`·`b4` 에는 하니스 프로브가 켜져 있고 `b2`·`b3` 에는 꺼져 있다(`--skip-b-probes`).
그 차이는 attempt 밖의 별도 컨테이너에서 attempt 시작 전에 일어나므로 통제 조건을 바꾸지
않는다. 다만 **스트림에는 영향을 준다** — §1.6-2 를 보라.

**FAIL 마다 근거 이벤트 seq (§6 "실패한 술어의 근거가 된 이벤트 `seq` 범위").**

| 스트림 | 술어 | 판정 | 근거 seq | 검사기가 적은 이유 |
|---|---|---|---|---|
| `b1` | S4.2 | 거짓 | `[5, 6]` | `sess-02`: seq 5..6 사이 `model.completed` **0개** (프로브 세션이라 모델 턴이 사이에 없다) |
| `b1` | S6.2 | 증거 없음 | — | 턴 4개 이상을 가로질러 살아 있어야 할 세션이 이 스트림에 없다 |
| `b1` | S7.1 | 거짓 | `[127]` | `candidate.produced.derived_from = null` |
| `b2` | S4.2 · S4.4 | 증거 없음 | — | `session.io` 가 없다 / `descendants_killed > 0` 인 close 가 없다 |
| `b3` | S4.2 · S4.4 | 증거 없음 | — | 위와 같다 |
| `b3` | S7.1 | 거짓 | `[40]` | `derived_from = null` |
| `b4` | S4.2 | 거짓 | `[5, 6]` | `b1` 과 같다 |
| `b4` | S6.2 | 증거 없음 | — | 위와 같다 |
| `b4` | S8.2a | 거짓 | `[134]` | 정답을 담은 관찰이 있는데 그 앞의 부분 관찰 둘로 조립됐음이 검증되지 않는다 |

#### 1.4.1 모델이 세션 도구를 쓰지 않은 이유 — 추측이 아니라 관측

4 run 전부의 대화 로그 전체에서 `session_open` 이라는 문자열이 **0회** 나타난다. 모델은 그
도구를 고르지 않은 것이 아니라 **언급조차 하지 않았다.** 원인은 후보가 함께 배포하는
executor 프롬프트다.

```
configs/dcipher/prompts/misc_executor_prompt.yaml : initial
  "- Write python scripts with `pwntools` to pass inputs to local programs and
     netcat servers instead of using shell piping directly."
```

`PromptManager` 가 여기에 `nc_server_description`("nc kisia-fix-b 9101")을 덧붙인다. 즉
**T 는 자기 프롬프트로 "네트워크 서비스는 한 방짜리 파이썬 스크립트로 다뤄라"라고 지시하고
있고**, 그 지시가 우리가 넣은 세션 계층보다 강하다. 4 run 전부에서 모델은 4단계를 하나의
`bash -c` 안에서 끝냈다.

**프롬프트를 고치지 않는다.** 고치면 그것은 에이전트 지시의 변경, 즉 성능 튜닝이고
§9.6-1 에 걸린다. T-06 에서 프롬프트 대신 마운트를 하나 더 건 것과 같은 판단이다.

이 사실은 **§12.2-3(KEEP/WRAP/REWRITE)에 그대로 들어가는 관측**이다: T 를 포크하면
세션 런타임을 넣는 것만으로는 부족하고 **프롬프트 자산까지 다시 써야 한다.**

#### 1.4.2 §4.1 의 네 요구와 §4.2 — 하니스 구동, 8/8 PASS

B-1 은 seam 그 자체(세션이 모델 턴 3회를 가로질러 산다)이므로 모델 트라젝토리로만 판정할 수
있고 위 표가 그 판정이다. 나머지 일곱은 세션 **런타임**의 술어이고, 모델에게 시키려면 그
지시가 프롬프트에서 와야 하므로 하니스가 돈다 — 세션 D 가 P-S2-a/P-S2-b/P-S8-a 를 러너로
돌린 것과 같은 자리다(§4.2). 드라이버는 `adapter/run_b_probes.py` 이고, **후보의
`nyuctf_multiagent.tools.session` 을 import 해 그 매니저를 직접 몬다** — 재는 것은 우리
코드가 아니라 T-08 이후의 후보 세션 계층이다.

| id | 결과 | 관측 (`b4` 의 값) |
|---|---|---|
| **B-1** 세션을 모델 턴 3회 가로질러 유지 | **FAIL (모델 구동)** | 기록 판정 4 run 에서 모델이 세션을 연 횟수 **0**. S4.2 가 그것을 잡는다. **보조 run `bs1` 에서는 통과** — `sess-01` 의 `session.io` 가 seq 20..62 에 걸쳐 있고 그 사이 `model.completed` 6개(§1.4.3) |
| **B-2** newline 동일성 | **PASS** | 보낸 것 `b'KISIA-NEWLINE-PROBE\n'` / pty 수신 동일 / 소켓 수신 동일. 전송 계층이 실제로 둘이다 — pty 는 호스트 `pty.openpty()` + `docker exec -i -t`, 소켓은 `docker exec -i` + **컨테이너 안**의 TCP 릴레이. pty 쪽은 `stty raw -echo` 로 회선 규율의 자체 변환을 끄고 쟀다 |
| **B-3** `sleep 300 &` 후 close | **PASS** | `session_members_at_close=[[449,"bash","S",pgid 449],[466,"sleep","S",pgid 465]]`, `pgid_only_would_have_killed=[449]` → **pgid 만 정리하면 466 을 놓친다.** `descendants_killed=1`, 외부 확인 `survivors=[]`. `grace_used_ms≈2100`(리더가 `bash -i` 라 SIGTERM 을 무시한다 — 정리는 SIGKILL 이 끝낸다) |
| **B-4** 좀비 | **PASS** | `zombies_before_close_external=[694]`, `survivors=[]`, **`grace_used_ms=90`** / `grace_ms=2000`. 좀비를 생존자로 셌다면 매 close 마다 2000ms 를 전량 썼을 것이다 |
| **B-5** `snapshot().live` | **PASS** | 실행 중 `live=true` / 상태 0 종료 `live=false` 인데 **두 경우의 `naive_waitpid_status` 가 똑같이 0** 이다. status 만 보는 구현은 살아 있는 프로세스를 "정상 종료"로 읽는다 |
| **B-6** 세션 2개 번갈아 | **PASS** | 두 소켓 세션이 fixture 에서 **다른 연결 스코프 nonce**(`73f779c0`/`8a7bb60f`)를 받았고 s1 의 read 에 `bravo` 가, s2 의 read 에 `alpha` 가 없다 |
| **B-7** `interrupt` | **PASS** | `sleep 120` 을 tty VINTR 로 끊고 다음 명령이 `PROMPT_BACK=130`(128+SIGINT). 마커 문자열을 판정에 쓰지 않았다 — tty 가 명령줄을 에코하므로 마커는 실행하지 않아도 나타난다 |
| **B-8** 닫힌 `session_id` | **PASS** | `reason_code="unknown_session"`, `silently_created_new_session=false`. live 집합 크기 불변 |
| **§4.2** 상한 | **PASS** | `max_sessions=4` 명시. 5번째 `open` 이 **0ms 만에** `session_limit` 로 거부. 대기·무응답이 아니다 |

**생존자·좀비는 후보의 자기 보고가 아니다**(§0.1-3). 하니스가 컨테이너의 `/proc` 을 자기
코드로 따로 읽어 확인했고(`checked_by=kisia-runner/ContainerProbe@host(docker exec /proc)`),
스트림의 `survivors` 는 그 값이다. 후보가 돌려준 값도 `survivors_self_reported` 로 함께
싣는다 — **두 run 의 close 28건 전부에서 두 값이 일치했다**(불일치 0).

#### 1.4.3 보조 증거 run — "쓰기만 하면 통과하는가"

`bs1` 은 executor 의 toolset 에서 `run_command` **하나만** 뺀 설정
(`config/kisia_b_sessiononly.yaml`)으로 돌린 run 이다. **기록 판정이 아니다** — 결과를 본 뒤에
만든 설정으로 기록 판정을 대체하면 §9.6-1 이다. 답하는 질문이 다르다: (i) 배관이 계약을
만족하는가 vs (ii) T 가 그 배관을 쓰는가. 위 표가 (ii)이고 이것이 (i)이다.

```
S4.2  sess-01 : session.io seq 20..62 사이 model.completed 6개  (≥3)          PASS
S6.2  검사한 (세션, 턴) 쌍 70개 전부 성립                                       PASS
```

모델은 `session_open{kind:"socket", target:"kisia-fix-b:9101"}` 뒤 HELO → ARM → READ 를
**턴마다 하나씩** 밟았고, 세션 넷을 열었다. 첫 후보 `kisia{east-3_9e2f7b06}` 는 zone 을
지어낸 것이라 verifier 가 `verdict=false` 를 냈고(P-S8-a 와 같은 방향의 두 번째 증거),
그 뒤 실제 배너의 `zone=c41d` 로 다시 제출해 통과했다.

### 1.5 유형 C — 세션 계층 없이 통과한다. 남는 것은 S6.5 와 S7

**T-08 을 행사하지 않는 toolset 으로 돌렸다**(`config/kisia_c.yaml` — 세션 도구 없음).
유형 C 의 상태는 프로세스가 아니라 쿠키 항아리이고, 항아리는 `docker exec` 경계를 넘어
컨테이너 파일시스템에 살아남는다는 §9 의 예상이 **확인됐다.**

| run | 호출 | USD | 요청 배치 | S4(HTTP 연쇄) | S6 | S7 | 계 |
|---|---|---|---|---|---|---|---|
| `…150757Z-c1` | 10 | $0.0333 | 명령 3개, 요청 1개씩 | **●** | F(S6.5) | F | 4/6 |
| `…150923Z-c2` | 4 | $0.0164 | **명령 1개에 요청 3개** | **F**(S4.3) | F(S6.5) | F | 3/6 |
| `…151221Z-c3` | 4 | $0.0170 | **명령 1개에 요청 3개** | **F**(S4.3) | F(S6.5) | F | 3/6 |
| `…151300Z-c5` | 10 | $0.0330 | 명령 3개, 요청 1개씩 | **●** | F(S6.5) | F | 4/6 |
| **집합 (넷 전부)** | 28 | $0.0997 | | **●** | **F** | **F** | **4/6** |
| `…150951Z-c4neg` **개입** | 14 | $0.0482 | C-4 (§1.6-1) | 의도적 F | — | F | — |

**항아리 연쇄가 관측된 예 (`c1`).** 세 요청이 각각 다른 `run_command` 였다.

```
seq 13  POST /login  jar=/tmp/vault.cookies  before=absent            after=sha256:089faa8c…
seq 26  POST /arm    jar=/tmp/vault.cookies  before=sha256:089faa8c…  after=sha256:089faa8c…
seq 44  GET  /vault  jar=/tmp/vault.cookies  before=sha256:089faa8c…  after=sha256:089faa8c…
```

**FAIL 마다 근거 이벤트 seq.**

| 스트림 | 술어 | 판정 | 근거 seq | 검사기가 적은 이유 |
|---|---|---|---|---|
| `c1`·`c5` | S6.5 | 증거 없음 | — | 항아리를 버린 사례가 이 스트림에 없다(그 사례는 `c4neg` 에 있고 §1.6-1 이 그 결과를 적는다) |
| `c1`·`c5` | S7.1 | 거짓 | `[55]` | `derived_from = null` |
| `c2` | S4.3 | 거짓 | `[13, 15]` | **연쇄 True / 초기값과 다름 False** — 세 요청의 `jar_digest` 가 전부 `null` 이라 서로 같지만 초기값과도 같다 |
| `c2` | S7.1 | 거짓 | `[26]` | `derived_from = null` |
| `c3` | S4.3 | 거짓 | `[13, 15]` | `c2` 와 같다 |
| `c3` | S7.1 | 거짓 | `[31]` | `derived_from = null` |

네 스트림 모두 S1.2 를 거짓으로 낸다(`seq=[2]`, `files[]` 가 비었다). **판정에 들어가지
않는다** — 유형 C 는 `/input` 에 파일을 두지 않고 하중표의 S1 칸이 비어 있어 S1 이 `N/A` 다
(`FIXTURES.md` c-web `inputs: []`, `inputs_note`).

**4 run 중 2 run 에서 연쇄를 관측할 수 없었다 — 그리고 그것이 T 에 대한 관측이다.**
`c2`·`c3` 는 `curl … && curl … && curl …` 로 세 요청을 **하나의 `bash -c`** 안에서 끝냈다.
T 에는 HTTP 도구가 없고 모든 것이 불투명한 셸 명령이므로, 어댑터가 항아리를 해시할 수 있는
경계는 **명령 경계뿐**이다. 중간 항아리 상태는 존재하지 않으므로 지어낼 수 없다
(`jar_observation_granularity: "command"`, `requests_in_this_command: 3`).
`c3` 는 거기에 더해 항아리 경로가 `$jar`(셸 변수)라 경로 자체가 정적으로 읽히지 않았다.
**어댑터의 게으름이 아니라 도구 계층의 성질이다** — 세션 계층이 있었다면 요청마다 경계가
생겼을 것이고, 그것이 S4 가 "상태 있는 HTTP"를 세 실행 형태 중 하나로 세운 이유다.

집합 판정에서 S4 가 PASS 인 것은 검사기가 S4.3 을 **집합 안의 어느 스트림 하나가 만족시키면
만족**하는 술어로 다루기 때문이다(`CHECKER.md` §1.2). 그 처리를 틀렸다고 보지 않지만,
**4 중 2 에서만 관측됐다는 사실이 칸에 나타나지 않으므로 여기 적는다.**

**프로브별 결과**

| id | 결과 | 근거 |
|---|---|---|
| **C-1** 로그인→상태→flag | **통과** | `c1`·`c5`. 세 요청의 항아리 연쇄가 이어지고 `/vault` 가 part 를 준다 |
| **C-2** `target_id` 확인 | **통과** | 5 run 의 모든 `http.exchanged` 가 `target_id=kisia-fix-c`, `declared_target=true`. 선언 대상 밖 요청 **0건** |
| **C-3** 미선언 host:port | **통과** | **컨테이너 안에서** 양방향. `kisia-fix-c:8080 → CONNECTED`, `1.1.1.1:80 → REFUSED`, `93.184.216.34:443 → REFUSED`. `scope.refused{action:"connect:…", attempted_from:"container"}` 2건. 세션 C 가 arm 없이 확인해 둔 조건이 arm 위에서 재현됐다(`CHECKER.md` §6) |
| **C-4** 쿠키 버리기 (음성) | **개입 수행, 그러나 attempt 는 실패하지 않았다** | §1.6-1 |
| **C-5** 동시 요청 2개 | **시도하지 않음** | 판정에 넣지 않는 항목(§5). **시도하지 않은 이유는 소스에서 확정된다**: `openai_backend._call_model` 이 `"parallel_tool_calls": False` 를 고정으로 보낸다(`openai_backend.py:43`). 도구 호출은 언제나 한 번에 하나이므로 **도구 계층에서 동시 요청을 표현할 방법이 없고**, 가능한 것은 한 명령 안의 셸 동시성뿐이다. 그것은 T 의 동시성이 아니라 bash 의 동시성이다 |

### 1.6 계약 관측 둘 — 고치지 않고 보고한다

계약은 얼었다(r1 창은 세션 D 가 열리며 닫혔다). 아래 둘은 **arm 결과를 본 뒤**에 드러난
것이므로 고치면 §9.6-1 로 T 의 결과가 무효다. 세션 D 가 S7/S8 에 대해 한 것과 같이
관측으로만 남긴다.

**1. P-S6-a(C-4)의 "attempt 가 실패해야 한다"는 재시도하는 에이전트에게 이전되지 않는다.**

하니스가 두 번째 HTTP 명령 뒤에 항아리를 지웠다(`probe.observed{probe:"C-4"}` — 의도적
개입이므로 스트림에 남긴다, §9.6-5). 결과:

```
seq 13  POST /login   before=absent            after=sha256:0818f395…
seq 26  POST /arm     before=sha256:0818f395…  after=sha256:0818f395…
        [하니스 개입] rm -f /tmp/vault.cookies
seq 45  GET  /vault   before=absent                       <- 연쇄가 정확히 여기서 끊겼다
seq 61  run_command   jar=$(mktemp); login → arm → vault  <- 처음부터 다시 밟았다
seq 70  submit_flag   kisia{7a2e_d0416b93}                outcome=solved
```

**fixture 결함 주장이 아니다.** `FIXTURES.md` §5.3 이 막았다고 한 우회로("쿠키를 잃은 뒤
그냥 재로그인")는 그대로 막혀 있다 — 에이전트는 재로그인만으로는 403 을 받고, `/arm` 까지
다시 해야 했다. 세션 B 의 음성 프로브와 세션 C 의 재현을 뒤집는 관측이 아니라, **그 둘이
덮지 않는 경우**(처음부터 다시 시도할 수 있는 에이전트)의 기록이다. 골든 드라이버는 한 번
실패하면 끝나므로 그 경우가 나타날 수 없었다.

술어 문면은 "성공하면 그 챌린지가 상태를 시험하지 않고 있다는 뜻이므로 챌린지를 고친다"고
한다. **그 추론은 여기서 성립하지 않는다** — 챌린지는 상태를 시험했고(연쇄가 끊겼고 재-ARM
없이는 403), 다만 상태 유실이 **회복 불가능**하지 않았을 뿐이다. 두 성질은 다르고, 골든
드라이버 위에서만 같아 보인다. **fixture 를 고치지 않았고, 고칠 근거도 없다.**
그 결과 S6.5 는 유형 C 의 어느 스트림에서도 만족되지 않아 S6 이 `FAIL[no-evidence]` 다.

**2. S6.2 는 스트림에 세션이 하나도 없으면 공허참이고, 세션이 하나라도 있으면 증거 없음이 된다.**

같은 arm 행동(`b2`·`b3` 와 `b1`·`b4` 는 모델 행동이 같다)인데 하니스 프로브가 세션을
스트림에 넣는 순간 S6.2 가 `공허참(만족)` → `증거 없음(FAIL)` 으로 바뀐다. 그래서
`b2`=6/7, `b1`=4/7 이다. **이것은 술어의 성질이지 arm 의 성질이 아니다.**
집합 판정이 넷을 다 넣어 FAIL 로 접는 것이 더 정확한 답이고(세션이 있었는데 턴을
가로지르지 않았다), 그래서 §1 의 표는 집합 값을 싣는다. 다만 스트림 하나만 보고
"T 는 S6 을 통과한다"고 읽을 수 있는 자리가 있다는 것을 적어 둔다.

---

## 2. 보류 패치와 그것이 드러낸 것 — **통제 조건이 표현 불가능했다**

`REPRO_MATRIX.md` §2.1 이 세션 D 에 넘긴 보류 패치를 첫 작업으로 적용했다(T-04, §3.1).
적용 뒤 **코드를 읽어서가 아니라 나가는 HTTP 요청 본문을 가로채서** 확인했다.

```
docs/spike/arms/T/adapter/patches/observe_T04.py   (헤더는 읽지 않는다 — 키가 어디에도 찍히지 않게)
```

**1차 관측 — 파라미터는 실렸으나 API 가 거부했다.**

```
model                 'gpt-5.6-terra'
reasoning_effort      'medium'          <- 실렸다
max_completion_tokens 4096              <- max_tokens 가 아니다
max_tokens/temperature/top_p            <- 전부 absent
응답: 400 "Function tools with reasoning_effort are not supported for gpt-5.6-terra
          in /v1/chat/completions. To use function tools, use /v1/responses or set
          reasoning_effort to 'none'."
```

**추측하지 않고 여섯 칸을 실측했다** (`patches/probe_effort_matrix.py`):

| 조합 | 결과 |
|---|---|
| chat/completions + tools + `effort=medium` | **FAIL** |
| chat/completions + tools + `effort=none` | OK |
| chat/completions + tools + **effort 부재** | **FAIL** |
| chat/completions + tools 없음 + `effort=medium` | OK |
| `/v1/responses` + tools + `effort=medium` | OK |
| `/v1/responses` + tools + `effort=none` | OK |

세 가지가 여기서 확정된다.

1. **T 는 `reasoning effort medium` 을 표현할 수 없다** — 도구 계층이 곧 function calling 이고
   backend 가 `/v1/chat/completions` 를 쓰기 때문이다(`openai_backend.py:38`).
   `FOUNDATION_DECISION.md` §9.1 과 `EVAL_CONTRACT.md` 가 통제 조건으로 못박은 값이다.
2. **effort 부재도 실패한다.** 즉 T 는 T-04 이전에 이 모델에서 **도구를 쓰는 호출을 단 한 번도
   할 수 없었다.** 세션 A 의 P3 실패(`max_tokens`)는 두 관문 중 첫째였을 뿐이다.
   T-04 는 선택이 아니라 **필수**였다는 세션 A 의 판단이 실측으로 확인됐다.
3. **이것은 T 의 문제가 아니라 wire API 의 문제다.** E 도 chat/completions 를 쓰므로 같은 벽에
   걸리고, X(Codex)는 `wire_api=responses` 라 medium 이 가능하다(`REPRO_MATRIX.md` §2.3).
   arm 마다 다른 effort 를 쓰면 §9.6-2 위반이다.

### 2.1 운영자 결정 — 전 arm `reasoning effort none`

**운영자 결정 2026-08-07 (세션 D). 전문은 `docs/adr/ADR-0001-foundation-spike-reasoning-effort.md`.**

**`foundation-spike` 프로파일에 한해** 모델 구동 arm 전부(T·E·X)를 `reasoning_effort=none`
으로 통일한다. **영구 변경이 아니다** — `EVAL_CONTRACT.md` 는 고치지 않았고 제품·성능 평가
프로파일은 **`Responses API + medium` 을 유지한다.**

| | `foundation-spike` (지금) | `target-performance` (후속 gate) |
|---|---|---|
| endpoint | T·E `/v1/chat/completions`, X `/v1/responses` | 전부 `/v1/responses` |
| reasoning effort | `none` (requested = effective) | `medium` (requested = effective) |
| fixture | trivial-by-design 자작 3종 | nontrivial, clean/private |
| 판정 가능 | 도구 호출·상태 전파·telemetry·통합 비용·실행 안정성 | solve accuracy, time-to-flag, cost/solve, 장기 상태 유지 |
| 판정 **불가** | CTF 풀이 능력, 모델 선택, 최종 우승자 | — |

**지금 Responses 로 이식하지 않는 이유.** T·E 만 옮기면 tool 형식·`call_id` 연결·스트리밍
이벤트 모델·상태 유지·reasoning item 보존·캐싱·오류 경로가 동시에 바뀐다. URL 교체가 아니라
새 transport 구현이다. 더 중요한 것은 **Responses 가 중립적 전송 계층이 아니라는 점**이다 —
같은 프롬프트·설정에서도 결과와 캐시 효율이 달라지므로 한 arm 만 옮기면 **하니스 효과와 API
효과를 분리할 수 없다.** 실무적으로도 T 의 남은 구조 패치 예산 1개를 여기서 소진시킨다.

**모델을 다시 고르지 않는 이유.** 관측된 것은 모델 능력 문제가 아니라 endpoint × parameter
조합의 capability 문제다. 모델을 바꾸면 모델 능력이라는 더 큰 교란 변수가 추가된다.

**결과를 부르는 이름에 제약이 붙는다.** endpoint 가 arm 마다 다르므로 이 스파이크의 산출물은
**"원형에 가까운 전체 OSS stack 비교(as-integrated system comparison)"** 다.
**"순수한 orchestration 품질 비교"나 "동일 transport 에서의 harness-only 비교"라고 부르면
안 된다.** 최종 후보끼리는 공통 Responses 어댑터 아래에서 한 번 더 비교한다.

**무결성 규칙 — 조용한 강등 금지.** `requested_reasoning_effort != effective_reasoning_effort`
이면 **run 을 실패 처리한다**(`adapt.py` 의 fail-fast). effective 는 선언이 아니라 관측이다 —
`usage.completion_tokens_details.reasoning_tokens` 가 0이면 추론이 일어나지 않은 것이고, 이
값이 실제로 보고됨을 확인했다. 모든 run 이 profile / provider / model_alias / **model_snapshot** /
endpoint / requested·effective effort / tool_protocol / state_mode / store / streaming /
capability_probe_id 를 통제 블록에 싣는다. capability probe 는 메모가 아니라 artifact 다
(`capability-probes/openai-gpt-5.6-terra-chat-tools-effort-2026-08-07.json`).

**후속 gate.** foundation 채택 전에 (1) shortlist 후보에 Responses transport 구현·검증,
(2) 결선 후보 전부를 nontrivial clean fixture 에서 **medium 으로** 재평가, (3) solve rate·
latency·cost·tool reliability·variance 비교. **이 관문 전의 foundation 결정은 provisional 이다.**

- **§9.6-1 에 걸리지 않는 이유:** 특정 arm 을 살리려는 개정이 아니다. 이 모델에서
  **function tools 와 medium 의 조합이 존재하지 않는다**는 API 제약이고, 그 제약은 arm 을
  가리지 않는다. 결정 시점은 T 의 seam 판정을 보기 전이다(위 여섯 칸 관측 직후).
- **§9.6-2 에 걸리지 않는 이유:** 전 arm 에 같은 값을 쓴다. X 의 기본값이 이미 `none` 이라
  (`REPRO_MATRIX.md` §2.3) 추가 플래그도 필요 없다.
- **`EVAL_CONTRACT.md` 를 고치지 않는다.** 그 문서가 요구하는 것은 "model (id and reasoning
  effort)" 를 **비교 대상 run 사이에서 동일하게 유지하고 결과와 함께 기재하는 것**이다.
  값이 `none` 이어도 그 요구는 그대로 만족된다.
- **대가, 명시:** 이 스파이크는 **어떤 arm 도 medium 에서 재지 않았다.** `§12.2-7`(알려진
  성능 공백)에 기재한다. 배관 판정에 reasoning 이 필요하지 않고 fixture 가
  `trivial-by-design` 이므로 이 스파이크의 목적에 대한 손실은 작지만, **성능 단계로
  넘어갈 때 이 값은 다시 정해야 한다.**

**적용 뒤 재관측 — PASS.**

```
reasoning_effort 'none' / max_completion_tokens 4096 / max_tokens·temperature·top_p 부재
tools 1 schema  ->  content='ok'  error=None
```

**T 가 자기 backend 와 자기 도구 계층으로 `gpt-5.6-terra` 호출에 성공한 첫 관측이다.**

---

## 3. 패치 — 구조 3 / 사소 3 (예산 3 중 **3 사용, 0 남음**)

diff 는 `docs/spike/arms/T/patches/*.diff`. 적용 스크립트는 `adapter/patches/apply_*.py` 이고
전부 멱등이며 앵커가 어긋나면 조용히 실패하지 않고 죽는다.

| # | 종류 | 무엇을 | 왜 |
|---|---|---|---|
| T-04 | **사소** | `openai_backend._call_model`: `max_tokens`→`max_completion_tokens`, `temperature`/`top_p` 조건화, `reasoning_effort` 신설(+`config.py` 필드) | §3.1 |
| T-05 | **구조** | 정답 주입 제거와 성공 판정의 외부화 (`tools/misc.py`, `agent.py`) | §3.2 |
| T-06 | **구조** | 격리 모델 — mounts 와 read-only rootfs (`environment.py`) | §3.3 |
| T-07 | **사소** | `models.yaml` 에 `gpt-5.6-luna` 항목 추가 (A-5/P-S3-a 용) | §3.4 |
| **T-08** | **구조** | 지속 세션 계층 — `tools/session.py` 신설과 `tools/__init__.py` 의 `ALLTOOLS` 등록 | §3.5 |

세션 A 의 T-01·T-02·T-03 은 그대로 유효하다(`REPRO_MATRIX.md` §2.1).

**예산은 여기서 끝났다.** 구조 3/3. 유형 C 는 네 번째를 요구하지 않았다(§1.5) — 요구했다면
§9.3 대로 그 유형은 FAIL 이고 스파이크를 멈췄을 것이다.

**구조 패치 작성에 든 시간 (§9.4). 추정이 아니라 실측이다.**

| 구간 | 시각(UTC) | 소요 |
|---|---|---|
| T-05 착수 (첫 줄) | 2026-08-07T13:36Z | |
| T-06 작성 완료 | 2026-08-07T13:41Z | |
| 무과금 스모크로 둘 다 관측 확인 (mounts·rootfs·프로브·verifier 양방향) | 2026-08-07T13:52Z | **약 16분** |
| **T-08 착수 (첫 줄)** | 2026-08-07T14:39:57Z | |
| T-08 적용, `ALLTOOLS` 17종 확인 | 2026-08-07T14:47:34Z | |
| **§4.1·§4.2 프로브 8/8 통과** (B-4 측정 설계 결함 1건 진단·수정 포함) | 2026-08-07T~14:52Z | **약 12분** |
| **검사기가 세션 계층의 telemetry 를 통과시킴** (S4.2·S6 PASS, `bs1` 스트림) | 2026-08-07T15:05:22Z | **약 25분** |

**두 값의 뜻이 다르다.** 앞의 12분은 "후보 안에 들어간 구조 패치가 §4.1·§4.2 의 관측을
만족한다"까지이고, 뒤의 25분은 "그 사실이 계약의 봉투로 나와 검사기가 통과시킨다"까지다.
G 가 §7 에서 9분 16초와 약 13분 50초를 나눠 적은 것과 같은 구분이다.

- **12분에 포함된 것:** `tools/session.py`(§4 의 6개 연산 + §4.1 넷 + §4.2), 적용 스크립트,
  `run_b_probes.py`(B-2~B-8 + §4.2 + 외부 `/proc` 검증), 프로브 실행 2회와 그 사이의
  진단·수정 1건.
- **25분에 추가로 포함된 것:** `adapt.py` 의 `session.*` 매핑과 `live_session_ids` 추적,
  `run_arm.py` 배선, config 2종, 모델 run 4회.
- **포함되지 않은 것:** 유형 C 계측(`http.exchanged`), C-3 프로브, 문서 작성 시간,
  세션 D 가 이미 만들어 둔 어댑터(변환기·shim·러너·verifyd).

> **§10.2 의 우발 조항은 이 값을 쓰지 않는다.** 그 조항은 "**G 의 참조 구현 작성 시간**이
> **E 의 구조 패치 작성 시간**보다 작으면 3 이 2 보다 앞선다"이고, 비교 대상에 T 가 없다
> (선택지 1 은 이 예외의 대상이 아니라고 §10.2 가 명시한다). 세션 D-2 의 부팅 지시는 이
> 값이 §10.2 에 들어간다고 적었으나 **문면과 어긋난다.** §9.4 가 arm 마다 요구하는 기록
> 항목이므로 남기고, 참고로 같은 범위(§4 계약의 세션 런타임)에서 G 는 약 14분이었다.

### 3.1 T-04 — **사소**로 판정한다 (세션 A 의 의견에 동의)

`REPRO_MATRIX.md` §2.1 은 "적용 시 분류는 **사소**로 본다"고 남겼고 판정은 세션 D 의 몫이었다.
**동의한다.** 근거:

- §9.3 의 구조 패치 정의는 **core loop / 상태 모델 / 도구 인터페이스 / 격리 모델**을 바꾸는
  변경이다. 이 패치는 넷 중 어느 것도 건드리지 않는다 — provider 어댑터(S3) 안에서
  요청 파라미터의 **형태**만 바꾼다. 제어 흐름, 대화 상태, 도구 스키마, 컨테이너 인자
  전부 그대로다.
- S3 의 FAIL 조건은 "provider 이름이 후보의 제어 흐름에 박혀 있어 P-S3-a 에 소스 수정이
  필요한 경우"다. 이 패치는 그 상황을 **만드는 것이 아니라 푸는 쪽**이다 — 적용 뒤
  P-S3-a 가 소스 수정 없이 통과했다(§5).
- `config.py` 에 `reasoning_effort` 필드를 더한 것은 기본값 `None` 의 선택적 파라미터
  배관이고, 없으면 `get_param` 이 `ValueError` 로 죽는다. T-03(모델 레지스트리 항목 추가)과
  같은 자리다.

애매한 자리가 아니라고 본다. 애매했다면 "구조로 세고 이유를 적는다"를 따랐을 것이다.

### 3.2 T-05 — **구조**. 예산 1/3

**REPRO_MATRIX 가 지목한 곳은 하나였지만 같은 결함이 두 곳에 있다.** 세션 D 지시는
`misc.py` 만 언급했다. `misc.py` 만 껐다면 **더 넓은 경로가 살아남았을 것이다.**

```
(1) tools/misc.py:16   self.actual_flag = environment.challenge.flag
    tools/misc.py:21   flag != self.actual_flag -> error / else environment.solved = True

(2) agent.py:33-40     BaseAgent.check_flag_in_response
    정답의 가변부를 **모든 메시지**(user/assistant/observation)에 부분문자열 검색해
    맞으면 environment.solved = True.
    도구를 부르지 않아도, 모델이 그 문자열을 **말하기만 해도** 성공이 된다.
```

둘 다 §0.1-3(후보의 자기 보고는 증거가 아니다)과 S8(정답이 solver 의 도달 범위 밖)에
정면으로 걸린다. (2)는 `add_user_message`·`add_assistant_message`·`add_observation_message`
셋 모두에서 불린다(agent.py:49, 54, 56, 61).

**끄기만 하지 않고 외부 verifier 로 옮긴 이유.** `environment.solved` 는 세 루프 전부의 종료
조건이다(agent.py:209, 519, 542). 그냥 끄면 후보는 정답을 찾고도 멈추지 못하고 max_cost 까지
돈다. 계약이 요구하는 형태가 이미 답이다 — "후보가 받는 것은 판정뿐이다. 정답도, 정답의
해시도 받지 않는다."

**subprocess 가 아니라 unix 소켓 뒤의 데몬인 이유.** `submit_flag` 가 verifier 를 subprocess 로
띄우면 두 가지가 동시에 깨진다: verifier 가 후보의 **프로세스 트리 안**에서 돌고(S8 첫 술어
위반), 정답 파일 경로가 solver 의 환경에 들어가 `cat` 한 번으로 정답에 도달한다.
데몬으로 두면 solver 가 갖는 것은 소켓 경로 하나이고 돌아오는 것은 `verdict` 하나다.

**분류 근거 — 구조.** §9.3 의 넷 중 **상태 모델**(`environment.solved` 의 유일한 설정 지점,
즉 성공 판정)과 **도구 인터페이스**(`submit_flag` 의 판정 주체)를 바꾼다. 파일 둘을
만지지만 목적이 하나(정답을 프로세스에서 빼고 판정을 밖으로)라 **하나로 센다.**
애매하다고 보지 않지만, 애매했다면 구조 쪽이므로 결론은 같다.

**관측 (무과금, `patches/smoke_T05_T06.py`)**

```
tool.actual_flag = None                 <- 정답이 프로세스 안에 없다
wrong -> {'error': 'Flag is wrong!'}    solved=False
right -> {'success': True}              solved=True
verifyd: verdict=False / verdict=True   id=kisia-fix-verifier@host(verifyd.unix-socket)
```

### 3.3 T-06 — **구조**. 예산 2/3

**관측** (`environment.py:57-65`): T 는 worker 를
`docker run -d --rm --network <net> --label ... <image>` 로 띄운다. **볼륨 마운트가 하나도
없고, 루트fs 가 쓰기 가능하며, `/input` 도 `/work` 도 존재하지 않는다.** 입력물은
`docker cp` 로 컨테이너 홈에 복사된다(`environment.py:46-49`).

S2 는 "`/input` 읽기 전용, `/work`·`/artifacts` 쓰기, 그 밖 거부"를 요구하고 fixture
매니페스트의 `workspace` 블록이 그 형태를 그대로 선언한다. **어댑터로는 만들 수 없다** —
이벤트를 내지 못하는 문제가 아니라 격리가 실제로 없는 문제이므로, 밖에서 이벤트를 지어내면
§0.1-3 을 스스로 어긴다. 따라서 **후보를 고치거나 S2 를 FAIL 로 적는 둘 중 하나**이고,
§9.3 이 `PASS(patch n)` 을 두는 이유가 이 자리다.

바꾼 것은 `start_docker` 의 `docker run` 인자 한 곳뿐이다. 두 가지를 의도적으로 하지 않았다:

- **프롬프트를 고치지 않았다.** 후보의 프롬프트가 "These files are present in the folder
  `{environment.container_home}/ctf_files`" 라고 말한다. 프롬프트를 고치면 그것은 에이전트
  지시의 변경, 즉 성능 튜닝이 되어 §9.6-1 에 가까워진다. 대신 fixture 의 `input` 을
  `/input` **과** `/home/ctfplayer/ctf_files` 양쪽에 `:ro` 로 걸어 후보의 규약과 계약을
  동시에 만족시켰다.
- **`docker cp` 경로를 지우지 않았다.** ro 마운트 위로의 복사는 실패하지만
  `copy_into_container` 가 `check=True` 없이 호출되므로 조용히 무시된다. 그래야 diff 가
  격리 모델 하나만 바꾼 것으로 남는다.

**분류 근거 — 구조.** §9.3 의 넷 중 **격리 모델**을 정면으로 바꾼다. 논쟁의 여지가 없다.

**관측 (무과금)**

```
ReadonlyRootfs = True            NetworkMode = kisia-fixnet
/input                    rw=False   <- fixtures/a-static/input
/home/ctfplayer/ctf_files rw=False   <- 같은 디렉터리
/work                     rw=True    <- runs/T/<attempt>/work
/artifacts                rw=True
P-S2-a /etc/kisia-probe-a   rc=1 Read-only file system   host_check_exists=False
P-S2-b /input/kisia-probe-b rc=1 Read-only file system   host_check_exists=False
```

**부수 결함 1건과 그 수정 (패치 아님).** `/work` 는 호스트에서 `ctf-spike-user`(uid 1002) 소유인데
worker 는 `ctfplayer`(uid 1000)로 돈다. 첫 스모크에서 `/work` 쓰기가 `Permission denied` 로
막혔다 — 마운트는 됐지만 쓸 수 없어 S2 가 성립하지 않는다. `ctf-spike-user` 에 sudo 가 없어 chown 이
불가능하므로 러너가 run 디렉터리를 `0777` 로 연다. **호스트 경로의 모드이고 후보 코드가
아니므로 패치가 아니다.**

### 3.4 T-07 — **사소**

A-5/P-S3-a 는 모델 id 만 luna 로 바꿔 재실행하는 프로브다. `models.yaml` 에 항목이 없으면
`Backend.__init__` 이 `KeyError` 다. 세션 A 의 T-03(terra 항목 추가)과 같은 성격이고, 그
파일 머리말이 "Edit this file to add new models — no Python code changes needed" 라고 스스로
규정한다. **Python 소스는 한 줄도 바뀌지 않았으므로 P-S3-a 의 "후보 소스를 고치지 않고"가
만족된다.**

### 3.5 T-08 — **구조**. 예산 3/3 (마지막)

**관측(후보 소스).** `RunCommandTool.call`(`tools/run_command.py:33-42`)은 호출마다
`subprocess.Popen(['docker','exec', …,'bash','-c',command])` 를 새로 띄우고 `communicate`
로 끝낸다. pty 도, 소켓도, 세션 핸들도 없다. `ALLTOOLS`(`tools/__init__.py:11-13`) 11종
어디에도 세션 도구가 없고, `CTFEnvironment.get_toolset` 은 `self.tools[name]` 을 뽑을
뿐이므로 **config 로는 없는 도구를 고를 수 없다.**

**(a) 후보 안 / (b) 어댑터 — 어느 쪽인가.** (a)다. 근거는 셋이고, 이 판단이 세션 D 가 §4 에서
그은 선보다 넓지 않다는 것을 먼저 적는다.

1. **§9.3 의 구조 패치 정의 넷 중 "도구 인터페이스"를 정면으로 바꾼다.** §2 S4 가 이 자리를
   **미리** 못박았다 — "세 형태 중 지속 세션이 '도구를 하나 더 붙인 것'이 아니라 **도구
   계층의 형태를 바꾸는 것**이라는 게 이 seam 의 요점이다. 후보가 세션을 표현하기 위해
   loop 나 상태 모델을 고쳐야 하면 그것은 구조 패치이고, 3개 예산에 들어간다."
2. **shim monkeypatch 로 밖에서 꽂는 것은 기술적으로 가능하지만 그렇게 세지 않는다.**
   §0.1-1 의 선은 코드가 어느 파일에 있느냐가 아니라 **무엇이 바뀌느냐**이고, 세션 D 가
   §4 에서 그은 선은 "투명한 관측 래퍼는 어댑터, 행동을 바꾸면 패치"다. 도구를 더하는 것은
   모델이 할 수 있는 일을 바꾼다 — 관측이 아니라 행동이다. 밖에 두고 사소로 세면 §9.6-3 이다.
3. 애매하다고 보지 않지만, 애매했다면 "구조로 세고 이유를 적는다"를 따랐을 것이므로
   결론은 같다.

**바꾼 것은 둘뿐이다** (diff: `patches/T-08-structural-session.diff`, 584줄).

```
nyuctf_multiagent/tools/session.py     신설 — §4 의 6개 연산, §4.1 넷, §4.2
nyuctf_multiagent/tools/__init__.py    여섯 도구 import + ALLTOOLS 등록 (+13/-1)
```

`agent.py` 의 loop 도, `conversation.py` 의 상태 모델도, `environment.py` 도 건드리지
않았다. 세션 매니저는 `environment` 에 lazy 로 붙고(컨테이너 id 는 `start_docker` 전에는
없다), 정리는 `Tool` 기반 클래스가 **이미 갖고 있던** `teardown` 훅에 얹었다
(`tools/tool.py:20-23`). 그래서 diff 가 도구 계층 하나로 남는다.

**설계에서 계약이 강제한 것 셋.**

- **전송 계층이 실제로 둘이어야 한다.** 같은 전송을 두 이름으로 부르면 §4.1-1 이 공허참이
  된다(G 가 §2 에서 같은 판단을 했다). `pty` 는 호스트 `pty.openpty()` + `docker exec -i -t`,
  `socket` 은 `docker exec -i` + **컨테이너 안의 TCP 릴레이**다.
- **소켓을 호스트에서 열지 않는다.** 호스트 egress 는 네트워크 계층에서 전혀 제한되지 않는다
  (`HOST_EXCEPTIONS.md` §10.2 의 실측). 호스트 소켓으로 세션을 만들면 solver 에게 workspace
  가 갖지 않은 네트워크 도달 범위를 주게 되어 S2 가 깨진다. 릴레이는 `os.setsid()` 로 세션
  리더가 되어 두 전송이 **같은 정리 경계(커널 세션)** 를 갖는다.
- **리더 pid 를 세션 밖에서 정한다.** 세션 안에 `echo $$` 를 흘려 넣으면 B-2 의 기록기가 그
  바이트를 먼저 받아 재는 것이 달라진다(G 의 첫 run 이 여기서 걸렸다). 프로세스 표 diff 로
  "새로 생겼고 `pid == sid` 이고 comm 이 일치하는" 것을 고른다 — comm 을 함께 보는 이유는
  우리 자신의 `/proc` 읽기용 `docker exec sh -c` 도 새 프로세스이기 때문이다.

**후보 안에서 우리 스트림에 쓰는 코드는 한 줄도 없다.** 모든 사실은 도구의 **반환값**으로
나가고 그것을 봉투로 옮기는 것은 어댑터다(§4.3). 그래야 패치가 "도구 계층 하나"로 남는다.

**진단 1건 (패치 아님, 측정 설계).** 첫 프로브 실행에서 B-4 가 `grace_used_ms=2079/2000` 으로
실패했다. 가설은 "좀비 회계가 아니라 누군가 SIGTERM 후에도 살아 있다"였고, 반증 관측으로
grace 폴링 중 세션 멤버의 상태를 매 회 찍었다:

```
members before kill: [(15,'bash','S',15), (33,'python3','S',33), (34,'python3','Z',33)]
  t= 209ms alive=[(15,'bash','S'), (34,'python3','Z')]     <- python3(33) 은 이미 죽었다
  … 1862ms 까지 bash(15) 가 그대로 살아 있다
```

원인은 `docker exec -t … bash` 가 `-i` 없이도 stdin/stderr 이 tty 라 bash 를 **대화형**으로
만들고(출력의 bracketed-paste `[?2004l` 로 확인), 대화형 bash 는 SIGTERM 을 무시한다는 것이다.
그러면 재는 것이 좀비 회계가 아니라 셸의 시그널 처리가 된다. 프로브의 리더를
`bash -c '…; sleep 600'`(비대화형)으로 바꾸자 `grace_used_ms=90` 이 됐다. **후보 코드가
아니라 프로브의 측정 설계를 고친 것이므로 패치가 아니다.** G 가 §4.1-3 에 남긴 "측정 설계
주의"와 같은 함정이었고, 그 주의가 없었다면 좀비 회계 결함으로 오독했을 것이다.

부수로 `close` 의 grace 기준점을 SIGTERM 전달 시점으로 옮겼다 — 그 전에는 우리 자신의
`/proc` 읽기 지연이 grace 에 계상돼 모든 close 가 실제보다 느려 보였다.

---

## 4. 어댑터 — 무엇이 패치가 아니고, 왜 그런가

`SEAM_CONTRACT.md` §0.1-1 의 선: **후보 코드를 고쳐 이벤트를 내게 만들면 구조 패치,
후보의 기존 출력에서 사실을 뽑으면 패치가 아니다.** 아래 넷은 전부 후보 소스를 한 글자도
바꾸지 않는다(`git diff` 에 나타나지 않는다).

| 산출물 | 무엇을 | 분류 근거 |
|---|---|---|
| `adapter/make_dataset.py` | fixture 매니페스트 → `--dataset <json>` | 후보가 스스로 노출한 플래그에 우리 fixture 를 먹인다. 로더도 데이터 모델도 고치지 않았다 (§2 S1 이 미리 그은 선의 **사소 쪽보다도 아래** — 후보 파일이 아니다) |
| `adapter/shim/kisia_shim.py` + `kisia_launch.py` | 계측 — 모델 호출 usage, **절단 이전 도구 결과 전체**, 컨테이너 id | 투명한 관측 래퍼. 인자·반환값·예외를 그대로 통과시킨다. §9.3 의 넷 중 어느 것도 바꾸지 않는다. 진입점을 다르게 호출하는 것은 세션 A 가 `--keys <(...)` 에 적용한 판단과 같은 자리(`REPRO_MATRIX.md` §3) |
| `adapter/adapt.py` | 위 사실 + 후보 로그 → §1 봉투 | docker 를 쓰지 않는 순수 변환 |
| `adapter/run_arm.py`, `verifyd.py` | 하니스 몫의 이벤트 | §4.2 |
| `shim` 의 `http` 계측 (세션 D-2) | 유형 C 의 `jar_digest_before/after` — 명령 **앞뒤로** 컨테이너 안의 항아리 파일을 `sha256sum` 한다 | §4.3 |
| `adapter/run_b_probes.py` (세션 D-2) | §4.1·§4.2 프로브를 후보의 세션 계층에 대고 돌리고, 생존자를 후보 밖에서 확인 | §4.3 |

### 4.1 계측이 필요했다는 사실 자체가 T 에 대한 관측이다

숨기면 §12.2-3(KEEP/WRAP/REWRITE 판단)이 틀린 근거 위에 서게 되므로 적는다.
**T 의 출력에는 다음 둘이 존재하지 않는다.**

1. **호출 단위 토큰·비용.** `calculate_cost`(`openai_backend.py:49-54`)가 `response.usage` 를
   읽어 비용을 계산하고 **그 자리에서 버린다.** 로그(`agent.py:451-474`)에 남는 것은
   `total_cost` 하나다. S3 는 호출 단위 회계를, 개정 A-1 은 `cache_write_tokens` 를 요구한다.
2. **절단 이전 관찰 원본.** `Conversation.append_observation`(`conversation.py:89-99`)이 도구
   결과를 **제자리에서** 25,000자로 자르고 원본을 어디에도 남기지 않는다. S5 는 절단분마다
   sha256 을 가진 artifact 를 요구한다.

**둘 다 후보를 고치지 않고 얻었다** — shim 이 `Completions.create` 와 `run_tool` 을 감싸
버려지기 전에 받아 적는다. 즉 §0.1-2 의 "어떤 방법으로도 얻을 수 없다"에는 해당하지
않으므로 FAIL 이 아니다. 그러나 **T 를 그대로 가져오면 이 둘은 따로 만들어야 한다.**

한 가지 더: `cache_write_tokens` 를 chat/completions 의 `usage` 는 보고하지 않아
pricing 파일이 실측으로 기록한 관계(`cached + cache_write + 3 == input`)로 파생했다.
**`/v1/responses` 는 `input_tokens_details.cache_write_tokens` 를 직접 준다**(§2 의 여섯 칸
관측에서 확인). wire API 를 옮기면 A-1 이 파생 없이 만족된다.

### 4.2 러너가 내는 것 — arm 이 아니라 하니스의 몫

- **`answer.sweep`** (개정 A-3). 네 표면 전부 **적중 0건**, 3 run 모두.
  `container:/input`·`container:/work` 는 bind mount 이므로 호스트 경로 검색이 같은
  바이트를 덮고, 추가로 컨테이너가 살아 있는 동안 안에서 `grep` 도 돌렸다.
- **`scope.refused`** — P-S2-a/P-S2-b 를 **컨테이너 안에서** 시도한 결과와, 호스트에서
  파일 부재를 확인한 방법(`docker diff` / bind-mount 원본 stat).
- **`workspace.destroyed`** — 잔존 프로세스·컨테이너를 후보 밖에서 확인한 값. 3 run 모두 0.
- **P-S8-a** — 일부러 틀린 후보를 verifier 에 넣어 `verdict=false` 확인. 3 run 모두.
  `SEAM_CONTRACT.md` §2 S8 이 "이걸 돌리지 않은 verifier 는 계약을 만족하지 않는다"고
  한 대로 **verifier 를 재는 프로브**이므로 하니스가 돈다.

### 4.3 세션 D-2 가 더한 어댑터 둘 — 왜 패치가 아닌가

**(1) shim 의 항아리 해시 (`_parse_http` / `_jar_digests`).** `jar_digest_before/after` 는
**실행 시점 관측**이다 — 명령이 끝난 뒤에는 항아리의 이전 상태가 남아 있지 않으므로 나중에
재구성할 수 없다. shim 은 `run_command` 의 인자에서 URL 과 `-c/--cookie-jar`·`-b/--cookie`
경로를 읽고, 명령 **앞뒤로** 그 경로를 `sha256sum` 한다. 인자도 반환값도 제어 흐름도 바꾸지
않고 컨테이너 안의 파일을 **읽기만** 한다. 후보 소스는 한 글자도 다르지 않다.

**항아리 경로를 우리가 정하지 않았다.** 부팅 지시가 물은 항목이다 — fixture 설명도 후보
프롬프트도 특정 경로를 지시하지 않는다(`web_server_description` 은 `curl http://host:port`
예시뿐이다). 지시를 만들어 넣으려면 그 지시가 **프롬프트나 fixture 에서** 와야 하는데 둘 다
고칠 수 없으므로, 에이전트가 실제로 쓴 인자를 읽는 쪽을 골랐다. 그 대가가 §1.5 의 관측이다 —
에이전트가 한 명령 안에서 세 요청을 하거나 경로를 셸 변수로 쓰면 관측할 것이 사라진다.
**그 경우 지어내지 않고 `null` 로 두고 왜 없는지를 필드로 적는다**(`status_source`,
`jar_observation_granularity`).

**(2) `run_b_probes.py`.** 후보의 `nyuctf_multiagent.tools.session` 을 import 해 매니저를
직접 몰고, 생존자·좀비는 **하니스 자신의 `/proc` 읽기 코드**로 따로 확인한다(§0.1-3 —
후보의 자기 보고는 증거가 아니다). 후보 소스를 고치지 않고 후보가 노출한 인터페이스를
다르게 호출하는 것이므로, 세션 A 가 `--keys <(…)` 에 적용한 판단과 같은 자리다
(`REPRO_MATRIX.md` §3). **재는 대상은 우리 코드가 아니라 T-08 이후의 후보 세션 계층이다.**

### 4.4 검사기 밖에서 한 번 더 대조 (§6.1 이 남긴 경고)

§6.1 은 "어댑터가 계산하는 값은 검사기 밖에서 한 번 더 대조하라"고 했다. 셋을 대조했다.

| 값 | 대조 방법 | 결과 |
|---|---|---|
| `usd` | 스트림의 토큰을 pricing 요율로 **다시** 계산 + 후보 자신의 `total_cost` 와 대조 | `b1` 스트림 $0.0291 = 재계산 $0.0291. 후보의 $0.0425 는 후보 식(`in_price×prompt + out_price×completion`, 캐시 구분 없음)의 값과 **소수점까지 일치**한다 — 차이는 전부 캐시 할인이고 우리 값이 맞다. `cache_write_source` 는 모든 요청에서 `"reported"`(§6.1 의 수정이 유지된다) |
| `survivors` | 후보의 반환값 vs 하니스의 `/proc` 읽기 | `b1`·`b4` 의 close **28건 전부 일치**, 불일치 0 |
| 항아리 digest | 컨테이너 안의 `sha256sum`(우리 코드가 아닌 독립 도구) | `c1`·`c5` 에서 연쇄가 성립. `c2`·`c3` 은 관측 불가이고 그 사실을 필드로 남겼다 |

**후보의 비용 보고가 캐시를 무시해 약 46% 과대**라는 것은 T 에 대한 관측이다 —
`REPRO_MATRIX.md` §5 에 적는다.

---

## 5. run 기록 (§9.4)

**공통 통제 조건** — 네 run 전부 동일(모델 id 는 A-5 만 다르다):

```
arm T / 유형 A / challenge kisia-fix-a-static
challenge_manifest_sha256  5727c7ec4068dd7d87c65c0194707ce4aebe1d21852abdabd19039c977160723
model                      gpt-5.6-terra   (A-5 만 gpt-5.6-luna)
reasoning_effort           none            (§2.1 운영자 결정)
attempt_timeout_s 2400 / tool_timeout_s 300 / session_timeout_s null (T 에 세션 개념이 없다)
token_budget null / usd_budget 1.0   (T 의 유일한 예산 장치는 max_cost)
max_rounds  planner 12 / executor 20   (§9.7 "유형 A 를 최소로")
image_digest  ctfenv:multiagent sha256:7ffb5ff2…
network       kisia-fixnet (--internal), 선언 대상 없음
구조 패치     T-05, T-06 (2개)
```

| run | 모델 | 호출 | USD | exit | verifier | 검사기 | 지위 |
|---|---|---|---|---|---|---|---|
| `…135632Z` | terra | 7 | $0.0697 | solved | true, false | — | **폐기** — 어댑터 결함 5건 (§6) |
| `…140133Z-r1` | terra | 6 | $0.0191 | solved | true, false | 6/8 | 보조 증거 (토큰 회계 결함, §6.1) |
| `…140427Z-r2b` | terra | 8 | $0.0434 | solved | true, false | 6/8 | 보조 증거 (같음) |
| `…140508Z-luna2` | luna | 5 | $0.0019 | solved | true, false | 6/8 | **A-5/P-S3-a** (같음) |
| **`…142122Z-p1`** | terra | 6 | $0.1079 | solved | true, false | 6/8 | **기록 판정** |
| **`…142159Z-p2`** | terra | 6 | $0.0559 | solved | true, false | 6/8 | **기록 판정** |
| | | **38** | **$0.2980** | | | **집합 7/8** | |

**유형 B·C (세션 D-2).** 통제 조건은 위와 같고 셋만 다르다: 챌린지, config
(`kisia_b.yaml` / `kisia_c.yaml`), 구조 패치 **3개**(T-05·T-06·T-08).
`session_timeout_s` 는 여전히 `null` 이다 — T-08 은 세션 **수명**의 상한을 두지 않고
동시 세션 **수**의 상한(4)만 둔다. 계약이 요구하는 것은 후자이지만, 전자가 없다는 사실을
기록한다.

| run | 유형 | 호출 | USD | exit | verifier | 검사기 | 지위 |
|---|---|---|---|---|---|---|---|
| `…145826Z-b1` | B | 8 | $0.0291 | solved | true, false | 4/7 | 기록 판정 집합 · 프로브 8/8 |
| `…150110Z-b2` | B | 6 | $0.0278 | solved | true, false | 6/7 | 기록 판정 집합 |
| `…150201Z-b3` | B | 7 | $0.0243 | solved | true, false | 5/7 | 기록 판정 집합 |
| `…150613Z-b4` | B | 11 | $0.0392 | solved | true, false | 4/7 | 기록 판정 집합 · 프로브 8/8 |
| `…150341Z-bs1` | B | 37 | $0.0641 | solved | **false**, true, false | 5/7 | **보조 증거** (§1.4.3) |
| `…150757Z-c1` | C | 10 | $0.0333 | solved | true, false | 4/6 | 기록 판정 집합 · C-3 |
| `…150923Z-c2` | C | 4 | $0.0164 | solved | true, false | 3/6 | 기록 판정 집합 |
| `…151221Z-c3` | C | 4 | $0.0170 | solved | true, false | 3/6 | 기록 판정 집합 |
| `…151300Z-c5` | C | 10 | $0.0330 | solved | true, false | 4/6 | 기록 판정 집합 |
| `…150951Z-c4neg` | C | 14 | $0.0482 | solved | true, false | — | **C-4 개입 run** (§1.6-1) |
| | | **111** | **$0.3325** | | | **B 집합 3/7 · C 집합 4/6** | |

**폐기한 run 0건.** 세션 D-2 의 10 run 은 전부 모델을 호출했고 전부 보존되어 있다.
0 호출로 죽은 run 도 없었다 — 세션 D 가 `--config` 절대 경로 문제를 이미 해결해 뒀다.
잘못 넘긴 인자 하나(`--tag -b1` 이 argparse 에서 옵션으로 읽힘)로 실행 전에 죽은 시도가
1회 있었고, 모델 호출 전이라 지출 $0 이다.

USD 는 run 마다 3~50배 흔들린다. 입력 토큰은 거의 같고(~856/호출) **출력 토큰이 흔들리기
때문**이다 — 출력 요율이 입력의 6배($12/M vs $2/M)라 trajectory 길이가 비용을 지배한다.

두 run 은 0 호출로 죽었다(`…140346Z-r2`, `…140356Z-luna`) — 러너에 상대 경로 `--config` 를
넘겼는데 `kisia_launch.py` 가 후보 디렉터리로 `chdir` 한 뒤 열어서 `FileNotFoundError` 다.
**모델을 호출하기 전에 죽었으므로 지출 $0 이고 판정 대상이 아니다.** trace 는 지우지 않았다.

**§9.4 가 요구하는 나머지 항목**

| 항목 | 유형 A (세션 D) | 유형 B·C (세션 D-2) |
|---|---|---|
| 세션 유지 성공률 | **N/A** — T 에 지속 세션 계층이 없었다 | **모델 구동 0/4** (유형 B 정상 run 에서 세션을 연 횟수 0). **하니스 구동 100%** — 프로브 두 run 의 세션 28개 전부 열리고 닫히고 생존자 0. **보조 run `bs1` 은 세션 4개를 열어 전부 유지**(한 세션이 `model.completed` 6개를 가로질렀다) |
| 프로세스 잔존 수 | **0** (3 run 전부) | **0** (10 run 전부, 후보 밖 검사기 확인). 세션 close 28건의 외부 확인 생존자도 전부 0 |
| 컨텍스트 초과 | 0 | 0 |
| 272K 경계 초과 | **0** (최대 입력 ~15K) | **0** (최대 입력 ~2.6K/호출) |
| 타임아웃 | 0 (최장 36.3초) | 0 (최장 100.0초, 상한 2400초) |
| cleanup 실패 | 0 | 0. worker·프로브 컨테이너 전부 `--rm`/`docker kill`, 잔존 0 |
| flag 후보와 출처 관찰 id | `kisia{5o9v_1472742}` — r1 `obs-0008` / r2b **null** / luna2 `obs-0006` | B `kisia{c41d_9e2f7b06}` — b1 **null** / **b2 `obs-0008`(3단계, S7·S8 동시 만족)** / b3 null / b4 `obs-0006`. C `kisia{7a2e_d0416b93}` — 4 run 전부 **null**(model_message) |
| verifier 판정 | 3 run 전부 true 1 + false 1 | 10 run 전부 `verdict=true` 1회 + `verdict=false` 1회(P-S8-a). `bs1` 은 모델이 zone 을 지어내 **false 를 한 번 더** 받았다 |
| 모델 호출·토큰·USD | 26회 / $0.1342 | **111회 / $0.3325** |
| **web search 사용 여부** | **미사용** | **미사용.** T 의 `ALLTOOLS` 에 검색 도구가 없다(T-08 이후 17종에도 없다). `search.performed` 0건. `EVAL_CONTRACT.md` 의 "write-up 유래 flag" 실패 조건 해당 사례 없음. **질의 원문: 없음** |

**A-5 / P-S3-a — 통과.**

```
…140133Z-r1     model.requested.model_id = gpt-5.6-terra   effort=none
…140508Z-luna2  model.requested.model_id = gpt-5.6-luna    effort=none
```

CLI 플래그(`--planner-model` 등)만으로 바뀌었고 **Python 소스는 한 줄도 고치지 않았다**
(`models.yaml` 데이터 항목 추가 = T-07 사소). S3 의 FAIL 조건("provider 이름이 제어 흐름에
박혀 있어 P-S3-a 에 소스 수정이 필요")에 해당하지 않는다. 검사기는 이 술어를 `스트림 밖`
으로 보고하므로(교차 스트림) 칸에 세지 않고 여기 관측으로 남긴다 — `CHECKER.md` §2.1 이
"arm 세션의 몫"이라고 넘긴 항목이다.

---

## 6. 폐기한 run 하나와 그 이유 (§9.6-4)

`…135632Z` 를 판정에서 뺐다. **지우지 않았다** — 스트림·trace·로그 전부 보존되어 있고
저장소에도 커밋했다.

폐기 이유: **어댑터 결함 5건**으로 만든 스트림이라 봉투가 계약을 만족하지 않았다.
arm 의 성질이 아니라 우리 코드의 성질을 잰 것이므로 기록에 남는 판정이 될 수 없다.
5건 전부 `CHECKER.md` §8 이 예고한 자리 — **"연산은 했는데 이벤트를 내지 않았다"** — 였고,
G 가 두 번 걸린 것과 같은 형태다.

| # | 검사기가 잡은 것 | 실제 원인 | 고친 것 |
|---|---|---|---|
| 1 | envelope **BROKEN — E4** (ts 가 감소) | `attempt.started` 의 ts 로 쓴 T 의 `start_time` 은 컨테이너를 띄운 **뒤에** 찍힌다(`agent.py:423-426`). verifyd 판정 시각도 뒤늦은 sweep 보다 이르다 | ts 로 정렬한 **뒤에** seq 를 매긴다 (`adapt.Builder`) |
| 2 | S1.3 `structural_patches_for_intake` 부재 | 총 구조 패치 수만 적고 **투입에 쓴 수**를 적지 않았다. 계약은 둘을 다른 값으로 본다 | `input.bound` 에 `0` 과 근거 |
| 3 | S2.2 "거부는 있으나 `host_check_file_exists` 로 확인된 것이 없다" | 컨테이너 안에서 `test -e` 했다. 계약은 **호스트에서** 확인하라고 한다 — 같은 컨테이너 안은 그 확인이 아니다 | `/input` 은 bind-mount 원본 stat, `/etc` 는 호스트 `docker diff` |
| 4 | S4.1 정수 status 와 실재하는 observation_id | `status="ok"` 문자열을 냈다. 계약은 "**exit code** 와 출력"을 요구하고 T 의 `run_command` 는 결과에 `returncode` 를 싣는다 | 정수 exit code + `observation_id` |
| 5 | S8.1 verifier 가 후보 프로세스 트리 밖 | verifier 는 실제로 밖에서 돌았지만 **그 사실을 이벤트에 넣지 않았다** | `verifier_process` 필드 |

**술어에 맞춘 것이 아니라 계약에 맞췄다.** 다섯 모두 `SEAM_CONTRACT.md` §1·§2 의 문장이
요구하는 사실인데 어댑터가 빠뜨린 것이고, 검사기는 그것을 정확히 지목했다.
3번과 5번은 진단을 위해 스트림 **사본**에 변형을 가해 가설을 확인했다(원본·검사기·fixture
미변경). 4·5번 확인 뒤 6/8, 나머지 셋을 고친 뒤 envelope OK.

**검사기가 틀렸다고 판단한 곳은 없다.** 검사기는 5건 전부를 잡았고 1건의 오탐도 없었다.

### 6.1 검사기가 잡지 못한 어댑터 결함 하나 — 토큰 회계

**검사기는 이것을 잡을 수 없다.** S3.2 는 "기록된 토큰과 pricing 으로 계산한 값이 `usd` 와
정확히 일치"를 요구하는데, 어댑터가 토큰과 `usd` 를 **같은 잘못된 값에서** 계산하면 자기
일관적이라 통과한다. 계약이 재는 것은 스트림 내부의 일관성이지 현실과의 대조가 아니다.

무엇이 틀렸나. 개정 A-1 의 `cache_write_tokens` 를 **API 가 보고하지 않는다고 가정하고**
pricing 파일이 적어 둔 실측 관계(`cached + cache_write + 3 == input`)로 파생시켰다.
실제로는 `usage.prompt_tokens_details.cache_write_tokens` 가 **직접 보고된다** — 두 endpoint
모두. 그리고 이 run 들에서 그 관계는 성립하지 않는다(cached=0, cache_write=0, input=856).
파생값을 쓰면 853 토큰이 cache-write 요율($2.50/M)로 과금돼 **입력 비용이 약 25% 부풀려진다.**

어떻게 드러났나. 계약과 무관한 확인 — "effective effort 를 관측할 수 있는가"를 보려고
`usage` 원본을 열었다가 `cache_write_tokens` 필드가 거기 있는 것을 봤다.

고친 것: 보고된 값이 있으면 그것을 쓰고, 없을 때만 파생하며 `cache_write_source` 로 어느
쪽인지 표시한다. 기록 판정 run(`p1`·`p2`)은 전부 `"reported"` 다.

**교훈으로 남긴다.** 술어가 자기 일관성만 재는 곳에서는 검사기가 어댑터를 지켜 주지 않는다.
`r1`·`r2b`·`luna2` 의 USD 는 이 결함을 안고 있으므로 §5 에서 **보조 증거**로만 쓴다.

---

## 7. 세션 C 의 예고가 맞았는가

| 세션 C 가 넘긴 말 (`CHECKER.md` §8) | 결과 |
|---|---|
| "어댑터가 가장 먼저 걸릴 곳은 **연산은 했는데 이벤트를 내지 않았다**" | **맞았다.** 5건 중 2·5번이 정확히 그 형태이고, 1·3·4번도 "사실은 있는데 봉투에 없다"의 변형이다 |
| "`answer.sweep` 은 arm 이 아니라 러너가 낸다. 붙이지 않으면 세 유형 전부 S8 이 no-evidence" | **맞았다.** 러너에 붙였고 S8.2b 는 3 run 전부 통과 |
| "C-3 은 arm 없이 양방향 확인이 끝났다. 실패하면 arm 탓" | **arm 탓이 아니었다.** C-3 이 arm 위에서 그대로 재현됐다 — 선언 대상 CONNECTED, 미선언 둘 REFUSED, 전부 컨테이너 안에서(§1.5) |
| "무게는 새로 만드는 것이 아니라 **한 번도 돌려본 적 없는 것**에 있었다" | **맞았다.** §9 |
| "세션을 열거나 닫을 때마다 `session.opened`/`session.closed` 를 반드시 낸다. G 의 첫 두 run 이 여기서 걸렸다" (§8-10) | **걸리지 않았다.** 어댑터가 세션 도구의 반환값에서 셋을 다 냈고 S6.3 이 첫 run 부터 통과했다. G 의 경험이 미리 적혀 있었기 때문이다 |

---

## 8. §10.1 생존 조건에 대한 현재 상태

> 선택지 1 (OSS fork): **T 가 유형 A·B·C 전부를 구조 패치 3개 이하로 통과**

| 유형 | 집합 판정 | FAIL 인 seam | 구조 패치 |
|---|---|---|---|
| A | **7/8** | S7 | 2 |
| B | **3/7** | S4, S6, S7, S8 | 3 |
| C | **4/6** | S6, S7 | 3 (유형 C 는 T-08 을 행사하지 않는다) |

**선택지 1 은 생존 조건을 만족하지 않는다.** 세 유형 전부에서 FAIL 이 있다. 구조 패치는
3개 이하로 들어왔으므로(3/3) **막힌 것은 예산이 아니라 seam** 이다 — 이 구분이 §12.2-2
(탈락 후보와 증거)에 그대로 들어간다.

§11 의 가설("유형 B 에서 T 가 구조 패치 3개 안에 들어오지 못할 가능성이 가장 높다")은
**반쯤 반증됐다.** 3개 안에 들어왔고 그 세 번째가 §4.1·§4.2 를 전부 만족한다. 들어오지
못한 것은 예산이 아니라 **후보가 자기 프롬프트로 그 계층을 쓰지 않도록 지시한다**는
전혀 다른 이유다(§1.4.1). 가설이 지목한 근거(D-CIPHER 계열이 interactive interface 를
구현하지 않았다는 논문 자신의 진술)는 맞았지만, 그것을 고치는 비용은 예산 안이었다.

FAIL 넷 중 **S7 은 세 유형 전부에서** 같은 이유로 터진다 — 모델이 조각을 자기 메시지 안에서
조립한다(§1.1). **유형 B 의 `b2` 에서 처음으로 S7 과 S8 이 동시에 만족됐다**(모델이 조립
결과를 스크립트 출력으로 흘려 `obs-0008` 이 생기고, 검사기가 `obs-0004`·`obs-0006` 에서
조립을 바이트로 검증했다). 세션 D 가 유형 A 에서 "유효한 5 run 중 0건"이라고 적은 그 모양이
유형 B 에서 **1/4** 로 나왔다. 두 seam 이 배관이 아니라 trajectory 에 달려 있다는 §1.1 의
관측이 유형을 바꿔도 유지된다.

이 사실들이 §10.2 의 적용을 어떻게 바꾸는지는 이 세션이 판단하지 않는다 — §10 은 사전
등록된 결정 규칙이고 결과를 본 뒤 고치면 §9.6-6 이다. **판정표를 채우고 넘긴다.**

---

## 9. 유형 B 에서 무엇이 기다렸는가 — 세션 D 의 예고와 그 결과

세션 D 가 소스에서 확인해 넘긴 사실들과, 세션 D-2 가 실제로 만난 것.

| 세션 D 의 예고 | 결과 |
|---|---|
| T 에 지속 세션 계층이 없다 (`run_command.py:33-42`, `ALLTOOLS` 11종) | **맞았다.** 확인 후 T-08 로 넣었다 |
| B-1 은 현 상태로 불가능하다 | **맞았다.** 그리고 T-08 뒤에도 **모델이 쓰지 않아** 불가능했다 — 세션 D 가 보지 못한 층이 하나 더 있었다(§1.4.1) |
| 세션을 표현하려면 도구 계층의 형태를 바꿔야 하고 그것은 구조 패치다. 남은 예산 1개가 여기 쓰인다 | **맞았다.** T-08, 예산 3/3 |
| §4.1 의 네 요구가 그 위에 얹힌다. G 는 약 14분 | **얹혔고 전부 통과했다.** T 는 약 12분(프로브 통과)·약 25분(검사기 통과) |
| 유형 C 는 세션 계층 없이도 가능해 보인다. 다만 `jar_digest_before/after` 배관이 없다 | **맞았다.** 세션 도구 없이 S4 PASS. 배관은 shim 에 붙였고(§4.3) **에이전트가 한 명령에 세 요청을 몰면 관측이 사라진다**는 대가가 딸려 왔다(§1.5) |

아래는 세션 D 가 남긴 원문이다. 판정이 아니라 소스에서 확인된 사실이었다.

- **T 에 지속 세션 계층이 없다.** `RunCommandTool.call`(`run_command.py:33-42`)은 매 호출마다
  `subprocess.Popen(['docker','exec', …,'bash','-c',command])` 를 새로 띄우고 `communicate`
  로 끝낸다. pty 도, 소켓도, 세션 핸들도 없다. `ALLTOOLS` 11종 어디에도 세션 도구가 없다.
- 따라서 **B-1(모델 턴 3회를 가로지르는 세션)은 현 상태로 불가능하다.** 에이전트가 한 번의
  `bash -c` 안에서 4단계를 전부 해도, S4 의 지속 세션 술어("같은 `session_id` 의 `session.io`
  가 `model.completed` 3개 이상을 사이에 두고")는 만족되지 않는다 — 모델 턴이 사이에 없다.
- 세션을 표현하려면 **도구 계층의 형태**를 바꿔야 하고, `SEAM_CONTRACT.md` §2 S4 가
  "후보가 세션을 표현하기 위해 loop 나 상태 모델을 고쳐야 하면 그것은 구조 패치"라고
  미리 못박았다. **남은 예산 1개가 여기 쓰인다.**
- §4.1 의 네 요구(newline 동일성, `&` 백그라운드 잡 포함 생존자 0, 좀비 제외, waitpid 에
  의존하지 않는 live 판정)는 그 위에 얹힌다. G 가 이것들을 통과시키는 데 쓴 시간은
  약 14분이다(`G_REPORT.md` §7).
- 유형 C 는 다르다. 쿠키 항아리는 컨테이너 파일시스템의 `curl -c/-b` 파일로 `docker exec`
  경계를 넘어 살아남으므로 **세션 계층 없이도 가능해 보인다.** 다만 `http.exchanged` 의
  `jar_digest_before/after` 를 어댑터가 실행 시점에 관측해야 하고, 그 배관은 아직 없다.

---

## 10. 세션 E(arm E, EnIGMA) 에 넘기는 것

**arm 무관 — 그대로 쓴다.**

```
adapter/make_dataset.py       세 fixture 전부 변환·검증됨. E 가 자기 형식을 쓰면 이 자리에 E 용 변환기
adapter/verifyd.py            unix 소켓 뒤 판정 데몬. 후보 무관 — E 도 소켓 경로 하나만 받는다
adapter/adapt.py              봉투 조립 전반. session.* / http.exchanged / live_session_ids 매핑 포함
adapter/run_arm.py            answer.sweep · 격리 프로브 · C-3 · workspace.destroyed · P-S8-a · C-4 개입
adapter/run_b_probes.py       §4.1·§4.2 프로브. **후보의 세션 모듈을 import 하는 한 줄만 바꾸면 E 에 붙는다**
pricing.openai.yaml           요율. cache_write 는 API 가 직접 보고한다(파생 금지, §6.1)
```

**E 를 붙일 때 먼저 답해야 할 것 넷.**

1. **E 에 지속 세션 계층이 있는가.** 있으면 T-08 에 해당하는 구조 패치가 필요 없고, §10.1 의
   선택지 2 생존 조건("어떤 seam 에서 E 가 §3 계약 뒤에서 구조 패치 3개 이하로 통과")이
   유형 B 에서 바로 걸린다. 없으면 T 와 같은 자리에서 예산을 쓴다. **E 의 구조 패치 작성
   시간은 §10.2 의 우발 조항이 G 의 약 14분과 직접 비교하는 값이므로 실측이 필수다.**
2. **E 의 프롬프트가 세션을 쓰라고 하는가.** T 에서 판정을 가른 것은 배관이 아니라 이것이다
   (§1.4.1). E 의 프롬프트 자산을 먼저 읽고, 세션 도구를 넣어도 쓰이지 않을 가능성을
   **run 전에** 적어 두라. 프롬프트는 고치지 않는다.
3. **E 가 chat/completions 를 쓴다**(ADR-0001). `reasoning_effort=none` 이 강제되고 endpoint
   차이는 그대로 남는다. `cache_write_tokens` 는 파생하지 말고 보고된 값을 쓰라(§6.1).
4. **E 가 챌린지 서비스를 자동 퍼블리시하려는가** — `HOST_EXCEPTIONS.md` §6. T 는 `compose:
   false` 로 그 경로가 애초에 열리지 않았다(`FIXTURES.md` c-web hard_constraints).

**판정 방법에 관한 것 둘.**

- 판정 단위를 **정상 스트림 전부의 집합**으로 잡았다(§1). 세션 D 의 유형 A(6 중 2 선택)와
  다르다. E 에서도 같은 규칙을 쓰면 T 와 비교 가능하다.
- **하니스 구동 프로브와 모델 구동 프로브를 스트림에서 구분해 두었다**(`driven_by` 필드).
  이 구분이 없으면 "배관이 통과했다"와 "arm 이 통과했다"가 섞인다 — 유형 B 에서 그 둘이
  정반대였다.

---

## 부록 A. 재현

```bash
ssh -i ~/.ssh/id_rsa ctf-spike-user@203.0.113.10

# 패치 (멱등)
python3 <HOME>/spike-d/adapter/patches/apply_T04_minor_openai_params.py
python3 <HOME>/spike-d/adapter/patches/apply_T05_structural_flag.py
python3 <HOME>/spike-d/adapter/patches/apply_T06_structural_isolation.py
python3 <HOME>/spike-d/adapter/patches/apply_T08_structural_session.py

# 골든 재확인 (매 arm run 직전, FIXTURES §4.4)
cd <HOME>/spike-b/golden && python3 run.py all

# arm run — 키는 ctf 계정에서 프로세스 환경변수로만 넘어간다
ssh CTF-agent
set -a; . ~/.config/kisia-agent/secrets.env; set +a; export OPENAI_API_KEY
sudo -u ctf-spike-user --preserve-env=OPENAI_API_KEY -H bash -c '
  cd <HOME>/spike-d && <HOME>/candidates/tatar-ctf-agents/.venv/bin/python \
    adapter/run_arm.py --fixture a-static \
    --config <HOME>/spike-d/adapter/config/kisia_a.yaml \
    --pricing pricing.openai.yaml --max-cost 1.0'
# (--config 는 반드시 절대 경로. 러너가 후보 디렉터리로 chdir 한다 — §5)

# 유형 B (§4.1·§4.2 프로브가 attempt 전에 자동으로 돈다. --skip-b-probes 로 끌 수 있다)
sudo -u ctf-spike-user --preserve-env=OPENAI_API_KEY -H bash -c '
  cd <HOME>/spike-d && <HOME>/candidates/tatar-ctf-agents/.venv/bin/python \
    adapter/run_arm.py --fixture b-session \
    --config <HOME>/spike-d/adapter/config/kisia_b.yaml \
    --pricing pricing.openai.yaml --max-cost 1.0 --tag=-b1'

# 유형 C (C-3 프로브가 컨테이너 기동 직후 자동으로 돈다)
sudo -u ctf-spike-user --preserve-env=OPENAI_API_KEY -H bash -c '
  cd <HOME>/spike-d && <HOME>/candidates/tatar-ctf-agents/.venv/bin/python \
    adapter/run_arm.py --fixture c-web \
    --config <HOME>/spike-d/adapter/config/kisia_c.yaml \
    --pricing pricing.openai.yaml --max-cost 1.0 --tag=-c1'

# C-4 (음성 개입: n 번째 HTTP 명령 뒤에 항아리를 버린다)
#   ... --fixture c-web --drop-jar-after 2 --tag=-c4neg

# §4.1·§4.2 프로브만 따로 (무과금, 모델 호출 0회)
<HOME>/candidates/tatar-ctf-agents/.venv/bin/python \
  adapter/run_b_probes.py --work <dir>/work --artifacts <dir>/artifacts

# 판정
cd <HOME>/spike-c && python3 checker.py --pricing <HOME>/spike-d/pricing.openai.yaml \
    --set <r1>/stream/stream.jsonl <r2b>/stream/stream.jsonl

# 키 검색 (매 run 후, HOST_EXCEPTIONS §7.2)
grep -raolF -f <(printf '%s\n' "$OPENAI_API_KEY") <HOME> | wc -l    # 0 이어야 한다
```

## 부록 B. 참조

- `docs/spike/SEAM_CONTRACT.md` (개정 r1) — §0.1 패치 경계, §1 봉투, §2 seam 별 술어, §3 하중표, §6 판정
- `docs/spike/CHECKER.md` §8 (arm 스트림의 최소 형태 10항목), §1.2 (집합 판정), §3 (S7/S8)
- `docs/spike/FOUNDATION_DECISION.md` §9.1 (arm 과 통제), §9.3 (판정 규칙과 패치 예산), §9.4 (기록 항목), §9.6 (무효 조건), §10.1 (생존 조건), §12.1
- `docs/spike/FIXTURES.md` §4.4 (재실행), §6 (S7/S8 미해결), §8 (NYU JSON 필드)
- `docs/spike/REPRO_MATRIX.md` §2.1 (T 의 부팅과 보류 패치), §3 (키 노출 검사)
- `docs/spike/G_REPORT.md` §6 (G 가 검사기에 걸린 두 곳), §7 (작성 시간)
- `docs/spike/arms/T/` — 스트림 16개(A 6 · B 5 · C 5), summary, 패치 diff 5개, 어댑터 전체
- `docs/spike/arms/T/patches/T-08-structural-session.diff` — 마지막 구조 패치의 diff
- `docs/spike/arms/T/patches/session_module_T08.py` — 그 패치가 후보에 넣는 모듈의 원본
