# CANON_EDIT — 챌린지 저작을 건너뛰면 무엇으로 성적을 재는가

작성 2026-08-09, 재빌드-9. 부팅 프롬프트 §3.4 **서명 2**. **셋 중 가장 무겁다.**

**상태: 승인 (2026-08-09, dnhynk) — 선택지 (a′). canon 편집 없음.**

| # | 대상 | 무엇을 | 층 | 상태 |
|---|---|---|---|---|
| M-1 | **(a′)** — canon·계약 **미변경** | `clean_solve@1`을 대회 이후로 미루고, 그 동안 `calibration@1`로 하니스 크기를 잰다 | 편집 없음 | **승인** |

> **무엇이 실제로 바뀌었나: 문서는 하나도 안 바뀌었다.** (a′)는 `EVAL_CONTRACT.md`가
> **이미 정의하고 승인한** `calibration@1`을 쓰는 것이므로 canon도 계약도 고칠 것이
> 없다. 바뀐 것은 **다음 세션의 범위**다 — 아래 셋이 그 귀결이고
> `NEXT_SESSION.md`가 그것을 나른다.
>
> 1. **`clean_solve@1`은 대회 전까지 나오지 않는다.** 분모가 비어 있고(`HOLDOUT.md` §2)
>    그것을 채우는 유일한 길은 저작인데 §0.2가 건너뛰라고 했다. **미측정이라고 적는다.**
> 2. **`calibration@1`을 내려면 선행 작업 둘이 있다** — 매니페스트 **48개**가 아직 없고
>    (`HOLDOUT.md` §2.2), **39개가 `needs_vm`**(`O-21`)이라 프록시 아래서 선다는 보장이
>    없다. **"저작을 건너뛴다"가 "공짜로 측정이 생긴다"는 뜻이 아니다.**
> 3. **두 수를 같은 표에 실으면 행마다 어느 것인지 적는다** — `EVAL_CONTRACT.md`가
>    문면으로 요구한다. `calibration@1`을 `clean_solve@1`처럼 읽는 것이 이 선택의
>    유일한 실패 모드이고, **막는 것은 라벨 규칙 하나뿐이다. 검사기는 이 구분을 재지
>    않는다.**

---

## 0. 30초 요약

**§0.2가 "챌린지 저작은 건너뛴다"고 정했다. 그 귀결이 이것이다: 지금 이 저장소에는
성적을 낼 문제가 하나도 없다.** 실측이지 추정이 아니다 — §1.

고를 수 있는 것은 넷이고, **셋은 canon을 고치지 않는다.** 되돌릴 수 없는 것은 (b)
하나뿐이다.

**권하는 것: (a′).** canon을 고치지 않고, 이미 승인된 `calibration@1`로 하니스 크기를
재고, `clean_solve@1`은 문제가 생길 때까지 미룬다.

---

## 1. 실측 — 지금 세 세트에 무엇이 있나

`HOLDOUT.md` §2·§2.1을 그대로 읽은 것이다.

| 세트 | 지금 들어 있는 것 | 측정에 쓸 수 있나 |
|---|---|---|
| **dev** | `a-static` · `b-session` · `c-web` — 스파이크 계약 fixture 3종, **영구 dev** | **아니다.** §2가 못박는다: *"이 셋은 성능을 재는 데 쓸 수 없다. 원래 그 용도가 아니다 — 계약 픽스처는 배관을 강제하는 장치이고 CTF 문제가 아니다"* |
| **regression-private** | **비어 있다** | — |
| **final-holdout** | **비어 있다** | — |
| *(세 세트 밖)* **calibration** | 48문제, 전부 `dreamhack.io`, 349.3 MB | **`clean_solve@1`·`contest_solve`에는 아니다.** `calibration@1`로는 쓸 수 있다 — §3 |

**`clean_solve@1`의 분모가 비어 있다.** `OBJECTIVE.md`가 1순위로 두고
`EVAL_CONTRACT.md`가 *"the instrument"*·*"never dropped and never replaced"*라고 적는
그 수를, 지금 상태로는 **한 번도 낼 수 없다.**

---

## 2. 계약이 왜 calibration을 막는가 — 인용

`HOLDOUT.md` §1.0.a:

> **어떤 측정에도 쓰이지 않는다.** `clean_solve@1`·`contest_solve`의 분자에도 분모에도
> 들어가지 않는다.

`EVAL_CONTRACT.md` `Calibration figures`:

> An externally-authored challenge has public write-ups, and those write-ups **may already be
> inside the model's weights**. `clean_solve@1` requires a challenge the agent has never seen;
> **that property cannot be established** for such a challenge **and cannot be restored by any
> control this contract can impose.** A calibration figure is therefore **an upper bound on
> nothing and a lower bound on nothing.**

**이유는 관습이 아니라 인식론이다.** 푼 것이 실력인지 암기인지 **우리가 가릴 수 없다** —
느슨하게 판정해서 되는 문제가 아니라, 가릴 **수단이 없다**.

그리고 그 위험이 이 세트에서 특히 높다는 것이 실측돼 있다: `HOLDOUT.md` §2.2 —
**48 중 46이 외부·과거 대회 유래이고 자체 출제는 2개뿐이다**(`O-19`).

---

## 3. 고를 수 있는 것 넷

### (a′) — 권함. **canon 편집 없음**

**`clean_solve@1` 측정을 대회 이후로 미루고, 그 동안 `calibration@1`로 하니스 크기를
잰다.**

부팅 프롬프트 §3.4의 (a)("측정 없이 대회로 간다")를 실측으로 다듬은 것이다. **(a)의
대가를 그 표가 과대평가했다** — "대회 전에 우리가 나아졌는가를 답할 수단이 없다"고
적었는데, **수단이 하나 이미 승인돼 있다.**

`EVAL_CONTRACT.md`가 `calibration@1`을 이미 정의하고 그 용도를 이름으로 적는다:

> A calibration set exists for the purpose of **sizing the harness, not measuring it**: which
> categories it can physically handle, where difficulty first breaks it, whether the
> per-attempt timeout is the right value.

**대회 전에 실제로 답해야 하는 질문의 상당수가 그 목록에 있다.** 카테고리별로 물리적으로
도는가, 난이도 어디서 처음 깨지는가, attempt 타임아웃이 맞는가 — 프로덕션 스케줄러
(ADR-0003 §4가 열어 둔 "스케줄링 기본값")가 기다리는 것이 정확히 그 값이다.

**대가:** `clean_solve@1`은 대회 전까지 **한 번도 나오지 않는다.** "자율 코어가 나아지고
있는가"는 답하지 못한 채로 대회에 간다. `calibration@1`은 그 질문에 답하지 **않는다** —
canon이 "upper bound on nothing"이라고 적은 그대로다. **이 둘을 섞어 읽지 않는 것이
(a′)의 유일한 규율이고, `EVAL_CONTRACT.md`가 이미 그것을 강제한다**(*"A table that reports
a calibration figure alongside either of the other two states which is which on every row."*).

**공짜가 아니다 — 정직하게 적는다.** `calibration@1`을 실제로 내려면 셋이 필요하다.
① 48개 챌린지 **매니페스트**가 아직 없다(`HOLDOUT.md` §2.2: *"매니페스트는 아직 없다"*).
② 48 중 **39개가 `needs_vm`**(`O-21`)이라 프록시·네트워크 경로가 선다는 보장이 없다.
③ 모델 지출이 든다(유형 A 실측 하한 $0.0075/attempt × 48 × 반복 수 — 대회 문제에서
몇 배가 될지는 모른다). **"저작을 건너뛴다"가 "공짜로 측정이 생긴다"는 뜻은 아니다.**

### (b) — calibration을 측정에 쓸 수 있게 canon을 고친다. **되돌릴 수 없다**

`HOLDOUT.md` §1.0.a와 `EVAL_CONTRACT.md` `Calibration figures`를 고쳐, calibration
결과가 `clean_solve@1`에 들어가게 한다.

**대가:** `clean_solve@1`의 정의에서 **"본 적 없는 챌린지"가 빠진다.** 그것이 빠지면
그 수는 `EVAL_CONTRACT.md`가 말하는 *"the only uncontaminated measure of the agent
itself"*가 아니게 되고, **다른 이름으로 불러야 할 수를 같은 이름으로 부르게 된다.**

**되돌릴 수 없는 이유는 문서가 아니라 사실이다.** 문면은 다시 고칠 수 있다. 그러나
그 아래서 한 번 돌린 뒤에는 그 48문제를 **본 것**이 되고, 되돌리려면 **오염되지 않은
새 세트를 저작해야 한다** — 즉 (c)를 그때 하게 된다. 지금 (c)를 하는 것보다 비싸다.

**`FOUNDATION_DECISION.md` 전체가 막으려던 것이 이 형태다** — 세트를 살리려고 판정을
느슨하게 하는 것(`HOLDOUT.md` §1.2 마지막 줄, §9.6-1).

### (c) — 최소한만 저작한다. `regression-private`에 3~5문제

**대가:** §0.2가 건너뛰라고 한 저작 비용이 든다. 3~5문제면 유형당 하나 남짓이고,
스파이크가 fixture 3종을 만든 공정이 이미 있다(`docs/spike/FIXTURES.md`).

**얻는 것:** 오염되지 않은 회귀 계기. **다만 `clean_solve@1`은 아니다** —
`regression-private`은 "고치다가 다른 것을 깼는가"를 재는 자리이고,
`clean_solve@1`의 분모는 `final-holdout`이다(`HOLDOUT.md` §1). clean 측정을 원하면
`final-holdout`에도 저작해야 하고, 그것은 **측정 이벤트에서 한 번만 열린다.**

### (d) — 대회 성적 자체를 지표로 쓴다. **canon 편집 없음**

`contest_solve`는 *"what a contest actually scores"*이고, 대회에 나가면 그 수는
**저절로 생긴다.** 저작도 canon 편집도 필요 없다.

**대가:** 대회 **전에는** 아무 수도 없다. 그리고 `contest_solve`는 escalation 층을
포함하므로 자율 코어의 수가 아니다 — `EVAL_CONTRACT.md`가 *"the second figure does not
substitute for the first"*로 못박는다. **(a′)와 배타적이지 않다. 함께 고를 수 있다.**

---

## 4. 비교표

| | canon 편집 | 되돌릴 수 있나 | 대회 전에 나오는 수 | 저작 비용 |
|---|---|---|---|---|
| **(a′)** | **없음** | — | `calibration@1` | 없음 (매니페스트 48은 든다) |
| (b) | **있음, canon 2곳** | **아니다** | `clean_solve@1` (오염됨) | 없음 |
| (c) | 없음 | 예 | 회귀 계기 (clean 아님) | 3~5문제 |
| (d) | 없음 | 예 | 없음 (대회 후 `contest_solve`) | 없음 |

---

## 5. 무엇이 바뀌지 않는가 — 어느 선택지에서도

- **`OBJECTIVE.md`의 1순위는 그대로다.** (a′)·(c)·(d)는 `clean_solve@1`을 **미루는**
  것이지 **버리는** 것이 아니다. (b)만 그 정의를 바꾼다.
- **`HOLDOUT.md` §1.1의 일방향 이동은 불변.** 어느 선택지도 dev → regression-private
  방향을 열지 않는다.
- **세 fixture는 영구 dev.** 되돌릴 수 없고 이 문서가 건드리지 않는다.
- **`allow_auto_submit`은 false.** 후보 flag의 검증은 사람의 행위다.
- **calibration 예외의 만료(2026-09-30)와 회수 조항 불변.** (a′)를 고르면 09-30에
  349 MB가 회수되는 것이 **설계대로**이고, 그것을 막으려면 서명 1의 X-2가 따로 필요하다.

---

## 6. 감수하는 것 — 명시

1. **(a′)를 고르면 대회에 `clean_solve@1` 없이 간다.** "자율 코어가 나아졌는가"에
   답하지 못한 채 프로덕션을 얹는다. §0.2가 속도를 골랐으므로 정합적이지만,
   **그 사실이 나중에 "왜 재지 않았나"로 돌아온다.** 이 문단이 그 답이다.
2. **`calibration@1`을 `clean_solve@1`처럼 읽고 싶어진다.** 수가 하나뿐이면 그것이
   유일한 수가 된다. 완화는 canon의 라벨 규칙 하나뿐이고, **그것은 문서이지 장치가
   아니다.** 검사기는 이 구분을 재지 않는다.
3. **(a′)는 저작을 없애지 않고 미룬다.** 대회 뒤 `clean_solve@1`을 원하면 그때
   `final-holdout`을 저작해야 하고, **그 시점에는 이 저장소가 훨씬 많은 챌린지를 본
   뒤다.** 오염되지 않은 세트를 만들기가 지금보다 어렵지 쉽지 않다.

---

## 7. 서명

| # | 선택 | 승인자 | 날짜 | 적용 |
|---|---|---|---|---|
| M-1 | **(a′)** | **dnhynk** | **2026-08-09** | **canon·계약 편집 없음.** 귀결 셋은 머리말의 인용 블록, 범위는 `NEXT_SESSION.md` |

**(b)를 고르는 경우에만 canon 편집이 발생한다.** 그때 고칠 두 곳:
`docs/canon/EVAL_CONTRACT.md` `Calibration figures`, `docs/spec/HOLDOUT.md` §1.0.a.
**두 곳을 함께 고치지 않으면 canon과 계약이 어긋난 채로 남는다.**
