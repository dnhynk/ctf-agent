"""봉투 조립기 — 이벤트를 스트림에 쓰는 **단일 지점**.

`TELEMETRY_SCHEMA.md` §7의 최소 의무를 구조로 강제한다.

1. `seq` 는 여기서만 매긴다. 동시 세션의 이벤트도 이 지점을 통과하므로 `seq` 는
   **쓰기 순서**이지 발생 순서가 아니다(§3.2.1). 발생 순서는 `ts` 가 나른다.
2. **필드 이름이 겹치면 조용히 덮어쓰지 않고 죽는다** (§7.1). 이것이 스파이크에서
   가장 비쌌던 결함이고, `emit` 이 `**kwargs` 를 받지 않는 이유다.
3. 통제 블록이 불완전하면 스트림을 열지 않는다.
4. redaction sentinel 은 통제 블록의 `secret_refs[]` 에 등재된 이름에서만 온다.
   무엇이 비밀인지 조립기가 추측하지 않는다.
5. **한 attempt 안에서 모델 호출은 직렬이다.** 두 번째 `model.requested` 가 짝을
   기다리지 않고 들어오면 죽는다. 이 결정의 근거는 `docs/rebuild/REBUILD_LOG.md`
   의 설계 결정 3번이다 — 봉투가 `model.*` 에 `op_id` 를 주지 않으므로, 직렬을
   구조로 보장해야 S9.3의 짝짓기가 성립한다.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from kisia.runtime.telemetry.control import ControlBlock

#: 이벤트 봉투의 공통 필드 (`TELEMETRY_SCHEMA.md` §1). 이벤트 본문이 이 이름을
#: 쓰면 겹침이고, 겹침은 죽는다.
ENVELOPE_KEYS: frozenset[str] = frozenset({"ts", "run_id", "attempt_id", "seq", "type"})

#: §3의 이벤트 목록. 계약에 없는 이벤트 타입을 임의로 더하지 않는다
#: (`CLAUDE.md` §8). 필요하면 멈추고 보고한다.
EVENT_TYPES: frozenset[str] = frozenset(
    {
        "attempt.started",
        "attempt.finished",
        "input.bound",
        "workspace.created",
        "workspace.destroyed",
        "model.requested",
        "model.completed",
        "model.failed",
        "tool.requested",
        "tool.completed",
        "observation.recorded",
        "artifact.produced",
        "session.opened",
        "session.io",
        "session.closed",
        "http.exchanged",
        "state.snapshot",
        "candidate.produced",
        "candidate.provenance",
        "verification.completed",
        "answer.sweep",
        "scope.refused",
        "search.performed",
        # §5 예약. 어떤 술어에도 등장하지 않는다 (R2-15).
        "hypothesis.recorded",
        "hypothesis.rejected",
        "stall.observed",
    }
)

#: `attempt.finished` 뒤에 올 수 있는 것. 컨테이너 정리는 정의상 attempt 가 끝난 뒤에
#: 일어나고, S2.5 는 그 정리의 기록을 요구한다. 스파이크의 골든 여섯도 같은 순서다.
AFTER_FINISH: frozenset[str] = frozenset({"workspace.destroyed"})

#: 그 이벤트가 반드시 실어야 하는 필드. 없으면 소비자가 평가 대상을 잃는다.
REQUIRED_BY_TYPE: dict[str, tuple[str, ...]] = {
    "input.bound": ("challenge_id", "manifest_sha256", "files"),
    "workspace.created": ("container_id", "image_digest", "mounts", "network"),
    "workspace.destroyed": ("surviving_processes", "surviving_containers", "checked_by"),
    "model.requested": (
        "model_id",
        "effort",
        "input_tokens",
        "cached_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "prompt_digest",
        "observation_ids",
    ),
    "model.completed": ("output_tokens", "usd", "latency_ms", "finish_reason"),
    "tool.requested": ("op_id", "tool", "args", "args_digest"),
    "tool.completed": ("op_id", "status", "exit_code", "duration_ms", "artifact_ids"),
    "observation.recorded": (
        "observation_id",
        "source_ref",
        "bytes_total",
        "bytes_shown",
        "shown",
        "shown_digest",
        "truncated",
        "full_digest",
        "artifact_id",
    ),
    "artifact.produced": ("artifact_id", "sha256", "bytes", "producer_ref", "role"),
    "session.opened": ("session_id", "kind", "accepts_input", "banner_observation_id"),
    "session.io": ("session_id", "session_seq", "direction", "bytes", "payload", "payload_digest"),
    "session.closed": (
        "session_id",
        "transcript_artifact_id",
        "exit_status",
        "descendants_killed",
        "survivors",
        "grace_used_ms",
        "reason",
    ),
    "http.exchanged": (
        "target_id",
        "method",
        "host",
        "path",
        "status",
        "jar_digest_before",
        "jar_digest_after",
        "artifact_id",
    ),
    "state.snapshot": (
        "turn",
        "live_session_ids",
        "state_locations",
        "jar_digest",
        "artifact_count",
    ),
    "candidate.produced": ("value", "derived_from", "method"),
    "verification.completed": ("verdict", "verifier_id", "candidate_digest"),
    "answer.sweep": ("surfaces", "method", "checked_by"),
    "scope.refused": ("action", "reason_code", "checked_by", "attempted_from"),
    "attempt.finished": ("outcome", "reason", "wall_clock_s"),
    # §5.2 예약. **어떤 술어도 이것을 읽지 않는다**(§5.1) — 그래서 검사기는 결손을
    # 잡아 주지 않고, 발행 지점에서 막지 않으면 빈 이벤트가 그대로 스트림에 남는다.
    # 여기 등재하는 것은 통제 블록이 아니라 이벤트 본문이므로 `O-23` 의 소급은
    # 걸리지 않는다 — 저장된 스트림은 이 목록을 통과한 적이 없다.
    "hypothesis.recorded": (
        "hypothesis_id",
        "statement",
        "confidence",
        "supported_by",
        "attempt_family",
        "turn",
    ),
    "hypothesis.rejected": ("hypothesis_id", "refuted_by", "reason_code", "turn"),
    "stall.observed": ("signal", "window_turns", "confirmed_facts", "attempt_family"),
}


class EnvelopeError(RuntimeError):
    """봉투를 조립할 수 없다. **조용히 넘어가지 않는다.**"""


def redaction_sentinel(ref: str) -> str:
    """§3.2.1 — 값이 아니라 타입이다."""
    return f"<redacted:{ref}>"


class EnvelopeWriter:
    """한 attempt 의 스트림을 낸다.

    `emit` 은 이벤트 본문을 **딕셔너리로** 받는다. 키워드 인자로 받으면 조립기의
    내부 인자 이름이 계약 필드 이름과 겹칠 수 있고, 스파이크에서 `session.opened`
    가 통째로 사라진 원인이 정확히 그것이었다(§7.1).
    """

    def __init__(
        self,
        sink: TextIO,
        *,
        run_id: str,
        attempt_id: str,
        control: ControlBlock,
        clock: Iterator[str] | None = None,
    ) -> None:
        control.validate()
        self._sink = sink
        self._run_id = run_id
        self._attempt_id = attempt_id
        self._control = control
        self._seq = 0
        self._clock = clock
        self._started = False
        self._finished = False
        self._open_model_call = False
        self._open_ops: set[str] = set()

    # -- 핵심 ----------------------------------------------------------------
    def emit(self, event_type: str, fields: dict[str, Any] | None = None) -> int:
        if self._finished and event_type not in AFTER_FINISH:
            raise EnvelopeError(
                f"attempt.finished 뒤에 올 수 있는 것은 {sorted(AFTER_FINISH)} 뿐이다: {event_type}"
            )
        if event_type not in EVENT_TYPES:
            raise EnvelopeError(
                f"계약에 없는 이벤트 타입 {event_type!r}. 필요하면 멈추고 보고한다 "
                "(CLAUDE.md §8)."
            )
        body = dict(fields or {})

        collisions = sorted(ENVELOPE_KEYS & body.keys())
        if collisions:
            raise EnvelopeError(
                f"{event_type}: 봉투 공통 필드와 이름이 겹친다 {collisions}. "
                "조용히 덮어쓰지 않고 죽는다 (TELEMETRY_SCHEMA §7.1)."
            )
        missing = [f for f in REQUIRED_BY_TYPE.get(event_type, ()) if f not in body]
        if missing:
            raise EnvelopeError(f"{event_type}: 필수 필드가 없다 {missing}")

        self._check_ordering(event_type, body)

        self._seq += 1
        event: dict[str, Any] = {
            "ts": next(self._clock) if self._clock else _now(),
            "run_id": self._run_id,
            "attempt_id": self._attempt_id,
            "seq": self._seq,
            "type": event_type,
        }
        event.update(_redact(body, self._control.secret_refs))
        self._sink.write(json.dumps(event, ensure_ascii=False, sort_keys=False) + "\n")
        return self._seq

    def _check_ordering(self, event_type: str, body: dict[str, Any]) -> None:
        if event_type == "attempt.started":
            if self._started:
                raise EnvelopeError("attempt.started 는 1회다")
            self._started = True
            return
        if not self._started:
            raise EnvelopeError(f"{event_type} 이 attempt.started 보다 앞에 있다")

        if event_type == "model.requested":
            if self._open_model_call:
                raise EnvelopeError(
                    "앞선 model.requested 가 아직 닫히지 않았다. 한 attempt 안에서 모델 "
                    "호출은 직렬이다 — 봉투가 model.* 에 op_id 를 주지 않으므로 직렬이 "
                    "아니면 S9.3의 짝짓기가 성립하지 않는다."
                )
            self._open_model_call = True
        elif event_type in ("model.completed", "model.failed"):
            if not self._open_model_call:
                raise EnvelopeError(f"{event_type} 에 짝이 되는 model.requested 가 없다")
            self._open_model_call = False
        elif event_type == "tool.requested":
            op = str(body["op_id"])
            if op in self._open_ops:
                raise EnvelopeError(f"op_id {op!r} 가 이 attempt 안에서 이미 열려 있다")
            self._open_ops.add(op)
        elif event_type == "tool.completed":
            op = str(body["op_id"])
            if op not in self._open_ops:
                raise EnvelopeError(f"tool.completed 의 op_id {op!r} 에 짝이 되는 요청이 없다")
            self._open_ops.discard(op)
        elif event_type == "attempt.finished":
            if self._open_model_call or self._open_ops:
                raise EnvelopeError(
                    f"닫히지 않은 연산이 있다 — model={self._open_model_call} "
                    f"ops={sorted(self._open_ops)}"
                )
            self._finished = True

    # -- 편의 ----------------------------------------------------------------
    def start(self, extra: dict[str, Any] | None = None) -> int:
        body = self._control.as_event_fields()
        body.update(extra or {})
        return self.emit("attempt.started", body)


def _redact(body: dict[str, Any], secret_refs: Iterable[str]) -> dict[str, Any]:
    """등재된 비밀 이름을 만나면 그 자리에 sentinel 을 넣는다.

    **무엇이 비밀인지는 선언에서만 온다.** 조립기가 값의 모양을 보고 추측하면
    놓치거나 과도하게 가린다(§3.2.1).
    """
    refs = set(secret_refs)
    if not refs:
        return body
    return {k: (redaction_sentinel(k) if k in refs else v) for k, v in body.items()}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


@contextmanager
def open_stream(
    path: Path, *, run_id: str, attempt_id: str, control: ControlBlock
) -> Iterator[EnvelopeWriter]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        yield EnvelopeWriter(fh, run_id=run_id, attempt_id=attempt_id, control=control)
