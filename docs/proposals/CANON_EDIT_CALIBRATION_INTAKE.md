# CANON_EDIT — 외부 유래 calibration set 반입, 서명 요청

작성 2026-08-08. 운영자 요청(4분야 × 4난이도 × 3문제 = 48, Dreamhack 유래)이
`SAFETY_SCOPE.md`가 이름으로 금지한 행위에 걸려 **멈추고 보고한** 결과다. 절차는
`CANON_EDITS_2026-08-08.md`와 `CANON_EDIT_REBUILD_EXCEPTION.md`가 밟은 것과 같다 —
**제안 → 운영자 서명 → 편집.** 서명 전에는 canon도 계약도 고치지 않고, 크롤링도 하지
않는다.

**상태: 일곱 항목 전부 승인·적용 (2026-08-08, dnhynk).** 만료 **2026-08-29**.

> **이 문서의 08-29는 이력이다. 현재 만료는 2026-09-30이다** —
> `CANON_EDIT_EXPIRY_EXTENSION.md`(E-1, 2026-08-08 서명). **본문을 고치지 않는 이유**는
> 그 제안 §6 말미와 같다: 이 문서는 그 시점에 무엇을 정했는지의 기록이고, 특히 §8.1-1의
> "만료일이 짧을 가능성이 높다"는 대가 진술이 뒤에서 지워지면 연장의 근거가 사라진다.
서명 시점에 미확정이던 값 셋의 처리는 §8.1이다 — 약관 확인은 2026-08-08에 해소됐고,
**인스턴스 구조 관측(§8.1-3)은 여전히 미확인이다.**

| # | 대상 | 무엇을 | 층 | 상태 |
|---|---|---|---|---|
| C-1 | `docs/canon/SAFETY_SCOPE.md` | "Out of scope"의 contest-platform 줄을 좁힌다 | canon | **승인·적용** |
| C-2 | `docs/canon/SAFETY_SCOPE.md` | 기간 한정 예외 절 신설 (`allow_vps`는 켜지 않는다) | canon | **승인·적용** |
| C-3 | `docs/canon/EVAL_CONTRACT.md` | 셋째 지표 `calibration@k` 명문화 | canon | **승인·적용** |
| S-1 | `docs/spec/MANIFEST.md` §2.1 | `provenance`에 값 하나 추가 | 계약 | **승인·적용** |
| S-2 | `docs/spec/MANIFEST.md` §2.3 | 정답 검증 연기 허용 | 계약 | **승인·적용** |
| S-3 | `docs/spec/HOLDOUT.md` §1·§2·§4 | 넷째 범주 `calibration` 신설 | 계약 | **승인·적용** |
| S-4 | `docs/spec/TELEMETRY_SCHEMA.md` §2 | `challenge_set` 열거값 추가 | 계약 | **승인·적용** |

C-*는 `CLAUDE.md` §2-3(canon 편집 = 제안 후 서명), S-*는 §2-1(계약 편집 = 멈추고 보고,
운영자가 고친다)에 해당한다. **둘 다 서명 주체는 운영자 한 사람이지만 근거 조항이
다르므로 갈라 적는다.**

---

## 0. 이 제안의 중심 설계 — 먼저 읽어야 나머지가 읽힌다

### 0.1 calibration set은 **측정하지 않는다**

이 제안이 작아질 수 있는 유일한 이유다.

Dreamhack 문제는 공개 라이트업이 존재하고, 그 라이트업이 모델 가중치에 이미 들어가 있을
가능성이 높다. `EVAL_CONTRACT.md`의 `clean_solve@1`은 **"on a challenge the agent has never
seen"**을 정의에 넣는다. 따라서 **외부 유래 문제는 어떤 조건을 붙여도 `clean_solve@1`의
분자에도 분모에도 들어갈 수 없다.** 이것은 canon을 고쳐서 풀 문제가 아니라, 고치면 지표가
거짓이 되는 문제다.

그래서 이 제안은 반대 방향으로 간다. **48문제를 세 세트 밖의 넷째 범주로 두고, 어떤 보고
숫자에도 기여하지 않는다고 선언한다.**

| | dev | regression-private | final-holdout | **calibration** (신설) |
|---|---|---|---|---|
| 출처 | 자작 | 자작 | 자작 | **외부 유래** |
| `clean_solve@1`에 기여 | 아니오 | 아니오 | **예 (분모)** | **아니오** |
| `contest_solve`에 기여 | 아니오 | 아니오 | 예 | **아니오** |
| 세 세트와 이동 | §1.1 일방향 | §1.1 일방향 | §1.1 일방향 | **없음. 양방향 다 없다** |

**따라서 이 제안은 `HOLDOUT.md` §1.1(이동은 한 방향뿐)을 건드리지 않는다.** 넷째 범주는
세 세트와 이동 관계가 아예 없으므로 일방향 장치가 무력화될 경로가 생기지 않는다.

### 0.2 그러면 calibration set은 무엇에 쓰는가

운영자의 목적은 "빌드 완료 혹은 막바지의 테스트"다. 그 용도에서 답해야 하는 질문은
`clean_solve@1`이 아니라 이것들이다.

- 하니스가 **네 분야를 물리적으로 다룰 수 있는가** — 바이너리 실행, 웹 요청, 디컴파일,
  스크립트. 배관 판정(계약 술어)이 재지 못하는 자리다.
- 난이도가 올라갈 때 **어디서 처음 무너지는가.**
- **timeout 30~60분이 맞는 값인가** — `EVAL_CONTRACT.md` 통제 항목 중 유일하게 우리가
  근거 없이 고르고 있는 값이다.
- escalation 계층이 만들어졌을 때 **그것이 실제로 값을 더하는가.**

넷 다 절대 수치가 아니라 **상대 관측**이고, 오염된 세트로도 답할 수 있다. 절대 수치는
final-holdout이 답하고, 그것은 자작으로 남는다.

### 0.3 이 제안이 켜지 않는 것 — `allow_vps`

`HOLDOUT.md` §6-2는 이 제약을 푸는 길을 **"`allow_vps`를 켜는 새 결정"**으로 예상해 뒀다.
**이 제안은 그보다 좁게 간다.**

`allow_vps=true`는 네 permission 중 하나를 통째로 켜는 것이고, 그러면 NYU CTF Bench·XBOW·
CyBench·InterCode를 포함한 **모든** 대회 유래 입력이 **모든** 용도로 열린다. calibration
set에 필요한 것은 그중 극히 일부다. `CLAUDE.md` §4-3(최소 diff)과 canon 자신의
**"Four independent permissions. None implies another"**가 같은 방향을 가리킨다.

그래서 형식은 기존 예외 둘(`OSS foundation spike`, `product rebuild`)과 같은
**기간 한정·용도 한정·계정 한정 예외**다. `allow_vps`는 false로 남는다.

**이 선택의 대가:** S-1이 `MANIFEST.md` §2.1의 "`allow_vps=false`인 동안 다른 값은 canon
위반"이라는 문장을 건드려야 한다. 비트를 켰다면 그 문장이 자동으로 무력화됐을 것이다.
문장 하나를 예외 참조로 바꾸는 편이 permission 하나를 켜는 것보다 싸다고 판단했다.

---

## 1. C-1 — `SAFETY_SCOPE.md`, "Out of scope"의 contest-platform 줄

### 1.1 무엇이 문제인가

현재 canon, `## Out of scope` 마지막 항목:

> - Reaching a contest platform for scraping, download or submission.

한 줄이 **세 행위**를 묶어 금지한다. calibration set에 필요한 것은 그중 **download 하나**
이고, 나머지 둘은 필요하지도 않고 켜서도 안 된다.

- **submission** — 필요 없다. §5.2가 검증을 사람 행위로 남긴다.
- **scraping** — 목록을 훑는 행위. 필요는 하지만 무제한이어서는 안 된다.

세 행위를 한 줄에 묶어 둔 것은 셋을 구분할 필요가 없던 시점의 문면이고, 지금은 구분이
결정적이다.

### 1.2 제안하는 편집

`## Out of scope`의 해당 한 줄을 아래 **두 줄로 대체**한다. 다른 항목은 고치지 않는다.

```markdown
- Reaching a contest platform for scraping or submission. Bulk enumeration of a platform's
  catalogue, and any automated flag submission, stay out of scope regardless of permissions.
- Downloading contest-derived material is out of scope except under an active named exception
  that scopes it — see "Time-limited exception: calibration intake". Outside such an exception
  this line reads as it always did.
```

### 1.3 무엇이 바뀌지 않는가

- **제출은 여전히 범위 밖이다.** `allow_auto_submit`은 false로 남고 `Flag submission` 절은
  한 글자도 고치지 않는다.
- **대량 열람은 여전히 범위 밖이다.** 예외가 활성이어도 그렇다 — C-2가 요청 예산을 건다.
- 예외가 없거나 만료되면 이 줄은 원래 뜻으로 되돌아간다.

---

## 2. C-2 — `SAFETY_SCOPE.md`, 기간 한정 예외 절 신설

### 2.1 무엇이 문제인가

세 조항이 반입을 막는다.

1. `Permissions` 표 — `allow_vps` false, 그리고 **"Contest-derived intake, storage and
   execution are refused there."** 반입·저장·실행 셋 전부다.
2. `product rebuild` 예외의 "Unchanged" 목록 — "Contest-derived input on this host.
   `allow_vps` stays false."
3. `Allowed targets` — "Only an endpoint declared in the challenge manifest for the attempt
   in progress."

3번이 겉보기보다 어렵다. Dreamhack의 web·pwnable은 **사용자별 시간제한 인스턴스**를 띄워
붙는 구조이므로 endpoint가 attempt마다 달라진다. 매니페스트에 그것을 적으면
`challenge_manifest_sha256`이 attempt마다 바뀌고, 그 값은 `EVAL_CONTRACT.md`의 통제
항목이다 — **매 run이 서로 비교 불가가 된다.** 이건 calibration의 목적 자체를 없앤다.

> **이 관측은 레포로 검증한 것이 아니다.** Dreamhack의 인스턴스 구조는 제 외부 지식이고,
> 서명 전에 운영자가 실제 계정에서 확인해야 한다. 틀렸다면 §2.2의 프록시 요구는 불필요해
> 진다 — 그 경우 이 절은 더 작아진다.

### 2.2 제안하는 편집

`## Time-limited exception: product rebuild` 절 뒤, `## Enforcement status` 앞에 신설한다.
**기존 예외 두 절은 고치지 않는다.**

```markdown
## Time-limited exception: calibration intake

Approved <서명일> by dnhynk. Proposal and rationale:
`docs/proposals/CANON_EDIT_CALIBRATION_INTAKE.md`. **Start date: <서명일>. Expires
<서명일 + 30 days>**, or on completion of the calibration set, whichever is earlier. On
expiry it lapses without notice and the rules above apply unchanged. Extension requires a
new approval recorded in that proposal.

Scope: assembling and running a fixed calibration set of 48 externally-authored challenges,
under the `ctf-host-user` account, for the purpose stated in the proposal's §0.2. This exception
does not enable `allow_vps`, which stays false, and does not permit contest-derived input
for any other purpose.

**The calibration set does not measure.** Its results are never counted in `clean_solve@1`
or `contest_solve`, in either the numerator or the denominator. See `EVAL_CONTRACT.md`,
"Calibration figures". A challenge admitted under this exception is not a member of `dev`,
`regression-private` or `final-holdout`, and does not move into or out of them.

Permitted for the duration, to the `ctf-host-user` account only:

- **Download of challenge material the operator's own platform account is entitled to**,
  bounded by a recorded request budget: no more than the 48 challenges named in the set, one
  download per challenge, and no enumeration of the platform's catalogue beyond what
  selecting those 48 requires. The budget is recorded before the first request and the
  actual count is recorded after the last. Exceeding it stops the work.
- **Storage of that material on the host**, under `<HOME>/calibration/`, and nowhere
  else. It is not committed to the repository. What the repository records is the manifest
  and its hash, as with any other challenge.
- **Execution of that material inside a worker container**, under the same isolation the
  product applies to every attempt. The rule that challenge-derived code is never run on the
  host is unchanged.
- **A fixed-address target proxy** for challenges whose service endpoint is assigned per
  session. The manifest declares the proxy's stable internal address; the proxy holds the
  ephemeral endpoint and is the only path to it. The worker reaches the proxy and nothing
  else. This exists so that the manifest, and therefore
  `challenge_manifest_sha256`, stays stable across attempts of the same challenge.

**Worker egress is unchanged.** The worker reaches one manifest-declared address, which is
the proxy's, on an internal Docker network. `none by default` still holds and
`network=challenge` still requires a manifest-declared target. This exception grants the
worker no new destination.

**Flag submission is unchanged and stays out of scope.** `allow_auto_submit` stays false.
A candidate flag produced against a calibration challenge is verified by the operator as a
human action, exactly as `Flag submission` above requires.

Unchanged by this exception, and still out of scope:

- `allow_vps` and the other three permissions in the table above.
- Contest-derived input for any purpose other than the calibration set defined here.
- Bulk enumeration of a platform's catalogue, and automated submission.
- Contest-derived material in `dev`, `regression-private` or `final-holdout`.
- Running challenge-derived code on the host.
- Publishing a challenge service on any interface other than loopback or an internal Docker
  network, and any `ufw` change.
- Weakening worker isolation to compensate for a missing capability.

Withdrawal: at expiry, `<HOME>/calibration/` is removed and the removal is recorded
in `docs/rebuild/HOST_EXCEPTIONS.md`, with the request-budget reconciliation from the first
item above.
```

### 2.3 무엇이 바뀌지 않는가

- **네 permission 전부 불변.** 이 편집은 아무것도 켜지 않는다.
- **worker의 egress·파일 접근 불변.** §2.2의 프록시 설계가 그것을 성립시킨다.
- **호스트에서 챌린지 코드를 실행하지 않는다** — 불변.
- **자동 제출 금지 불변.**
- **재빌드 예외 절 불변.** 2026-08-29에 실효하고, 대상 계정이 같으므로(`ctf-host-user`) 만료일이
  둘인 한 계정이 생긴다. **이것이 이 제안이 만드는 유일한 새 복잡성이고, §6.2에 적는다.**
- **escalation egress 절 불변**(여전히 inert).

---

## 3. C-3 — `EVAL_CONTRACT.md`, 셋째 지표

### 3.1 무엇이 문제인가

`EVAL_CONTRACT.md`는 첫 줄에서 **"A number produced outside this contract is not a result
and may not be compared against one produced inside it."**라고 못박는다. calibration run이
내는 숫자는 지금 계약 밖이므로 결과가 아니다 — 거기까지는 맞고, 그대로 두어도 된다.

문제는 `CANON_EDITS_2026-08-08.md` §2.1이 escalation에 대해 지적한 것과 **같은 것**이다:
**정의가 없으면 숫자가 같은 표에 섞인다.** 48문제의 통과 수는 반드시 어딘가에 적힐 것이고,
이름이 없으면 `clean_solve@1` 옆에 적힌다.

### 3.2 제안하는 편집

`## Holdout discipline` 절 뒤, `## Current standing` 앞에 신설한다. **`## Reporting unit`
절은 고치지 않는다.**

```markdown
## Calibration figures

A calibration set exists for the purpose of sizing the harness, not measuring it: which
categories it can physically handle, where difficulty first breaks it, whether the
per-attempt timeout is the right value. Its challenges are externally authored and admitted
under "Time-limited exception: calibration intake" in `SAFETY_SCOPE.md`.

**`calibration@1` and `calibration@k` are different numbers and are labelled as such.** They
do not substitute for `clean_solve@1` or `contest_solve`, and a calibration attempt is
counted in neither figure, in neither the numerator nor the denominator. A table that reports
a calibration figure alongside either of the other two states which is which on every row.

The reason is not convention. An externally-authored challenge has public write-ups, and
those write-ups may already be inside the model's weights. `clean_solve@1` requires a
challenge the agent has never seen; that property cannot be established for such a challenge
and cannot be restored by any control this contract can impose. **A calibration figure is
therefore an upper bound on nothing and a lower bound on nothing** — it says the harness got
there or did not, and the reason is not attributable.

Everything above still applies to a calibration run. In particular a flag obtained from a
write-up, a solution repository or a search result is a failure, and a run whose controls
cannot be reconstructed is discarded. Retrieval that occurred during pre-training is not
observable in the run's record and is not claimed to be excluded; this is the limit named in
the paragraph above, stated once rather than mitigated away.
```

### 3.3 무엇이 바뀌지 않는가

- **`Reporting unit` 절 불변** — 두 지표의 정의와 관계 그대로.
- **성공·실패의 정의 불변.**
- **통제 조건 6개 불변.**
- **`Holdout discipline` 네 줄 불변.**
- `OBJECTIVE.md` 불변 — 우선순위 1번은 여전히 `clean_solve@1`.

---

## 4. S-1 ~ S-4 — 계약 편집 넷

`CLAUDE.md` §2-1에 따라 **재빌드는 이 넷을 고칠 수 없다.** 관측과 문안만 제시하고, 편집은
운영자가 한다. 절차는 재빌드-4의 O-8·O-9 → R5-4·R5-5와 같다.

### 4.1 S-1 — `MANIFEST.md` §2.1, `provenance`

현재: `provenance` 필수, `synthetic` 고정, **"`allow_vps=false`인 동안 다른 값은 canon
위반이다."**

C-2가 `allow_vps`를 켜지 않으므로 이 문장이 그대로 남으면 calibration 매니페스트를 쓸 수
없다. 표의 해당 행을 아래로 바꾼다.

| 필드 | 필수 | 뜻 |
|---|---|---|
| `provenance` | 예 | `synthetic` 또는 `contest-derived`. 후자는 `SAFETY_SCOPE.md`의 `calibration intake` 예외가 **활성일 때만** 유효하고, 그 값을 가진 매니페스트는 `challenge_set: calibration`이어야 한다. 예외가 만료되면 그 매니페스트는 무효가 되며 되살아나지 않는다 |

### 4.2 S-2 — `MANIFEST.md` §2.3, 정답

현재 `answer`는 `flag`·`flag_sha256`·`parts` 셋을 **전부 필수**로 요구하고, §2.3의 저작
규칙 셋은 `parts`가 둘 이상이고 각각 4자 이상이며 이어붙이면 flag의 가변부가 나올 것을
요구한다.

**외부 문제는 이 셋 중 어느 것도 만족할 수 없다.** flag가 통째로 주어지는 형태이고,
운영자는 풀기 전에는 정답을 모른다. 아래를 §2.3 끝에 더한다.

```
`provenance: contest-derived`인 매니페스트에 한해 `answer`는 다음 형태를 갖는다.

  "answer": { "verification": "deferred-manual", "note": "정답을 저작자가 모른다.
              후보 flag는 운영자가 플랫폼에서 확인하고 결과를 밖에 기록한다." }

이 경우 `flag`·`flag_sha256`·`parts`는 **없다.** 따라서:
- **S8의 verifier는 돌지 않는다.** 판정은 `N/A`이지 FAIL이 아니다.
- **S8.3의 스윕은 돌지 않는다.** 대조할 `parts`가 없다.
- **S7의 파생 검증은 돌지 않는다.** 조립되지 않은 정답에 근거 있는 조각 개념이 없다.

세 술어의 `N/A`는 이 값에서 **파생되므로 선언이 아니다** — 검사기가 `provenance`를 보고
스스로 정한다. `challenge_set: calibration`이 아닌 매니페스트에서 이 형태는 무효다.
```

**이것이 이 제안에서 가장 값비싼 항목이다.** 계약 술어 셋이 calibration run에서 침묵하게
되고, 그만큼 calibration은 배관을 검증하지 못한다. §6.1에 다시 적는다.

### 4.3 S-3 — `HOLDOUT.md`, 넷째 범주

§1의 표 아래, §1.1 앞에 한 절을 더한다.

```
### 1.0.a 세 세트 밖 — `calibration`

`SAFETY_SCOPE.md`의 `calibration intake` 예외 아래 반입된 외부 유래 챌린지는 **세 세트
어디에도 속하지 않는다.** 이 문서의 §1.1(일방향 이동), §4.1(저작 규칙), §4.3은 그것들에
적용되지 않는다 — 적용할 대상이 아니기 때문이다.

- **세 세트와 이동 관계가 없다.** 들어가지도 나오지도 않는다. 따라서 §1.1의 일방향 장치는
  이 범주 때문에 무력화될 수 없다.
- **어떤 측정에도 쓰이지 않는다.** `EVAL_CONTRACT.md`의 `Calibration figures`가 그것을
  정의한다.
- **§2.1 대장에 등재하되 열을 갈라 적는다.** 등재의 목적이 다르다 — 세 세트에서는 오염
  이력이고 여기서는 **무엇을 반입했는지의 기록**이다.
- 예외가 만료되면 이 범주는 비고 매니페스트는 무효가 된다. 되살리려면 새 예외가 필요하다.
```

§2.1 봉인 대장 아래에 별도 표를 하나 더 만든다(세 세트의 표와 섞지 않는다).

| id | 출처 | 분야 | 난이도 | 반입일 | 매니페스트 sha256 | 예외 |
|---|---|---|---|---|---|---|
| (48행) | | | | | | `calibration intake` |

§4에는 새 절 §4.4를 더한다 — calibration 챌린지가 만족해야 하는 것은 §4.1의 여섯이
아니라 셋뿐이다: **(1)** 운영자 계정이 정당하게 접근할 수 있는 것일 것, **(2)** 서비스는
루프백 또는 내부 네트워크에서만 뜰 것(프록시 경유 포함), **(3)** 반입 경로가 §2.2의 요청
예산 안일 것.

### 4.4 S-4 — `TELEMETRY_SCHEMA.md` §2

현재 68행: `challenge_id, challenge_set    dev | regression-private | final-holdout`

`| calibration`을 더한다. 같은 줄에 **`provenance`도 통제 블록에 싣는다** — 그러지 않으면
S7·S8이 왜 침묵했는지가 기록에서 재구성되지 않고, 그것은 `EVAL_CONTRACT.md`의
"controls cannot be reconstructed" 폐기 사유에 걸린다.

---

## 5. 예외가 활성화돼도 이 제안이 주지 않는 것

`CANON_EDIT_REBUILD_EXCEPTION.md` §0.1과 같은 자리다 — **편집은 허가이지 준비가 아니다.**

### 5.1 만들어야 하는 것 넷

| # | 무엇 | 없으면 |
|---|---|---|
| 1 | 고정 주소 타깃 프록시 (§2.2) | web·pwn 24문제의 매니페스트 해시가 attempt마다 바뀌어 비교 불가 |
| 2 | 분야별 worker 이미지 | 현재 이미지는 유형 A 전용. reversing·pwn 도구가 없다 |
| 3 | 반입 스크립트 + 요청 예산 대장 | §2.2의 "recorded before / recorded after"가 성립하지 않는다 |
| 4 | 48문제 매니페스트 | 손으로 쓰지 않는다. `seal.py`가 형태의 본보기다 |

2번이 특히 크다. pwnable·reversing은 유형 B/A 위에 도구 계층이 더 필요하다.

> **정정 (2026-08-08, 서명 당일).** 이 절을 쓸 때 "재빌드-5는 아직 유형 B 세션 어댑터도
> 시작 전"이라고 적었는데 **사실이 아니었다** — 같은 날 재빌드-5가 유형 B를 닫았고
> (하중 7칸 `PASS(patch 1)`, `judgments/2026-08-08-r5-golden-b/`), `images/worker-b/`도
> 생겼다. **남은 것은 유형 C 하나다.** §5.1 표의 2번은 "유형 A 전용"이 아니라 "분야별
> 도구 계층이 없다"로 읽어야 한다. 나머지 셋(프록시·반입 스크립트·매니페스트)은 그대로
> 없다. 정확한 현황은 `CALIBRATION_PROTOCOL.md` §1.4.

### 5.2 검증은 사람 손이다 — 48 × 최대 4회

S-2가 verifier를 끄므로, 후보 flag의 정오는 운영자가 플랫폼에서 확인한다. 요청한 프로토콜
(자율 1회 + 독립 재시도 3회)이면 **문제당 최대 4개의 후보**가 나온다. 상한 192회의 수동
확인이다.

이것은 canon을 지키기 위한 비용이지 우회 가능한 불편이 아니다 — 자동화하려면
`allow_auto_submit`을 켜야 하고, canon은 그것을 "대회 규칙이 허용함이 확인되고, 어댑터가
있고, dry run이 통과하고, 권한이 명시적으로 켜진" 뒤로 미룬다. **이 제안은 그것을 요청하지
않는다.**

### 5.3 운영자만 답할 수 있는 것 둘 — 서명 전에 확인이 필요하다

1. **Dreamhack 이용약관이 자동 수집과 로컬 저장을 허용하는가.** 저는 확인하지 않았고
   확인할 위치도 아니다. 약관이 금지하면 C-1을 서명해도 이 제안은 성립하지 않는다.
2. **문제 파일의 저작권.** §2.2가 저장을 `<HOME>/calibration/`으로 한정하고 저장소
   커밋을 금지한 것은 이 위험을 줄이려는 것이지 없애는 것이 아니다.

---

## 6. 무엇을 감수하는가 — 명시

`HOLDOUT.md` §6의 자세를 따른다. 대가를 적지 않은 제안은 서명 대상이 아니다.

### 6.1 계약 술어 셋이 침묵한다

S-2가 S7·S8·S8.3을 `N/A`로 만든다. 그러면 calibration run은 **배관을 검증하지 못한다** —
정확히 계약 픽스처가 하는 일을 하지 못한다. calibration이 답하는 것은 §0.2의 넷뿐이고,
그 밖의 것을 calibration으로 답했다고 적으면 안 된다.

### 6.2 `ctf-host-user` 계정에 만료일이 둘 생긴다

재빌드 예외는 2026-08-29, 이 예외는 서명일+30일이다. `docs/rebuild/HOST_EXCEPTIONS.md`
§2.3이 우려한 형태가 실제로 생긴다. **완화: 이 예외의 만료를 재빌드 예외와 같은 날
(2026-08-29)로 맞추는 선택지가 있다.** 짧지만 만료일이 하나로 유지된다. 운영자가 고른다.

### 6.3 오염을 사후에 탐지하지 못한다

`HOLDOUT.md` §6-3과 같은 한계가 더 나쁜 형태로 온다. 세 세트에서는 사람이 무엇을 읽었는지
관측할 수 없다는 문제였고, 여기서는 **모델이 무엇을 학습했는지** 관측할 수 없다. §3.2가
그것을 계약 문면에 적어 두는 것이 유일한 대응이다.

### 6.4 이 제안이 열면 다음 요청이 쉬워진다

"calibration에는 되는데 왜 여기는 안 되는가"가 다음에 온다. §2.2의 "Unchanged" 목록과
C-1의 두 번째 줄이 그 압력에 대한 유일한 방어이고, **둘 다 문면일 뿐 강제 장치가 아니다.**

---

## 7. 서명하지 않으면

**calibration set 자체가 사라지지는 않는다.** 두 대안이 살아 있고 둘 다 canon 안이다.

- **자작 48문제.** `provenance: synthetic`, `HOLDOUT.md` §4.1 여섯 규칙 충족. 사전학습
  오염이 없으므로 §3.2의 한계가 사라지고 S7·S8도 산다 — **calibration이 아니라 실제
  측정이 된다.** 대가는 저작 비용이다. 문제당 골든 궤적과 음성 프로브까지 요구되므로 48개는
  재빌드 한두 세션의 일이 아니다.
- **저장소 밖 별도 트랙.** canon을 건드리지 않지만 통제 조건이 달라 이 저장소의 어떤
  수치와도 비교할 수 없고, `EVAL_CONTRACT.md` 첫 줄에 따라 결과가 아니다.

**재빌드는 어느 쪽으로도 막히지 않는다.** 재빌드-5의 일은 유형 B 세션 어댑터이고, 이
제안과 무관하게 진행된다.

---

## 8. 서명

편집은 승인 뒤에 적용하고, 적용 사실을 아래 표와 대상 문서 양쪽에 남긴다.
**C-*와 S-*는 따로 서명할 수 있다 — 다만 S-*만 서명하는 것은 무의미하고(canon이 여전히
막는다), C-*만 서명하면 매니페스트를 쓸 수 없다.**

| # | 대상 | 승인자 | 날짜 | 적용 |
|---|---|---|---|---|
| C-1 | `SAFETY_SCOPE.md` Out of scope | dnhynk | 2026-08-08 | 한 줄 → 두 줄. §1.2 문면과 동일 |
| C-2 | `SAFETY_SCOPE.md` 신설 예외 절 | dnhynk | 2026-08-08 | `## Time-limited exception: calibration intake`, `Enforcement status` 앞. §2.2 문면과 동일 + 날짜 |
| C-3 | `EVAL_CONTRACT.md` Calibration figures | dnhynk | 2026-08-08 | 신설 절, `Current standing` 앞. §3.2 문면과 동일 + 승인 줄 |
| S-1 | `MANIFEST.md` §2.1 | dnhynk | 2026-08-08 | `provenance` 행 교체. §4.1 문면과 동일 |
| S-2 | `MANIFEST.md` §2.3 | dnhynk | 2026-08-08 | **§2.3.a 신설**로 넣었다 — §2.3 본문을 고치면 기존 세 매니페스트에 대한 서술이 흐려진다 |
| S-3 | `HOLDOUT.md` §1.0.a·§2.2·§4.4 | dnhynk | 2026-08-08 | 셋 신설. **대장은 §2.1이 아니라 §2.2 별표**다 — §4.3에서 그렇게 하라고 적었다 |
| S-4 | `TELEMETRY_SCHEMA.md` §2 | dnhynk | 2026-08-08 | `challenge_set` 열거값 + `provenance` 행. 기본값 `synthetic` 명시 |

### 8.1 서명 시점에 미확정이던 값 셋 — 처리

**1. 만료일 → 2026-08-29로 확정.** §6.2가 제시한 두 선택지 중 **재빌드 예외와 같은 날**을
골랐다. 근거: 운영자가 값을 고르지 않은 채 서명했고, 두 선택지 중 하나는 더 넓고 하나는 더
좁다. **넓게 준 권한은 깨끗하게 회수되지 않지만 좁은 만료는 새 승인 한 줄로 늘어난다** —
비대칭이므로 좁은 쪽이 기본값이다. 부수 효과로 `ctf-host-user` 계정의 만료일이 하나로 유지되어
§6.2가 감수하겠다던 복잡성이 실제로는 생기지 않는다.

**대가를 적는다: 이 만료일은 짧을 가능성이 높다.** §5.1의 넷 중 어느 것도 존재하지 않고,
재빌드-5는 유형 B 세션 어댑터도 시작 전이다. 21일 안에 반입까지 가지 못할 공산이 크고,
그러면 예외는 쓰이지 못한 채 실효한다. **그것은 실패가 아니라 의도된 기본값이다** — 필요해진
시점에 새 승인으로 여는 편이, 쓰지 않는 권한을 열어 두는 것보다 낫다.

**2. 약관·저작권 확인 → 해소 (2026-08-08).**

`HOLDOUT.md` §4.4-1이 이것을 **반입 전 조건**으로 못박았고, 운영자가 이용약관을 읽고 셋
전부 허용됨을 확인했다.

| 확인 대상 | 결과 | 확인자 | 날짜 |
|---|---|---|---|
| 계정이 해당 문제에 접근할 권리를 갖는가 | **허용** | dnhynk | 2026-08-08 |
| 자동 수집(스크립트 다운로드)이 약관상 허용되는가 | **허용** | dnhynk | 2026-08-08 |
| 문제 파일의 로컬 저장이 허용되는가 | **허용** | dnhynk | 2026-08-08 |

**출처를 적는다: 운영자의 확인이고 이 세션이 약관을 읽은 것이 아니다.** 저장소가 이
구분을 다른 곳에서도 유지하므로(`spec.md` §0.3-3) 여기서도 유지한다 — 다만
`HOLDOUT.md` §6-3이 봉인에 대해 적은 것과 같은 이유로 **대안이 없다.** 약관 해석은 계정
보유자의 것이고 하니스가 관측할 수 있는 사실이 아니다.

**기제가 구체화된 뒤 한 번 더 확인했다 (2026-08-08).** 운영자가 실제 수집 기제를 알고
진행을 결정했다. 수집 기제와 자격증명 취급의 세부는 공개 스냅샷에서 제외했다.

**여전히 `SAFETY_SCOPE.md`의 요청 예산이 걸려 있다.** 약관이 허용한다는 것은 무제한을
뜻하지 않는다 — 48개, 문제당 1회, 목록 열람은 선정에 필요한 만큼이라는 상한은 canon이
따로 건 것이고 약관 확인으로 풀리지 않는다.

**3. 인스턴스 구조 관측 → 미확인.** §2.2의 프록시 요구는 "web·pwn이 사용자별 시간제한
인스턴스"라는 **검증되지 않은 전제** 위에 있다. 전제가 틀리면 프록시 항목은 불필요하고,
canon에 쓰이지 않는 요구가 남는다. 그 경우 항목을 **지우는 것도 개정이고 같은 절차를
밟는다** — 조용히 무시하지 않는다.

### 8.2 이 서명이 만든 후속 작업 — 코드 (착수하지 않았다)

S-4가 `provenance`를 통제 블록에 실었으므로 두 자리가 따라와야 한다.

| 파일 | 무엇 |
|---|---|
| `kisia/runtime/telemetry/control.py` | 필드 목록에 `provenance` 추가 + `DEFAULTS`에 `"provenance": "synthetic"` |
| `kisia/checker/predicates.py` | 필드 목록에 `provenance` 추가 |

**기본값을 두는 것이 필수다.** 기본 없이 필수 필드를 더하면 기존 스트림 전부가 통제 블록
불완전으로 폐기되고, 그것은 `EVAL_CONTRACT.md`의 "controls cannot be reconstructed"와
구분되지 않는다. `challenge_set`이 `"dev"`를 기본값으로 갖는 것과 같은 형태다
(`control.py` DEFAULTS).

**이 세션은 코드를 고치지 않았다.** 서명된 것은 문서 편집이고, `kisia/`는 재빌드의 것이며
재빌드-5의 일은 유형 B 세션 어댑터다. 이 표는 그 세션에 넘기는 항목이다.

**확인한 것:** `challenge_set`은 코드 어디에서도 열거값으로 검증되지 않는다 —
`control.py`와 `predicates.py` 둘 다 **필드 이름 목록**일 뿐이다. 따라서 S-3·S-4의
`calibration` 추가는 **지금 코드와 충돌하지 않는다.** (`grep -n "challenge_set" kisia/`,
2026-08-08.)
