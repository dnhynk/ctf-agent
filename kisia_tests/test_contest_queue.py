"""대회 큐 — smoke.

**진짜 자식 프로세스에 대고 잰다. 가짜 자식이지 가짜 프로세스가 아니다.**
`kisia.contest.run` 진입점은 아직 없고(W-3), 있어도 import 하지 않는다 — 큐와 run 은
**프로세스 경계로 갈린다**(`kisia/contest/__init__.py` 머리말). 그래서 여기서 띄우는
것은 `sys.executable -c` 로 만든 스크립트이고, 그것이 계약대로 stdout 마지막 줄에
`kisia.contest.result/1` 봉투를 낸다. `--max-wall-s-per-challenge` 가 **실제로 죽이는지**는
그렇게만 잴 수 있다(`O-54`).

**커버리지를 채우지 않는다** — `MVP_SCOPE.md` §2-8 이 신규 contest 경로를 smoke 로 잘랐다.
이 파일은 어떤 seam 술어 판정도 인용하지 못한다(`CLAUDE.md` §6.1-3).
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from kisia.contest import queue as q

# 자식 하나. argv[1] 의 계획대로 자고, 떠들고, 봉투를 내고, 정해진 코드로 죽는다.
FAKE_CHILD = (
    "import json, sys, time\n"
    "plan = json.loads(sys.argv[1])\n"
    "time.sleep(plan.get('sleep', 0))\n"
    "for line in plan.get('noise', []):\n"
    "    print(line)\n"
    "if plan.get('payload') is not None:\n"
    "    print(json.dumps(plan['payload']))\n"
    "sys.exit(plan.get('exit', 0))\n"
)


def _result(
    challenge_id: str,
    state: str,
    *,
    attempts: int = 1,
    usd: str | None = "0.0100",
    candidates: Iterable[str] = (),
    error: str | None = None,
) -> dict[str, Any]:
    """고정된 자식 계약 봉투 (`TASK` §3)."""
    return {
        "schema": "kisia.contest.result/1",
        "challenge_id": challenge_id,
        "state": state,
        "attempts": attempts,
        "candidates": list(candidates),
        "usd_spent": usd,
        "wall_s": 0.1,
        "streams": [],
        "last_rung": "deepen",
        "error": error,
    }


def _builder(plans: dict[str, dict[str, Any]], seen: list[str]) -> q.ArgvBuilder:
    def build_argv(spec: q.ChildSpec) -> list[str]:
        seen.append(spec.challenge_id)
        return [sys.executable, "-c", FAKE_CHILD, json.dumps(plans[spec.challenge_id])]

    return build_argv


class FakeDocker:
    """`DockerCli` 자리의 가짜. **docker 를 부르지 않는다.**

    `rc` 는 `present` 에 그 이름이 있으면 0(지웠다), 없으면 1(그런 것이 없다) 이다 —
    진짜 `docker rm` 이 하는 그대로다. `explode` 에 있는 이름은 **부르지도 못한** 경우를
    흉내 낸다(`docker` 실행 파일 없음·타임아웃).
    """

    def __init__(
        self,
        present: Iterable[str] = (),
        *,
        explode: Iterable[str] = (),
        **_ignored: Any,
    ) -> None:
        self.present = set(present)
        self.explode = set(explode)
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str, check: bool = True, **_kw: Any) -> Any:
        self.calls.append(args)
        name = args[-1]
        if name in self.explode:
            raise FileNotFoundError("docker 를 찾을 수 없다")
        rc = 0 if name in self.present else 1
        self.present.discard(name)
        return SimpleNamespace(argv=("docker", *args), rc=rc, out=b"", err="")


@pytest.fixture(autouse=True)
def _no_real_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    """**이 파일은 docker 를 부르지 않는다.** 진짜 `DockerCli` 가 서면 시험 결과가
    "이 기계에 docker 가 깔려 있는가"에 달리게 된다. 회수기를 실제로 재는 시험은
    가짜를 **명시적으로** 주입하고, 나머지는 이 기본값이 받는다."""
    monkeypatch.setattr(q, "DockerCli", FakeDocker)


def _queue(
    tmp_path: Path,
    ids: Iterable[str],
    *,
    flag_format: str | None = "kisia{...}",
) -> q.Queue:
    root = tmp_path / "challenges"
    for cid in ids:
        (root / cid).mkdir(parents=True)
    queue = q.build(
        root,
        queue_path=tmp_path / "queue.json",
        out_root=tmp_path / "out",
        flag_format=flag_format,
    )
    queue.save()
    return queue


# ---------------------------------------------------------------------------
# 자식 계약 — W-3 이 받는 argv 다. 바꾸면 여기서 깨진다
# ---------------------------------------------------------------------------


def test_default_argv_is_the_fixed_child_contract(tmp_path: Path) -> None:
    argv = q.default_argv(
        q.ChildSpec(
            python="PY",
            challenge_dir=tmp_path / "c",
            challenge_id="alpha",
            flag_format="kisia{...}",
            out_dir=tmp_path / "out" / "alpha",
            max_attempts=3,
            max_usd=Decimal("0.50"),
        )
    )
    assert argv[:3] == ["PY", "-m", "kisia.contest"]
    assert argv[-1] == "--json"
    for flag in ("--challenge", "--flag-format", "--challenge-id", "--out", "--max-attempts"):
        assert flag in argv
    assert argv[argv.index("--challenge-id") + 1] == "alpha"
    assert argv[argv.index("--max-usd") + 1] == "0.50"


def test_max_usd_is_omitted_when_there_is_no_money_box(tmp_path: Path) -> None:
    argv = q.default_argv(
        q.ChildSpec(
            python="PY",
            challenge_dir=tmp_path / "c",
            challenge_id="alpha",
            flag_format="kisia{...}",
            out_dir=tmp_path / "out" / "alpha",
            max_attempts=3,
            max_usd=None,
        )
    )
    assert "--max-usd" not in argv


# ---------------------------------------------------------------------------
# 상자 — 없으면 큐가 없는 것과 같다
# ---------------------------------------------------------------------------


def test_wall_box_kills_the_child_and_moves_on(tmp_path: Path) -> None:
    """시간 상자 소진 → 자식이 **죽는다** → `parked` → 다음 문제로 넘어간다 (`O-54`)."""
    queue = _queue(tmp_path, ["alpha", "bravo"])
    seen: list[str] = []
    plans = {
        "alpha": {"sleep": 30},  # 봉투를 낼 기회가 없다
        "bravo": {"payload": _result("bravo", "candidate", candidates=["kisia{b}"])},
    }
    runner = q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=3, max_wall_s_per_challenge=1.0),
        argv_builder=_builder(plans, seen),
    )
    runner.run()

    alpha = queue.by_id("alpha")
    assert alpha.state == "parked"
    assert alpha.note is not None and "벽시계 상자 소진" in alpha.note
    # **지출 미상을 0 으로 접지 않는다** (`CLAUDE.md` §6).
    assert alpha.usd_spent is None
    assert alpha.wall_s >= 1.0

    # 넘어갔다.
    assert seen == ["alpha", "bravo"]
    bravo = queue.by_id("bravo")
    assert bravo.state == "candidate"
    assert bravo.candidates == ["kisia{b}"]


def test_attempt_box_exhausted_is_parked_not_unsolved(tmp_path: Path) -> None:
    queue = _queue(tmp_path, ["alpha"])
    plans = {"alpha": {"payload": _result("alpha", "unsolved", attempts=3)}}
    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=3, max_wall_s_per_challenge=30.0),
        argv_builder=_builder(plans, []),
    ).run()

    alpha = queue.by_id("alpha")
    assert alpha.state == "parked"
    assert alpha.note is not None and "시도 상자 소진" in alpha.note


def test_money_box_exhausted_is_parked(tmp_path: Path) -> None:
    queue = _queue(tmp_path, ["alpha"])
    plans = {"alpha": {"payload": _result("alpha", "unsolved", attempts=1, usd="0.5000")}}
    q.QueueRunner(
        queue,
        boxes=q.Boxes(
            max_attempts=9,
            max_wall_s_per_challenge=30.0,
            max_usd_per_challenge=Decimal("0.50"),
        ),
        argv_builder=_builder(plans, []),
    ).run()

    alpha = queue.by_id("alpha")
    assert alpha.state == "parked"
    assert alpha.note is not None and "돈 상자 소진" in alpha.note


def test_total_budget_hard_stop_leaves_the_rest_pending(tmp_path: Path) -> None:
    """전역 상한은 하드 스톱이다. 남은 것은 **손대지 않고** `pending` 으로 남는다 —
    상자를 쓴 것이 아니므로 `parked` 가 아니다."""
    queue = _queue(tmp_path, ["alpha", "bravo", "charlie"])
    seen: list[str] = []
    plans = {
        cid: {"payload": _result(cid, "unsolved", attempts=1, usd="0.2000")}
        for cid in ("alpha", "bravo", "charlie")
    }
    q.QueueRunner(
        queue,
        boxes=q.Boxes(
            max_attempts=9,
            max_wall_s_per_challenge=30.0,
            total_usd_budget=Decimal("0.10"),
        ),
        argv_builder=_builder(plans, seen),
    ).run()

    assert seen == ["alpha"]  # 하나만 띄웠다
    assert queue.by_id("alpha").state == "unsolved"
    assert queue.by_id("bravo").state == "pending"
    assert queue.by_id("charlie").state == "pending"
    assert queue.by_id("bravo").note is None


# ---------------------------------------------------------------------------
# 여섯 상태를 접지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("plan", "expected", "note_fragment"),
    [
        ({"payload": _result("alpha", "candidate", candidates=["kisia{a}"])}, "candidate", "후보"),
        ({"payload": _result("alpha", "unsolved", attempts=1)}, "unsolved", "사다리를 끝까지"),
        ({"payload": _result("alpha", "error", error="boom")}, "error", "자식이 error"),
        ({"payload": _result("alpha", "unsolved"), "exit": 3}, "error", "자식 exit 3"),
        ({"noise": ["not json"]}, "error", "봉투를 내지 않았다"),
    ],
)
def test_states_are_distinguished(
    tmp_path: Path, plan: dict[str, Any], expected: str, note_fragment: str
) -> None:
    queue = _queue(tmp_path, ["alpha"])
    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=9, max_wall_s_per_challenge=30.0),
        argv_builder=_builder({"alpha": plan}, []),
    ).run()

    alpha = queue.by_id("alpha")
    assert alpha.state == expected
    assert alpha.note is not None and note_fragment in alpha.note


def test_a_child_reporting_another_challenge_id_is_an_error(tmp_path: Path) -> None:
    queue = _queue(tmp_path, ["alpha"])
    plans = {"alpha": {"payload": _result("bravo", "candidate", candidates=["kisia{x}"])}}
    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=9, max_wall_s_per_challenge=30.0),
        argv_builder=_builder(plans, []),
    ).run()

    alpha = queue.by_id("alpha")
    assert alpha.state == "error"
    assert alpha.candidates == []


# ---------------------------------------------------------------------------
# flag_format — 추측한 형식으로 돌리지 않는다 (`O-49`)
# ---------------------------------------------------------------------------


def test_unknown_flag_format_parks_without_spawning(tmp_path: Path) -> None:
    queue = _queue(tmp_path, ["alpha", "bravo"], flag_format=None)
    queue.by_id("bravo").flag_format = "hspace{...}"  # 항목별 덮어쓰기
    seen: list[str] = []
    plans = {"bravo": {"payload": _result("bravo", "unsolved", attempts=1)}}
    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=9, max_wall_s_per_challenge=30.0),
        argv_builder=_builder(plans, seen),
    ).run()

    alpha = queue.by_id("alpha")
    assert alpha.state == "parked"
    assert alpha.note == q.UNKNOWN_FLAG_FORMAT_NOTE
    assert seen == ["bravo"]  # alpha 는 **자식을 띄우지 않았다**


def test_item_flag_format_overrides_the_global_default(tmp_path: Path) -> None:
    queue = _queue(tmp_path, ["alpha"], flag_format="kisia{...}")
    queue.by_id("alpha").flag_format = "FINAL{...}"
    formats: list[str] = []

    def build_argv(spec: q.ChildSpec) -> list[str]:
        formats.append(spec.flag_format)
        payload = json.dumps({"payload": _result("alpha", "unsolved", attempts=1)})
        return [sys.executable, "-c", FAKE_CHILD, payload]

    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=9, max_wall_s_per_challenge=30.0),
        argv_builder=build_argv,
    ).run()
    assert formats == ["FINAL{...}"]


# ---------------------------------------------------------------------------
# 우선순위 · 재개 · 원자성
# ---------------------------------------------------------------------------


def test_operator_order_beats_points_beats_file_order(tmp_path: Path) -> None:
    queue = _queue(tmp_path, ["alpha", "bravo", "charlie"])
    queue.by_id("charlie").order = 1  # 운영자 지정이 무엇보다 앞선다
    queue.by_id("alpha").points = 100
    queue.by_id("bravo").points = 500
    seen: list[str] = []
    plans = {
        cid: {"payload": _result(cid, "unsolved", attempts=1)}
        for cid in ("alpha", "bravo", "charlie")
    }
    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=9, max_wall_s_per_challenge=30.0),
        argv_builder=_builder(plans, seen),
    ).run()
    assert seen == ["charlie", "bravo", "alpha"]


def test_resume_turns_running_back_into_pending(tmp_path: Path) -> None:
    """크래시했으므로 실제로 돌지 않았거나 결과를 못 받은 것이다. **둘 다 [틀렸다]가 아니다.**"""
    queue = _queue(tmp_path, ["alpha"])
    queue.by_id("alpha").state = "running"
    queue.save()

    reread = q.load(tmp_path / "queue.json")
    assert reread.by_id("alpha").state == "running"

    seen: list[str] = []
    plans = {"alpha": {"payload": _result("alpha", "candidate", candidates=["kisia{a}"])}}
    runner = q.QueueRunner(
        reread,
        boxes=q.Boxes(max_attempts=9, max_wall_s_per_challenge=30.0),
        argv_builder=_builder(plans, seen),
    )
    assert runner.resume() == ["alpha"]
    assert reread.by_id("alpha").state == "pending"
    assert reread.by_id("alpha").note == q.RESUMED_NOTE

    runner.run()  # 그리고 실제로 이어서 돈다
    assert seen == ["alpha"]
    assert reread.by_id("alpha").state == "candidate"


def test_queue_json_is_rewritten_atomically(tmp_path: Path) -> None:
    queue = _queue(tmp_path, ["alpha", "bravo"])
    plans = {
        "alpha": {"payload": _result("alpha", "candidate", candidates=["kisia{a}"])},
        "bravo": {"payload": _result("bravo", "unsolved", attempts=1)},
    }
    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=9, max_wall_s_per_challenge=30.0),
        argv_builder=_builder(plans, []),
    ).run()

    # 임시 파일이 남지 않는다.
    assert list(tmp_path.glob("*.tmp")) == []
    reread = q.load(tmp_path / "queue.json")
    assert reread.by_id("alpha").state == "candidate"
    assert reread.by_id("bravo").state == "unsolved"
    totals = reread.totals()
    assert totals["states"]["candidate"] == 1
    assert totals["usd_unknown_items"] == 0


def test_out_dir_is_split_per_challenge(tmp_path: Path) -> None:
    """`attempt_id` 접두가 겹치면 `writeup --out` 이 죽는다 (`D-64`)."""
    queue = _queue(tmp_path, ["alpha", "bravo"])
    outs: list[Path] = []

    def build_argv(spec: q.ChildSpec) -> list[str]:
        outs.append(spec.out_dir)
        payload = json.dumps({"payload": _result(spec.challenge_id, "unsolved", attempts=1)})
        return [sys.executable, "-c", FAKE_CHILD, payload]

    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=9, max_wall_s_per_challenge=30.0),
        argv_builder=build_argv,
    ).run()

    assert [p.name for p in outs] == ["alpha", "bravo"]
    assert len({str(p) for p in outs}) == 2
    assert all(p.is_dir() for p in outs)


def test_concurrency_runs_children_in_parallel(tmp_path: Path) -> None:
    """넷이 각각 2초씩 자는데, 순차라면 8초를 넘는다. 5초 안에 끝나면 겹쳐 돈 것이다."""
    queue = _queue(tmp_path, ["alpha", "bravo", "charlie", "delta"])
    plans = {
        cid: {"sleep": 2, "payload": _result(cid, "unsolved", attempts=1)}
        for cid in ("alpha", "bravo", "charlie", "delta")
    }
    runner = q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=9, max_wall_s_per_challenge=30.0),
        argv_builder=_builder(plans, []),
        concurrency=4,
    )
    started = time.monotonic()
    runner.run()
    elapsed = time.monotonic() - started

    assert all(i.state == "unsolved" for i in queue.items)
    assert sum(i.wall_s for i in queue.items) >= 8.0  # 자식 넷의 합은 그대로 8초 이상
    assert elapsed < 5.0  # 벽시계는 그렇지 않다


def test_init_scans_one_subdirectory_per_challenge(tmp_path: Path) -> None:
    root = tmp_path / "challenges"
    (root / "web-01").mkdir(parents=True)
    (root / "pwn-02").mkdir(parents=True)
    (root / "__pycache__").mkdir(parents=True)
    (root / "README.md").write_text("x", encoding="utf-8")

    rc = q.main(
        [
            "init",
            str(root),
            "--queue",
            str(tmp_path / "queue.json"),
            "--out-root",
            str(tmp_path / "out"),
            "--flag-format",
            "kisia{...}",
        ]
    )
    assert rc == 0
    queue = q.load(tmp_path / "queue.json")
    assert [i.challenge_id for i in queue.items] == ["pwn-02", "web-01"]
    assert queue.flag_format == "kisia{...}"
    assert all(i.state == "pending" for i in queue.items)


def test_run_cli_requires_the_boxes(tmp_path: Path) -> None:
    """상자 없이 큐만 돌리면 **큐가 없는 것과 같다** (`MVP_SCOPE.md` §5)."""
    with pytest.raises(SystemExit):
        q.main(["run", "--queue", str(tmp_path / "queue.json")])


# ---------------------------------------------------------------------------
# 회수기 — 호스트 실측 결함. 죽인 자식은 `finally` 를 돌지 않는다
# ---------------------------------------------------------------------------


def _leftovers(challenge_id: str, attempt: str = "02") -> list[str]:
    """호스트에서 실제로 남아 있던 것들 (2026-08-09 실측)."""
    return [
        f"kisia-{challenge_id}-{attempt}",
        f"kisia-{challenge_id}-{attempt}-net",
        f"kisia-{challenge_id}-{attempt}-input",
        f"kisia-{challenge_id}-{attempt}-work",
        f"kisia-{challenge_id}-{attempt}-artifacts",
    ]


def test_reap_targets_are_narrowed_to_this_challenge(tmp_path: Path) -> None:
    """**접두로 좁히는 것이 필수다** — 큐는 동시 실행 2~4 를 쓰고, 넓게 지우면 지금
    돌고 있는 남의 문제를 죽인다."""
    targets = q.reap_targets("chal-01", max_attempts=2)
    every = [*targets.containers, *targets.networks, *targets.volumes]

    assert every, "지울 이름이 하나도 없으면 회수기가 아니다"
    for name in every:
        assert "chal-01-01" in name or "chal-01-02" in name, name
    # 이름이 비슷한 남의 문제를 건드리지 않는다.
    assert not any("chal-011" in name or "chal-02" in name for name in every)
    # 유형 B 의 서비스 컨테이너는 `kisia-<challenge_id>-` 로 **시작하지 않는다**
    # (`agent_b.py:535`) — 접두 하나로 좁히면 그것을 놓친다.
    assert "kisia-r5-fix-b-chal-01-01" in targets.containers


def test_reap_order_is_containers_then_networks_then_volumes() -> None:
    """컨테이너가 붙어 있으면 네트워크·볼륨이 지워지지 않는다."""
    # 호스트에 남아 있던 것은 **두 번째 attempt** 의 것이었다 — 쓸기가 attempt 범위
    # 전체를 덮는다는 사실이 여기서 함께 잡힌다.
    cli = FakeDocker(_leftovers("chal-01"))
    report = q.reap(cli, "chal-01", max_attempts=2)

    verbs = [call[:2] for call in cli.calls]
    first_network = verbs.index(("network", "rm"))
    first_volume = verbs.index(("volume", "rm"))
    last_container = max(i for i, v in enumerate(verbs) if v == ("rm", "-f"))
    assert last_container < first_network < first_volume

    assert (report.containers, report.networks, report.volumes) == (1, 1, 3)
    assert report.ok


def test_reap_is_idempotent_and_says_zero(tmp_path: Path) -> None:
    """아무것도 없을 때 오류가 아니다. **0 건도 적는다** — 안 적으면 회수기가 돌았는지
    알 수 없다."""
    cli = FakeDocker()
    report = q.reap(cli, "chal-01", max_attempts=1)

    assert report.ok
    assert (report.containers, report.networks, report.volumes) == (0, 0, 0)
    assert report.note == "회수: 컨테이너 0 · 네트워크 0 · 볼륨 0"
    assert cli.calls, "부르지 않고 0 을 적으면 그것은 관측이 아니다"


def test_the_reaper_runs_before_the_child_and_after_a_kill(tmp_path: Path) -> None:
    """(a) 시작 전 — 앞선 실행의 잔존물을 지운다 → **재개가 산다.**
    (b) 죽인 뒤 — `SIGKILL` 된 자식은 `finally` 를 돌지 않았다."""
    queue = _queue(tmp_path, ["alpha"])
    cli = FakeDocker(_leftovers("alpha", "01"))
    plans = {"alpha": {"sleep": 30}}  # 상자를 소진시켜 죽인다
    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=1, max_wall_s_per_challenge=1.0),
        argv_builder=_builder(plans, []),
        docker=cli,
    ).run()

    alpha = queue.by_id("alpha")
    assert alpha.state == "parked", "회수는 상자 판정을 바꾸지 않는다"
    assert alpha.note is not None
    assert "벽시계 상자 소진" in alpha.note
    # 시작 전에 5건을 지웠고, 죽인 뒤에는 남은 것이 없다 — 자식이 가짜라 아무것도
    # 만들지 않았으므로 0 이 나오는 것이 맞다.
    assert "시작 전 회수: 컨테이너 1 · 네트워크 1 · 볼륨 3" in alpha.note
    assert "종료 뒤 회수: 컨테이너 0 · 네트워크 0 · 볼륨 0" in alpha.note
    assert not cli.present, "잔존물이 남았다"


def test_the_reaper_only_touches_its_own_challenge(tmp_path: Path) -> None:
    """동시 실행 중인 남의 문제를 죽이지 않는다."""
    queue = _queue(tmp_path, ["alpha"])
    cli = FakeDocker([*_leftovers("alpha", "01"), *_leftovers("bravo", "01")])
    plans = {"alpha": {"payload": _result("alpha", "unsolved", attempts=1)}}
    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=1, max_wall_s_per_challenge=30.0),
        argv_builder=_builder(plans, []),
        docker=cli,
    ).run()

    assert cli.present == set(_leftovers("bravo", "01")), "남의 것을 건드렸다"
    assert all("bravo" not in call[-1] for call in cli.calls)


def test_a_failing_reaper_makes_the_item_an_error(tmp_path: Path) -> None:
    """**조용히 넘기지 않는다.** 잔존물 위에서 도는 attempt 는 무엇을 잰 것인지
    정의되지 않는다."""
    queue = _queue(tmp_path, ["alpha"])
    cli = FakeDocker(explode=["kisia-alpha-01"])
    plans = {"alpha": {"payload": _result("alpha", "candidate", candidates=["kisia{a}"])}}
    seen: list[str] = []
    q.QueueRunner(
        queue,
        boxes=q.Boxes(max_attempts=1, max_wall_s_per_challenge=30.0),
        argv_builder=_builder(plans, seen),
        docker=cli,
    ).run()

    alpha = queue.by_id("alpha")
    assert alpha.state == "error"
    assert alpha.note is not None and "회수" in alpha.note and "FileNotFoundError" in alpha.note
    assert seen == [], "시작 전 회수가 실패하면 자식을 띄우지 않는다"
