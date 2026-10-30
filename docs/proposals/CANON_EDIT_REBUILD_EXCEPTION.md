# CANON_EDIT — 재빌드 호스트 예외의 `SAFETY_SCOPE.md` 반영

문서 세션, 2026-08-08. `docs/rebuild/HOST_EXCEPTIONS.md` §5의 **세 번째 화살표**에 해당하는
문서다 — 제안(그 문서) → 서명(§5, 다섯 항목 전부 2026-08-08 dnhynk) → **`SAFETY_SCOPE.md`
반영(이 문서)**.

**상태: 반영 완료 (2026-08-08).** 착수일 **2026-08-08**, 만료 **2026-08-29**.

> **만료는 2026-09-30으로 연장됐다** — `CANON_EDIT_EXPIRY_EXTENSION.md`(E-2, 2026-08-08
> 서명). 재빌드-6·7이 21일 안에 끝나지 않으면 `ctf-host-user` 계정이 컨테이너 생성 권한을 잃기
> 때문이고, calibration 예외와 **같은 날로 맞춰** §2.3이 우려한 "만료일이 둘인 한 계정"을
> 피했다. **이 문서의 08-29는 이력이므로 고치지 않는다.**
canon 쪽 문면은 `SAFETY_SCOPE.md`의 "Time-limited exception: product rebuild" 절이다.

**왜 재빌드가 아니라 여기서 하는가.** canon 편집은 `CLAUDE.md` §2-3이 재빌드 세션에
금지한 행위다. 서명은 이미 있으므로 남은 것은 편집이고, 그 편집의 문안을 여기서 확정한다.
본보기는 `CANON_EDITS_2026-08-08.md`(같은 절차로 canon 두 곳을 고쳤다).

---

## 0. 반영 전에 알아야 할 것 둘

### 0.1 편집은 허가이지 준비가 아니다 — 컨테이너까지 다섯이 더 있다

`docs/rebuild/HOST_EXCEPTIONS.md`는 **아직 아무것도 존재하지 않는 상태**를 전제로 쓰였다.
반영 후에도 아래가 만들어지기 전에는 재빌드-2가 컨테이너를 띄울 수 없다. 전부 `ctf`의
sudo가 필요한 **운영자 작업**이다.

| # | 무엇 | 근거 | 현재 |
|---|---|---|---|
| 1 | 계정 **`ctf-host-user`** 신규 생성 | §2.3 (`ctf-spike-user` 재사용하지 않는다) | 없음 |
| 2 | **docker socket proxy** 셋업 — 생성/시작/정지/삭제만, bind mount·`--privileged`·`--network=host` 거부 | §2.1 | 없음. fallback은 raw docker 그룹 |
| 3 | `sudo /usr/local/sbin/rebuild-close` 스크립트 + sudoers **한 줄** | §2.2 · §4.1 | 없음 |
| 4 | **전용 재빌드 키** + OpenAI 프로젝트 예산 **$300 강제** | §2.5 | 없음. 스파이크는 공용 키 + 관측 상한이었다 |
| 5 | 제품 checkout `<HOME>/kisia` | §2.3 | 없음 |

**권고: 반영과 준비를 한 자리에서 한다.** 만료는 착수일 기준의 **달력** 21일이고,
§2.2의 자기 종료가 줄이는 것은 **노출**(root 동등 시간)이지 달력이 아니다. 둘은 다른 값이다.
반영만 먼저 하고 준비가 며칠 뒤면 그 며칠은 호스트를 쓰지 못한 채 상한에서 빠진다.

**그리고 재빌드-2의 호스트 없이 되는 일을 먼저 끝낸다** — `PINS.md`에서 새로 clone,
`vendor/` 복사, 심볼 허용 목록 테스트. 이 셋은 `PATH_SCOPE.md` §4.3의 표에서 워크스테이션
쪽이고, 상한을 소비하지 않는다.

### 0.2 "egress를 넓힌다"고 쓸 수 없다 — 이미 열려 있다

스파이크가 실측했다: **호스트 outbound는 네트워크 계층에서 전혀 제한되지 않는다**
(`docs/spike/HOST_EXCEPTIONS.md` §10.2 — `DEFAULT_OUTPUT_POLICY=ACCEPT`, OUTPUT 체인 규칙
**0개**). 재빌드 예외 §2.4가 그 사실을 그대로 적었다: **"egress allowlist는 허구였다."**

canon의 `Allowed network` 표는 `Host: api.openai.com only`라고 적는다. 그것은 **규칙의
진술이지 강제의 진술이 아니고**, canon 자신이 `Enforcement status` 절에서 그 구분을 이미
해 둔다("These are the rules. What is actually enforced in code ... is recorded in
`docs/evidence/...` §4 and §7").

따라서 이 편집은 **egress를 넓히지 않는다.** 넓힐 것이 없다 — 넓힌다고 쓰면 canon이
거짓을 말하게 된다. 대신 (a) 재빌드가 그 사실 위에서 시작한다는 것과 (b) **워커 쪽
egress 강제는 제품이 만들어야 한다는 것**을 적는다. 후자는 S2 seam의 재빌드 과제이고,
프로토타입이 한 번도 실행한 적 없는 경로다(evidence §7 B3-1).

---

## 1. 제안하는 편집

`docs/canon/SAFETY_SCOPE.md`의 **`## Time-limited exception: OSS foundation spike` 절 뒤,
`## Enforcement status` 앞**에 아래 절을 신설한다. 기존 스파이크 예외 절은 **고치지
않는다** — 그 절은 2026-08-21에 통지 없이 실효하고, Path A로 이미 닫혔다는 사실은
`docs/spike/HOST_EXCEPTIONS.md` §10.3에 있다.

```markdown
## Time-limited exception: product rebuild

Approved 2026-08-08 by dnhynk; the five terms are signed in
`docs/rebuild/HOST_EXCEPTIONS.md` §5. **Start date: <반영일>. Expires <반영일 + 21 days>**,
or on completion of the rebuild, whichever is earlier. On expiry it lapses without notice.
Extension requires a new approval recorded in that table.

Scope: building the product described in `docs/spec/spec.md`, on the integration host,
under a dedicated unprivileged account named `ctf-host-user`, separate from `ctf-spike-user`.

This exception differs from the spike's in kind, not only in dates. The spike measured
unverified code and threw it away; the rebuild vendors a verified MIT subset and builds a
product that keeps running. Container creation therefore stops being temporary access and
becomes **the product's permanent posture**, which is what the first item below settles.

Permitted for the duration, to the `ctf-host-user` account only:

- **Container creation through a socket proxy.** The proxy exposes container
  create/start/stop/remove and refuses host bind mounts, `--privileged`, `--network=host`,
  and `exec` into containers it did not create. The product speaks only to the proxy and
  never to `/var/run/docker.sock`. The raw socket stays out of scope; the proxy is the
  answer to the tension between that rule and a product that must launch workers.
  If proxy setup would block the rebuild's first day, raw docker-group membership is a
  fallback **and introducing the proxy becomes a named rebuild deliverable**. The product
  is not shipped on raw group membership.
- **Self-withdrawal.** `sudo /usr/local/sbin/rebuild-close` — one sudoers line, one command
  — revokes container-creation rights and stops rebuild containers. It is run between work
  sessions whenever more than a day will pass. The spike could not do this: withdrawal
  required the operator, which bound closing to their presence.
- **A dedicated model key with a provider-enforced budget of $300.** Unlike the spike's
  shared key and observed-only ceiling, this limit is enforced by the provider: reaching it
  fails the run rather than letting it continue silently. The key reaches processes as an
  environment variable only — never a file under `<HOME>`, never inside a container,
  never in a prompt, artifact, log or telemetry record. After every build/verify cycle the
  workspace, build images and volumes are searched for the key string; a hit stops the work,
  rotates the key, and is recorded.
- **Package installation for build purposes** — host-side environments and image builds.
  A container installing packages mid-attempt is recorded as an observation, not treated as
  normal.

**Host egress is not widened, because it is not currently constrained.** The spike measured
the host's outbound policy directly and found it unrestricted at the network layer
(`docs/spike/HOST_EXCEPTIONS.md` §10.2). The `Allowed network` table above states the rule;
the `Enforcement status` section below states what is actually enforced, and this is one of
the gaps it refers to. The rebuild starts from that fact rather than from a permission.

**Worker egress is unchanged and is the rebuild's own task.** `network=challenge` still
requires a manifest-declared target, and the container-side restriction has never been
exercised (`docs/evidence/2026-08-07-phase-b-evidence.md` §7). Implementing it is part of
the S2 seam, not something this exception grants.

Unchanged by this exception, and still out of scope:

- Contest-derived input on this host. `allow_vps` stays false; the rebuild verifies against
  self-authored synthetic fixtures only. NYU CTF Bench, XBOW, CyBench and InterCode are not
  brought here.
- The four permissions in the table above.
- Publishing a challenge service on any interface other than loopback or an internal Docker
  network, and any `ufw` change.
- The frozen prototype: `<PROTO_HOME>/kisia-agent`, the event log under `<PROTO_HOME>/kisia-runs`,
  and the six pinned prototype images.
- Weakening worker isolation to compensate for a missing capability.

Withdrawal is the checklist in `docs/rebuild/HOST_EXCEPTIONS.md` §4, executed between
sessions (§4.1) and at completion (§4.2), with results recorded there.
```

---

## 2. 무엇이 바뀌지 않는가

- **네 permission 불변.** 이 편집은 아무것도 켜지 않는다.
- **`allow_vps` 여전히 false.** 합성 fixture만.
- **worker의 파일 접근·egress 불변.** `/input` ro, `/work`·`/artifacts` rw, 그 밖 거부.
- **자동 제출 금지 불변.**
- **스파이크 예외 절 불변.** 2026-08-21에 실효한다. 두 절이 잠시 공존하고, 대상 계정이
  다르므로(`ctf-spike-user` / `ctf-host-user`) `docs/rebuild/HOST_EXCEPTIONS.md` §2.3이 우려한 "만료일이
  둘인 한 계정"은 생기지 않는다.
- **escalation egress 절 불변**(2026-08-08 승인, 여전히 inert).

## 3. 반영 기록

| 항목 | 값 |
|---|---|
| 문안 확정 | 2026-08-08, 문서 세션 |
| 서명 | `docs/rebuild/HOST_EXCEPTIONS.md` §5 — 다섯 항목 전부 2026-08-08 dnhynk |
| **반영일 (= 착수일)** | **2026-08-08** |
| **만료일** | **2026-08-29** |
| 반영 | `SAFETY_SCOPE.md` 신설 절 + `docs/rebuild/HOST_EXCEPTIONS.md` §5 표·§5.1, 한 커밋 |

**문면에서 벗어난 것: 없다.** §1의 텍스트를 그대로 넣었고, 서명·제안 문서 포인터와
확정된 날짜(2026-08-08 / 2026-08-29)만 채웠다.

**호스트 준비 다섯은 2026-08-08에 끝났다** — `docs/rebuild/HOST_EXCEPTIONS.md` §5.1과
`docs/runbook/rebuild-provisioning.md` §5.1(실측). 위 §0.1의 "현재: 없음"은 제안 시점의
값이다.

### 3.1 반영 뒤에 한 번 개정했다 — 키 항목

**2026-08-08, 서명·반영 당일.** 운영자에게 키가 하나뿐이어서 §1.2가 넣은
"**A dedicated** model key with a provider-enforced budget of $300"이 실상과 달라졌다.
그대로 두면 **canon이 갖고 있지 않은 분리를 주장**하게 되므로 — §0.2가 egress에 대해
피한 것과 같은 오류의 더 나쁜 방향 — 승인을 받아 고쳤다.

| | 반영 시점 (§1.2) | 개정 후 |
|---|---|---|
| 키 | 전용 재빌드 키 | **제품 키 공유** |
| 상한 장치 | 프로젝트 예산 | **선불 잔고 $300** (달력과 무관한 절대 상한) |
| 강제되는가 | 예 | **예** — 키 개수와 상한 강제는 분리 가능하다 |
| 감수하는 것 | — | **유출 시 제품 키 교체.** 그래서 매 사이클 키 검색이 의무 |

**핵심은 이것이다:** 스파이크가 못 고친 것은 키를 공유했다는 사실이 아니라 **상한이
어디에도 걸려 있지 않았다는 것**이었다. 잔고를 걸면 키가 하나여도 그 결함은 고쳐진다.
단 **auto-recharge가 꺼져 있어야 하고, 그것이 이 장치의 단일 실패점이다.**
