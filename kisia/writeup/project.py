"""스트림 → 라이트업 투영. **순수 함수이고 판정에 참여하지 않는다.**

근거: `SEAM_IMPLEMENTATION_MAP.md` §6, `TELEMETRY_SCHEMA.md` §4.1.

스트림 **밖** 입력이 없다. 검사기는 둘을 쓰고 각각을 스트림이 해시로 지목하는데
(S9.4a), 라이트업은 그 둘도 쓰지 않는다 — 통제 블록이 재현에 필요한 것을
이미 나르기 때문이다(실측: `r7a-ok-01` 의 통제 블록 39항에 모델·effort·이미지
digest·매니페스트 sha·단가표 sha가 다 있다). 밖에서 아무것도 읽지 않으면
라이트업의 재현성이 스트림 하나의 성질이 된다.
"""

from __future__ import annotations

import shlex
from typing import Any

from kisia.checker.model import Stream
from kisia.writeup.model import (
    Artifact,
    Candidate,
    Observation,
    Repro,
    SelfReport,
    SessionIO,
    Step,
    Sufficiency,
    Verification,
    Writeup,
)


def project(stream: Stream) -> Writeup:
    """스트림 하나를 라이트업으로 투영한다."""
    control = dict(stream.control)
    for k in ("type", "ts", "run_id", "attempt_id", "seq"):
        control.pop(k, None)

    finished = stream.first("attempt.finished") or {}
    bound = stream.first("input.bound") or {}

    observations = _observations(stream)
    artifacts = _artifacts(stream)
    steps = _steps(stream)
    session_io = _session_io(stream, steps)
    candidates = _candidates(stream, observations)
    verifications = _verifications(stream)

    gaps: list[str] = []
    sufficiency = _sufficiency(
        steps, session_io, observations, artifacts, candidates, verifications,
        solved=str(finished.get("outcome", "")) == "solved", gaps=gaps,
    )
    repro = _repro(steps, artifacts, control, bound, gaps)

    return Writeup(
        stream_path=str(stream.path),
        run_id=stream.run_id,
        attempt_id=stream.attempt_id,
        control=control,
        outcome=str(finished.get("outcome", "")),
        reason=_opt_str(finished.get("reason")),
        wall_clock_s=_opt_float(finished.get("wall_clock_s")),
        input_files=tuple(bound.get("files") or ()),
        steps=steps,
        session_io=session_io,
        observations=observations,
        candidates=candidates,
        verifications=verifications,
        artifacts=artifacts,
        self_reports=_self_reports(stream),
        sufficiency=sufficiency,
        repro=repro,
        sweep=stream.first("answer.sweep"),
        reader_notes=tuple(stream.reader_notes),
        gaps=gaps,
    )


# ---------------------------------------------------------------------------
# 이벤트별 투영
# ---------------------------------------------------------------------------


def _observations(stream: Stream) -> tuple[Observation, ...]:
    out: list[Observation] = []
    for e in stream.by_type("observation.recorded"):
        out.append(
            Observation(
                seq=int(e.get("seq", 0)),
                observation_id=str(e.get("observation_id", "")),
                source_ref=str(e.get("source_ref", "")),
                bytes_total=_opt_int(e.get("bytes_total")),
                bytes_shown=_opt_int(e.get("bytes_shown")),
                # `shown` 은 **없음과 빈 문자열이 다르다.** get 의 기본값을 ""로 두면
                # 그 둘이 접히고, 접히는 순간 (c) 의 측정이 거짓이 된다.
                shown=_opt_str(e.get("shown")),
                shown_digest=_opt_str(e.get("shown_digest")),
                truncated=bool(e.get("truncated")),
                full_digest=_opt_str(e.get("full_digest")),
                artifact_id=_opt_str(e.get("artifact_id")),
            )
        )
    return tuple(out)


def _artifacts(stream: Stream) -> tuple[Artifact, ...]:
    return tuple(
        Artifact(
            seq=int(e.get("seq", 0)),
            artifact_id=str(e.get("artifact_id", "")),
            sha256=str(e.get("sha256", "")),
            bytes_count=_opt_int(e.get("bytes")),
            producer_ref=str(e.get("producer_ref", "")),
            role=_opt_str(e.get("role")),
        )
        for e in stream.by_type("artifact.produced")
    )


def _steps(stream: Stream) -> tuple[Step, ...]:
    """`op_id` 로 짝짓고, op 창 안의 세션 이벤트를 그 단계에 붙인다.

    창은 `[seq(requested), seq(completed)]` 다. `seq` 는 **쓰기 순서**이고 동시
    세션의 이벤트도 그 지점을 통과하므로(`TELEMETRY_SCHEMA.md` §3.2.1), 창으로
    묶는 것은 인과의 주장이 아니라 **그 op 가 열려 있는 동안 오간 것**의 기록이다.
    """
    completed = {
        str(e.get("op_id")): e for e in stream.by_type("tool.completed") if e.get("op_id")
    }
    sess_io = stream.by_type("session.io")
    sess_open = stream.by_type("session.opened")

    steps: list[Step] = []
    for index, req in enumerate(stream.by_type("tool.requested"), start=1):
        op_id = str(req.get("op_id", ""))
        comp = completed.get(op_id)
        seq_req = int(req.get("seq", 0))
        seq_comp = _opt_int(comp.get("seq")) if comp else None
        hi = seq_comp if seq_comp is not None else seq_req

        io = tuple(
            SessionIO(
                seq=int(e.get("seq", 0)),
                session_id=str(e.get("session_id", "")),
                session_seq=_opt_int(e.get("session_seq")),
                direction=str(e.get("direction", "")),
                bytes_count=_opt_int(e.get("bytes")),
                payload=_opt_str(e.get("payload")),
                payload_digest=_opt_str(e.get("payload_digest")),
            )
            for e in sess_io
            if seq_req <= int(e.get("seq", 0)) <= hi
        )
        opened = tuple(
            str(e.get("session_id", ""))
            for e in sess_open
            if seq_req <= int(e.get("seq", 0)) <= hi
        )

        args = req.get("args")
        argv = _as_argv(args)
        if argv is not None:
            shape = "argv"
        elif io or opened:
            shape = "session"
        else:
            shape = "structured"

        steps.append(
            Step(
                index=index,
                op_id=op_id,
                tool=str(req.get("tool", "")),
                seq_requested=seq_req,
                seq_completed=seq_comp,
                args=args,
                shape=shape,
                argv=argv,
                status=_opt_str(comp.get("status")) if comp else None,
                exit_code=_opt_int(comp.get("exit_code")) if comp else None,
                duration_ms=_opt_int(comp.get("duration_ms")) if comp else None,
                observation_id=_opt_str(comp.get("observation_id")) if comp else None,
                artifact_ids=(
                    tuple(str(a) for a in (comp.get("artifact_ids") or ())) if comp else ()
                ),
                session_io=io,
                opened_sessions=opened,
            )
        )
    return tuple(steps)


def _session_io(stream: Stream, steps: tuple[Step, ...]) -> tuple[SessionIO, ...]:
    """**모든** `session.io` 를 seq 순으로 모으고, 어느 op 창에 들었는지만 표시한다.

    도구 단계에 매다는 것이 아니라 독립으로 모으는 이유는 실측이다 — 골든 유형 B의
    음성 스트림 `negative-b9` 는 `tool.requested` 가 **0건**이고 `session.io` 가
    12건이다. 단계에만 매달면 그 12건이 라이트업에서 통째로 사라지고, (b) 절이
    조용히 비어 나온다. `TELEMETRY_SCHEMA.md` §7.1 이 봉투 조립기의 가장 비싼
    결함으로 이름 붙인 것이 정확히 그 모양이다.
    """
    windows = [
        (
            s.seq_requested,
            s.seq_completed if s.seq_completed is not None else s.seq_requested,
            s.op_id,
        )
        for s in steps
    ]
    out: list[SessionIO] = []
    for e in stream.by_type("session.io"):
        seq = int(e.get("seq", 0))
        op = next((op_id for lo, hi, op_id in windows if lo <= seq <= hi), None)
        out.append(
            SessionIO(
                seq=seq,
                session_id=str(e.get("session_id", "")),
                session_seq=_opt_int(e.get("session_seq")),
                direction=str(e.get("direction", "")),
                bytes_count=_opt_int(e.get("bytes")),
                payload=_opt_str(e.get("payload")),
                payload_digest=_opt_str(e.get("payload_digest")),
                op_id=op,
            )
        )
    return tuple(out)


def _as_argv(args: Any) -> tuple[str, ...] | None:
    """`args` 가 실행 가능한 argv 인가 — **모양으로만** 판정한다.

    실측된 두 모양을 받는다: 골든의 `["python3", "/work/…", …]` (리스트 자체가
    argv) 와 모델 주도의 `{"argv": [...]}`. 도구 이름(`exec`·`http`·`run_command`)
    으로 가르지 않는 이유는 계약이 도구 이름을 열거하지 않기 때문이다 — 열거하면
    구현 모양을 계약이 정하게 된다(`spec.md` §0.1).
    """
    if isinstance(args, list) and args and all(isinstance(a, str) for a in args):
        return tuple(str(a) for a in args)
    if isinstance(args, dict):
        inner = args.get("argv")
        if isinstance(inner, list) and inner and all(isinstance(a, str) for a in inner):
            return tuple(str(a) for a in inner)
    return None


def _candidates(stream: Stream, observations: tuple[Observation, ...]) -> tuple[Candidate, ...]:
    known = {o.observation_id for o in observations}
    out: list[Candidate] = []
    for e in stream.by_type("candidate.produced"):
        derived = tuple(str(d) for d in (e.get("derived_from") or ()))
        missing = tuple(d for d in derived if d not in known)
        out.append(
            Candidate(
                seq=int(e.get("seq", 0)),
                value=str(e.get("value", "")),
                derived_from=derived,
                method=str(e.get("method", "")),
                resolved=bool(derived) and not missing,
                unresolved=missing,
            )
        )
    return tuple(out)


def _verifications(stream: Stream) -> tuple[Verification, ...]:
    return tuple(
        Verification(
            seq=int(e.get("seq", 0)),
            verdict=e.get("verdict") if isinstance(e.get("verdict"), bool) else None,
            verifier_id=str(e.get("verifier_id", "")),
            candidate_digest=_opt_str(e.get("candidate_digest")),
        )
        for e in stream.by_type("verification.completed")
    )


def _self_reports(stream: Stream) -> tuple[SelfReport, ...]:
    """자기 보고 셋을 밖에서 읽은 값과 **나란히** 싣는다 (R2-12).

    `usd_self_reported` 는 실측에서 **부재**다 — provider 가 비용을 보고하지 않는다.
    0이 아니라 없는 것이고, 그 둘을 접으면 거짓 관측이 된다.
    """
    out: list[SelfReport] = []
    for e in stream.by_type("model.completed"):
        out.append(
            SelfReport(
                label=f"seq {e.get('seq')} model.completed.usd",
                observed=e.get("usd"),
                self_reported=e.get("usd_self_reported"),
            )
        )
    for e in stream.by_type("workspace.destroyed"):
        out.append(
            SelfReport(
                label=f"seq {e.get('seq')} workspace.destroyed.surviving_processes",
                observed=e.get("surviving_processes"),
                self_reported=e.get("surviving_processes_self_reported"),
                checked_by=_opt_str(e.get("checked_by")),
            )
        )
    for e in stream.by_type("session.closed"):
        out.append(
            SelfReport(
                label=f"seq {e.get('seq')} session.closed.survivors",
                observed=e.get("survivors"),
                self_reported=e.get("survivors_self_reported"),
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# (a)~(e) 충분성 — CHECKER.md §7 의 조작적 정의를 그대로 옮긴다
# ---------------------------------------------------------------------------


def _sufficiency(
    steps: tuple[Step, ...],
    session_io: tuple[SessionIO, ...],
    observations: tuple[Observation, ...],
    artifacts: tuple[Artifact, ...],
    candidates: tuple[Candidate, ...],
    verifications: tuple[Verification, ...],
    *,
    solved: bool,
    gaps: list[str],
) -> Sufficiency:
    """(a)~(e) 를 셋으로 잰다 — 있다 / 없다 / **평가 대상 없음**.

    셋째 값이 없으면 "봉투가 나르지 않는다"와 "잴 것이 없다"가 접힌다. 실측이
    그것을 강제했다: `negative-b9` 는 도구를 한 번도 부르지 않으므로 (a) 가
    `없다` 가 아니라 해당 없음이다.
    """
    notes: list[str] = []
    sent = [io for io in session_io if io.direction == "out"]

    # (a) 도구 순서 — op_id 짝이 맞고 전부 tool 이름을 싣는다
    a: bool | None
    if not steps:
        a = None
        notes.append(
            "(a) `tool.requested` 가 0건이다 — **해당 없음**이지 결손이 아니다. "
            "이 스트림의 행위는 세션으로 돈다."
        )
    else:
        op_ids = [s.op_id for s in steps]
        a = all(s.paired and s.op_id and s.tool for s in steps)
        if len(set(op_ids)) != len(op_ids):
            a = False
            notes.append("(a) `op_id` 가 attempt 안에서 유일하지 않다 (§3.2.1).")
        if not a:
            notes.append("(a) 짝지어지지 않았거나 `tool` 이름이 없는 단계가 있다.")

    # (b) 실행 가능한 solve 단계 — args 원문 + **모든** 세션 payload
    b: bool | None
    missing_args = [s for s in steps if s.args is None]
    missing_payload = [io for io in sent if not io.payload_present]
    if not steps and not sent:
        b = None
        notes.append("(b) 도구 호출도 세션 출력도 0건이다 — 실을 풀이 단계가 없다.")
    else:
        b = not missing_args and not missing_payload
    if missing_args:
        notes.append(
            f"(b) `tool.requested.args` 가 없는 단계 {len(missing_args)}건 — "
            "원문이 없으면 재현 절차가 서지 않는다."
        )
    if missing_payload:
        notes.append(
            f"(b) `session.io(out).payload` 가 없는 것 {len(missing_payload)}건 — "
            "R2-13 이 닫은 자리가 다시 열렸다 (`CHECKER.md` §7.1-1)."
        )

    # (b') role=solve_script 인 artifact
    bp: bool | None
    scripts = [a_ for a_ in artifacts if a_.role == "solve_script"]
    verbatim = not missing_args and not missing_payload and bool(steps or sent)
    if scripts:
        bp = True
        notes.append(
            f"(b') `role=solve_script` artifact {len(scripts)}건이 있다. **다만 봉투는 "
            "sha256 만 나르고 바이트를 나르지 않는다** — 인용은 되고 재현은 되지 않는다."
        )
    elif verbatim:
        # 저작된 스크립트가 **없는** 궤적이다. 모든 단계가 (b) 에 원문으로 있으므로
        # 라이트업이 잃는 것이 없다. 결손이 아니라 해당 없음이다.
        bp = None
        notes.append(
            "(b') `role=solve_script` artifact 가 없다 — **해당 없음.** 이 궤적에는 "
            "저작된 solve 스크립트가 존재하지 않고(모델이 턴마다 도구를 고른다), "
            "풀이 단계 전부가 (b) 에 원문으로 있다. 실측: 재빌드-7의 모델 주도 "
            "스트림 10개가 전부 이 모양이다."
        )
    else:
        bp = False
        notes.append(
            "(b') `role=solve_script` artifact 가 없고 (b) 도 원문을 다 나르지 못한다 — "
            "이쪽은 **실제 결손**이다. 풀이를 복원할 경로가 봉투에 없다."
        )

    # (c) 무엇을 관찰해 답에 이르렀나
    c: bool | None
    solve_obs = [o for o in observations if not o.from_probe]
    if not solve_obs:
        c = None
        notes.append("(c) 풀이 경로의 관찰이 0건이다 — 잴 대상이 없다.")
    else:
        c = all(o.shown is not None and o.shown_digest for o in solve_obs)
        if not c:
            notes.append("(c) `shown` 또는 `shown_digest` 가 없는 관찰이 있다 (A-9).")

    # (d) 성공의 증거 — **성공하지 않은 attempt 에는 잴 대상이 없다**
    d: bool | None
    solve_cands = [x for x in candidates if not x.from_probe]
    true_ver = [v for v in verifications if v.verdict is True]
    unresolved = [x for x in solve_cands if not x.resolved]
    if not solved:
        d = None
        notes.append(
            "(d) `outcome` 이 `solved` 가 아니다 — 성공의 증거는 **해당 없음**이다. "
            "실패한 attempt 에 성공 증거가 없는 것은 봉투의 결손이 아니다."
        )
    else:
        d = bool(true_ver) and bool(solve_cands) and not unresolved
        if unresolved:
            notes.append(
                f"(d) `derived_from` 이 앞선 관찰로 해소되지 않는 후보 {len(unresolved)}건."
            )
        if not true_ver:
            notes.append("(d) `verdict=true` 인 `verification.completed` 가 없다.")

    # **결손만** gaps 에 넣는다. 해당 없음은 채우지 못한 자리가 아니다.
    for value, prefix in ((a, "(a)"), (b, "(b)"), (bp, "(b')"), (c, "(c)"), (d, "(d)")):
        if value is False:
            gaps.extend(n for n in notes if n.startswith(prefix))

    return Sufficiency(
        a_tool_order=a,
        b_solve_steps=b,
        b_prime_solve_script=bp,
        c_observations=c,
        d_success_evidence=d,
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# (e) 재현 절차의 재료
# ---------------------------------------------------------------------------


def _repro(
    steps: tuple[Step, ...],
    artifacts: tuple[Artifact, ...],
    control: dict[str, Any],
    bound: dict[str, Any],
    gaps: list[str],
) -> Repro:
    """재현 재료를 모은다. **"재현된다"는 주장을 여기서 만들지 않는다.**

    생성기가 아는 것은 "몇 단계가 argv 로 렌더됐고 무엇이 렌더되지 않았나"까지다.
    실행 가능한지는 실제로 돌려 본 사람이 적는다 — `CLAUDE.md` §6 이 "동작합니다"에
    실행 명령과 출력을 요구하는 그 자리다.
    """
    solve_steps = [s for s in steps if not s.tool.startswith("probe:")]
    argv_steps = [s for s in solve_steps if s.argv is not None]

    lines: list[str] = []
    unrendered: list[str] = []
    for s in solve_steps:
        if s.argv is not None:
            lines.append(f"# 단계 {s.index} — op {s.op_id} (스트림 seq {s.seq_requested})")
            lines.append(_argv_to_sh(s.argv))
            lines.append("")
        elif s.shape == "session":
            sent = [io for io in s.session_io if io.direction == "out"]
            unrendered.append(
                f"단계 {s.index} ({s.tool}) — 세션 단계다. 보낸 바이트 {len(sent)}건은 "
                "라이트업 (b) 에 원문으로 있으나 셸 스크립트로 서지 않는다: 세션을 여는 "
                "주체가 런타임이다."
            )
        else:
            unrendered.append(
                f"단계 {s.index} ({s.tool}) — argv 가 아니다. `args` 를 (b) 에 원문으로 싣는다."
            )

    script = _script_header(control, bound) + "\n".join(lines) if lines else None

    assumptions: list[str] = []
    for img in control.get("image_digest") or ():
        if isinstance(img, dict):
            assumptions.append(f"이미지 {img.get('image')} = {img.get('id')}")
    for f in bound.get("files") or ():
        if isinstance(f, dict):
            assumptions.append(f"입력 {f.get('path')} ({f.get('bytes')}B) sha256={f.get('sha256')}")
    if control.get("challenge_manifest_sha256"):
        assumptions.append(f"매니페스트 sha256={control['challenge_manifest_sha256']}")
    net = control.get("network_policy")
    if isinstance(net, dict):
        assumptions.append(f"네트워크 정책 {net}")

    hash_only = tuple(
        a for a in artifacts if a.role in ("solve_script", "tool_script") and not a.from_probe
    )
    if hash_only:
        gaps.append(
            f"(e) 봉투가 해시만 나르는 스크립트 artifact {len(hash_only)}건이 있다 — "
            "이 스트림은 스트림만으로 재현되지 않는다."
        )
    if unrendered:
        gaps.extend(f"(e) {u}" for u in unrendered)

    return Repro(
        script=script,
        argv_steps=len(argv_steps),
        solve_steps=len(solve_steps),
        assumptions=tuple(assumptions),
        hash_only=hash_only,
        unrendered=tuple(unrendered),
    )


def _script_header(control: dict[str, Any], bound: dict[str, Any]) -> str:
    imgs = ", ".join(
        f"{i.get('image')}@{i.get('id')}"
        for i in (control.get("image_digest") or ())
        if isinstance(i, dict)
    )
    files = ", ".join(
        str(f.get("path")) for f in (bound.get("files") or ()) if isinstance(f, dict)
    )
    return (
        "#!/bin/sh\n"
        "# 재현 스크립트 — kisia.writeup 이 스트림에서 생성했다. 손으로 쓰지 않았다.\n"
        f"# challenge : {control.get('challenge_id')}\n"
        f"# 이미지     : {imgs or '(스트림에 없음)'}\n"
        f"# 입력       : {files or '(스트림에 없음)'}\n"
        "#\n"
        "# **정답 문자열을 싣지 않는다.** 실으면 이 파일이 S8.3 스윕의 표면이 되고,\n"
        "# 재현 확인이 자기 자신을 확인하는 것이 된다. 대조는 라이트업 (d) 의 값으로\n"
        "# 스크립트 **밖에서** 한다.\n"
        "#\n"
        "# **이 파일을 작업 디렉터리에 두지 마라.** 단계가 그 디렉터리를 들여다보면\n"
        "# 스크립트가 자기 자신을 관찰해 재현이 어긋난다. 재빌드-8 실측: /work 에 두면\n"
        "# `ls -l /work` 가 repro.sh 를 세어 `total 1820` 이 `1824` 가 되고, /artifacts\n"
        "# 로 옮기면 기록된 관찰과 **바이트로 같아진다**(sha256 dff384d6…, 185 B).\n"
        "set -e\n\n"
    )


def _argv_to_sh(argv: tuple[str, ...]) -> str:
    return " ".join(shlex.quote(a) for a in argv)


# ---------------------------------------------------------------------------


def _opt_str(v: Any) -> str | None:
    return None if v is None else str(v)


def _opt_int(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _opt_float(v: Any) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None
