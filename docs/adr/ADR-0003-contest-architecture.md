# ADR-0003 — 대회 제품 아키텍처를 확정하고 clean_solve@1 계기 위에 얹는다

## Status

**Accepted (2026-08-08). 로드맵 브레인스토밍 세션. 운영자 결정.**

운영자가 제품 아키텍처를 **최종 결정본**으로 제시했고
(`docs/rebuild/CONTEST_ARCHITECTURE.md`에 원문 보존), 이 문서가 그것을 로드맵에
고정한다. 앞 로드맵 세션이 운영자 아키텍처 제안 없이 정한 잠정 결정 여섯
(`REBUILD_LOG.md` 로드맵 절 §2·§4)을, 이 세션이 그 제안 위에서 다시 판정한다.

**결정의 실질: 브리핑은 프로젝트 목표를 바꾸지 않는다.** `EVAL_CONTRACT.md`가
`contest_solve`를 **"the goal"**(:52)로, `clean_solve@1`을 계기(:46)로 이미 갈라 두었고,
브리핑은 그 `contest_solve` 층의 구체적 형태다. `SEAM_IMPLEMENTATION_MAP.md` §6:341–346이
같은 두-지표 구조를 spec 쪽에서도 재진술한다. 따라서 이것은 canon 편집이 아니라 canon이
이미 연 자리를 채우는 결정이다. **canon·계약 문서는 이 세션에서 고치지 않았다.**

## Context

브리핑은 재빌드가 지금까지 만든 것(자율 코어 + 계약 = `clean_solve@1` 계기)의 **위에**
얹히는 대회 배치층이다. canon이 두 지표를 못박아 두 층을 서로의 숫자에서 격리한다:

- `clean_solve@1` — 계기. 1시도·무재시도·무개입·**단일 모델·escalation 없음**·미공개 챌린지.
  `OBJECTIVE.md` 1순위.
- `contest_solve` — 목표. escalation 층 포함. **둘째 지표는 첫째를 대체하지 않는다**
  (`EVAL_CONTRACT.md` :56).

브리핑 세 worker의 canon 자리:

| 브리핑 컴포넌트 | canon 자리 |
|---|---|
| NativeHarnessWorker | 자율 코어 (`clean_solve@1` 측정 대상) |
| ClaudeCodeWorker (도구를 직접 돌리는 둘째 코어) | canon에 **아키텍처** 자리 없음 — 지표 어휘로는 `solve@k` |
| ManualEscalationWorker → 외부 모델 | escalation 층 (`SAFETY_SCOPE.md` "Escalation egress", 6조건) |

## Decision

1. **대회 제품 아키텍처를 채택한다.** 컴포넌트 경계는 브리핑 §16-B대로: orchestrator ·
   solver(들) · evidence store · verifier · scheduler · escalation exporter · 운영 UI.
   solver는 공통 계약 하나를 만족하는 교체 가능한 실행자이고, 인증/provider는 그 계약에
   들어가지 않는다(Credential Provider 뒤).

2. **G-1 — ClaudeCodeWorker는 도구를 직접 돌리는 둘째 코어다.** 귀결은 회계 규칙 하나:
   ClaudeCode가 참여한 run(race 또는 escalation)은 `solve@k`/`contest_solve`로 세고
   `clean_solve@1`로는 세지 않는다 — `clean_solve@1`은 정의상 단일 모델·1시도다
   (`EVAL_CONTRACT.md` :39, :46). **`clean_solve@1` 측정은 final-holdout 위에서 단일
   코어로만 돈다. race는 contest_solve 모드다** — holdout은 측정 이벤트에서 한 번 열면
   세트째 regression-private으로 내려가므로(`HOLDOUT.md` §1.1·§3), 그 한 번을 race로
   쓰면 계기의 유일한 측정이 solve@k가 되어 버려진다.

3. **G-3 — escalation 패킷은 telemetry-only다.** 넘어가는 것은 재현 절차·관측·가설·상태의
   투영이고, raw 챌린지 바이너리·캡처·입력파일은 넘어가지 않는다(`SAFETY_SCOPE.md` :87,
   `SEAM_IMPLEMENTATION_MAP.md` §6:339). 이 해석에서 canon 편집은 불필요하고, 수동 ChatGPT
   경로라도 6조건(단일 경로·컴파일·비밀제거·목적지 named·기록·코어 하류)을 전부 만족해야
   한다.

4. **로드맵 배치 — 대회 층은 계기 완성 후다.** `SEAM_IMPLEMENTATION_MAP.md` §6이 라이트업
   생성기를 "자율 코어와 함께"(재빌드-7), escalation 패킷 컴파일러를 "재빌드 이후"로 이미
   두었고, 이 결정이 그것을 확인한다(§3-D 유지). 재빌드-6(유형 C seam)·재빌드-7(통합 +
   Responses transport)의 순서는 이 결정이 바꾸지 않는다(§3-A 유지).

5. **N_open의 위상은 계약이 이미 정했고 이 결정이 바꾸지 않는다.**
   `SEAM_IMPLEMENTATION_MAP.md` §7.0이 N_open을 **완료 기준이 아니라 보고 항목**으로
   두었고(§7.0 말미, §4-3), 통합이 실패한 채 재빌드가 끝날 수 있으며 그 실패는 성능
   단계의 첫 과제가 된다. 이것을 완료 기준으로 바꾸는 것은 계약 편집이고 §2-1이다 —
   하지 않는다. **브리핑이 더하는 것은 위상이 아니라 그 보고값의 무게다:** 대회 제품
   전체가 "코어가 실제로 세션을 열고 도구를 쓴다"에 얹혀 있으므로, 재빌드-7이 §7.0대로
   N_open을 보고할 때 그 값을 **제품 명제의 첫 증거**로 읽는다. N_open=0이면 완료를
   막지 않고 성능 단계의 첫 과제로 명시 인계한다 — §7.0이 이미 그렇게 적는다.

## 이 문서가 정하지 않고 열어 둔 것

앞 세션의 실패는 묻지 않은 것을 정한 것이다. 다음은 **정하지 않는다**:

- **스케줄링 기본값.** 리뷰 권고는 Native-first 순차 + race 옵트인(quota·$300 account-wide
  잔고·one-shot·동시성 규칙 때문에 race-by-default 반대)이지만, 확정은 calibration
  데이터가 있어야 한다. 능력 계층이 없어 카테고리 라우팅은 지금 측정 불가다
  (`EVAL_CONTRACT.md` :96, `CALIBRATION_PROTOCOL.md` §1.4).
- **MVP 경계와 head-start T(G-2).** 측정 후 정한다.
- **escalation 이벤트 타입 계약 공백.** 봉투에 INFERRED/REJECTED·stall 신호가 없다
  (`SEAM_IMPLEMENTATION_MAP.md` §6:339의 "§5의 예약 이벤트", `SESSIONS.md` :404–414).
  escalation 컴파일러의 하드 전제이고, 닫는 것은 운영자 계약 편집이다 — 이 세션이
  정할 수 없다. `OBSERVATION_LEDGER.md` O-22가 지목한다.

## Consequences

- **지표 회계가 제품의 1급 관심이 된다.** 모든 Attempt는 생성 시점에 clean/solve@k/
  contest 라벨이 붙어야 하고, holdout Attempt는 clean 라벨만 허용한다. 이것 없이는
  "우리 시스템이 낫다"가 오염된 숫자 위에 선다.
- **둘째 코어는 격리·회계·자원을 하나 더 요구한다.** 공유 $300 잔고는 account-wide라
  소진되면 전부 멈춘다(`SAFETY_SCOPE.md` :219). ClaudeCode 구독은 별 quota다.
- **가설 9에 자리가 생겼다.** process-tree kill 요구(브리핑 §10)에 따라, 실행 층이
  생기면 cgroup 계수를 판정이 아닌 병렬 관측으로 싣는다(§3-C 정련, `reuse/S4.md` §2의
  R2-12 자세).
- **능력 계층은 여전히 아무것도 재지 않는다**(ADR-0002 Consequences 마지막 줄과 같은
  사실). 브리핑의 라우팅 야심이 이 층에 걸리고, calibration이 그것을 볼 유일한 계기다 —
  다만 calibration figure는 귀속 불가다(`EVAL_CONTRACT.md` :96).

## References

- `docs/rebuild/CONTEST_ARCHITECTURE.md` — 운영자 아키텍처 결정본 (브리핑 원문 보존)
- `docs/canon/OBJECTIVE.md` (우선순위), `EVAL_CONTRACT.md` (:39, :46–59, :96),
  `SAFETY_SCOPE.md` ("Escalation egress" :82–99, :108, :219)
- `docs/spec/SEAM_IMPLEMENTATION_MAP.md` §6, §7.0
- `docs/spec/HOLDOUT.md` §1.1, §3
- `docs/rebuild/REBUILD_LOG.md` 로드맵 절 §2·§2.1·§4, 그리고 로드맵 브레인스토밍 절
- `docs/rebuild/OBSERVATION_LEDGER.md` O-22, `SESSION_BOUNDARIES.md`
- `docs/spike/SESSIONS.md` :404–414 (escalation 이벤트 타입 예약)
