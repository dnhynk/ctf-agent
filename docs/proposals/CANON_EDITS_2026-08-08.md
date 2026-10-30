# CANON_EDITS — 2026-08-08, 서명 요청

문서 세션. `FOUNDATION_DECISION.md` §13.1.a-3이 **문서 세션에서 하라고 지정한 canon 편집
두 건**의 제안이다. 절차는 `HOST_EXCEPTIONS.md`를 다뤘던 방식 그대로다 —
**제안 → 운영자 승인 → 편집.** 서명 전에는 canon을 고치지 않는다.

**상태: 둘 다 승인됨 (2026-08-08, dnhynk). 적용 완료.**

| # | 대상 | 무엇을 | 상태 |
|---|---|---|---|
| 1 | `docs/canon/SAFETY_SCOPE.md` | escalation egress 예외 (비활성 상태로 추가) | **승인·적용** |
| 2 | `docs/canon/EVAL_CONTRACT.md` | `contest_solve` vs `clean_solve@1` 구분 명문화 | **승인·적용** |

---

## 0. 왜 지금인가, 그리고 왜 이 둘만인가

`FOUNDATION_DECISION.md` §13.1.a는 운영자 결정(2026-08-07)을 기록한다: **제품은 하나이고,
라이트업과 escalation은 별도 제품이 아니라 그 하나의 두 계층이며, 둘 다 seam이 아니라
S9(telemetry)의 소비자다.** 그 결정에서 canon 편집 두 건이 파생됐고, 같은 절이 그것을
**"지금이 아니라 문서 세션에서"** 하라고 못박았다.

**지금인 이유.** 두 편집 모두 **재빌드가 만들 telemetry의 형태를 결정한다.** escalation
export 경계는 S2에 요구를 걸고, 두 지표의 구분은 S7의 소스 집합을 가른다
(`TELEMETRY_SCHEMA.md` §5.3). 재빌드가 시작된 뒤에 정하면 이미 쌓인 기록이 소급해서
쓸모없어진다.

**이 둘만인 이유.** `OBJECTIVE.md`는 **고치지 않는다.** 그 문서는 "autonomously ...
produces a verified flag"로 자율 코어를 규정하고, escalation은 그 위에 얹히는 하류
능력이라 OBJECTIVE 하위에 놓인다. §13.1.a가 명시적으로 그렇게 적었다.

**서명이 거부되면.** 두 편집 없이도 재빌드는 진행할 수 있다. 대가는 각각 §1.4·§2.4에
적었다.

---

## 1. 편집 1 — `SAFETY_SCOPE.md`, escalation egress 예외

### 1.1 무엇이 문제인가

현재 canon:

- `Allowed network` 표: **Host egress = `api.openai.com` only.**
- `Permissions` 표: **`allow_external_ai` = true.**

이 둘이 이미 서로 정합하지 않는다. `allow_external_ai`가 참인데 그 AI에 닿을 egress가
없다. 스파이크 동안에는 문제가 되지 않았다 — 스파이크의 모델 축이 OpenAI 하나였고,
넓힌 egress는 기간 한정 예외였다.

escalation 계층은 **정의상** 챌린지 유래 콘텐츠를 다른 모델에 보낸다. 그 동작은 지금
canon 아래에서 **범위 밖**이고, 범위 밖인 채로 재빌드가 telemetry 경계를 설계하면 나중에
그 경계를 다시 그어야 한다.

### 1.2 제안하는 편집

`docs/canon/SAFETY_SCOPE.md`의 `## Allowed network` 절 끝, "Host egress is widened for the
OSS foundation spike until 2026-08-21; see the exception below." 바로 뒤에 다음 문단을
추가하고, 문서 끝의 `## Enforcement status` 앞에 아래 절을 신설한다.

**(a) `Allowed network` 절에 추가할 한 줄**

```markdown
A second, permanent exception exists for the escalation layer and is currently inert; see
"Escalation egress" below. It does not widen the worker's egress, which stays `none by default`.
```

**(b) 신설 절 — `## Flag submission` 뒤, `## Permissions` 앞**

```markdown
## Escalation egress

The product has one escalation layer: when the autonomous core stalls, a packet compiled from
its own telemetry is analysed by a model other than the one driving the attempt. That crossing
is an exception to "Host egress: `api.openai.com` only" and is defined here rather than left
to the layer that will implement it.

**Currently inert.** The escalation layer does not exist. Until it does, and until the
operator enables it for a named contest, no traffic is permitted under this section and the
`Allowed network` table applies unchanged.

When it is enabled, all six conditions hold simultaneously. Failing any one of them, the
export is refused and the refusal is recorded.

1. **One path.** Challenge-derived content leaves the host through a single export function.
   No other code path may reach an external model with challenge-derived bytes. An attempt to
   do so is a scope violation, not a bug.
2. **Compiled, not raw.** What crosses is a packet projected from the attempt's telemetry —
   observations, hypotheses, and their status. Raw challenge artifacts, binaries, captures and
   input files do not cross.
3. **Secret-scrubbed.** The export aborts rather than shipping a redaction sentinel. This is
   the existing rule under `Credentials`, applied to the export.
4. **Scope-checked.** The destination is an endpoint named in the enabled escalation
   configuration. There is no destination named by a model at call time and none resolved from
   a challenge description — the same rule the `Allowed targets` section applies to targets.
5. **Recorded.** Every export is recorded with its destination, the packet's content hash, the
   redaction result and the attempt it belongs to. An export that cannot be reconstructed from
   the record is treated as a run that left scope.
6. **Downstream of the core.** Escalation never runs inside the worker. It is a host-side
   projection of telemetry; the worker's egress is unchanged and stays `none by default`.

A run that used escalation is not a `clean solve@1`. See `EVAL_CONTRACT.md`.
```

### 1.3 무엇이 바뀌지 않는가

- **worker의 egress는 그대로다.** `none by default`, 그리고 `network=challenge`는 여전히
  매니페스트가 선언한 대상을 요구한다.
- **네 permission은 그대로다.** 이 편집은 `allow_external_ai`가 이미 참이라는 사실 위에
  경계를 그을 뿐, 어떤 permission도 켜지 않는다.
- **대회 유래 입력 반입 금지는 그대로다.** `allow_vps`는 false다.
- **자동 제출 금지는 그대로다.**
- 스파이크의 기간 한정 예외(만료 2026-08-21)와 무관하고 그것을 연장하지 않는다.

### 1.4 서명하지 않으면

escalation 계층은 canon 위반이 되므로 만들 수 없다. `contest_solve`는 측정 불가능해지고,
`FOUNDATION_DECISION.md` §13.1.a의 "제품은 하나이고 두 계층이다"라는 결정이 실질적으로
철회된다. **재빌드 자체는 막히지 않는다** — 자율 코어는 이 예외 없이 완성된다.

---

## 2. 편집 2 — `EVAL_CONTRACT.md`, 두 지표의 구분

### 2.1 무엇이 문제인가

현재 canon의 `Reporting unit`은 `solve@1` 하나만 정의하고, "no human intervention
mid-attempt"를 그 정의에 넣는다. escalation은 **사람 매개 + 멀티모델 + 재주입**이므로
현재 문면상 `solve@1`이 아니다 — 거기까지는 맞다. 문제는 그 다음이다: **escalation을 쓴
attempt가 무엇으로 보고되는지가 정의되어 있지 않다.** 정의가 없으면 두 숫자가 같은 표에
섞이고, `FOUNDATION_DECISION.md` §13.1.a가 막으려는 오염이 정확히 그것이다.

### 2.2 제안하는 편집

`docs/canon/EVAL_CONTRACT.md`의 `## Reporting unit` 절을 아래로 **대체**한다. 기존 문단은
첫 두 줄로 그대로 남고, 나머지가 추가다.

```markdown
## Reporting unit

`solve@1`: one attempt per challenge, no retry, no human intervention mid-attempt. Anything
else (`solve@k`, best-of-n, resumed attempts) is a different number and is labelled as such. It
does not substitute for `solve@1`.

Two figures are reported, always both, never merged.

**`clean_solve@1`** — the instrument. One attempt, no retry, no human intervention, one model,
no escalation, on a challenge the agent has never seen. This is the number that governs whether
the autonomous core is improving and the number `OBJECTIVE.md` ranks first. It is the only
uncontaminated measure of the agent itself, because a figure that mixes in a human or a second
model cannot be attributed to the agent. It is never dropped and never replaced.

**`contest_solve`** — the goal. The result including the escalation layer: operator-mediated
handoff, analysis by a second model, and reinjection of what came back. This is what a contest
actually scores.

The relationship is the one this contract already applies to `solve@k`: **the second figure
does not substitute for the first.** A run that used escalation is counted in `contest_solve`
and is **not** counted as a `clean_solve@1` success; it remains in the `clean_solve@1`
denominator as an attempt that the core did not solve alone.

Both figures are subject to everything above. In particular, a flag obtained from a write-up, a
solution repository, a search result or by searching for the flag string is a **failure under
both**. Escalation is analysis of the attempt's own record by another model; it is not
retrieval, and a packet that carries a retrieved solution is a retrieval regardless of which
model produced it.

An escalated run records which model was consulted and what crossed the boundary. See
`SAFETY_SCOPE.md`, "Escalation egress". A run whose escalation cannot be reconstructed from its
record is discarded, like any other run whose controls cannot be reconstructed.
```

### 2.3 무엇이 바뀌지 않는가

- **성공의 정의는 그대로다** — verifier를 통과한 flag.
- **실패의 정의는 그대로다** — write-up·검색으로 얻은 flag는 두 지표 **모두에서** 실패이고
  분모에 남는다. 이 편집은 그 규칙을 넓히지 않는다.
- **통제 조건 6개는 그대로다.**
- **holdout 규율은 그대로다.**
- `OBJECTIVE.md`의 우선순위 1번은 여전히 clean solve@1이다.

### 2.4 서명하지 않으면

escalation을 쓴 run을 어떻게 보고할지가 정의되지 않은 채로 남는다. 실무적 결과는 둘 중
하나다: 그런 run을 아예 만들지 않거나(= 편집 1의 서명 여부와 무관하게 escalation 포기),
만들되 두 숫자가 섞인다(= `FOUNDATION_DECISION.md` §13.1.a가 막으려던 것). **재빌드
자체는 막히지 않는다.**

---

## 3. 서명

편집은 승인 뒤에 적용하고, 적용 사실을 아래 표와 대상 문서 양쪽에 남긴다.

| # | 승인자 | 날짜 | 적용 |
|---|---|---|---|
| 1 SAFETY_SCOPE escalation egress | dnhynk | 2026-08-08 | `SAFETY_SCOPE.md` — `Allowed network` 한 줄 + 신설 절 `## Escalation egress`. 제안 문면과 동일 |
| 2 EVAL_CONTRACT 두 지표 | dnhynk | 2026-08-08 | `EVAL_CONTRACT.md` — `## Reporting unit` 확장. 기존 세 줄은 그대로 두고 뒤에 추가. 제안 문면과 동일 |

**적용 시 문면에서 벗어난 것: 없다.** 두 편집 모두 §1.2·§2.2의 텍스트를 그대로 넣었고,
각 지점에 승인자·날짜·이 제안서로의 포인터를 한 줄 더했다.
