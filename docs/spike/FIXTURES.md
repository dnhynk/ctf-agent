# FIXTURES — 계약 픽스처 3종, 골든 트라젝토리, 음성 프로브

스파이크 세션 B, 2026-08-07. `FOUNDATION_DECISION.md` §9.2·§9.2.1의 산출물이고,
`SEAM_CONTRACT.md` §5의 프로브가 딛고 설 바닥이다.

**이 세션이 만들지 않은 것:** 검사기(세션 C), G 참조 구현(세션 C), arm 실행(세션 D~F).
**모델 호출 0회.** 골든 트라젝토리는 도구 계층만 쓰므로 모델이 필요 없고, 필요했다면
설계가 틀린 것이다. 이 세션의 모델 비용은 $0이다.

---

## 1. 세 fixture가 공유하는 형태 — flag는 조립된다

세 fixture 모두 정답이 `kisia{X_Y}` 꼴이고, **X와 Y는 서로 다른 두 관찰에서 나오며
완성된 문자열은 어느 한 곳에도 존재하지 않는다.**

이 형태는 §9.2의 두 요구를 동시에 만족시키는 유일한 형태다. §9.2는 유형 C에 대해
"세 번째 요청에서 비로소 flag"라고 하면서 공통 규칙에서는 "정답은 fixture 서비스 응답
어디에도 없다"고 한다. 두 문장이 동시에 참이려면 **서비스가 주는 것은 flag가 아니라
flag의 재료**여야 한다. 유형 A·B에도 같은 형태를 적용해 세 fixture의 S8 성질을 하나로
맞췄다.

측정으로 확인했다(§5.4). 세 flag 각각에 대해 `/input`(아카이브 내부까지 풀어서),
`/work`, `/artifacts`, 절단 원본 artifact 전부에서 **적중 0건**이다.

| | X (관찰 1) | Y (관찰 2) | 어느 하나만으로는 안 되는 이유 |
|---|---|---|---|
| **A** | `notes.bin`에 심긴 `TAGSEL:<tag>` | `ledger.csv`에서 그 tag의 value 합 | tag 없이는 무엇을 합칠지 모르고, 합 없이는 값이 없다 |
| **B** | 접속 배너의 `zone=` | `READ`가 주는 `part=` | `READ`는 `ARM` 뒤에만 열리고 `ARM`은 그 연결의 nonce를 요구한다 |
| **C** | `/login` 응답의 `zone=` | `/vault` 응답의 `part=` | `/vault`는 쿠키 **와** `ARMED` 상태를 둘 다 요구한다 |

**난이도를 올리지 않았다.** §9.2가 요구한 대로 셋 다 단일 경로이고 각 단계가 자명하다.
모델 능력이 배관 판정에 섞이지 않게 하는 것이 목적이므로, 어렵게 만들 이유가 없다.

---

## 2. fixture별 설계와 그 근거

### 2.1 유형 A — `fixtures/a-static/` 정적 분석

`/input/bundle.tar.gz` 하나. 풀면 `notes.bin`(64 KiB)과 `ledger.csv`(1,795,837 B).

**`notes.bin`을 0x80–0xFF 바이트로만 채운 이유.** 그 범위에는 인쇄 가능한 ASCII가 하나도
없으므로 `strings`가 찾아내는 문자열은 우리가 심은 것 **하나뿐**이다. 단일 경로를 바이트
수준에서 보장하는 장치이고, 동시에 `cat`으로는 읽히지 않아 도구를 하나 강제한다.
"도구 2종"을 `strings`라는 **이름**으로 고정하지 않고 **관찰의 종류**로 고정한 것은,
arm마다 이미지가 달라 특정 바이너리의 유무가 배관 판정에 섞이지 않게 하기 위해서다.

**`ledger.csv`가 1.8 MB인 이유(A-2).** 표시 한도 4096 B의 438배다. 절단이 선택이 아니라
필연이 되어야 S5의 절단·artifact 경로가 강제된다.

**입력물을 저장소에 커밋하지 않는 이유.** `build/build_inputs.py`가 시드 `20260807` 하나로
바이트 단위 재생성한다(tar 메타데이터와 gzip mtime을 전부 고정했다). 저장소에는 생성기와
**봉인된 sha256**만 둔다. 세션 C가 `artifact.produced.sha256`을 실제 바이트와 대조해야 할
때 이 스크립트를 다시 돌리면 되고, 어긋나면 `manifest.json`의 값이 기준이다.

### 2.2 유형 B — `fixtures/b-session/` 인터랙티브 세션

`kisia-fix-b:9101` TCP. 네 단계: 배너 → `HELO`(연결 전용 nonce) → `ARM <nonce 역순>` → `READ`.

**세션 유지를 강제하는 장치는 한 줄이다.** `nonce`·`greeted`·`armed`가 전부
`Handler.handle`의 지역 변수, 즉 **연결 스코프**다. 연결이 끊기면 사라지고 새 연결은 새
nonce를 뽑는다. 공유 저장소가 없으므로 재접속으로 이어받을 경로가 존재하지 않는다.

**단계가 넷인 것은 자의적이지 않다.** S4의 지속 세션 술어는 "같은 `session_id`의
`session.io`가 **`model.completed` 3개 이상을 사이에 두고** 나타난다"이다. 관찰마다 턴
하나인 루프에서 세션을 만지는 턴이 k개면 첫 io와 마지막 io 사이의 `model.completed`는
k−1개다. 3개를 만들려면 세션을 만지는 턴이 4개여야 하고, 프로토콜의 단계 수는 거기서
나왔다. 실측: 골든 B 스트림에서 `session.io` seq 10..40 사이의 `model.completed` **4개**.

**정답 경로가 아닌 입력물 2개.** `/input/spawn_bg.sh`(B-3: `sleep 300 &`),
`/input/spawn_zombie.sh`(B-4: 즉시 종료하는 자식을 거두지 않는다). §9.2가 말한 "**별도로**
자식 프로세스를 만드는 명령"이다. **골든 트라젝토리는 이 둘을 밟지 않는다** — 이유는 §4.3.

### 2.3 유형 C — `fixtures/c-web/` 웹 상태

`kisia-fix-c:8080` HTTP. `POST /login` → `POST /arm` → `GET /vault`.

**유형 B와 다른 점.** HTTP는 연결이 끊겨도 정상이다. 턴을 가로질러 살아야 하는 것은
프로세스가 아니라 **쿠키 항아리 하나**다. 그래서 항아리를 도구 안이 아니라 도구
밖(드라이버)에 두었다 — 그래야 `jar_digest_before/after`가 의미를 갖고, C-4가 "턴 사이에
항아리를 버린다"를 실제로 수행할 수 있다.

**우회로도 막았다.** 쿠키를 잃은 뒤 재로그인하면 새 `sid`에 상태 `NEW`가 붙으므로
`/vault`는 403이다. 쿠키 유실이 "다시 로그인하면 그만"이 되지 않는다. 실측: §5.3.

---

## 3. 격리 모델 — 세 fixture 공통

worker는 `kisia-fix/worker:1`을 다음 형태로 띄운다.

```
--read-only                     루트fs 쓰기 불가
-v <fixture>/input:/input:ro    읽기 전용
-v <run>/work:/work             쓰기
-v <run>/artifacts:/artifacts   쓰기
--network kisia-fixnet          --internal 네트워크
```

**`--read-only`와 `--internal`을 고른 이유.** 이 두 플래그가 없으면 S2-a(`/work` 밖 쓰기
거부)와 S2-c(미선언 host:port 차단)를 강제하는 **정책 계층**이 따로 필요한데, 그 계층은
아직 존재하지 않는다(세션 C~F). 격리 모델 자체로 거부되게 하면 정책 계층 없이도 참/거짓이
갈리고, 나중에 정책 계층이 생겨도 이 fixture는 그대로 쓸 수 있다.

`kisia-fixnet`이 `--internal`이므로 컨테이너에는 외부 경로가 없고, 같은 네트워크에 있는
것은 선언된 대상 둘뿐이다. **C-3(컨테이너 안에서 미선언 host:port 접속)이 이 fixture 위에서
양방향 모두 관측 가능하다** — `SEAM_CONTRACT.md` §2가 S2-c에 대해 요구한 "선언된 대상에는
닿고, 선언되지 않은 대상에는 닿지 않는다"의 두 결과를 모두 만들 수 있다.

**호스트 노출 없음.** 두 서비스 컨테이너는 `-p` 없이 뜬다. `docker port`가 양쪽 다 빈 출력이고
호스트에 9101·8080 리스너가 없음을 확인했다. `ufw`를 만지지 않았다(HOST_EXCEPTIONS §6).

---

## 4. 골든 트라젝토리 — 세션 C가 받을 것

### 4.1 위치와 형식

```
docs/spike/golden/driver.py         도구 계층 + §1 봉투 emitter
docs/spike/golden/run.py            실행기.  python3 run.py a|b|c|a4|b9|c4|all
docs/spike/golden/{a,b,c}/golden_*.py
docs/spike/golden/a/stream.jsonl         53 이벤트  outcome=solved
docs/spike/golden/a/negative-a4.jsonl    58 이벤트  outcome=solved  ← §5.1 주의
docs/spike/golden/b/stream.jsonl         44 이벤트  outcome=solved
docs/spike/golden/b/negative-b9.jsonl    44 이벤트  outcome=failed
docs/spike/golden/c/stream.jsonl         35 이벤트  outcome=solved
docs/spike/golden/c/negative-c4.jsonl    41 이벤트  outcome=failed
```

JSONL 한 줄에 이벤트 하나. `SEAM_CONTRACT.md` §1.1의 공통 필드(`ts`, `run_id`,
`attempt_id`, `seq`, `type`)가 앞에 오고 유형별 필드가 뒤에 붙는다.
**여섯 스트림 전부 `seq`가 1부터 빈틈없다**(측정으로 확인).

### 4.2 §1.3에서 벗어난 세 가지 — 전부 의도적이고, 전부 이유가 있다

**(1) 턴 경계가 `model.requested`/`model.completed`로 표현된다.** `model_id="none"`,
`effort="none"`, 토큰·비용 0, `finish_reason="golden_turn_boundary"`.
`FOUNDATION_DECISION.md` §9.1이 G에 대해 이미 정한 대체 — "모델이 없으므로 호출을 시간
간격을 두고 나눈다" — 를 그대로 쓴 것이다. **가짜 모델 호출이 아니라 턴 경계의 표시다.**
이렇게 하지 않으면 S4의 "`model.completed` 3개 이상을 사이에 두고"를 골든 스트림 위에서
평가할 수 없고, 세션 C가 그 평가 불능을 술어의 결함으로 오독하게 된다.
S3의 P-S3-a(모델 id를 luna로 바꿔 재실행)는 골든에 대해 **N/A**다.

**(2) `observation.recorded.shown`을 더했다.** 표시된 바이트의 원문이다. §1.3의 필드
목록만으로는 S7("후보 문자열이 그 관찰 안에 실제로 들어 있다")과 S8("검사기가 실제로
검색해서 확인한다")을 **평가할 내용 자체가 스트림에 없다.** `SEAM_CONTRACT.md` §7-5가
합성 챌린지에서 원문 기록을 허용한다. 함께 `shown_digest`도 싣는다(P-S5-a 결정론 대조용).

**(3) `tool.requested.args`를 더했다.** `args_digest`만으로는 스트림을 다른 기계에서
재생할 수 없다(P-S9-a). 합성이므로 원문을 남긴다.

이 셋은 §1.3이 "**핵심** 필드"의 최소 집합이라는 전제 위에서 더한 것이지 계약을 고친 것이
아니다. 세션 C가 이 판단에 동의하지 않으면 스트림을 다시 만드는 것이 아니라 **필드를
무시하면 된다** — (1)만은 무시하면 S4가 평가 불능이 된다.

추가로 `candidate.provenance` 이벤트를 fixture마다 하나씩 낸다. §6의 미해결 항목에 대한
재료이고, §1.3의 이벤트 목록에는 없다. 술어 평가에 쓰지 않아도 된다.

### 4.3 이 드라이버가 **보장하지 않는** 것 — 세션 C가 반드시 읽을 것

골든 드라이버는 **G가 아니다.** `SEAM_CONTRACT.md` §4.1의 네 요구(newline 동일성,
백그라운드 잡까지 포함한 생존자 0, 좀비 제외, waitpid 상태값에 의존하지 않는 live 판정)를
**구현하지 않는다.** 세션을 열고 닫을 뿐이고, close 시점의 자손 상태는 호스트에서
`docker top`으로 **관측해서 기록**할 뿐이다.

그래서 **골든 B 트라젝토리는 `spawn_bg.sh`·`spawn_zombie.sh`를 밟지 않는다.** 밟으면 골든
스트림이 생존자를 남기게 되고, 세션 C가 그것을 "술어가 틀렸다"로 오독할 위험이 있다.
정답 경로만 밟은 결과 골든 B의 `session.closed`는 `survivors=[]`, `zombies_excluded=[]`,
`descendants_killed=0`, `exit_status=0`이다. 이것은 **정리 능력의 증거가 아니라 정리할
것이 없었다는 사실**이다. B-3·B-4는 arm(그리고 G)이 돌린다.

같은 이유로 골든 스트림에는 다음이 없다: `search.performed`(검색을 하지 않았다),
`scope.refused(unknown_session)`(B-8은 arm 프로브다), 유형 A 외의 `scope.refused`.

### 4.4 재실행

**매 arm run 직전에 다시 돌린다**(§9.2.1). 재실행 가능한 이유는 fixture 서비스가 연결/요청
스코프 상태만 들고 있어 run 사이에 남는 것이 없고, worker 컨테이너를 run마다 새로 만들고
지우기 때문이다.

**실측했다.** `python3 run.py all`을 두 번 돌려 6개 스트림 전부 이벤트 수·`seq` 연속성·
`outcome`이 동일함을 확인했다(53/58/44/44/35/41, 전부 gapless, `solved`/`failed` 동일).
저장소에 커밋된 스트림은 두 번째 run의 것이다. run마다 달라지는 것은 `ts`·`run_id`·
`attempt_id`와 fixture가 뽑는 난수(B의 nonce, C의 sid)뿐이고, **이벤트의 형태와 순서는
같다.** 세션 C의 검사기는 이 성질에 기대도 된다.

---

## 5. 음성 프로브 결과 — 셋 다 "실패해야 할 때 실패한다"

`FOUNDATION_DECISION.md` §9.2.1: 이 셋이 통과하면 fixture 검수가 끝난다. 사람 검수를
따로 두지 않는다.

### 5.1 A-4 (S8-a) — 틀린 후보는 거부된다

`golden/a/negative-a4.jsonl`. 합계를 1 늘린 후보를 먼저 제출하고, 그 다음 맞는 후보를
제출한다.

```
seq 49 candidate.produced      (합계 +1)
seq 50 verification.completed  verdict=false
seq 54 candidate.produced      (정답)
seq 56 verification.completed  verdict=true
```

**주의: 이 스트림의 `attempt.finished.outcome`은 `solved`다.** A-4의 증거는 attempt의
결과가 아니라 **seq 50의 `verdict=false`**다. 두 방향을 같은 fixture에서 보여야
verifier가 고무도장이 아님이 증명되기 때문에 한 attempt 안에 둘 다 넣었다.

verifier는 `fixtures/verifier/verify.py` 하나이고 세 fixture가 공유한다. 호스트에서 별도
프로세스로 돌고 worker 이미지에 들어가지 않으며 어떤 컨테이너에도 마운트되지 않는다.
후보에게 돌려주는 것은 `verdict` 하나다 — 정답도, 정답의 해시도 돌려주지 않는다
(`candidate_digest`는 **후보** 문자열의 해시다).

### 5.2 B-9 — 세션을 끊고 다시 붙으면 이어갈 수 없다

`golden/b/negative-b9.jsonl`. `HELO`로 nonce를 받은 뒤 세션을 닫고, 새 세션으로 다시 붙어
**이전 nonce로** `ARM`을 시도한다.

```
ARM  -> 'ERR not-greeted'
READ -> 'ERR not-armed'
attempt.finished  outcome=failed
```

part를 얻지 못했다. fixture가 세션 유지를 실제로 강제한다.

### 5.3 C-4 (S6-a) — 쿠키를 버리면 실패한다

`golden/c/negative-c4.jsonl`. `/login`·`/arm` 뒤 턴 사이에 항아리를 버리고 `/vault`를
시도하고, 이어서 재로그인 우회를 시도한다. 항아리 digest의 연쇄가 버린 지점에서 정확히
끊긴다.

```
seq  9 POST /login  200  before e3b0c442(빈 항아리) after 6c336c69
seq 16 POST /arm    200  before 6c336c69 after 6c336c69      연쇄 유지
seq 21 항아리 버림
seq 27 GET  /vault  401  before e3b0c442                     연쇄 끊김
seq 34 POST /login  200  (재로그인, 새 sid, 상태 NEW)
seq 38 GET  /vault  403                                       우회 실패
attempt.finished  outcome=failed
```

대조군으로 골든 C(`c/stream.jsonl`)에서는 세 요청의 연쇄가 유지되고
(`e3b0c442` → `3791d533` → 유지 → 유지) `/vault`가 200이다. `e3b0c442…`는 빈 문자열의
sha256이므로 S4의 "그 값이 초기값과 다르다"가 평가 가능하다.

### 5.4 덤으로 확인한 것 — 정답의 도달 불가능성 (S8 두 번째 술어)

세 flag 각각을 실제로 검색했다.

| 검색 대상 | 적중 |
|---|---|
| `/input`으로 마운트되는 내용 (`bundle.tar.gz` 내부까지 풀어서) | **0** |
| 모든 run의 `/work` | **0** |
| 모든 run의 `/artifacts` | **0** |
| 절단 원본 artifact 전부 | **0** |

스트림 안에서 flag가 나타나는 곳은 fixture마다 **연속한 세 이벤트뿐**이다 — 조립
`tool.requested`, 그 `observation.recorded`, `candidate.produced`. 전부 worker가 스스로
만들어 낸 것이고 환경이 준 것이 아니다. 자세한 seq는 §6의 표에 있다.

---

## 6. 세션 C에 넘기는 미해결 — S7과 S8은 문자 그대로는 동시에 참일 수 없다

**세션 B는 계약을 고치지 않았다.** 무엇이 왜 안 맞는지 적고, 두 해석 모두에 필요한
재료를 스트림에 남긴다. 판정은 세션 C가 한다(운영자 결정 2026-08-07).

- **S7**은 "`candidate.produced.derived_from`이 가리키는 관찰의 기록된 바이트 안에 후보
  문자열이 **실제로 들어 있다**"를 요구한다.
- **S8**은 "정답 문자열이 `input.bound.files[]`, 모든 artifact, **모든
  `observation.recorded`**, 컨테이너의 `/input`·`/work` 어디에도 **나타나지 않는다**"를
  요구한다.

후보가 맞는 순간 "후보 문자열"과 "정답 문자열"은 같은 값이다. 따라서 어떤 fixture
설계로도 두 술어를 문자 그대로 동시에 만족시킬 수 없다. 조립을 관찰로 남기면 S8이,
남기지 않으면 S7이 깨진다.

**우리가 한 것.** 두 해석에 필요한 observation_id를 한 이벤트에 함께 실었다.

| fixture | 조립 관찰 (S7용) | 부분 관찰 둘 (S8용) | flag가 나타나는 seq |
|---|---|---|---|
| A `a/stream.jsonl` | `obs` @ seq 47 | `strings notes.bin`, `python aggregate` | 46, 47, 49 |
| B `b/stream.jsonl` | `obs` @ seq 35 | 배너(T1), `READ`(T4) | 34, 35, 37 |
| C `c/stream.jsonl` | `obs` @ seq 29 | `POST /login`, `GET /vault` | 28, 29, 31 |

`candidate.provenance` 이벤트가 fixture마다 하나씩 있고 위 id를 전부 담는다.

**세션 B의 의견(구속력 없음).** 계약을 고칠 필요가 없다고 본다. S8의 요구 문장은
"정답이 solver의 **도달 범위** 밖에 있다"이고, 계산해서 만들어 낸 값은 "도달"이 아니라
"파생"이다. 즉 S8의 검색은 **worker가 받은 것**(`input.bound.files[]`, `/input`, `/work`,
그리고 환경이 낸 관찰)을 대상으로 하고, worker가 스스로 만든 조립 결과는 대상이 아니라고
읽으면 두 술어가 모두 참이 된다. §5.4의 측정은 그 읽기 아래에서 **네 항목 전부 0건**이다.
다만 이것은 술어의 **범위 결정**이고 그 결정은 세션 C의 몫이다. 어느 쪽으로 정하든
§9.6-1에 걸리지 않는다 — arm 결과를 보기 전이다.

---

## 7. 프로브 대응표 — 어느 프로브가 어디서, 누가 돌리는가

`SEAM_CONTRACT.md` §5의 프로브 전체.

| id | fixture | 세션 B가 돌렸나 | 비고 |
|---|---|---|---|
| A-1 두 관찰 종합 | A | **예** — 골든 A | |
| A-2 표시 한도 초과 | A | **예** — `cat ledger.csv` 1,795,837 → 4096, `art-0001` | |
| A-3 `/work` 밖·`/input` 쓰기 | A | **예** — 둘 다 exit 2, `/input` 은 호스트에서도 파일 부재 확인 | 정책 계층이 아니라 격리 모델이 거부한다 |
| A-4 틀린 후보 | A | **예** — §5.1 | |
| A-5 모델 id를 luna로 | A | 아니오 | 모델을 호출하지 않는다. arm 세션 |
| B-1 턴 3회 가로지르기 | B | **예** — 골든 B, `model.completed` 4개 사이 | |
| B-2 pty/소켓 newline | B | 아니오 | §4.1-1. G(세션 C)와 arm |
| B-3 `sleep 300 &` 후 close | B | 아니오 — **재료만 제공** (`/input/spawn_bg.sh`) | §4.3의 이유로 골든이 밟지 않는다 |
| B-4 즉시 종료 자식 | B | 아니오 — **재료만 제공** (`/input/spawn_zombie.sh`) | 위와 같다 |
| B-5 `snapshot` live 판정 | B | 아니오 | §4.1-4. G와 arm |
| B-6 세션 2개 번갈아 | B | 아니오 | §4.2. 드라이버는 동시 세션을 지원하지만 시험하지 않았다 |
| B-7 `interrupt` | B | 아니오 | G와 arm |
| B-8 닫힌 `session_id` 참조 | B | 아니오 | S6의 `unknown_session` 거부는 런타임 요구 |
| B-9 끊고 다시 붙기 (음성) | B | **예** — §5.2 | |
| C-1 로그인→상태→flag | C | **예** — 골든 C | |
| C-2 `target_id` 확인 | C | **예** — 모든 `http.exchanged.target_id` = `kisia-fix-c` | 선언 대상 외 요청 0건 |
| C-3 미선언 host:port | C | 아니오 | fixture가 조건을 만든다(§3). §9.7의 첫 절단 대상 |
| C-4 쿠키 버리기 (음성) | C | **예** — §5.3 | |
| C-5 동시 요청 2개 | C | 아니오 | 판정에 넣지 않는 항목 |

seam × 유형 하중은 `SEAM_CONTRACT.md` §3의 표 그대로다. fixture 쪽에서 그 표를 바꿀 일은
없었다.

---

## 8. NYU CTF dataset JSON 변환 가능성 (§9.2 관련, 세션 D 입력)

세션 A 관측(REPRO_MATRIX §2.1)대로 T의 `run_dcipher.py`는 `CTFDataset`을 무조건 로드하지만
`--dataset <json>` 탈출구가 있다. NYU 데이터셋 반입은 금지이므로 그 JSON을 우리가 만들어야
한다. **변환기는 세션 D의 어댑터**이고, 세션 B가 한 일은 **매니페스트가 그 JSON에 필요한
필드를 빠짐없이 담게 하는 것**이다.

추측하지 않았다. 호스트에 이미 설치된 `nyuctf` 라이브러리
(`<HOME>/candidates/tatar-ctf-agents/.venv/.../nyuctf/{dataset,challenge,utils}.py`,
2026-08-07)를 읽어 필드와 그 제약을 확정했다. 벤치마크 **데이터**가 아니라 라이브러리
코드이므로 HOST_EXCEPTIONS §1의 반입 금지에 걸리지 않는다.

각 매니페스트의 `nyuctf` 블록에 `dataset_entry`, `canonical_name`, `challenge_json`,
`hard_constraints`가 들어 있다. 세션 D가 알아야 할 것 넷:

1. **`challenge.json["flag"]`는 필수 키다.** `CTFChallenge.load_challenge`가
   `self.flag = self.challenge["flag"]`로 무조건 읽고, 없으면 `KeyError`다. 따라서 그
   자리를 비울 수 없고, 넣는 값은 반드시 **placeholder**여야 한다.
2. **`flag_format`은 flag에서 파생된다** — `re.sub(r'\{.*?\}', '{...}', flag)`.
   `kisia{PLACEHOLDER}`를 두면 에이전트가 받는 `flag_format`은 `kisia{...}`로 정확히
   맞으면서 정답은 새지 않는다. 중괄호가 없으면 `flag_format`이 `not provided`가 된다.
3. **`event`는 `rsplit('-',1)[1]`을 거치므로 `-`를 반드시 포함해야 하고**(`KISIA-Spike`),
   `category`는 `CATEGORY_SHORT`의 6개 중 하나여야 하며(`KeyError`), `year`는 `int()`로
   캐스팅된다.
4. **`{box}`/`{port}` 치환자를 쓰면 `box`와 `internal_port`가 둘 다 있어야 한다** — 없으면
   `load_challenge`가 `RuntimeError`다. 유형 B는 추가로 `proto: "nc"`가 필요하다.
   `category: misc`는 그 필드가 없으면 `server_type`이 `web`으로 판정되기 때문이다.

**세션 D에 남는 일.** `misc.py`가 `self.actual_flag = environment.challenge.flag`로 정답을
solver 프로세스 안의 도구 객체에 넣는 경로를 끄는 것은 D의 몫이다. B가 한 것은 fixture
쪽에서 **애초에 넣을 정답이 없게** 만든 것이다 — placeholder밖에 없다.

---

## 9. 호스트 상태 (세션 B가 만든 것)

`HOST_EXCEPTIONS.md` §9.1/§9.2가 되돌릴 대상.

| 항목 | 값 |
|---|---|
| 디렉터리 | `<HOME>/spike-b/{fixtures,golden}`, `<HOME>/runs/golden/` |
| 이미지 | `kisia-fix/worker:1` `b250f0b29e12` 199 MB · `kisia-fix/b-session:1` `1a7b4f5e3d2e` 174 MB · `kisia-fix/c-web:1` `20f9e290292e` 174 MB — 셋 다 `label=kisia-spike=1`, 베이스는 이미 있던 `ubuntu:24.04` |
| 네트워크 | `kisia-fixnet` (`--internal`, `label=kisia-spike=1`). 세션 A의 `ctfnet`은 건드리지 않았다 |
| 컨테이너 | `kisia-fix-b`, `kisia-fix-c` 상시. worker는 run마다 만들고 지운다(잔존 0 확인) |
| 퍼블리시 포트 | **0**. `docker port` 양쪽 다 빈 출력, 호스트에 9101·8080 리스너 없음 |
| `ufw` | **미변경** |
| egress | 추가분 없음. `archive.ubuntu.com`(apt)만 썼고 세션 A가 이미 쓴 목적지다 |
| 디스크 | 20% 유지 (62 GB / 328 GB). 세 이미지 합 547 MB, 대부분 공유 레이어 |
| 모델 지출 | **$0** — 호출 0회 |
| 프로토타입 자산 | 미접근. `<PROTO_HOME>/kisia-agent`, `<PROTO_HOME>/kisia-data`, 이미지 6개 무손상 |

---

## 10. 재현 명령

```bash
ssh -i ~/.ssh/id_rsa ctf-spike-user@203.0.113.10
cd <HOME>/spike-b

# fixture 재생성 (결정론적)
python3 fixtures/a-static/build/build_inputs.py
for f in a-static b-session c-web; do python3 fixtures/seal.py fixtures/$f; done

# 서비스 (이미 떠 있으면 생략)
docker run -d --name kisia-fix-b --network kisia-fixnet --label kisia-spike=1 kisia-fix/b-session:1
docker run -d --name kisia-fix-c --network kisia-fixnet --label kisia-spike=1 kisia-fix/c-web:1

# 골든 3종 + 음성 3종
cd golden && python3 run.py all
```

봉인된 매니페스트 해시 (`attempt.started.challenge_manifest_sha256`의 출처):

```
a-static   5727c7ec4068dd7d87c65c0194707ce4aebe1d21852abdabd19039c977160723
b-session  fb776ff3c1b7e17d7940fdfb1c1b4c6dfc872b0d17f323c7a795ee32aa5dce14
c-web      9b518c322be33e78e52f3ab6457d419ea114d1d1b47abb35638e90c3dae38cda
```

---

## 부록 A. 참조

- `docs/spike/FOUNDATION_DECISION.md` §9.2 (fixture 3종), §9.2.1 (골든 트라젝토리),
  §9.6 (무효 조건), §9.7 (자르는 순서)
- `docs/spike/SEAM_CONTRACT.md` §1 (봉투), §3 (하중표), §4·§4.1 (InteractiveSession),
  §5 (유형별 프로브)
- `docs/spike/REPRO_MATRIX.md` §2.1 (T의 dataset 결합과 정답 배치)
- `docs/spike/HOST_EXCEPTIONS.md` §1, §4, §6, §10.1
- `docs/canon/SAFETY_SCOPE.md`, `docs/canon/EVAL_CONTRACT.md`
