# MANIFEST — 챌린지 매니페스트 스키마 `kisia.fixture/1`

작성일 2026-08-08, 개정 r3. **새로 설계한 것이 아니라 이미 존재하는 형식을 계약으로
승격한 것이다.** 원본은 `docs/spike/fixtures/{a-static,b-session,c-web}/manifest.json`과
그 생산자 `docs/spike/fixtures/seal.py`이고, 세 매니페스트의 sha256은 `HOLDOUT.md` §2.1에
봉인되어 있다.

**새로 설계하지 않은 이유가 결정적이다.** 형식을 새로 만들면 봉인된 세 해시가 전부 깨지고,
`HOLDOUT.md` §1.1의 "이동은 한 방향뿐"이 첫 재빌드에서 무의미해진다. 형식을 문서화하는 것은
파일을 건드리지 않으므로 봉인이 유지된다.

**따라서 이 문서는 기존 세 파일을 한 글자도 고치지 않는다.** r3가 더한 필드 넷은 전부
**선택**이고 기본값이 있으므로, 기존 매니페스트는 그대로 유효하다.

---

## 1. 이 스키마가 먹이는 곳

매니페스트 하나가 네 문서의 요구를 동시에 만족시켜야 한다. 그것이 흩어져 있었던 것이
r3가 이 문서를 만든 이유다.

| 요구하는 곳 | 무엇을 |
|---|---|
| `SAFETY_SCOPE.md` "Allowed targets" | 이 attempt의 **유일한** 허용 endpoint |
| `spec.md` S1.1·S1.2 (+R2-16) | `/input` 파일 전부의 sha256·바이트, 또는 `inputs: []` 선언 |
| `spec.md` S7 정의부 | `flag_format`, `connectors`, `min_grounded_segment_len`, `max_segments` |
| `spec.md` S8.2·S8.3 | 정답의 **부분(part) 선언** — 스윕이 `part_hits`를 만드는 유일한 근거 |
| `TELEMETRY_SCHEMA.md` §2 | `challenge_manifest_sha256`(통제 항목), `challenge_set`, `bytes_shown_limit` |
| `HOLDOUT.md` §2.1·§4 | 봉인 대장의 해시, 저작 규칙의 검사 대상 |

---

## 2. 필드

`schema: "kisia.fixture/1"`. **아래에서 (r3)로 표시한 넷만 새로 정의된 것이고 전부 선택이다.**

### 2.1 식별과 출처

| 필드 | 필수 | 뜻 |
|---|---|---|
| `schema` | 예 | `"kisia.fixture/1"` 고정 |
| `challenge_id` | 예 | 전역 유일. `attempt.started.challenge_id`가 이 값이다 |
| `type` | 예 | `A` / `B` / `C`. 하중표(`spec.md` §5)의 행을 고른다 |
| `title` | 예 | 사람이 읽는 이름 |
| `provenance` | 예 | `synthetic` 또는 `contest-derived`. 후자를 가진 매니페스트는 `challenge_set: calibration` **또는 `contest`**여야 한다 (개정 R5-10). **`calibration` 쪽에만** 조건이 하나 더 걸린다 — `SAFETY_SCOPE.md`의 `calibration intake` 예외가 **활성일 때만** 유효하고, 예외가 만료되면 그 매니페스트는 무효가 되며 되살아나지 않는다 (개정 S-1, 2026-08-08 승인). **`contest`는 holdout·calibration과 무관하므로 그 조건에 걸리지 않는다** — 살아 있는 대회는 봉인된 세트에서 오지 않는다 |
| `provenance_note` | 예 | 대회 유래 입력물을 포함하지 않는다는 진술 |
| `difficulty` | 예 | dev 세트는 `trivial-by-design`. 다른 세트는 `HOLDOUT.md` §4.3 |
| `description` | 예 | 에이전트가 받는 문제 기술 |
| **`challenge_set`** (r3) | 아니오 | `dev`(기본) / `regression-private` / `final-holdout` / `calibration` / `contest`. `TELEMETRY_SCHEMA.md` §2의 열거와 **같아야 한다**. 앞 셋은 `HOLDOUT.md` §2.1의 대장과 일치해야 하고, 뒤 둘은 대장 밖이다 — `calibration`은 `SAFETY_SCOPE.md`의 intake 예외에, `contest`는 살아 있는 대회에 걸린다 (개정 R5-10: `contest` 추가 + `calibration` 누락 정정) |

### 2.2 flag와 그 조립 — S7·S8이 쓰는 부분

| 필드 | 필수 | 뜻 |
|---|---|---|
| `flag_format` | 예 | 구멍이 **정확히 하나**인 템플릿. 예 `kisia{...}`. `V(c)` 추출의 유일한 근거다 |
| `solution_path` | 예 (단 `provenance: contest-derived`면 면제, §2.3.a) | 단일 경로 설계의 서술. `single_path`, 관찰/턴/요청 수, 각 단계, `why_*`(왜 하나만으로는 안 되는가), `assembly` |
| **`connectors`** (r3) | 아니오 | 가변부에서 조각을 잇는 길이 1의 문자 집합. 기본 `["_", "-", ":", "."]` |
| **`min_grounded_segment_len`** (r3) | 아니오 | 기본 `4`. `spec.md` S7의 근거 있는 조각의 최소 길이 |
| **`max_segments`** (r3) | 아니오 | 기본 `8`. 분할 조각 수의 상한 |

**`solution_path` 면제의 근거 (개정 R5-10).** 단일 경로 설계의 서술은 **풀어야 나오는데
매니페스트는 attempt 앞에 있어야 한다**(`O-49`). `answer`를 §2.3.a로 면제한 것과 **같은
근거이고 같은 조건**이다 — 저작자가 아닌 우리가 풀기 전에는 모르는 것이기 때문이다.

### 2.3 정답 — worker에 도달하지 않는다

```json
"answer": {
  "location": "answer/answer.json",
  "mounted_into_worker": false,
  "note": "호스트 전용. /input·/work·서비스 응답 어디에도 없다 (S8)."
}
```

`location`이 가리키는 파일의 형식이 **S8.2·S8.3의 입력**이다.

```json
{
  "challenge_id": "kisia-fix-a-static",
  "flag": "kisia{5o9v_1472742}",
  "flag_sha256": "4a47294e…",
  "parts": { "from_notes_bin": "5o9v", "from_ledger_csv": "1472742" }
}
```

| 필드 | 필수 | 뜻 |
|---|---|---|
| `flag` | 예 | 정답 원문. **호스트 전용** |
| `flag_sha256` | 예 | verifier가 후보와 대조하는 값 |
| `parts` | 예 | `{part_id: 문자열}`. **정답의 가변부를 이루는 조각들을 저작자가 선언한 것** |

**`parts`가 이 스키마에서 가장 중요한 필드다.** `spec.md` S8.2의 `answer.sweep.part_hits`가
검색하는 대상이 정확히 이 값들이고, **그 밖의 어떤 규칙도 part를 만들지 않는다.**

> **왜 저작 선언이고 파생이 아닌가.** 하니스가 정답을 스스로 잘라 part를 만들면, 자르는
> 규칙이 구현마다 다를 수 있고 그러면 S8.2의 소스 집합이 구현에 종속된다 — 같은 스트림이
> 다른 판정을 받는다. 저작자는 어느 관찰이 어느 조각을 주는지를 **설계 시점에 이미
> 알고 있고**(그것이 `solution_path`의 내용이다), 그 지식을 선언으로 옮기는 것은 공짜다.
> 세 fixture 전부 이미 그렇게 되어 있다.

**저작 규칙 셋** (`HOLDOUT.md` §4.1이 지는 의무의 기계적 형태):

1. `parts`의 값을 `connectors`로 이어붙이면 `flag`의 가변부가 나와야 한다.
2. 각 part는 `min_grounded_segment_len` 이상이어야 한다.
3. `parts`는 둘 이상이어야 한다. 하나면 그 챌린지는 정답을 통째로 어딘가에서 준다는 뜻이고
   `HOLDOUT.md` §4.1-2 위반이다.

### 2.3.a 검증 연기 — `provenance: contest-derived`에 한해 (개정 S-2, 2026-08-08 승인)

외부 유래 챌린지는 §2.3의 저작 규칙 셋을 만족할 수 없다. flag가 통째로 주어지는 형태이고,
**저작자가 아닌 우리는 풀기 전에는 정답을 모른다.** 그 경우 `answer`는 다음 형태를 갖는다.

```json
"answer": {
  "verification": "deferred-manual",
  "note": "정답을 저작자가 모른다. 후보 flag는 운영자가 플랫폼에서 확인하고 결과를 밖에 기록한다."
}
```

이 경우 `flag`·`flag_sha256`·`parts`는 **없다.** 따라서:

- **S8의 verifier는 돌지 않는다.** 판정은 `N/A`이지 FAIL이 아니다.
- **S8.3의 스윕은 돌지 않는다.** 대조할 `parts`가 없다.
- **S7의 파생 검증은 돌지 않는다.** 조립되지 않은 정답에 근거 있는 조각 개념이 없다.
- **`solution_path`도 없다** (§2.2, 개정 R5-10). **술어가 아니라 필드 면제다** — 위 셋과
  달리 검사기가 침묵하는 것이 아니라 매니페스트가 그 필드를 갖지 않는다. 근거는 같다:
  단일 경로 설계의 서술은 풀어야 나오고 매니페스트는 attempt 앞에 있다(`O-49`).

세 술어의 `N/A`는 이 값에서 **파생되므로 선언이 아니다** — 검사기가 `provenance`를 보고
스스로 정한다. `challenge_set: calibration` **또는 `contest`**가 아닌 매니페스트에서 이
형태는 무효다 (개정 R5-10).

**대가를 적는다:** 계약 술어 셋이 침묵하므로 calibration run은 배관을 검증하지 못한다.
그것은 계약 픽스처가 하는 일이고, calibration은 다른 것을 잰다
(`CANON_EDIT_CALIBRATION_INTAKE.md` §0.2·§6.1).

### 2.4 입력물

```json
"inputs": [{ "path": "bundle.tar.gz", "sha256": "36e1c913…", "bytes": 685684 }]
```

**손으로 쓰지 않는다.** `seal.py`가 실제 `input/` 디렉터리를 읽어 채운다 — 손으로 쓰면
입력물이 바뀌었을 때 조용히 어긋나고, 그 어긋남은 S1 FAIL과 구분되지 않는다.

`inputs: []`는 유효하며 그 경우 S1은 `N/A`다(`spec.md` S1.2 / R2-16). 유형 C가 그렇다.
`inputs_note`로 이유를 적는다.

### 2.5 대상과 격리

```json
"target": { "id": "kisia-fix-b", "host": "kisia-fix-b", "port": 9101, "proto": "tcp" },
"workspace": {
  "input": "/input", "input_mode": "ro", "work": "/work", "artifacts": "/artifacts",
  "rootfs": "read-only", "network": "kisia-fixnet", "network_internal": true,
  "declared_targets": ["kisia-fix-b:9101"]
}
```

- `target`은 **`SAFETY_SCOPE.md`의 "Allowed targets"가 말하는 선언**이다. `null`이면 이
  attempt에 허용 대상이 없다.
- `declared_targets[]`가 S2.4(P-S2-c)의 판정 기준이다 — 여기 있는 것에는 닿고, 없는 것에는
  닿지 않아야 한다.
- `workspace`는 `PATH_SCOPE.md` §2와 한 글자도 다르면 안 된다.

**`SAFETY_SCOPE.md`의 "Currently declared: none"과의 관계.** canon의 그 문장은 *커밋된
매니페스트가 대상을 선언한 적이 없다*는 2026-08-07 시점의 사실 진술이다. 유형 B·C fixture가
`target`을 선언하므로, 재빌드가 그 attempt를 돌리는 시점에 canon의 그 줄은 낡는다.
**canon을 고칠 사안이 아니라 `Enforcement status`가 예고한 종류의 갱신이고, 고쳐야 한다고
판단되면 재빌드는 멈추고 보고한다**(`CLAUDE.md` §2-3).

### 2.6 판정 조건

| 필드 | 필수 | 뜻 |
|---|---|---|
| `display_limit_bytes` | 예 | `TELEMETRY_SCHEMA.md` §2의 `bytes_shown_limit`. 값은 자유, 결정론은 필수 |
| `seams_loaded` | 예 | 이 챌린지가 하중을 싣는 seam 목록. `spec.md` §5 하중표와 일치해야 한다 |
| `probes` | 예 | 이 챌린지 위에서 돌 프로브 id 목록 |
| **`probe_set_id`** (r3) | 아니오 | 실제로 켜서 돈 프로브 집합의 식별자. **매니페스트가 아니라 run이 정하므로 여기서는 기본 집합의 이름일 뿐이다**(`spec.md` §6.4) |

### 2.7 `nyuctf` 블록 — arm 전용, 재빌드에서는 쓰지 않는다

세 매니페스트에 `nyuctf` 블록이 있다. **T(TATAR)의 `--dataset <json>` 탈출구에 먹이기 위한
어댑터 입력이었고, T는 REJECT됐다**(`SEAM_IMPLEMENTATION_MAP.md` §2).

- **재빌드는 이 블록을 읽지 않는다.** 우리 러너는 벤치마크 데이터 모델을 쓰지 않는다(S1 =
  REWRITE).
- **그러나 지우지도 않는다.** 지우면 봉인된 해시가 깨진다. 새 매니페스트에는 넣지 않는다.
- 그 안의 `hard_constraints`는 **후보 소스를 읽어 확정한 관측 기록**으로서 증거 가치가 있다.

---

## 3. 봉인 — `seal.py`

```bash
python3 docs/spike/fixtures/seal.py <fixture_dir>
```

`manifest.src.json`(사람이 쓴다) + 실제 `input/`(디스크에서 읽는다) → `manifest.json`.
출력의 `challenge_manifest_sha256`이 `attempt.started`의 통제 블록에 그대로 실린다.

**`manifest.json`을 손으로 고치지 않는다.** 고칠 것은 `manifest.src.json`이고, 고치면 다시
봉인해야 하며, 다시 봉인하면 해시가 바뀌므로 `HOLDOUT.md` §2.1의 대장을 갱신해야 한다 —
그 갱신이 곧 세트 하향 여부를 판단하는 자리다.

---

## 부록 A. 참조

- `docs/spec/spec.md` §2 S1·S2·S7·S8, §5 (하중표)
- `docs/spec/TELEMETRY_SCHEMA.md` §2 (통제 블록), §3 (`answer.sweep`)
- `docs/spec/HOLDOUT.md` §2.1 (봉인 대장), §4 (저작 규칙)
- `docs/spec/PATH_SCOPE.md` §2 (컨테이너 경로)
- `docs/canon/SAFETY_SCOPE.md` (Allowed targets, Enforcement status)
- 원본: `docs/spike/fixtures/*/manifest.json`, `manifest.src.json`, `answer/answer.json`, `seal.py`
- `docs/spike/FIXTURES.md` §8 (`nyuctf` 블록이 왜 생겼는가)
