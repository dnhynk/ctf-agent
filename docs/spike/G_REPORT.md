# G_REPORT — greenfield 참조 구현, 유형 B 프로브 B-1~B-8

스파이크 세션 C, 2026-08-07. `SEAM_CONTRACT.md` §4 `InteractiveSession` 계약의 참조 구현과
그 위에서 돌린 유형 B 프로브 여덟 개의 결과다.

**G가 무엇인가.** `FOUNDATION_DECISION.md` §7.2·§9.1이 정한 대로 **§4 계약의 참조 구현이지
전체 러너가 아니다.** OSS 코드를 포함하지 않는다. agent loop이 없다. 모델을 호출하지 않는다
(**지출 $0**). 유형 A·C의 arm으로 서지 않는다.

**결과 한 줄.** B-1~B-8 여덟 개 전부 통과, §4.2 동시성 통과, 구조 패치 0개. 검사기가 G의
스트림에 대해 유형 B의 하중표 ● 칸 **7/7 PASS**를 낸다.

---

## 1. 산출물

```
docs/spike/g-reference/session.py        §4 의 6개 연산 + §4.1 네 요구 + §4.2 동시성
docs/spike/g-reference/telemetry.py      §1 봉투 emitter (새로 씀, §2)
docs/spike/g-reference/run_b_probes.py   B-1~B-8 실행기 + answer.sweep 참조 구현
docs/spike/g-reference/b/stream.jsonl    G 의 이벤트 스트림 87 이벤트 outcome=solved
```

재현:

```bash
ssh -i ~/.ssh/id_rsa ctf-spike-user@203.0.113.10
cd <HOME>/spike-c/g-reference && python3 run_b_probes.py --out b-stream.jsonl
# 판정
python3 docs/spike/checker/checker.py --pricing config/pricing.openai.yaml \
        docs/spike/g-reference/b/stream.jsonl
```

두 종류의 세션을 **서로 다른 전송 계층**으로 구현했다. 같은 전송을 두 이름으로 부르면
§4.1-1(newline이 세션 종류와 무관하게 지켜진다)이 공허하게 참이 되기 때문이다.

| 종류 | 전송 | tty | 시그널 |
|---|---|---|---|
| `pty` | 호스트 `pty.openpty()` + `docker exec -i -t <worker> …` | 컨테이너 안에 tty, job control | tty의 VINTR(`\x03`) |
| `socket` | 호스트 TCP 소켓 | 없음 | 없음 → `interrupt`는 **명시적 거부** |

---

## 2. `golden/driver.py` 재사용 여부와 그 대가

**재사용하지 않았다. 새로 썼다.**

**이유.** §9.2.1-2는 "골든 궤적을 흘렸을 때 술어가 전부 PASS여야 한다, 아니면 술어가 틀린
것이다"로 검사기를 검증한다. 골든 스트림의 생산자와 G의 생산자가 같으면 그 검증은 같은
코드가 만든 두 출력을 비교하는 것이 되어 독립성을 잃는다. 검사기는 이미 세션 C가 썼으므로
생산자까지 겹치면 남는 독립 관측이 없다.

**대가 — 정직하게.**
- 봉투 emitter 약 90줄이 중복이다(`telemetry.py`). 필드 이름과 `seq` 규칙은 §1과 골든
  스트림의 실제 형태를 보고 맞췄으므로 **완전한 독립은 아니다** — 스키마는 공유하고 코드만
  다르다. 얻은 독립성은 "같은 스키마의 두 독립 구현이 같은 검사기를 통과한다" 수준이고,
  그 이상이 아니다.
- 도구 계층은 어차피 공유할 수 없었다. `driver.py`에는 **pty가 없다**(`docker exec -i`,
  `-t` 없음). B-2는 pty와 소켓 양쪽을 요구하므로 pty 세션·프로세스 트리 정리·`snapshot`은
  어느 쪽을 골랐든 새로 써야 했다. 재사용으로 아낄 수 있었던 것은 emitter뿐이었다.

**부수 효과 하나가 실제로 나왔다.** G의 스트림이 검사기의 두 번째 독립 입력이 되어, 골든
스트림만으로는 드러나지 않았던 술어 결함 하나(A-7, 한 글자 `arm_id`)를 잡았다.

---

## 3. B-1 ~ B-8 결과

전부 `g-reference/b/stream.jsonl` 위에서 검사기가 다시 판정할 수 있는 형태로 남겼다.
아래 "관측"은 전부 실행 결과이고 구현 설명이 아니다(§0.1-3).

| id | 결과 | 관측 |
|---|---|---|
| **B-1** 세션을 열고 모델 턴 3회를 가로질러 유지 | **통과** | 세션 `gsess-01`이 턴 1~6을 가로질러 살아 있었다. 검사기 판정: `session.io` seq 10..38 사이 `model.completed` **4개**(≥3). `state.snapshot` turn 2~6의 `live_session_ids`에 `gsess-01`이 계속 있다. 모델 턴은 §9.1의 대체(시간 간격을 둔 호출 셋)를 썼고 `model_id="none"`, `finish_reason="g_turn_boundary"`다 |
| **B-2** 같은 바이트열을 pty와 소켓에 전송 | **통과** | §4.1-1, 아래 §4 |
| **B-3** tty에서 `sleep 300 &` 후 close | **통과** | §4.1-2, 아래 §4 |
| **B-4** 즉시 종료하는 자식 생성 후 close | **통과** | §4.1-3, 아래 §4 |
| **B-5** 상태 0 종료 / 실행 중 프로세스에 `snapshot` | **통과** | §4.1-4, 아래 §4 |
| **B-6** 세션 2개를 번갈아 읽기 | **통과** | 동시 세션 3개 유지. 두 소켓 세션이 fixture에서 **서로 다른 연결 스코프 nonce** `03c811a1` / `671d7a3c`를 받았고, `s1`의 read에 `bravo`가, `s2`의 read에 `alpha`가 나타나지 않았다 — 두 세션의 바이트가 섞이지 않았다 |
| **B-7** 장시간 명령을 `interrupt` | **통과** | `sleep 120`을 tty의 VINTR로 중단한 뒤 다음 명령이 `PROMPT_BACK=130`을 보고했다(130 = 128+SIGINT). 프롬프트가 돌아왔다. 판정에 마커 문자열의 존재를 쓰지 않은 이유: tty가 입력한 명령줄을 **에코**하므로 마커는 실행하지 않아도 한 번 나타난다. 실행 여부를 가르는 것은 종료 코드다 |
| **B-8** 닫힌 `session_id` 참조 | **통과** | 닫힌 `gsess-11`을 참조하자 `ScopeRefused(unknown_session)`. 스트림에 `scope.refused{reason_code:"unknown_session", silently_created_new_session:false}`. **조용히 새 세션을 만들지 않았다** — 이것이 상태 유실을 성공처럼 보이게 만드는 주된 경로다(S6) |

`b/stream.jsonl` 위 검사기 판정:

```
S1 N/A   S2 PASS   S3 N/A   S4 PASS   S5 PASS   S6 PASS   S7 PASS   S8 PASS   S9 PASS
load-table cells: 7/7 PASS
judgment digest: sha256:ab0cbc604793815fb5b39435efd1ff50d31fae7a65170a3ad75192200b9fa70f
```

`attempt.started.structural_patches == []` 이므로 §9.3의 판정은 **PASS**이고 `PASS(patch n)`가
아니다. G는 후보 코드를 고칠 일이 없다 — 후보 코드가 없다.

---

## 4. §4.1의 네 요구 — 요구마다 **관측**

계약은 구현 방법을 지정하지 않고 관측만 지정한다. 아래는 전부 실행 결과다.

### 4.1-1 `newline`은 세션 종류와 무관하게 동일하게 지켜진다 [ev §8.5]

pty 기록기(`stty raw -echo; head -c 20 > /work/pty_rx.bin`)와 소켓 기록기(worker 컨테이너
안의 리스너)에 **같은 호출**로 같은 바이트열을 보내고, 상대가 받은 것을 비교했다.

```
sent            b'KISIA-NEWLINE-PROBE\n'
pty  received   b'KISIA-NEWLINE-PROBE\n'
socket received b'KISIA-NEWLINE-PROBE\n'
equal           True
```

pty 쪽은 `stty raw -echo`로 회선 규율의 자체 변환을 끈 상태에서 쟀다. 그래야 재는 것이
"우리 계층이 newline을 붙였는가"이지 tty의 번역이 아니다. 스트림: `probe.observed{probe:"B-2"}`
+ `observation.recorded` obs-0006.

### 4.1-2 `close` 후 생존자 0, `&`로 띄운 백그라운드 잡 포함 [ev §8.1]

`bash -i`(job control 활성) 세션에서 `/input/spawn_bg.sh`(`sleep 300 &`)를 돌리고 close했다.

```
session_members_at_close       [[69,"bash","S",pgid 69], [83,"sleep","S",pgid 82]]
pgid_only_would_have_killed    [69]              <- 프로세스 그룹만 정리하면 83 을 놓친다
descendants_killed             1
survivors                      []
zombies_excluded               [83]
checked_by                     g-reference/ContainerProbe@host(docker exec /proc)
```

**백그라운드 잡 pid 83은 자기 프로세스 그룹(pgid 82)을 갖는다.** 프로세스 그룹만 정리하는
구현은 리더의 그룹(69)만 죽이고 83을 남긴다 — [ev §8.1]이 실측한 결함이 여기서 재현됐다.
정리 경계를 **커널 세션(sid)**으로 잡아 생존자 0을 얻었다. 확인은 후보 밖에서 했다
(별도 `docker exec`로 컨테이너의 `/proc`을 읽는다, §0.1-3).

### 4.1-3 좀비는 생존자가 아니다 [ev §8.2]

`/input/spawn_zombie.sh`(자식을 fork시키고 거두지 않은 채 sleep)를 돌리고 close했다.

```
zombies_before_close                [204]
survivors                           []
zombies_excluded                    [204]
grace_ms                            2000
grace_used_ms                       369
grace_used_if_zombies_counted_ms    2000      <- 좀비를 생존자로 셌다면 매번 전량 소모
```

**grace 2000ms 중 369ms만 썼다.** 좀비를 생존자로 세는 구현은 정리가 끝난 뒤에도 생존자
집합이 비지 않아 매 close마다 grace를 전부(2000ms) 쓴다 — [ev §8.2]가 "2.00s → 0.05s"로
실측한 것과 같은 현상을 같은 방향으로 재현했다.

*측정 설계 주의.* B-4의 세션 리더는 비대화형 셸이다. `bash -i`는 SIGTERM을 무시하므로
리더가 grace를 전부 쓰고, 그러면 재는 것이 좀비 회계가 아니라 셸의 시그널 처리가 된다.
B-3은 job control이 필요해 `bash -i`를 쓰고(그래서 `grace_used_ms`가 2312ms다), B-4는
필요하지 않다.

### 4.1-4 `snapshot().live`를 waitpid 상태값으로 추론하지 않는다 [ev §8.3]

두 세션에 동시에 `snapshot()`을 걸었다.

| | 실행 중 (`sleep 120`) | 상태 0 종료 (`exit 0`) |
|---|---|---|
| `live` | **true** | **false** |
| `container_state` | `S` | (프로세스 없음) |
| `naive_waitpid_pid` | 0 | 253619 |
| `naive_waitpid_status` | **0** | **0** |
| `naive_live_from_status_only` | false ← **틀렸다** | false |

**두 경우의 waitpid status가 똑같이 0인데 `live`는 다르다.** status만 보는 구현은 살아 있는
프로세스를 "정상 종료(0)"로 읽는다 — 표의 마지막 행이 그 오독을 그대로 보여준다.
`live`는 컨테이너 프로세스 표(존재 + 상태 ≠ `Z`)로 정했다. 스트림:
`probe.observed{probe:"B-5", correct:true}`.

---

## 5. §4.2 동시성

- **동시 세션 2개 이상.** B-6에서 3개를 동시에 유지했고, 상한을 채우는 시험에서 4개까지 갔다.
- **상한이 명시적이다.** `SessionManager(max_sessions=4)`.
- **초과는 거부이고 대기가 아니다.** 5번째 `open`은 **303ms 만에** `ScopeRefused(session_limit)`로
  돌아왔다. 대기·무응답이 아니라 즉시 거부다. 스트림:
  `scope.refused{reason_code:"session_limit", limit:4, elapsed_ms_before_refusal:303}`.
  (303ms는 대기가 아니라 그 직전 `open`들의 소켓 연결에 든 시간이 아니라, 거부 판정까지의
  경과다 — 상한 검사가 연결 시도보다 먼저 일어난다.)
- **두 세션의 `read`가 서로의 바이트를 섞지 않는다.** B-6. 세션마다 전송과 버퍼가 따로다.

부수로 `answer.sweep`(개정 A-3)의 참조 구현을 냈다. G의 run에서 네 표면 전부 **적중 0건**:

```
surfaces  ["input_files","artifacts","container:/input","container:/work"]
hits      0
checked_by  g-reference/run_b_probes@host
```

세션 D는 이것을 러너로 옮긴다 — arm이 아니라 하니스가 내는 이벤트다.

---

## 6. run 세 번과, 그중 하나를 폐기한 이유

| run | 결과 | 무엇이 바뀌었나 |
|---|---|---|
| 1 | B-2·B-4·B-5·B-7 실패 | (a) `open`이 세션 안에 `echo G_LEADER=$$`를 흘려 넣어 B-2의 기록기가 그 바이트를 먼저 받았다 → 리더 pid를 **세션 밖에서**(프로세스 표 diff) 확정하도록 고쳤다. (b) B-4의 리더가 `bash -i`라 SIGTERM을 무시해 grace를 전부 썼다 → 비대화형 셸로. (c) B-7의 판정이 tty 에코를 실행으로 오독했다 → 종료 코드 130으로. (d) `snapshot().live`가 리더 pid 부재로 `None`이었다 → (a)와 같은 원인 |
| 2 | B-1~B-8 전부 통과. **검사기는 3/7** | 검사기가 S2.5·S4.4·S8.2b·S6.2를 거짓으로 판정했다. 앞의 셋은 **검사기 결함**(A-7, 한 글자 `arm_id`에 대한 문자 포함 검사), S6.2는 **G의 결함**(세션을 닫으면서 `session.closed`를 내지 않았다) |
| 3 | B-1~B-8 전부 통과. **검사기 7/7** | 남은 G 결함 하나 더: 상한 시험용으로 연 세션에 `session.opened`를 내지 않아, 뒤의 `session.closed`가 열린 적 없는 세션을 가리켰다(검사기 S6.3이 잡았다) |

**run 2의 결과는 폐기했다.** A-7은 G의 결과를 본 뒤에 고친 술어이므로 §9.6-1에 따라 그
run의 결과는 무효다. 개정된 술어 아래에서 다시 돌린 run 3이 기록에 남는 판정이다.
A-7을 고칠 수밖에 없었던 이유와 그것이 arm 하나를 살리는 개정이 아닌 이유는
`CHECKER.md` §4.1에 있다.

**부수 소득.** 검사기가 G의 텔레메트리 결손을 **두 건** 잡았다 — 둘 다 "연산은 했는데
이벤트를 내지 않았다"는 같은 형태다. 이것이 검사기가 실제로 무언가를 잡는다는 첫 증거이고,
세션 D가 arm 어댑터를 쓸 때 가장 먼저 걸릴 곳이기도 하다(`CHECKER.md` §8-10).

---

## 7. 작성 시간 — §9.4가 요구하고 §10.2의 우발 조항이 쓰는 값

**추정이 아니라 실측이다.**

| 구간 | 시각(UTC) | 소요 |
|---|---|---|
| 착수 (첫 줄) | 2026-08-07T12:45:32Z | |
| B-1~B-8 전부 통과 (run 2) | 2026-08-07T12:54:48Z | **9분 16초** |
| 검사기가 7/7 PASS (run 3, 계약 개정 반영) | 2026-08-07T~12:59:20Z | **약 13분 50초** |

**§10.2가 쓸 값은 뒤쪽(약 14분)이다.** 앞의 값은 "프로브가 통과한다"까지이고, 뒤의 값은
"계약이 요구하는 텔레메트리까지 갖춰 검사기가 통과시킨다"까지다. E의 구조 패치 작성 시간과
비교할 때 같은 범위여야 하므로 뒤쪽을 쓴다.

**이 값에 포함된 것:** `session.py`(6개 연산 + §4.1 넷 + §4.2), `telemetry.py`(봉투 emitter),
`run_b_probes.py`(B-1~B-8 + `answer.sweep`), run 3회와 그 사이의 진단·수정.

**포함되지 않은 것, 명시.**
- 검사기(`checker.py`) 작성 시간. G와 별개의 산출물이다.
- `SEAM_CONTRACT` 개정 r1 작성 시간.
- 사전 지식의 값. §4.1의 네 요구는 [ev §8]이 **이미 원인까지 규명해 둔** 결함이다. G는
  "커널 세션이 경계다", "좀비를 빼라", "pid를 봐라"를 **찾은 것이 아니라 적용했다.**
  E의 구조 패치도 같은 지식 위에서 이뤄지므로 §10.2의 비교는 이 점에서 공평하지만,
  **"greenfield로 S4/S5/S6를 만드는 데 드는 시간"의 추정치로 이 14분을 쓰면 안 된다.**
  이것은 §4 계약 하나의 참조 구현 시간이지 유형 B 런타임 전체의 구축 시간이 아니다.
- 호스트·fixture 준비(세션 A·B가 이미 해 둔 것).

---

## 8. G가 재지 않은 것

`FOUNDATION_DECISION.md` §9.1이 미리 명시한 대가 그대로다.

- **S6의 loop 절반.** G는 "핸들·쿠키가 호출을 가로질러 살아남는가"(런타임 절반)만 판정하고
  "모델이 매 턴 올바른 상태를 받는가"(loop 절반)는 판정하지 않는다. 결정이 선택지 3으로
  가면 이 절반은 측정되지 않은 위험으로 재빌드에 넘어간다. §12.2의 7번에 기재해야 한다.
- **유형 A·C.** G는 유형 B에서만 arm으로 선다. `b/stream.jsonl`의 S1·S3이 N/A인 것은 그
  때문이다.
- **P-S3-a.** 모델을 호출하지 않으므로 N/A다.
- **라이트업 충분성 (b).** G의 스트림도 `session.io(direction=out)`이 바이트 수만 실어,
  세션에 무엇을 보냈는지가 봉투에 없다. `CHECKER.md` §7.1의 공백 1과 같은 것이다.

---

## 9. 호스트 상태 (세션 C가 더한 것)

| 항목 | 값 |
|---|---|
| 디렉터리 | `<HOME>/spike-c/g-reference/`, `<HOME>/spike-c/checker.py`, `<HOME>/runs/g/` (4 run, 84 KB) |
| 이미지 | **추가분 0.** 세션 B의 `kisia-fix/worker:1`을 그대로 쓴다 |
| 네트워크 | **추가분 0.** `kisia-fixnet` 그대로 |
| 컨테이너 | worker는 run마다 만들고 `--rm`으로 지운다(잔존 0 확인). 상시 기동은 세션 B의 `kisia-fix-b`·`kisia-fix-c` 둘 그대로 |
| 퍼블리시 포트 | **0.** B-2의 소켓 기록기는 worker 컨테이너 안에서만 listen하고 `kisia-fixnet` 안에서만 닿는다. `-p` 없음 |
| `ufw` | **미변경** |
| egress 추가분 | **0.** 컨테이너는 `--internal` 네트워크라 외부 경로가 없다(§6의 실측) |
| 디스크 | 20% 유지 (63 GB / 328 GB). 세션 B와 동일 |
| 모델 지출 | **$0** — 호출 0회 |
| 프로토타입 자산 | 미접근. `<PROTO_HOME>/kisia-agent`, `<PROTO_HOME>/kisia-data` 읽지도 쓰지도 않았다 |

---

## 부록 A. 참조

- `docs/spike/SEAM_CONTRACT.md` (개정 r1) §4 (`InteractiveSession`), §4.1 (네 요구),
  §4.2 (동시성), §5 (유형 B 프로브)
- `docs/spike/CHECKER.md` — 검사기, 골든 판정, S7/S8 판정, 개정 r1의 근거
- `docs/spike/FOUNDATION_DECISION.md` §7.2 (G의 범위), §9.1 (G가 다르게 도는 이유와 대가),
  §9.4 (기록 항목), §10.2 (우발 조항이 쓰는 시간값)
- `docs/evidence/2026-08-07-phase-b-evidence.md` §8 — §4.1 네 요구의 출처
