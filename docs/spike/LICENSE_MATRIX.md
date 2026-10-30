# LICENSE_MATRIX

스파이크 세션 A (Stage 0), 2026-08-07. 양식은 [pack §15].

**research pack이 "MIT"라고 적었다는 사실은 이 표의 근거가 아니다.** 각 행은 pin된 커밋의 LICENSE
원문을 직접 내려받아 확인한 것이다. 확인 URL은 브랜치가 아니라 **커밋 SHA로 고정**했다 — 브랜치
URL은 나중에 다른 내용을 가리킬 수 있어 증거가 되지 않는다.

원문 사본: `<HOME>/logs/licenses/`. 확인일 전부 **2026-08-07**.

---

## 1. 표

| Candidate/component | License | Product-use allowed? | Attribution | Copyleft/network clause | Verified source |
|---|---|---|---|---|---|
| **T** TATAR-LAB `ctf-agents` | MIT | 예 | 저작권 고지 + 라이선스 전문을 배포물에 포함. `(c) 2024 NYU Tandon School of Engineering and NYU Abu Dhabi` | 없음 | `raw.githubusercontent.com/TATAR-LAB/ctf-agents/e52e38ea30fb162446342ed456a969f9c71fa815/LICENSE` (HTTP 200, 1107 B, 21행, sha256 `ffe785deace99260…`) |
| **E** SWE-agent `v0.7.0` | MIT | 예 | 저작권 고지 + 전문 포함. `(c) 2024 John Yang, Carlos E. Jimenez, Alexander Wettig, Shunyu Yao, Karthik Narasimhan, Ofir Press` | 없음 | `raw.githubusercontent.com/SWE-agent/SWE-agent/dc18a740faabd2fc625a9b018184dfc4a81cbc78/LICENSE` (HTTP 200, 1147 B, 21행, sha256 `7610ed3916f6674e…`) |
| **X** `openai/codex` | **Apache-2.0** | 예 | 라이선스 사본 + 변경 파일에 변경 고지. `NOTICE` 파일이 있으면 그 내용도 전파 | 없음 (copyleft·network 조항 없음). 다만 §3(a)~(d) 재배포 의무가 MIT보다 무겁고, **특허 종료 조항**(§3)이 있다 | `raw.githubusercontent.com/openai/codex/85e0661c3baacc62db7b006d2b8085b006d0795e/LICENSE` (HTTP 200, 10926 B, 201행, sha256 `d17f227e4df5da16…`) |
| **CTFusion** (읽기 전용) | MIT **+ 제3자 고지 절** | 예 | 세 곳의 저작권 고지가 필요하다 — 아래 §2 | 없음 | `raw.githubusercontent.com/kaist-hacking/CTFusion/167982004c2eff9975872654ed9e883c7c8f9d52/LICENSE` (HTTP 200, 1627 B, 33행, sha256 `df666ba66582082a…`) |
| D-CIPHER upstream (참조) | MIT | 예 | `(c) 2024 NYU Tandon…` (T와 동일 계보) | 없음 | T의 LICENSE와 동일 계보. upstream 자체는 이 세션에서 별도 확인하지 않았다 — arm이 아니다 |

**copyleft 자동 탐지 결과:** 네 파일 전부에서 `affero|gnu general public|network|source code must|
reciprocal|noncommercial` 적중 0건. AGPL/GPL/network 조항이 없다는 것을 문자열 수준에서도 확인했다.

---

## 2. CTFusion — GitHub이 `NOASSERTION`으로 보는 이유

GitHub API의 licence 탐지는 네 저장소 중 CTFusion만 `NOASSERTION | Other`로 보고한다. 파일을 직접
읽어 이유를 확인했다: **MIT 전문 뒤에 제3자 고지 절이 붙어 있어** 탐지기가 표준 MIT로 매칭하지
못하는 것이다. 라이선스 자체는 MIT다.

고지 절의 내용(원문 요약이 아니라 그대로):

```
This repository includes third-party components under their own licenses:

- EVAL-D-CIPHER/  — derived from NYU-LLM-CTF/llm_ctf_automation (D-CIPHER),
                    MIT License, (c) 2024 NYU Tandon School of Engineering and NYU Abu Dhabi.
                    See EVAL-D-CIPHER/LICENSE.
- EVAL-Enigma/    — derived from SWE-agent / Enigma, MIT License,
                    (c) 2024 John Yang, Carlos E. Jimenez, Alexander Wettig,
                    Shunyu Yao, Karthik Narasimhan, Ofir Press.
```

두 가지가 따라온다.

1. **CTFusion에서 무언가를 가져오면 저작권 고지가 최대 셋이다** — KAIST HackingLab, NYU, SWE-agent
   저자들. 어느 서브트리에서 가져왔는지에 따라 달라지므로, 실제로 가져오는 시점에 파일 단위로
   기록해야 한다 (`FOUNDATION_DECISION.md` §6.2-4).
2. **CTFusion은 D-CIPHER와 EnIGMA를 둘 다 번들한다.** 우리 arm T와 E의 계보를 한 저장소 안에서
   evaluation plane 뒤에 놓은 셈이다. §9.1이 CTFusion을 S8 설계의 읽기 전용 참조로 둔 것과 맞물려
   세션 C 이후에 참고 가치가 있을 수 있다. **이 세션은 그 판단을 하지 않는다.**

---

## 3. 확인 중에 발견한 불일치 — T의 패키지 메타데이터

`TATAR-LAB/ctf-agents`의 `pyproject.toml`은 classifier로

```
"License :: OSI Approved :: Apache Software License"
```

를 선언한다. **같은 커밋의 `LICENSE` 파일은 MIT다.** upstream에서 물려받은 것으로 보인다.

- **우리의 판단: LICENSE 파일이 지배한다.** 표의 T 행은 MIT다. classifier는 배포 메타데이터일 뿐
  라이선스 부여 문서가 아니다.
- 그러나 T를 fork해 배포까지 간다면 이 불일치를 정리해야 한다. 두 문서가 다른 라이선스를 말하는
  패키지를 그대로 재배포하는 것은 `FOUNDATION_DECISION.md` §5.5의 철수 조건 (c)에 닿을 수 있는
  종류의 위험이다. **지금 조치하지 않고 기록만 한다.**

---

## 4. 이 표가 덮지 않는 것 — 명시

1. **의존성 라이선스는 스냅샷하지 않았다.** [pack §10 Stage 0-4]는 "LICENSE와 dependency license
   snapshot을 먼저 저장하라"고 하고, 이 세션은 **앞의 절반만 했다.** T의 venv에는 `together`,
   `google-genai`, `anthropic`, `tiktoken` 등이, E에는 `swebench`, `datasets`, `groq` 등이 들어 있다.
   전부 우리가 재배포할 대상은 아니지만 확인된 적은 없다.
   **왜 미뤘는가:** Stage 0의 조기 중단 조건(pack §14)은 "라이선스가 제품 목적과 충돌하거나 불명확"인데,
   그 판정을 가르는 것은 후보 본체의 라이선스이지 개발 의존성이 아니다. 그리고 의존성 목록은 아직
   확정되지 않았다 — T·E 모두 이 세션에서 버전이 움직였다(§REPRO_MATRIX).
   **언제 해야 하는가:** foundation 결정 뒤, 실제로 vendored/forked 대상이 정해진 시점.
   `FOUNDATION_DECISION.md` §6.2-4가 요구하는 파일 단위 출처 유지와 같은 작업이다.
   → **§5가 이 항목을 부분 상환했다 (2026-08-08, 문서 세션).** 파일 단위 출처는 확정됐고,
   의존성 스냅샷은 **아직 남아 있다.** 남은 이유와 누가 언제 하는지는 §5.3.
2. **X는 바이너리로 검증했고 소스 빌드를 하지 않았다.** Apache-2.0은 릴리스 저장소의 LICENSE로
   확인했다. 배포 바이너리에 번들된 제3자 Rust crate들의 고지는 확인하지 않았다. 우리는 X를
   **대조군으로 실행만** 하고 재배포하지 않으므로 Stage 0에서는 충분하다. X를 감싸 제품에 넣는
   §10.5의 우발 조항이 발동하면 그때 crate 고지를 확인해야 한다.
3. **SmartData `CTF_agent`는 열지 않았다.** pack §4가 LICENSE 미확인으로 분류했고 §9.1이 읽기 전용으로
   두었다. 이 세션의 대상이 아니다.

---

## 5. vendored 대상이 확정된 뒤의 의무 (2026-08-08, 문서 세션)

`FOUNDATION_DECISION.md` §12.3 item 5가 "아직 갚지 않은 것"으로 남긴 항목이다. 결정이
선택지 2로 났고 추출 범위가 확정됐으므로(`docs/spec/SEAM_IMPLEMENTATION_MAP.md` §3),
**갚을 수 있는 부분을 갚고 남는 부분을 명시한다.**

### 5.1 파일 단위 출처 — 확정

전부 **E = SWE-agent `v0.7.0`, commit `dc18a740faabd2fc625a9b018184dfc4a81cbc78`**, MIT.
vendor 경로는 **`vendor/swe_agent_dc18a740/`**(언더스코어)이고 파일은 **통째로** 들어온다.

> **정정 둘 (재빌드-2, 2026-08-08).**
> 1. **경로가 언더스코어다.** r2 시절의 하이픈 표기를 `SEAM_IMPLEMENTATION_MAP.md` §3의
>    R3-15가 통일했고 `PATH_SCOPE.md` §3도 R5-1로 따라왔다. 이 절만 남아 있었다
>    (`REBUILD_LOG.md` 재빌드-2 O-7).
> 2. **파일이 다섯에서 아홉이 됐고, 넷은 "수정 없이"가 아니다.** 개정 **R5-3**이 import
>    closure 넷을 목록에 더했고, 그중 둘과 위 자산 둘이 §5 대장의 **사소 패치**를 받는다
>    (`V-02`~`V-05`). **고지 의무의 대상이 늘었다는 뜻이므로 이 표를 고친다.**

| vendored 파일 | 저작권 고지 | 상태 |
|---|---|---|
| `sweagent/agent/interactive_commands.py` | `(c) 2024 John Yang, Carlos E. Jimenez, Alexander Wettig, Shunyu Yao, Karthik Narasimhan, Ofir Press` | **변경됨 (V-02)** |
| `sweagent/environment/utils.py` | 같음 | **변경됨 (V-03)** |
| `sweagent/utils/log.py` | 같음 | **변경됨 (V-04)** |
| `sweagent/utils/config.py` | 같음 | **변경됨 (V-05)** |
| `sweagent/__init__.py` | 같음 | 수정 없음 |
| `sweagent/utils/__init__.py` | 같음 | 수정 없음 (빈 파일) |
| `config/commands/_connect.py` | 같음 | 수정 없음 |
| `config/commands/server_connection.sh` | 같음 | 수정 없음 |
| `LICENSE` (MIT 전문) | — 의무 이행의 본체 | 수정 없음 |

**MIT 자체는 변경 고지를 요구하지 않는다**(§1의 E 행: copyleft·network 조항 없음). 위
`상태` 열은 **저장소 규칙**이다 — `SEAM_IMPLEMENTATION_MAP.md` §5-2가 패치의 등재를
요구하고, 배포물을 받는 쪽이 "이것이 upstream 그대로인가"를 물을 때 답이 있어야 한다.
diff 는 `vendor/patches/`에 있다.

**파생물 하나를 함께 등재한다.** `utils.py:748-760`의 `set_server_description()`이 만드는
프롬프트 문장은 `SEAM_IMPLEMENTATION_MAP.md` §3.3에 따라 **형태를 유지한 채 매개변수화**해
우리 loop이 다시 쓴다. 원문을 그대로 복사하면 MIT 코드의 복사이므로, 그 문장을 담는 파일도
고지 대상이다. 재빌드가 그 파일 경로를 정하는 시점에 이 표에 한 행을 더한다.

### 5.2 이행 방법 — 릴리스 절차에 넣는다

`FOUNDATION_DECISION.md` §6.2-4가 요구한 것이다. E의 의무는 **저작권 고지 + MIT 전문
포함**뿐이고 copyleft·network 조항이 없다.

1. `vendor/swe_agent_dc18a740/LICENSE`를 저장소와 배포물 양쪽에 그대로 둔다.
2. 저장소 최상위에 `NOTICE`(또는 `THIRD_PARTY_LICENSES`)를 두고 위 표를 싣는다.
3. 배포물을 만들 때 그 파일이 포함되는지 확인하는 단계를 릴리스 절차에 넣는다.

### 5.3 아직 갚지 않은 것 — 의존성 라이선스 스냅샷

**이 세션은 하지 못했고, 못한 이유를 적는다.**

- 문서 세션은 **호스트를 만지지 않고 후보 저장소 소스를 열지 않는다**(부팅 지시). 의존성
  스냅샷은 pin된 커밋의 **실제 import closure**를 봐야 만들어지고, 문서만으로는 만들 수
  없다. 추측으로 채우면 이 표가 서 있는 원칙("pack이 MIT라고 적었다는 사실은 근거가
  아니다")을 스스로 어긴다.
- E는 **잠금 파일이 없다.** `requirements.txt`가 `swebench>=2.0.0` 식 하한만 주고
  `uv.lock`/`poetry.lock`/`requirements.lock`이 전부 없다(`REPRO_MATRIX.md`). 따라서
  "E의 의존성"이라는 집합 자체가 설치 시점에 따라 달라지고, **vendored 4파일의 closure로
  좁혀서** 다시 재야 한다. §4-1이 인용한 `together`·`google-genai`·`anthropic`·`tiktoken`·
  `swebench`·`datasets`·`groq`는 **후보 전체**의 venv이지 우리가 가져가는 4파일의 것이
  아니다.

**문서로 확정할 수 있는 것 둘은 적어 둔다.**

1. **컨테이너 쪽 런타임 의존성 하나가 확정적으로 따라온다** — `config/commands/_connect.py`가
   컨테이너 안에서 **pwntools**의 `NetcatShell`을 쓴다(`ARM_E_REPORT.md` §1(a)). 우리 worker
   이미지가 그것을 담아야 하고, 따라서 pwntools와 **그 의존성**이 스냅샷 대상이다.
2. **호스트 쪽에서 따라오는 것은 표준 라이브러리와 docker CLI 호출뿐일 가능성이 높다** —
   vendored 4파일이 하는 일이 `docker exec -i`로 프로세스를 띄우고 타임아웃 읽기를 하는
   것이기 때문이다. **가능성이지 확인이 아니다.**

> **누가 언제 하는가.** 재빌드 세션이 `vendor/`를 실제로 만드는 시점에, 4파일의 import
> closure를 기계적으로 뽑고 worker 이미지의 패키지 목록과 합쳐 스냅샷한다. 결과는 이
> 문서의 §5.4로 들어온다. **그때까지 이 항목은 미상환이다.**

> **상환됨 (재빌드-2, 2026-08-08) — 단 절반이다.** 호스트 쪽은 §5.4가 채웠고, **스냅샷할
> 서드파티가 0개**라는 것이 결론이다(§5.4.3). **컨테이너 쪽(pwntools)은 여전히 미상환이고**
> worker 이미지를 빌드하는 세션이 §5.4.5를 채운다.

> **나머지 절반도 상환됨 (재빌드-5, 2026-08-08).** 유형 B worker 이미지에
> `_connect.py`·`server_connection.sh` 를 굽고 pwntools 를 넣었다. 목록은 §5.4.5.
> **이 항목 전체가 이제 닫혔다.**

### 5.4 의존성 스냅샷 — 재빌드-2, 2026-08-08

`PATH_SCOPE.md` §3.4가 명시한 예외로 재빌드가 쓰는 유일한 절이다. 다른 절과 다른 파일은
읽기 전용 그대로다.

측정 대상은 `PINS.md` §1에서 새로 clone한 `dc18a740faabd2fc625a9b018184dfc4a81cbc78`
(태그 `v0.7.0`으로 재확인)이고, 스파이크 clone(`<HOME>/candidates/`)이 아니다 —
그 트리에는 패치 여섯이 들어 있다(`SEAM_IMPLEMENTATION_MAP.md` §3).

#### 5.4.1 반입한 바이트 — upstream blob과 동일함을 확인

작업 트리가 아니라 `git cat-file blob HEAD:<path>`에서 뽑았다. 이유는 아래 §5.4.4다.

| vendored 파일 | bytes | sha256 |
|---|---|---|
| `sweagent/agent/interactive_commands.py` | 1,100 | `b88da049f7211528…` |
| `sweagent/environment/utils.py` | 45,290 | `fac9d12460d9c2a8…` |
| `config/commands/_connect.py` | 1,759 | `a31f4a4933449411…` |
| `config/commands/server_connection.sh` | 1,872 | `fd09560680017ab5…` |
| `LICENSE` | 1,147 | `7610ed3916f6674e…` |

**마지막 행이 §1의 E 행과 독립적으로 일치한다**(1147 B, 21행, `7610ed3916f6674e…`).
스파이크가 2026-08-07에 `raw.githubusercontent.com`에서 확인한 값을, 재빌드-2가
2026-08-08에 clone한 트리에서 다시 얻었다. 두 경로가 같은 바이트를 가리킨다.

`kisia_tests/test_vendor_boundary.py`가 이 다섯 값을 잠근다.

#### 5.4.2 호스트 쪽 import closure — **§5.3의 가설 2는 틀렸다**

§5.3-2는 "호스트 쪽에서 따라오는 것은 표준 라이브러리와 docker CLI 호출뿐일 **가능성이
높다**"고 적고 "가능성이지 확인이 아니다"라고 단서를 달았다. **재서 보니 함수 수준에서는
맞고 모듈 수준에서는 틀리다.** 그 둘이 갈리는 것이 이 절의 핵심 관측이다.

**(a) 허용된 세 심볼이 실제로 쓰는 것** — `ast`로 두 함수의 참조를 닫아서 뽑았다.

```
Callable  PIPE  STDOUT  os  platform  shlex  subprocess  time      ← 전부 표준 라이브러리
InteractiveSession                                                 ← vendored (§3.1)
get_logger  keys_config                                            ← sweagent 내부, 미반입
```

`get_interactive_session`은 본문 11줄(`docker exec -i` + `subprocess.Popen`),
`read_with_timeout`은 57줄(`select`/`os.read` 비차단 읽기)이다. **서드파티는 하나도 쓰지
않는다.**

**(b) 그러나 모듈을 import 하면 따라오는 것** — 모듈 수준 import는 함수가 쓰든 안 쓰든
실행된다.

| 패키지 | 어디서 | 세 심볼이 쓰는가 | 라이선스 |
|---|---|---|---|
| `simple_parsing` | `interactive_commands.py:6` (`FrozenSerializable`) | **아니다** — 허용하지 않은 `InteractiveSessionConfig`만 쓴다 | 미확인 |
| `datasets` (HuggingFace) | `utils.py:19` | 아니다 | 미확인 |
| `ghapi` | `utils.py:20` | 아니다 | 미확인 |
| `GitPython` | `utils.py:21` | 아니다 | 미확인 |
| `unidiff` | `utils.py:22` | 아니다 | 미확인 |
| `docker` | `utils.py:24-26` | 아니다 — 우리가 REJECT한 컨테이너 생성 경로가 쓴다 | 미확인 |
| `rich` | `sweagent/utils/log.py:7` | 간접 (`get_logger`) | 미확인 |
| `config` (PyPI) | `sweagent/utils/config.py:7` | 간접 (`keys_config`) | 미확인 |

**라이선스를 "미확인"으로 남긴 것은 게으름이 아니다.** 이 여덟을 가져갈지 자체가 아직
결정되지 않았고(§5.4.3), 이 문서의 원칙은 "가져갈 것만 원문으로 확인한다"이다. 가져가기로
정해지면 그 시점에 §1의 양식대로 커밋 SHA 고정 URL과 함께 채운다.

**(c) 반입 목록에 없는데 import가 요구하는 upstream 파일 넷**

```
sweagent/__init__.py          524 B   REPO_ROOT/CONFIG_DIR 를 정하고 assert 로 검사한다
sweagent/utils/__init__.py      0 B
sweagent/utils/config.py    2,977 B   keys.cfg 를 읽는 설정 시스템. PACKAGE_DIR.parent/keys.cfg
sweagent/utils/log.py       1,958 B   rich 기반 로거
```

`SEAM_IMPLEMENTATION_MAP.md` §3.1의 목록은 **넷 + LICENSE**이고 이 넷은 거기 없다.

**(d) 실행으로 확인** — 추론이 아니다.

```
$ .venv/Scripts/python -c "import vendor.swe_agent_dc18a740.sweagent.agent.interactive_commands"
ModuleNotFoundError: No module named 'simple_parsing'
$ .venv/Scripts/python -c "import vendor.swe_agent_dc18a740.sweagent.environment.utils"
ModuleNotFoundError: No module named 'datasets'
```

경로 해소 자체는 된다(PEP 420 namespace package). 막는 것은 **모듈 수준 서드파티
import**이고, 그것을 넘겨도 다음에 `No module named 'sweagent'`가 온다 — vendored 파일들이
`from sweagent...`라는 **절대 import**를 쓰는데 우리 트리에서 그 이름은
`vendor.swe_agent_dc18a740.sweagent`이기 때문이다.

#### 5.4.3 결정과 그 결과 — 호스트 쪽 서드파티 의존성은 **0개**다

§5.4.2를 운영자에게 보고했고(`docs/rebuild/REBUILD_LOG.md` 재빌드-2 O-6), **운영자가
2026-08-08에 "사소 패치로 import만 손본다"를 선택했다.** 그 결과:

- 반입 파일이 5 → **9개**가 됐고, **계약도 같은 날 `R5-3`으로 그 아홉을 적었다**
  (`SEAM_IMPLEMENTATION_MAP.md` §3.1(b)·§3.1.a, 등재는 `spec.md` §8.5). 더해진 넷
  (`sweagent/{__init__, utils/__init__, utils/config, utils/log}.py`)은 upstream 바이트
  그대로 들어왔고 그중 둘만 패치됐다.
- 패치 **넷**(`V-02`~`V-05`)이 모듈 수준 import 표면만 바꾼다. 전부 `spec.md` §6.1(R3-5)의
  **사소 패치**이고 diff 는 `vendor/patches/` 에 있다. **구조 패치 누계는 0이다.**
- **그 결과 호스트 쪽 서드파티 의존성이 0개다.** 세 심볼을 import 해도 딸려 오는
  서드파티가 없다:

```
$ .venv/Scripts/python -c "import sys;
    from vendor.swe_agent_dc18a740.sweagent.environment.utils import (
        get_interactive_session, read_with_timeout);
    print(sorted({m.split('.')[0] for m in sys.modules} &
        {'datasets','ghapi','git','unidiff','docker','simple_parsing','rich','config'}))"
[]
```

`kisia_tests/test_vendor_boundary.py::test_vendor_pulls_no_third_party` 가 이 성질을
잠근다.

**따라서 §5.3이 남긴 "의존성 라이선스 스냅샷" 부채는 호스트 쪽에서 상환됐다** — 스냅샷할
서드파티가 없기 때문이다. §5.3-2의 가설("표준 라이브러리와 docker CLI 호출뿐")이 **패치
이후에 참이 됐다.** 패치 이전에 거짓이었다는 사실은 §5.4.2에 그대로 남긴다.

**남는 의무는 §5.1의 고지뿐이고 그것은 대상이 늘었다** — vendored 파일 9개 전부가 MIT
`(c) 2024 John Yang, Carlos E. Jimenez, Alexander Wettig, Shunyu Yao, Karthik Narasimhan,
Ofir Press` 이고, **패치한 파일에는 변경 사실을 함께 적어야 한다.** MIT 자체는 변경 고지를
요구하지 않지만(§1의 E 행: copyleft·network 조항 없음), `SEAM_IMPLEMENTATION_MAP.md` §5-2가
저장소 규칙으로 요구한다.

#### 5.4.4 부수 관측 — 줄끝 변환이 출처 확인을 깬다

`core.autocrlf=true`(Windows 워크스테이션의 system 설정) 아래에서 clone하면 작업 트리가
CRLF로 부푼다. **`LICENSE`가 1,147 → 1,168 바이트가 되고**(줄 수 21만큼), sha256이 §1의
값과 달라진다. 그 상태로 반입하면 셋이 동시에 깨진다: §1의 확인과 대조 불가, upstream과
재diff 불가(`SEAM_IMPLEMENTATION_MAP.md` §3.1-1), 그리고 컨테이너에 굽는
`server_connection.sh`가 CRLF 셰방으로 죽는다.

막은 방법: 저장소 `.gitattributes`에 `vendor/** -text`. `text eol=lf`가 아니라 `-text`인
것은 **어느 방향으로도 변환하지 않는다**는 뜻이고, 여기서 필요한 것이 그쪽이다.

#### 5.4.5 컨테이너 쪽 (pwntools) — **상환됨 (재빌드-5, 2026-08-08)**

§5.3-1이 확정적이라고 한 항목이다. worker 이미지를 빌드하는 시점에 패키지 목록과 함께
채운다.

##### 5.4.5.a 재빌드-4가 채우지 **못한** 이유 (기록으로 남긴다)

**재빌드-4가 worker 이미지를 빌드했다. 그런데 이 항목은 채워지지 않았다.**

그 이미지는 **유형 A** 골든 궤적이 도는 환경이고, vendored 컨테이너 자산
(`config/commands/_connect.py`)이 들어가지 않는다. pwntools 를 요구하는 것은 그 파일이고
(`ARM_E_REPORT.md` §1(a)), 유형 A 는 세션을 열지 않으므로 굽지 않았다 — **쓰지 않는 자산을
구우면 라이선스 고지 대상만 늘어난다.**

**따라서 "빌드했으니 상환됐다"로 접지 않는다.** 채우는 세션은 `_connect.py` 와
`server_connection.sh` 를 `/opt/kisia/session/` 에 굽는 세션, 즉 §4 어댑터와 유형 B
이미지를 만드는 세션이다(`PATH_SCOPE.md` §2.3).

**참고로 재빌드-4의 유형 A 이미지가 담은 것** — 이 표가 pwntools 스냅샷은 아니지만,
그때 이 이미지가 어디까지 갔는지의 기준선이다.

| | |
|---|---|
| reference / digest | `kisia/worker-a:1` · `sha256:49a321f3f86522c3ea5111f9fe99e0770c5af2749fb63ac91c3a85b31b97af33` |
| Dockerfile | `images/worker/Dockerfile` (재빌드의 트리) · 고정은 `images/images.lock.yaml` |
| base | `ubuntu:24.04` (호스트에 이미 있던 것. pull 하지 않았다 — 프록시가 `POST /images/create` 를 거부한다) |
| 명시 설치 | `binutils`(strings) · `python3`. 둘 다 Ubuntu 배포 패키지이고 **vendored 코드가 아니다** |
| vendored 자산 | **없음** |
| pwntools | **없음** |

빌드는 `ctf` 가 했다 — 프록시가 `POST /build` 를 거부한다(`HOST_EXCEPTIONS.md` §2.1.b).

##### 5.4.5.b 유형 B worker 이미지 — 스냅샷 (재빌드-5, 2026-08-08)

**재빌드-4의 유형 A 이미지를 고치지 않고 새 이미지를 만들었다.** 그 이미지 위에서 골든 A가
8칸 PASS 를 받았고, 그 스트림이 재현 가능해야 한다.

| | |
|---|---|
| reference / digest | `kisia/worker-b:1` · `sha256:451558c5d7333e6b574572e2469e8e59ac56426aff9d956a162f723c603d5894` |
| Dockerfile | `images/worker-b/Dockerfile` (재빌드의 트리) · 고정은 `images/images.lock.yaml` |
| base | `ubuntu:24.04` (재빌드-4와 같은 것. pull 하지 않았다) |
| vendored 자산 | `/opt/kisia/session/_connect.py` (`a31f4a49…`) · `/opt/kisia/session/server_connection.sh` (`fd095606…`) — **둘 다 upstream 바이트 그대로**, 마운트가 아니라 구움(`PATH_SCOPE.md` §2.3) |

**명시 설치 다섯과 그 버전** (`dpkg-query`, 이미지 안에서 실측):

| 패키지 | 버전 | 왜 |
|---|---|---|
| `python3-pwntools` | **4.12.0-1** | `_connect.py` 의 `from pwn import *` |
| `python3-setproctitle` | 1.3.3-1build2 | 같은 파일의 `import setproctitle` |
| `binutils` | 2.42-4ubuntu2.10 | 유형 A와 같은 도구 계층 유지 |
| `python3` | 3.12.3-0ubuntu2.1 | 세션 리더(pty)와 P-S2-c |
| `procps` | 2:4.0.4-4ubuntu3.2 | 진단용 `ps`. **판정에 쓰지 않는다** — 생존자 계수는 호스트 `/proc` 에서 온다 |

**pwntools 가 끌고 온 의존 닫힘** (같은 실측, `ii` 상태만):

```
python3-bcrypt 3.2.2-1build1          python3-capstone 4.0.2-5.1build1
python3-certifi 2023.11.17-1          python3-cffi-backend 1.16.0-2build1
python3-chardet 5.2.0+dfsg-1          python3-colored-traceback 0.3.0-4
python3-cryptography 41.0.7-4ubuntu0.4 python3-dateutil 2.8.2-3ubuntu1
python3-idna 3.6-2ubuntu0.2           python3-intervaltree 3.0.2-1.1
python3-mako 1.3.2-1ubuntu0.1         python3-markupsafe 2.1.5-1build2
python3-nacl 1.5.0-4build1            python3-packaging 24.0-1
python3-paramiko 2.12.0-2ubuntu4.1    python3-pip 24.0+dfsg-1ubuntu1.3
python3-plumbum 1.8.2-1               python3-psutil 5.9.8-2build2
python3-pyelftools 0.30-1             python3-pygments 2.17.2+dfsg-1
python3-requests 2.31.0+dfsg-1ubuntu1.1  python3-ropgadget 7.4+dfsg-1
python3-rpyc 5.3.1-1                  python3-serial 3.5-2
python3-six 1.16.0-4                  python3-socks 1.7.1+dfsg-1
python3-sortedcontainers 2.4.0-2      python3-unicorn 2.0.1.post1-4.1build1
python3-urllib3 2.0.7-1ubuntu0.7      python3-zstandard 0.22.0-1build1
```

**라이선스 관점에서 이것이 뜻하는 것.** 전부 **Ubuntu 24.04 배포 패키지**이고 PyPI 에서
직접 끌어온 것이 하나도 없다. 배포 채널이 하나이므로 §1의 양식(커밋 SHA 고정 URL)이
아니라 **배포판 버전 고정**이 출처 확인의 형태이고, 그 고정은 `images/images.lock.yaml`
의 이미지 digest 가 나른다 — 이미지가 같으면 이 목록도 같다.

**접지 않고 적는 것 둘.**

1. **`python3-pip` 이 딸려 들어왔다.** `python3-pwntools` 의 의존이다. 런타임에 무엇을
   설치하지는 않지만(worker 는 `--internal` 네트워크라 egress 가 없다) **그 경로가
   이미지 안에 존재한다**는 사실은 `PATH_SCOPE.md` §2.3-3("런타임 패키지 설치 금지")이
   막으려는 것에 닿는다. 없애려면 pwntools 를 apt 가 아닌 방식으로 넣어야 하고 그러면
   배포판 고정을 잃는다 — **바꾸지 않고 사실만 남긴다.**
2. **`server_connection.sh` 는 굽되 우리 도구 계층이 source 하지 않는다.**
   `PATH_SCOPE.md` §2.3이 목록에 넣었으므로 굽는다. 그 파일의 마커 프로토콜
   (`<<INTERACTIVE||…||INTERACTIVE>>`)은 우리가 vendor 하지 않는 `swe_env.py` 가 읽는
   것이다(`SEAM_IMPLEMENTATION_MAP.md` §3.2). **고지 대상에는 들어가고 실행 경로에는
   들어가지 않는다.**

**남는 고지 의무.** 구운 두 파일은 MIT `(c) 2024 John Yang, Carlos E. Jimenez, Alexander
Wettig, Shunyu Yao, Karthik Narasimhan, Ofir Press` 이고 §5.1의 대상이다. **둘 다 패치되지
않았다** — `(예정) V-01`(`_connect.py` 의 `cmdloop`)은 적용하지 않았고, 그 이유는
`REBUILD_LOG.md` 재빌드-5 §2다.
