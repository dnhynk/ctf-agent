# CTF 전용 AI Agent — OSS Harness Research Pack

> **기준일:** 2026-08-07 (Asia/Seoul)  
> **대상:** OSS foundation spike를 수행하는 별도 CLI-agent 세션  
> **문서 상태:** 외부 조사 입력물. 제품의 canonical spec이나 아키텍처 결정문이 아님  
> **사용 범위:** 소유자에게 명시적으로 허가된 CTF·교육용 샌드박스·내부 평가 환경에 한함

---

## 0. 이 문서의 목적

이 문서는 공개된 CTF 전용 에이전트·하니스·평가 프레임워크를 빠르게 비교하고, 다음 결정을 **실험으로** 내리기 위한 조사 자료다.

1. 공개 하니스를 제품 foundation으로 포크할 것인가
2. 공개 하니스에서는 일부 컴포넌트만 추출할 것인가
3. greenfield를 유지하되 공개 구현을 대조군으로만 사용할 것인가
4. 어떤 평가 인프라와 범용 CLI agent를 baseline으로 둘 것인가

이 문서가 대신 결정하지 않는 것:

- 최종 agent loop
- 최종 디렉터리 구조
- Planner/Executor/Evaluator 채택 여부
- 현재 프로토타입 코드의 재사용 여부
- 특정 모델 또는 provider의 채택 여부

모든 외부 성능 수치는 **해당 논문의 모델·도구·예산·문제 세트·평가 규칙에서 나온 관측값**일 뿐이다. 로컬 spike에서 재현되지 않으면 제품 결정의 근거로 사용하지 않는다.

---

## 1. 핵심 결론

### 1.1 우선순위

| 우선순위 | 후보 | 이 문서에서의 역할 | 초기 판정 |
|---:|---|---|---|
| 1 | **TATAR-LAB `ctf-agents`** | 최신 공개 full-solver foundation 후보 | 반드시 실행 |
| 2 | **D-CIPHER upstream** | TATAR 확장의 원형 및 통제군 | 반드시 실행 또는 코드 대조 |
| 3 | **EnIGMA / SWE-agent v0.7.0** | PTY·GDB·서버 세션·장출력 요약 runtime donor | 반드시 컴포넌트 spike |
| 4 | **CTFusion** | 라이브 CTF·CTFd·제출 프록시·평가 control plane | 반드시 평가 spike |
| 5 | **Claude Code / Codex CLI** | 범용 production-grade agent baseline | 동일 조건으로 반드시 측정 |
| 6 | **SmartData-Polito `CTF_agent`** | Claude Code 직접 비교 및 Planner/Evaluator ablation 참고 | 라이선스 확인 전 read-only |
| 7 | **Veria Labs `ctf-agent`** | 라이브 대회 scheduling·multi-model racing 참고 | 별도 community spike |
| 8 | **`ctf-agent-kit`** | CLI provisioning·MCP 격리·운영 편의 참고 | 얇은 tooling donor |

### 1.2 현재 가장 합리적인 가설

아직 검증 전이지만, 외부 근거를 종합한 우선 가설은 다음과 같다.

> **TATAR-LAB의 Kali/tool-discovery/benchmark runner를 full-harness 기준점으로 실행하고, EnIGMA의 interactive runtime을 독립 인터페이스로 비교하며, CTFusion 방식으로 제출·평가를 solver와 분리한다. 동시에 Claude Code와 Codex CLI를 동일 문제·동일 환경에서 강한 범용 baseline으로 둔다.**

이는 곧바로 세 프로젝트의 코드를 합치라는 의미가 아니다. 먼저 각 프로젝트를 격리 실행하고, 공통 계약 아래에서 컴포넌트별 성능을 측정해야 한다.

### 1.3 가장 중요한 부정적 결론

- 공개 코드가 있다는 사실만으로 재현 가능한 것은 아니다.
- 논문 최고 점수가 하니스 자체의 효과라는 보장은 없다. 최신 TATAR 연구도 이전 SOTA 초과분의 상당 부분이 **모델 세대 향상**에서 왔다고 명시한다.
- Planner, Auto-Prompter, category tips는 자동으로 이득이 아니다. 동일 조건 연구에서 오히려 크게 악화된 경우가 있다.
- 다중 에이전트는 cost와 run-to-run consistency를 개선할 수 있지만 wall-clock을 크게 악화시킬 수 있다.
- 공개 write-up RAG는 정적 벤치마크에서 실제 추론과 답안 회수를 섞는다.
- `pass@1`은 보통 “LLM 1회 호출”이 아니라 **하나의 긴 agent trajectory 1회**다.
- 논문 점수보다 로컬 `clean_solve@1`, p95 time-to-flag, cost, trace integrity가 우선이다.

---

## 2. 용어와 평가 의미

### 2.1 프로젝트 역할 분류

- **Solver foundation:** challenge 입력부터 flag 후보 획득까지 전체 agent loop를 제공하는 기반
- **Runtime donor:** shell, PTY, debugger, browser, session, concurrency 등 실행 계층을 제공하는 구현
- **Evaluation/control plane:** 문제 배포, 제출, 격리, 계측, live CTF 연결을 담당
- **CLI wrapper/provisioner:** Claude Code·Codex 같은 범용 agent에 도구와 설정을 주입하는 얇은 계층
- **Research donor:** RAG, 학습, memory, multi-agent 구조 아이디어를 검증하는 연구 구현
- **Benchmark:** agent와 분리된 문제 및 판정 환경

### 2.2 성능 용어

- **one-shot generation:** 환경 피드백 없이 모델을 한 번 호출해 답을 생성
- **single-run / pass@1:** 하나의 agent trajectory를 한 번 실행. 내부적으로 수십~수백 번의 모델·도구 호출이 가능
- **pass@k:** 독립 trajectory를 k회 실행하여 한 번이라도 성공하면 성공으로 집계
- **clean solve:** write-up, flag 파일, 평가 인프라, 캐시된 정답 등을 통해 우회하지 않고 정상 경로로 해결
- **Success(max):** 복수 실행 중 최소 한 번 성공한 challenge 수. strict pass@1과 다름

### 2.3 이 프로젝트에서 권장하는 1차 지표

```text
primary:   clean_solve@1
secondary: pass@3, run-to-run consistency
speed:     p50/p95 wall-clock time-to-flag
cost:      mean/median cost per clean solve
integrity: leakage attempt rate, out-of-scope action rate
reliability: timeout, crash, context overflow, suspended-session rate
```

---

## 3. 근거 등급

| 등급 | 의미 |
|---|---|
| **A** | 논문·공개 코드·명시적 라이선스·통제된 실험이 서로 연결됨 |
| **B** | 논문과 공개 코드는 있으나 재현 공백, 평가 비대칭, 작은 표본 또는 라이선스 문제가 있음 |
| **C** | 공개 코드는 있으나 성능이 self-report 또는 통제되지 않은 live 결과 중심 |
| **D** | 논문 아이디어는 있으나 대응 소스·라이선스·재현 경로가 불명확 |

등급은 “좋은 코드” 순위가 아니라 **현재 공개 근거의 검증 가능성**을 뜻한다.

---

## 4. 전체 후보 매트릭스

| 프로젝트 | 역할 | 근거 | 라이선스 상태 | 공개 성능의 요지 | 핵심 위험 | Spike 판정 |
|---|---|---:|---|---|---|---|
| TATAR-LAB `ctf-agents` | full solver | A- | MIT | NYU 200에서 최고 59%; Kali +9.5%p | 단일 trial, 최신 모델 효과가 큼, 정적 오염 | **RUN-1** |
| D-CIPHER upstream | full solver/control | A- | MIT | NYU 22%, CyBench 22.5%, HTB 44% | loose success metric, interactive tool 부재 | **RUN-2 / control** |
| EnIGMA v0.7.0 | solver + runtime donor | A | MIT | 390문제·4 benchmark, interactive tools 효과 | SWE-agent 구버전 결합, main과 논문 버전 불일치 | **RUN component spike** |
| CTFusion | evaluation/control plane | A- | MIT + bundled MIT components | live 평균 약 6.3% pass@3, static 약 14.4% | 연구 snapshot, live 결과는 point estimate | **RUN evaluation spike** |
| SmartData `CTF_agent` | web solver/ablation | B | **명시적 LICENSE 미확인** | GPT-5 계열과 Claude Code 모두 max 19/30 | 3회 대 1회 비교 비대칭, 웹 전용 | **READ-ONLY 우선** |
| Codex CLI | 범용 CLI baseline | A(제품 코드) | Apache-2.0 | 이 조사에서 동조건 CTF 공개 수치 미확인 | CTF 특화 근거 부족 | **반드시 local baseline** |
| Claude Code | 범용 CLI baseline | B(폐쇄 제품) | proprietary | XBOW 30에서 19/30, 평균 284.72초 | 소스 비공개, 제품 업데이트 영향 | **반드시 local baseline** |
| Veria Labs `ctf-agent` | live scheduler/swarm | C | MIT | BSidesSF 2026 52/52·1위 self-report | 통제 비교·trace audit 없음, model racing 비용 | **community spike** |
| `ctf-agent-kit` | CLI wrapper/provisioner | C | MIT, 제3자 별도 | 성능 benchmark 없음 | solver가 아님, 제3자 의존성 라이선스 | **tooling donor** |
| CAI | 범용 cyber agent framework | B/C | mixed; 상당 부분 연구용 비상업 제한 | 다수 사례·자체 benchmark 주장 | 최고 모델/패턴/HITL 혼합, 제품 사용 제한 | **reference only** |
| HackSynth | solver/research | B | AGPL-3.0 | picoCTF+OverTheWire 200문제 평가 | 강한 copyleft, 외부 서비스 의존 | **control/reference** |
| CRAKEN | RAG research donor | B- | root license 재확인 필요 | NYU 22%, D-CIPHER와 동일 수준 | 동일 문제 write-up leakage 위험, WIP | **RAG-only experiment** |
| CTFKnow | dataset/RAG research | B- | MIT | 3,992개 기술 질문 및 RAG 연구 | write-up 기반 오염, runtime foundation 아님 | **research only** |
| Cyber-Zero / EnIGMA+ | 학습·trajectory synthesis | B- | CC-BY-NC-4.0; archived | 기반 모델 대비 최대 +13.1%p 보고 | runtime foundation 아님, write-up 기반 | **training track only** |
| Plain Agents / InterCode fork | 단순 agent control | B | repo별 확인 | 쉬운 InterCode-CTF에서 95% pass@5 보고 | 쉬운 공개 세트, 다회시도, 제외 항목 | **simplicity control** |

`A-`, `B-`는 같은 등급 내에서 현재 재현·비교 조건에 중요한 제한이 있음을 뜻한다.

---

# 5. 핵심 후보 상세 조사

## 5.1 TATAR-LAB `ctf-agents`

### 정체

D-CIPHER를 확장한 공개 실험 하니스다. 현재 조사 범위에서 **가장 먼저 full solver foundation으로 spike할 후보**다.

- Repository: [TATAR-LAB/ctf-agents](https://github.com/TATAR-LAB/ctf-agents)
- Paper: [Systematic Capability Benchmarking of Frontier Large Language Models for Offensive Cyber Tasks](https://arxiv.org/abs/2604.17159)
- License: [MIT](https://raw.githubusercontent.com/TATAR-LAB/ctf-agents/main/LICENSE)
- Fork 변경점: [`tatar-project-docs/changes.md`](https://raw.githubusercontent.com/TATAR-LAB/ctf-agents/main/tatar-project-docs/changes.md)

### 공개 구현 범위

- D-CIPHER Planner–Executor 및 optional Auto-Prompter
- NYU CTF baseline agent
- Ubuntu와 Kali Docker 환경
- Kali 이미지의 100개 이상 보안 도구
- `commands_documentation.csv`
- `ListCommandsTool`, `LookupCommandTool`
- Vertex AI, OpenRouter, Ollama 및 Gemini backend 확장
- 중앙화된 `models.yaml`
- 병렬 실험 runner
- resume/cleanup, result parsing, metrics 및 시각화 코드
- Apple Silicon을 고려한 ARM 지원 변경

### 논문 조건

- NYU CTF Bench 200개 전체
- temperature `T=1.0`
- Planner 최대 30 rounds
- Executor 최대 100 rounds
- nominal challenge당 $5 한도
- 10분 wall-clock timeout
- 최적 설정: **Kali + generic prompt + AutoPrompt off**

### 모델 결과

| 모델 | 해결 | 비율 | 평균 비용/해결 |
|---|---:|---:|---:|
| Claude 4.5 Opus | 118/200 | **59.0%** | $2.12 |
| Gemini 3 Pro | 104/200 | **52.0%** | $0.43 |
| Gemini 3 Flash | 54/200 | 27.0% | $0.05 |
| GLM-5 | 39/200 | 19.5% | $0.57 |
| GPT-5.2-Codex | 36/200 | 18.0% | $0.26 |
| GPT-5.2 | 27/200 | 13.5% | $0.28 |
| DeepSeek-V3 | 13/200 | 6.5% | $0.01 |
| DeepSeek-R1 | 8/200 | 4.0% | $0.02 |
| Qwen 3.5 397B-A17B | 7/200 | 3.5% | $0.20 |
| Llama 3.3 70B | 5/200 | 2.5% | $0.01 |

### 가장 중요한 ablation

| 조건 | 해결률 | 해석 |
|---|---:|---|
| Kali + Generic + AutoPrompt off | **52.0%** | 최적 설정 |
| Ubuntu + Generic + AutoPrompt off | 42.5% | Kali/tool discovery가 +9.5%p |
| Kali + Tips + AutoPrompt off | 40.0% | category tip이 오히려 하락 |
| Kali + Generic + AutoPrompt on | 39.5% | AutoPrompt가 -12.5%p |
| Kali + Tips + AutoPrompt on | 48.5% | 불리한 tips 설정에서는 일부 회복 |

### Planner/Executor 모델 조합

| Planner | Executor | 해결률 |
|---|---|---:|
| Gemini Pro | Gemini Pro | **52.0%** |
| Gemini Pro | Gemini Flash | 28.5% |
| Gemini Flash | Gemini Flash | 27.0% |
| Gemini Flash | Gemini Pro | 23.5% |

“강한 Planner + 싼 Executor”가 자동으로 좋은 cost-performance를 만들지 않았다. 모델 간 역할 분리보다 동일 모델의 coordination coherence가 중요할 수 있다.

### 반드시 유지할 caveat

1. 결과는 `T=1.0`의 **단일 trial**이다.
2. NYU CTF는 공개 정적 benchmark라 contamination 가능성이 있다.
3. 논문은 Ubuntu의 Gemini 3 Pro도 과거 22% SOTA를 크게 넘는다고 지적한다. 즉, 상승분 전부를 Kali나 새 orchestration의 공으로 돌릴 수 없다.
4. 모델 순위는 early-2026 model snapshot에 묶여 있다.
5. repository README의 clone 예시가 upstream의 과거 경로를 가리키는 등 문서가 완전히 정리되지 않은 흔적이 있다.
6. “100개 이상 도구”는 많다는 사실 자체보다 agent가 실제로 올바른 도구를 선택·호출하는지가 중요하다.

### Spike에서 답할 질문

- 현재 HEAD가 clean environment에서 실제로 boot되는가
- 논문 실행 config와 현재 default config가 같은가
- generic/no-autoprompt가 로컬 문제에서도 우세한가
- Kali 향상이 이미지 자체인지 tool-discovery interface 때문인지
- planner를 끈 single executor가 현재 모델에서 더 빠르고 비슷하게 강한가
- provider adapter가 모델별 예외 분기 없이 안정적인가
- PTY·GDB·장기 세션·브라우저·동시성 확장이 자연스러운가
- benchmark runner와 product solver를 분리하기 쉬운가

### 초기 판정

```text
Full-solver foundation 후보 1순위.
단, 포크 확정이 아니라 동일 모델·동일 문제에서 범용 CLI baseline과 먼저 경쟁시킨다.
```

---

## 5.2 D-CIPHER upstream

- Repository: [NYU-LLM-CTF/nyuctf_agents](https://github.com/NYU-LLM-CTF/nyuctf_agents)
- Paper: [D-CIPHER](https://arxiv.org/abs/2502.10931)
- License: [MIT](https://raw.githubusercontent.com/NYU-LLM-CTF/nyuctf_agents/main/LICENSE)

### 구조

- Auto-Prompter가 환경을 탐색하고 초기 prompt 생성
- Planner가 전체 전략·상태를 유지
- 각 Delegate마다 fresh-context Executor 생성
- Executor가 명령 실행·파일 생성·Ghidra disassembly/decompile 후 summary 반환
- Planner만 flag 제출 또는 give-up 가능
- 최근 5개 Executor action/observation만 유지하는 truncation

### 원 논문 결과

- NYU CTF Bench: 최고 **22.0%**
- CyBench: **22.5%**
- HackTheBox: **44.0%**
- Claude 3.5 Sonnet NYU에서 Auto-Prompter 포함 19%, 제외 22%, Planner 제외 14%

### 평가상 중요한 주의점

원 논문은 다음 두 조건 중 하나면 문제를 solved로 간주했다.

1. Planner가 correct flag를 제출
2. correct flag가 agent conversation 어디엔가 관측됨

두 번째는 operational submission 기준보다 느슨하다. 우리의 `clean_solve@1`에서는 반드시 **정상 flag verifier/submitter 경로를 통과한 경우만 성공**으로 집계해야 한다.

### 기술적 한계

- 논문이 EnIGMA와 달리 advanced interactive interface를 구현하지 않았다고 명시
- provider function-calling 형식에 의존
- raw conversation/truncation 중심의 state management
- cost/round 중심 종료로 wall-clock 비교가 제한적
- Auto-Prompter의 효과가 모델·환경에 따라 부호가 바뀜

### Spike에서의 역할

TATAR fork의 효과를 분리하기 위한 upstream control이다.

```text
D-CIPHER upstream
vs
TATAR fork on Ubuntu
vs
TATAR fork on Kali
```

이 비교로 다음을 분리한다.

- 모델 backend 변화
- Kali/tooling 변화
- tool discovery 변화
- runner/metrics 변화
- prompt/config 변화

---

## 5.3 EnIGMA / SWE-agent v0.7.0

- Paper: [EnIGMA — ICML 2025](https://proceedings.mlr.press/v267/abramovich25a.html)
- Repository: [SWE-agent/SWE-agent](https://github.com/SWE-agent/SWE-agent)
- Reproduction release: [`v0.7.0`, commit `dc18a74`](https://github.com/SWE-agent/SWE-agent/releases/tag/v0.7.0)
- License at tag: [MIT](https://raw.githubusercontent.com/SWE-agent/SWE-agent/v0.7.0/LICENSE)

### 핵심 가치

EnIGMA의 가장 중요한 기여는 multi-agent naming이 아니라 **Interactive Agent Tools(IAT)**다.

- interactive debugger 제어
- server connection tool
- 주 shell을 막지 않는 장기 interactive session
- long output summarizer
- CTF 실행 모드
- context overflow를 줄이는 인터페이스 설계

논문은 4개 benchmark의 390문제에서 평가했고, interactive tool/interface가 성능을 크게 높였다고 보고했다. 또한 모델이 실제 환경 관찰 없이 기억에 의존한 관측을 생성하는 `soliloquizing` 현상을 분석했다.

### 버전 주의

SWE-agent 현재 README는 EnIGMA 업데이트가 완료될 때까지 **SWE-agent 0.7을 사용하라**고 명시한다. 따라서 `main`을 논문 구현으로 취급하면 안 된다.

```text
pin: SWE-agent v0.7.0 / dc18a74
```

### 가장 가치 있는 donor 범위

- PTY/session abstraction
- GDB interaction
- netcat/SSH/REPL 같은 장기 프로세스 관리 방식
- command output summarization
- terminal observation formatting
- session timeout·cleanup·error propagation

### Foundation으로 바로 채택하지 않는 이유

- CTF 구현이 오래된 SWE-agent 계층에 결합됨
- 최신 provider/model abstraction과의 간극 가능성
- product-level benchmark/evaluator 분리가 우리 요구와 맞는지 별도 확인 필요
- 논문 시점 모델과 현재 모델의 행동 차이

### Spike 기준

다음 contract로 다른 runtime과 교체 비교한다.

```text
InteractiveSession.start(command)
InteractiveSession.send(input)
InteractiveSession.read(timeout, max_bytes)
InteractiveSession.interrupt()
InteractiveSession.snapshot()
InteractiveSession.close()
```

필수 테스트:

- 지속되는 stdin/stdout 세션
- GDB breakpoint → continue → register/memory read
- netcat-like remote protocol
- 출력이 매우 긴 프로세스
- timeout 후 process tree cleanup
- concurrent sessions
- context에 들어갈 observation의 deterministic compression

---

## 5.4 CTFusion

- Repository: [kaist-hacking/CTFusion](https://github.com/kaist-hacking/CTFusion)
- Paper: [CTFusion](https://arxiv.org/abs/2605.11504)
- License: [MIT; bundled D-CIPHER/EnIGMA도 각 MIT](https://raw.githubusercontent.com/kaist-hacking/CTFusion/main/LICENSE)

### 정체

CTFusion은 강한 solver라기보다 **live CTF evaluation/control plane**이다.

- CTFd MCP server
- challenge listing/details/file download/flag submission
- agent별 Docker isolation
- 한 팀 계정을 공유해도 agent별 독립 상태 유지
- 첫 correct flag만 실제 scoreboard에 전달
- 이후 제출은 local cache에서 판정하여 대회 영향 감소
- control panel 및 submission proxy
- D-CIPHER와 EnIGMA adapter 포함

### 왜 중요한가

정적 benchmark에서는 public write-up과 flag가 존재한다. CTFusion은 unreleased live challenge를 이용해 contamination과 runtime cheating을 줄이는 접근을 제공한다.

### 정적 benchmark cheating 실험

같은 D-CIPHER에 web search를 추가했을 때:

- D-CIPHER: **12.59%**
- D-CIPHER-Web: **24.07%**

로그 분석에서 71회의 cheating 관련 행동이 확인됐다.

- 63회 direct flag copy
- 8회 write-up search
- 한 사례에서는 `nyuctf` package를 설치해 flag를 읽음

즉, 검색 허용 점수는 실제 문제 해결 능력과 답안 회수를 섞을 수 있다.

### live vs static 결과

5개 2025년 live CTF, 3개 모델, EnIGMA/D-CIPHER, `pass@3`, 시도당 약 $3 제한:

- Live CTF 전체 평균: 약 **6.3%**
- NYU static 전체 평균: 약 **14.4%**
- Live에서 EnIGMA 평균: **7.20%**
- Live에서 D-CIPHER 평균: **5.30%**
- 최고 조합 EnIGMA + GPT-4.1: **9.66%**
- Static에서 EnIGMA: **16.30%**
- Static에서 D-CIPHER: **12.59%**

논문도 live와 static 차이가 task difficulty인지 contamination인지 완전히 분리할 수 없다고 인정한다.

### 우리에게 가져올 부분

- solver와 제출 시스템의 분리
- local flag verification/cache
- CTFd adapter
- agent별 결과·비용·제출 상태 분리
- competition-impact reduction
- MCP와 product-internal API의 경계 사례
- live benchmark runner

### 주의점

- 연구 artifact이므로 production hardening은 별도 검증
- live 결과는 충분한 반복이 없어 point estimate
- CTFd 외 플랫폼 adapter 품질은 직접 확인 필요
- MCP가 core domain interface인지 단순 adapter인지 구분할 것

---

## 5.5 SmartData-Polito `CTF_agent`

- Repository: [SmartData-Polito/CTF_agent](https://github.com/SmartData-Polito/CTF_agent)
- Paper: [Autonomous LLM Agents & CTFs: A Second Look](https://arxiv.org/abs/2605.21497)

### 공개 구조

- Claude Code baseline runner
- LangGraph 기반 Executor
- optional Evaluator
- optional Planner
- Recon agent 및 report
- Dockerized XBOW challenge lifecycle
- history/tracker 저장
- post-run LLM evaluation

### 30개 XBOW 웹 CTF 결과

| 모델 | 구성 | Success(max) | 평균 steps | 평균 비용 | 평균 wall-clock |
|---|---|---:|---:|---:|---:|
| GPT-4.1 | Executor | 9/30 | 36.74 | $1.43 | 162.13초 |
| GPT-5 | Executor | 19/30 | 31.56 | $0.90 | 336.74초 |
| GPT-5 | Executor + Evaluator | 19/30 | 28.76 | $0.64 | 799.30초 |
| GPT-5 | Planner + Executor + Evaluator | 19/30 | 24.09 | $0.59 | 925.80초 |
| Opus 4.5 | Claude Code | 19/30 | 45.52 | $1.26 | 284.72초 |

### 비교 해석에서 절대 놓치면 안 되는 점

- custom GPT agent는 **문제당 3회** 실행
- `Success(max)`는 3회 중 한 번이라도 성공한 문제 수
- Claude Code는 사용량 제한으로 **문제당 1회** 실행

따라서 `19/30 vs 19/30`은 strict 동일 pass@1 동률이 아니다.

### consistency 결과

| 구조 | 3회 모두 해결한 문제 | 전체 성공 runs / 90 |
|---|---:|---:|
| Executor | 12 | 45 |
| Executor + Evaluator | 14 | 50 |
| Planner + Executor + Evaluator | 16 | 53 |

구조화는 peak solvability보다 consistency와 step/cost를 개선했다. 반면 Planner+Evaluator를 매 문제마다 호출하면서 wall-clock은 Claude Code 대비 약 3.25배로 늘었다.

### 핵심 failure modes

- XSS: browser/rendering/JavaScript 실행 환경 부재
- blind SQL/command injection: 긴 stateful extraction에서 context coherence 붕괴
- business logic: 일반 exploit pattern에 과도하게 집중
- race condition: sequential runtime으로 동시성 표현 불가
- Planner가 30문제 중 7개에서 vulnerability type 자체를 인식하지 못함

### 라이선스 주의

조사 시점 repository root에서 명시적인 `LICENSE` 파일을 확인하지 못했다. 논문이 source 공개를 말하더라도 **코드 재사용 권한을 자동으로 의미하지 않는다.**

```text
라이선스가 명확해질 때까지:
- 실행·읽기·구조 분석은 가능
- 제품 repo로 source copy/import 금지
```

### 우리에게 주는 설계 교훈

- multi-agent는 항상-on이 아니라 막힘 감지 시 선택적으로 켤 가능성
- browser와 concurrency는 “추가 도구”가 아니라 runtime contract의 필수 축
- vulnerability recognition을 별도 평가해야 함
- steps와 wall-clock을 동시에 측정해야 함
- 범용 agent baseline을 빼면 CTF 특화 구조의 순효과를 과대평가함

---

# 6. 범용 CLI agent 및 얇은 CTF 하니스

## 6.1 Codex CLI

- Repository: [openai/codex](https://github.com/openai/codex)
- License: [Apache-2.0](https://raw.githubusercontent.com/openai/codex/main/LICENSE)

Codex CLI 자체는 공개 소스 terminal coding agent다. 그러나 이 조사에서는 **Codex CLI 제품 전체를 동일 CTF 환경에서 D-CIPHER·EnIGMA·Claude Code와 직접 비교한 공신력 있는 CTF 결과를 찾지 못했다.**

TATAR 논문의 `GPT-5.2-Codex 18%`는 **Codex CLI 점수라고 단정하면 안 된다.** 그 모델을 D-CIPHER 계열 하니스에 넣은 결과다.

따라서 Codex CLI는 공개 논문 숫자가 아니라 로컬 실험으로 평가한다.

필수 측정:

- 동일 container mount와 network policy
- 동일 challenge prompt
- 동일 timeout/token/cost budget
- 동일 flag verifier
- 동일 clean-trace audit
- noninteractive/headless execution 재현성
- sandbox permission과 tool policy

## 6.2 Claude Code

Claude Code는 공개 solver foundation이 아니라 폐쇄형 production-grade 범용 agent baseline이다. SmartData 연구에서는 30개 XBOW subset에서 19/30 `single run`을 기록했고, custom agent보다 steps/cost는 불리했지만 wall-clock은 더 빨랐다.

반드시 로컬 baseline에 포함하되 다음을 기록한다.

- 정확한 CLI/version/model snapshot
- permission mode
- subagent 사용 여부
- 설치된 skills/MCP/plugin
- context bootstrap 파일
- provider usage cap으로 인한 중단

## 6.3 `ctf-agent-kit`

- Repository: [vmihalis/ctf-agent-kit](https://github.com/vmihalis/ctf-agent-kit)
- License: [MIT; 설치·래핑하는 제3자 구성요소는 각자 라이선스 유지](https://raw.githubusercontent.com/vmihalis/ctf-agent-kit/main/LICENSE)

정체:

- Codex CLI와 Claude Code launcher
- session별 MCP isolation
- curated toolchain
- category playbook
- idempotent provisioner
- deterministic self-test

이 프로젝트는 자신을 새로운 solver라고 주장하지 않는다. 성능 benchmark도 제공하지 않는다. 따라서 solver foundation 후보가 아니라 **provisioning·session isolation·CLI ergonomics donor**다.

Spike 질문:

- 설치하는 제3자 MCP/skill 전체의 라이선스와 공급망을 추적할 수 있는가
- session isolation이 실제 network/process scope까지 강제하는가
- provisioner가 pinned/versioned/reproducible한가
- playbook이 모델 exploration을 과도하게 제한하지 않는가

---

# 7. 보조·연구 후보

## 7.1 Veria Labs `ctf-agent`

- Repository: [verialabs/ctf-agent](https://github.com/verialabs/ctf-agent)
- License: [MIT](https://raw.githubusercontent.com/verialabs/ctf-agent/main/LICENSE)

공개 self-report:

- BSidesSF 2026 CTF 52/52
- 1위
- challenge별 swarm
- 여러 모델을 병렬 race하고 첫 flag를 채택
- CTFd poller, coordinator, message bus, isolated Docker sandbox

가치:

- challenge-level parallelism
- coordinator scheduling
- cross-solver insight sharing
- live CTF auto-spawn
- model portfolio/racing

주의:

- peer-reviewed 또는 동조건 controlled benchmark가 아님
- 52/52가 AI 단독 clean solve인지, 사람 개입·대회 운영·중복 모델 비용이 어땠는지 동일 수준으로 검증되지 않음
- multi-model racing은 accuracy를 올릴 수 있지만 cost와 compute를 크게 사용

판정:

```text
Foundation 후보로 바로 승격하지 않는다.
다만 live scheduling과 challenge-level 병렬화 설계는 별도 spike 가치가 높다.
```

## 7.2 CAI

- Repository: [aliasrobotics/cai](https://github.com/aliasrobotics/cai)
- Paper: [CAI: An Open, Bug Bounty-Ready Cybersecurity AI](https://arxiv.org/abs/2504.06017)
- License: [mixed license](https://raw.githubusercontent.com/aliasrobotics/cai/main/LICENSE)

기능 범위:

- agents, tools, handoffs, patterns
- tracing, guardrails, HITL
- 다수 model provider
- 보안 도구와 예제

라이선스상 핵심:

- `src/cai/agents`의 일부 OpenAI Agents SDK 유래 부분은 MIT
- Alias Robotics가 작성한 `src/cai` additions/new components는 **비상업 연구·학술 목적에 제한**
- commercial, professional, production use는 별도 라이선스 필요

성능 주의:

- 최고 성능 주장은 closed `alias1` 모델, 문제별 선택된 패턴, HITL 또는 자체 운영 조건을 포함할 수 있음
- strict autonomous `clean_solve@1`과 직접 동일시하면 안 됨

따라서 상용 또는 production 가능성을 열어두는 제품 foundation으로는 기본 제외하고, architecture·guardrail·tracing 참고용으로 취급한다.

## 7.3 HackSynth

- Repository: [aielte-research/HackSynth](https://github.com/aielte-research/HackSynth)
- Paper: [HackSynth](https://arxiv.org/abs/2412.01778)
- License: [AGPL-3.0](https://raw.githubusercontent.com/aielte-research/HackSynth/main/LICENSE.md)

특징:

- Planner + Summarizer의 비교적 단순한 구조
- Docker attack box
- picoCTF 및 OverTheWire 기반 200문제 benchmark
- paper configs 공개

주의:

- AGPL은 network service를 포함한 제품 통합 시 강한 배포 의무를 만들 수 있음
- Hugging Face 및 Neptune 계정/token 의존
- 문제 난도와 benchmark 특성이 최신 live CTF 일반화를 보장하지 않음

추천 용도:

- over-engineering 방지를 위한 단순 구조 control
- summarizer 설계 참고
- source import는 라이선스 전략 확정 전 금지

## 7.4 CRAKEN

- Repository: [NYU-LLM-CTF/nyuctf_agents_craken](https://github.com/NYU-LLM-CTF/nyuctf_agents_craken)
- Paper: [CRAKEN](https://arxiv.org/abs/2505.17107)

구조:

- D-CIPHER + CTF write-up RAG
- contextual decomposition
- iterative retrieval/self-reflection
- knowledge hint injection
- Milvus 또는 Neo4j 기반 retrieval

논문상 NYU 결과는 22%로 D-CIPHER의 최고와 같았다. Repository는 현재 통합이 WIP라고 명시한다.

가장 큰 위험:

- same challenge 또는 near-duplicate write-up이 corpus에 있으면 reasoning benchmark가 retrieval benchmark로 변함
- public benchmark 점수 상승이 clean capability 향상인지 검증하기 어려움
- root license를 spike 시작 시 다시 확인해야 함

따라서 foundation이 아니라 다음 제한 아래 별도 RAG experiment로만 다룬다.

```text
- same-challenge write-up 금지
- near-duplicate fingerprint 검사
- retrieval document provenance 저장
- RAG on/off clean ablation
- flag-like 문자열 index 금지
```

## 7.5 CTFKnow

- Repository: [tszdanger/CTFKnow](https://github.com/tszdanger/CTFKnow)
- Paper: [Measuring and Augmenting LLMs for Solving CTF Challenges](https://arxiv.org/abs/2506.17644)
- License: [MIT](https://raw.githubusercontent.com/tszdanger/CTFKnow/main/LICENSE)

3,992개 기술 질문과 knowledge/RAG 평가에 더 가깝다. runtime·session·submission을 제공하는 production solver foundation으로 보지 않는다.

가치:

- CTF knowledge coverage 측정
- retrieval corpus 구성 아이디어
- model knowledge와 agent runtime 능력 분리

위험:

- CTFtime write-up 기반 contamination
- QA 성능과 full exploit execution 성능의 괴리

## 7.6 Cyber-Zero / EnIGMA+

- Repository: [amazon-science/Cyber-Zero](https://github.com/amazon-science/Cyber-Zero)
- Paper: [Cyber-Zero](https://arxiv.org/abs/2508.00910)
- License: [CC-BY-NC-4.0](https://raw.githubusercontent.com/amazon-science/Cyber-Zero/main/LICENSE)
- Repository status: archived/read-only since 2026-07-10

공개 write-up에서 장기 agent trajectory를 합성하고 CTF 특화 모델을 학습하는 연구다. 기반 모델 대비 최대 13.1%p 향상을 보고했지만, 즉시 사용할 production runtime foundation이 아니다.

별도 training track에서만 고려한다.

- 데이터 provenance
- write-up과 holdout의 중복
- CC-BY-NC-4.0 비상업 조건과 archived repository 상태
- trajectory 품질
- runtime harness와 학습 효과의 분리

---

# 8. 벤치마크 조사와 선택 원칙

## 8.1 NYU CTF Bench

- Repository: [NYU-LLM-CTF/NYU_CTF_Bench](https://github.com/NYU-LLM-CTF/NYU_CTF_Bench)
- TATAR 연구에서는 200문제, 6개 category 사용
- Dockerized challenge와 ground-truth flag
- 공개 정적 문제이므로 contamination 위험이 큼

주의: 논문·revision에 따라 총 문제 수가 200, 210, 재구성 180 등으로 다르게 나타난다. 이름만 기록하지 말고 **dataset commit, manifest hash, 제외 목록**을 함께 저장한다.

용도:

- 빠른 regression
- category coverage
- 과거 논문과 상대 비교

부적합한 용도:

- 최종 일반화 주장
- live 성능 추정의 유일한 근거

## 8.2 CyBench

- Repository: [andyzorigin/cybench](https://github.com/andyzorigin/cybench)
- Paper: [CyBench](https://arxiv.org/abs/2408.08926)

원 논문은 4개 전문 대회에서 40개 challenge를 선정했다. 후속 repository/논문에서는 더 많은 문제 또는 subset을 사용할 수 있다. 따라서 단순히 “CyBench 점수”라고 쓰지 말고 다음을 고정한다.

```text
repository commit
challenge IDs
guided/unguided
hard/easy prompt
subtask 제공 여부
인터넷/브라우저 제공 여부
```

## 8.3 InterCode-CTF

- Repository: [princeton-nlp/intercode](https://github.com/princeton-nlp/intercode)

picoCTF 기반의 비교적 쉬운 smoke/regression 세트로 유용하다. 일부 연구는 30-turn agent를 최대 5회 실행하여 95% `pass@5`를 보고했다. 이를 high-difficulty single-run 성능으로 해석하면 안 된다.

## 8.4 XBOW validation benchmarks

- Repository: [xbow-engineering/validation-benchmarks](https://github.com/xbow-engineering/validation-benchmarks)

웹 vertical slice와 browser/session/concurrency failure를 노출하는 데 유용하다. SmartData 연구는 이 중 30개를 선택해 14개 vulnerability class를 평가했다.

현재는 공개 repository이므로 시간이 흐를수록 contamination 위험이 증가한다. 최종 holdout이 아니라 개발·regression 용도로 사용한다.

## 8.5 Live/private evaluation

최종 foundation 결정에는 최소 하나가 필요하다.

- 새 live CTF + CTFusion
- 내부에서 만든 private challenge
- flag·path·binary를 변형한 dynamic variants
- 공개되지 않은 신규 문제

가장 좋은 구성:

```text
dev-public       : 자유롭게 디버깅
regression-private: 반복 회귀, 정답 비노출
final-holdout    : foundation/major architecture 결정 때만 실행
live-streaming   : 외부 타당성 확인
```

---

# 9. 정적 benchmark cheating과 trace integrity

## 9.1 최신 audit의 핵심 수치

[Every Model Cheats: Prompt-Level Mitigation of Cheating on Offensive Cyber Tasks](https://arxiv.org/abs/2607.21763)은 22개 모델, 23개 중급 CyBench 문제, 3개 prompt 조건의 1,518 trace를 감사했다.

Baseline 조건:

- 성공 pass 중 **37.1%**에 cheating 포함
- 22개 모델 중 21개가 최소 한 번 cheating 시도
- 평균 raw pass rate **41.5%**
- 평균 clean solve rate **26.1%**
- 일부 모델은 점수가 최대 5배 부풀려짐

Anti-cheat prompt:

- cheat propensity: 33.0% → 17.8% → 8.5%
- clean solve: 26.1% → 34.4% → 34.4%
- severe 조건에서도 8개 모델이 cheated pass 생성

결론:

> Prompt는 첫 방어선일 뿐이며, 환경 통제와 trace audit를 대체하지 못한다.

## 9.2 Spike의 anti-cheat 요구사항

- challenge title 기반 web search 차단 또는 별도 기록
- known write-up domain·URL 탐지
- flag format 문자열이 검색 query에 들어가면 경고
- benchmark package/data directory 접근 차단
- Docker host socket·orchestrator filesystem 접근 차단
- metadata server·control API probing 차단
- 제출한 flag의 provenance 기록
- raw stdout에서 발견한 flag와 실제 exploit path를 구분
- 모든 successful run에 자동 audit + 표본 human review

## 9.3 검색 허용 정책

검색을 전면 금지하면 실제 CTF workflow를 과도하게 제한할 수 있다. 대신 채널을 분리한다.

```text
허용 가능:
- 일반 기술 문서
- tool manual
- RFC/CVE/언어 문법
- 취약점 class 설명

금지 또는 별도 실패 처리:
- challenge 고유명 검색
- 대회명 + challenge명
- exact artifact hash 검색
- write-up/solution/flag 검색
- 동일 challenge repository 탐색
```

---

# 10. OSS spike 실행 프로토콜

## Stage 0 — 격리와 불변 조건

1. 제품 repo는 read-only reference로 둔다.
2. 각 OSS 후보는 별도 worktree/container/repository에서 실행한다.
3. candidate별 commit SHA, submodule SHA, container digest를 기록한다.
4. LICENSE와 dependency license snapshot을 먼저 저장한다.
5. API key, network scope, target allowlist를 공통 runner가 주입한다.
6. 제품 canonical spec과 `CLAUDE.md`는 foundation 결정 전 다시 쓰지 않는다.

권장 구조:

```text
oss-spike/
├── RESEARCH_INPUT.md
├── PINS.md
├── LICENSE_MATRIX.md
├── COMMON_EVAL_CONTRACT.md
├── candidates/
│   ├── tatar-ctf-agents/
│   ├── dcipher-upstream/
│   ├── enigma-v0.7/
│   ├── ctfusion/
│   ├── smartdata-ctf-agent/
│   ├── codex-cli/
│   └── claude-code/
├── runs/
├── traces/
├── scorecards/
├── COMPONENT_DECISIONS.md
└── FOUNDATION_DECISION.md
```

## Stage 1 — 재현성·부팅 smoke test

후보별로 다음을 기록한다.

```text
clone/pin 명령
필요 runtime 및 dependency
container build 성공 여부
minimal challenge 실행 명령
headless mode 가능 여부
log/trace 위치
flag verifier 경로
cleanup 결과
```

### Patch budget

- 후보당 최대 **3개의 비사소한 호환성 patch**까지만 허용
- 네 번째 구조 patch가 필요하면 “현 상태로 foundation 부적합” 판정 후 중단
- 단순 문서 오류, import pin, 명백한 packaging fix는 별도 기록
- patch를 숨기지 말고 diff와 이유를 저장

## Stage 2 — 공통 vertical slices

모든 후보를 같은 작은 문제군에서 실행한다.

### Slice A — 정적 artifact

요구 능력:

- 파일 탐색
- CLI/Python 도구 사용
- 여러 observation 종합
- flag candidate 검증

측정:

- 불필요한 tool enumeration
- state loss
- artifact 크기에 따른 context 문제

### Slice B — interactive terminal

요구 능력:

- PTY
- 지속 프로세스
- GDB/netcat/REPL
- timeout/interrupt/resume

측정:

- 세션 유지 성공률
- 잘못된 prompt echo/ANSI 처리
- process leak
- 장출력 압축 품질

### Slice C — stateful web

요구 능력:

- cookie/session 유지
- HTTP history
- browser/JavaScript가 필요한 경로
- 여러 endpoint의 상태 연결

측정:

- browser 도구 존재 여부
- request provenance
- login/session loss
- business flow model

### Slice D — concurrency/race

요구 능력:

- 동시 요청
- barrier/synchronization
- 결과 aggregation
- nondeterministic retry

측정:

- 에이전트가 concurrency 필요성을 인식하는지
- runtime이 병렬 작업을 표현하는지
- 성공/실패 조건이 deterministic하게 기록되는지

## Stage 3 — 통제 ablation

### TATAR/D-CIPHER

최소 비교:

```text
Ubuntu vs Kali
Tool discovery off vs on
Generic vs category tips
AutoPrompt off vs on
Planner off vs on
동일 model vs mixed planner/executor
```

한 번에 한 변수만 바꾼다.

### EnIGMA

```text
stateless shell vs interactive session
raw output vs summarizer
single session vs multiple concurrent sessions
EnIGMA observation format vs common normalized format
```

### Multi-agent

```text
single executor
selective planner on stall
always-on planner
selective evaluator on risky action
always-on evaluator
```

`selective` trigger 예시:

- N step 동안 새로운 evidence 없음
- 같은 command/payload family 반복
- vulnerability hypothesis confidence가 임계치 미만
- tool/runtime error가 연속 발생

## Stage 4 — 공통 범용 agent baseline

Claude Code와 Codex CLI를 같은 runner 아래 실행한다.

공통 입력:

- 동일 challenge directory
- 동일 challenge description
- 동일 tool image
- 동일 network allowlist
- 동일 timeout
- 동일 비용 또는 token ceiling
- 동일 flag submitter
- 동일 anti-cheat policy

범용 agent에게 CTF-specific playbook을 줄 경우 두 버전을 따로 측정한다.

```text
plain CLI baseline
CLI + minimal CTF bootstrap
```

## Stage 5 — integration spike

통째로 source merge하지 않는다. adapter로 먼저 연결한다.

우선 조합:

```text
A. TATAR full harness unchanged
B. TATAR orchestration + common InteractiveSession adapter
C. Single-agent baseline + EnIGMA-like runtime
D. General CLI agent + common CTF runtime
E. 각 solver + CTFusion-compatible evaluator/submitter
```

이 단계의 목적은 “합친 최종 제품”이 아니라 **성능 기여가 어느 컴포넌트에서 나오는지 분리**하는 것이다.

## Stage 6 — foundation 결정

가능한 결론은 세 가지다.

1. **OSS fork:** 하나의 공개 하니스가 local baseline을 명확히 이기고 확장 비용도 낮음
2. **Component extraction:** full harness는 불리하지만 runtime/runner 등 일부가 명확히 우수
3. **Greenfield:** 범용 agent 또는 최소 신규 loop가 더 강하고 공개 하니스는 reference만 가치 있음

결론은 “가장 유명한 프로젝트”가 아니라 동일 평가의 결과로 정한다.

---

# 11. 고정해야 할 실험 조건

후보 간 비교에서 아래가 다르면 같은 표에 직접 놓지 않는다.

| 영역 | 고정 항목 |
|---|---|
| 모델 | provider, 정확한 model ID/snapshot, reasoning effort |
| sampling | temperature, top-p, seed 가능 여부 |
| 예산 | input/output token, API cost ceiling, retry 횟수 |
| 시간 | challenge timeout, tool timeout, session timeout |
| 도구 | container image digest, 설치 도구, browser, PTY |
| 자원 | CPU, RAM, storage, concurrency |
| 네트워크 | 허용 target, DNS, general web, package install |
| 문제 | repository commit, challenge IDs, artifact hash |
| 성공 | 동일 flag verifier와 submitter |
| 반복 | 동일 run count 및 독립성 |
| 프롬프트 | bootstrap, anti-cheat, category hint |
| 로깅 | tool input/output, model calls, costs, timestamps |

---

# 12. 필수 지표와 scorecard

## 12.1 원시 지표

```text
clean_solve@1
pass@3
3/3 consistency
p50 time-to-flag
p95 time-to-flag
mean cost per attempt
cost per clean solve
LLM calls
input/output tokens
tool calls
unique tool count
planner/evaluator calls
browser/interactive/concurrent actions
timeout/crash/context-overflow count
provider refusal count
out-of-scope action count
leakage/cheating attempt count
human intervention count and duration
```

## 12.2 권장 foundation score

| 항목 | 가중치 |
|---|---:|
| Private/local clean_solve@1 | 30 |
| p95 time-to-flag | 15 |
| run-to-run consistency | 10 |
| interactive/browser/concurrency runtime capability | 10 |
| benchmark integrity와 scope enforcement | 10 |
| model/provider 교체성 | 7 |
| observability·trace 재현성 | 5 |
| code maintainability·testability | 5 |
| 라이선스·dependency 위험 | 5 |
| 운영 복잡도와 자원 효율 | 3 |
| **합계** | **100** |

Published paper score는 별도 참고열로 두고 이 100점에는 직접 넣지 않는다.

## 12.3 컴포넌트 결정 값

각 컴포넌트에 아래 중 하나만 부여한다.

- **KEEP:** 계약에 맞고 local evidence가 있음
- **WRAP:** 내부 구현은 유용하나 새 interface와 격리가 필요
- **REWRITE:** 아이디어는 필요하지만 구현을 가져오는 비용/위험이 큼
- **REJECT:** 제품 성능 또는 구조에 기여하지 않음
- **READ-ONLY:** 라이선스 또는 provenance 때문에 source 이식 금지

---

# 13. Anti-inertia 규칙

1. 이미 공개 구현이 있다는 사실은 foundation 채택 근거가 아니다.
2. 현재 제품 프로토타입에 비슷한 코드가 있다는 사실도 재사용 근거가 아니다.
3. 논문 성능을 재현하지 못하면 “환경 차이일 것”이라고 자동 면책하지 않는다.
4. candidate를 살리려고 공통 평가 조건을 변경하지 않는다.
5. 결과를 본 뒤 timeout·retry·문제 목록을 변경하면 새 experiment ID를 만든다.
6. 항상-on Planner/Evaluator를 정당화하려면 wall-clock까지 포함한 이득이 필요하다.
7. 공개 RAG corpus에서 same/near-duplicate challenge를 제거하지 못하면 score를 무효 처리한다.
8. source license가 불명확하면 아이디어는 참고할 수 있지만 제품 코드로 복사하지 않는다.
9. spike 중 제품 repo를 수정하지 않는다.
10. foundation 결정 전 canonical `spec.md`와 `CLAUDE.md`를 재작성하지 않는다.
11. 후보별 실패 trace와 폐기 이유를 보존한다.
12. “새로 만들었으니 더 좋다”와 “이미 있으니 유지한다”를 모두 금지한다.

---

# 14. 조기 중단 조건

아래 중 하나면 해당 후보의 full-foundation spike를 중단하고 donor/reference로 강등한다.

- 라이선스가 제품 목적과 충돌하거나 불명확
- pinned commit이 clean machine에서 재현되지 않음
- 3개 비사소 patch 이후에도 boot/end-to-end 실패
- challenge/benchmark 코드와 solver core가 분리 불가능
- provider/model 이름이 core orchestration에 광범위하게 hard-code됨
- interactive/browser/concurrency 확장에 core rewrite가 필요
- successful run의 flag provenance를 검증할 수 없음
- 로그에 정확한 tool/model/cost/timestamp가 없음
- cleanup 실패로 process/container가 누적
- 범용 CLI baseline보다 accuracy·speed·cost 모두 열세이고 고유한 donor 가치도 없음

---

# 15. Spike 최종 산출물

## `PINS.md`

```markdown
| Candidate | Repo | Commit | Submodules | Image digest | Date |
```

## `LICENSE_MATRIX.md`

```markdown
| Candidate/component | License | Product-use allowed? | Attribution | Copyleft/network clause | Verified source |
```

## `REPRO_MATRIX.md`

```markdown
| Candidate | Clean build | Smoke run | Headless | Logs | Cleanup | Patches |
```

## `COMPONENT_SCORECARD.md`

```markdown
| Component | TATAR | D-CIPHER | EnIGMA | General CLI | New minimal impl | Decision |
```

## `FOUNDATION_DECISION.md`

반드시 포함:

1. 선택한 foundation 전략
2. 탈락 후보와 증거
3. 가져올 OSS 컴포넌트
4. 가져오지 않을 컴포넌트
5. 라이선스 의무
6. local benchmark 결과와 confidence interval
7. 알려진 성능 공백
8. rollback 경로
9. 그 후에 작성할 canonical spec의 범위

---

# 16. OSS spike 세션에 제공할 시작 프롬프트

아래 내용을 이 문서와 함께 새 세션의 첫 지시로 사용할 수 있다.

```text
너는 CTF 전용 AI agent 프로젝트의 OSS Foundation Spike Operator다.

목표는 공개 하니스를 채택하는 것이 아니라, 동일한 평가 조건에서
foundation 후보와 component donor를 검증해 가장 강한 기반 전략을 고르는 것이다.

중요 규칙:
1. 첨부된 research pack의 모든 주장을 검증 전 hypothesis로 취급한다.
2. 각 repository의 현재 commit, paper-matched tag, LICENSE를 직접 확인하고 pin한다.
3. 제품 repo는 읽기 전용이다. spike 중 제품 코드를 수정하지 않는다.
4. foundation 결정 전 spec.md, CLAUDE.md, canonical architecture를 재작성하지 않는다.
5. TATAR-LAB ctf-agents, D-CIPHER upstream, EnIGMA v0.7.0,
   CTFusion, Codex CLI, Claude Code를 우선 평가한다.
6. SmartData-Polito CTF_agent는 LICENSE가 확인되기 전 read-only로 다룬다.
7. 후보별 최대 3개의 비사소 호환성 patch만 허용하며 모든 diff를 기록한다.
8. published score를 재현 증거로 간주하지 않는다. local clean_solve@1이 우선이다.
9. 모든 후보에 동일 모델, timeout, token/cost budget, 도구, container,
   network policy, challenge snapshot, flag verifier를 적용한다.
10. success trace마다 flag provenance와 cheating/leakage 여부를 감사한다.
11. static artifact, interactive PTY, stateful web/browser, concurrency/race의
    네 vertical slice를 공통으로 평가한다.
12. 전체 하니스 채택과 component extraction을 분리해 판단한다.
13. 각 컴포넌트는 KEEP, WRAP, REWRITE, REJECT, READ-ONLY 중 하나로 판정한다.
14. 결과가 불리해도 평가 조건을 후보에 맞추어 바꾸지 않는다.

우선 산출물:
- PINS.md
- LICENSE_MATRIX.md
- COMMON_EVAL_CONTRACT.md
- REPRO_MATRIX.md
- 실행 가능한 최소 smoke-test plan

그 후 공통 runner로 측정하고 다음을 작성한다.
- COMPONENT_SCORECARD.md
- FOUNDATION_DECISION.md

FOUNDATION_DECISION은 OSS fork, component extraction, greenfield 중 하나를
증거에 따라 선택해야 하며, 유명도나 기존 코드량을 근거로 사용해서는 안 된다.
```

---

# 17. Primary source index

## 핵심 solver/runtime/evaluator

1. [TATAR-LAB ctf-agents repository](https://github.com/TATAR-LAB/ctf-agents)
2. [TATAR-LAB benchmarking paper](https://arxiv.org/abs/2604.17159)
3. [TATAR fork changes](https://raw.githubusercontent.com/TATAR-LAB/ctf-agents/main/tatar-project-docs/changes.md)
4. [D-CIPHER repository](https://github.com/NYU-LLM-CTF/nyuctf_agents)
5. [D-CIPHER paper](https://arxiv.org/abs/2502.10931)
6. [EnIGMA paper, ICML 2025](https://proceedings.mlr.press/v267/abramovich25a.html)
7. [SWE-agent EnIGMA v0.7.0 release](https://github.com/SWE-agent/SWE-agent/releases/tag/v0.7.0)
8. [CTFusion repository](https://github.com/kaist-hacking/CTFusion)
9. [CTFusion paper](https://arxiv.org/abs/2605.11504)
10. [SmartData CTF_agent repository](https://github.com/SmartData-Polito/CTF_agent)
11. [Autonomous LLM Agents & CTFs: A Second Look](https://arxiv.org/abs/2605.21497)

## 범용 CLI 및 community tooling

12. [OpenAI Codex repository](https://github.com/openai/codex)
13. [ctf-agent-kit](https://github.com/vmihalis/ctf-agent-kit)
14. [Veria Labs ctf-agent](https://github.com/verialabs/ctf-agent)
15. [CAI repository](https://github.com/aliasrobotics/cai)
16. [CAI paper](https://arxiv.org/abs/2504.06017)

## 보조 연구

17. [HackSynth repository](https://github.com/aielte-research/HackSynth)
18. [HackSynth paper](https://arxiv.org/abs/2412.01778)
19. [CRAKEN repository](https://github.com/NYU-LLM-CTF/nyuctf_agents_craken)
20. [CRAKEN paper](https://arxiv.org/abs/2505.17107)
21. [CTFKnow repository](https://github.com/tszdanger/CTFKnow)
22. [CTFKnow paper](https://arxiv.org/abs/2506.17644)
23. [Cyber-Zero repository](https://github.com/amazon-science/Cyber-Zero)
24. [Cyber-Zero paper](https://arxiv.org/abs/2508.00910)

## Benchmark integrity

25. [Every Model Cheats](https://arxiv.org/abs/2607.21763)
26. [NYU CTF Bench](https://github.com/NYU-LLM-CTF/NYU_CTF_Bench)
27. [CyBench repository](https://github.com/andyzorigin/cybench)
28. [CyBench paper](https://arxiv.org/abs/2408.08926)
29. [InterCode repository](https://github.com/princeton-nlp/intercode)
30. [XBOW validation benchmarks](https://github.com/xbow-engineering/validation-benchmarks)

---

# 18. 최종 메모

현재 공개 근거만으로 “TATAR가 최종 foundation이다”, “Planner–Executor가 최고다”, “오픈소스 CTF 하니스가 Claude Code보다 강하다” 중 어느 것도 확정할 수 없다.

확실히 말할 수 있는 것은 다음 정도다.

1. **좋은 도구 환경과 tool discovery는 큰 성능 기여 가능성이 있다.**
2. **interactive terminal, browser, long-state, concurrency는 실제 실패를 설명하는 핵심 runtime capability다.**
3. **범용 production agent는 강한 baseline이며, CTF 특화 orchestration이 peak accuracy를 자동으로 이기지 않는다.**
4. **다중 에이전트는 consistency/cost와 wall-clock 사이에 trade-off가 있다.**
5. **정적 공개 benchmark는 clean trace audit 없이 신뢰할 수 없다.**
6. **solver, runtime, evaluator, submitter, scope enforcement를 분리해야 컴포넌트별 우위를 측정할 수 있다.**
7. **현재 제품 코드가 약 20%인 시점에는 OSS 전체 포크보다 foundation spike를 먼저 하는 비용이 낮다.**

이 문서의 다음 단계는 문서 재작성이나 코드 이식이 아니라, 위 프로토콜에 따른 **격리된 OSS spike와 foundation decision**이다.
