# ARM_E_REPORT — EnIGMA / SWE-agent v0.7.0, 유형 A·B·C

스파이크 세션 E(유형 A)와 **세션 E-2(유형 B·C)**, 2026-08-07.
`FOUNDATION_DECISION.md` §9.4 가 요구하는 기록과 seam 별 판정·근거 seq·패치 분류가 여기 있다.

> **세션 E-2 가 이 문서에 한 편집.** §0 을 **실측값으로 대체**했고(그것이 이 세션의 핵심
> 산출물이다), §12~§18 을 새로 더했다. **유형 A 의 절(§1~§11)은 고치지 않았다** — 제목과
> 이 머리말만 문서 범위가 넓어진 것을 반영해 고쳤고, 유형 A 의 사실·판정·수치는 한 글자도
> 바꾸지 않았다. 유형 A 판정표를 다시 돌려 확인한 결과는 §16.3 에 있다.

**이 세션이 한 것.** §4-0 의 네 질문에 소스 근거로 답하고 그것을 **run 전에 커밋**했다
(`arms/E/PREREG.md`, 커밋 `f82bafc`). E 용 어댑터 일체(투입 변환기·workspace 선점·계측
shim·러너·봉투 조립기), 구조 패치 **E-05** 하나와 사소 패치 **E-04·E-06**, ADR-0001
capability probe(E 의 요청 모양), **유형 A run 9회**(기록 2 · 보조 1 · 폐기 6)와 집합 판정.

**이 세션이 하지 않은 것 — 명시한다.** **유형 B 와 유형 C 를 돌리지 않았다.** 따라서
**§10.2 우발 조항이 쓰는 시간값을 이 세션은 만들지 못했다**(§0 이 그 사실과 이유를 적는다).
세션 D 가 유형 A 를 끝내고 B·C 를 D-2 로 넘긴 것과 같은 분할이고, **세션 E-2 가 이어받는다**
(§11).

**고치지 않은 것.** `SEAM_CONTRACT`, fixture, 골든 스트림, 골든 드라이버, 검사기 술어,
canon 문서, **후보의 프롬프트.**

**실측 지출 $0.1010.** 누적(세션 A·D·D-2 포함) **$1.31 미만**. 상한 $150.

**키 검색 적중 0건.** **매 run 후**에 돌았다 — `adapter/post_run.sh` 가 봉투 조립·검사기·키
검색·비용 대조를 한 스크립트로 묶어 run 직후에 호출한다. 세션 D-2 가 묶음 단위로 돌아
보고서에 그 사실을 적어야 했던 자리를 이렇게 닫았다. 대상은 매번 **그 run 디렉터리와
`<HOME>` 전체** 둘 다이고, 5개 유효 run 전부 `run_dir_hits=0 home_spike_hits=0` 이다.

---

## 0. §10.2 우발 조항이 쓰는 시간 — **실측했다**

세션 E 는 이 값을 만들지 못했다(유형 B 를 돌리지 않았으므로 비교의 한쪽 항이 없었다).
**세션 E-2 가 실측으로 채운다.** 추정이 아니다.

조항의 문면은 이렇다.

> 선택지 2와 3이 함께 생존했고, **유형 B의 세션 런타임이라는 동일 범위에서** G의 참조 구현
> 작성 시간이 E의 구조 패치 작성 시간보다 작으면, 3이 2보다 앞선다.

### 0.1 두 값

| | 착수 (첫 줄) | 종점 | 소요 |
|---|---|---|---|
| **(i)** §4.1·§4.2 프로브가 최종 관측값에 도달 | 2026-08-07T16:47:05Z | 2026-08-07T17:23:12Z | **36분 07초** |
| **(ii)** 검사기가 세션 스트림을 통과 | 2026-08-07T16:47:05Z | 2026-08-07T17:36:12Z | **49분 07초** |
| (참고) 소스 연구 구간까지 포함 | 2026-08-07T16:43:21Z | 2026-08-07T17:36:12Z | 52분 51초 |

**§10.2 에 넣는 값은 (ii) 의 49분 07초다.** G 의 대응값은 **약 13분 50초**(`G_REPORT.md`
§7). 시각은 전부 **호스트 UTC** — 워크스테이션 달력은 2026-08-08 을 가리켰으나 앞선 모든
세션(G §7, T §3, E §4)이 호스트 시계로 기록했으므로 비교 가능성을 위해 호스트 시계를 썼다.

**조항의 발동 여부는 판단하지 않는다.** 그것은 §10.1 의 생존 판정 둘이 모두 확정된 뒤
`FOUNDATION_DECISION.md` 를 쓰는 세션의 몫이다. 이 세션은 두 값만 낸다.

### 0.2 종점의 정의가 G 와 글자 그대로 같지 않다 — 그 차이를 먼저 적는다

G 의 두 종점은 "B-1~B-8 **전부** 통과"와 "검사기 **7/7**"이었다. **E 는 둘 다 글자 그대로는
도달할 수 없다.**

- **(i)** E 는 B-6(동시 세션 2개)과 B-7(interrupt 후 프롬프트 복귀)을 통과하지 못한다
  (§12.3). 그래서 (i)의 종점을 "8개 전부 통과"가 아니라 **"프로브가 최종 관측값에 도달한
  시각 — 그 뒤로는 패치도 프로브도 고치지 않았고 값이 재현된다"**로 정의했다.
- **(ii)** 검사기가 유형 B 에서 내는 판정은 **6/7** 이고 남는 FAIL 은 S7 하나다. S7 은
  **세션 계층의 성질이 아니라 trajectory 의 성질**이다 — 유형 A 에서도(§2.2), T 의 세
  유형 전부에서도 같은 칸이 같은 원인으로 터졌다. 그래서 (ii)의 종점을 **"세션 계층이
  책임지는 seam(S2·S4·S5·S6)이 전부 PASS 가 된 시각"**으로 정의했다.

**정의를 바꿨다는 사실 자체가 §10.2 를 읽는 사람에게 필요한 정보다.** 같은 이름의 종점이
두 arm 에서 같은 것을 뜻하지 않으므로, 49분과 13분 50초를 뺄셈해서 쓰지 말고 **각각이
무엇까지 포함하는지를 보고 쓰라**는 것이 이 절의 요지다.

### 0.3 포함한 것과 포함하지 않은 것 (G §7 · T §3 과 같은 형식)

**포함된 것.** §4.1·§4.2 프로브 드라이버(`run_b_probes_E.py`, 후보의 세션 계층을 직접
몰고 생존자·live 를 하니스가 컨테이너 밖에서 확인), **구조 패치 E-07**(세션 close 의 자손
정리, 세 종료 지점), 그 사이의 진단과 수정(프로브 3회 재실행, 어댑터 결함 3건 수정,
유형 B run 6회 중 폐기 2회), 봉투 매핑(`session.*` 이 실제로 흐르게 만든 것).

**포함되지 않은 것 — 명시한다.**

- 세션 E 가 이미 만든 유형 A 어댑터·러너·투입 변환기·shim 의 뼈대. 세션 계측 코드는
  세션 E 가 **써 두었으나 한 번도 행사되지 않았고**(유형 A 에 세션이 없다), 그것을 처음
  돌려 고치는 시간은 포함된다.
- 유형 C 작업(C-4 개입 경로, 항아리 의미 수정)과 A-5/P-S3-a. 범위가 "유형 B 의 세션
  런타임"이므로 뺐다.
- 검사기 작성 시간, `SEAM_CONTRACT` 개정 시간, 호스트·fixture 준비.
- **사전 지식의 값.** §4.1 의 네 요구는 [ev §8]이 이미 원인까지 규명해 둔 결함이고,
  세션 E 가 `PREREG.md` §(a)에서 E 의 세션 소스를 이미 읽어 표로 정리해 두었다. **그
  읽기 시간은 이 값에 없다.** G 도 같은 항목을 뺐으므로 그 점에서는 공평하다.

> **비대칭 하나를 숨기지 않는다.** G 는 자기가 설계한 계층을 썼고 E 는 **남의 계층을 읽어
> 계약 뒤에 놓았다.** 추출(선택지 2)에서 "남의 코드를 읽는 시간"은 실제 비용인데 G 의
> 값에는 대응 항목이 없다. 그래서 소스 연구 구간을 포함한 52분 51초를 **함께** 적었다.
> 어느 값을 쓸지는 §10.2 를 적용하는 세션이 정하되, 두 값이 다 있으므로 고를 수 있다.

### 0.4 그 작업은 구조 패치인가 어댑터인가 — 나뉜다

§0.3 이 요구한 판정이다. **E 가 내지 않는 넷이 서로 다른 칸에 떨어졌다.**

| 계약이 요구하는데 E 가 내지 않는 것 | 어떻게 채웠나 | 분류 | 근거 |
|---|---|---|---|
| `session_id` | shim 이 `InteractiveSession` **객체 하나마다** id 를 붙인다 | **어댑터** | 후보가 이미 들고 있는 객체 동일성을 라벨로 바꾼 것이지 새 사실을 만들지 않는다 |
| `snapshot`(`live`) | 하니스가 컨테이너 프로세스 표를 읽고, 후보의 `poll()` 과 **나란히** 싣는다 | **어댑터** | 관측만 더한다. E 의 행동은 바뀌지 않는다. §0.1-3 이 오히려 이것을 요구한다 |
| `survivors` | 하니스가 컨테이너 밖에서 읽는다 (판정값) | **어댑터** | 위와 같다 |
| `descendants_killed` = 자손을 **실제로 거두는 것** | **구조 패치 E-07** | **구조** | 관측이 아니라 **행동**을 바꾼다. E 는 컨테이너 안을 거두는 코드가 한 줄도 없었다 |
| 동시 세션 2개 | **채우지 않았다** | — | §12.4 가 이유를 적는다. 상태 모델 변경이므로 구조 패치인 것은 맞으나, **어떤 seam 판정도 바꾸지 않아** 쓰지 않기로 판정했다 |

**세션 E 의 예상 하나가 맞고 하나가 틀렸다.** 「`survivors` 는 하니스 관측이라 어댑터일
가능성」은 맞았다. 「동시 세션 2개에 남은 예산 하나가 쓰일 가능성이 높다」는 **틀렸다** —
예산은 거기 쓰이지 않았고, 대신 **아무도 예상하지 않았던 자리**(close 의 자손 정리)에
쓰였다. 그 자리는 §1 (a)의 표에 `descendants_killed`·`survivors` 로 **이미 적혀 있었으나**
"하니스가 재면 되는 값"으로 분류돼 있어 행동 변경이 필요하다는 점이 드러나지 않았다.

---

## 1. §4-0 의 네 질문 — 소스 근거와 함께

전문은 `arms/E/PREREG.md` 에 있고 **run 전에 커밋됐다**. 여기에는 결론과, run 이 그 예상을
어떻게 판정했는지를 싣는다.

### (a) E 에 지속 세션 계층이 있는가 — **있다. 여섯 연산 중 둘만 온전하다**

```
sweagent/agent/interactive_commands.py:20-24   InteractiveSession(name, session_process: Popen)
sweagent/agent/interactive_commands.py:26-41   INTERACTIVE_SESSIONS_CONFIG = {"gdb", "connect"}
sweagent/environment/utils.py:446-456          get_interactive_session -> docker exec -i -w <cwd> <ctr> <cmdline>
sweagent/environment/swe_env.py:210            self.interactive_session: InteractiveSession | None   <- 슬롯 하나
sweagent/environment/swe_env.py:499-588        _handle_interactive_commands  (START/STOP/그 밖)
sweagent/environment/swe_env.py:1067-1117      communicate_session  (send+read 융합)
sweagent/environment/swe_env.py:1475-1488      interrupt_interactive  (pkill -SIGINT ×3)
config/commands/server_connection.sh:17-68     connect_start / connect_sendline / connect_exec / connect_stop
config/commands/_connect.py:22-66              컨테이너 안의 pwntools NetcatShell, prompt "(nc) "
```

| §4 연산 | E 의 대응 | 계약이 요구하는데 **없는** 것 |
|---|---|---|
| `open` | `connect_start`→`START`→`get_interactive_session` | **`session_id` 없음** (식별자가 종류 이름뿐). **배너가 버려진다** — `utils.py:455` 가 `_ = read_with_timeout(...)` |
| `send`/`read` | **융합** — `communicate_session` 하나 | 독립 `read` 없음, `max_bytes` 없음, `closed`·`timed_out` 이 필드가 아니라 관찰 텍스트에 붙는 문구(`swe_env.py:560-565`) |
| `interrupt` | `interrupt_interactive` | **모델이 부를 수 없다** — `TimeoutError` 경로에서만 내부 호출(`swe_env.py:559`). `signal` 인자 없음 |
| `snapshot` | 없음 (`session_process.poll()` 이 최근접) | `live`·`pid`·`seq_high`·`bytes_since_open` 전부. `poll()` 은 컨테이너 안이 아니라 호스트의 `docker exec` 클라이언트를 본다 |
| `close` | `connect_stop`→`STOP`→`terminate()` | `transcript_artifact_id`·`exit_status`·`descendants_killed`·`survivors` 전부 |

**§4.2 동시성 — 상한이 1 이다.** `swe_env.py:210` 이 슬롯 하나이고 둘째 세션은 거부된다
(`swe_env.py:515-520`, `526-527`). 상한이 **명시적이고 거부이며 대기가 아니라는** 점은
§4.2 를 만족하지만, "동시 세션 **2개 이상**"은 만족하지 못한다. **B-6 은 현 상태로
불가능하다.** 전송 계층은 실제로 둘이다(파이프→gdb stdin / 파이프→컨테이너 안
pwntools→TCP)이나 **pty 는 없다** — `docker exec -i` 이고 `-t` 가 없다(`utils.py:451`).

### (b) 프롬프트가 그 계층을 쓰라고 하는가 — **명시적으로 말한다. T 와 정반대다**

**run 전에 적은 예상이다**(`PREREG.md`, 커밋 `f82bafc`). 근거는 넷이 한 방향을 가리킨다:

```
config/ctf/ctf_misc.yaml  IMPORTANT TIPS 2 "make use of the interactive tools supplied to you!"
                                        5 "prefer using the interactive commands supplied to you!"
                                        8 "Interactive commands are only available through the
                                           commands supplied to you at the beginning - make use of them!"
config/ctf/ctf_misc.yaml  blocklist: [..., gdb]        -> gdb 를 막아 debug_start 로 몰아넣는다
config/ctf/ctf_misc.yaml  next_step_template           -> "(Interactive session: {...})" 를 **매 턴** 싣는다
sweagent/environment/utils.py:748-760  set_server_description()
    category ∈ {web,misc} 이고 proto != "nc" -> "... using `curl http://{host}:{port}`."
    그 외 (= 우리 b-session: misc + nc)      -> "... using `connect_start {host} {port}`."
```

우리 유형 B 매니페스트가 `category: misc` + `proto: "nc"` 이므로(`FIXTURES.md` §8-4)
**E 가 모델에게 주는 문장에 문자 그대로 `connect_start kisia-fix-b 9101` 이 들어간다.**
T 의 executor 프롬프트가 "네트워크 서비스는 pwntools 한 방짜리 스크립트로 다뤄라"라고
지시해 유형 B 를 가른 것(`ARM_T_REPORT.md` §1.4.1)과 **정확히 반대 방향**이다.

**예상 세 가지를 그대로 남긴다** (판정은 세션 E-2 의 몫이다):
1. 유형 B — 모델이 세션을 연다(T 는 4 run 0회).
2. 유형 C — 모델이 `curl` 을 쓰지만, E 의 파서가 턴마다 코드블록 하나만 받으므로 T 의
   `c2`·`c3` 처럼 `curl && curl && curl` 로 몰기 어렵고 **항아리 연쇄가 관측될 가능성이 높다**.
3. 가장 큰 위험은 프롬프트가 아니라 **봉투**다 — 모델은 세션을 쓰는데 계약이 요구하는
   사실(`session_id`·`survivors`)이 없는, T 와 **정반대 모양의 실패**.

**유형 A 는 이 예상을 시험하지 않는다.** 유형 A 는 세션을 싣지 않으므로(하중표 S6 빈칸)
(b)의 판정은 세션 E-2 에서만 나온다.

### (c) 격리 모델을 표현하는가 — **후보 스스로는 못 한다. 그러나 패치 없이 세울 수 있다**

```
utils.py:471-485  _get_non_persistent_container   docker run -i --rm -v <abs>:/<basename> ...
                                                  :ro 없음 · --read-only 없음 · --network 없음
utils.py:459-465  _get_container_mounts_list      target 이 /{basename} 으로 강제, 모드는 rw
utils.py:506-536  _get_persistent_container       read_only 인자 없음 · network 인자 없음
swe_env.py:809-815 + utils.py:398-418             docker network connect **ctfnet** (하드코딩)
```

**T-06 과 같은 자리의 결함이고, E 에는 문제가 하나 더 있다** — 호스트의 `ctfnet` 은
`internal=false` 인 bridge 였다(실측 2026-08-07T15:47Z). 그대로 두면 solver 에게 무제한
egress 가 열린다.

**그런데 E 에는 T 에 없던 탈출구가 있다.** `--container_name X` 를 주면 `persistent=True`
가 되고(`swe_env.py:86,167,170`), `_get_persistent_container` 는 **이름이 같은 컨테이너가
이미 있으면 다시 만들지 않고 그대로 쓴다**(`utils.py:510-524`). 하니스가 계약이 요구하는
형태로 컨테이너를 **먼저** 만들면 E 는 거기에 `docker exec` 로 붙는다.

**무과금 스모크로 실측했다**(`adapter/smoke_workspace.py`, 모델 호출 0회):

```
reset: OK  (15.7초)                       <- E 의 환경 초기화가 끝까지 돈다
P-S2-a  /etc/kisia-probe-a   -> rc=1 Read-only file system
P-S2-b  /input/kisia-probe-b -> rc=1 Read-only file system
/work 쓰기 ok · /root/commands 쓰기 ok
선언 대상 kisia-fix-b 해석됨(172.19.0.2) · 미선언 1.1.1.1:80 -> connect_ex 101
networks_after_reset: ctfnet kisia-fixnet   <- ctfnet 은 E 가 스스로 붙였다
```

**패치가 아니라 어댑터로 세는 근거.** 세션 D 가 §4 에 그은 선은 "투명한 관측 래퍼는
어댑터, **행동을 바꾸면** 패치"이고 기준은 코드의 위치가 아니라 무엇이 바뀌느냐다. 여기서
바뀌는 것은 후보 코드도 후보의 제어 흐름도 아니다 — 후보가 **스스로 문서화한**
`container_name` 경로가 설계대로 기존 컨테이너를 재사용할 뿐이다. 세션 A 가 T 의
`--keys <(...)` 에 적용한 판단과 같은 자리다(`REPRO_MATRIX.md` §3).

> **이견의 여지를 남긴다.** 이것을 구조로 세어야 한다고 볼 여지가 있다 — 결과적으로 격리
> 모델이 바뀌기 때문이다. §9.6-3 의 "애매하면 구조로 세고 이유를 적는다"에 따라 **양쪽
> 계수를 함께 싣는다: 이 세션의 판정은 구조 1개(E-05), 반대 해석을 취하면 구조 2개.**
> 어느 쪽이든 예산 3 안이고 유형 A 의 판정표는 바뀌지 않는다.

**세우는 데 필요했던 것 셋 — 전부 실측으로 찾았고, 전부 후보 소스 밖이다.**

| 관측 | 조치 | 분류 |
|---|---|---|
| `docker run -d`(-i -t 없이)면 `bash -l -m` 이 stdin 없이 즉시 끝나 컨테이너가 죽는다 | `-i -t` 추가. E 자신이 쓰는 값이다(`utils.py:530-531`) | 어댑터 |
| 루트fs 가 ro 면 pip 이 user 설치로 넘어가 `/root/.local` 을 만들려다 OSError | `-e PIP_USER=0`. 쓰기 표면을 늘리지 않는 최소 조치 | 어댑터 |
| `swe_env.py:396` 이 **무조건** `pip install flake8` 을 도는데 이미지에 flake8 이 없다 | 이미지에 굽는다 (`sweagent/enigma:spike-kisia`) | **사소 E-04** (packaging) |

**E 가 요구하는 쓰기 표면이 T 보다 넓다 — 숨기지 않는다.** 계약의 `/work`·`/artifacts`
외에 셋이 더 필요했고 전부 `workspace.created.mounts` 에 실려 있다:
`/root/commands`(`swe_env.py:879-887`), `/root/files_to_edit.txt`(`swe_env.py:414`),
`/output`(요약기의 원본 보관소, `summarizer.py:133-137`·`218-219`). **T 에는 이 셋이
필요 없었다.** P-S2-a 가 겨냥하는 `/etc` 는 그대로 거부된다.

### (d) 정답을 solver 프로세스 안에 넣는가 — **넣는다. 그리고 로그로 흘린다**

```
swe_env.py:1169   solution = self.challenge["flag"]          <- agent 프로세스 안
swe_env.py:686    step() 이 그 판정으로 에피소드를 끝낸다
swe_env.py:694    틀리면 "real flag is {self.challenge['flag']}" 를 **로그에 찍는다**
run.py:368        extract_flag_format(challenge["flag"]) -> 프롬프트의 flag_format
```

T-05 와 같은 뿌리, 다른 모양이다.

- **E 가 나은 쪽:** 정답이 **컨테이너 안으로 들어가지 않는다.** 컨테이너 쪽 `submit` 은
  문자열을 되울릴 뿐이다(`config/commands/submit_ctf.sh:9-18`). T 의 `agent.py:33-40`
  ("모델이 말하기만 해도 성공")에 해당하는 두 번째 경로가 E 에는 없다 — 그래서 E-05 는
  파일 **하나**만 만진다(T-05 는 둘).
- **E 가 나쁜 쪽:** 틀린 제출마다 정답을 로그에 쓴다. T 에는 이 경로가 없었다.

**구조 패치 E-05 로 처리했다**(§3.1).

---

## 2. 판정 — E × 유형 A

판정 단위는 스트림 하나가 아니라 **그 유형의 정상 스트림 전부의 집합**이다
(`SEAM_CONTRACT.md` §6 개정 A-8). 세션 D-2 가 유형 B·C 에 쓴 규칙을 그대로 쓴다 — 그래야
T 와 비교된다.

| | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | 계 |
|---|---|---|---|---|---|---|---|---|---|---|
| **E / 유형 A** | PASS(patch 1) | PASS(patch 1) | PASS(patch 1) | PASS(patch 1) | PASS(patch 1) | N/A | **FAIL(S7)** | PASS(patch 1) | PASS(patch 1) | **7/8** |
| 참고 — T / 유형 A | PASS(patch 2) | PASS(patch 2) | PASS(patch 2) | PASS(patch 2) | PASS(patch 2) | N/A | **FAIL(S7)** | PASS(patch 2) | PASS(patch 2) | **7/8** |

```
cd <HOME>/spike-c && python3 checker.py \
    --pricing <HOME>/spike-d/pricing.openai.yaml --set \
    docs/spike/arms/E/streams/E-a-static-20260807T161937Z.jsonl \
    docs/spike/arms/E/streams/E-a-static-20260807T162049Z.jsonl
# judgment digest (스트림별): sha256:8a28b74047f67969bf27563345dbcada4dece8a01314f8d91c050b6c11f02aa2
```

**`patch 1` 은 `attempt.started.structural_patches` 의 길이**이고 검사기가 통제 블록에서
읽는다. **E 는 유형 A 를 T 의 절반 예산으로 통과했다** — 같은 7/8, 같은 FAIL 칸, 구조 패치
2개 대신 1개.

### 2.1 스트림별 판정 — 집합과 다른 곳이 하나뿐이다

| run | 호출 | USD | 입력(캐시) | 출력 | S5 | S7 | 계 | 지위 |
|---|---|---|---|---|---|---|---|---|
| `…161937Z` | 5 | $0.0157 | 50,569 (50,026) | 361 | **F**[no-ev] | **F** | 6/8 | **기록 판정 집합** |
| `…162049Z` | 5 | $0.0159 | 50,581 (50,039) | 377 | **F**[no-ev] | **F** | 6/8 | **기록 판정 집합** |
| **집합 (둘)** | **10** | **$0.0316** | | | **●** | **F** | **7/8** | |
| `…161235Z-p1` | 5 | $0.0380 | 50,479 (40,116) | 340 | F | F | 4/8 | 보조 증거 — 어댑터 결함 3건(§5) |

**S5 가 집합에서 해소된다.** 스트림 하나 안에는 같은 `full_digest` 를 갖는 관찰 쌍이 없어
P-S5-a(결정론)가 `증거 없음` 이지만, 같은 유형의 두 스트림이 같은 바이트를 읽었으므로
집합 위에서는 그것이 곧 "두 번"이다 — 세션 C 가 골든에 대해 쓴 처리와 같다
(`CHECKER.md` §2.1).

### 2.2 FAIL 하나 — 근거 이벤트 seq

| 스트림 | 술어 | 판정 | 근거 seq | 검사기가 적은 이유 |
|---|---|---|---|---|
| `…161937Z` | S7.1 | 거짓 | `[41]` | `candidate.produced.derived_from = null` |
| `…162049Z` | S7.1 | 거짓 | `[41]` | 같다 |

**S7 은 T 와 같은 원인으로, 같은 칸에서 터진다.** 유효한 5 run **전부**에서
`derived_from=null`, `method="model_message"` 다. 모델이 `strings` 결과의 `<tag>` 와
python 으로 계산한 `<sum>` 을 **자기 메시지 안에서** 조립해 제출했고, 어떤 관찰의 바이트
안에도 완성된 후보 문자열이 없다.

**어댑터 결함이 아님을 확인했다.** S7 의 술어는 "그 관찰의 기록된 바이트 **또는 그
artifact**"를 허용한다. 두 기록 run 모두 **절단된 관찰이 0건이고 artifact 가 0개**이며
(`truncated` 전부 false), 따라서 뒤지지 못한 바이트가 존재하지 않는다. `shown` 에는
관찰 원문이 그대로 실려 있다(§7-5 가 합성 챌린지에 허용한 형태).

**S8 은 PASS 다 — 그리고 T 와 갈린다.** 세션 D 가 "유효한 5 run 중 S7 과 S8 을 동시에
만족시킨 것은 0건"이라고 적은 그 긴장이(`ARM_T_REPORT.md` §1.1) E 의 유형 A 에서도
유지된다: **모델이 머릿속에서 조립하면 S7 이 깨지고 S8 은 공허참으로 만족한다.**
E 의 5 run 전부가 그 모양이다. `candidate.provenance` 는 어댑터가 내지만, 정답을 담은
관찰이 애초에 없으므로 조립 면제가 발동할 일이 없었다.

> **계약 관측 — 세션 D 의 것과 같고, arm 을 바꿔도 유지된다.** S7 과 S8(i)는 arm 의
> trajectory 가 3단계일 때만 동시에 참이 될 수 있다. **T 와 E 가 서로 다른 하니스인데
> 유형 A 에서 같은 칸이 같은 이유로 터졌다** — 이 seam 쌍이 재는 것이 배관이 아니라
> 모델의 선택이라는 §1.1 의 관측을 **두 번째 arm 이 독립적으로 재현했다.**
> 계약은 얼었으므로 고치지 않고 보고만 한다(§9.6-1).

### 2.3 PASS 여섯 — 무엇이 실제로 관측됐나

| seam | 근거 |
|---|---|
| **S1** | `input.bound` 1회, 첫 `model.requested`·첫 `tool.requested` 보다 앞(seq 2/10/13). `files[]` 에 path·sha256·bytes. `structural_patches_for_intake=0` — 투입에 쓴 것은 `challenge.json` 변환기 하나이고 어댑터다 |
| **S2** | `workspace.created` 가 mounts 7개를 모드와, network 를 이름과 함께 기록. **P-S2-a**: 컨테이너 안 `/etc` 쓰기 → rc=1 `Read-only file system`, 호스트 `docker diff` 로 부재 확인. **P-S2-b**: `/input` 쓰기 → rc=1, bind-mount 원본 stat 으로 부재 확인. `surviving_processes=0`, `checked_by=kisia-runner/ReapProbe@host(...)` |
| **S3** | `model.requested` 5건 전부에 짝이 되는 `model.completed`. 기록 토큰과 pricing 계산값이 `usd` 와 정확히 일치. 272K 초과 0건. `cache_write_source` 전부 `"reported"` |
| **S4** | 모든 `tool.completed` 에 정수 exit code(`self.returncode`)와 실재하는 `observation_id` |
| **S5** | 집합 위에서 P-S5-a 만족(§2.1). **절단은 한 번도 일어나지 않았다** — §2.4 |
| **S8** | verifier 가 unix 소켓 뒤 별도 데몬. P-S8-a 가 `verdict=false`(seq 7·8), 뒤이어 실제 제출이 `verdict=true`(seq 38) — 고무도장이 아님을 양방향으로 보인다. `answer.sweep` 네 표면 전부 적중 0 |
| **S9** | 통제 블록 16개 전부, `seq` 1부터 빈틈없음, 모든 `*.requested` 에 짝. 판정 digest 재현 가능 |

### 2.4 PASS 지만 약한 칸 — 명시한다

**S5 의 절단 경로가 한 번도 행사되지 않았다.** fixture 는 1.8 MB `ledger.csv` 로 절단을
필연으로 만들려 했지만(`FIXTURES.md` §2.1), **5 run 전부에서 모델이 파일을 덤프하지 않고
python 으로 처리해 E 의 표시 한도를 한 번도 넘지 않았다.** 그래서 S5.1·S5.2 는 공허참이고,
S5.4 를 만족시킨 digest 쌍은 큰 파일의 재독이 아니다. E 의 요약기는 **한 번도 발동하지
않았다** — 후보 자신의 기록에도 `summarizer.model_stats.api_calls = 0` 이다.

**T 에서 관측된 것과 같은 현상이고**(`ARM_T_REPORT.md` §1.3), 이제 **두 arm 에서 재현됐다.**
"표시 한도를 넘는 파일을 넣는다"는 `cat` 하는 에이전트를 가정하는데, 도구를 쓰는
에이전트에게는 절단이 강제되지 않는다. fixture 결함 주장이 아니라 fixture 가 잡지 못하는
경우의 기록이다(§9.2.1 "잃는 것").

**표시 한도 값이 fixture 선언과 다르고, 단위마저 다르다.** 매니페스트는 **4096 바이트**,
T 는 25,000자, **E 는 105줄**이다(`summarizer.py:23`·`129`·`209`). `SEAM_CONTRACT.md`
§7-6 이 "값 자체는 arm 마다 다를 수 있고, 다르다는 사실을 기록한다"고 허용한 항목이지만,
**E 는 값이 아니라 단위가 다르다**(바이트가 아니라 줄). 기록한다.

**E 의 절단은 절단이 아니라 요약이다.** 한도를 넘으면 E 는 원본을 컨테이너의
`/output/<slug>` 에 파일로 올리고 **모델을 한 번 더 불러** 요약한 것을 보여 준다
(`summarizer.py:205-233`). 즉 S5 의 "잘린 원본이 남는다"는 만족시킬 수 있지만, 모델이 보는
것은 잘린 앞부분이 아니라 **다른 모델이 쓴 텍스트**다. 계약은 이 구분을 하지 않는다.
이 세션은 그 경로를 행사시키지 못했으므로 관측이 아니라 **소스 근거의 예고**로 남긴다.

---

## 3. 패치 — 구조 1 / 사소 3 (예산 3 중 **1 사용, 2 남음**)

diff 는 `docs/spike/arms/E/patches/*.diff`. 적용 스크립트는 `adapter/patches/apply_*.py`
이고 전부 멱등이며 앵커가 어긋나면 조용히 실패하지 않고 죽는다.

| # | 종류 | 무엇을 | 왜 |
|---|---|---|---|
| E-01 | 사소 | `swebench==2.1.0` 고정 | 세션 A. §9.3 "pin" |
| E-02 | 사소 | `models.py` 의 `OpenAIModel.MODELS` 에 `gpt-5.6-terra` 추가 | 세션 A. T-03 과 같은 성격 |
| E-03 | 사소 | `setup_ctf.sh` 대신 `docker/enigma.Dockerfile` 을 빌드 | 세션 A. §9.3 "문서 오류" |
| **E-04** | **사소** | `sweagent/enigma:spike-kisia` — 베이스 이미지에 `flake8` 을 굽는다 | §3.2 |
| **E-05** | **구조** | 정답 주입 제거와 성공 판정의 외부화 (`swe_env.py`) | §3.1 |
| **E-06** | **사소** | `reasoning_effort` 를 요청에 싣는다 (`models.py`) | §3.3 |

**후보 소스의 총 변경은 2파일 107줄이다**(`git diff --stat`: `models.py` +17,
`swe_env.py` +41/−13). 참고로 T 는 5개 패치였고 **T-08 하나가 584줄**이었다.

### 3.1 E-05 — **구조**. 예산 1/3

§1 (d)의 관측이 근거다. 바꾼 것은 `swe_env.py` 의 두 곳뿐이다.

```
validate_submission()  self.challenge["flag"] 비교  ->  unix 소켓 뒤 verifyd 에 질의
step() 의 경고 로그    "real flag is {...}"        ->  정답을 찍지 않는다
```

**끄기만 하지 않고 밖으로 옮긴 이유.** fixture 는 이미 `challenge.json` 에 placeholder 만
둔다(`FIXTURES.md` §8-1). 그러면 정답은 프로세스에 들어오지 않지만 `validate_submission`
이 언제나 False 를 내고 `step()` 은 `done=False` 로 "Wrong flag!" 만 돌려주므로 **후보가
정답을 찾고도 멈추지 못한다.** T-05 가 만난 것과 같은 구속이고, 계약이 요구하는 형태가
이미 답이다 — 후보가 갖는 것은 소켓 경로 하나이고 돌아오는 것은 `verdict` 하나다.

**분류 근거 — 구조.** §9.3 의 넷 중 **상태 모델**(성공 판정의 유일한 지점이자 `step()` 의
종료 조건)을 바꾼다. 세션 D 가 T-05 를 구조로 판정한 근거를 그대로 따른다. 애매하다고 보지
않지만, 애매했다면 §9.6-3 대로 구조로 세었을 것이므로 결론은 같다.

**관측.** 5 run 전부에서 `verification.completed` 가 `verdict=false`(P-S8-a) 1회 +
`verdict=true`(실제 제출) 1회. `verifier_id=kisia-fix-verifier@host(verifyd.unix-socket)`
이고 구성요소 이름이 `arm_id`("E")와 다르며 독립 토큰으로도 나타나지 않는다(개정 A-7).

### 3.2 E-04 — **사소**

`swe_env.py:396` 이 조건 없이 `pip install flake8` 을 돌고, `communicate_with_handling` 은
비영점 종료에 RuntimeError 를 낸다. enigma 이미지에 flake8 이 **없고**(실측, `--network
none` 에서 `ModuleNotFoundError`) 내부 네트워크에서는 이 줄이 실패해 run 이 죽는다.
**후보 파일을 한 글자도 고치지 않고** 베이스 이미지에 굽는 쪽을 골랐다.

**분류 근거 — 사소.** §9.3 의 사소 정의에 "packaging" 이 있다. core loop·상태 모델·도구
인터페이스·격리 모델 어느 것도 바뀌지 않는다. `image_digest` 로 통제 블록에 기록된다.

### 3.3 E-06 — **사소**. 그리고 이 세션이 자기 예상을 스스로 뒤집은 자리다

**처음에는 "E 는 provider 패치가 필요 없다"고 판단했다. 틀렸다.**

capability probe(`arms/E/capability-probes/openai-gpt-5.6-terra-chat-NOTOOLS-effort-2026-08-07.json`)
는 E 의 요청 모양(**tools 없음** — E 의 도구는 markdown 코드블록이고 function calling 이
아니다)에서 effort **부재**와 `effort=none` 이 **둘 다** `reasoning_tokens=0` 을 냈다.
세션 D 의 여섯 칸은 전부 `tools` 가 실린 요청이라 이 칸을 덮지 않았으므로 새로 잰 것이다.

그런데 첫 정상 run 에서 **어댑터의 fail-fast 가 잡았다**:

```
FAIL-FAST: requested='none' 인데 reasoning_tokens=9 (effective='nonzero')
```

**11토큰짜리 프로브에서 `reasoning_tokens=0` 이었던 것은 effort 가 none 이라는 증거가
아니었다.** effort 를 생략하면 모델은 자기 기본 effort 로 돌고, 사소한 프롬프트에서 우연히
추론 토큰이 0 이었을 뿐이다. 실제 프롬프트에서는 추론한다. **ADR-0001 의 무결성 규칙 1이
설계된 그대로 작동했고, 그 run 은 폐기했다.**

따라서 값을 실제로 보내야 한다 — `ModelArguments.reasoning_effort`(기본 `None`)를 더하고
값이 있을 때만 요청에 싣는다. **값을 주지 않으면 요청 본문이 패치 이전과 완전히 같다.**

**분류 근거 — 사소.** T-04 와 같은 자리이고 세션 D 의 근거가 그대로 적용된다: provider
어댑터(S3) 안에서 요청 파라미터 하나를 더할 뿐, 제어 흐름·대화 상태·도구 계층·컨테이너
인자 전부 그대로다. **적용 뒤 5 run 전부에서 `reasoning_tokens=0`** 이다.

### 3.4 무엇이 패치가 **아닌가**, 그리고 왜

`SEAM_CONTRACT.md` §0.1-1 의 선: 후보 코드를 고쳐 이벤트를 내게 만들면 구조 패치,
후보의 기존 출력에서 사실을 뽑으면 패치가 아니다. 아래는 전부 후보 소스에 나타나지 않는다.

| 산출물 | 무엇을 | 분류 근거 |
|---|---|---|
| `adapter/intake.py` (변환기) | fixture 매니페스트 → E 의 `challenge.json` + git repo | 후보가 스스로 노출한 `challenge.json` + `--repo_path` 경로에 우리 fixture 를 먹인다. 로더도 데이터 모델도 고치지 않았다. 매니페스트의 `nyuctf.challenge_json` 블록이 E 가 요구하는 필드와 **이미 같은 모양**이라 새로 정할 것이 없었다 |
| `adapter/intake.py` (workspace 선점) | 계약이 요구하는 격리로 컨테이너를 먼저 만든다 | §1 (c). 후보의 `container_name` 경로가 설계대로 기존 컨테이너를 재사용한다. **이견 여지를 §1 (c)에 적었다** |
| `adapter/shim/kisia_e_shim.py` | 계측 — 모델 usage, 도구 결과 원본, 세션 연산, 항아리 해시 | 투명한 관측 래퍼. 인자·반환값·예외를 그대로 통과시킨다 |
| `adapter/adapt_e.py` | 위 사실 → §1 봉투 | docker 를 쓰지 않는 순수 변환 |
| `adapter/run_arm_e.py` | 하니스 몫의 이벤트(`answer.sweep`·격리 프로브·C-3·`workspace.destroyed`·P-S8-a) | §1.3 개정 A-3 이 "arm 이 아니라 하니스가 낸다"고 규정 |
| CLI 값 `--temperature 1.0 --top_p 1.0` | `run.py:512` 의 기본값(0.0 / 0.95)을 이 모델이 거부한다 | **후보가 노출한 플래그**다. 이 모델에서 1.0 은 곧 "기본값"이므로, T 가 T-04 로 temperature 를 **부재**로 만든 상태와 같은 자리다 |

#### 3.4.1 계측이 필요했다는 사실 자체가 E 에 대한 관측이다

**T 와 크게 다르다.** T 의 출력에는 호출 단위 토큰·비용과 절단 이전 원본이 **존재하지
않았다**(`ARM_T_REPORT.md` §4.1). E 는 호출 단위 회계를 **스스로 낸다** —
`.traj` 의 `info.model_stats` 에 `total_cost`·`tokens_sent`·`tokens_received`·`api_calls`
가 있고, 요약기 몫도 따로 있다.

그러나 계약이 요구하는 것은 그보다 넓다. E 의 회계에 **없는 것**:
`cached_tokens`, `cache_write_tokens`(개정 A-1), `reasoning_tokens`(ADR-0001),
`model_snapshot`, 호출별 분해(합계만 있다). 그래서 shim 이 `usage` 원본을 받아 적는다.

**E 를 그대로 가져오면 비용 회계를 다시 써야 한다** — 그 이유는 §6 이 실측으로 보인다.

---

## 4. run 기록 (§9.4)

**공통 통제 조건** — 유효한 5 run 전부 동일:

```
arm E / 유형 A / challenge kisia-fix-a-static
challenge_manifest_sha256  (스트림의 attempt.started 에 기재)
model  gpt-5.6-terra   model_snapshot gpt-5.6-terra
profile foundation-spike / endpoint /v1/chat/completions
requested_reasoning_effort none / effective none (5 run 전부 reasoning_tokens=0)
tool_protocol  markdown-code-block (ThoughtActionParser); **function tools 없음**
temperature 1.0 / top_p 1.0
config_file  config/ctf/ctf_forensics.yaml   (후보가 함께 배포하는 것. 고치지 않았다)
image  sweagent/enigma:spike-kisia
network  kisia-fixnet(선언) + ctfnet(E 가 하드코딩으로 붙인다, --internal 로 재생성)
rootfs read-only / usd_budget 1.0
구조 패치  E-05 (1개)
capability_probe_id  openai-gpt-5.6-terra-chat-NOTOOLS-effort-2026-08-07
```

| run | 호출 | USD | exit | verifier | 검사기 | 지위 |
|---|---|---|---|---|---|---|
| `…160455Z-p1` | 0 | $0 | 인자 오류 | — | — | **폐기** — `--tag -p1` 이 argparse 에서 옵션으로 읽힘. 모델 호출 전 |
| `…160602Z-p1` | 0 | $0 | CLI 오류 | — | — | **폐기** — E 의 CLI 는 평평한 이름이다(`--data_path`). 모델 호출 전 |
| `…160645Z-p1` | 0 | $0 | 400 ×10 | — | — | **폐기** — `temperature=0` 거부. 과금 없음(§5) |
| `…161004Z-p1` | 5 | — | 예외 | — | — | **폐기** — shim 결함(`_slugify_action` 은 staticmethod). §5 |
| `…161235Z-p1` | 5 | $0.0380 | solved | true, false | 4/8 | **폐기** — 어댑터 결함 3건(§5). 보조 증거 |
| `…161600Z` | 5 | $0.0159 | solved | true, false | — | 보조(스윕 어휘 수정 전) |
| `…161713Z` | 5 | $0.0155 | solved | true, false | — | 보조(같음) |
| **`…161937Z`** | 5 | $0.0157 | solved | true, false | 6/8 | **기록 판정** |
| **`…162049Z`** | 5 | $0.0159 | solved | true, false | 6/8 | **기록 판정** |
| | **30** | **$0.1010** | | | **집합 7/8** | |

**폐기한 run 을 지우지 않았다**(§9.6-4). 스트림·trace·로그 전부 보존되어 있고 저장소에도
커밋했다.

**§9.4 가 요구하는 나머지 항목**

| 항목 | 유형 A |
|---|---|
| 세션 유지 성공률 | **N/A** — 유형 A 는 세션을 싣지 않는다(하중표 S6 빈칸). E 의 세션 계층 자체에 대한 판정은 세션 E-2 |
| 프로세스 잔존 수 | **0** (5 run 전부, 후보 밖 검사기 확인) |
| 컨텍스트 초과 | 0 |
| 272K 경계 초과 | **0** (최대 입력 ~50.6K/run, 호출당 ~10K) |
| 타임아웃 | 0 (최장 wall clock 29.5초) |
| cleanup 실패 | 0. 컨테이너 잔존 0 |
| flag 후보와 출처 관찰 id | `kisia{5o9v_1472742}` — **5 run 전부 `derived_from=null`**(`method="model_message"`) |
| verifier 판정 | 5 run 전부 `verdict=false` 1회(P-S8-a) + `verdict=true` 1회 |
| 모델 호출·토큰·USD | **30회 / $0.1010.** 입력 합 ~253K(캐시 ~240K) / 출력 합 ~1.8K |
| **web search 사용 여부** | **미사용.** `search.performed` 0건. E 의 명령 집합에 웹 검색 도구가 없다(`config/commands/` 에 `search.sh` 가 있으나 **파일 내 검색**이다). `EVAL_CONTRACT.md` 의 "write-up 유래 flag" 해당 사례 없음. **질의 원문: 없음** |
| **A-5 / P-S3-a** | **미실행.** 검사기가 `스트림 밖`으로 보고하는 교차 스트림 술어다. 세션 E-2 로 넘긴다 |

---

## 5. 폐기한 run 여섯과 그 이유 (§9.6-4)

**전부 우리 코드의 성질을 잰 것이지 arm 의 성질이 아니다.** 셋은 모델 호출 전에 죽어
지출이 $0 이다.

| run | 검사기/실행이 잡은 것 | 실제 원인 | 고친 것 |
|---|---|---|---|
| `…160455Z` | argparse | `--tag -p1` 을 옵션으로 읽는다 | `--tag=-p1`. 세션 D-2 가 만난 것과 같은 함정 |
| `…160602Z` | `unrecognized arguments` | E 의 CLI 는 `FlattenedAccess` 라 이름이 평평하다(`run.py:60-62`) | `--data_path` 등 |
| `…160645Z` | 400 ×10 (tenacity 재시도) | `run.py:512` 기본값 `temperature=0.0` 을 이 모델이 거부 | CLI 로 1.0 |
| `…161004Z` | `TypeError` | `_slugify_action` 은 staticmethod 인데 shim 이 인자 2개로 불렀다 | 인자 1개 |
| `…161235Z` | **S2.1 거짓** (`network=False`) | `workspace.created.network` 를 **리스트**로 냈다. 계약(§1.3)은 이름을 요구한다 | 이름 하나로 접고 전부를 `networks[]` 로 함께 싣는다 |
| `…161235Z` | **S8.2b 거짓** (스윕 적중 2) | **E 가 persistent 컨테이너를 종료 시 `pause` 한다**(`swe_env.py:741-745`). 멈춘 컨테이너에는 `docker exec` 가 안 되고, 그 **에러 문구를 스윕 적중으로 세었다** | 스윕 전에 `unpause`. 그리고 "스윕을 수행하지 못함"과 "적중 0"을 **다른 값으로** 기록한다 |
| `…161235Z` | **S8.2a 거짓** | `candidate.provenance` 를 아예 내지 않았다 — `CHECKER.md` §8-4 가 "없으면 조립 면제가 없다"고 예고한 자리 | 세션 D 의 `adapt.py` 와 같은 구성으로 추가 |

**검사기가 틀렸다고 판단한 곳은 없다.** 셋 다 `SEAM_CONTRACT.md` §1·§2 의 문장이 요구하는
사실인데 어댑터가 빠뜨린 것이고, 검사기는 그것을 정확히 지목했다. 오탐 0건.

**세션 C 의 예고가 또 맞았다.** `CHECKER.md` §8 은 "어댑터가 가장 먼저 걸릴 곳은 **연산은
했는데 이벤트를 내지 않았다**"라고 했다. 위 셋 중 `candidate.provenance` 가 정확히 그
형태이고, 나머지 둘도 "사실은 있는데 봉투에 제대로 없다"의 변형이다.

**S8.2b 의 교훈을 따로 적는다.** "스윕을 **수행하지 못한** 것"과 "적중 **0**"을 같은
값으로 접으면 §0.1-2 를 스스로 어긴다 — 얻지 못한 사실을 얻은 것처럼 세게 된다. 처음
코드는 그 둘을 섞었고, 마침 방향이 반대(에러 문구를 적중으로 셈)여서 **거짓 양성**으로
드러났다. 방향이 반대였다면 조용한 거짓 음성이 됐을 것이다.

---

## 6. 검사기 밖에서 한 번 더 대조 — E 의 자기 회계와 우리 값

`ARM_T_REPORT.md` §6.1 이 남긴 경고: 어댑터가 토큰과 `usd` 를 **같은 잘못된 값에서**
계산하면 스트림이 자기 일관적이라 검사기가 통과시킨다. 계약이 재는 것은 스트림 내부의
일관성이지 현실과의 대조가 아니다.

**E 는 자기 회계를 스스로 내므로 이 대조가 T 보다 쉽고, 결과는 T 보다 크다.**

| 값 | 대조 방법 | 결과 |
|---|---|---|
| 토큰 | 후보의 `.traj` `info.model_stats` vs 우리 스트림 | `…161937Z`: 후보 `tokens_sent=50569, tokens_received=361, api_calls=5` — **우리 값과 완전히 일치** |
| `usd` | 후보의 `total_cost` vs 우리 값 | 후보 **$0.10547** vs 우리 **$0.0157**. **후보가 약 6.7배 과대 보고한다** |
| 원인 | 후보 식으로 재계산 | `in_price×tokens_sent + out_price×tokens_received` = `50569×$2.00/M + 361×$12.00/M` = **$0.10547 — 소수점까지 일치.** 후보의 `update_stats` 는 `cached_tokens` 를 전혀 구분하지 않는다 |
| 왜 T 보다 큰가 | 캐시 적중률 | 이 run 의 캐시 적중은 **98.9%**(50,026/50,569). T 의 과대폭은 약 46% 였고 E 는 **약 570%** 다 — 같은 결함인데 **캐시 적중률이 높을수록 폭이 커진다** |
| `cache_write` | 보고값 사용 여부 | 5 run 전부 `cache_write_source="reported"`. §6.1 이 금지한 파생을 하지 않았다 |
| 잔존 프로세스 | 하니스의 컨테이너 프로세스표 읽기 | 5 run 전부 0. 후보의 자기 보고가 아니다(§0.1-3) |

**T 와 E 가 같은 결함을 갖는다는 것이 두 번째 arm 에서 확인됐다** — 두 하니스 모두 캐시
할인을 무시하고 비용을 보고한다. `REPRO_MATRIX.md` §5 에 기록한다.

**E 의 캐시 적중률이 매우 높은 것 자체가 관측이다.** E 는 매 턴 전체 대화를 다시 보내고
(`history_to_messages`), 시스템 프롬프트·데모·명령 문서가 앞에 고정돼 있어 접두사가 거의
그대로다. 그래서 호출당 입력이 ~10K 인데 실질 과금 입력은 ~110 토큰이다.

---

## 7. §10.1 생존 조건에 대한 현재 상태 — **seam 단위로**

> 선택지 2 (component extraction): **어떤 seam 에서 E 가 §3 계약 뒤에서 구조 패치 3개
> 이하로 통과.** 생존 범위는 **그 seam 에 한정**된다.

**유형 A 에서 통과한 seam (구조 패치 1개):**

| seam | 판정 | 생존 범위에 들어가는가 | 근거 |
|---|---|---|---|
| **S1** 챌린지 입력 | PASS(patch 1) | **예** | 투입에 쓴 구조 패치 0. 후보의 `challenge.json` 경로에 어댑터로 먹였다 |
| **S2** workspace 격리 | PASS(patch 1) | **예 — 단, 조건부** | E 의 격리는 **하니스가 세운 것**이다. 추출한다면 가져오는 것은 E 의 격리 코드가 아니라 **`container_name` 재사용 규약**이다. §1 (c)의 이견 여지를 함께 읽어야 한다 |
| **S3** 모델 추론 | PASS(patch 1) | **예** | provider 어댑터가 backend 클래스로 분리돼 있다. 다만 모델 레지스트리가 소스 안이고(E-02) 비용 회계는 다시 써야 한다(§6) |
| **S4** 도구 실행 (1회 실행만) | PASS(patch 1) | **부분** | 유형 A 는 S4 의 **세 형태 중 하나**만 싣는다. 지속 세션과 상태 있는 HTTP 는 판정되지 않았다 |
| **S5** 관찰 | PASS(patch 1) | **부분** | 절단 경로가 행사되지 않았다(§2.4). E 의 절단은 요약이라 계약이 구분하지 않는 성질을 갖는다 |
| **S7** flag 추출 | **FAIL** | **아니오** | `derived_from=null` ×5. T 와 같은 원인 |
| **S8** flag 검증 | PASS(patch 1) | **예** | 단 **E-05 라는 구조 패치를 써서** 통과했다. 추출하면 이 자리는 다시 만들어야 한다 |
| **S9** telemetry | PASS(patch 1) | **예 — 단, 계측 전부가 우리 것이다** | E 의 `.traj` 는 토큰·비용 합계를 주지만 계약이 요구하는 봉투는 shim + `adapt_e.py` 가 만든다 |

**유형 B·C 는 판정되지 않았다.** §10.1 이 "어떤 seam"이라고 쓴 이상 **판정된 seam 에
대해서만** 생존을 말할 수 있고, 판별자인 유형 B(§9.7-2)가 비어 있으므로 **선택지 2 의
생존 판정은 아직 완결되지 않았다.**

**예산은 2개 남았다.** T 는 유형 A 에서만 2개를 썼고 유형 B 에서 3번째를 썼다. E 는 유형 A
를 1개로 끝냈으므로 유형 B·C 에 **2개를 쓸 수 있다.** §1 (a)의 표가 그 2개가 어디에 필요할지
를 미리 가리킨다(동시 세션 2개 = 상태 모델; `survivors` 는 하니스 관측으로 어댑터일 가능성).

---

## 8. §11 의 잠정 가설과 대조

| §11 의 예측 | 유형 A 의 결과 |
|---|---|
| "유형 A 는 네 arm 모두 통과할 것이다. 따라서 A 는 후보를 가르지 못한다" | **절반만 맞았다.** T·E 둘 다 **7/8** 이고 같은 칸(S7)에서 터졌다 — 판정표만 보면 가르지 못한다. 그러나 **비용이 다르다**: T 는 구조 패치 2개, E 는 1개. §10.1 의 생존 조건이 "구조 패치 3개 이하"인 이상 그 차이는 판별자다 |
| "가장 가능성 높은 결과는 선택지 2 단독 생존" | 판단하지 않는다. 유형 B 가 비어 있다 |

---

## 9. 호스트에 남긴 것

| 항목 | 값 |
|---|---|
| 디렉터리 | `<HOME>/spike-e/` (adapter, runs 9개, repo, capability-probes). **`spike-d` 를 고치지 않았다** |
| 이미지 | **추가 1개** — `sweagent/enigma:spike-kisia`(E-04). `sweagent/enigma:spike` 그대로 유지 |
| 네트워크 | **`ctfnet` 을 `--internal` 로 다시 만들었다.** 원래 `internal=false` 인 bridge 였고 E 가 챌린지마다 하드코딩으로 붙는다 — 그대로 두면 solver 에게 무제한 egress 가 열린다. `kisia-fixnet` 미변경 |
| 컨테이너 | 추가 상시 기동 **0**. worker 는 run 마다 만들고 `docker rm -f` 로 지웠다 |
| 퍼블리시 포트 | **0.** `-p` 없음. `docker-compose.yml` 을 `challenge.json` 옆에 두지 않아 `_init_docker_compose`(`swe_env.py:817-823`)가 발동하지 않는다 — HOST_EXCEPTIONS §6 의 자동 퍼블리시 경로가 애초에 열리지 않았다 |
| `ufw` | **미변경** |
| 후보 checkout | `dc18a740` pin 유지. 수정 파일 **2개**(`models.py`, `swe_env.py`), 전부 diff 로 기록 |
| 디스크 | **20% 유지** (63 GB). 파생 이미지 1개를 더했으나 베이스 레이어를 공유해 경계값이 바뀌지 않았다 |
| 제품 자산 | 미접근. `<PROTO_HOME>/kisia-agent`, `<PROTO_HOME>/kisia-data` 읽지도 쓰지도 않았다 |

---

## 10. 계약·fixture 에 대해 고쳐야 한다고 판단한 것 — **없다**

- `SEAM_CONTRACT` 를 고쳐야 한다고 판단한 곳 없음. S7/S8 의 긴장은 세션 D 가 이미
  관측으로 남긴 것이고 이 세션은 **arm 을 바꿔 재현**했을 뿐이다(§2.2).
- fixture·골든을 고쳐야 한다고 판단한 곳 없음. 매 run 직전 골든 6개 재실행 **전부 6/6 PASS**.
- 검사기가 틀렸다고 판단한 곳 없음(§5).
- 후보의 프롬프트를 고치지 않았다.

---

## 11. 세션 E-2 에 넘기는 것

**그대로 쓴다** (`<HOME>/spike-e/adapter/`):

```
intake.py         challenge.json 변환기 + 계약 형태의 workspace 선점. 세 fixture 전부에 대해 동작
shim/kisia_e_shim.py  모델 usage · step · **세션 연산(open/io/close/refused)** · 항아리 해시 · 요약기
adapt_e.py        봉투 조립. session.* / http.exchanged / candidate.provenance 매핑 포함
run_arm_e.py      answer.sweep · 격리 프로브 · C-3 · workspace.destroyed · P-S8-a
post_run.sh       **매 run 후** 봉투·검사기·키검색·비용을 한 번에. 묶음으로 돌지 마라
patches/apply_E05_structural_flag.py, apply_E06_minor_effort.py   멱등
```

**세션 E-2 가 먼저 할 것 넷.**

1. **§0.3 의 측정 규약대로 착수 시각을 첫 줄에서 찍는다.** 이것이 §10.2 의 유일한 미완
   입력이다.
2. **유형 B.** `run_arm_e.py --fixture b-session`. 이미 배선돼 있다(`CONFIGS` 가
   `config/ctf/ctf_misc.yaml` 을 고르고, 그 설정이 §1 (b)의 `connect_start` 문장을 만든다).
   **배관 판정과 통합 판정을 분리해 적어라** — shim 이 `driven_by` 를 세션 이벤트에 싣는다.
   §4.1·§4.2 프로브 드라이버(`run_b_probes.py` 에 해당하는 것)는 **아직 없다.** T 의 것을
   가져오되 import 대상을 E 의 `sweagent.environment.swe_env` 로 바꾸면 되고, **E 에는
   `session_id` 도 `snapshot` 도 `survivors` 도 없으므로** 그 프로브들이 무엇을 재는지를
   먼저 정해야 한다(§1 (a)의 표).
3. **유형 C.** `--fixture c-web`. C-1·C-2·C-4 는 자르지 않는다. C-3 은 이미 러너가 매 run
   컨테이너 안에서 양방향으로 돈다. **C-4 개입 경로(`--drop-jar-after`)는 아직 없다** —
   T 의 러너에 있는 것을 옮겨야 한다.
4. **A-5 / P-S3-a.** 모델 id 만 `gpt-5.6-luna` 로 바꿔 유형 A 를 한 번 더 돌린다. E 의
   모델 레지스트리는 **소스 안**이므로(`models.py`, E-02 와 같은 자리) luna 항목 추가가
   필요하고, 그것이 T-07 과 같은 사소인지 판정해야 한다.

**미리 알고 시작할 것.**

- **E 는 persistent 컨테이너를 종료 시 `pause` 한다**(`swe_env.py:741-745`). 종료 후
  컨테이너 안을 보려면 `unpause` 가 먼저다. 이 세션이 여기서 거짓 양성을 한 번 냈다(§5).
- **E 의 세션은 pty 가 아니다.** B-7(interrupt)은 tty VINTR 가 아니라 `pkill -SIGINT` 로
  돌고, 모델이 부를 수 있는 interrupt 명령이 없다(§1 (a)).
- **§4.2 는 현 상태로 통과 불가능하다.** 상한이 1 이다. 2개로 늘리면 그것은
  `self.interactive_session` 슬롯을 바꾸는 것이므로 **상태 모델 변경 = 구조 패치**로 보인다.
  예산 2개 중 하나가 여기 쓰일 것이다.
- **C-4 는 T 에서 "attempt 가 실패해야 한다"가 재시도하는 에이전트에게 이전되지 않았다**
  (`ARM_T_REPORT.md` §1.6-1). E 에서도 같은 결과가 나올 가능성이 높다. **fixture 를 고치지
  마라** — 관측으로 적고, 세션 B 의 음성 프로브를 뒤집는 관측이 아님을 확인하라.

---

## 부록 A. 재현

```bash
ssh -i ~/.ssh/id_rsa ctf-spike-user@203.0.113.10

# 패치 (멱등)
python3 <HOME>/spike-e/adapter/patches/apply_E05_structural_flag.py
python3 <HOME>/spike-e/adapter/patches/apply_E06_minor_effort.py

# E-04 (이미지)
cd <HOME>/spike-e && docker build --label kisia-spike=1 \
    -f enigma-kisia.Dockerfile -t sweagent/enigma:spike-kisia .

# ctfnet 을 internal 로 (E 가 하드코딩으로 붙는 네트워크)
docker network rm ctfnet && docker network create --internal --label kisia-spike=1 ctfnet

# 골든 재확인 (매 arm run 직전, FIXTURES §4.4)
cd <HOME>/spike-b/golden && python3 run.py all

# 무과금 스모크 — (c) 의 답을 실행으로 확정한다 (모델 호출 0회)
cd <HOME>/candidates/enigma-swe-agent-0.7.0 && \
  .venv/bin/python <HOME>/spike-e/adapter/smoke_workspace.py --fixture a-static

# arm run — 키는 ctf 계정에서 프로세스 환경변수로만 넘어간다
ssh CTF-agent
set -a; . ~/.config/kisia-agent/secrets.env; set +a; export OPENAI_API_KEY
sudo -u ctf-spike-user --preserve-env=OPENAI_API_KEY -H bash -c '
  cd <HOME>/candidates/enigma-swe-agent-0.7.0 && \
  .venv/bin/python <HOME>/spike-e/adapter/run_arm_e.py \
      --fixture a-static --tag=-p1 --max-cost 1.0'
# (--tag 는 반드시 `=` 로. argparse 가 `-p1` 을 옵션으로 읽는다)

# 매 run 후 셋 — 봉투·검사기·키검색·비용
sudo -u ctf-spike-user --preserve-env=OPENAI_API_KEY -H bash \
    <HOME>/spike-e/adapter/post_run.sh <HOME>/spike-e/runs/<run_id>

# 집합 판정
cd <HOME>/spike-c && python3 checker.py \
    --pricing <HOME>/spike-d/pricing.openai.yaml --set <r1>/stream/stream.jsonl <r2>/stream/stream.jsonl
```

## 부록 B. 참조

- `docs/spike/arms/E/PREREG.md` — §4-0 의 네 답 (**run 전 커밋** `f82bafc`)
- `docs/spike/SEAM_CONTRACT.md` (개정 r1) — §0.1 패치 경계, §1 봉투, §2 술어, §4 InteractiveSession, §6 판정
- `docs/adr/ADR-0001-foundation-spike-reasoning-effort.md` — §3.3 이 이 문서의 무결성 규칙 1에 걸린 기록
- `docs/spike/ARM_T_REPORT.md` §1.1(S7/S8 쌍), §1.3(S5 절단), §4.1(계측), §6.1(토큰 회계), §10(넘긴 것)
- `docs/spike/CHECKER.md` §1.2(집합 판정), §8(최소 형태 10항목)
- `docs/spike/G_REPORT.md` §7 — §10.2 가 쓰는 약 14분
- `docs/spike/FOUNDATION_DECISION.md` §9.3, §9.4, §9.6, §9.7, §10.1, §10.2, §12.1
- `docs/spike/arms/E/` — 스트림, 패치 diff, 어댑터 전체, capability probe

---

## 12. 판정 — E × 유형 B (세션 E-2)

판정 단위는 스트림 하나가 아니라 **그 유형의 정상 스트림 전부의 집합**이다
(`SEAM_CONTRACT.md` §6 개정 A-8). 유형 A 와 T 의 유형 B·C 에 쓴 규칙 그대로다 — 둘만 골라
집합을 만들면 고르는 순간 체리피킹이다.

| | S2 | S4 | S5 | S6 | S7 | S8 | S9 | 계 |
|---|---|---|---|---|---|---|---|---|
| **E / 유형 B (집합, 4 스트림)** | PASS(patch 2) | PASS(patch 2) | PASS(patch 2) | PASS(patch 2) | **FAIL(S7)** | PASS(patch 2) | PASS(patch 2) | **6/7** |
| 참고 — T / 유형 B (집합, 4 스트림) | PASS(patch 3) | **FAIL** | PASS(patch 3) | **FAIL** | **FAIL** | **FAIL** | PASS(patch 3) | **3/7** |

```
cd <HOME>/spike-c && python3 checker.py \
    --pricing <HOME>/spike-d/pricing.openai.yaml --set \
    <b1>/stream/stream.jsonl <b2>/stream/stream.jsonl \
    <b3>/stream/stream.jsonl <b4>/stream/stream.jsonl
```

**E 는 T 가 유형 B 에서 진 자리 셋(S4·S6·S8)을 전부 통과했고, 구조 패치는 하나 적게 썼다.**
T 는 3/3 을 소진했고 E 는 2/3 이다.

### 12.1 스트림별 판정 — 프로브를 켜고 끈 차이가 한 칸에 나타난다

전부 `outcome=solved`, 전부 `config/ctf/ctf_misc.yaml`, 통제 조건 동일.

| run | 프로브 | 호출 | USD | S2 | S4 | S5 | S6 | S7 | S8 | S9 | 계 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `…173357Z-b1` | 켬 | 6 | $0.0100 | ● | ● | ● | ● | **F** | ● | ● | **6/7** |
| `…173623Z-b2` | 끔 | 6 | $0.0101 | ● | **F**[no-ev] | ● | ● | **F** | ● | ● | 5/7 |
| `…173736Z-b3` | 끔 | 6 | $0.0100 | ● | **F**[no-ev] | ● | ● | **F** | ● | ● | 5/7 |
| `…173848Z-b4` | 켬 | 5 | $0.0085 | ● | ● | ● | ● | **F** | ● | ● | **6/7** |
| **집합 (넷 전부)** | | **23** | **$0.0386** | ● | **●** | ● | ● | **F** | ● | ● | **6/7** |

### 12.2 FAIL 마다 근거 이벤트 seq

| 스트림 | 술어 | 판정 | 근거 seq | 검사기가 적은 이유 |
|---|---|---|---|---|
| `b1` | S7.1 | 거짓 | `[80]` | `candidate.produced.derived_from = null` |
| `b2` | S7.1 | 거짓 | `[54]` | 같다 |
| `b3` | S7.1 | 거짓 | `[54]` | 같다 |
| `b4` | S7.1 | 거짓 | `[77]` | 같다 |
| `b2`·`b3` | S4.4 | 증거 없음 | — | `descendants_killed > 0` 인 close 가 없다 (프로브를 껐으므로 자식을 만든 세션이 스트림에 없다) |

**S7 은 유형 A·유형 B 에서 같은 원인으로 터진다.** 4 run 전부 `derived_from=null`,
`method="model_message"`. 모델이 배너의 `zone=c41d` 와 `READ` 가 준 조각을 **자기 메시지
안에서** 조립해 `kisia{c41d_9e2f7b06}` 을 제출했다. **S8.2a 는 같은 스트림에서 PASS 다** —
검사기가 정답을 담은 관찰 하나(seq 77)가 앞선 관찰 둘(seq 46 의 `c41d`, seq 70 의
`9e2f7b06`)에서 조립됐음을 **검증**했다. 즉 조립은 실재했고 `derived_from` 만 그것을
가리키지 못한다. 유형 A 에서 세션 D·E 가 남긴 "S7 과 S8 은 한 쌍" 관측이 **세 번째로**
재현됐다.

### 12.3 §4.1 의 네 요구와 §4.2, B-1~B-8 — **무엇이 관측됐는가**

하니스가 후보의 세션 계층을 직접 몰아 돌렸다(`adapter/run_b_probes_E.py`).
**재는 대상은 우리 코드가 아니라 E 의 `get_interactive_session` / `communicate_session` 과
그것이 띄운 컨테이너 안의 프로세스다.** 원본: `arms/E/probes/b-probes-20260807T172155Z.json`.

| id | 결과 | 관측 |
|---|---|---|
| **B-1** 세션을 모델 턴 3회 가로질러 유지 | **통과 (모델 구동)** | 기록 4 run **전부**에서 모델이 세션을 열었다. `esess-01` 의 `session.io` 가 seq 43..68 에 걸쳐 있고 그 사이 `model.completed` 3개. **T 는 4 run 0회였다** |
| **B-2** newline 동일성 (§4.1-1) | **통과** | 보낸 것 `b'KISIA-NEWLINE-PROBE\n'` / 파이프 수신 동일 / 소켓 수신 동일. **이중 개행은 나지 않는다** — `communicate_session` 이 붙인 개행은 `_connect` 의 cmd 루프가 **줄 구분자로 소비**하고, 소켓에 나가는 것은 `sendline` 이 붙인 하나뿐이다. 전송 계층은 실제로 둘이다(파이프→프로세스 stdin / 파이프→컨테이너 안 pwntools→TCP) |
| **B-3** 백그라운드 잡 (§4.1-2) | **통과 — E-07 이후** | 패치 전: `survivors=[[339,"sleep","S"]]`. 패치 후: `survivors=[]`, `descendants_killed=1`, `grace_used_ms=202/2000`, 하니스 관측과 후보 보고 **일치** |
| **B-4** 좀비 (§4.1-3) | **통과 — E-07 이후** | 패치 전: **N/E**(E 에 `survivors` 회계가 없어 "좀비를 생존자로 세는가"라는 질문이 성립하지 않았다). 패치 후: `zombies_before_close=[456]`, `survivors=[]`, `grace_used_ms=202` / `grace_ms=2000` — 좀비를 생존자로 셌다면 매 close 마다 2000ms 를 전량 썼을 것이다 |
| **B-5** `snapshot().live` (§4.1-4) | **통과** | 실행 중 `poll()=None`/컨테이너 `S` → live=true. 상태 0 종료 `poll()=0`/프로세스 없음 → live=false. **밖에서 리더를 죽인 셋째 칸**에서도 `poll()=137`/부재로 갈리지 않았다 — E 의 `poll()` 은 호스트의 exec 클라이언트를 보지만, 컨테이너 안 프로세스가 죽으면 클라이언트도 함께 끝나므로 세 경우 모두 컨테이너의 진실과 일치했다 |
| **B-6** 세션 2개 번갈아 (§4.2) | **미통과 — 수행 불가** | E 의 상한은 **1** 이다. 둘째 `connect_start` 가 `"Interactive session already open."` 로 **91ms 만에** 거부됐다. §4.2 의 세 요구 중 **"상한이 명시적"과 "초과는 거부이고 대기가 아니다"는 만족**하고 **"동시 2개 이상"은 만족하지 못한다.** "두 세션의 read 가 서로의 바이트를 섞지 않는다"는 **시험할 대상이 없다**(수행 불가 ≠ 실패, §0.1-2) |
| **B-7** interrupt 후 프롬프트 복귀 | **미통과** | 블로킹 중 `interrupt_interactive` 를 걸자 세션이 **죽었다**(exit 130). 원인은 후보의 트레이스백이 지목한다: `pkill -SIGINT connect` → `_connect.py:66` 의 `NetcatShell().cmdloop()` 이 `KeyboardInterrupt` 를 잡지 않는다. **모델이 부를 수 있는 interrupt 명령은 없다**(명령 집합에 0건; `TimeoutError` 경로에서만 내부 호출). tty 가 없으므로 VINTR 경로가 아니다 |
| **B-8** 닫힌 뒤 참조 | **통과** | `connect_stop` 뒤 `connect_sendline` → `"Interactive session connect is not running!"`, `silently_created_new_session=false`. **E 에는 `session_id` 가 없어** '닫힌 id 참조'가 아니라 '닫힌 뒤 참조'를 시험했다 |

**§4.1 의 네 요구에 대한 최종 관측: 1·2·3·4 전부 만족.** 단 **2와 3은 E-07 이후**이고,
패치 이전에는 2가 실패, 3이 평가 불가였다.

**측정 설계에서 정직하게 적을 것 둘.**

1. **B-2 의 peer 는 우리가 골랐다.** 전송 A 의 원래 peer 는 gdb 인데 gdb 는 받은 raw
   바이트를 기록하지 않는다. `cmdline` 은 후보 자신의 `get_interactive_session` 의
   **인자**이므로 전송 코드 경로(Popen · `docker exec -i` · `os.write`)는 gdb 세션과 한
   글자도 다르지 않다. T 가 pty 세션을 `bash` 로 열고 그 안에서 기록한 것과 같은 자리다.
2. **B-3 의 `pgid_only_would_have_missed` 는 `[]` 였다.** 즉 이 구성에서는 pgid 만
   정리해도 백그라운드 잡을 놓치지 않았다 — gdb 의 `shell` 이 job control 없는 비대화형
   `sh` 를 띄워 잡이 리더와 같은 프로세스 그룹에 남기 때문이다. **커널 세션(sid) 경계가
   여기서 결정적이었다고 주장하지 않는다.** 계약이 요구하는 경계라서 그것을 썼고, G·T 가
   `bash -i` 에서 관측한 "pgid 만으로는 놓친다"는 E 의 이 경로에서는 재현되지 않았다.

**부수 관측 — 판정에는 넣지 않는다.** 세션이 없는 상태에서 `connect_stop` 을 부르면
`swe_env.py:535` 가 `self.interactive_session.session_process` 를 None 검사 없이 만져
`AttributeError` 로 죽는다. 같은 "닫힌 뒤 참조"인데 io 계열은 곱게 거부하고 stop 은 죽는
비대칭이다.

### 12.4 세 번째 구조 패치를 **쓰지 않기로 판정했다** — 근거

부팅 지시는 "남은 2개 중 하나가 §4.2(동시 세션)에 쓰일 가능성이 높다"고 예고했다.
**쓰지 않았다. 반대한 근거를 적는다.**

1. **동시 세션 2개는 어떤 seam 판정도 바꾸지 않는다.** S4 의 통과 술어는 (1회 실행)·
   (지속 세션)·(상태 있는 HTTP)·P-S4-a 넷이고 어느 것도 동시성을 요구하지 않는다.
   S6·S9 도 마찬가지다 — S9 의 `op_id`(개정 A-2)는 "동시 연산이 끼어들 수 있는 구현은
   필수, 그렇지 않으면 생략 가능"이라 **E 처럼 상한이 1인 구현에는 요구되지 않는다.**
   §10.1 의 생존 조건은 **seam 단위**이므로, seam 을 바꾸지 않는 패치는 생존 범위를
   넓히지 못한다.
2. **B-7 도 같다.** interrupt 는 §4 의 명명된 연산이지만 seam 의 PASS 술어에 들어 있지
   않다. 고치려면 `config/commands/_connect.py` 에 `KeyboardInterrupt` 처리를 넣어야 하고,
   그것은 후보의 도구 구현 변경이다.
3. **쓰면 재는 것이 바뀐다.** 동시성을 우리가 넣으면 §4.2 가 재는 것은 **E 의 동시성이
   아니라 우리가 E 에 심은 동시성**이 된다. 그 사실은 §12.2-3(KEEP/WRAP/REWRITE)에
   들어가야 할 관측인데, 패치로 덮으면 사라진다.
4. **예산이 남았다는 것은 쓸 이유가 아니다.** 남은 1개는 그대로 남긴다.

**따라서 E 의 구조 패치 누계는 2 (E-05, E-07) 이고 1 이 남아 있다.**

> **계수의 이견을 함께 싣는다(§9.6-3).** E-07 은 **세 종료 지점**(STOP 분기,
> `_terminate_interactive_session`, `close()`)에 같은 정리 호출을 넣는다. 이 세션은 그것을
> **하나의 상태 모델 변경**으로 세었다 — 세션 E 가 E-05 를 두 곳 고치고 하나로 센 것과
> 같은 기준이다. 호출 지점마다 따로 세는 더 엄격한 해석을 취하면 **구조 3개**가 되고,
> 거기에 §1 (c)의 격리 해석까지 엄격하게 취하면 **4개가 되어 예산을 넘는다.** 그 경우
> §9.3 대로 해당 유형은 FAIL 이다. **이 세션의 판정은 2개**이고, 근거는 (i) 하나의 결함에
> 대한 하나의 수정이며 (ii) 세 지점 모두 "세션이 끝나는 자리"라는 같은 의미를 갖는다는
> 것이다. **두 계수를 다 적었으므로 뒤 세션이 다시 판정할 수 있다.**

### 12.5 예상 (b) 의 판정 — **확증**

반증 조건은 run 전에 `arms/E/PREREG-2.md` §1.2 에 적고 커밋했다(`94fc44d`).

| | 규칙 | 관측 | 판정 |
|---|---|---|---|
| 확증 | 정상 스트림 **전부**에서 `N_open >= 1` | 4/4 에서 `N_open = 1` | **확증** |
| 반증 | 정상 스트림 **전부**에서 `N_open = 0` | 해당 없음 | |
| 부분 | 갈리면 비율을 적는다 | 해당 없음 | |

`N_act`(모델이 낸 행동 텍스트에 `connect_start` 가 들어간 수) 도 4/4 에서 **1**.
대조용 `N_prompt`: 후보의 `.traj` 전체에 `connect_start` 가 **5회** 나타나고 그중
`connect_start kisia-fix-b 9101` 이라는 **완성된 문장이 프롬프트에 실려 있음을 확인**했다
(`utils.py:748-760` 의 `set_server_description`). (b)의 근거가 run 시점에도 성립했다.

**T 와 정확히 반대다.** T 는 4 run 전부에서 `session_open` 이 대화 로그에 **0회**였고
(`ARM_T_REPORT.md` §1.4.1), E 는 4 run 전부에서 모델이 세션을 열었다. 세션 E 가
`PREREG.md` 에서 "T 와 정반대 방향"이라고 적은 예상이 **맞았다.**

**배관 판정과 통합 판정을 나눠 적는다** (T 가 §1.4 에서 두 문장으로 가른 그대로):

1. **배관** — E 의 세션 계층은 §4.1 의 네 요구를 만족한다(§12.3). 단 **E-07 이후**이고,
   §4.2 의 "2개 이상"은 만족하지 못한다.
2. **통합** — 그리고 **모델이 그 배관을 실제로 쓴다.** T 에서 이 두 문장이 갈렸던 자리가
   E 에서는 갈리지 않는다. 이것이 유형 B 에서 T 와 E 를 가른 실질적 차이다.

### 12.6 프로브를 켜면 점수가 **오른다** — T 와 반대 방향의 같은 현상

`ARM_T_REPORT.md` §1.6-2 는 "하니스 프로브가 세션을 스트림에 넣는 순간 S6.2 가
공허참(만족) → 증거 없음(FAIL) 으로 바뀐다"고 적었다. **E 에서는 방향이 반대다** —
프로브를 켜면 S4.4(P-S4-a)가 증거를 얻어 `증거 없음` → `만족` 이 된다(`b2`·`b3` 5/7 vs
`b1`·`b4` 6/7).

**같은 성질의 두 얼굴이다:** 프로브의 존재가 술어의 **평가 가능성**을 바꾸고, 그것이
arm 의 행동과 무관하게 점수를 움직인다. 집합 판정이 넷을 다 넣어 판정하는 것이 더 정확한
답이고(§6 개정 A-8), 그래서 §12 의 표는 집합 값을 싣는다. **술어의 성질이지 arm 의
성질이 아니며, 계약을 고치지 않고 관측으로만 남긴다**(§9.6-1).

---

## 13. 판정 — E × 유형 C (세션 E-2)

| | S2 | S4 | S6 | S7 | S8 | S9 | 계 |
|---|---|---|---|---|---|---|---|
| **E / 유형 C (집합, 4 스트림)** | PASS(patch 2) | PASS(patch 2) | **FAIL(S6)** | **FAIL(S7)** | PASS(patch 2) | PASS(patch 2) | **4/6** |
| 참고 — T / 유형 C (집합, 4 스트림) | PASS(patch 3) | PASS(patch 3) | **FAIL** | **FAIL** | PASS(patch 3) | PASS(patch 3) | **4/6** |

**T 와 판정표가 같다.** 다른 것은 구조 패치 수(2 vs 3)뿐이다.

### 13.1 스트림별 판정과 FAIL 근거 seq

| run | 호출 | USD | S2 | S4 | S6 | S7 | S8 | S9 | 계 | FAIL 근거 seq |
|---|---|---|---|---|---|---|---|---|---|---|
| `…175318Z-c1` | 5 | $0.0233 | ● | **F**(S4.3) | **F**[no-ev] | **F** | ● | ● | 3/6 | S4.3 `[17,38]` · S7.1 `[46]` |
| `…175440Z-c2` | 4 | $0.0175 | ● | **F**(S4.3) | **F**(S6.4) | **F** | ● | ● | 3/6 | S4.3 `[31]` · S6.4 `[17,31]` · S7.1 `[41]` |
| `…175553Z-c3` | 5 | $0.0229 | ● | **F**(S4.3) | **F**[no-ev] | **F** | ● | ● | 3/6 | S4.3 · S7.1 `[46]` |
| `…175714Z-c4` | 4 | $0.0159 | ● | **●** | **F**[no-ev] | **F** | ● | ● | 4/6 | S7.1 `[39]` |
| **집합 (넷)** | **18** | **$0.0796** | ● | **●** | **F** | **F** | ● | ● | **4/6** | |
| `…180331Z-c4neg` **개입** | 4 | $0.0220 | — | — | — | — | — | — | — | §13.3 |

**S4 가 집합에서 PASS 인 이유**는 S4.3 을 "집합 안의 어느 스트림 하나가 만족시키면 만족"
하는 프로브 술어로 다루기 때문이다(`CHECKER.md` §1.2). **4 중 1 에서만 관측됐다는 사실이
칸에 나타나지 않으므로 여기 적는다** — T 가 4 중 2 였던 자리이고, **이 지표만 보면 E 가
T 보다 나쁘다.**

**S6 은 집합에서 FAIL 이다.** S6.4 는 상시 술어라 정상 스트림 **전부**가 만족해야 하는데
`c2` 가 거짓이다(`seq [17,31]`). 나머지 셋의 S6.5(P-S6-a)는 증거 없음이고 그 증거는
개입 run 에 있어야 하는데 §13.3 이 그 결과를 적는다.

**네 스트림 모두 S1.2 를 거짓으로 낸다** (`files[]` 가 비었다). **판정에 들어가지 않는다** —
유형 C 는 `/input` 에 파일을 두지 않고 하중표의 S1 칸이 비어 있어 S1 이 `N/A` 다
(`FIXTURES.md` c-web `inputs: []`). T 에서도 같았다.

### 13.2 항아리 예상의 판정 — **결과는 반증, 기제도 반증**

반증 조건은 run 전에 `PREREG-2.md` §2.2 에 적고 커밋했다. **결과와 기제를 따로 판정한다.**

| | 규칙 | 관측 | 판정 |
|---|---|---|---|
| **결과** | 확증 = 전부 `chain` 성립 / 반증 = 절반 이상 불성립 | 4 중 **1** 성립 (3 불성립) | **반증** |
| **기제** | 반증 = 한 행동에 `curl` 이 2개 이상 실린 사례가 **한 번이라도** 관측되면 | `c1` seq 14 가 `curl … && curl … && curl …`, `requests_in_this_command = 3` | **반증** |

**세션 E 의 예상은 틀렸다.** "E 의 프롬프트가 한 번에 한 명령만 쓰라고 못박고
`ThoughtActionParser` 가 코드블록 하나만 파싱하므로 세 요청을 몰기 어렵다"는 추론은
**한 명령 안의 셸 연산자를 계산에 넣지 않았다.** 파서가 코드블록 하나만 받는 것과 그 블록
안에 명령이 몇 개인지는 **다른 문제**이고, 모델은 `&&` 로 셋을 한 블록에 넣었다. T 의
`c2`·`c3` 와 **같은 모양**이다.

**그리고 T 에 없던 셋째 기제가 관측됐다.** `c4neg` 의 세 번째 명령은 항아리를 아예 쓰지
않고 `sid` 를 응답 헤더에서 뽑아 **셸 변수**로 나른 뒤 `-H "Cookie: sid=$sid"` 로 보낸다.
**상태가 파일이 아니라 셸 변수에 있으면** 항아리 digest 로 관측할 대상이 존재하지 않는다 —
어댑터의 게으름이 아니라 에이전트가 고른 표현의 성질이다. `PREREG-2.md` §2.2 가 "셋째
경우"로 미리 적어 둔 칸이고, **T 가 만난 것과 다른 기제이므로 반증으로 접지 않고 따로
적는다.**

**항아리 digest 의 의미를 어댑터에서 갈랐다.** `absent`(관측됨 — 그 시점에 파일이 없었다)와
`null`(관측하지 못했다 — 상대 경로이거나 셸 변수라 볼 위치를 특정할 수 없다)을 다른 값으로
싣는다. 처음 코드는 둘을 `None` 으로 접었고, 상대 경로 `cookies.txt` 에 대해 하마터면
"없었다"고 **거짓 관측**을 적을 뻔했다 — 우리 `docker exec` 의 cwd 가 에이전트 셸의 cwd 와
다르기 때문이다. 세션 E 가 스윕에서 밟은 것과 같은 종류의 함정이다(§5).

### 13.3 C-4 (P-S6-a) — **개입을 확인하지 못했다.** 실패했다고 적지 않는다

T 는 §1.6-1 에서 "항아리를 버렸으나 재시도하는 에이전트가 회복했다"고 적었다. **E 에서
같은 결론을 적을 수 없다** — 그렇게 적으려면 항아리가 실제로 버려졌음을 먼저 보여야 하는데
**세 번의 시도에서 한 번도 확인하지 못했다.**

| 시도 | 무엇을 했나 | 결과 |
|---|---|---|
| 1 | `rm -f <에이전트가 쓴 경로>` | 경로가 상대(`cookies.txt`)라 우리 `docker exec` 의 cwd 와 달랐다. **삭제 확인 없음** |
| 2 | basename 으로 `find / -xdev` 후 삭제 + 부재 확인 | `-xdev` 가 `/tmp`(tmpfs)·`/work`(bind mount)를 건너뛴다. **0건** |
| 3 | `-xdev` 제거, `/tmp /work /root /output /` 를 `-maxdepth 6` 으로 | **여전히 0건** |

**배제된 것:** cwd 불일치(basename 검색으로 해소), 파일시스템 경계(`-xdev` 제거).
**남은 가설:** 그 시점에 항아리 파일이 **존재하지 않았다** — 세 번째 명령이 항아리를 쓰지
않고 `sid` 를 셸 변수로 나르는 것이 관측됐고(§13.2), 그렇다면 버릴 대상 자체가 없다.

**같은 실패를 두 번 고치지 못했으므로 멈추고 보고한다.** 기록은 이렇다:
`jars_dropped=[]`, `any_drop_confirmed=false`, `outcome=solved`.
**"개입했는데 attempt 가 실패하지 않았다"가 아니라 "개입을 확인하지 못했다"** 이고, 둘을
같은 값으로 접으면 §0.1-2 를 스스로 어긴다. **S6.5 는 유형 C 의 어느 스트림에서도
만족되지 않는다.**

**fixture 를 고치지 않았고, 고칠 근거도 나오지 않았다.** 고치려면 세션 B 의 음성
프로브(`FIXTURES.md` §5.3)와 세션 C 의 재현(`CHECKER.md` §1.3)을 **둘 다 뒤집는 관측**이
필요한데, 이 세션이 낸 것은 그 둘과 무관한 **우리 개입 경로의 한계**다. "재로그인만으로
`/vault` 가 열리는가"도 확인 대상이었으나, 개입이 확인되지 않았으므로 그 질문에 답할
관측도 얻지 못했다. **T 의 §1.6-1 이 E 에서 재현됐다고 적지 않는다.**

### 13.4 프로브별 결과

| id | 결과 | 근거 |
|---|---|---|
| **C-1** 로그인→상태→flag | **통과** | 4 run 전부 `outcome=solved`. `c4` 에서 항아리 연쇄가 세 요청을 가로질러 이어졌다 |
| **C-2** `target_id` 확인 | **통과** | 5 run 의 모든 `http.exchanged` 가 `target_id=kisia-fix-c`, `declared_target=true`. 선언 대상 밖 요청 **0건** |
| **C-3** 미선언 host:port | **통과** | 러너가 매 run **컨테이너 안에서** 양방향으로 돈다. 선언 대상 연결, `1.1.1.1:80`·`93.184.216.34:443` 거부 → `scope.refused{attempted_from:"container"}` 2건. 세션 C 가 arm 없이 확인해 둔 조건이 arm 위에서 재현됐다 |
| **C-4** 쿠키 버리기 (음성) | **개입 미확인** | §13.3 |
| **C-5** 동시 요청 2개 | **시도하지 않음** | 판정에 넣지 않는 항목(§5). E 의 도구 계층은 markdown 코드블록 하나이고 `ThoughtActionParser` 가 블록 하나만 파싱하므로 도구 계층에서 동시 요청을 표현할 수 없다. 가능한 것은 한 명령 안의 셸 동시성뿐이고 그것은 E 의 동시성이 아니라 bash 의 동시성이다 — **T 와 같은 결론, 다른 이유**(T 는 `parallel_tool_calls: False` 고정) |

---

## 14. 패치 (세션 E-2 시점) — 구조 **2** / 사소 **5**

| # | 종류 | 무엇을 | 어느 세션 | 근거 |
|---|---|---|---|---|
| E-01 | 사소 | `swebench==2.1.0` 고정 | A | §3 |
| E-02 | 사소 | `models.py` 에 `gpt-5.6-terra` 추가 | A | §3 |
| E-03 | 사소 | `docker/enigma.Dockerfile` 로 빌드 | A | §3 |
| E-04 | 사소 | 이미지에 `flake8` 을 굽는다 | E | §3.2 |
| **E-05** | **구조 1/3** | 정답 주입 제거와 성공 판정의 외부화 | E | §3.1 |
| E-06 | 사소 | `reasoning_effort` 를 요청에 싣는다 | E | §3.3 |
| **E-07** | **구조 2/3** | **세션 close 가 컨테이너 안의 자손을 거둔다** | **E-2** | §12.3·§12.4 |
| E-08 | 사소 | `models.py` 에 `gpt-5.6-luna` 추가 (A-5) | **E-2** | §15 |

diff: `arms/E/patches/E-07-structural-session-reap.diff`,
`arms/E/patches/E-02-E-06-E-08-minor-models.diff`. 적용 스크립트는 전부 **멱등**이고 앵커가
어긋나면 조용히 실패하지 않고 죽는다.

**후보 소스의 총 변경은 2파일이다** (`git diff --stat`: `models.py` +17, `swe_env.py`
+197/−13). 참고로 T 는 5개 패치였고 **T-08 하나가 584줄**이었다. E-07 이 커진 이유는
정리기를 컨테이너 **안에서** 돌려야 해서 스크립트를 상수로 안고 있기 때문이다.

### 14.1 E-07 — **구조.** 예산 2/3

**관측이 근거다. 한 원인이 네 자리에서 터졌다:** B-3(§4.1-2 생존자), B-4(§4.1-3 평가
불가), S2.5(`surviving_processes=1`), S4.4(`descendants_killed > 0` 인 close 없음).

E 의 close 는 `session_process.terminate()` 이고 그것은 **호스트의 `docker exec`
클라이언트**에 SIGTERM 을 줄 뿐이다. `docker exec` 는 클라이언트가 죽어도 컨테이너 안의
프로세스를 죽이지 않으므로 세션 리더와 자손이 그대로 남는다. **E 에는 컨테이너 안을 거두는
코드가 한 줄도 없다.**

**설계에서 계약이 강제한 것 — `ARM_T_REPORT.md` §3.5 의 셋을 그대로 적용했다.**

- **경계는 커널 세션(sid)이다.** §4.1-2 가 "`&` 로 띄운 잡이 포함된다"고 요구하므로 pgid 가
  아니라 sid 로 잡는다. (다만 E 의 이 경로에서는 pgid 로도 충분했다 — §12.3 의 측정 설계
  주의 2.)
- **좀비는 생존자가 아니다.** 상태 `Z` 를 빼고 grace 도 좀비 때문에 쓰지 않는다(§4.1-3).
- **리더를 close 가 아니라 open 에서 정한다.** 이것이 이 패치에서 가장 비쌌던 진단이다.
  close 시점에 이름으로 찾으면 **늦다** — `terminate()` 가 클라이언트를 죽이면 gdb 는
  stdin EOF 로 함께 죽고 `connect_stop` 은 그 전에 이미 `quit` 을 보낸다. 그러면 이름으로
  찾을 대상이 사라진 뒤이고 **고아만 남는다**(실측: gdb 는 사라지고 `sleep` 만 생존,
  `descendants_killed=0`). 고아는 sid 를 그대로 물려받으므로 open 에서 sid 를 잡아 두면
  리더가 죽은 뒤에도 정확히 거둘 수 있다.

**세 종료 지점 전부에 건다.** STOP 분기, `_terminate_interactive_session`, 그리고
**`close()`** — 모델이 `connect_stop` 을 부르지 않고 끝내면 정리는 거기밖에 남지 않는데,
E 는 거기서도 클라이언트만 죽이면서 로그에는 `"Interactive session stopped"` 라고 적는다.
**후보의 자기 보고가 틀리는 자리이고**(§0.1-3), 실측에서 그것이 S2.5 를 깨뜨렸다.

**분류 근거 — 구조.** §9.3 의 넷 중 **상태 모델**을 바꾼다: 세션 생애주기에 "정리"라는
단계가 없었는데 생긴다. 관측을 더하는 것이 아니라 **행동을 바꾸므로** 어댑터가 아니다.
하니스가 밖에서 대신 죽이는 길도 있었으나 그러면 S2.5 가 재는 것이 **E 의 정리 능력이
아니라 우리의 정리 능력**이 되므로 그렇게 하지 않았다.

**후보의 보고를 증거로 쓰지 않는다.** 이 패치는 `descendants_killed` 를 내지만
`survivors` 의 **판정값은 여전히 하니스가 컨테이너 밖에서 읽은 값**이고, 후보의 보고는
`survivors_self_reported` 로 나란히 실린다. **두 값은 모든 close 에서 일치했다**(불일치 0).

### 14.2 E-08 — **사소.** 그리고 P-S3-a 의 문면과 화해시키는 자리

§15 가 결과를 적는다. 요지: **E 의 모델 레지스트리는 YAML 이 아니라 소스 안이다**
(`models.py:191` `OpenAIModel.MODELS`; v0.7.0 은 gpt-5.x 이전이라 표가 코드에 박혀 있다).
따라서 P-S3-a 의 "**후보 소스를 고치지 않고**"는 **문면 그대로는 만족되지 않는다.**

**그러나 S3 의 FAIL 조건은 다른 것을 가리킨다** — "provider 이름이 후보의 **제어 흐름**에
박혀 있어 P-S3-a 에 소스 수정이 필요한 경우". 여기서 고치는 것은 제어 흐름이 아니라
**단가 표의 행 하나**(`max_context` 와 토큰당 비용)다. 분기도, provider 선택도, 요청
조립도 바뀌지 않고 `--model_name` 이 그대로 모델 id 가 된다.

**그래서 판정을 이렇게 적는다: 통과하되 사소 패치 1개가 필요하다.** "무패치 통과"로 적으면
§9.6-3 을 스스로 어긴다. **T 는 이 문제가 없었다**(모델 목록이 YAML) — 그 차이 자체가
§12.2-3 에 들어갈 관측이다.

---

## 15. run 기록 (§9.4) — 세션 E-2

**공통 통제 조건** — 유형 B·C 의 기록 run 전부 동일:

```
arm E / challenge kisia-fix-b-session · kisia-fix-c-web
model  gpt-5.6-terra   model_snapshot gpt-5.6-terra   (A-5 만 gpt-5.6-luna)
profile foundation-spike / endpoint /v1/chat/completions
requested_reasoning_effort none / effective none (전 run reasoning_tokens=0)
tool_protocol  markdown-code-block (ThoughtActionParser); function tools 없음
temperature 1.0 / top_p 1.0
config_file  config/ctf/ctf_misc.yaml (유형 B) · config/ctf/ctf_web.yaml (유형 C)
image  sweagent/enigma:spike-kisia
network  kisia-fixnet(선언) + ctfnet(E 가 하드코딩으로 붙인다, --internal)
rootfs read-only / usd_budget 1.0
구조 패치  E-05, E-07 (2개)
```

**세션 E-2 는 28 run 을 돌렸다** (기록 9 · 보조 12 · 폐기 7). 세션 E 의 9 run 을 합쳐
누계 37 run, **누적 지출 $0.4722** (세션 E $0.1010 + 세션 E-2 $0.3712). 상한 $150.

### 15.1 폐기한 run 일곱과 그 이유 (§9.6-4 — 전부 보존했다)

**전부 우리 코드의 성질을 잰 것이지 arm 의 성질이 아니다.** 다섯은 모델 호출 전에 죽어
지출이 $0 이다.

| run | 무엇이 잡았나 | 실제 원인 | 고친 것 |
|---|---|---|---|
| `E-b-…170025Z-b1` | `TypeError: _emit() got multiple values for argument 'kind'` | shim 의 `_emit(kind, **fields)` 가 `session.opened` 의 **계약 필드 `kind`** 와 충돌. 세션 E 가 써 두었으나 유형 A 에 세션이 없어 **한 번도 행사되지 않은** 줄이다 | 위치 인자를 `_kind` 로 |
| `E-b-…170324Z-b1` | 검사기 S6.3 거짓 `[43,44,51,52,59]` | **같은 충돌의 두 번째 얼굴.** `**fields` 가 레코드의 `kind` 를 **덮어써서** adapt 가 세션 open 을 통째로 버렸다 — `session.opened` 가 스트림에 **하나도 없는** 조용한 거짓 음성 | 계약 필드를 `sess_kind` 로 옮기고, **충돌하면 죽도록** `_emit` 에 가드를 넣었다 |
| `E-c-…174212Z` ~ `174424Z` (4건) | `ValueError: Reference at 'refs/heads/master' does not exist` | 유형 C 는 `/input` 에 파일을 두지 않아(`inputs: []`) stage 할 것이 없고, 커밋이 없으면 ref 도 없다 | `prepare_repo` 가 HEAD 가 없으면 빈 커밋으로 ref 를 만든다 |
| `E-c-…175843Z-c4neg` | C-4 개입이 스트림에 실리지 않음 | 개입 레코드에 `ts` 가 없어 adapt 의 drain 이 `None` 비교로 죽었다 | 레코드에 `ts` 를 싣고, adapt 는 앞 레코드 시각으로 떨어뜨린다 |

**보조로만 쓴 run 12건**은 (i) E-07 적용 전, (ii) E-07 이 두 종료 지점만 덮던 중간 상태,
(iii) 항아리 의미(`absent` / `null`) 구분 전에 돈 것이다. **기록 판정에 넣지 않았다** —
같은 유형의 스트림을 서로 다른 어댑터 버전으로 섞으면 집합 판정이 무엇을 재는지 흐려진다.

**검사기가 틀렸다고 판단한 곳은 없다.** 위 넷 다 계약이 요구하는 사실인데 어댑터가
빠뜨린 것이고, 검사기는 그것을 정확히 지목했다. 오탐 0건. **세션 C 의 예고가 세 번째로
맞았다**(`CHECKER.md` §8: "어댑터가 가장 먼저 걸릴 곳은 연산은 했는데 이벤트를 내지 않았다").

### 15.2 §9.4 가 요구하는 나머지 항목

| 항목 | 유형 B | 유형 C |
|---|---|---|
| 세션 유지 성공률 | **4/4** — 모델이 연 세션이 4 run 전부에서 모델 턴 3회를 가로질러 살아 있었다 | **N/A** — 세션을 열지 않는다(`N_open = 0`). 상태는 쿠키 항아리다 |
| 프로세스 잔존 수 | **0** (4 run 전부, 후보 밖 검사기 확인). **E-07 이전에는 1** | **0** (5 run 전부) |
| 컨텍스트 초과 | 0 | 0 |
| 272K 경계 초과 | **0** (최대 입력 4,632/run) | **0** |
| 타임아웃 | 0 (최장 wall clock 30.3초) | 0 (최장 34.9초) |
| cleanup 실패 | 0. 컨테이너 잔존 0 | 0 |
| flag 후보와 출처 관찰 id | `kisia{c41d_9e2f7b06}` — 4 run 전부 `derived_from=null` (`method="model_message"`) | 4 run 전부 `derived_from=null` |
| verifier 판정 | 전 run `verdict=false` 1회(P-S8-a) + `verdict=true` 1회 | 같다 |
| 모델 호출·토큰·USD | 23회 / $0.0386 | 18회 / $0.0796 (+ c4neg 4회 / $0.0220) |
| **web search 사용 여부** | **미사용.** `search.performed` 0건. E 의 명령 집합에 웹 검색 도구가 없다(`config/commands/search.sh` 는 **파일 내 검색**이다). `EVAL_CONTRACT.md` 의 "write-up 유래 flag" 해당 사례 없음. **질의 원문: 없음** | 같다 |

### 15.3 A-5 / P-S3-a — **통과. 단 사소 패치 1개가 필요하다**

`--model_name` 만 바꿔 유형 A 를 한 번 더 돌렸다. **비교의 두 스트림은 패치 집합이 같다** —
처음에는 세션 E 의 terra run(구조 `["E-05"]`)과 비교했으나 그러면 모델 id 말고도 다른 것이
바뀌므로, **현재 패치 집합에서 terra 를 다시 돌려** 짝을 맞췄다(§9.6-2).

| 스트림 | `model_id` | `model_snapshot` | 구조 패치 | 검사기 |
|---|---|---|---|---|
| `E-a-…180819Z-a5terra` | `gpt-5.6-terra` | `gpt-5.6-terra` | `["E-05","E-07"]` | **7/8** |
| `E-a-…180630Z-a5luna` | `gpt-5.6-luna` | `gpt-5.6-luna` | `["E-05","E-07"]` | — |

**`model_id` 와 `model_snapshot` 이 둘 다 바뀐다** — 요청이 실제로 다른 모델에 갔다는 뜻이고,
provider 어댑터가 core loop 밖에 있다는 S3 의 요구가 성립한다. 검사기는 P-S3-a 를
`스트림 밖`으로 보고하므로(교차 스트림 술어) 이 대조는 손으로 했다.

**문면과의 불일치는 §14.2 에 적었다.** 레지스트리가 소스 안이라 **E-08(사소) 한 줄이
필요했고**, 그 사실을 숨기지 않는다.

---

## 16. 검사기 밖에서 한 번 더 대조

`ARM_T_REPORT.md` §6.1 의 경고: 어댑터가 토큰과 `usd` 를 **같은 잘못된 값에서** 계산하면
스트림이 자기 일관적이라 검사기가 통과시킨다.

### 16.1 후보의 자기 회계 vs 우리 스트림 — **과대 폭이 캐시 적중률을 따라간다**

| 유형 | 토큰 대조 | 후보 `total_cost` | 우리 `usd` | 배율 | 캐시 적중 |
|---|---|---|---|---|---|
| A (세션 E) | **완전 일치** | $0.10547 | $0.0157 | **6.7배** | 98.9% |
| **B** | **완전 일치** (`tokens_sent`·`tokens_received`·`api_calls` 셋 다) | $0.055948 | $0.0100 | **5.60배** | 97.6% |
| **C** | **완전 일치** | $0.156996 | $0.0233 | **6.75배** | 98.3% |

**세션 E 의 예상대로 폭이 유형마다 달랐고, 그 값 자체가 관측이다.** 후보의 `update_stats`
는 `cached_tokens` 를 전혀 구분하지 않고 `in_price×tokens_sent + out_price×tokens_received`
를 계산하므로, **캐시 적중률이 높을수록 과대 폭이 커진다.** 유형 B 가 가장 낮은 것은 이
유형의 프롬프트가 가장 짧아(최대 입력 4.6K) 캐시 접두사 비중이 상대적으로 작기 때문이다.

**T·E 두 arm 이 같은 결함을 갖는다**(T 는 약 46% 과대). `REPRO_MATRIX.md` §5 에 기록한다.

### 16.2 `survivors` — 세션 E 때와 달리 **대조 대상이 생겼다**

세션 E 는 "E 가 이 값을 내지 않으므로 대조 대상이 아니라 하니스 관측 하나뿐"이라고 적었다.
**E-07 이후에는 후보도 이 값을 낸다.** 그래서 T 가 §1.4.2 에서 한 것과 같은 두 값 대조가
가능해졌다:

- 판정에 쓰는 `survivors` 는 **여전히 하니스가 컨테이너 밖에서 읽은 값**이다(§0.1-3).
- 후보의 값은 `survivors_self_reported` 로 나란히 싣는다.
- **모든 close 에서 두 값이 일치했다. 불일치 0.**

`descendants_killed` 는 후보의 반환값이고 대조 대상이 없다 — 그 사실을 필드로 적는다.

### 16.3 유형 A 를 다시 돌려 확인했다 — **E-07 이 유형 A 를 깨지 않는다**

E-07 은 유형 A 의 판정 이후에 들어간 패치이므로, 유형 A 가 그대로인지 확인해야 한다.
`E-a-…180819Z-a5terra`(구조 `["E-05","E-07"]`)의 검사기 판정은 **7/8** 로 세션 E 의 값과
같다. **유형 A 절(§1~§11)을 고치지 않아도 되는 근거가 이것이다.**

---

## 17. §10.1 생존 조건 — **seam 단위 판정 (완성)**

> 선택지 2 (component extraction): **어떤 seam 에서 E 가 §3 계약 뒤에서 구조 패치 3개
> 이하로 통과.** 생존 범위는 **그 seam 에 한정**된다.

**구조 패치 2개로 통과한 seam** (세션 E 의 §7 표를 유형 B·C 까지 채워 완성한 것):

| seam | A | B | C | 생존 범위에 들어가는가 | 근거와 단서 |
|---|---|---|---|---|---|
| **S1** 챌린지 입력 | PASS | N/A | N/A | **예 (유형 A 한정)** | 투입 구조 패치 0. 후보의 `challenge.json` 경로에 어댑터로 먹였다 |
| **S2** workspace 격리 | PASS | **PASS** | **PASS** | **예 — 세 유형 전부** | 단 격리 자체는 **하니스가 세운 것**이고(§1 (c)), 유형 B 의 잔존 0 은 **E-07 이후**다 |
| **S3** 모델 추론 | PASS | N/A | N/A | **예** | P-S3-a 통과. 단 레지스트리가 소스 안이라 사소 패치 1개(E-08), 비용 회계는 다시 써야 한다(§16.1) |
| **S4** 도구 실행 | PASS | **PASS** | **PASS** | **예 — 세 형태 전부** | **유형 A 에서 부분이던 칸이 채워졌다.** 지속 세션은 §12.3, 상태 있는 HTTP 는 §13.1. 단 HTTP 연쇄는 4 중 1 에서만 관측됐다 |
| **S5** 관찰 | PASS | **PASS** | N/A | **부분** | 절단 경로가 **여전히 한 번도 행사되지 않았다** — 유형 B 도 절단된 관찰 0건, 요약기 `api_calls=0`. 세 유형에서 모두 미행사 |
| **S6** 상태 유지 | N/A | **PASS** | **FAIL** | **유형 B 한정으로 예** | 유형 B 는 세션이 턴을 가로질러 살아 PASS. 유형 C 는 S6.4(`c2`)와 S6.5(개입 미확인)로 FAIL |
| **S7** flag 추출 | FAIL | **FAIL** | **FAIL** | **아니오 — 세 유형 전부** | `derived_from=null`. T 와 같은 원인, 세 유형에서 재현 |
| **S8** flag 검증 | PASS | **PASS** | **PASS** | **예** | 단 **E-05 라는 구조 패치를 써서** 통과했다. 추출하면 이 자리는 다시 만들어야 한다 |
| **S9** telemetry | PASS | **PASS** | **PASS** | **예 — 단, 계측 전부가 우리 것이다** | E 의 `.traj` 는 합계만 준다. 계약이 요구하는 봉투는 shim + `adapt_e.py` 가 만든다 |

**선택지 2 의 생존 판정: 생존한다. 범위는 S1·S2·S3·S4·S8·S9 이고, S5 는 부분, S6 은 유형
B 한정, S7 은 생존 범위 밖이다.** 구조 패치는 **2개**로 예산 3 안에 들어왔다.

**막힌 것은 예산이 아니라 seam 이다** — T 에 대해 세션 D-2 가 적은 문장이 E 에도 그대로
적용된다. 다만 T 는 세 유형 전부에 FAIL 이 있어 선택지 1 의 조건("A·B·C **전부** 통과")을
만족하지 못했고, **선택지 2 의 조건은 "어떤 seam"이므로 E 는 위 목록만큼 생존한다.**

---

## 18. 세션 F(arm X)에 넘기는 것

**그대로 쓴다** (`<HOME>/spike-e/adapter/`, 저장소에도 커밋됨):

```
run_b_probes_E.py  §4.1·§4.2 프로브 드라이버. **후보의 세션 계층을 직접 몬다** —
                   X 에 붙이려면 재는 대상을 X 의 세션 API 로 다시 정해야 한다.
                   "import 만 바꾸면 된다"는 T→E 에서 이미 성립하지 않았다
one_run.sh         골든 재실행 → arm run → post_run 을 **한 단위로 강제**한다.
                   손으로 부르면 언젠가 빠뜨린다
patches/apply_E07_structural_reap.py, apply_E08_minor_luna.py   멱등
```

**미리 알고 시작할 것.**

- **어댑터의 조용한 거짓 음성이 이 세션의 가장 비싼 결함이었다.** `_emit` 의 위치 인자가
  계약 필드 이름과 겹쳐 `session.opened` 가 통째로 사라졌고, 검사기는 그것을 S6.3 으로
  잡았지만 **원인은 arm 이 아니라 우리였다.** 이제 `_emit` 은 충돌하면 죽는다. X 의
  어댑터를 쓸 때 같은 검사를 넣어라.
- **"수행하지 못함"과 "0"을 접지 마라.** 이 세션이 세 번 만났다: 항아리 `absent` vs
  `null`(상대 경로), C-4 의 `jars_dropped=[]`(개입 미확인 vs 개입 무효), B-4 의 N/E
  (평가 불가 vs 실패).
- **프로브의 존재가 점수를 움직인다.** T 에서는 내리고 E 에서는 올렸다(§12.6). 집합
  판정으로만 읽어라.
- **X 를 자르면 §10.5 의 우발 조항을 발동시킬 수 없다.** `FOUNDATION_DECISION.md` §9.7-1 이
  X 를 첫 절단 대상으로 정했고 §10.5 는 "X 가 잘린 경우 이 조항은 발동할 수 없다. 그
  사실을 §12 에 적는다"고 했다. **X 를 돌리는 것이 그 조항을 살려 두는 유일한 길이다.**

### 18.1 계약·fixture 에 대해 고쳐야 한다고 판단한 것 — **없다**

- `SEAM_CONTRACT` 를 고쳐야 한다고 판단한 곳 없음. §12.6 의 "프로브가 평가 가능성을
  바꾼다"와 §13.3 의 C-4 는 **관측으로만** 남긴다(§9.6-1).
- fixture·골든을 고쳐야 한다고 판단한 곳 없음. **매 arm run 직전 골든 6개 재실행,
  전부 6/6 PASS**(`one_run.sh` 가 강제한다).
- 검사기가 틀렸다고 판단한 곳 없음. 오탐 0건.
- 후보의 프롬프트를 고치지 않았다.

### 18.2 호스트에 남긴 것 (세션 E 의 §9 에서 달라진 것만)

| 항목 | 값 |
|---|---|
| 디렉터리 | `<HOME>/spike-e/` (runs 37개로 증가, `bprobe-*` 프로브 run 포함). **`spike-d` 를 고치지 않았다** |
| 이미지 | 추가 **0**. `sweagent/enigma:spike-kisia` 그대로 |
| 네트워크 | 추가 **0**. `ctfnet` 은 세션 E 가 `--internal` 로 재생성한 상태 유지 |
| 컨테이너 | 추가 상시 기동 **0**. 프로브·worker 컨테이너는 run 마다 만들고 `docker rm -f` 로 지웠다 |
| 퍼블리시 포트 | **0.** `-p` 없음. `docker-compose.yml` 을 `challenge.json` 옆에 두지 않는 배치를 **유지했다** |
| `ufw` | **미변경** |
| 후보 checkout | `dc18a740` pin 유지. 수정 파일 **2개**(`models.py`, `swe_env.py`) |
| 디스크 | **20%** (63 GB). 착수 시점과 같다 |
| 제품 자산 | 미접근. `<PROTO_HOME>/kisia-agent`, `<PROTO_HOME>/kisia-data` 읽지도 쓰지도 않았다 |
