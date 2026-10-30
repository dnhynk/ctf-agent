# SEAM_IMPLEMENTATION_MAP — 어느 seam이 어느 구현으로 채워지는가

작성일 2026-08-08. `FOUNDATION_DECISION.md` §13.1-2·§13.1-3이 요구한 문서이고,
§12.3 item 3·4가 "문서 세션으로" 넘긴 확정표다. 표제는 §12.3이 이미 고정했고 이 문서는
그것을 **seam 단위와 파일 경계로** 확정한다.

판정 라벨은 [pack §12.3]의 다섯이다: **KEEP / WRAP / REWRITE / REJECT / READ-ONLY.**

---

## 1. 결정과 그 근거의 위치 (§13.1-2)

| 항목 | 값 |
|---|---|
| 전략 | **선택지 2 — component extraction** |
| 추출 대상 | **E = SWE-agent `v0.7.0`, commit `dc18a740faabd2fc625a9b018184dfc4a81cbc78`** (`PINS.md` §1) |
| 추출 범위 | E의 `InteractiveSession` / **유형 B 세션 런타임**에 한정 |
| 승인 | 2026-08-08, dnhynk (`FOUNDATION_DECISION.md` §12.3) |
| 판정표 | `FOUNDATION_DECISION.md` §12.1 (T·E·X·G 전 행), §12.1.a (§10.5 판정) |
| arm 1차 기록 | `ARM_T_REPORT.md` · `ARM_E_REPORT.md`(특히 §12·§13·§17) · `ARM_X_REPORT.md` · `G_REPORT.md` |
| §10.3 후속 의무 | **적용 없음** — 선택지 1 전용 조항 |
| rollback | `FOUNDATION_DECISION.md` §6.5 — `vendor/` 삭제 + 어댑터 재작성. 계약과 그 테스트는 남는다 |

**왜 E인가, 한 문장으로.** E는 **배관(§4.1의 네 요구)과 통합(모델이 실제로 그 배관을
쓰는가)이 둘 다 성립한 유일한 arm**이다 — 정상 4 run **전부**에서 모델이 세션을 열었고
세션이 모델 턴 3회를 가로질러 살았다. T는 같은 4 run에서 세션 도구를 **0회** 불렀고
(프롬프트가 pwntools 한 방짜리를 지시), X도 **0회**였다(아무 지시가 없는데 모델이
`python3` 소켓 스크립트를 골랐다).

---

## 2. seam 단위 확정표

| seam | 판정 | 무엇으로 채우는가 | 근거 |
|---|---|---|---|
| **S1** 챌린지 입력 | **REWRITE** (자작) | 매니페스트 → 러너의 입력 바인딩. 벤치마크 데이터 모델을 쓰지 않는다 | E의 투입 경로는 `challenge.json` + `nyuctf` 데이터 모델에 묶여 있다. 우리는 그 모델을 쓰지 않는다 |
| **S2** workspace 격리 | **REWRITE** (자작) | 컨테이너 생성·마운트·네트워크·정리 전부 우리 것. 규칙은 `PATH_SCOPE.md` §2 | E는 `:ro`도 `--read-only`도 `--network`도 표현하지 못하고 `ctfnet`을 하드코딩으로 붙인다(그 네트워크는 `internal=false`였다). 스파이크에서 격리는 **하니스가 세운 것**이다 |
| **S2** 세션 close의 자손 정리 | **KEEP(범위) / 코드는 우리 것** | E-07이 만든 sid 기반 reaper를 우리 런타임의 close 경로로 옮긴다 | §12.3의 표제가 "E-07의 S2 정리"를 KEEP 범위에 넣었다. **그러나 그 코드는 E의 것이 아니라 스파이크가 쓴 패치다**(§3.4) |
| **S3** 모델 추론 | **REWRITE** (자작) | provider 어댑터, 토큰·비용 회계 | E의 모델 레지스트리는 소스 안에 박힌 단가 표이고(E-08), 자기 비용 회계는 캐시를 무시해 5.6~6.75배 과대다 |
| **S4** 1회 실행 / 상태 있는 HTTP | **REWRITE** (자작) | 도구 계층, 쿠키 항아리 | E의 도구 계층은 markdown 코드블록 파서이고 HTTP 도구가 없다. 항아리 연쇄는 4 run 중 1에서만 관측됐다 |
| **S4·S5·S6** 지속 세션 런타임 | **KEEP (vendored) + WRAP** | §3의 파일 경계. 우리 `InteractiveSession` 어댑터가 감싼다 | **이것이 추출 범위 전부다.** E의 B 6/7, §4.1 네 요구 전부 만족(E-07 이후) |
| **S5** 관찰·절단·artifact | **REWRITE** (자작) | 표시 한도, 절단, artifact 생산 이벤트 | E의 요약기는 5 run 내내 발동하지 않았다(`api_calls=0`). 절단 경로는 T·E 세 유형 전부에서 **미행사** |
| **S6** loop 절반 | **REWRITE** (자작) | agent loop이 매 턴 올바른 상태를 준다 | loop은 추출 대상이 아니다. `spec.md` §0.2가 loop의 형태를 정하지 않는다 |
| **S7** flag 후보 추출 | **REWRITE** (자작) | `candidate.produced` + 파생 검증 | `spec.md` §3의 R2-1. 9개 조합 전부 FAIL이었던 자리이고, 고친 계약을 만족시키는 구현은 아직 없다 |
| **S8** flag 검증 | **REWRITE** (자작) | verifier를 solver 밖 프로세스로. `answer.sweep`은 러너가 낸다 | E는 정답을 solver 프로세스 안에 넣고 틀린 제출마다 로그로 흘린다. **E-05라는 구조 패치를 써서** 통과했으므로 추출하면 이 자리는 다시 만들어야 한다 |
| **S9** telemetry | **REWRITE** (자작) | `TELEMETRY_SCHEMA.md` 전부 | E의 `.traj`는 합계만 준다. 계약이 요구하는 봉투는 스파이크에서도 전부 우리 것이었다 |
| **T** TATAR-LAB `ctf-agents` | **REJECT** | — | 유형 A·B·C **전부**에 FAIL. 구조 패치는 3/3으로 예산 안이었으므로 **막은 것은 예산이 아니라 seam이다** |
| **X** Codex CLI | **REJECT** | — | §10.5 미발동(§12.1.a). S7을 빼도 B의 S4, C의 S4·S6이 독립적으로 막는다 |
| **G** 참조 구현 | **READ-ONLY 참조** | `docs/spike/g-reference/session.py` | 자작 코드이고 §4·§4.1·§4.2를 0 패치로 만족시킨 **존재 증명**이다. 재빌드가 재사용할지는 §8-2 |
| **CTFusion** | **READ-ONLY** | S8 설계의 참조로만 | `FOUNDATION_DECISION.md` §9.1. 실행하지 않는다. 가져오면 저작권 고지가 최대 셋이다 |
| **TATAR의 도구 목록·문서 CSV** | **READ-ONLY, 미채택** | — | 도구 목록 부채를 덜어 주는 유일한 외부 자산이지만(§7.3-2) 이 결정의 범위 밖이다. 채택하려면 **새 결정**이 필요하고 MIT 고지 의무가 따라온다 |
| **SmartData `CTF_agent`** | **READ-ONLY** | 열지 않았다 | LICENSE 미확인 |
| **현 프로토타입 `src/`·`tests/`** | **판정 보류** | — | `FOUNDATION_DECISION.md` §13.3이 재빌드 뒤로 미룬 질문이다. §8-2 |

**요약: vendored는 한 곳뿐이고 나머지는 전부 자작이다.** 이것이 §12.3의 표제
("E 세션 런타임 = KEEP 후보, 나머지 seam = 자작, T = REJECT")를 seam 단위로 편 결과다.

---

## 3. vendor 경계 — 파일 단위

`FOUNDATION_DECISION.md` §6.2-2: 컴포넌트를 `vendor/<candidate>-<commit>/`에 **커밋 단위로
격리**하고, 제품 코드는 **어댑터 파일 하나를 통해서만** 접근한다.

```
vendor/swe_agent_dc18a740/
```

**이름 규칙 (개정 R3-15).** r2는 디렉터리를 하이픈(`swe-agent-dc18a740`)으로, 심볼 경로를
언더스코어(`swe_agent_dc18a740`)로 써서 둘이 이어지지 않았다. **디렉터리 이름을
언더스코어로 통일한다** — 파이썬 패키지 경로가 그것을 강제하고, 디렉터리를 하이픈으로 두면
import 경로와 파일 경로가 갈려 심볼 허용 목록 테스트가 두 이름을 알아야 한다.
규칙: `vendor/<candidate>_<commit12>/`, 소문자, 하이픈 없음. `<commit12>`는 pin된 커밋의
앞 12자다(`dc18a740faab` → 이 경우는 `dc18a740`으로 시작하는 태그 표기와 맞추기 위해
**`dc18a740`** 여덟 자를 쓴다. `PINS.md`가 그 표기를 쓴다).

**원본을 어디서 가져오는가.** `PINS.md` §1의 URL과 커밋에서 새로 clone해 `dc18a740…`을
detached checkout하고, 그중 §3.1의 파일만 복사한다. **호스트의 스파이크 clone
(`<HOME>/candidates/`)을 쓰지 않는다** — 그 트리에는 스파이크가 가한 패치
(E-01·E-02·E-05·E-06·E-07·E-08)가 들어 있고, vendored 원본은 **수정 없는** 것이어야 한다.
복사 후 `git log -1`의 SHA가 `PINS.md`와 일치하는지 확인하고 그 확인을
`REBUILD_LOG.md`에 남긴다.

### 3.1 vendor하는 것

**규칙: 파일을 통째로 가져온다.** 심볼 단위로 잘라 오지 않는다. 변경이 필요하면 §5의
대장에 등재된 패치로만 한다.

**목록이 두 부분이다 (개정 R5-3).** 위 다섯은 **추출 대상 자산**이고, 아래 넷은 그 자산을
import할 수 있게 만드는 **closure**다. 둘을 가르는 이유는 §3.1.a에 있다.

**(a) 추출 대상 자산**

| 파일 | 무엇 때문에 | 근거 |
|---|---|---|
| `sweagent/agent/interactive_commands.py` | `InteractiveSession` 객체와 `INTERACTIVE_SESSIONS_CONFIG`(gdb / connect 두 종류) | `ARM_E_REPORT.md` §1(a) |
| `sweagent/environment/utils.py` | `get_interactive_session`(=`docker exec -i` 로 세션 프로세스를 띄우는 전송 계층), `read_with_timeout`(타임아웃 읽기 원시 연산), `set_server_description`(§3.3) | 같은 곳 |
| `config/commands/_connect.py` | **컨테이너 안**의 pwntools `NetcatShell`. 유형 B의 소켓 세션이 실제로 서는 자리 | 같은 곳 |
| `config/commands/server_connection.sh` | `connect_start` / `connect_sendline` / `connect_exec` / `connect_stop` — 모델에게 노출되는 명령 표면 | 같은 곳 |
| `LICENSE` | MIT 전문. 의무다 | `LICENSE_MATRIX.md` E 행 |

**(b) import closure — 개정 R5-3이 더한다**

| 파일 | 무엇 때문에 | 근거 |
|---|---|---|
| `sweagent/__init__.py` | `PACKAGE_DIR`·`REPO_ROOT`·`CONFIG_DIR`. `utils.py`가 닿는 패키지 뿌리다 | `REBUILD_LOG.md` 재빌드-2 O-6 |
| `sweagent/utils/__init__.py` | 빈 파일. 패키지 경로를 잇는다 | 같은 곳 |
| `sweagent/utils/config.py` | `keys_config` — `get_interactive_session`이 쓰는 `DOCKER_START_UP_DELAY`가 여기서 온다 | 같은 곳 |
| `sweagent/utils/log.py` | `get_logger` — 같은 함수의 `logger.debug` | 같은 곳 |

**넷 다 upstream 바이트 그대로 들어오고, 그중 둘(`config.py`·`log.py`)만 §5의 대장에
등재된 사소 패치를 받는다.**

### 3.1.a 왜 목록이 늘었는가 — 허용 목록이 막지 못하는 것 (개정 R5-3)

**무엇을.** §3.1의 파일 목록을 다섯에서 아홉으로 늘리고, 심볼 허용 목록만으로는 경계가
서지 않는다는 사실과 그 보완(§5의 사소 패치)을 명시한다. **심볼 허용 목록 자체는 셋
그대로다.**

**왜, 그리고 그것을 드러낸 관측 (§8-2).** 재빌드-2가 `vendor/`를 실제로 만들고 import를
시도했다(2026-08-08, `REBUILD_LOG.md` 재빌드-2 §1, `LICENSE_MATRIX.md` §5.4.2).

```
$ python -c "import vendor.swe_agent_dc18a740.sweagent.agent.interactive_commands"
ModuleNotFoundError: No module named 'simple_parsing'
$ python -c "import vendor.swe_agent_dc18a740.sweagent.environment.utils"
ModuleNotFoundError: No module named 'datasets'
```

> **허용 목록은 *우리 코드*의 import를 막는다. *파이썬 import 기계*가 모듈 전체를
> 실행하는 것은 막지 못한다.** 모듈 수준 import는 허용된 심볼이 쓰든 안 쓰든 실행된다.

세 허용 심볼이 **실제로 참조하는 것**을 AST로 닫아서 뽑으면
`Callable PIPE STDOUT os platform shlex subprocess time` — **전부 표준 라이브러리**다
(`get_interactive_session` 본문 11줄, `read_with_timeout` 57줄, `InteractiveSession`은
2필드 dataclass). 그런데 모듈을 적재하면 **세 심볼이 하나도 쓰지 않는** 서드파티 여덟
(`datasets`(HuggingFace) · `ghapi` · `GitPython` · `unidiff` · `docker` ·
`simple_parsing` · `rich` · `config`)과 위 (b)의 파일 넷이 요구된다.

**이것을 그대로 받는 것이 왜 답이 아닌가.** `datasets`는 §3.2가 명시적으로 REJECT한
nyuctf 데이터 모델 결합 그 자체이고, 여덟을 받으면 §6.5의 철수 조건("SWE-agent 0.7 계층을
끌고 오는 범위가 컴포넌트보다 커질 때")에 정면으로 닿는다. **68줄의 표준 라이브러리
코드에 닿기 위해 치르는 값으로는 과하다.**

**그래서 보완이 둘이 된다.** §3.1의 완화 블록이 하나뿐이라고 적은 자리를 고친다.

1. **심볼 허용 목록** — 우리 코드가 무엇을 import하는가. 아래 블록 그대로, 셋.
2. **§5 대장의 사소 패치** — vendored 모듈이 무엇을 요구하는가. `spec.md` §6.1(R3-5)이
   "import 경로"를 개수 제한 없는 **사소 패치**로 분류하고, 그 분류가 여기 쓰인다.
   실적은 `REBUILD_LOG.md` 재빌드-2 §1.2의 `V-02`~`V-05`이고 **구조 패치 누계는 0이다.**

**둘 다 테스트로 강제한다** — `kisia_tests/test_vendor_boundary.py`. 넷째 테스트가
"세 심볼을 import해도 위 여덟이 하나도 딸려 오지 않는다"를 별도 프로세스에서 확인한다.

**§8-3 확인 — 기록된 판정을 뒤집지 않는다.** `FOUNDATION_DECISION.md` §12.1의 어느 칸도
움직이지 않는다. §12.1은 **arm으로서의 E**를 잰 것이고 그때 E는 자기 의존성을 전부 설치한
상태로 돌았다. 이 개정은 그 측정이 아니라 **추출물의 적재 방법**을 정한다. §12.3의 근거
(B 6/7, 정상 4 run 전부에서 모델이 세션을 열었다)도 그대로다.

**§8-5 확인 — 구현을 살리려는 개정인가. 아니다.** 살릴 구현이 아직 없다 — 재빌드-2는
어댑터를 쓰지 않았고 vendored 코드가 스트림을 한 줄도 내지 않았다. 그리고 이 개정은
경계를 **조인다**: 개정 전에는 서드파티 여덟이 제품에 들어오는 것이 §3.1과 어긋나지
않았고, 개정 후에는 **0개**가 요구되며 그 성질이 테스트로 잠긴다.

**이 개정이 §3.5를 무효로 만드는가 — 아니다.** §3.5는 "vendor **표면**이 말보다 작다"를
처리했고, 여기서 드러난 것은 **표면에 닿는 비용**이다. 다른 축이므로 §3.5의 세 논거는
그대로 서고, 이 절이 그 목록에 넷째 항목으로 붙는다.

**파일을 통째로 가져오는 이유 셋.**

1. **upstream과 다시 diff할 수 있어야 한다.** 심볼 단위로 잘라 오면 보안 패치가 나왔을 때
   무엇이 우리 것이고 무엇이 그들 것인지 기계적으로 알 수 없다.
2. **`LICENSE_MATRIX.md`가 요구하는 파일 단위 출처**(§6.2-4)가 그대로 성립한다.
3. **§6.5의 철수 조건**("어댑터를 유지하려고 vendor 원본을 반복 수정하게 되는 시점")이
   관측 가능해진다 — `git diff vendor/`가 비어 있지 않으면 그 조건에 가까워진 것이다.

**대가와 그 완화.** `utils.py`는 우리가 REJECT한 코드도 함께 들여온다
(`_get_non_persistent_container`, `_get_persistent_container`,
`_get_container_mounts_list` — `:ro`·`--read-only`·`--network`가 없고 `ctfnet`이
하드코딩된 바로 그 함수들). 그대로 두면 §6.3-2의 **경계 침식**이 정확히 그 자리에서
일어난다. **완화는 둘이고 둘 다 반드시 있어야 한다 (개정 R5-3 — r3까지는 하나라고
적었고, 그 하나로는 부족하다는 것이 실측됐다. §3.1.a).**

**완화 1 — 우리 코드가 무엇을 import하는가.**

> **심볼 허용 목록을 테스트로 강제한다.** 제품 코드는 `vendor/`에서 아래 세 심볼 외
> 어떤 것도 import하지 않는다. 위반은 테스트 실패다.
>
> ```
> vendor.swe_agent_dc18a740.sweagent.agent.interactive_commands.InteractiveSession
> vendor.swe_agent_dc18a740.sweagent.environment.utils.get_interactive_session
> vendor.swe_agent_dc18a740.sweagent.environment.utils.read_with_timeout
> ```
>
> 디렉터리 이름과 import 경로가 같은 문자열이다(R3-15).
>
> 컨테이너 쪽 두 파일(`_connect.py`, `server_connection.sh`)은 import가 아니라
> **이미지에 구워지는 자산**이고, 경로 규칙은 `PATH_SCOPE.md` §2.3이다.

**완화 2 — vendored 모듈이 무엇을 요구하는가 (개정 R5-3).**

> **모듈 수준 import 표면을 §5 대장의 사소 패치로 좁힌다.** 세 허용 심볼이 참조하지 않는
> 서드파티 import는 제거하고, `sweagent.*` 절대 import는 상대 import로 바꾼다.
> **허용 심볼의 본문은 건드리지 않는다** — 건드리면 그것은 사소가 아니라 구조 패치이고
> §5-3의 계수에 들어간다.
>
> 목표 성질: **세 심볼을 import해도 서드파티가 하나도 딸려 오지 않는다.** 이것도 테스트로
> 강제한다. 완화 1이 "우리가 안 쓴다"를 보장한다면 완화 2는 "적재가 요구하지 않는다"를
> 보장하고, **둘은 서로를 대신하지 못한다.**

### 3.2 vendor하지 **않는** 것 — 그리고 그 이유

| 대상 | 왜 안 가져오는가 |
|---|---|
| `sweagent/environment/swe_env.py` | 1500줄짜리 환경·loop 파일이다. 이것을 들여오면 **SWE-agent 0.7의 환경 계층 전체**가 따라오고, 그것이 `FOUNDATION_DECISION.md` §6.5가 적은 철수 조건("SWE-agent 0.7 계층을 끌고 오는 범위가 컴포넌트보다 커질 때")이다. 세션 관련 세 함수는 §3.4에서 REWRITE로 처리한다 |
| `sweagent/agent/models.py` | 우리 S3와 정면으로 겹친다. 단가 표가 소스 안이고 캐시를 모른다 |
| `sweagent/environment/utils.py`의 컨테이너 생성 경로 | 파일은 들어오되 **심볼 허용 목록으로 차단**한다(§3.1) |
| `sweagent/agent/summarizer.py` | S5는 자작이다. E의 요약기는 5 run 내내 발동하지 않았다 |
| `run.py`, `nyuctf` 결합, `validate_submission`, 정답 주입 경로 | S1·S8이 자작이다. E-05가 끈 자리를 다시 열 이유가 없다 |
| 후보의 도구 이미지(`sweagent/enigma:*`) | 우리 이미지는 `PATH_SCOPE.md` §2가 규정한다. `flake8` 무조건 설치 같은 부수 요구를 물려받지 않는다 |

### 3.3 경계 위의 항목 하나 — 프롬프트 문장

`utils.py:748-760`의 `set_server_description()`은 seam이 아니다. 그런데 **유형 B에서 E와
T·X를 가른 실질적 원인이 이것이다** — 이 함수가 모델에게 주는 문장에 문자 그대로
`connect_start kisia-fix-b 9101`이 들어가고, 그 결과 모델이 4/4 run에서 세션을 열었다.
T는 프롬프트가 반대로 지시해 0/4였고, X는 **아무 지시가 없었는데도** 0/4였다.

> **세션 도구를 노출하고 설명문으로 안내하는 것만으로는 모델이 그것을 쓰게 만들지
> 못한다.** 완성된 호출 문장을 매 턴 프롬프트에 싣는 것이 관측된 차이다.

판정: **KEEP(자산) + WRAP.** 우리 loop은 이 문장의 **형태**(선언된 대상의 host·port를
채운 완성된 호출문)를 유지하되 우리 도구 이름으로 매개변수화한다. 원문을 그대로 복사하면
그것은 MIT 코드의 복사이므로 고지 의무가 따른다 — `LICENSE_MATRIX.md` §5의 파일 목록에
포함시켰다.

**이것을 조용히 버리면 안 되는 이유:** 선택지 2를 고른 근거의 절반이 "통합이 성립한 유일한
arm"이고, 통합을 성립시킨 것이 이 문장이다. 버리면 결정의 근거를 버리는 것이다.

### 3.4 vendored 런타임이 계약을 만족하지 **못하는** 곳 — 재빌드가 만들 것

`spec.md` §4의 여섯 연산 중 **온전한 것은 둘뿐이다.** 나머지는 우리가 만든다.

| §4 연산 | vendored가 주는 것 | 재빌드가 해야 하는 것 | 판정 |
|---|---|---|---|
| `open` | `get_interactive_session` → 세션 프로세스 | **`session_id` 부여**(E에는 식별자가 종류 이름뿐), **배너 보존**(E는 `_ = read_with_timeout(...)`으로 **버린다**) | WRAP |
| `send` | `communicate_session`(send+read **융합**) | **분리.** 융합된 형태로는 `max_bytes`·`timed_out`·`closed`를 표현할 수 없다 | REWRITE |
| `read` | 위와 같음. `read_with_timeout`은 쓸 수 있다 | 독립 `read(timeout_ms, max_bytes)` | REWRITE |
| `interrupt` | `interrupt_interactive`(`pkill -SIGINT`) | **전부.** E의 interrupt는 세션을 **죽인다**(exit 130) — `_connect.py`의 `cmdloop()`이 `KeyboardInterrupt`를 잡지 않는다. 모델이 부를 수 있는 interrupt 명령도 없다. `spec.md` §4.3 | REWRITE (+ vendor 패치 1건 예상) |
| `snapshot` | 없음. `session_process.poll()`이 최근접이고 그것은 **호스트의 `docker exec` 클라이언트**를 본다 | `live`·`pid`·`seq_high`·`bytes_since_open`. **진실은 컨테이너 안의 프로세스 표에 있다** | REWRITE |
| `close` | `terminate()` — **호스트 클라이언트만 죽이면서 로그에는 "Interactive session stopped"라고 적는다** | `transcript_artifact_id`·`exit_status`·`descendants_killed`·`survivors`, 그리고 **sid 기반 자손 정리**(E-07) | REWRITE |
| §4.2 동시성 | **상한 1.** 둘째 세션은 91ms 만에 거부된다 | **세션 레지스트리 전부.** 단 그 슬롯은 `swe_env.py:210`에 있고 우리는 그 파일을 vendor하지 않으므로, **상한 1은 따라오지 않는다**(`spec.md` §4.2, R2-10) | REWRITE |

**E-07(자손 정리)의 출처를 정확히 적는다.** §12.3의 표제는 "E-07의 S2 정리"를 KEEP 범위에
넣었고 그것은 **기능의 범위**를 말한 것이다. 코드로 보면 E-07은 **스파이크가 쓴 패치**이고
(`arms/E/patches/E-07-structural-session-reap.diff`), E의 원본에는 컨테이너 안을 거두는
코드가 **한 줄도 없다.** 따라서:

- 기능은 KEEP 범위 안에 있다.
- **코드는 우리 것**이고 `vendor/` 밖의 우리 런타임에 놓인다.
- 설계 제약 셋은 그대로 물려받는다: 경계는 **커널 세션(sid)**, **좀비는 생존자가 아니다**,
  **리더는 close가 아니라 open에서 정한다**(close 시점에 이름으로 찾으면 늦고 고아만
  남는다).

### 3.5 이것이 §12.3에 반하는 증거인가 — **아니다**

**vendor 표면이 "E의 세션 런타임"이라는 말보다 작다는 사실을 숨기지 않는다.** 여섯 연산 중
넷이 REWRITE이고, 동시성도 우리 것이다. 그런데도 결정에 반하는 증거가 아닌 이유는 셋이다.

1. **전부 결정 이전에 기록돼 있었다.** E의 상한 1, interrupt가 세션을 죽인다는 것,
   `session_id` 부재, 배너 폐기, send/read 융합, close가 클라이언트만 죽인다는 것 —
   **여섯 전부 `FOUNDATION_DECISION.md` §12.2-7과 `ARM_E_REPORT.md` §1(a)·§12.3에 있다.**
   §12.3은 이 목록을 보고 내려졌다.
2. **§10.1의 생존 조건은 seam 단위였지 파일 단위가 아니었다.** "어떤 seam에서 E가 계약
   뒤에서 구조 패치 3개 이하로 통과"이고, E는 S4·S5·S6를 유형 B에서 **2개로** 통과했다.
3. **결정의 실질적 근거는 코드량이 아니라 측정이었다.** §12.3이 적은 것은 "E는 실제 arm으로
   B 6/7 + 모델이 4/4 run에서 세션을 실제로 열어 배관과 통합이 둘 다 성립한 유일한 arm"이고,
   그 관측을 만든 자산이 §3.1과 §3.3의 목록이다. 그 자산은 그대로 온다.

---

## 4. 배관과 통합 — 계약이 재지 않는 자리의 책임

`spec.md` §2 S4가 적은 대로 계약은 **배관만** 잰다. 통합(모델이 그 배관을 쓰기로 고르는가)은
프롬프트와 loop의 성질이고, 스파이크는 이 둘이 갈리는 것을 두 번 봤다(T·X 모두 배관은
통과, 모델 호출 0회).

**재빌드가 지는 책임:**

1. 세션 도구가 존재한다는 것을 **매 턴** 프롬프트에 싣는다(§3.3).
2. 선언된 대상의 host·port를 채운 **완성된 호출문**을 싣는다. 설명문만으로는 부족하다는
   것이 X의 관측이다.
3. **통합이 성립했는지를 telemetry로 잰다** — 정상 스트림당 `session.opened`의 수
   (`N_open`)를 보고 항목에 넣는다. 배관 판정(S4.2)과 별개의 숫자다.

---

## 5. vendor 패치 대장

vendored 파일에 가하는 모든 변경은 여기 등재된다. **`git diff vendor/`가 이 대장과 일치하지
않으면 그것 자체가 결함이다.**

| id | 파일 | 종류 | 무엇을 | 왜 |
|---|---|---|---|---|
| (예정) V-01 | `config/commands/_connect.py` | 구조 | `cmdloop()`이 `KeyboardInterrupt`를 잡아 프롬프트로 복귀 | `spec.md` §4.3 / R2-11. E의 interrupt가 세션을 죽인다 |

**`(예정) V-01`은 아직 세어지지 않는다 (개정 R3-16).** 이 표의 `(예정)` 행은 계약이
요구하는 것에서 **연역된 예상**이지 적용된 패치가 아니다. 계수에 들어가는 것은 실제로
`vendor/`를 고친 시점부터다. 재빌드가 V-01을 실제로 쓰면 `(예정)` 표시를 지우고 diff
경로를 채우는데, **그 편집은 이 문서가 아니라 `docs/rebuild/REBUILD_LOG.md`에서 한다** —
이 문서는 재빌드에게 읽기 전용이다(`PATH_SCOPE.md` §3). 이 표는 **예상 대장**이고,
**실적 대장은 `REBUILD_LOG.md`에 있다.** 둘이 어긋나면 실적이 사실이다.

**규칙 다섯.**

1. 패치는 **멱등**이고, 앵커가 어긋나면 조용히 실패하지 않고 **죽는다.** 스파이크의 세
   arm이 전부 이 형태를 썼다.
2. 패치마다 diff를 저장소에 커밋하고 실적 대장에 등재한다.
3. **패치가 늘어나는 것이 철수 신호다.** §6.5: "어댑터를 유지하려고 vendor 원본을 반복
   수정하게 되는 시점(= 사실상 REWRITE)"이 철수 조건이다. 임계치를 여기서 못박는다 —
   **구조 패치 3개째에서 멈추고 보고한다.** 스파이크가 후보당 쓴 예산과 같은 수이고,
   **seam당이 아니라 vendored 컴포넌트 전체의 누계다**(`spec.md` §6.1, R3-6).
   구조/사소의 구분도 같은 절이 정의한다.
4. upstream을 따라가지 않는다. vendored 코드는 `dc18a740`에 고정되고, 보안 패치가 필요하면
   그때 새 결정을 한다.
5. **`git diff vendor/`가 실적 대장과 일치한다는 확인을 세션마다 남긴다**
   (`CLAUDE.md` §10-2).

---

## 6. S9의 두 소비자 — 재빌드 산출물로 명명한다

`FOUNDATION_DECISION.md` §13.1.a-1이 요구한 명명이다. **둘 다 seam이 아니다. 둘 다
telemetry의 투영이다.**

| 산출물 | 무엇을 하는가 | 소재 | 언제 |
|---|---|---|---|
| **라이트업 생성기** (`writeup-generator`) | 한 attempt의 스트림에서 사람이 읽는 풀이 기록을 만든다 — 도구 순서, 실행 가능한 solve 단계, 무엇을 관찰해 답에 이르렀나, 성공의 증거, 재현 절차 | `TELEMETRY_SCHEMA.md` §4.1의 (a)~(e) | 자율 코어와 함께. 봉투가 이미 (b)·(b')를 포함하므로 뒤로 미룰 이유가 없다 |
| **escalation 패킷 컴파일러** (`escalation-packet-compiler`) | 막힌 attempt의 스트림에서 CONFIRMED / INFERRED / REJECTED로 나뉜 패킷을 만들어 `SAFETY_SCOPE.md`의 단일 export를 통해 내보낸다 | 같은 스키마 + §5의 예약 이벤트 | **재빌드 이후.** escalation은 "막힌 문제를 넘긴다"이므로 넘길 대상인 자율 코어가 먼저 있어야 얹힌다 |

**지표의 위치**(§13.1.a, 2026-08-08 canon 반영):

- `clean_solve@1` — **도구.** foundation을 고르고 자율 코어가 나아지는지 재는, 오염되지
  않은 유일한 자. 없애지 않는다.
- `contest_solve` — **실제 목표.** escalation 보조를 포함한 성적.
- 후자는 전자를 대체하지 않는다. `EVAL_CONTRACT.md`에 명문화됐다.

---

## 7. 미측정 위험과 후속 gate — 재빌드가 물려받는 것

### 7.0 "재빌드가 끝났다"의 정의 — 운영자 결정 2026-08-08 (개정 R3-17)

r2에는 세션별 종료 기준만 있고 **단계 종료의 정의가 없었다.** `OBJECTIVE.md`의 1순위
(`clean_solve@1`)는 `HOLDOUT.md` §2의 두 세트가 비어 있어 재빌드 안에서 측정할 수 없으므로,
1순위 지표로 완료를 정의할 수 없다. 운영자가 정한 정의는 이렇다.

> **재빌드는 다음 둘이 모두 참일 때 끝난다.**
>
> 1. **계약 술어 전부 PASS** — `spec.md` §2의 9개 seam이 세 fixture 위에서
>    `spec.md` §6.3의 집합 판정(정상 스트림 4개 이상)으로 전부 만족된다. 스파이크가 arm을
>    잰 것과 **같은 기준을 우리 스택에 적용하는 것**이다.
> 2. **후속 gate에 착수** — §7.1의 1번(Responses transport 구현·검증)이 끝난다.

**왜 이 둘인가.** 1번은 "만들었다"의 유일한 기계적 정의다 — 배관이 계약을 만족하는지는
검사기가 답하고 사람 판단이 들어가지 않는다. 2번은 **foundation 결정이 provisional인
상태를 재빌드가 물려받은 채로 끝내지 않기 위해서**다(§7.1-4: "foundation-spike 결과만으로
승격하지 않는다"). transport를 구현해 두지 않으면 성능 단계가 그 자리에서 다시 막힌다.

**포함되지 않는 것, 명시.** `reasoning effort medium` 재평가(§7.1-2), solve rate 비교
(§7.1-3), 챌린지 저작, `clean_solve@1` 측정은 **성능 단계**의 일이다(`HOLDOUT.md` §6-1,
`FOUNDATION_DECISION.md` §13.2). 재빌드는 **아직 아무것도 풀지 못한 상태로 끝난다** —
그것이 정상이고, 그 사실을 여기 적어 두는 이유는 "풀 때까지 재빌드"로 미끄러지는 것을
막기 위해서다.

**스파이크가 통합에 대해 남긴 관측 하나가 여기 걸린다.** 배관 PASS는 통합 성립을 뜻하지
않는다(T·X가 배관을 통과하고도 모델이 세션을 0회 열었다). 1번은 배관만 요구하므로,
`N_open`은 **완료 기준이 아니라 보고 항목**이다(§4-3). 통합이 실패한 채로 재빌드가
끝날 수 있고, 그 경우 그 사실이 `REBUILD_LOG.md`에 남아 성능 단계의 첫 과제가 된다.

### 7.1 후속 gate — foundation 채택 전 필수

`FOUNDATION_DECISION.md` §9.1 개정(ADR-0001)이 건 조건이고, **이 관문 전의 foundation
결정은 provisional이다.**

| # | 무엇 | 현재 상태 |
|---|---|---|
| 1 | Responses transport(`/v1/responses`) 구현·검증 | **닫혔다 — 재빌드-7, 2026-08-09 (개정 R5-6).** 스파이크의 T·E는 `/v1/chat/completions`에서 돌았다. 구현은 `kisia/runtime/model.py`(표준 라이브러리 전송), 검증은 `docs/rebuild/judgments/2026-08-09-r7-agent-ab/` — 모델이 실제로 그 배관을 써서 유형 A 하중 8칸 `PASS`, **S3의 네 술어가 처음으로 실제 값을 받았다.** capability probe 12칸은 `docs/rebuild/capability-probes/openai-responses-tools-effort-2026-08-09.json` |
| 2 | nontrivial clean fixture에서 **`reasoning effort medium`으로** 재평가 | **어떤 arm도 medium에서 재지 않았다** |
| 3 | solve rate · latency · cost · tool reliability · variance 비교 | 미착수 |
| 4 | **foundation-spike 결과만으로 승격하지 않는다** | 이 문서가 그 규칙을 상속한다 |

**"결선 후보 전부"를 어떻게 읽는가.** 이 조항은 후보가 여럿일 때 쓰였다. 선택지 1이 죽고
3이 미선택이므로, 지금 남은 읽기는 **"추출한 스택 자체를 medium·Responses에서 재평가한다"**
이다. 비교 대상이 필요하면 §8-2의 G 참조 구현이 세션 런타임 축의 A/B가 된다
(`FOUNDATION_DECISION.md` §6.4가 예고한 그 A/B다).

### 7.2 계약이 아직 잡지 못하는 것

`FOUNDATION_DECISION.md` §12.2-7의 목록 중 **r2가 닫지 못한 것**만 적는다. 닫은 것은
`spec.md` §8.1에 있다.

| 공백 | 상태 |
|---|---|
| 어떤 arm도 `reasoning effort medium`에서 재지 않았다 | **열림.** §7.1의 gate |
| 유형 C의 브라우저/JS 실행과 동시성(race) | **열림.** §11의 가설대로 공통 미해결. `spec.md` §9-1·§9-2 |
| **S6의 loop 절반** — "모델이 매 턴 올바른 상태를 받는가" | **부분적으로 닫힘.** G는 재지 못했지만 **E가 실제 모델로 쟀다**(B-1 4/4). 다만 그 loop은 E의 것이고, **우리 loop은 다시 미측정**이다 |
| 골든 트라젝토리가 잡지 못하는 fixture 결함 | **열림.** 완화는 단일 경로 설계뿐(`spec.md` §7) |
| 유형 C의 arm 간 이미지 비대칭(curl 유무) | **소멸.** arm이 하나뿐이다 |
| `answer.sweep`의 네 표면 밖 — 챌린지 서비스가 정답을 통째로 반환하는 경우 | **열림.** fixture 저작 규칙으로 막는다(`HOLDOUT.md` §4) |
| E의 자기 회계·자기 보고 결함 전반 | **소멸.** 회계·보고가 전부 우리 것이다(REWRITE) |

---

## 8. 이 문서가 정하지 않는 것

1. **디렉터리 구조와 모듈 경계.** `vendor/` 하나만 고정한다. 나머지는
   `FOUNDATION_DECISION.md` §13.3이 재빌드로 미룬 질문이다.
2. **G 참조 구현과 현 프로토타입 `src/`의 재사용 여부.** §13.3이 "선택 후에 **seam 단위로**
   `docs/evidence/2026-08-07-phase-b-evidence.md`를 근거로만 판단한다"고 했고, 그 판단은
   재빌드가 각 seam에 착수하는 시점에 한다. **경로 규칙은 `PATH_SCOPE.md` §3이 미리
   그어 둔다** — 판단 전까지 프로토타입 코드는 읽기 전용이다.
3. **agent loop의 형태**(단일 executor / 선택적 planner / 상시 planner).
4. **모델 라우팅과 escalation의 상세 설계.**

---

## 부록 A. 참조

- `docs/spec/spec.md` — 계약 확정판. §3(S7), §4(InteractiveSession), §8.1(r2 개정 목록)
- `docs/spec/TELEMETRY_SCHEMA.md` — 봉투, 두 소비자의 충분성, 예약 필드
- `docs/spec/PATH_SCOPE.md` — vendor·프로토타입·컨테이너·호스트의 경로 규칙
- `docs/spike/FOUNDATION_DECISION.md` §6(선택지 2 분석), §12.1(판정표), §12.3(결정), §13
- `docs/spike/ARM_E_REPORT.md` §1(a)(b)(c)(d), §3.1, §12.3~§12.5, §14.1, §16, §17
- `docs/spike/PINS.md` §1 (commit), `docs/spike/LICENSE_MATRIX.md` (의무), `REPRO_MATRIX.md`
- `docs/spike/G_REPORT.md` §7(작성 시간의 범위), §8(G가 재지 않은 것)
