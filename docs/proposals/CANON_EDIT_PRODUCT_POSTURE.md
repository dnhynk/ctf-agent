# CANON 편집 제안 — 제품 상시 자세로의 승격과 거부 목록의 열거

프로덕션-2, 2026-08-09. `CLAUDE.md` §2-3의 절차다 — **canon 은 서명을 먼저 받는다.**
본보기는 `CANON_EDITS_2026-08-08.md`.

**운영자 결정 2026-08-09 (이 세션 중):**

- **항목 3** — *"지금 승격한다 — 소켓 프록시와 워커 egress 강제를 canon 으로."*
  **초안(`COMPLETION_CHECKLIST_DRAFT.md` §3 항목 3)의 권고는 "미승격 + 시점 조건"이었고
  운영자가 그것을 뒤집었다.** 그 사실을 접지 않는다.
- **항목 4** — *"여덟을 비준하고 canon 문면을 열거로 올린다."*

**이 문서는 아직 서명되지 않았다. 서명 전에는 canon 을 한 글자도 고치지 않는다.**

---

## 0. 열거로 가기로 하자마자 드러난 것 — **"여덟"이 틀렸다**

**이것이 이 제안의 가장 중요한 한 줄이다.** `HOST_EXCEPTIONS.md` §2.1.a-3 이 확장을
*"넷 → 여덟"* 으로 적고 §4.2 항목 4가 그것을 *"왜 여덟인가"* 로 물려받았다.
**프로덕션-2가 실제로 재 보니 여덟이 아니다.**

2026-08-09 실측(`COMPLETION_CHECKLIST_DRAFT.md` 부록 A). 프록시가 **create 본문에서**
거부하는 `HostConfig` 필드:

| # | 필드 | 프록시가 낸 사유 | canon 이 오늘 적나 |
|---|---|---|---|
| 1 | `Binds` | *host bind mount 는 거부된다 (canon)* | **적는다** |
| 2 | `Mounts[].Type=bind` | *host bind mount 는 거부된다 (canon)* | 같은 규칙의 다른 철자. 문면에 없다 |
| 3 | `Privileged` | *거부된다 (canon)* | **적는다** |
| 4 | `NetworkMode='host'` | *거부된다 (canon)* | **적는다** |
| 5 | `PidMode=host` | *같은 탈출의 다른 철자다* | 없다 |
| 6 | `CapAdd` | *같은 탈출의 다른 철자다* | 없다 |
| 7 | `Devices` | *같은 탈출의 다른 철자다* | 없다 |
| 8 | `UsernsMode=host` | *같은 탈출의 다른 철자다* | 없다 |
| 9 | `SecurityOpt` (`seccomp=unconfined` · `apparmor:unconfined` **두 철자 다**) | *같은 탈출의 다른 철자다* | 없다 |

**아홉이다.** 그리고 그것과 **별개의 기제 둘**이 더 있다:

- **소유권 검사** — `kisia-rebuild=1` 이 없는 컨테이너에 대한 `exec`·`cp`·`diff` 거부.
  실측 사유: *"컨테이너 … 는 우리 것이 아니다 (kisia-rebuild=1 없음)"*.
  **canon 은 이것을 `exec` 에 대해서만 적는다.** 실제로는 `PUT /archive`·`GET /changes`
  에도 걸린다.
- **허용 목록의 기본 거부** — `POST /volumes/prune`·`GET /volumes/{name}`·`POST /build`·
  `GET /images/json` 등. 실측 사유: *"허용 목록에 없다 (§2.1.a-3 의 기본값은 거부다)"*.

**따라서 "여덟"을 그대로 비준하면 canon 이 다시 틀린 수를 적게 된다.** 열거가 옳은 이유가
바로 이것이고 — 부류로 적었으면 이 어긋남이 **드러나지 않았을 것이다.**

**대가도 그대로 적는다:** 열거는 **반드시 낡는다.** 초안이 단 조건(§2.1.c 를 상시 회귀로
둔다)을 P-1 에 그대로 싣는다.

---

## 1. P-1 — 거부 목록을 열거로 올린다 (항목 4)

### 대상

`docs/canon/SAFETY_SCOPE.md` :200–204, "Time-limited exception: product rebuild" 의 첫 항목.

### 지금 문면

> - **Container creation through a socket proxy.** The proxy exposes container
>   create/start/stop/remove and refuses host bind mounts, `--privileged`, `--network=host`,
>   and `exec` into containers it did not create. …

### 제안 문면

> - **Container creation through a socket proxy.** The proxy exposes container
>   create/start/stop/remove. It **refuses, by enumeration**, any create whose body sets
>   `HostConfig.Binds`, `HostConfig.Mounts[].Type=bind`, `HostConfig.Privileged`,
>   `HostConfig.NetworkMode=host`, `HostConfig.PidMode=host`, `HostConfig.CapAdd`,
>   `HostConfig.Devices`, `HostConfig.UsernsMode=host`, or `HostConfig.SecurityOpt`.
>   It refuses `exec`, `PUT /archive`, and `GET /changes` against any container it did not
>   create, identified by the `kisia-rebuild=1` label. **Every other endpoint is refused by
>   default**; the allowed set is enumerated in `docs/rebuild/HOST_EXCEPTIONS.md` §2.1.a-3.
>   The product speaks only to the proxy and never to `/var/run/docker.sock`. …
>
>   **This enumeration will go stale, and that is accepted rather than mitigated away.**
>   A new escape spelling is a new refusal here, not a category. The standing guard is the
>   two-way test of `HOST_EXCEPTIONS.md` §2.1.c, which is **run as a regression, not once**:
>   an allow path, every refusal above, and a raw-socket `connect()` that must fail.

### 왜 부류가 아니라 열거인가 — 초안의 논거 그대로

부류(`"모든 탈출 가능 필드"`)로 적으면 **강제도 검사도 못 한다.** 이 저장소에 이미 그
자리가 하나 있다 — `allow_network_automation` 은 이름과 `false` 만 있고
(`HOST_EXCEPTIONS.md` §6.3.a) 무엇이 그것을 위반하는지 아무도 재지 못한다.
**부류는 같은 종류를 하나 더 만든다.**

그리고 §0 이 그 증거다 — **열거로 가려 하자마자 "여덟"이 아홉이라는 것이 드러났다.**

---

## 2. P-2 — 소켓 프록시와 워커 egress 를 제품 상시 자세로 (항목 3)

### 2.1 무엇을 canon 에 편입하고 무엇을 재빌드 한정으로 닫는가

**운영자가 갈라 달라고 한 그 선이다.**

| canon 에 편입 (상시) | 재빌드 한정으로 닫는다 |
|---|---|
| **컨테이너 생성은 소켓 프록시를 통해서만.** raw `/var/run/docker.sock` 은 영구히 범위 밖 | **넓은 빌드 egress** — 이미지 빌드를 위한 호스트측 패키지 설치(:231) |
| **워커 egress 강제** — `network=challenge` 는 매니페스트가 선언한 목적지를 요구한다 | **반복 빌드 권한** — 같은 항목 |
| 소유권 라벨(`kisia-rebuild=1`)에 의한 격리 | 자기 종료(`rebuild-close`) — **항목 6에서 승격하지 않기로 했다** |

### 2.2 대상과 제안 문면 — 새 절 하나

`docs/canon/SAFETY_SCOPE.md` 의 **`## Permissions` 뒤, `## Out of scope` 앞**에 넣는다.
시한부 예외 절이 **아니다** — 그것이 "상시"의 뜻이다.

> ## Container isolation (standing)
>
> This is the product's permanent posture, not a time-limited exception. It was measured
> before being written: the two-way test of `docs/rebuild/HOST_EXCEPTIONS.md` §2.1.c was
> exercised on 2026-08-09 with every allow path succeeding, every refusal above observed with
> its reason, and a raw-socket `connect()` failing with `EACCES`.
>
> - **The product creates containers only through the socket proxy.** The raw Docker socket
>   is out of scope for the product as it is for everything else. An account that must launch
>   workers is put in the proxy's group, never in `docker`.
> - **Worker egress is enforced at the container.** `network=challenge` requires a
>   manifest-declared target; a worker on an internal network reaches nothing else. **This is
>   no longer unexercised** — it was observed on 2026-08-09, which supersedes the sentence
>   under the product-rebuild exception that says the container-side restriction "has never
>   been exercised".
> - **A missing capability is reported and the work is blocked.** Isolation is not weakened to
>   supply it. This restates the `Out of scope` rule and is repeated here because this is the
>   section a product engineer reads.

### 2.3 그리고 낡은 문장 하나를 정정한다 — 관측 C

`SAFETY_SCOPE.md` :242–243 이 적는다:

> `network=challenge` still requires a manifest-declared target, and the container-side
> restriction **has never been exercised** …

**2026-08-09 에 행사됐다.** `--internal` 네트워크의 컨테이너 안에서 `1.1.1.1:80` 연결이
실패했고(부록 A §B), `HOST_EXCEPTIONS.md`:393 이 그보다 앞선 행사를 이미 담고 있었다.

**덮어쓰지 않고 P-2 의 새 절이 supersede 한다고 적는 쪽을 택했다** — `ADR-0001`
§Correction 이 세운 자세이고, 그 문장이 언제 참이었는지가 이력으로 남아야 한다.

### 2.4 반대 근거 — 초안이 이것을 권고하지 **않았다**. 접지 않는다

초안 §3 항목 3은 **미승격 + 시점 조건**을 권고했고 근거가 둘이었다:

1. **코드 0줄인 상태의 승격은 canon 이 존재하지 않는 제품의 자세를 규정하는 것이다.**
   `ADR-0003` 이 채택한 컴포넌트 일곱이 여전히 0줄이다(`O-42`). **이 반대는 여전히 유효
   하다** — P-2 는 프록시 위에 실제로 도는 제품이 없는 상태에서 그 제품의 자세를 적는다.
2. **승격은 만료(09-30 자동 실효)라는 장치를 자발적으로 버리는 것이다.** 시한부 예외는
   방치되면 스스로 닫히지만, 상시 절은 누가 지우기 전까지 남는다.

**운영자가 그것을 알고 승격을 골랐다.** 완화 둘을 제안에 넣는다 —
① P-2 가 **자세**만 적고 어떤 새 권한도 열지 않는다(§3), ② §2.1.c 양방향 시험을 **상시
회귀**로 걸어 문면이 관측 없이 참으로 남는 것을 막는다.

---

## 3. 무엇이 바뀌지 않는가

- **네 permission 전부 불변.** `allow_vps` 는 false 그대로. **이 문서는 아무것도 켜지
  않는다.**
- **`ctf-host-user` 계정의 예외와 만료(2026-09-30)는 그대로다.** P-2 는 시한부 예외를 지우지
  않는다 — 제품의 상시 자세를 그 옆에 세울 뿐이다.
- **`ccworker` 에게 아무 권한도 주지 않는다.** 컨테이너 생성은 여전히 `ctf-host-user` 뿐이다
  (`O-45`, `D-82`).
- **holdout·worker 격리·자동 제출 금지 불변.**
- **회수 체크리스트 불변** — `HOST_EXCEPTIONS.md` §4.

---

## 4. 서명

| # | 대상 | 승인자 | 날짜 | 적용 |
|---|---|---|---|---|
| **P-1** | `SAFETY_SCOPE.md` :200–204 — 거부 목록을 **열거**로. **"여덟"이 아니라 `HostConfig` 아홉 + 소유권 + 기본거부** | **dnhynk** | **2026-08-09** | **적용.** 그 항목을 열거로 다시 썼고 낡는다는 사실과 §2.1.c 상시 회귀를 함께 실었다 |
| **P-2** | `SAFETY_SCOPE.md` 에 `## Container isolation (standing)` 신설 + :242–243 supersede | **dnhynk** | **2026-08-09** | **적용.** `## Permissions` 뒤·`## Out of scope` 앞에 신설. **:242–243 은 지우지 않았다** — 새 절이 supersede 한다고 적고 옛 문장은 *"언제 참이었는지의 기록"* 으로 남긴다 |

**둘을 갈라 서명할 수 있었다.** 운영자는 **둘 다** 서명했다(2026-08-09).

**이것이 `docs/canon/` 의 열두 세션 만의 첫 변경이다.** 직전 canon 편집은 2026-08-08의
`CANON_EDITS_2026-08-08.md`(`9e5bb09`)였다.

---

## 5. 적용 뒤 — 기재 자리를 정정한다

**§4 초판이 *"`HOST_EXCEPTIONS.md` §5 표와 §4.2 체크리스트에 기재한다"* 고 적었는데
§5 는 틀린 자리다. 이 제안서 자신을 정정한다.**

`HOST_EXCEPTIONS.md` §5 의 머리 블록이 그것을 명시한다:

> **이 표는 예외, 즉 재빌드에게 권한을 *주는* 항목의 서명란이고, 조이는 변경은 아무
> 권한도 주지 않는다.** 그것을 여기 두면 **아무 권한도 요구하지 않는 항목이 권한 서명에
> 막히고**, 실제로 재빌드-3의 첫 일이 그렇게 교착했다. **확장의 비준 자리는 §4.2다.**

**P-1 은 조이는 변경이고 P-2 는 자세의 선언이다 — 둘 다 아무 권한도 주지 않는다.**
따라서 기재는 **§4.2 항목 3·4** 에만 한다. **§5 표는 건드리지 않았다.**

재빌드-2가 §2.1.a-3 확장을 §5에 한 행으로 넣었다가 뺐고, 그 때문에 재빌드-3의 첫 일이
교착했다. **같은 실수를 제안서가 반복할 뻔했다.**
