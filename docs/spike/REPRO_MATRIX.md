# REPRO_MATRIX

스파이크 세션 A (Stage 0), 2026-08-07. 양식은 [pack §15], 기록 항목은 [pack §10 Stage 1].

**이 문서의 범위는 build + 기동 + headless + provider 인증까지다.** fixture가 아직 없으므로
(세션 B의 산출물) end-to-end run은 하지 않았다. seam 판정은 세션 D~F의 일이며 **이 문서에는 seam
판정이 없다.**

실행 계정 `ctf-spike-user`(uid 1002, docker 그룹, sudo 없음). 원본 로그 `<HOME>/logs/`,
패치 diff `<HOME>/logs/patches/`.

---

## 1. 표

| Candidate | Clean build | Smoke run | Headless | Logs | Cleanup | Patches |
|---|---|---|---|---|---|---|
| **T** TATAR | **성공** (문서화된 경로로는 실패, §2.1) `ctfenv:multiagent` 10.5 GB `sha256:7ffb5ff2…` | **인증 성공**, 후보 자신의 호출 형태는 **실패** (§2.1-P3) → 세션 D의 T-04 적용 후 **성공** | **가능** `run_dcipher.py --help` rc=0, TTY 불필요 | `--logdir/$USER/$EXPNAME/*.json` (`utils.py:58`). 세션 D의 4 run에서 생성 확인 | 컨테이너 0, 이미지 1, 네트워크 `ctfnet` 1 | 세션 A 구조 **0** / 사소 **3**. 세션 D 누계 구조 **2** / 사소 **5** |
| **E** EnIGMA v0.7.0 | **성공** (문서화된 경로로는 실패, §2.2) `sweagent/enigma:spike` 17.9 GB `sha256:10040d90…` | **인증 성공 + 후보 자신의 `query()` 성공** | **가능** `run.py --help` rc=0 (pin 적용 후) | `trajectories/` (저장소 내), stdout에 비용·토큰 회계 | 컨테이너 0, 이미지 1(+베이스) | 구조 **0** / 사소 **3** |
| **X** Codex CLI 0.147.0 | n/a (릴리스 바이너리) | **인증 성공 + headless 완주** | **가능** `codex exec` | `$CODEX_HOME/` (sqlite 4종 + `sessions/**/rollout-*.jsonl`), `codex exec --json` 이벤트 스트림 | 컨테이너 0 | 세션 A 구조 **0** / 사소 **0**. **세션 F-2 누계 구조 1**(X-01) / 사소 **0** — 유형 A·B·C 전부를 구조 패치 **1개**로 돌렸다 |
| **CTFusion** | 해당 없음 — clone·boot하지 않음 (`FOUNDATION_DECISION.md` §9.1: 읽기 전용 참조) | — | — | — | — | — |

**디스크:** 착수 17 GB(6%) → 세션 종료 62 GB(20%). HOST_EXCEPTIONS §4의 80% 중단선까지 여유가 있다.
두 이미지가 28 GB를 차지한다.

**프로토타입 자산 무손상:** `kisia/*` 이미지 6/6 그대로, `<PROTO_HOME>/kisia-data` 미접근,
`<PROTO_HOME>/kisia-agent` 미변경(HEAD `bf59a07`, status clean — HOST_EXCEPTIONS §10 기준선).

---

## 2. 후보별 상세

### 2.1 T — TATAR-LAB `ctf-agents`

```
clone/pin
  git clone --no-checkout https://github.com/TATAR-LAB/ctf-agents.git
  git checkout --detach e52e38ea30fb162446342ed456a969f9c71fa815
필요 runtime
  Python 3.12 (pyproject: >=3.9, README: 3.10+ 권장), uv 0.12.1, Docker 29.7.1
container build
  docker network create ctfnet
  docker build --label kisia-spike=1 -t ctfenv:multiagent docker/multiagent    → 성공
headless
  .venv/bin/python run_dcipher.py --help                                        → rc=0
provider 인증
  아래 P1/P2/P3
```

**부팅 실패 2건과 그 처리.**

*실패 1 — 문서화된 설치 경로가 import 불가능한 패키지를 만든다.* `setup_dcipher.sh`는
`pip install --editable .`을 한다. `pyproject.toml`의 `together`가 버전 미고정이라 최신
(2.x)이 설치되고, `together_backend.py`의 `from together.types.chat_completions import
ChatCompletionMessage`가 `ImportError`로 죽는다. `backends/__init__.py`가 모든 백엔드를 무조건
import하므로 **패키지 전체가 import되지 않는다.**
→ 가설: 미고정 의존성 드리프트. 반증 관측: 저장소에 `uv.lock`이 있으니 잠금대로 설치하면 성공해야
한다. 관측: `uv sync --frozen`(together 1.5.34) → 이 오류 소멸. **가설 확인.**
→ 처리: 저장소가 함께 배포하는 잠금 파일을 쓴다. **후보 파일 수정 없음.**

*실패 2 — 패키징 메타데이터가 코드 변경을 따라가지 못했다.* `gemini_backend.py`가
`from google import genai`를 하는데 `pyproject.toml`의 의존성은 구 `google-generativeai`뿐이다.
`changes.md`는 "Gemini 백엔드를 새 `google-genai` SDK로 재작성했다"고 적고 `requirements.txt`에는
`google-genai`가 있다. 즉 저장소가 스스로 필요하다고 적은 패키지가 설치 경로에서 빠져 있다.
→ 처리: `uv pip install google-genai` (2.17.0). **후보 파일 수정 없음.**

**provider 인증 (호출 3회, 최소 프롬프트).** 후보 자신의 `OpenAIBackend`를 생성해 키가 후보 코드를
통과하게 했다.

| 프로브 | 결과 |
|---|---|
| P1 최소 인증 (`client.chat.completions.create`, `max_completion_tokens=16`) | **OK** — prompt 7 / completion 8 토큰 |
| P2 `temperature=0.0` 수용 여부 | **FAIL** — `400 Unsupported value: 'temperature' does not support 0 with this model. Only the default (1) value is supported.` |
| P3 후보 자신의 `_call_model()` | **FAIL** — `400 Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.` |

`_call_model`은 `temperature`, `top_p`, `max_tokens`를 **무조건** 보낸다(조건 분기 없음). 따라서
**T는 현 상태로 `gpt-5.6-terra`에 단 한 번의 모델 호출도 할 수 없다.** 인증(P1)은 통과하므로 키 배관과
네트워크 경로는 정상이고, 막히는 것은 provider 어댑터의 파라미터 형태다.

여기에 §9.1의 통제 조건이 하나 더 걸린다. **`_call_model`에는 `reasoning_effort`가 없다.**
`FOUNDATION_DECISION.md` §9.1은 모델 구동 arm 전부에 "reasoning effort medium"을 요구하고
`EVAL_CONTRACT.md`는 그것을 비교의 통제 조건으로 못박는다. 현 상태의 T는 그 통제를 **표현할 수 없다.**

**이 세션은 이 수정을 적용하지 않았다.** Stage 0의 범위는 인증까지이고, 인증은 확인되었다. 수정을
지금 하면 세션 D가 쓸 패치 예산을 Stage 0에서 미리 소비하게 된다. 세션 D에 넘긴다(§4).

**패치 목록 (구조 0 / 사소 3).**

| # | 종류 | 내용 | 후보 파일 수정 | 근거 한 줄 |
|---|---|---|---|---|
| T-01 | 사소 | 설치를 `pip install -e .` 대신 저장소가 배포하는 `uv.lock`으로 (`uv sync --frozen`) | 없음 | §9.3 "packaging". 저장소가 함께 배포하는 두 설치 경로 중 하나를 고른 것이라 엄밀히는 패치가 아니지만, 문서화된 경로가 실패한다는 사실이 기록될 자리가 여기라 남긴다 |
| T-02 | 사소 | `google-genai` 설치 | 없음 | §9.3 "packaging". 저장소의 `requirements.txt`가 이미 선언한 패키지이고 `pyproject.toml`에서만 누락 |
| T-03 | 사소 | `backends/models.yaml`에 `gpt-5.6-terra` / `backend: openai` 항목 추가 (append) | **있음** (설정 파일) | §9.3의 구조 패치 정의 넷(core loop / 상태 모델 / 도구 인터페이스/ 격리 모델) 중 어느 것도 아니다. 그 파일 머리말이 "Edit this file to add new models — no Python code changes needed"라고 스스로 규정한다. diff: `T-minor-01-models-yaml-openai-entry.diff` |

**~~보류(미적용)~~ → 세션 D에서 적용됨 (T-04, 사소).** `openai_backend.py::_call_model`의 파라미터
형태(`max_tokens` → `max_completion_tokens`, `temperature`/`top_p` 조건화, `reasoning_effort` 추가).
세션 D가 **사소** 분류에 동의했다 — 근거는 `ARM_T_REPORT.md` §3.1. diff:
`docs/spike/arms/T/patches/T-04-minor-openai-params.diff`.

**적용 뒤 관측이 이 절의 예상을 하나 뒤집었다.** 세션 D가 나가는 요청 본문을 가로채 확인한
결과 `reasoning_effort=medium`은 실제로 실렸으나 **API가 거부했다**:
`Function tools with reasoning_effort are not supported for gpt-5.6-terra in
/v1/chat/completions.` 여섯 칸을 실측한 결과 **effort 부재도 실패한다** — 즉 T는 T-04 이전에
이 모델에서 **도구를 쓰는 호출을 단 한 번도 할 수 없었고**, 위 P3 실패(`max_tokens`)는 두
관문 중 첫째였을 뿐이다. "필수"라는 이 절의 판단은 실측으로 확인됐고, 그 이유는 한 겹 더
깊었다. 전 arm `reasoning effort none`으로 통일한 운영자 결정과 그 근거는
`ARM_T_REPORT.md` §2, `FOUNDATION_DECISION.md` §9.1.

**세션 D가 추가로 적용한 패치 (구조 2 / 사소 1).** 상세와 분류 근거는 `ARM_T_REPORT.md` §3.

| # | 종류 | 내용 | 후보 파일 수정 | 근거 한 줄 |
|---|---|---|---|---|
| T-05 | **구조** | 정답 주입 제거와 성공 판정의 외부화 — `misc.py`의 `actual_flag` **와** `agent.py`의 `check_flag_in_response`(같은 결함의 더 넓은 경로). unix 소켓 뒤 verifier 데몬에서 판정만 받는다 | **있음** (소스 2파일) | §9.3의 **상태 모델**(`environment.solved`의 유일한 설정 지점)과 **도구 인터페이스**를 바꾼다. diff: `T-05-structural-flag-verifier.diff` |
| T-06 | **구조** | 격리 모델 — `start_docker`에 `/input:ro`·`/work`·`/artifacts` 마운트와 `--read-only` | **있음** (소스) | §9.3의 **격리 모델**. 상류는 마운트가 하나도 없고 루트fs가 쓰기 가능하다. 어댑터로 만들 수 없는 사실이다. diff: `T-06-structural-isolation.diff` |
| T-07 | 사소 | `models.yaml`에 `gpt-5.6-luna` 항목 추가 (A-5/P-S3-a용) | **있음** (설정 파일) | T-03과 같은 성격. Python 소스 미변경이므로 P-S3-a의 "후보 소스를 고치지 않고"가 만족된다 |

**세션 D-2가 적용한 패치 (구조 1).** 상세와 분류 근거는 `ARM_T_REPORT.md` §3.5.

| # | 종류 | 내용 | 후보 파일 수정 | 근거 한 줄 |
|---|---|---|---|---|
| T-08 | **구조** | 지속 세션 계층 — `tools/session.py` 신설(§4의 6개 연산 + §4.1 넷 + §4.2 동시성)과 `tools/__init__.py`의 `ALLTOOLS` 등록 | **있음** (소스 1파일 신설 + 1파일 +13/-1) | §9.3의 **도구 인터페이스**를 바꾼다. `SEAM_CONTRACT.md` §2 S4가 이 자리를 미리 구조 패치로 못박았다. diff: `T-08-structural-session.diff` (584줄) |

**구조 패치 누계 3 / 예산 3 — 예산 소진.** 4번째는 필요하지 않았다. 유형 C는 T-08을
행사하지 않고 통과했다(쿠키 항아리는 `docker exec` 경계를 넘어 살아남는다).

**후보 checkout의 수정 파일은 7개**(세션 D의 6개 + `tools/session.py` 신설). pin `e52e38ea`
유지, 전부 diff로 기록됨.

**Stage 0에서 눈에 띈 것 (판정 아님, 세션 D의 입력):**
`nyuctf_multiagent/tools/misc.py`가 `self.actual_flag = environment.challenge.flag`로 **정답을 solver
프로세스 안의 도구 객체에 넣고** `self.environment.solved = True`로 성공을 스스로 판정한다.
`FOUNDATION_DECISION.md` §5.2가 S8에 대해 예측한 것과 §9.2의 "정답은 worker가 도달할 수 있는 어떤
경로에도 두지 않는다"에 그대로 걸리는 지점이다. **여기서 판정하지 않는다.**

### 2.2 E — EnIGMA / SWE-agent v0.7.0

```
clone/pin
  git clone --no-checkout https://github.com/SWE-agent/SWE-agent.git
  git checkout --detach dc18a740faabd2fc625a9b018184dfc4a81cbc78    (tag v0.7.0 재확인)
필요 runtime
  Python 3.12 (pyproject: >=3.9), uv, Docker
container build
  docker build --label kisia-spike=1 -f docker/enigma.Dockerfile -t sweagent/enigma:spike .
    → 성공, rc=0, 429초, 베이스 sweagent/swe-agent:0.6.1 (Docker Hub)
headless
  .venv/bin/python run.py --help                                      → rc=0 (pin 적용 후)
```

**부팅 실패 2건과 그 처리.**

*실패 1 — 잠금 파일이 없고 의존성이 전부 미고정이다.* `requirements.txt`는 `swebench>=2.0.0`처럼
하한만 준다. `uv.lock`/`poetry.lock`/`requirements.lock` **전부 없다**(확인함). 결과로 swebench
4.1.0이 설치되고 `from swebench.harness.utils import get_environment_yml, get_requirements`가
`ImportError`로 죽는다. 이것이 `sweagent.environment.swe_env` → `agents` 연쇄에 걸려 **`run.py --help`
조차 뜨지 않는다.**
→ 처리: `swebench==2.1.0` 고정. §9.3이 "pin"을 사소로 명시한다. **후보 파일 수정 없음.**
→ T와 대비된다: 같은 종류의 드리프트인데 T는 저장소가 준 `uv.lock`으로 무패치 복구가 가능했고,
E는 잠금이 없어 우리가 버전을 골라야 했다. **재현성 면에서 E가 T보다 약하다.**

*실패 2 — 문서화된 CTF 설치 스크립트가 존재하지 않는 파일을 빌드한다.* `setup_ctf.sh`는
`docker build -f docker/swe-ctf.Dockerfile …`를 하는데, **태그 `v0.7.0`의 `docker/`에 그 파일이
없다.** 실제 존재하는 것은 `enigma.Dockerfile`, `swe.Dockerfile`, `ctf_requirements.txt`,
`ghidra_scripts` 등이다.
→ 처리: 존재하는 `docker/enigma.Dockerfile`을 빌드했다. **후보 파일 수정 없음.**
→ pack §5.3의 "논문 버전과 main 불일치" 경고와 같은 계열의 문제가 **태그 안에서도** 있다는 뜻이다.

**키 처리 — §7.2를 무패치로 만족한다.** `run.py`는 `keys.cfg not found` ERROR를 출력하지만 죽지
않는다. `keys_config = Config()`(`sweagent/utils/config.py:85`)가 환경변수 폴백을 하기 때문이다.
`keys_config.get("OPENAI_API_KEY")` → True (키는 프로세스 환경변수에만 존재). **파일에 쓰지 않고
동작한다.**

**provider 인증 (호출 2회).**

| 프로브 | 결과 |
|---|---|
| P1 최소 인증 | **OK** — prompt 7 / completion 5 |
| P2 후보 자신의 `OpenAIModel.query()` | **OK** — 응답 수신. 후보 stdout에 `input_tokens=7, output_tokens=8, instance_cost, total_cost, total_api_calls=1` 회계가 함께 나온다 |

**T와의 차이가 여기서 가장 크다.** 같은 모델·같은 키로 T의 `_call_model`은 400으로 죽고 E의
`query()`는 통과한다. 그리고 E는 호출 단위 토큰·비용 회계를 스스로 낸다(`FOUNDATION_DECISION.md`
§3의 S3 "토큰·비용이 호출 단위로 회계된다"에 대응하는 관측이지만, **판정은 하지 않는다** — 그 사실이
우리 telemetry로 재구성 가능한지는 세션 E가 볼 일이다).

**패치 목록 (구조 0 / 사소 3).**

| # | 종류 | 내용 | 후보 파일 수정 | 근거 한 줄 |
|---|---|---|---|---|
| E-01 | 사소 | `swebench==2.1.0` 고정 | 없음 | §9.3 "pin". 잠금 파일 부재로 인한 드리프트 복구 |
| E-02 | 사소 | `sweagent/agent/models.py`의 `OpenAIModel.MODELS`에 `gpt-5.6-terra` 항목 추가 (7줄) | **있음** (소스) | T-03과 같은 성격의 변경인데 E는 모델 레지스트리를 YAML이 아니라 소스에 두어 소스에 떨어진다. §9.3의 넷 중 어느 것도 아니다. diff: `E-minor-01-model-registry-entry.diff` |
| E-03 | 사소 | `setup_ctf.sh` 대신 `docker/enigma.Dockerfile`을 직접 빌드 | 없음 | §9.3 "문서 오류". 스크립트가 가리키는 파일이 태그에 없다 |
| **E-04** | **사소** | 베이스 이미지에 `flake8`을 굽는다 (`sweagent/enigma:spike-kisia`) | 없음 | §9.3 "packaging". `swe_env.py:396`이 **조건 없이** `pip install flake8`을 돌고 `communicate_with_handling`이 비영점에 RuntimeError를 낸다. 이미지에 flake8이 없어(실측, `--network none`에서 `ModuleNotFoundError`) 내부 네트워크 + read-only 루트fs에서 run이 죽는다 |
| **E-05** | **구조 (1/3)** | 정답 주입 제거와 성공 판정의 외부화 (`swe_env.py` — `validate_submission`이 verifyd에 질의, 경고 로그가 정답을 찍지 않는다) | **있음** (소스) | §9.3의 넷 중 **상태 모델**(성공 판정의 유일한 지점이자 `step()`의 종료 조건)을 바꾼다. T-05와 같은 근거. diff: `E-05-structural-flag-verifier.diff` |
| **E-06** | **사소** | `ModelArguments.reasoning_effort` 신설 + 값이 있을 때만 요청에 싣는다 (`models.py`) | **있음** (소스) | T-04와 같은 자리. provider 어댑터 안에서 요청 파라미터 하나를 더할 뿐이고 제어 흐름·상태·도구 계층·격리 전부 그대로다. 값을 주지 않으면 요청 본문이 패치 이전과 **완전히 같다**. diff: `E-02-E-06-minor-models.diff` |
| **E-07** | **구조 (2/3)** | 세션 close 가 컨테이너 안의 자손을 거둔다 (`swe_env.py` — 커널 세션(sid) 경계, 좀비 제외, 리더를 **open 에서** 기록. STOP 분기·`_terminate_interactive_session`·`close()` 세 지점) | **있음** (소스) | §9.3의 넷 중 **상태 모델**을 바꾼다 — 세션 생애주기에 "정리" 단계가 없었는데 생긴다. 관측이 아니라 **행동**이라 어댑터가 아니다. 한 원인이 네 자리에서 터졌다: B-3(§4.1-2)·B-4(§4.1-3)·S2.5(`surviving_processes=1`)·S4.4. diff: `E-07-structural-session-reap.diff`. **세 호출 지점을 따로 세는 해석을 취하면 3개**이고 그 이견은 `ARM_E_REPORT.md` §12.4에 함께 실었다 |
| **E-08** | **사소** | `models.py`의 `OpenAIModel.MODELS`에 `gpt-5.6-luna` 추가 (A-5 / P-S3-a) | **있음** (소스) | E-02와 **같은 줄에 같은 모양**으로 더한다. 구조 패치 정의 넷 중 어느 것도 아니다 — 제어 흐름이 아니라 **단가 표의 행 하나**다. 다만 P-S3-a의 문면 "**후보 소스를 고치지 않고**"는 E에서 문자 그대로는 만족되지 않는다(T는 YAML이라 이 문제가 없었다). **"무패치 통과"로 적지 않고 "통과하되 사소 패치 1개"로 적는다** — `ARM_E_REPORT.md` §14.2. diff: `E-02-E-06-E-08-minor-models.diff` |

**세션 E의 관측 셋 — 세션 A의 판단을 확정하거나 뒤집는다.**

1. **"E는 provider 패치가 필요 없다"는 처음 판단이 틀렸다.** E는 function tools를 쓰지
   않으므로(`models.py:312-317` — 도구 계층이 markdown 코드블록이다) 세션 D의 여섯 칸이
   E의 요청 모양을 덮지 않는다. 새로 잰 probe에서 effort **부재**와 `none`이 **둘 다**
   `reasoning_tokens=0`이라 패치가 불필요해 보였으나, **첫 정상 run에서 어댑터의 fail-fast가
   `reasoning_tokens=9`를 잡았다.** 11토큰짜리 프로브의 0은 effort가 none이라는 증거가
   아니었다. ADR-0001의 무결성 규칙 1이 설계대로 작동했고 그 run은 폐기했다 → E-06.
2. **`run.py:512`의 기본값 `temperature=0.0`을 이 모델이 거부한다**(400 "Only the default
   (1) value is supported"). **패치가 아니라 CLI 값으로 해결된다** — E는 `--temperature`를
   노출하고, 이 모델에서 1.0은 곧 기본값이라 T가 T-04로 temperature를 **부재**로 만든 상태와
   같은 자리다.
3. **E는 격리 모델을 표현하지 못하지만 T-06에 해당하는 구조 패치가 필요 없었다.**
   `--container_name`이 있으면 `_get_persistent_container`가 **이름이 같은 컨테이너를 다시
   만들지 않고 그대로 쓴다**(`utils.py:510-524`). 하니스가 계약 형태로 먼저 만들면 E가 거기
   붙는다. 무과금 스모크로 `reset: OK`와 P-S2-a/P-S2-b 거부를 실측했다. **T에는 이 탈출구가
   없었다.** 구조로 세어야 한다는 반대 해석의 여지는 `ARM_E_REPORT.md` §1(c)에 적었다.

### 2.3 X — Codex CLI (대조군)

```
pin/설치
  release rust-v0.147.0 자산 codex-x86_64-unknown-linux-musl.tar.gz
  sha256 0246e2e773834e07f0fb5249ed6ebad12e4591e608f8c7bb97dd6a9690544c36
  → <HOME>/bin/codex   (`codex-cli 0.147.0`)
필요 runtime
  없음. 정적 musl 바이너리. 호스트에 node/npm/cargo를 설치하지 않았다
headless
  codex exec --skip-git-repo-check --sandbox read-only "<prompt>"      → 완주
```

**인증 — 실패 2회 후 성공. 진단을 남긴다.**

*시도 1:* `OPENAI_API_KEY`를 프로세스 환경에 두고 `codex exec` → `401 Unauthorized, Missing bearer
or basic authentication in header` (websocket과 HTTPS 양쪽).
가설: 0.147은 기본 인증이 ChatGPT 로그인이고 `OPENAI_API_KEY`를 자동으로 쓰지 않는다.

*시도 2:* `--config preferred_auth_method="apikey"` → **여전히 401.** 가설이 부분적으로만 맞다.

*시도 3 (성공):* 커스텀 provider를 CLI 플래그로만 정의.

```
codex exec --model gpt-5.6-terra --skip-git-repo-check --sandbox read-only \
  --config model_provider=kisia \
  --config model_providers.kisia.name=OpenAI \
  --config model_providers.kisia.base_url=https://api.openai.com/v1 \
  --config model_providers.kisia.env_key=OPENAI_API_KEY \
  --config model_providers.kisia.wire_api=responses \
  "Reply with exactly: ok"
```

→ 완주, 응답 `ok`. 같은 실행에서 `env | grep -c '^OPENAI_API_KEY='` = 1로 환경변수 도달을 확인했다.

**이 경로가 §7.2에 중요한 이유:** codex의 통상 인증은 `codex login --api-key`이고 그것은
`~/.codex/auth.json`을 만든다. 그 파일은 `<HOME>` 아래이므로 §7.2("키를 `<HOME>` 아래 어떤
파일에도 쓰지 않는다") 위반이다. **위 config-only 경로는 그것을 피한다.** 실제로 세션 종료 시
`~/.codex/auth.json`은 존재하지 않고, 키 검색도 0건이다(§3). 세션 F는 반드시 이 경로를 써야 한다.

> **정정 2026-08-07, 세션 F.** 아래 "부수 관측" 넷 중 **둘이 실제와 다르다.** 세션 A가 틀린
> 관측을 한 것이 아니라 **CLI 표면만 보고 와이어를 보지 않았기 때문**이고, X는 그 둘이
> 갈린다. 정정 근거는 전부 **무과금 능력 프로브**(모델 호출 0회, 요청을 상류로 보내지 않고
> 기록만 하는 유닉스 소켓 프록시)이며 원본은
> `arms/X/capability-probes/codex-0.147.0-terra-toolmode-2026-08-07.json`에 있다.
> 전문은 `arms/X/PREREG.md` §3, 판정에 미친 영향은 `ARM_X_REPORT.md` §3.1.
>
> 1. **기본 reasoning effort는 `none`이 아니라 `medium`이다.** 와이어 실측이
>    `"reasoning": {"effort": "medium"}`이고, 카탈로그의 `gpt-5.6-terra.default_reasoning_level`도
>    `"medium"`이다(`supported_reasoning_levels`에 `none`은 **없다**). 그대로 두면 T·E는
>    `none`인데 X만 `medium`이라 §9.6-2 위반이다. `--config model_reasoning_effort=none`으로
>    **표현 가능**하고(와이어가 `"none"`으로 바뀜), 유효함은 ADR-0001대로 `reasoning_tokens`로
>    관측해 확인했다 — 세션 F의 전 run에서 **0**이다.
> 2. **Code Mode 경고는 "fail-closed라 안전"이 아니라 `tools: []`를 뜻한다.**
>    `gpt-5.6-terra`의 카탈로그 `tool_mode`가 `"code_mode_only"`인데 `codex-code-mode-host`가
>    pin한 자산에 없어, **모델이 받는 도구가 0개**다. 세션 A의 스모크("Reply with exactly: ok")는
>    텍스트 응답이라 이 경로를 밟지 않았다. 도구 0개면 X는 에이전트가 아니라 채팅이고
>    S4·S5·S7이 성립할 수 없다. feature flag로는 풀리지 않으며(`--disable code_mode_host` 등
>    셋 다 `tools: []`), 최소 변경은 **모델 카탈로그 두 필드**(`use_responses_lite=false`,
>    `tool_mode=null`)로 그러면 11개가 나온다 — 그중 `exec_command`·`write_stdin`이
>    §4의 지속 세션 계층이다. **세션 F는 이것을 구조 패치 X-01로 세었다.**

**부수 관측 (판정 아님).**
- 기본 `reasoning effort: none`. §9.1의 "medium" 통제를 맞추려면 `--config model_reasoning_effort=medium`이
  필요하다. **표현 가능하다** — T가 표현하지 못하는 것과 대비된다.
  *(→ 위 정정 1. 기본값은 `medium`이다. 표현 가능하다는 결론 자체는 옳고, 방향이 반대다.)*
- `warning: Codex could not find bubblewrap on PATH … will use the bundled bubblewrap` — 호스트에
  bubblewrap이 없어 번들 것을 쓴다. 격리 관련이므로 세션 F가 볼 항목이다.
- `warning: Code Mode is unavailable … will fail closed` — `codex-code-mode-host` 바이너리 미설치.
  fail-closed라 안전하다.
  *(→ 위 정정 2. 안전한 것이 아니라 **도구 계층 전체의 부재**다. 이 한 줄이 세션 F의 구조
  패치 X-01을 낳았다.)*
- 사소한 프롬프트 하나에 **11,422 토큰**. 시스템 프롬프트가 크다. §9.5의 비용 산술(호출당 입력 60K
  가정)이 X에서는 다른 모양이 될 수 있다.

**패치: 0.** 후보를 전혀 고치지 않았고 설정 파일도 만들지 않았다. 전부 CLI 플래그다.

### 2.4 CTFusion

clone하지 않았고 boot하지 않았다. `FOUNDATION_DECISION.md` §9.1이 "solver가 아니라 evaluation/control
plane이며 S8 설계의 읽기 전용 참조로만 쓰고 실행하지 않는다"고 정했기 때문이다. 확인한 것은
`LICENSE`뿐이며 `LICENSE_MATRIX.md` §2에 있다. HEAD SHA는 `PINS.md`에 pin해 두었다 — 나중에 참조할
때 같은 지점을 보기 위해서다.

---

## 3. 키 노출 검사 (HOST_EXCEPTIONS §7.2) — Stage 0에서 실제로 돌렸다

§7.2는 "매 arm run이 끝날 때마다 그 arm의 로그·trace·artifact를 키 문자열로 검색"하라고 하고,
세션 지시는 **arm 실행 전에 이 장치가 작동함을 확인할 기회가 Stage 0뿐**이라고 했다. 두 번 돌렸다.

```
방법  : sudo grep -raolF -f <(printf '%s\n' "$OPENAI_API_KEY") <경로>
        패턴을 argv에 두지 않으려고 프로세스 치환을 쓴다 (ps에 값이 보이지 않게)
1회차 : T 인증 직후, <HOME> + ctfenv:multiagent 이미지 Config.Env   → 0건
2회차 : T·E·X 인증 전부 끝난 뒤, <HOME> 전체 (바이너리 포함, -a)     → 0건
        그중 <HOME>/.codex (sqlite 4종 포함)                        → 0건
        <HOME>/.codex/auth.json                                     → 존재하지 않음
키 길이 164자. 값은 어떤 로그·대화·파일에도 출력하지 않았다.
```

**세 후보 모두 키를 파일에 남기지 않았다.** 그리고 이 장치가 실제로 실행 가능하다는 것이 확인되었다 —
세션 D~F는 매 run 후 같은 명령을 돌리면 된다.

**키 전달 경로 (세 후보 공통).** `ctf` 셸에서 `secrets.env`를 source해 export하고
`sudo -u ctf-spike-user --preserve-env=OPENAI_API_KEY`로 넘긴다. 값이 sudo의 argv에 들어가지 않으므로 `ps`에
노출되지 않는다. `secrets.env` 파일 자체는 마운트하지도 복사하지도 않았다.

**T만 추가 장치가 필요했다.** `run_dcipher.py`는 `--keys <파일>`로만 키를 받는다(`APIKeys.__init__`이
`Path(key_cfg).open("r")`). 파일을 만들면 §7.2 위반이다.
→ **무패치 우회가 성립한다.** `APIKeys`는 한 번의 순차 읽기만 하므로 프로세스 치환이 통한다:
`--keys <(printf 'OPENAI=%s\n' "$OPENAI_API_KEY")` → `/dev/fd/63`. 디스크에 아무것도 쓰이지 않는다.
후보 코드를 고치지 않고 후보의 기존 인터페이스를 다르게 호출한 것이므로 패치로 세지 않는다
(`SEAM_CONTRACT.md` §0.1 규칙 1의 취지). **세션 D는 이 형태를 써야 한다.**
*주의:* `line.strip().split("=")`이므로 키 값에 `=`가 들어가면 깨진다. 현재 키에서는 문제없다.

---

## 4. 조기 중단 판정 (pack §14)

pack §14의 10개 조건을 Stage 0에서 관측 가능한 것에 한해 대조했다. 관측하지 않은 조건은 "미관측"으로
남긴다 — 통과로 세지 않는다.

| 후보 | 판정 | 근거 |
|---|---|---|
| **T** TATAR | **계속** | 라이선스 명확(MIT). pinned commit이 clean machine에서 재현됨. 구조 패치 0개로 build·headless·인증 통과. §14의 어느 조건에도 걸리지 않았다 |
| **E** EnIGMA v0.7.0 | **계속** | 위와 같고, 추가로 후보 자신의 모델 호출 경로가 우리 모델에서 그대로 동작한다 |
| **X** Codex CLI | **계속** | 패치 0개로 headless 완주. Apache-2.0 명확 |
| **CTFusion** | **해당 없음** | arm이 아니다. 라이선스만 확인했고 그 결과는 제품 사용 가능(MIT) |

**§14 중 이 세션이 관측하지 않은 조건**(세션 D~F가 답할 것): challenge/benchmark 코드와 solver core의
분리 가능성, interactive/browser/concurrency 확장에 core rewrite가 필요한지, flag provenance 검증
가능성, 로그의 tool/model/cost/timestamp 완비 여부, cleanup 실패 누적, 범용 baseline 대비 열세.

**부분 관측 2건은 적어 둔다.**
- *"provider/model 이름이 core orchestration에 광범위하게 hard-code"* — T·E 모두 모델 레지스트리를
  들고 있으나 어댑터 뒤에 있고 backend 클래스로 분리되어 있다. "광범위한 hard-code"에는 해당하지
  않는다고 본다. 단 E는 레지스트리가 소스 안에 있어 T(YAML)보다 결합이 조금 세다.
- *"로그에 정확한 tool/model/cost/timestamp가 없음"* — E는 호출 단위 비용·토큰을 스스로 낸다.
  T는 이번 세션에서 로그를 생성할 만큼 돌리지 않아 미관측이다.

**구조 패치 3개 초과로 강등된 후보는 없다.** 세 후보 모두 구조 패치 **0개**다.

---

## 5. 비용

| 항목 | 값 |
|---|---|
| 모델 호출 | T 3회(P1·P2·P3, 두 개는 400으로 과금 없음), E 2회, X 3회(401 두 번 포함) |
| 기록된 토큰 | T·E는 각 호출 prompt 7 / completion 5~8. X는 성공 run 11,422 |
| `gpt-5.6-terra` 단가로 산술 | 합계 **$0.5 미만** |
| 세션 A의 중단선 $15 (캡 $150의 10%) | **크게 밑돈다** |

**세션 D (첫 유료 arm run).** 유형 A 8 run + 관측 프로브. 모델 호출 **38회 + 프로브 8회**,
실측 **$0.2980**. 누적 **$0.8 미만**, 상한 $150. §9.5의 산술("run 1회 ≈ $0.94")은
**9~500배 과대평가**였다 — 실측은 run 1회 $0.002~$0.108. 근거: fixture가 trivial-by-design이라
run이 5~8 호출에 끝나고(가정 20회), 입력이 호출당 ~856 토큰이다(가정 60K).
**run 간 편차는 출력 토큰이 지배한다** — 출력 요율이 입력의 6배라 trajectory 길이가 비용을
가른다. 자세한 대조는 `ARM_T_REPORT.md` §5.

**어댑터의 토큰 회계 결함 1건을 세션 D 안에서 발견·수정했다.** `cache_write_tokens`를
API가 직접 보고하는데 pricing 파일의 실측 관계로 파생시켜 입력 비용을 약 25% 과대 기록했다.
검사기는 이것을 잡을 수 없다(자기 일관성만 잰다). `ARM_T_REPORT.md` §6.1.

**세션 D-2 (유형 B·C).** 유형 B 5 run + 유형 C 5 run, 모델 호출 **111회**, 실측 **$0.3325**.
누적 **$1.2 미만** / 상한 $150. run당 $0.016~$0.064이고 §9.5의 산술("run 1회 ≈ $0.94")은
여기서도 **15~60배 과대평가**다. **비용 때문에 자른 프로브는 없다.**

**세션 E-2 (arm E, 유형 B·C).** 유형 B 11 run + 유형 C 13 run + A-5 2 run = **28 run**
(기록 9·보조 12·폐기 7). 모델 호출 **약 120회**, 실측 **$0.3712**. arm E 누계 **$0.4722**,
스파이크 누계 **$1.7 미만** / 상한 $150. run당 $0.0085~$0.0377이고 §9.5의 산술
("run 1회 ≈ $0.94")은 여기서 **25~110배 과대평가**다. **비용 때문에 자른 프로브는 없다** —
오히려 어댑터 결함을 고치느라 같은 유형을 세 번 다시 돌렸고 그 여유가 있었다.

**세션 F (arm X, 유형 A).** 유형 A 8 run(기록 4·A-5 쌍 2·폐기 2), 모델 호출 **25회**,
실측 **$0.3468**. 스파이크 누계 **$2.05 미만** / 상한 $150. run당 $0.0043~$0.0673이다.
**X 는 시스템 프롬프트가 커서(호출당 입력 11.7K~23.1K, T·E 는 ~856) run 당 호출 수가 적은데도
비용은 T·E 와 같은 자리에 있다** — §9.5 의 산술("run 1회 ≈ $0.94")은 여기서 **14~220배
과대평가**다. **비용 때문에 자른 프로브는 없다.** 무과금 능력 프로브 15회는 상류로 요청을
보내지 않으므로 **$0** 이다.

**세션 F-2 (arm X, 유형 B·C).** 유형 B 4 run + 유형 C 6 run = **10 run**(기록 8·개입 1·보조 1, 폐기 1은 보존). 모델 호출 **32회**, 실측 **$0.4324**.
arm X 누계 **$0.7792**, 스파이크 누계 **$2.5 미만** / 상한 $150. run당 $0.0361~$0.0539다. **비용 때문에 자른 프로브는 없다** — §4.1·§4.2 프로브 6회는 **모델을 합성 SSE 로 대체**해 상류로 요청을 보내지 않으므로 **$0** 이다(`ARM_X_REPORT.md` §11). 구조 패치는 **하나도 늘지 않았다**.

**X 의 자기 회계는 우리 값과 완전히 일치한다 — 그러나 이유가 T·E 와 다르다 (세션 F 의 검사기 밖 대조).**
기록 4 run 전부에서 X 의 rollout `token_count` 가 우리 `input_tokens`·`output_tokens` 와
**완전히 일치**했다(캐시 적중 51~74%). **T·E 의 결함이 X 에 없는 이유는 X 가 더 정교해서가
아니라 X 가 비용을 계산하지 않기 때문**이다 — 토큰만 보고하므로 "캐시를 무시하고 요율을
곱하는" 코드가 없다. **우리 `usd` 에는 대조 대상이 없다**(`ARM_X_REPORT.md` §5.1).

**E 의 자기 비용 보고도 캐시를 무시한다 — 그리고 폭이 T 보다 크다 (세션 E-2 의 검사기 밖 대조).**
`update_stats` 가 `in_price × tokens_sent + out_price × tokens_received` 이고
`cached_tokens` 를 전혀 구분하지 않는다. **토큰은 세 유형 전부에서 완전히 일치**했고
(`tokens_sent`·`tokens_received`·`api_calls`), `usd` 만 갈렸다:

| 유형 | 후보 | 우리 | 배율 | 캐시 적중 |
|---|---|---|---|---|
| A | $0.10547 | $0.0157 | **6.7배** | 98.9% |
| B | $0.055948 | $0.0100 | **5.60배** | 97.6% |
| C | $0.156996 | $0.0233 | **6.75배** | 98.3% |

**같은 결함을 두 arm 이 공유하고, 과대 폭은 캐시 적중률을 따라간다.** T·E 중 무엇을
가져오든 **비용 회계는 다시 써야 한다.**

**후보 자신의 비용 보고가 캐시를 무시한다 (세션 D-2의 검사기 밖 대조, `ARM_T_REPORT.md` §4.4).**
`OpenAIBackend.calculate_cost`는 `in_price × prompt_tokens + out_price × completion_tokens`
이고 `cached_tokens`·`cache_write_tokens`를 구분하지 않는다. 실측: `b1` run에서 우리 기록
$0.0291 vs 후보의 `total_cost` $0.0425 — 차이가 전부 캐시 할인이고, 후보 식으로 재계산하면
소수점까지 일치한다. **T를 그대로 가져오면 비용 회계를 다시 써야 한다**(캐시 적중률이
높을수록 과대폭이 커진다. 이 run들에서 약 46%).

**세션 E (arm E, 유형 A).** 유형 A run 9회(유효 5·모델 호출 전 사망 3·shim 결함 1), 모델
호출 **30회**, 실측 **$0.1010**. 누적 **$1.31 미만** / 상한 $150. run당 $0.0155~$0.0380이고
§9.5의 산술("run 1회 ≈ $0.94")은 여기서 **25~60배 과대평가**다. **비용 때문에 자른 프로브는
없다.** `--tag -p1`을 argparse가 옵션으로 읽어 죽은 시도와 CLI 이름 오류·`temperature=0`
거부는 전부 **모델 호출 전 또는 과금 없는 400**이라 지출 $0이다.

**후보 자신의 비용 보고가 캐시를 무시한다 — T와 같은 결함이고 폭은 훨씬 크다** (세션 E의
검사기 밖 대조, `ARM_E_REPORT.md` §6). E의 `update_stats`는
`in_price × tokens_sent + out_price × tokens_received`이고 `cached_tokens`를 구분하지
않는다. 실측: `…161937Z` run에서 우리 기록 **$0.0157** vs 후보의 `total_cost`
**$0.10547** — 후보 식으로 재계산하면 `50569×$2.00/M + 361×$12.00/M = $0.10547`로
**소수점까지 일치**한다. **약 6.7배(≈570%) 과대**이고, T의 약 46%보다 큰 이유는 **캐시
적중률이 98.9%**이기 때문이다(E는 매 턴 전체 대화를 다시 보내고 접두사가 거의 고정이다).
**같은 결함이 두 하니스에서 확인됐다 — 어느 쪽을 가져오든 비용 회계는 다시 써야 한다.**
토큰 자체(`tokens_sent`/`tokens_received`/`api_calls`)는 우리 값과 **완전히 일치**한다.

**키 노출 검사 (세션 D·D-2).** 매 run 후와 세션 끝에 실행, **전부 적중 0건**
(`<HOME>/runs/T`, `<HOME>/spike-d`, `<HOME>` 전체). `ctf-spike-user`에 sudo가 없어
`sudo` 없이 돌렸다 — 대상 파일이 전부 `ctf-spike-user` 소유라 결과는 같다. 키 길이 164자, 값은 어떤
로그·대화·파일에도 출력하지 않았다.

**미이행 항목 하나를 명시한다.** HOST_EXCEPTIONS §7.2는 "기록된 `usd` 합계와 **provider 콘솔의
사용량을 둘 다** 보라"고 한다. 이 세션은 앞의 절반만 했다. 콘솔 조회는 대시보드 접근이 필요해
운영자의 일이다. Stage 0의 실제 지출이 $0.5 미만이라 위험은 작지만, **arm을 실제로 돌리는 세션
D~F부터는 이 대조가 실질적**이므로 그때는 운영자가 함께 봐야 한다.

---

## 6. 재현 명령 (요약)

```bash
# 계정
ssh -i ~/.ssh/id_rsa ctf-spike-user@203.0.113.10

# T
cd <HOME>/candidates/tatar-ctf-agents
uv sync --frozen && uv pip install --python .venv/bin/python google-genai
docker build --label kisia-spike=1 -t ctfenv:multiagent docker/multiagent
.venv/bin/python run_dcipher.py --help

# E
cd <HOME>/candidates/enigma-swe-agent-0.7.0
uv pip install --python .venv/bin/python -e . && uv pip install --python .venv/bin/python swebench==2.1.0
docker build --label kisia-spike=1 -f docker/enigma.Dockerfile -t sweagent/enigma:spike .
.venv/bin/python run.py --help

# X
<HOME>/bin/codex --version

# 키가 필요한 단계는 ctf 계정에서
ssh CTF-agent
set -a; . ~/.config/kisia-agent/secrets.env; set +a; export OPENAI_API_KEY
sudo -u ctf-spike-user --preserve-env=OPENAI_API_KEY -H bash -c '<command>'
```
