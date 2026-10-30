"""통제 블록 — `TELEMETRY_SCHEMA.md` §2, 값의 형식은 §2.1.

**이 블록만으로 run 을 재구성할 수 없으면 S9 FAIL 이고 그 attempt 의 결과는
폐기된다.** 그래서 조립기는 블록이 불완전하면 스트림을 열지 않고 죽는다 — 불완전한
블록으로 attempt 를 돌리면 그 run 의 비용만 쓰고 결과는 버려진다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

#: §2의 항목 전부. 순서는 문서의 순서다.
REQUIRED_FIELDS: tuple[str, ...] = (
    "runtime_id",
    "vendored_components",
    "structural_patches",
    "profile",
    "provider",
    "model_id",
    "model_snapshot",
    "endpoint",
    "requested_reasoning_effort",
    "effective_reasoning_effort",
    "tool_protocol",
    "state_mode",
    "store",
    "streaming",
    "capability_probe_id",
    "attempt_timeout_s",
    "tool_timeout_s",
    "session_timeout_s",
    "token_budget",
    "usd_budget",
    "bytes_shown_limit",
    "session_concurrency_limit",
    "session_kinds",
    "max_variable_len",
    "host_id",
    "image_digest",
    "network_policy",
    "challenge_id",
    "challenge_set",
    "challenge_manifest_sha256",
    #: 개정 S-4 (`CANON_EDIT_CALIBRATION_INTAKE.md` §4.1) — `synthetic` 또는
    #: `contest-derived`. S7·S8·S8.3 이 왜 침묵했는지를 기록에서 재구성하는 근거다.
    "provenance",
    "flag_format",
    "connectors",
    "min_grounded_segment_len",
    "max_segments",
    "probe_set_id",
    #: 개정 R5-2 / `spec.md` S9.4a — 검사기의 스트림 밖 고정 입력 둘 중 단가표 쪽
    #: 지목. 픽스처 쪽은 위의 `challenge_manifest_sha256` 이다.
    "pricing_sha256",
    #: 지표 회계 — `ADR-0003` §Consequences. "모든 Attempt 는 생성 시점에 clean /
    #: solve@k / contest 라벨이 붙어야 하고, holdout Attempt 는 clean 라벨만 허용한다."
    #: 셋 다 **기본값이 없다** — 이유는 `DEFAULTS` 말미의 주석이다.
    #: **셋 다 run 의 성질이고 attempt 의 성질이 아니다.** G-1 이 "ClaudeCode 가 참여한
    #: **run**" 을 세지 않는다고 적으므로, race 의 native attempt 도 자기 run 의
    #: 참여자를 전부 싣지 않으면 그 attempt 만 clean 으로 빠져나간다.
    "accounting_label",
    "solve_k",
    "run_participants",
)

#: 라벨의 값 집합 — `ADR-0003` §Consequences 가 세 갈래로 적은 그대로다.
#: **`clean` 은 모드이지 세트가 아니다.** `clean_solve@1` 로 세려면 이 라벨과
#: `challenge_set == "final-holdout"` 이 **함께** 참이어야 한다(`ADR-0003` §Decision-2:
#: "clean_solve@1 측정은 final-holdout 위에서 단일 코어로만 돈다"). 그래서 dev 나
#: calibration 위의 단일 코어 run 도 `clean` 라벨을 달 수 있고, 그것이 계기의 숫자로
#: 세어지지는 않는다 — 세트가 그것을 가른다(`HOLDOUT.md` §1.0.a).
ACCOUNTING_LABELS: frozenset[str] = frozenset({"clean", "solve@k", "contest"})

#: `run_participants[].kind` — 참여자의 **회계상 종류**. 구현 이름이 아니라
#: `EVAL_CONTRACT.md` 가 가르는 세 갈래다(단일 모델 / 둘째 모델 / escalation).
#: **G-1 을 이름이 아니라 이 종류로 판정한다** — 열린 이름 집합에 문자열 대조를 걸면
#: `ClaudeCodeWorker` 를 다르게 부른 run 이 조용히 clean 으로 빠져나간다. 구현 이름은
#: `run_participants[].id` 가 따로 나르고, §2 의 "이 블록만으로 run 을 재구성한다" 가
#: 그 id 를 요구한다.
PARTICIPANT_KINDS: frozenset[str] = frozenset({"native_core", "second_core", "external_model"})

#: 계약이 값을 정하지 않았다고 **선언한** 것들(`spec.md` §8.2 말미). 값은 자유이되
#: 선언과 결정론은 필수다. 그래서 기본값을 두되 `None` 을 허용하지 않는다.
DEFAULTS: dict[str, Any] = {
    "connectors": ["_", "-", ":", "."],
    "min_grounded_segment_len": 4,
    "max_segments": 8,
    "max_variable_len": 128,
    "challenge_set": "dev",
    #: 개정 S-4 가 정한 기본값. **기본값은 발행 시점에 조립기가 넣는다** — 검사기가
    #: 넣지 않는다. 그 자세를 `challenge_set` 이 이미 세웠고 여기서도 같다.
    #: 검사기 쪽 목록(`predicates.CONTROL_FIELDS`)에도 있고, 두 목록은 같아야 한다 —
    #: `kisia_tests/test_pinned_inputs.py` 가 그것을 잠근다.
    "provenance": "synthetic",
    "structural_patches": [],
    "vendored_components": [],
    "session_kinds": [],
    #: `null` 은 "상한 없음"이고 §4.2의 '명시적'을 만족한다. 미선언과는 다르다.
    "session_concurrency_limit": None,
    #: 무엇이 비밀인지는 조립기가 추측하지 않는다 — 선언에서만 온다 (§3.2.1).
    "secret_refs": [],
    #: 검색 도구를 노출하지 않는 것과 검색을 하지 않은 것은 다른 사실이다 (§3.2.1).
    "search_tool_exposed": False,
    #: **`accounting_label`·`solve_k`·`run_participants` 에는 기본값을 두지 않는다.**
    #: `build()` 가 `dict(DEFAULTS)` 를 먼저 병합하므로 기본값을 주면 새 블록이 그 값을
    #: 자동으로 얻는다. `clean` 을 기본값으로 주면 오염된 run 이 조용히 계기의 숫자로
    #: 세어지고, 그것이 `ADR-0003` §Consequences 가 막으려는 해악 그 자체다. `contest`
    #: 를 기본값으로 줘도 나은 것이 아니다 — 선언하지 않은 run 이 목표 지표에 조용히
    #: 섞이고, **미선언과 어떤 값도 접지 않는다**(`TELEMETRY_SCHEMA.md` §7.1). 선언이
    #: 없으면 스트림을 열지 않는 것이 §2 의 자세이고, 이 모듈 머리말이 그것이다.
}

#: `null` 이 유효한 값인 필드. 나머지는 `None` 이면 미선언으로 본다.
NULLABLE: frozenset[str] = frozenset({"session_concurrency_limit"})


class ControlBlockError(ValueError):
    """통제 블록이 불완전하거나 형식이 어긋난다."""


@dataclass
class ControlBlock:
    values: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(cls, values: dict[str, Any]) -> ControlBlock:
        merged = dict(DEFAULTS)
        merged.update(values)
        block = cls(merged)
        block.validate()
        return block

    def validate(self) -> None:
        missing = [
            f
            for f in REQUIRED_FIELDS
            if f not in self.values or (self.values[f] is None and f not in NULLABLE)
        ]
        if missing:
            raise ControlBlockError(
                "통제 블록에 " + " ".join(missing) + " 가 없다. "
                "하나라도 빠지면 S9 FAIL 이고 그 attempt 는 폐기된다 (TELEMETRY_SCHEMA §2)."
            )
        for name, check in (
            ("bytes_shown_limit", _positive_int),
            ("min_grounded_segment_len", _positive_int),
            ("max_segments", _positive_int),
            ("max_variable_len", _positive_int),
        ):
            if not check(self.values[name]):
                raise ControlBlockError(f"{name} 은 양의 정수여야 한다: {self.values[name]!r}")
        limit = self.values["session_concurrency_limit"]
        if limit is not None and not _positive_int(limit):
            raise ControlBlockError(
                "session_concurrency_limit 은 양의 정수 또는 null(상한 없음)이다 "
                f"(§2.1): {limit!r}"
            )
        if not isinstance(self.values["connectors"], list):
            raise ControlBlockError("connectors 는 길이 1 문자의 리스트다")
        bad = [c for c in self.values["connectors"] if not isinstance(c, str) or len(c) != 1]
        if bad:
            raise ControlBlockError(f"connectors 에 길이 1이 아닌 항목: {bad!r}")
        if self.values["flag_format"].count("...") != 1:
            raise ControlBlockError(
                f"flag_format 에 구멍(...)이 정확히 하나가 아니다: {self.values['flag_format']!r}"
            )
        _check_accounting(self.values)

    @property
    def secret_refs(self) -> list[str]:
        raw = self.values.get("secret_refs")
        return [str(x) for x in raw] if isinstance(raw, list) else []

    def as_event_fields(self) -> dict[str, Any]:
        return dict(self.values)


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _check_accounting(values: dict[str, Any]) -> None:
    """지표 회계 라벨과 그 모순 — `ADR-0003` §Decision-2 (G-1) · §Consequences.

    **강제하는 자리가 검사기가 아니라 조립기인 이유.** 라벨은 통제 블록 필드이지
    계약 술어가 아니다(`TELEMETRY_SCHEMA.md` §2). 그리고 ADR 이 "생성 시점에 붙인다"
    고 적은 것은 회계가 사후에 고쳐질 수 없어야 하기 때문이다 — 스트림이 난 뒤에
    라벨을 바꾸면 이미 난 숫자를 되돌릴 수 없다. 그래서 모순은 **스트림을 열기 전에**
    죽는다.
    """
    label = values["accounting_label"]
    if label not in ACCOUNTING_LABELS:
        raise ControlBlockError(
            f"accounting_label 은 {sorted(ACCOUNTING_LABELS)} 중 하나다 (`ADR-0003` "
            f"§Consequences): {label!r}"
        )
    if not _positive_int(values["solve_k"]):
        raise ControlBlockError(f"solve_k 는 양의 정수여야 한다: {values['solve_k']!r}")

    participants = values["run_participants"]
    if not isinstance(participants, list) or not participants:
        raise ControlBlockError(
            "run_participants 는 비어 있지 않은 목록이다 — 참여자가 없는 run 은 없고, "
            f"빈 목록은 G-1 을 공허하게 만든다: {participants!r}"
        )
    kinds: list[str] = []
    for p in participants:
        if not isinstance(p, dict):
            raise ControlBlockError(f"run_participants 의 항목은 {{id, kind}} 다: {p!r}")
        pid = p.get("id")
        if not isinstance(pid, str) or not pid:
            raise ControlBlockError(f"run_participants[].id 는 비어 있지 않은 문자열이다: {p!r}")
        kind = p.get("kind")
        if kind not in PARTICIPANT_KINDS:
            raise ControlBlockError(
                f"run_participants[].kind 는 {sorted(PARTICIPANT_KINDS)} 중 하나다: {p!r}"
            )
        kinds.append(str(kind))

    if label == "clean":
        # G-1 — `ADR-0003` §Decision-2. ClaudeCode 가 참여한 run 은 `clean_solve@1` 로
        # 세지 않는다. **이름이 아니라 선언된 종류로 판정한다** (PARTICIPANT_KINDS 주석).
        foreign = sorted({k for k in kinds if k != "native_core"})
        if foreign:
            raise ControlBlockError(
                f"accounting_label=clean 인데 run 참여자에 {foreign} 가 있다. "
                "`clean_solve@1` 은 정의상 단일 모델이다 (`EVAL_CONTRACT.md`, "
                "`ADR-0003` §Decision-2 G-1)"
            )
        if len(participants) > 1:
            raise ControlBlockError(
                f"accounting_label=clean 인데 run 참여자가 {len(participants)} 이다. "
                "race 는 `solve@k` 이지 clean 이 아니다 (`ADR-0003` §Decision-2)"
            )
        if values["solve_k"] != 1:
            raise ControlBlockError(
                f"accounting_label=clean 인데 solve_k={values['solve_k']} 이다. "
                "`clean_solve@1` 은 1시도·무재시도다 (`EVAL_CONTRACT.md` Reporting unit)"
            )
    if "external_model" in kinds and label != "contest":
        raise ControlBlockError(
            f"run 참여자에 external_model 이 있는데 accounting_label={label!r} 이다. "
            "escalation 을 쓴 run 은 `contest_solve` 로 센다 (`EVAL_CONTRACT.md`)"
        )
    if values["challenge_set"] == "final-holdout" and label != "clean":
        raise ControlBlockError(
            f"challenge_set=final-holdout 인데 accounting_label={label!r} 이다. "
            "holdout Attempt 는 clean 라벨만 허용한다 (`ADR-0003` §Consequences). "
            "holdout 은 한 번 열면 세트째 내려가므로(`HOLDOUT.md` §1.1) 그 한 번을 "
            "race 로 쓰면 계기의 유일한 측정이 버려진다"
        )


def probe_set_id(probe_ids: list[str]) -> str:
    """켜진 프로브 집합의 식별자 — `TELEMETRY_SCHEMA.md` §2.1.

    정렬해 콤마로 이은 문자열의 sha256 앞 12자. 프로브 하나를 더하거나 빼면 다른
    id 다. 동치 규칙이 없으면 `spec.md` §6.4의 "다르면 섞지 않는다"를 기계적으로
    판정할 수 없다.
    """
    joined = ",".join(sorted(set(probe_ids)))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]
