"""`kisia.contest` — 진입점과 승격 사다리의 **smoke**.

**모델을 부르지 않고 컨테이너를 만들지 않는다.** `run_attempt` 는 가짜를 끼우고
(`NativeHarnessWorker(run_attempt=...)` 가 그 자리를 이미 연다), 그 가짜는 **진짜
봉투**를 낸다 — `EnvelopeWriter` 가 봉투 규칙(순서·필수 필드·통제 블록)을 전부
통과시킨 바이트다. 손으로 만든 jsonl 이 아니다.

**커버리지를 채우려 하지 않는다** — `MVP_SCOPE.md` §2-8 이 신규 contest 경로의 시험을
**smoke 만**으로 잘랐고 그것은 예선 뒤에 갚을 빚으로 적혀 있다.

**이 파일은 어떤 seam 판정도 인용하지 못한다**(`CLAUDE.md` §6.1-3). 여기서 재는 것은
배관이다: 매니페스트가 스키마를 만족하는가 · 라벨이 어디서 오는가 · stall 이 승격을
움직이는가 · 막힌 rung 이 크래시가 아니라 종료인가.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from kisia.checker.fixture import load_fixture
from kisia.contest import manifest as manifest_mod
from kisia.contest import run as contest_run
from kisia.orchestrator.scheduler import OPERATOR_LADDER, Rung, Scheduler
from kisia.runtime.telemetry.control import ControlBlock
from kisia.runtime.telemetry.envelope import EnvelopeWriter
from kisia_tests.conformance import _control

#: 사다리 앞 넷. rung 5·6 은 effort 가 미정이라 돌지 않는다.
RUNNABLE = tuple(r for r in OPERATOR_LADDER if r.is_runnable)


# ---------------------------------------------------------------------------
# 가짜 solver — 진짜 봉투를 낸다
# ---------------------------------------------------------------------------


def _write_stream(
    path: Path,
    *,
    attempt: str,
    outcome: str = "failed",
    label: str | None = None,
    solve_k: int | None = None,
    candidates: tuple[str, ...] = (),
    stalls: tuple[str, ...] = (),
    hypotheses: tuple[str, ...] = (),
    usd: str = "0.05",
) -> Path:
    block = _control(attempt=attempt)
    over: dict[str, Any] = {}
    if label is not None:
        over["accounting_label"] = label
    if solve_k is not None:
        over["solve_k"] = solve_k
    if over:
        block = ControlBlock.build({**block.values, **over})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        w = EnvelopeWriter(fh, run_id="test-contest", attempt_id=attempt, control=block)
        w.start()
        # 봉투는 두 모델 이벤트를 **짝으로** 요구한다.
        w.emit(
            "model.requested",
            {
                "model_id": "gpt-5.6-luna",
                "effort": "medium",
                "input_tokens": 10,
                "cached_tokens": 0,
                "cache_write_tokens": 0,
                "reasoning_tokens": 0,
                "prompt_digest": "sha256:" + "0" * 64,
                "observation_ids": [],
            },
        )
        w.emit(
            "model.completed",
            {"output_tokens": 10, "usd": usd, "latency_ms": 1, "finish_reason": "completed"},
        )
        for n, statement in enumerate(hypotheses, start=1):
            w.emit(
                "hypothesis.recorded",
                {
                    "hypothesis_id": f"hyp-{n:02d}",
                    "statement": statement,
                    "confidence": 0.5,
                    "supported_by": [],
                    "attempt_family": "test",
                    "turn": n,
                },
            )
        for signal in stalls:
            w.emit(
                "stall.observed",
                {
                    "signal": signal,
                    "window_turns": 3,
                    "confirmed_facts": [],
                    "attempt_family": "test",
                },
            )
        for value in candidates:
            w.emit(
                "candidate.produced",
                {"value": value, "derived_from": [], "method": "model_submission"},
            )
        w.emit("attempt.finished", {"outcome": outcome, "reason": "test", "wall_clock_s": 0.1})
    return path


def _faker(plan: list[dict[str, Any]], seen: list[dict[str, Any]]) -> Any:
    """`plan[i]` 이 i 번째 attempt 의 스트림 모양이다."""

    def fake_run_attempt(**kwargs: Any) -> dict[str, Any]:
        seen.append(dict(kwargs))
        shape = plan[len(seen) - 1] if len(seen) <= len(plan) else {}
        out = Path(kwargs["out_path"])
        _write_stream(
            out,
            attempt=str(kwargs["attempt"]),
            label=str(kwargs["accounting_label"]),
            solve_k=int(kwargs["solve_k"]),
            **shape,
        )
        return {"solved": False, "stream": str(out)}

    return fake_run_attempt


def _challenge(tmp_path: Path) -> Path:
    root = tmp_path / "chal"
    (root / "sub").mkdir(parents=True)
    (root / "chal.bin").write_bytes(b"\x00\x01binary payload")
    (root / "sub" / "notes.txt").write_text("two files, no readme\n", encoding="utf-8")
    return root


def _run(tmp_path: Path, plan: list[dict[str, Any]], **over: Any) -> dict[str, Any]:
    seen: list[dict[str, Any]] = []
    over.setdefault("ladder", RUNNABLE)
    result = contest_run.run_contest(
        challenge_dir=_challenge(tmp_path),
        out_dir=tmp_path / "out",
        flag_format="kisia{...}",
        max_attempts=over.pop("max_attempts", 4),
        run_attempt=_faker(plan, seen),
        # 이 시험 기계에는 SIGALRM 이 없을 수 있다 — 상한 자체는 따로 잰다.
        attempt_wall_s=0,
        **over,
    )
    result["_seen"] = seen
    return result


# ---------------------------------------------------------------------------
# ③-a 매니페스트 합성
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_synthesized_manifest_satisfies_kisia_fixture_1(tmp_path: Path) -> None:
    """`MANIFEST.md` §2 의 필수 필드와 §2.3.a 의 무정답 형태."""
    syn = manifest_mod.synthesize(
        challenge_dir=_challenge(tmp_path),
        root=tmp_path / "fx",
        flag_format="kisia{...}",
    )
    loaded = load_fixture(syn.root, expect_sha256=syn.manifest_sha256)
    m = loaded.manifest

    assert m["schema"] == "kisia.fixture/1"
    assert m["challenge_id"] == syn.challenge_id == "contest-chal"
    assert m["type"] == "A"
    assert m["provenance"] == "contest-derived"
    assert m["challenge_set"] == "contest"
    assert m["flag_format"] == "kisia{...}"
    for required in ("title", "provenance_note", "difficulty", "description"):
        assert str(m[required]).strip(), required
    # R5-10 — 풀어야 나오는 것을 풀기 전에 요구하지 않는다.
    assert "solution_path" not in m
    # §2.3.a — flag·flag_sha256·parts 는 **없다**. 검사기가 정답을 못 찾는 것이 정상이다.
    assert m["answer"] == {"verification": "deferred-manual", "note": m["answer"]["note"]}
    assert loaded.answer is None
    assert loaded.parts == {}
    assert loaded.declared_targets == []
    assert isinstance(m["display_limit_bytes"], int)


@pytest.mark.contract
def test_inputs_sha256_is_the_bundle_that_is_actually_mounted(tmp_path: Path) -> None:
    """`inputs[]` 는 **실제로 `/input` 에 들어가는 것**만 적는다 (`MANIFEST.md` §2.4).

    `agent_a.run_attempt` 가 넣는 것은 `fixture.bundle` 하나이므로, 원본 파일별 해시는
    `contest_source_files[]` 가 따로 나른다.
    """
    import hashlib

    syn = manifest_mod.synthesize(
        challenge_dir=_challenge(tmp_path), root=tmp_path / "fx", flag_format="kisia{...}"
    )
    m = json.loads(syn.manifest_path.read_text(encoding="utf-8"))
    bundle = (syn.root / "input" / "bundle.tar.gz").read_bytes()

    assert [i["path"] for i in m["inputs"]] == ["bundle.tar.gz"]
    assert m["inputs"][0]["sha256"] == hashlib.sha256(bundle).hexdigest()
    assert m["inputs"][0]["bytes"] == len(bundle)

    listed = {s["path"]: s for s in m["contest_source_files"]}
    assert set(listed) == {"chal.bin", "sub/notes.txt"}
    raw = (tmp_path / "chal" / "chal.bin").read_bytes()
    assert listed["chal.bin"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert listed["chal.bin"]["bytes"] == len(raw)


@pytest.mark.unit
def test_description_comes_from_the_challenge_and_is_not_invented(tmp_path: Path) -> None:
    """운영자 파일 > README > **관측한 사실**. 문제를 지어내지 않는다."""
    root = _challenge(tmp_path)
    minimal = manifest_mod.synthesize(
        challenge_dir=root, root=tmp_path / "a", flag_format="k{...}"
    )
    text = json.loads(minimal.manifest_path.read_text(encoding="utf-8"))["description"]
    assert "No challenge description was provided" in text
    assert "chal.bin" in text and "sub/notes.txt" in text

    (root / "README.md").write_text("Find the flag in the blob.", encoding="utf-8")
    from_readme = manifest_mod.synthesize(
        challenge_dir=root, root=tmp_path / "b", flag_format="k{...}"
    )
    assert (
        json.loads(from_readme.manifest_path.read_text(encoding="utf-8"))["description"]
        == "Find the flag in the blob."
    )

    given = manifest_mod.synthesize(
        challenge_dir=root, root=tmp_path / "c", flag_format="k{...}", description="운영자가 준 것"
    )
    assert json.loads(given.manifest_path.read_text(encoding="utf-8"))["description"] == (
        "운영자가 준 것"
    )


@pytest.mark.unit
def test_an_empty_flag_format_is_refused(tmp_path: Path) -> None:
    """`O-49` — 기본값 없는 필수 통제 필드다. 미상이면 attempt 가 시작조차 못 한다."""
    with pytest.raises(manifest_mod.ManifestError, match="flag_format"):
        manifest_mod.synthesize(
            challenge_dir=_challenge(tmp_path), root=tmp_path / "fx", flag_format="  "
        )


# ---------------------------------------------------------------------------
# ③-b 진입점
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_service_makes_a_type_b_manifest_instead_of_being_refused(tmp_path: Path) -> None:
    """예선에 서비스(nc/http) 문항이 있다 — 거부하면 그 범주를 통째로 0점 처리한다.

    `MVP_SCOPE.md` §1.5 가 금지한 트레이드 오프이므로 배선한다.
    """
    from kisia.runtime.golden_b import SERVICE_NAME, SERVICE_PORT

    syn = manifest_mod.synthesize(
        challenge_dir=_challenge(tmp_path),
        root=tmp_path / "fx",
        flag_format="kisia{...}",
        service=manifest_mod.ServiceTarget(host=SERVICE_NAME, port=SERVICE_PORT),
    )
    m = load_fixture(syn.root, expect_sha256=syn.manifest_sha256).manifest

    assert m["type"] == "B"
    # `agent_b.run_attempt` 는 이 둘을 **매니페스트에서만** 읽고 없으면 죽는다.
    assert m["target"]["host"] == SERVICE_NAME
    assert m["target"]["port"] == SERVICE_PORT
    # S2.4 / P-S2-c 의 판정 기준 — 여기 있는 것에는 닿고 없는 것에는 닿지 않는다.
    assert m["workspace"]["declared_targets"] == [f"{SERVICE_NAME}:{SERVICE_PORT}"]
    # `spec.md` §5 하중표의 유형 B 행. 봉인된 b-session 매니페스트에서 그대로 왔다.
    assert m["seams_loaded"] == ["S2", "S4", "S5", "S6", "S7", "S8", "S9"]
    # 유형 B 의 프롬프트는 `/input` 을 한 번도 말하지 않는다 (실측) — 첨부가 있으면
    # 그 사실을 문제 기술이 날라야 한다.
    assert "/input/bundle.tar.gz" in m["description"]


@pytest.mark.unit
def test_a_service_challenge_may_ship_no_files_at_all(tmp_path: Path) -> None:
    """`nc host port` 하나가 전부인 문항이 실제로 그렇다. `inputs: []` 는 유효하고
    그 경우 S1 은 N/A 다 (`MANIFEST.md` §2.4, R2-16)."""
    empty = tmp_path / "svc"
    empty.mkdir()

    syn = manifest_mod.synthesize(
        challenge_dir=empty,
        root=tmp_path / "fx",
        flag_format="kisia{...}",
        service=manifest_mod.ServiceTarget(host="svc", port=1337),
    )
    m = json.loads(syn.manifest_path.read_text(encoding="utf-8"))
    assert m["inputs"] == []
    assert not (syn.root / "input" / "bundle.tar.gz").exists()
    assert "no files" in m["description"]

    # 유형 A 에서는 여전히 오류다 — 파일도 서비스도 없으면 풀 대상이 없다.
    with pytest.raises(manifest_mod.ManifestError, match="파일이 없다"):
        manifest_mod.synthesize(
            challenge_dir=empty, root=tmp_path / "fx2", flag_format="kisia{...}"
        )


@pytest.mark.contract
def test_the_solver_is_chosen_by_type_without_a_dispatcher(tmp_path: Path) -> None:
    """**하나로 덮는 디스패처를 세우지 않는다** (`native.py` 머리말). 갈리는 것은
    이 함수 하나이고 두 `run_attempt` 의 시그니처는 그대로다."""
    from kisia.runtime import agent_a, agent_b

    assert contest_run.solver_impl(None) is agent_a.run_attempt
    assert contest_run.solver_impl("some/service:tag") is agent_b.run_attempt
    assert contest_run._probes_for(None) == tuple(agent_a.PROBES)
    assert contest_run._probes_for("some/service:tag") == tuple(agent_b.PROBES)


@pytest.mark.contract
def test_a_type_b_run_hands_the_service_image_to_the_solver(tmp_path: Path) -> None:
    """`service_image` 는 `Assignment` 이 아니라 **배치의 사실**이라 `fixed` 로 간다."""
    result = _run(tmp_path, [{}, {}, {}], service_image="ctf/svc:tag", service_port=31337)

    seen = result["_seen"][0]
    assert seen["service_image"] == "ctf/svc:tag"
    # 통제 블록의 두 갈래도 함께 간다 — 러너의 기본값 dev/synthetic 이 남으면 대회
    # 스트림이 dev 세트의 자작 챌린지로 기록된다 (R5-10).
    assert seen["challenge_set"] == "contest"
    assert seen["provenance"] == "contest-derived"

    m = json.loads((tmp_path / "out" / "fixture" / "manifest.json").read_text("utf-8"))
    assert m["type"] == "B"
    assert m["target"]["port"] == 31337


@pytest.mark.contract
def test_the_type_a_path_is_unchanged(tmp_path: Path) -> None:
    """회귀 — 서비스를 주지 않으면 이 변경 전과 한 글자도 다르지 않아야 한다."""
    from kisia.runtime import agent_a

    result = _run(tmp_path, [{}, {}, {}])
    m = json.loads((tmp_path / "out" / "fixture" / "manifest.json").read_text("utf-8"))

    assert m["type"] == "A"
    assert m["target"] is None
    assert m["workspace"]["declared_targets"] == []
    assert m["seams_loaded"] == ["S1", "S2", "S3", "S4", "S5", "S7", "S8", "S9"]
    assert m["probes"] == list(agent_a.PROBES)
    assert "service_image" not in result["_seen"][0]
    assert "/input/bundle.tar.gz" not in m["description"], (
        "유형 A 의 프롬프트가 이미 그것을 나른다 — 두 벌로 적지 않는다"
    )


@pytest.mark.unit
def test_service_host_and_port_without_an_image_are_refused(tmp_path: Path) -> None:
    """이미지가 없으면 띄울 서비스가 없다 — 조용히 무시하면 유형 A 로 도는데 대상만
    선언된 매니페스트가 나온다."""
    with pytest.raises(contest_run.ContestError, match="--service"):
        contest_run.run_contest(
            challenge_dir=_challenge(tmp_path),
            out_dir=tmp_path / "out",
            flag_format="kisia{...}",
            max_attempts=1,
            service_port=9999,
            run_attempt=lambda **_: {},
            attempt_wall_s=0,
        )


@pytest.mark.contract
def test_the_result_json_is_the_last_line_of_stdout_and_nothing_else_is(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """큐가 읽는 것은 그 줄 하나다 (`kisia/contest/__init__.py`)."""
    seen: list[dict[str, Any]] = []

    def noisy(**kwargs: Any) -> dict[str, Any]:
        print("solver 가 stdout 에 지껄인다")
        return _faker([{"candidates": ("kisia{found}",)}], seen)(**kwargs)

    monkeypatch.setattr(contest_run, "DEFAULT_RUN_ATTEMPT", noisy)
    for name in (
        contest_run.ENV_API_KEY,
        contest_run.ENV_IMAGE,
        contest_run.ENV_PROBE,
        contest_run.ENV_PROBE_ID,
    ):
        monkeypatch.setenv(name, "x")

    code = contest_run.main(
        [
            "--challenge", str(_challenge(tmp_path)),
            "--flag-format", "kisia{...}",
            "--out", str(tmp_path / "out"),
            "--max-attempts", "2",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    lines = captured.out.splitlines()
    assert len(lines) == 1, f"stdout 에 결과 줄 말고 다른 것이 있다: {lines}"
    result = json.loads(lines[0])
    assert result["schema"] == "kisia.contest.result/1"
    assert result["state"] == "candidate"
    assert result["candidates"] == ["kisia{found}"]
    assert "solver 가 stdout 에 지껄인다" in captured.err


@pytest.mark.contract
def test_the_result_carries_the_schema_and_the_stop_reason(tmp_path: Path) -> None:
    result = _run(tmp_path, [{}, {}, {"candidates": ("kisia{abc}",)}, {}])
    assert result["schema"] == "kisia.contest.result/1"
    assert result["challenge_id"] == "contest-chal"
    assert result["state"] == "candidate"
    assert result["candidates"] == ["kisia{abc}"]
    assert result["attempts"] == 3, "후보가 나오면 그 문제의 사다리를 멈춘다"
    assert result["last_rung"] == "execute"
    assert result["usd_spent"] == "0.1500"
    assert len(result["streams"]) == 3
    assert result["error"] is None


@pytest.mark.unit
def test_no_candidate_is_unsolved_and_never_solved(tmp_path: Path) -> None:
    """무정답 모드에서 `solved` 는 우리가 말할 수 있는 값이 아니다."""
    result = _run(tmp_path, [{}, {}, {}, {}])
    assert result["state"] == "unsolved"
    assert result["candidates"] == []


@pytest.mark.unit
def test_the_money_box_stops_the_ladder(tmp_path: Path) -> None:
    result = _run(tmp_path, [{"usd": "0.4"}, {"usd": "0.4"}, {}], max_usd=Decimal("0.5"))
    assert result["attempts"] == 2
    assert result["usd_spent"] == "0.8000"
    assert result["state"] == "unsolved"
    # **상자는 attempt 안에서도 걸린다** — 사이에서만 보면 넘긴 것이 보일 때는 이미 썼다.
    assert [k["usd_budget"] for k in result["_seen"]] == [Decimal("0.5"), Decimal("0.1")]


# ---------------------------------------------------------------------------
# ④ 승격 사다리
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_contest_runs_are_labelled_contest_with_the_attempt_number(tmp_path: Path) -> None:
    """`R5-9` — contest run 은 `clean_solve@1` 의 분자에도 분모에도 안 들어간다.
    라벨이 그것을 나르므로 시도 번호와 무관하게 `contest` 다."""
    result = _run(tmp_path, [{}, {}, {}])
    labels = [(k["accounting_label"], k["solve_k"]) for k in result["_seen"]]
    assert labels == [("contest", 1), ("contest", 2), ("contest", 3)]


@pytest.mark.unit
def test_outside_contest_the_first_attempt_is_still_clean(tmp_path: Path) -> None:
    """`O-57` 이 옮긴 것은 **출처**이지 규칙이 아니다 — dev 세트의 파생은 그대로다."""
    from kisia.evidence import EvidenceStore
    from kisia.orchestrator import Orchestrator

    orc = Orchestrator(
        store=EvidenceStore(tmp_path / "ev"),
        scheduler=Scheduler(RUNNABLE),
        solver=lambda a: (_ for _ in ()).throw(AssertionError("돌리지 않는다")),
    )
    ch = orc.submit("ch-01")
    first = orc.next_assignment(ch)
    assert first is not None
    assert (first.accounting_label, first.solve_k) == ("clean", 1)


@pytest.mark.contract
def test_a_stall_promotes_to_rung_four_and_its_absence_ends_the_ladder(
    tmp_path: Path,
) -> None:
    """운영자의 rung 4 는 순서가 아니라 **조건**이다 — *"새 증거 없이 3회 반복 /
    같은 가설 2회"*. 조건이 관측되면 건너뛰고, 관측되지 않으면 그 앞에서 끝난다."""
    stalled = _run(
        tmp_path / "s",
        [{"stalls": ("no_new_observation",)}, {}, {}, {}],
        ladder=RUNNABLE,
    )
    assert [k["effort"] for k in stalled["_seen"]] == ["medium", "xhigh"], (
        "첫 attempt 에서 stall 을 봤으므로 plan·execute 를 건너뛰고 deepen 으로 간다"
    )
    assert stalled["last_rung"] == "deepen"

    quiet = _run(tmp_path / "q", [{}, {}, {}, {}], ladder=RUNNABLE)
    assert quiet["attempts"] == 3, "stall 이 없으면 deepen 앞에서 사다리가 끝난다"
    assert quiet["last_rung"] == "execute"


@pytest.mark.unit
def test_the_same_hypothesis_twice_is_also_a_stall(tmp_path: Path) -> None:
    """운영자가 적은 둘째 숫자다. **다른 숫자를 쓰지 않는다.**"""
    once = _run(tmp_path / "a", [{"hypotheses": ("the key is in the header",)}, {}, {}, {}])
    assert once["last_rung"] == "execute", "한 번은 되풀이가 아니다"

    twice = _run(
        tmp_path / "b",
        [{"hypotheses": ("the key is in the header", "the key is in the header")}, {}],
    )
    assert twice["last_rung"] == "deepen"


@pytest.mark.unit
def test_a_probe_candidate_is_not_reported_as_a_candidate(tmp_path: Path) -> None:
    """`A-4` 는 하니스가 **일부러 어긋나게** 만든 값이다 — 올리면 운영자가 틀린 것을
    제출한다."""
    from kisia.orchestrator.native import read_stream_outcome

    path = tmp_path / "s.jsonl"
    block = _control(attempt="a01")
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        w = EnvelopeWriter(fh, run_id="r", attempt_id="a01", control=block)
        w.start()
        w.emit(
            "candidate.produced",
            {"value": "kisia{wrong}", "derived_from": [], "method": "probe:A-4"},
        )
        w.emit(
            "candidate.produced",
            {"value": "kisia{mine}", "derived_from": [], "method": "model_submission"},
        )
        w.emit("attempt.finished", {"outcome": "failed", "reason": "t", "wall_clock_s": 0.1})

    read = read_stream_outcome(path)
    assert read.candidates == ("kisia{mine}",)


@pytest.mark.contract
def test_a_blocked_promotion_ends_the_run_instead_of_crashing(tmp_path: Path) -> None:
    """rung 5·6 은 `reasoning_effort` 가 미정이다. 값은 운영자가 주고 이 코드가 고르지
    않으며, 그 사이에도 **결과 한 줄은 나가야 한다.**"""
    result = _run(
        tmp_path,
        [{"stalls": ("budget_burn",)}, {}, {}, {}, {}],
        ladder=OPERATOR_LADDER,
        max_attempts=6,
    )
    assert result["last_rung"] == "deepen"
    assert result["state"] == "unsolved"
    assert result["error"] is None, "막힌 승격은 오류가 아니라 사다리의 끝이다"


@pytest.mark.unit
def test_a_solver_crash_becomes_a_result_line_not_a_traceback(tmp_path: Path) -> None:
    def boom(**_: Any) -> dict[str, Any]:
        raise RuntimeError("docker 가 없다")

    result = contest_run.run_contest(
        challenge_dir=_challenge(tmp_path),
        out_dir=tmp_path / "out",
        flag_format="kisia{...}",
        max_attempts=2,
        run_attempt=boom,
        ladder=RUNNABLE,
        attempt_wall_s=0,
    )
    assert result["state"] == "error"
    assert "docker 가 없다" in str(result["error"])
    assert result["attempts"] == 0


# ---------------------------------------------------------------------------
# ④-d escalation 패킷
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_the_escalation_packet_rides_into_the_next_problem_statement(tmp_path: Path) -> None:
    """없으면 강한 모델이 **맥락 없이 맨몸으로** 받는다 (`MVP_SCOPE.md` §1.5).

    운영자가 rung 5 의 effort 를 아직 주지 않았으므로 **여기서는 그 자리에 값을 넣은
    사다리로 잰다** — 값이 오는 순간 이 배선이 도는지를 미리 재는 것이고, 값 자체를
    고르는 것이 아니다(`OPERATOR_LADDER` 는 건드리지 않았다).
    """
    ladder = (*RUNNABLE, Rung("escalate", "gpt-5.6-sol", "high", "시험 전용"))
    result = _run(
        tmp_path,
        [
            {"stalls": ("no_new_observation",)},
            # **패킷은 직전 attempt 의 스트림에서 온다** — 여기 실린 가설이 다음 문제
            # 기술의 INFERRED 절이 된다.
            {"stalls": ("repeated_action",), "hypotheses": ("the header is a decoy",)},
            {},
        ],
        ladder=ladder,
        max_attempts=3,
    )

    assert [k["model_id"] for k in result["_seen"]] == [
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "gpt-5.6-sol",
    ]
    escalated = result["_seen"][-1]["fixture"]
    description = json.loads(
        (Path(escalated.root) / "manifest.json").read_text(encoding="utf-8")
    )["description"]
    assert "escalation packet" in description
    assert "the header is a decoy" in description, "INFERRED 절이 실려야 한다"

    packet = tmp_path / "out" / "evidence" / "escalation" / "contest-chal-02" / "packet.json"
    assert packet.is_file(), "패킷은 PATH_SCOPE.md §3.7 의 자리에도 남는다"


# ---------------------------------------------------------------------------
# ④-f 벽시계 상한
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_wall_clock_ceiling_is_the_declared_attempt_timeout(tmp_path: Path) -> None:
    """`attempt_timeout_s: 900` 은 통제 블록이 **선언만** 하고 강제하는 코드가 없다
    (실측). 이 상한은 그 선언된 값이지 새로 고른 숫자가 아니다."""
    assert _control(attempt="x").values["attempt_timeout_s"] == contest_run.ATTEMPT_WALL_S


@pytest.mark.unit
def test_a_platform_without_sigalrm_says_so_instead_of_pretending(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """*"걸었다"고 적지 않는다* — 걸지 못한 것과 상한이 없는 것은 다른 사실이다."""
    import signal as signal_mod

    monkeypatch.delattr(signal_mod, "SIGALRM", raising=False)
    with contest_run._deadline(900) as armed:
        assert armed is False
    assert "SIGALRM" in capsys.readouterr().err
