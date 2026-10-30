# PINS

스파이크 세션 A (Stage 0), 2026-08-07. 산출물 양식은 [pack §15].

**모든 값은 이 세션이 원문에서 직접 관측한 것이다.** research pack의 진술을 옮긴 것이 아니다
(`FOUNDATION_DECISION.md` §1). 관측 시각은 호스트 UTC이고, 관측 경로는 `git ls-remote` 또는
GitHub API이며, 어느 쪽인지 각 행에 적었다.

관측 호스트: `203.0.113.10`, 계정 `ctf-spike-user`. 명령 로그: `<HOME>/logs/`.

---

## 1. arm

| Candidate | Repo | Commit | Submodules | Image digest | Date (UTC) |
|---|---|---|---|---|---|
| **T** TATAR-LAB `ctf-agents` | `https://github.com/TATAR-LAB/ctf-agents` | `e52e38ea30fb162446342ed456a969f9c71fa815` | **없음** (`.gitmodules` 부재, gitlink 0개) | `ctfenv:multiagent` = `sha256:7ffb5ff2edbf3406a02c921b95065be5face2f4127ededd5715140dfd2483584` | 2026-08-07T10:30Z |
| **E** EnIGMA / SWE-agent `v0.7.0` | `https://github.com/SWE-agent/SWE-agent` | `dc18a740faabd2fc625a9b018184dfc4a81cbc78` | **없음** | `sweagent/enigma:spike` — 세션 A 종료 시점 빌드 미완, §4 참조 | 2026-08-07T10:30Z |
| **X** Codex CLI | `https://github.com/openai/codex` | `be6e8eac029b183056b7e4402879f15d2c85f61b` | n/a (릴리스 바이너리) | n/a (컨테이너 아님) | 2026-08-07T11:05Z |
| **CTFusion** (읽기 전용 참조) | `https://github.com/kaist-hacking/CTFusion` | `167982004c2eff9975872654ed9e883c7c8f9d52` | 미확인 (clone하지 않음) | n/a | 2026-08-07T10:30Z |

### 1.1 각 행의 근거

**T.** `git ls-remote https://github.com/TATAR-LAB/ctf-agents HEAD refs/heads/main` → `HEAD`와
`refs/heads/main`이 같은 SHA. `.gitmodules` 없음, `git ls-tree -r HEAD`에 `commit` 타입 항목 0개.
저장소 8.5M. 최신 커밋 `e52e38e 2026-03-30 hakanotal "Minor updates"`.

**E.** `git ls-remote --tags`로 `refs/tags/v0.7.0` → `dc18a740…`. clone 후 detached checkout하고
`git tag --points-at HEAD` → `v0.7.0`으로 재확인. **pack이 적은 `dc18a74`와 일치한다.** 경량 태그다
(`^{}` peeled 참조가 없다). 참고로 같은 저장소의 현재 `main`은 `3ea751c087f32b16e039a2233dd6eefecef325d5`
이며, README가 EnIGMA 재현에는 0.7을 쓰라고 하므로 [pack §5.3] `main`은 pin 대상이 아니다.

**X.** 이 후보만 커밋이 아니라 **릴리스**로 pin한다. 우리가 실행하는 것이 소스가 아니라 사전 빌드
바이너리이기 때문이다.

```
release tag : rust-v0.147.0   (published 2026-08-07T01:41:49Z)
tag object  : 3ed6f04f6bf8b7c46299d1cb1ff99c74ce21a51d
commit      : be6e8eac029b183056b7e4402879f15d2c85f61b     ← 위 표의 Commit
asset       : codex-x86_64-unknown-linux-musl.tar.gz  (98,970,270 bytes)
asset sha256: 0246e2e773834e07f0fb5249ed6ebad12e4591e608f8c7bb97dd6a9690544c36
binary      : codex-cli 0.147.0  (`--version` 출력)
```

`main`의 HEAD는 관측 시점에 `85e0661c3baacc62db7b006d2b8085b006d0795e`였다. 세션 지시는 HEAD를
요구했으므로 기록하되, **재현 대상은 HEAD가 아니라 위 릴리스**다. HEAD는 매일 움직이고 우리는 그것을
빌드하지 않는다.

**CTFusion.** `git ls-remote … HEAD`만 수행. `FOUNDATION_DECISION.md` §9.1이 읽기 전용 참조로
규정했으므로 clone도 boot도 하지 않았다. submodule 유무는 clone하지 않아 확인하지 않았고, 확인할
필요가 생기는 시점은 S8 설계를 실제로 참조할 때다.

---

## 2. 참조용 pin — arm이 아님

| 대상 | Repo | Commit | 왜 기록하는가 |
|---|---|---|---|
| D-CIPHER upstream | `NYU-LLM-CTF/nyuctf_agents` | `612190f298ae9e604f00370019beed4ba1f372f6` (main, 2026-07-17 push) | §9.1의 제외 근거를 검증하려면 upstream을 실제로 fetch해야 했다 |
| T의 fork base | 같은 저장소 | `6bb4d2b437c09457adb7dba6f15074f57af83a1f` (2025-10-26) | T와 upstream의 merge-base. §3의 삭제 판정이 이 지점 기준이다 |

**upstream 저장소의 정체를 확정했다.** TATAR의 `tatar-project-docs/changes.md`는 fork 부모를
`NYU-LLM-CTF/ctf-agents`로 적지만 **그 경로는 존재하지 않는다**(GitHub API 404). GitHub 메타데이터가
답을 준다: `TATAR-LAB/ctf-agents`는 `fork=true`이고 `parent = source = NYU-LLM-CTF/nyuctf_agents`다.
즉 pack §5.2가 D-CIPHER upstream이라 부른 바로 그 저장소가 맞고, changes.md의 링크는 죽은 포인터다
(pack §5.1 caveat 5가 지적한 "문서 미정리"와 같은 종류).

---

## 3. §9.1의 D-CIPHER 제외 근거 — 검증 결과

`FOUNDATION_DECISION.md` §9.1은 D-CIPHER upstream을 arm에서 빼면서 "TATAR가 그 상위집합"이라는
근거를 달고, **Stage 0에서 `changes.md`를 읽어 fork가 upstream 기능을 제거하지 않았는지 확인하라**고
지시했다.

`changes.md`만 읽는 것으로는 답이 되지 않는다. 저자의 자기 보고이기 때문이다. 그래서 두 가지를 했다.

**(a) 자기 보고.** `changes.md` 61줄 전체에서 제거를 뜻하는 문장은 하나뿐이고, 그것은
"Removed the hardcoded `--platform linux/amd64` flag from Docker run to support ARM"이다. 이식성
수정이지 기능 제거가 아니다. 나머지는 전부 추가와 버그 픽스다.

**(b) 실제 diff.** upstream을 remote로 붙이고 merge-base 대비로 쟀다.

```
merge-base 6bb4d2b → TATAR e52e38e
  삭제된 파일: 0개              (git diff --diff-filter=D --name-only)
  변경 총계  : 115 files changed, 12960 insertions(+), 233 deletions(-)
  분기       : TATAR는 upstream/main보다 46 커밋 앞서고 3 커밋 뒤처진다
```

**결론: 제외 근거는 유지된다.** 파일 단위 제거가 없고, 능력을 담은 클래스가 전부 남아 있다.

**단, 정확히 이렇게 기록한다. 한 가지 실질적 회귀가 있다.**

upstream은 `OpenAIBackend.MODELS`에 OpenAI 모델 9종(gpt-4o 계열, gpt-4.1 등)을 하드코딩했고
`MODELS = {m: b for b in BACKENDS for m in b.MODELS}`로 조립했다. TATAR는 이를 `models.yaml` 구동으로
바꾸면서 **`backend: openai` 항목을 하나도 옮기지 않았다(9 → 0).** 관측된 분포는 openrouter 14 /
vertexai 8 / ollama 1이다.

- **능력은 남아 있다.** `OpenAIBackend` 클래스와 `BACKEND_CLASSES['openai']` 배선이 그대로다.
  seam 판정은 능력의 유무를 보므로 상위집합 관계는 이 축에서 깨지지 않는다.
- **그러나 우리에게는 실질적이다.** `SAFETY_SCOPE.md`가 허용하는 provider는 OpenAI 하나뿐인데,
  TATAR는 그 provider로 쓸 수 있는 모델이 shipped config에 0개인 상태로 온다. upstream에서는
  필요 없었을 설정 추가가 우리에게는 필수다(§REPRO_MATRIX의 `T-minor-01`).
- **부수 효과 하나가 더 중요하다.** TATAR가 공개한 실험 config(RQ1~RQ5)는 전부 openrouter/vertexai를
  쓴다. 즉 **`OpenAIBackend` 경로는 fork 자신의 실험에서 한 번도 돌지 않았다.** 그 경로의 결함
  가능성이 다른 경로보다 높다고 보아야 하고, 실제로 §REPRO_MATRIX가 그런 결함을 하나 발견했다.
- **"상위집합"은 merge-base 기준이다.** TATAR는 upstream/main보다 3 커밋 뒤처져 있다
  (`update dependencies`, `update gitignore`, `update backend and model list`). 마지막 것이 백엔드·모델
  목록 갱신이라 위 회귀와 같은 영역이다. 성능 단계에서 upstream을 통제군으로 쓴다면 이 3 커밋을
  통제 조건에 적어야 한다.

**이 세션이 하지 않은 것:** 233줄의 line-level 삭제가 어떤 능력에도 대응하지 않는다는 것을 한 줄씩
확인하지는 않았다. 파일 삭제 0개와 클래스 잔존으로 seam 수준의 판단은 충분하고, 그 이상은 Stage 0의
범위가 아니다.
