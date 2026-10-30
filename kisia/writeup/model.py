"""라이트업 생성기의 자료형 — 스트림의 투영이지 판정이 아니다.

근거: `SEAM_IMPLEMENTATION_MAP.md` §6 (S9의 두 소비자 — "둘 다 seam이 아니다.
둘 다 telemetry의 투영이다"), `TELEMETRY_SCHEMA.md` §4.1 ((a)~(e) 충분성 목록).

**여기에 판정값이 없는 것이 설계다.** `kisia.checker.model.Verdict` 를 쓰지 않고
`bool` 과 사유 문자열만 나른다 — 라이트업이 seam 판정을 흉내 내면 §6 머리말이
가른 것이 흐려진다. 있음/없음은 라이트업의 사실이지 계약의 판정이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: 관찰·artifact 의 `source_ref`/`producer_ref` 가 이 접두로 시작하면 **하니스**가 낸 것이고
#: 풀이 경로가 아니다. 실측 근거: `r7a-ok-01` 의 `obs-0004`(`probe:P-S5-b`)·`obs-0005`
#: (`probe:A-4`)가 정답 제출(seq 19~23) **뒤에** 온다. 이것을 풀이 단계로 실으면
#: 라이트업이 거짓말을 하고, 조용히 버리면 검증기에 이빨이 있다는 증거를 버린다.
PROBE_PREFIX = "probe:"


@dataclass(frozen=True)
class Step:
    """한 도구 호출 — `tool.requested` ↔ `tool.completed` 를 `op_id` 로 짝지은 것.

    `spec.md` §3.2.1: "인과 순서를 `seq` 로 주장하려면 `op_id` 로 짝지어야 한다."
    """

    index: int
    op_id: str
    tool: str
    seq_requested: int
    seq_completed: int | None
    args: Any
    #: `argv` / `session` / `structured`. **도구 이름이 아니라 `args` 의 모양과 op 창
    #: 안의 세션 이벤트로 정한다** — 계약이 도구 이름을 열거하지 않기 때문이다
    #: (`TELEMETRY_SCHEMA.md` §2.1 의 `session_kinds[].kind` 주석과 같은 이유).
    shape: str
    argv: tuple[str, ...] | None = None
    status: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    observation_id: str | None = None
    artifact_ids: tuple[str, ...] = ()
    #: op 창 안에서 오간 세션 바이트 (`session.io`). (b) 가 유형 B에서 깨졌던 자리다.
    session_io: tuple[SessionIO, ...] = ()
    #: op 창 안에서 열린 세션.
    opened_sessions: tuple[str, ...] = ()

    @property
    def paired(self) -> bool:
        return self.seq_completed is not None


@dataclass(frozen=True)
class SessionIO:
    seq: int
    session_id: str
    session_seq: int | None
    direction: str
    bytes_count: int | None
    payload: str | None
    payload_digest: str | None
    #: 이 입출력이 어느 도구 op 창 안에서 났는가. **`None` 이면 도구 호출 밖이다** —
    #: 골든 유형 B의 음성 스트림(`negative-b9`)이 실제로 그 모양이고, 도구 단계에만
    #: 매달아 두면 그 스트림의 세션 12건이 라이트업에서 **통째로 사라진다.**
    #: `TELEMETRY_SCHEMA.md` §7.1 이 "조용한 거짓 음성"으로 이름 붙인 실패다.
    op_id: str | None = None

    @property
    def payload_present(self) -> bool:
        """`payload` 가 봉투에 있는가. **없음과 빈 문자열은 다르다.**"""
        return self.payload is not None


@dataclass(frozen=True)
class Observation:
    seq: int
    observation_id: str
    source_ref: str
    bytes_total: int | None
    bytes_shown: int | None
    shown: str | None
    shown_digest: str | None
    truncated: bool
    full_digest: str | None
    artifact_id: str | None

    @property
    def from_probe(self) -> bool:
        return self.source_ref.startswith(PROBE_PREFIX)


@dataclass(frozen=True)
class Candidate:
    seq: int
    value: str
    derived_from: tuple[str, ...]
    method: str
    #: `derived_from` 이 이 스트림의 관찰 id 로 전부 해소되는가.
    resolved: bool
    #: 해소되지 않은 id (있으면 라이트업이 그 사실을 적는다).
    unresolved: tuple[str, ...] = ()

    @property
    def from_probe(self) -> bool:
        return self.method.startswith(PROBE_PREFIX)


@dataclass(frozen=True)
class Verification:
    seq: int
    verdict: bool | None
    verifier_id: str
    candidate_digest: str | None


@dataclass(frozen=True)
class Artifact:
    seq: int
    artifact_id: str
    sha256: str
    bytes_count: int | None
    producer_ref: str
    role: str | None

    @property
    def from_probe(self) -> bool:
        return self.producer_ref.startswith(PROBE_PREFIX)


@dataclass(frozen=True)
class SelfReport:
    """자기 보고와 밖에서 읽은 값의 쌍 (`TELEMETRY_SCHEMA.md` §0.3-3, R2-12).

    **판정에 쓰지 않되 기록은 한다.** `observed` 와 `self_reported` 를 접지 않는
    것이 요점이고, 없는 것은 `None` 으로 남아 라이트업이 "부재"라고 적는다 —
    `0` 이 아니다.
    """

    label: str
    observed: Any
    self_reported: Any
    checked_by: str | None = None


@dataclass(frozen=True)
class Sufficiency:
    """`TELEMETRY_SCHEMA.md` §4.1 의 (a)~(e) 가 이 봉투에 있는가.

    **세션 C가 `CHECKER.md` §7 에서 쓴 조작적 정의를 그대로 옮긴다.** "있다"는
    계약의 주장이고 관측이 아니므로, 같은 방법으로 다시 잰다.

    **값이 셋인 이유** — `True`/`False`/`None`. `None` 은 **평가 대상 없음**이고
    `False` 가 아니다. 두 값만 두었더니 도구를 한 번도 부르지 않은 스트림
    (`negative-b9`)의 (a)·(b) 가 `없다` 로 나왔는데, 그것은 봉투의 결손이 아니라
    잴 것이 없다는 뜻이다. `CLAUDE.md` §6("수행하지 못함과 0을 접지 마라")이 걸리는
    자리이고, 검사기가 `Verdict` 를 여섯으로 둔 것과 같은 이유다(`spec.md` §6.2).
    """

    a_tool_order: bool | None
    b_solve_steps: bool | None
    b_prime_solve_script: bool | None
    c_observations: bool | None
    d_success_evidence: bool | None
    notes: tuple[str, ...] = ()

    def as_json(self) -> dict[str, Any]:
        return {
            "a_tool_order": self.a_tool_order,
            "b_solve_steps": self.b_solve_steps,
            "b_prime_solve_script": self.b_prime_solve_script,
            "c_observations": self.c_observations,
            "d_success_evidence": self.d_success_evidence,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class Repro:
    """(e) 재현 절차의 재료. **재현되었다는 주장은 여기에 없다.**

    생성기는 스트림이 나르는 것을 옮길 뿐이고, "실행 가능하다"는 실제로 돌려
    본 사람이 적는다(`CLAUDE.md` §6). 그래서 이 자료형은 `script` 와 **그 script 가
    무엇을 가정하는지**, 그리고 **봉투가 바이트를 나르지 않는 것**을 함께 나른다.
    """

    #: argv 로 렌더된 단계에서 만든 셸 스크립트. argv 단계가 없으면 `None`.
    script: str | None
    #: argv 로 렌더된 단계 수 / 풀이 경로 단계 수.
    argv_steps: int
    solve_steps: int
    #: 스크립트가 서려면 있어야 하는 것 — 이미지 digest, 마운트, `/input` 파일과 sha256.
    assumptions: tuple[str, ...] = ()
    #: 봉투가 **해시만** 나르고 바이트를 나르지 않는 artifact. 여기 있는 것에
    #: 의존하는 단계는 스트림만으로 재현되지 않는다.
    hash_only: tuple[Artifact, ...] = ()
    #: argv 로 렌더되지 않은 단계와 그 이유.
    unrendered: tuple[str, ...] = ()


@dataclass(frozen=True)
class Writeup:
    """한 attempt 의 라이트업. **스트림 하나에 대한 순수 함수의 결과다.**"""

    stream_path: str
    run_id: str
    attempt_id: str
    control: dict[str, Any]
    outcome: str
    reason: str | None
    wall_clock_s: float | None
    input_files: tuple[dict[str, Any], ...]
    steps: tuple[Step, ...]
    #: 이 attempt 의 **모든** `session.io` — 도구 op 창 밖의 것을 포함한다.
    #: `Step.session_io` 는 그중 op 창 안의 것만 보는 부분집합이고, (b) 는 이쪽으로
    #: 렌더한다. 단계에만 매달면 도구 없이 도는 세션이 통째로 사라진다.
    session_io: tuple[SessionIO, ...]
    observations: tuple[Observation, ...]
    candidates: tuple[Candidate, ...]
    verifications: tuple[Verification, ...]
    artifacts: tuple[Artifact, ...]
    self_reports: tuple[SelfReport, ...]
    sufficiency: Sufficiency
    repro: Repro
    sweep: dict[str, Any] | None = None
    reader_notes: tuple[str, ...] = ()
    #: 스트림에서 읽지 못했거나 계약이 값을 정하지 않아 비운 자리. **비어 있는 것과
    #: 0을 접지 않기 위해** 라이트업이 이 목록을 직접 싣는다.
    gaps: list[str] = field(default_factory=list)

    @property
    def challenge_id(self) -> str:
        return str(self.control.get("challenge_id", ""))

    @property
    def solved(self) -> bool:
        return self.outcome == "solved"

    @property
    def orphan_session_io(self) -> tuple[SessionIO, ...]:
        """어느 도구 op 에도 속하지 않은 세션 입출력. (b) 가 이것을 반드시 실어야 한다."""
        return tuple(io for io in self.session_io if io.op_id is None)

    @property
    def solve_observations(self) -> tuple[Observation, ...]:
        return tuple(o for o in self.observations if not o.from_probe)

    @property
    def probe_observations(self) -> tuple[Observation, ...]:
        return tuple(o for o in self.observations if o.from_probe)

    @property
    def solve_candidates(self) -> tuple[Candidate, ...]:
        return tuple(c for c in self.candidates if not c.from_probe)

    @property
    def probe_candidates(self) -> tuple[Candidate, ...]:
        return tuple(c for c in self.candidates if c.from_probe)
