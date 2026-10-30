"""라이트업 → 사람이 읽는 마크다운.

`SEAM_IMPLEMENTATION_MAP.md` §6 이 산출물의 내용을 다섯으로 적는다: 도구 순서 ·
실행 가능한 solve 단계 · 무엇을 관찰해 답에 이르렀나 · 성공의 증거 · 재현 절차.
절 이름을 그 다섯에 맞추고 `TELEMETRY_SCHEMA.md` §4.1 의 (a)~(e) 라벨을 함께 단다.
"""

from __future__ import annotations

import json
from typing import Any

from kisia.writeup.model import Observation, Step, Writeup

#: 관찰 본문을 라이트업에 실을 때의 상한. 봉투의 `bytes_shown_limit` 과 다른 값이고
#: 다른 것을 뜻한다 — 저쪽은 **모델에게 보인 바이트**의 한도(계약 값)이고, 이쪽은
#: 문서의 가독성이다. 넘기면 잘랐다고 적고 `shown_digest` 로 원본을 지목한다.
RENDER_LIMIT = 1200


def render_markdown(w: Writeup) -> str:
    p: list[str] = []
    _head(w, p)
    _section_a(w, p)
    _section_b(w, p)
    _section_c(w, p)
    _section_d(w, p)
    _section_e(w, p)
    _appendix(w, p)
    return "\n".join(p).rstrip() + "\n"


def _head(w: Writeup, p: list[str]) -> None:
    c = w.control
    p.append(f"# 라이트업 — {w.challenge_id or '(challenge_id 없음)'} / `{w.attempt_id}`")
    p.append("")
    p.append(
        "**이 문서는 스트림 하나의 투영이다. 판정에 참여하지 않는다** — "
        "`SEAM_IMPLEMENTATION_MAP.md` §6 이 라이트업 생성기를 seam 이 아니라 "
        "telemetry 의 소비자로 명명한다. 여기 있는 값은 전부 봉투에서 왔고, "
        "봉투에 없는 것은 **부재**라고 적는다 — `0` 이 아니다."
    )
    p.append("")
    p.append(f"생성 대상 스트림: `{w.stream_path}`")
    p.append("")
    p.append("| | |")
    p.append("|---|---|")
    p.append(f"| challenge | `{c.get('challenge_id')}` (`{c.get('challenge_set')}`) |")
    p.append(f"| provenance | `{c.get('provenance')}` |")
    p.append(f"| flag_format | `{c.get('flag_format')}` |")
    p.append(f"| run / attempt | `{w.run_id}` / `{w.attempt_id}` |")
    p.append(f"| outcome | **`{w.outcome or '(없음)'}`** — {w.reason or '사유 부재'} |")
    p.append(f"| wall clock | {_num(w.wall_clock_s)} s |")
    p.append(f"| 이벤트 | 단계 {len(w.steps)} · 관찰 {len(w.observations)} · "
             f"artifact {len(w.artifacts)} |")
    p.append("")
    if not w.solved:
        p.append(
            f"> **`outcome` 이 `solved` 가 아니다 (`{w.outcome}`).** 이 라이트업은 "
            "성공한 풀이의 기록이 아니라 그 attempt 에 무슨 일이 있었는지의 기록이다. "
            "`spec.md` §6.3 아래에서 이런 스트림은 집합 판정의 상시 술어에서 빠진다."
        )
        p.append("")


def _section_a(w: Writeup, p: list[str]) -> None:
    p.append("## (a) 사용한 도구의 순서")
    p.append("")
    if not w.steps:
        p.append("`tool.requested` 가 0건이다. **도구를 쓰지 않은 것과 기록되지 않은 것은 "
                 "다르고, 이 스트림만으로는 갈리지 않는다.**")
        p.append("")
        return
    p.append("`op_id` 로 짝지었다 — `seq` 는 쓰기 순서이므로 인과를 주장하려면 "
             "`op_id` 로 짝지어야 한다(`TELEMETRY_SCHEMA.md` §3.2.1).")
    p.append("")
    p.append("| # | op_id | 도구 | 모양 | seq | exit | 소요 | 관찰 |")
    p.append("|---|---|---|---|---|---|---|---|")
    for s in w.steps:
        seqs = f"{s.seq_requested}→{s.seq_completed}" if s.paired else f"{s.seq_requested}→**미완**"
        p.append(
            f"| {s.index} | `{s.op_id}` | `{s.tool}` | {s.shape} | {seqs} | "
            f"{_num(s.exit_code)} | {_num(s.duration_ms)} ms | "
            f"{('`' + s.observation_id + '`') if s.observation_id else '부재'} |"
        )
    p.append("")


def _section_b(w: Writeup, p: list[str]) -> None:
    p.append("## (b) 실행 가능한 solve 단계")
    p.append("")
    p.append(
        "**봉투의 원문 그대로다** — 요약하거나 다시 쓰지 않았다. 유형 A·C 는 "
        "`tool.requested.args` 가, 세션형(유형 B)은 `session.io.payload` 가 나른다. "
        "후자는 R2-13 이 넣은 필드이고, 그 전에는 라이트업의 이 절이 유형 B에서만 "
        "깨져 있었다(`CHECKER.md` §7.1-1)."
    )
    p.append("")
    for s in w.steps:
        p.append(f"### 단계 {s.index} — `{s.tool}` (op `{s.op_id}`)")
        p.append("")
        _render_step_body(s, p)

    orphans = w.orphan_session_io
    if orphans:
        p.append("### 도구 호출 밖의 세션 입출력")
        p.append("")
        p.append(
            f"어느 `tool.requested`/`tool.completed` 창에도 들지 않은 `session.io` "
            f"{len(orphans)}건이다. **도구 단계에만 매달아 두면 이것이 라이트업에서 "
            "통째로 사라진다** — 이 절이 조용히 비어 나오는 것이 "
            "`TELEMETRY_SCHEMA.md` §7.1 이 이름 붙인 실패다."
        )
        p.append("")
        p.append("```")
        for io in orphans:
            if io.direction == "out":
                body = io.payload if io.payload is not None else "«payload 부재»"
                p.append(f"[seq {io.seq}] {io.session_id} #{io.session_seq} ← {body!r}")
            else:
                p.append(
                    f"[seq {io.seq}] {io.session_id} #{io.session_seq} → "
                    f"{_num(io.bytes_count)} B (내용은 (c) 의 관찰)"
                )
        p.append("```")
        p.append("")
    if not w.steps and not orphans:
        p.append("도구 호출도 세션 입출력도 0건이다 — 실을 풀이 단계가 없다.")
        p.append("")


def _render_step_body(s: Step, p: list[str]) -> None:
    if s.argv is not None:
        p.append("```sh")
        p.append(" ".join(s.argv) if len(s.argv) <= 2 else _shell_join(s.argv))
        p.append("```")
        p.append("")
    else:
        p.append("```json")
        p.append(json.dumps(s.args, ensure_ascii=False, indent=2))
        p.append("```")
        p.append("")
    if s.opened_sessions:
        p.append(f"열린 세션: {', '.join('`' + x + '`' for x in s.opened_sessions)}")
        p.append("")
    sent = [io for io in s.session_io if io.direction == "out"]
    got = [io for io in s.session_io if io.direction != "out"]
    if sent:
        p.append("보낸 바이트 (`session.io.payload`):")
        p.append("")
        p.append("```")
        for io in sent:
            body = io.payload if io.payload is not None else "«payload 부재 — 봉투가 나르지 않는다»"
            p.append(f"[{io.session_id} #{io.session_seq}] {body!r}")
        p.append("```")
        p.append("")
    if got:
        p.append(f"돌아온 것 {len(got)}건은 (c) 의 관찰로 기록된다.")
        p.append("")


def _section_c(w: Writeup, p: list[str]) -> None:
    p.append("## (c) 무엇을 관찰해 답에 이르렀나")
    p.append("")
    solve = w.solve_observations
    if not solve:
        p.append("풀이 경로의 관찰이 0건이다.")
        p.append("")
    else:
        p.append(
            "`shown` 은 **모델에게 실제로 보인 바이트**다. 잘린 관찰은 그 사실과 "
            "`full_digest` 를 함께 싣는다 — 보인 것과 있던 것을 접지 않는다."
        )
        p.append("")
        for o in solve:
            _render_observation(o, p)
    probes = w.probe_observations
    if probes:
        p.append(
            f"> 이 스트림에는 하니스 프로브가 낸 관찰이 {len(probes)}건 더 있다. "
            "**풀이 경로가 아니므로 부록으로 옮겼다** — 여기 실으면 라이트업이 "
            "하니스의 행동을 풀이 단계로 보고하게 된다."
        )
        p.append("")


def _render_observation(o: Observation, p: list[str]) -> None:
    head = f"**`{o.observation_id}`** — 출처 `{o.source_ref}`"
    if o.truncated:
        head += f" · **잘림** {_num(o.bytes_shown)}/{_num(o.bytes_total)} B"
    else:
        head += f" · {_num(o.bytes_shown)}/{_num(o.bytes_total)} B"
    p.append(head)
    p.append("")
    if o.shown is None:
        p.append("`shown` **부재** — 봉투가 보인 바이트를 나르지 않는다 (A-9 이 닫은 자리).")
        p.append("")
        return
    body = o.shown
    clipped = len(body) > RENDER_LIMIT
    if clipped:
        body = body[:RENDER_LIMIT]
    p.append("```")
    p.append(body)
    p.append("```")
    if clipped:
        p.append(
            f"*(문서 가독성을 위해 {RENDER_LIMIT}자에서 잘랐다. 봉투가 나르는 원문은 "
            f"`shown_digest` `{o.shown_digest}` 가 지목한다. 이 자름은 계약의 "
            "`bytes_shown_limit` 과 무관하다.)*"
        )
    p.append(f"`shown_digest` `{o.shown_digest or '부재'}`"
             + (f" · `full_digest` `{o.full_digest}`" if o.full_digest else ""))
    p.append("")


def _section_d(w: Writeup, p: list[str]) -> None:
    p.append("## (d) 성공의 증거")
    p.append("")
    cands = w.solve_candidates
    if not cands:
        p.append("풀이 경로의 후보가 0건이다.")
        p.append("")
    for cnd in cands:
        p.append(f"후보 `{cnd.value}` (seq {cnd.seq}, method `{cnd.method}`)")
        p.append("")
        if cnd.derived_from:
            state = "앞선 관찰로 **해소된다**" if cnd.resolved else "해소되지 **않는다**"
            p.append(f"- `derived_from` = {list(cnd.derived_from)} — {state}")
            if cnd.unresolved:
                p.append(f"- 해소되지 않은 id: {list(cnd.unresolved)}")
        else:
            p.append("- `derived_from` **부재** — 파생을 주장하지 않는다.")
        p.append("")
    if w.verifications:
        p.append("검증:")
        p.append("")
        p.append("| seq | verdict | verifier_id |")
        p.append("|---|---|---|")
        for v in w.verifications:
            mark = {True: "**참**", False: "거짓", None: "부재"}[v.verdict]
            p.append(f"| {v.seq} | {mark} | `{v.verifier_id}` |")
        p.append("")
        p.append(
            "**검증기는 solver 밖이다** (S8.1·S8.4). `verifier_id` 의 "
            "`<구성요소>@<위치>(<방법>)` 꼴이 그것을 기록한다."
        )
        p.append("")
    if w.sweep:
        surfaces = w.sweep.get("surfaces") or []
        p.append(
            "정답 스윕(`answer.sweep`, **하니스가 낸다**): "
            + ", ".join(
                f"`{s.get('surface')}` whole={s.get('whole_hits')}"
                for s in surfaces
                if isinstance(s, dict)
            )
        )
        p.append("")
    neg = w.probe_candidates
    if neg:
        p.append(
            f"그리고 하니스가 **틀린 후보** {len(neg)}건을 만들어 검증기가 그것을 "
            "거절하는지 확인했다. 부록에 있다 — 이것은 풀이가 아니라 **검증기에 "
            "이빨이 있다는 증거**이고, 빼면 (d) 가 약해진다."
        )
        p.append("")


def _section_e(w: Writeup, p: list[str]) -> None:
    r = w.repro
    p.append("## (e) 재현 절차")
    p.append("")
    p.append(
        "**통제 블록이 재현에 필요한 것을 나른다.** 이 절은 스트림 밖에서 아무것도 "
        "읽지 않았다 — 그래서 재현성이 이 스트림 하나의 성질이 된다."
    )
    p.append("")
    p.append("| 항목 | 값 |")
    p.append("|---|---|")
    for key in (
        "runtime_id", "profile", "provider", "model_id", "model_snapshot", "endpoint",
        "requested_reasoning_effort", "effective_reasoning_effort", "tool_protocol",
        "capability_probe_id", "probe_set_id", "host_id", "challenge_manifest_sha256",
        "pricing_sha256", "bytes_shown_limit", "attempt_timeout_s", "tool_timeout_s",
    ):
        if key in w.control:
            p.append(f"| `{key}` | `{w.control[key]}` |")
    p.append("")
    if r.assumptions:
        p.append("이 절차가 서려면 있어야 하는 것:")
        p.append("")
        for a in r.assumptions:
            p.append(f"- {a}")
        p.append("")
    p.append(f"**argv 로 렌더된 단계 {r.argv_steps} / 풀이 단계 {r.solve_steps}.**")
    p.append("")
    if r.script:
        p.append("생성된 재현 스크립트 (`repro.sh`):")
        p.append("")
        p.append("```sh")
        p.append(r.script.rstrip())
        p.append("```")
        p.append("")
        p.append(
            "> **이 스크립트가 실행 가능하다는 주장은 여기에 없다.** 생성기는 봉투의 "
            "바이트를 옮길 뿐이고, \"동작합니다\"는 실행 명령과 출력이 따라올 때만 "
            "쓴다(`CLAUDE.md` §6). 실제 실행 기록은 `docs/rebuild/` 에 있다."
        )
        p.append("")
    else:
        p.append("argv 로 렌더할 단계가 없어 스크립트를 만들지 않았다.")
        p.append("")
    if r.unrendered:
        p.append("**스크립트로 서지 않는 단계:**")
        p.append("")
        for u in r.unrendered:
            p.append(f"- {u}")
        p.append("")
    if r.hash_only:
        p.append(
            "**봉투가 해시만 나르는 스크립트 artifact** — 이 스트림은 스트림만으로 "
            "재현되지 않는다. `artifact.produced` 는 `sha256`·`bytes`·`producer_ref`·"
            "`role` 을 나르고 **내용을 나르지 않는다**:"
        )
        p.append("")
        for art in r.hash_only:
            p.append(f"- `{art.artifact_id}` role=`{art.role}` {art.bytes_count}B "
                     f"`{art.sha256}` (생산자 `{art.producer_ref}`)")
        p.append("")


def _appendix(w: Writeup, p: list[str]) -> None:
    p.append("---")
    p.append("")
    p.append("## 부록 1. 봉투 충분성 — `TELEMETRY_SCHEMA.md` §4.1")
    p.append("")
    s = w.sufficiency
    p.append("| 요소 | 이 스트림 |")
    p.append("|---|---|")
    p.append(f"| (a) 사용한 도구의 순서 | {_yn(s.a_tool_order)} |")
    p.append(f"| (b) 실행 가능한 solve 단계 | {_yn(s.b_solve_steps)} |")
    p.append(f"| (b') `role=solve_script` artifact | {_yn(s.b_prime_solve_script)} |")
    p.append(f"| (c) 무엇을 관찰해 답에 이르렀나 | {_yn(s.c_observations)} |")
    p.append(f"| (d) 성공의 증거 | {_yn(s.d_success_evidence)} |")
    p.append("")
    for n in s.notes:
        p.append(f"- {n}")
    p.append("")
    p.append(
        "(e) 재현 절차는 이 표에 없다 — `CHECKER.md` §7 이 (e) 를 P-S9-a(다른 기계에서 "
        "같은 `judgment_digest`)로 잰다고 적고 그것은 **검사기의** 술어다. 라이트업이 "
        "재는 것은 위 §(e) 의 재료가 봉투에 있는가까지다."
    )
    p.append("")

    probes = w.probe_observations
    negs = w.probe_candidates
    if probes or negs:
        p.append("## 부록 2. 하니스 프로브 — **풀이 경로가 아니다**")
        p.append("")
        p.append(
            "`source_ref`/`method` 가 `probe:` 로 시작하는 것들이다. `spec.md` §7 의 "
            "프로브는 술어를 **평가 가능하게** 만들려고 하니스가 개입하는 것이고, "
            "실행 주체가 고른 행동이 아니다. 실측에서 이것들은 정답 제출 **뒤에** 온다."
        )
        p.append("")
        for o in probes:
            p.append(f"- `{o.observation_id}` 출처 `{o.source_ref}` "
                     f"{_num(o.bytes_shown)}/{_num(o.bytes_total)} B"
                     + (" **잘림**" if o.truncated else ""))
        for cnd in negs:
            p.append(f"- 후보 `{cnd.value}` (method `{cnd.method}`) — 검증기가 거절해야 하는 값")
        p.append("")

    if w.self_reports:
        p.append("## 부록 3. 자기 보고 — **판정에 쓰지 않는다**")
        p.append("")
        p.append(
            "`spec.md` §0.3-3 (R2-12): 자기 보고는 기록하되 판정 입력이 아니다. "
            "출처가 다른 두 값을 나란히 싣는다. **`None` 은 부재이고 `0` 이 아니다.**"
        )
        p.append("")
        p.append("| 항목 | 밖에서 읽은 값 | 자기 보고 | 확인 주체 |")
        p.append("|---|---|---|---|")
        for sr in w.self_reports:
            p.append(
                f"| {sr.label} | {_val(sr.observed)} | {_val(sr.self_reported)} | "
                f"{('`' + sr.checked_by + '`') if sr.checked_by else '—'} |"
            )
        p.append("")

    if w.gaps:
        p.append("## 부록 4. 이 라이트업이 채우지 못한 자리")
        p.append("")
        p.append(
            "**비어 있는 것을 채운 것처럼 적지 않는다.** 아래는 봉투가 나르지 않아 "
            "생성기가 만들 수 없었던 것들이다."
        )
        p.append("")
        for g in w.gaps:
            p.append(f"- {g}")
        p.append("")

    if w.reader_notes:
        p.append("## 부록 5. 스트림 판독 주석")
        p.append("")
        for n in w.reader_notes:
            p.append(f"- {n}")
        p.append("")


# ---------------------------------------------------------------------------


def _shell_join(argv: tuple[str, ...]) -> str:
    return " ".join(a if _plain(a) else f"'{a}'" for a in argv)


def _plain(token: str) -> bool:
    return bool(token) and all(ch.isalnum() or ch in "-_./:=@" for ch in token)


def _yn(v: bool | None) -> str:
    """셋을 셋으로 적는다. **`None` 은 해당 없음이지 `없다` 가 아니다.**"""
    if v is None:
        return "해당 없음"
    return "**있다**" if v else "**없다**"


def _num(v: Any) -> str:
    return "부재" if v is None else str(v)


def _val(v: Any) -> str:
    return "**부재**" if v is None else f"`{v}`"
