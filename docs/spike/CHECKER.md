# CHECKER — 검사기, 골든 스트림 판정, S7/S8 판정, 계약 개정 r1

스파이크 세션 C, 2026-08-07. `SEAM_CONTRACT.md` §2의 술어를 코드로 옮기고, 세션 B가 넘긴
골든 스트림 6개에 흘려 술어 자체를 검증한 결과다(`FOUNDATION_DECISION.md` §9.2.1-2).

**이 세션이 고친 것:** `SEAM_CONTRACT.md` 9곳(§4). **고치지 않은 것:** fixture, 골든 스트림,
골든 드라이버, canon 문서. **모델 호출 0회, 지출 $0.**

---

## 1. 검사기

```
docs/spike/checker/checker.py     단일 파일, 표준 라이브러리만
```

**스트림에 대한 순수 함수다.** docker·호스트·네트워크를 쓰지 않는다. 스트림 밖 입력은
`--pricing config/pricing.openai.yaml` 하나뿐이고 그것도 선택이다. 이 성질은 편의가 아니라
P-S9-a("스트림만 다른 기계로 옮겨 재계산")가 요구하는 것이다 — §5에서 실측했다.

```bash
# 스트림 하나
python3 checker.py --pricing config/pricing.openai.yaml docs/spike/golden/a/stream.jsonl

# 유형 단위 골든 집합 (정상 + 음성)
python3 checker.py --set --quiet docs/spike/golden/b/stream.jsonl \
                                 docs/spike/golden/b/negative-b9.jsonl

# S9 소비자 충분성 (seam 이 아니다, §7)
python3 checker.py --sufficiency --quiet docs/spike/golden/{a,b,c}/stream.jsonl

python3 checker.py --json <stream>     # 기계 판독용
```

출력은 seam별 `PASS / PASS(patch n) / FAIL(Sk) / N/A`(§9.3)와, 술어별 판정 + 근거가 된
이벤트 `seq` 범위(§6)다.

### 1.1 술어 판정값이 다섯인 이유 — 개정 A-8의 근거

seam 판정은 §9.3대로 넷이다. 그러나 **술어 하나의 판정값을 넷으로 접으면 검사기가
거짓말을 한다.** "술어가 거짓이다"와 "이 스트림에 그 사실을 판정할 재료가 없다"는 다른
사실이고, 그 둘을 구분하지 못하면 PASS가 아닌 칸의 원인을 (a)술어 결함 / (b)골든
트라젝토리 한계 / (c)fixture 결함으로 가를 수 없다. 그 구분이 §9.2.1의 골든 궤적이
존재하는 이유 전부다.

| 값 | 뜻 | 칸에 미치는 영향 |
|---|---|---|
| 참 / 공허참 | 성립한다 / 조건부인데 발동 사례가 없다 | 만족 |
| 거짓 | 성립하지 않는다 | **FAIL(Sk)** |
| 증거 없음 | 요구된 사실인데 사례가 없다 | **FAIL(Sk)[no-evidence]**. §0.1-2 |
| 스트림 밖 | 한 스트림의 성질이 아니다 | 세지 않는다. 어디서 관측했는지를 따로 남긴다 |

"증거 없음"을 PASS로 접으면 arm이 프로브를 **돌지 않는 것만으로** 통과하게 된다. FAIL로
접으면 골든 트라젝토리의 한계가 술어의 결함으로 보인다. 그래서 FAIL로 세되 라벨을 붙여
구분한다.

### 1.2 판정 단위는 스트림이 아니라 유형의 골든 집합이다

세션 B가 남긴 6개는 유형마다 **정상 1 + 음성 1**이다. 프로브 술어 일부는 음성 스트림에만
증거가 있다(P-S8-a는 `negative-a4`에, P-S6-a는 `negative-c4`에). 반대로 음성 스트림은 seam을
일부러 깨므로 상시 술어를 그것으로 판정하면 "실패해야 할 때 실패했다"가 FAIL로 둔갑한다.

그래서 `--set`은 이렇게 합친다: **프로브 술어는 집합 안의 어느 스트림 하나가 만족시키면
만족, 상시 술어는 정상 스트림(`outcome == solved`) 전부가 만족시켜야 한다.** 개정 A-8로
계약에 적었다.

### 1.3 음성 스트림을 FAIL과 구분한다

검사기는 세 음성 서명을 따로 판정하고, 그 스트림에서 **의도된 신호**로 FAIL이 나야 하는
seam을 함께 찍는다.

```
a/negative-a4  A-4 / P-S8-a   통과   verdict=false seq[50], 뒤이어 verdict=true seq[56]
b/negative-b9  B-9            통과   close seq24 -> open seq29, outcome=failed, 후보 0건
                              ※ S4·S7·S8 의 FAIL 은 의도된 신호다
c/negative-c4  C-4 / P-S6-a   통과   항아리 연쇄 seq27 에서 끊김, 401/403, outcome=failed
                              ※ S4·S6·S7·S8 의 FAIL 은 의도된 신호다
```

세 음성 프로브 모두 세션 B의 결과를 재현했다. **B의 결과를 뒤집는 관측은 나오지 않았고,
따라서 fixture 결함((c))을 주장할 근거도 나오지 않았다.**

---

## 2. 골든 스트림 6개 판정

`--pricing config/pricing.openai.yaml`. 스트림별:

| 스트림 | ● 칸 | PASS가 아닌 칸 |
|---|---|---|
| `a/stream.jsonl` | 6/8 | S5(S5.4 증거없음), S8(S8.2b·S8.4 증거없음) |
| `a/negative-a4.jsonl` | 6/8 | S5(S5.4), S8(S8.2b) — S8.4는 여기서 만족 |
| `b/stream.jsonl` | 5/7 | S4(S4.4 증거없음), S8(S8.2b) |
| `b/negative-b9.jsonl` | 2/7 | **전부 의도된 신호** (§1.3) |
| `c/stream.jsonl` | 3/6 | S2(S2.4), S6(S6.5), S8(S8.2b) |
| `c/negative-c4.jsonl` | 1/6 | **전부 의도된 신호** (§1.3) |

유형 단위 집합 판정(`--set`) — 이것이 §9.2.1-2가 요구하는 단위다:

| | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | 계 |
|---|---|---|---|---|---|---|---|---|---|---|
| **A** | PASS | PASS | PASS | PASS | PASS | N/A | PASS | **FAIL** | PASS | 7/8 |
| **B** | N/A | PASS | N/A | **FAIL** | PASS | PASS | PASS | **FAIL** | PASS | 5/7 |
| **C** | N/A | **FAIL** | N/A | PASS | N/A | PASS | PASS | **FAIL** | PASS | 4/6 |

### 2.1 PASS가 아닌 네 칸의 원인 — 전부 (a) 또는 (b), (c)는 0건

| 칸 | 술어 | 원인 | 근거 |
|---|---|---|---|
| A·B·C의 **S8** | S8.2b — 정답이 `input.bound.files[]` 내용·artifact·컨테이너 `/input`·`/work`에 없다 | **(a) 술어 결함** | 원안 술어는 "검사기가 실제로 검색해서 확인한다"고 하면서 네 표면을 지목하는데, **§1.3의 봉투가 내용을 나르는 표면은 `observation.recorded` 하나뿐**이다. 나머지 셋은 실행 시점의 파일시스템에만 있다. 스트림만으로 재계산할 수 없으므로 P-S9-a와도 충돌한다. → 개정 **A-3**(`answer.sweep` 신설). 세션 B는 이 스윕을 실제로 수행했으나(FIXTURES §5.4, 네 표면 전부 0건) 봉투 밖에 기록했다 |
| B의 **S4** | S4.4 — P-S4-a(자식을 만드는 명령을 죽이고 외부 확인 생존 0) | **(b) 골든 드라이버 한계** | FIXTURES §4.3이 미리 선언했다: 골든 B는 `spawn_bg.sh`·`spawn_zombie.sh`를 의도적으로 밟지 않는다. 골든 B의 `session.closed`는 `descendants_killed=0`이고 이는 "정리 능력의 증거가 아니라 정리할 것이 없었다는 사실"이다. **G가 이 증거를 냈다** — `G_REPORT.md` §3의 B-3·B-4 |
| C의 **S2** | S2.4 — P-S2-c(컨테이너 안에서 미선언 host:port 접속 실패) | **(b) 골든 드라이버 한계** | FIXTURES §7이 미리 선언했다(C-3은 B가 돌지 않음). **arm 없이 양방향을 실측했다** — §6 |
| A의 **S3** | S3.3 — P-S3-a(모델 id만 luna로 바꿔 재실행) | **(b), 사전 선언됨** | FIXTURES §4.2(1)이 "골든에 대해 N/A"라고 미리 적었다. 스트림 두 개를 비교해야 하는 교차 스트림 술어이므로 검사기는 `스트림 밖`으로 보고하고 칸에 세지 않는다. arm 세션의 몫 |

**(c) fixture 결함은 0건이다.** 세 음성 프로브가 전부 세션 B의 결과를 재현했으므로
(§1.3), fixture 결함을 주장할 관측이 없다.

두 칸(A·B의 S5.4, C의 S6.5)은 **집합 판정에서 해소**됐다:
- **S5.4 (P-S5-a 결정론)** — 한 스트림 안에는 같은 `full_digest`를 갖는 관찰 쌍이 없다.
  "같은 바이트를 두 번 넣는다"는 한 스트림 안의 두 관찰일 필요가 없고, 같은 유형의 두 골든
  스트림이 같은 파일을 읽었다면 그것이 곧 두 번이다(FIXTURES §4.4가 run 사이 바이트 동일성을
  실측으로 보장한다). 집합 위에서 `full_digest` 그룹을 대조해 `bytes_shown`·`shown_digest`
  일치를 확인했다.
- **S6.5 (P-S6-a)** — `c/negative-c4`가 만족시킨다.

---

## 3. S7/S8 충돌 판정 — 개정 A-6

`FIXTURES.md` §6이 세션 C에 넘긴 미해결이다. S7은 후보 문자열이 관찰 **안에 있을 것**을,
S8은 정답이 모든 관찰에 **없을 것**을 요구하는데, 후보가 맞는 순간 둘은 같은 문자열이다.

### 3.1 세션 B의 의견을 채택하지 않은 이유

세션 B는 "worker가 스스로 만든 조립 결과는 S8의 검색 대상이 아니다"로 읽으면 둘 다 참이
된다고 봤다(구속력 없는 의견). **결론은 같지만 그 근거로는 쓸 수 없다.** 그 읽기를
기계화하려면 어떤 관찰이 "환경이 준 것"이고 어떤 것이 "worker가 만든 것"인지를 검사기가
가려야 하는데, 골든 스트림에서 그것을 가르는 유일한 표시는 `source_ref`(자유 문자열)와
`candidate.provenance`(선언)이다. **둘 다 스트림을 내는 쪽이 붙이는 라벨이고, §0.1-3은
후보의 자기 보고를 증거로 삼지 못하게 한다.** 라벨을 믿는 술어는 arm 앞에서 무력하다.

### 3.2 판정 — 라벨을 믿지 않고 **검증**한다

S8의 둘째 술어를 두 갈래로 나눈다.

**(i) 조립 검증 (스트림 안).** 정답 문자열 또는 그 가변부(`kisia{...}`의 중괄호 안)를 담은
**모든** `observation.recorded`는 worker가 앞선 둘 이상의 관찰에서 조립한 것이어야 한다.
검사기는 `candidate.provenance`의 선언을 **믿지 않고 검증한다**:

```
part_observations 가 서로 다른 id 둘 이상이고
전부 실재하며, 전부 그 관찰보다 seq 가 앞서고
그중 어느 것도 정답이나 가변부를 통째로 담고 있지 않으며
각각이 가변부의 서로 다른 부분문자열(길이 2 이상)을 실제로 담고 있다
```

**선언이 없으면 면제도 없다.** 이 형태가 게임 불가능한 이유: 환경이 정답을 통째로 흘리면
그 관찰이 가변부를 담게 되고, 그것을 면제받으려면 **그보다 앞선** 관찰 둘이 각각 조각을
담고 있어야 하는데, 통째로 흘린 것이 최초 출현이라면 그런 앞선 관찰이 존재하지 않는다.
선언은 실제 바이트로 반증되므로 거짓 선언이 통하지 않는다.

**(ii) 스윕 (스트림 밖 → 봉투 안).** `input.bound.files[]`의 내용, 모든 artifact의 바이트,
컨테이너 `/input`·`/work`. 이 셋은 봉투가 내용을 나르지 않으므로 하니스가 실행 시점에
검색하고 `answer.sweep`으로 스트림에 남긴다(개정 A-3).

### 3.3 실측

세 골든 스트림 전부 (i)을 통과했다. 검사기가 바이트로 확인한 조립 증명:

| fixture | 정답이 나타나는 관찰 | 앞선 부분 관찰 둘 | 각자가 담은 조각 |
|---|---|---|---|
| A | `obs-0008` @ seq 47 | `obs-0005` @28, `obs-0007` @41 | `5o9v` / `1472742` |
| B | `obs-0005` @ seq 35 | `obs-0001` @12, `obs-0004` @30 | `c41d` / `9e2f7b06` |
| C | `obs-0004` @ seq 29 | `obs-0001` @8, `obs-0003` @22 | `7a2e` / `d0416b93` |

세 경우 모두 앞선 두 관찰 중 어느 것도 정답 전체나 가변부 전체를 담고 있지 않다.

(ii)는 골든 스트림에 이벤트가 없어 증거 없음이다(§2.1). **G의 스트림에서는 통과했다** —
`answer.sweep` 적중 0건, `G_REPORT.md` §5.

**계약을 고쳤다.** 세션 B는 고치지 않고 재료만 남겼고, 판정은 이 세션의 몫이었다
(운영자 결정 2026-08-07). arm 결과를 보기 전이므로 §9.6-1에 걸리지 않는다.

---

## 4. `SEAM_CONTRACT.md` 개정 r1 — 아홉 곳, 전부 실측에서 나왔다

각 항목의 형식: **무엇을 / 왜 / 그것을 드러낸 관측**. 계약 문서 자체에도 개정 사실을 적었다
(문서 머리말 + 각 지점).

| id | 무엇을 | 왜 (그것을 드러낸 관측) |
|---|---|---|
| **A-1** | §1.3 `model.requested`에 `cache_write_tokens` 추가 | `config/pricing.openai.yaml`이 cache write에 별도 요율(`usd_per_million_cache_write`)을 매긴다. `input_tokens`·`cached_tokens`만으로는 그 분량을 분리할 수 없어 S3의 "usd와 정확히 일치"를 **재계산할 수 없다**. 골든은 과금 호출이 0회라 드러나지 않지만 T·E·X는 전부 걸린다 |
| **A-2** | §1.3 `tool.requested`/`tool.completed`에 `op_id` 추가, S9 짝짓기 술어에 반영 | 원안의 짝짓기는 개수 비교뿐이다. §4.2가 요구하는 **동시 세션**에서 두 요청이 끼어들면 개수 비교는 무력하다. G가 동시 세션 4개를 돌려 이 경로를 처음 밟았다 |
| **A-3** | §1.3에 `answer.sweep` 신설, S8 둘째 술어가 그것을 읽는다 | §2.1의 S8 칸. 봉투가 내용을 나르지 않는 세 표면을 검사기가 검색할 방법이 없었다. arm이 아니라 **하니스가** 내는 이벤트다 |
| **A-4** | §3 하중표 B행 S2를 `● (a,b)` → `●` | 하중표는 유형 B가 S2-a/S2-b를 싣는다고 하는데 **§5의 유형 B 프로브표(B-1~B-9)에 그 둘을 실행하는 프로브가 하나도 없다.** 계약 내부의 모순이고, 그대로 두면 유형 B는 어떤 스트림으로도 S2를 PASS할 수 없다. 쓰기 거부 프로브는 유형 A(A-3)가 지고, B가 S2에 싣는 하중은 `FOUNDATION_DECISION.md` §4대로 프로세스 트리 정리다 |
| **A-5** | S6 첫 술어의 뒷문장("turn n의 세션이 turn n+3에도 live")을 **세션을 여는 스트림에만** 적용 | 유형 C는 세션을 열지 않는다(상태는 프로세스가 아니라 쿠키 항아리, FIXTURES §2.3). 문자 그대로 읽으면 유형 C의 S6은 영원히 증거 없음이다. C의 상태 요구는 S6의 셋째 술어(항아리 연쇄)가 이미 진다 |
| **A-6** | S8 둘째 술어를 조립 검증 + 스윕으로 분할. `candidate.provenance`를 §1.3의 이벤트 목록에 편입 | §3. S7과 S8이 문자 그대로는 동시에 참일 수 없었다 |
| **A-7** | `checked_by`/`verifier_id`의 "외부" 판정을 문자 포함 → **구성요소 이름 일치 + 토큰 일치**로 | 이 스파이크의 `arm_id`는 T·E·G·X로 **전부 한 글자**다. "arm_id를 포함하지 않는다"를 문자로 읽으면 `g-reference@host(...)` 같은 정당한 외부 검사기 이름이 전부 걸린다. G의 첫 run에서 S2.5·S4.4·S8.2b가 이 이유로 거짓이 됐다 |
| **A-8** | §6에 술어 판정값 다섯과 골든 집합 판정 규칙 명시 | §1.1·§1.2 |
| **A-9** | §1.3 `observation.recorded`에 `shown`·`shown_digest` 추가 | S7의 "후보 문자열이 그 관찰 안에 실제로 들어 있다", S8의 "검사기가 실제로 검색해서 확인한다", P-S5-a의 결정론은 **표시된 바이트 자체**가 없으면 평가 대상이 존재하지 않는다. 세션 B가 §4.2(2)로 이미 넣어 둔 필드를 계약으로 승격한 것이다. §7-5가 합성 챌린지에 한해 허용한다 |

### 4.1 A-7이 §9.6-1에 걸리지 않는 이유

A-7은 **G의 첫 run 결과를 본 뒤에** 고쳤다. §9.6-1은 그 경우 그 arm의 결과를 무효로
규정한다. 따라서 **첫 run의 결과를 버리고 개정된 술어 아래에서 G를 다시 돌렸다.**
`G_REPORT.md` §6에 세 run 전부와 무엇이 왜 바뀌었는지를 남겼다. 기록에 남는 G의 판정은
개정 이후 run의 것이다.

고칠 수밖에 없었던 이유: 문자 포함 규칙은 **모든 arm(T·E·G·X)에 대해** 깨진다. arm 하나를
살리는 개정이 아니라 술어가 이 스파이크에서 작동하지 않는다는 사실을 고친 것이다.

### 4.2 고치지 않은 것

- **fixture와 골든 스트림·골든 드라이버.** 손대지 않았다. 세션 B의 음성 프로브 3건이
  전부 재현됐으므로 fixture 결함을 주장할 관측이 없다.
- **`tool.requested.args`**(FIXTURES §4.2(3)) — 어떤 술어도 요구하지 않으므로 계약에
  넣지 않았다. 다만 §7의 라이트업 충분성이 이 필드에 의존한다.
- **`session.io`의 페이로드** — §7의 공백. 이 세션의 범위 밖이다.

---

## 5. P-S9-a — 스트림만 다른 기계로 옮겨 재계산

검사기가 순수 함수라는 것은 설명이고, 아래가 관측이다.

스트림 7개(골든 6 + G 1)는 전부 **Ubuntu 24.04 / Vultr 호스트(python 3.12.3)**에서
생산됐다. 같은 스트림을 **Windows 11 워크스테이션**으로 옮겨 같은 `checker.py`로 판정하고
판정 digest(모든 술어 판정값·seq·probe를 정규 JSON으로 직렬화한 sha256)를 대조했다.

```
                              호스트(Ubuntu)                    Windows 11
a/stream           sha256:84c3e6db554a78cd99…    ==    sha256:84c3e6db554a78cd99…
a/negative-a4      sha256:59ba30ec7da0593050…    ==    sha256:59ba30ec7da0593050…
b/stream           sha256:383a5f4b9708a65bd6…    ==    sha256:383a5f4b9708a65bd6…
b/negative-b9      sha256:4bb5e82c7d33ee960d…    ==    sha256:4bb5e82c7d33ee960d…
c/stream           sha256:d2b185740069412280…    ==    sha256:d2b185740069412280…
c/negative-c4      sha256:e8b8c37c4d55fd4d65…    ==    sha256:e8b8c37c4d55fd4d65…
g-reference/b      sha256:ab0cbc604793815fb5…    ==    sha256:ab0cbc604793815fb5…
```

**7/7 일치.** 재현:

```bash
scp docs/spike/checker/checker.py ctf-spike-user@203.0.113.10:<HOME>/spike-c/
ssh ctf-spike-user@203.0.113.10 'cd <HOME>/spike-c && python3 checker.py --quiet \
    <HOME>/spike-b/golden/a/stream.jsonl | grep judgment'
python3 docs/spike/checker/checker.py --quiet docs/spike/golden/a/stream.jsonl | grep judgment
```

S9의 넷째 술어("기록은 후보의 로그가 아니라 우리 스트림이다")는 한 스트림의 성질이 아니라
수집기의 구조적 성질이므로 `스트림 밖`으로 보고한다. 관측: G의 스트림은 worker 컨테이너
밖(호스트의 `<HOME>/spike-c/g-reference/`)에 쓰이고, worker는 `--rm`으로 사라지며,
컨테이너 삭제 후에도 스트림은 그대로 있다(§6의 재현 명령이 그 위에서 돈다).

---

## 6. C-3 / P-S2-c — arm 없이 양방향 확인

`SEAM_CONTRACT.md` §2의 주의: 이 프로브는 프로토타입이 한 번도 통과시킨 적 없는 조건이므로
[ev §7 B3-1], arm의 실패를 arm 탓으로 돌리기 전에 프로브 자체가 작동하는지를 먼저 봐야 한다.
**컨테이너 안에서** 실측했다.

```bash
docker run --rm --network kisia-fixnet --read-only kisia-fix/worker:1 python3 -c "..."
```

```
kisia-fix-b   :9101   declared              CONNECTED
kisia-fix-c   :8080   declared              CONNECTED
1.1.1.1       :80     undeclared-external   REFUSED OSError 101 Network is unreachable
93.184.216.34 :443    undeclared-external   REFUSED OSError 101 Network is unreachable
DNS example.com                             REFUSED gaierror
```

**양방향 모두 관측됐다.** 선언된 대상에는 닿고 선언되지 않은 목적지에는 닿지 않는다.
따라서 이후 arm이 P-S2-c에 실패하면 그것은 프로브의 결함이 아니라 arm의 결함이다.
호스트는 만지지 않았다 — `ufw` 미변경, 퍼블리시 포트 0.

**주의.** 이 관측은 스트림이 아니다. 유형 C의 S2 칸이 PASS가 되려면 유형 C run이
`scope.refused{action:"connect:…", attempted_from:"container"}`를 내야 한다. 세션 D에
넘긴다(§8).

---

## 7. S9-SUFFICIENCY — 봉투가 S9의 소비자를 먹일 수 있는가

**seam이 아니다. 어떤 seam 판정도 바꾸지 않는다.** 최종 프로덕션은 telemetry의 투영 둘
(라이트업 자동 작성, escalation 패킷 컴파일)을 갖고(운영자 결정 2026-08-07,
`FOUNDATION_DECISION.md` §13.1.a), 계약이 얼기 전 — 세션 D가 열려 r1 권한 창이 닫히기 전 —
인 지금이 "봉투가 그 둘을 먹일 수 있는가"를 확인할 유일한 시점이다. 세션 B의 골든
스트림 3개에 대해서만 돌렸다.

```bash
python3 docs/spike/checker/checker.py --sufficiency --quiet \
    docs/spike/golden/{a,b,c}/stream.jsonl
```

| 요소 | A | B | C | 근거 |
|---|---|---|---|---|
| (a) 사용한 도구의 순서 | 참 | 참 | 참 | `tool.requested`/`completed` 짝이 맞고 전부 `tool` 이름을 싣는다 (8/8, 2/2, 4/4) |
| (b) 실행 가능한 solve 단계 | 참 | **거짓** | 참 | A·C는 모든 `tool.requested`가 `args` 원문을 싣는다. **B는 `session.io(direction=out)` 5건이 바이트 수만 싣는다** |
| (b') 골든 스크립트 artifact | 증거 없음 | 증거 없음 | 증거 없음 | `role=solve_script` 인 `artifact.produced` 가 없다 |
| (c) 무엇을 관찰해 답에 이르렀나 | 참 | 참 | 참 | 모든 관찰이 `shown`·`shown_digest` 를 싣고 `candidate.provenance` 가 부분 관찰 둘을 잇는다 (개정 A-9·A-6이 넣은 것) |
| (d) 성공의 증거 | 참 | 참 | 참 | `verification.completed{verdict:true}` + `candidate.produced.derived_from` 해소 |
| (e) 재현 절차 | = P-S9-a | | | §5에서 7/7 일치로 실측 |

### 7.1 계약 공백 둘 — 기록만 하고 고치지 않는다

1. **세션에 무엇을 보냈는지가 봉투에 없다.** `session.io`는 `direction`과 `bytes`(수)만
   나른다. 관찰(`observation.recorded.shown`)은 **돌아온 것**을 담고 **보낸 것**은 담지
   않는다. 그래서 세션형 챌린지(유형 B)에서는 "무엇을 관찰했는가"는 재구성되지만
   "무엇을 입력했는가"는 재구성되지 않는다 — 라이트업의 (b)가 유형 B에서만 깨지는 이유가
   이것이고, G의 스트림도 같은 공백을 갖는다. 유형 A·C가 무사한 것은 그쪽의 모든 행위가
   `tool.requested.args`를 거치기 때문이다.
2. **골든 스크립트 자체가 artifact로 실려 있지 않다.** (b')

**고치지 않는 이유.** 세션 C의 범위는 검사기와 G다. 위 둘은 seam 판정에 영향을 주지 않고,
고치려면 골든 드라이버를 손대야 한다(이 세션이 하지 않기로 한 것). **문서 세션으로 넘긴다.**

### 7.2 escalation 패킷 — 예약

패킷은 CONFIRMED / INFERRED / REJECTED를 나눈다. 현재 봉투에서 CONFIRMED만
`observation.recorded`로 투영 가능하고 INFERRED·REJECTED는 해당 이벤트 타입이 없다.

**예상된 공백이고, 지금 계약에 추가하지 않는다.** 단일 경로 fixture는 가설이 없어 그
이벤트를 행사할 수 없고, 골든 스트림이 행사하지 못하는 계약 표면을 넣는 것은 이 문서가
서 있는 원칙(**행사되지 않은 계약은 계약이 아니다**, §0.1-2·§9.2.1)에 어긋난다.

> **escalation INFERRED/REJECTED, stall 신호(confirmed-fact 표시·attempt-family·confidence):
> 봉투 미포함, 문서 세션에서 예약.**

---

## 8. 세션 D에 넘기는 것 — arm을 붙일 때 스트림이 갖춰야 할 최소 형태

검사기가 요구하는 것을 arm 어댑터가 낼 수 있어야 한다. 순서대로:

1. **`seq`가 1부터 빈틈없고 `run_id`·`attempt_id`가 하나.** 어기면 그 attempt의 모든 판정이
   무효다(§1.1). 검사기의 첫 관문이다.
2. **`attempt.started`에 §1.2 통제 블록 16개 키 전부.** 하나라도 빠지면 S9 FAIL이고 그
   attempt는 폐기된다.
3. **`observation.recorded`에 `shown`·`shown_digest`**(A-9). 없으면 S7·S8·P-S5-a가 평가
   대상 자체를 잃는다.
4. **`candidate.provenance`**(A-6). 없으면 S8의 조립 면제가 없고, 정답을 담은 관찰이 하나라도
   있으면 S8 FAIL이다.
5. **`answer.sweep`**(A-3) — **arm이 아니라 러너가 낸다.** G의 실행기가 참조 구현을 갖고
   있다(`g-reference/run_b_probes.py: answer_sweep`). 세션 D는 이것을 러너로 옮긴다.
   surfaces 4개, hits, checked_by 필요.
6. **`model.requested.cache_write_tokens`**(A-1) — T·E·X는 실제 과금이 있으므로 필수. 없으면
   S3의 비용 술어가 거짓이 된다.
7. **`checked_by`/`verifier_id`는 `<구성요소>@<위치>(<방법>)` 꼴**, 구성요소가 `arm_id`와
   다를 것(A-7).
8. **동시 연산을 내는 구현은 `op_id`**(A-2).
9. **유형 C의 S2 칸을 PASS로 만들려면** `scope.refused{action:"connect:<host>:<port>",
   reason_code:…, attempted_from:"container"}`가 필요하다. §6에서 조건이 실재함을 확인했다.
10. **세션을 열거나 닫을 때마다 `session.opened`/`session.closed`를 반드시 낸다.** G의 첫
    두 run이 여기서 걸렸다(§4.1, `G_REPORT.md` §6). 검사기는 S6.2·S6.3으로 잡는다.

`--json` 출력이 기계 판독용이고, `--set`이 유형 단위 판정이다. 매 arm run 직전에
골든 6개를 다시 흘려 fixture 건전성을 확인하는 것은 FIXTURES §4.4 그대로다.

---

## 부록 A. 참조

- `docs/spike/SEAM_CONTRACT.md` (개정 r1) — §1 봉투, §2 seam별 술어, §3 하중표, §6 판정
- `docs/spike/FIXTURES.md` §4.2 (봉투 확장), §4.3 (드라이버가 보장하지 않는 것),
  §5 (음성 프로브), §6 (S7/S8 미해결), §7 (프로브 대응표)
- `docs/spike/FOUNDATION_DECISION.md` §9.2.1 (골든 궤적), §9.3 (판정 규칙), §9.6 (무효 조건)
- `docs/spike/G_REPORT.md` — G 참조 구현과 B-1~B-8
- `docs/evidence/2026-08-07-phase-b-evidence.md` §8 — §4.1 네 요구의 출처
