"""queue — **대회 전체**를 치른다. 순서 · 상자 · 넘어가기 · 재개.

`MVP_SCOPE.md` §4.1: *"한 문제를 푸는 것과 대회를 치르는 것은 다르다. 예선에는 문제가
수십 개이고, 점수를 가르는 것은 대부분 어느 것을 먼저·얼마나 붙잡고·언제 넘어가는가다."*
그 층이 없으면 **첫 문제가 예산과 시간을 전부 먹고 대회가 끝난다.** 개발 로드가 아니라
성능이다.

**프로세스 경계다.** 이 모듈은 `kisia.contest.run` 을 import 하지 않고 `python -m
kisia.contest` 를 **자식 프로세스로** 띄운다 (`kisia/contest/__init__.py` 머리말).
그래야 `--max-wall-s-per-challenge` 를 **실제로 죽여서** 강제할 수 있다 — `O-54`(도달
불가 endpoint 에서 워커가 90초에도 안 죽는다)를 큐 층에서 막는 자리가 여기 하나뿐이다.
그리고 한 문제의 크래시가 대회를 끝내지 않는다.

**판정하지 않는다.** `candidate` 는 `solved` 가 아니다. 라이브 대회에서 맞았는지는
운영자가 플랫폼에서 확인한다(`MANIFEST.md` §2.3.a `verification: deferred-manual`).
같은 이유로 `parked` 는 `failed` 가 아니다 — **"시간이 없었다"를 "틀렸다"로 접지
않는다**(`D-63`, `CLAUDE.md` §6). 접으면 나중에 어느 문제를 다시 붙어야 하는지 잃는다.

**`queue.json` 이 곧 수동 인터페이스다**(`MVP_SCOPE.md` §4.1). 운영자가 대회 중간에
열어 `order` 를 바꾸고 항목을 지운다. 운영 UI 는 없다(`CONTEST_ARCHITECTURE.md` §13).
그래서 상태 전이마다 **원자적으로** 다시 쓴다 — 반쯤 쓰인 파일을 운영자가 여는 자리가
없어야 한다.

**항목별 `flag_format` 을 받는 것에 관하여 — 문서와 갈린다.** `MVP_SCOPE.md` §4.1 의
표는 *"항목별 덮어쓰기를 만들지 않는다"* 로 적혀 있고(운영자 확인 2026-08-09: 예선 전
문항 동일), 이 트랙의 지시는 *"항목별은 그대로 받아라 — 본선에서 갈릴 수 있다"* 였다.
**둘 다 적어 둔다.** 코드는 지시를 따랐고, 예선에서는 전역 하나로 끝나므로 두 문서가
가리키는 실행 경로는 같다. 갈리는 것은 본선뿐이다.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from kisia.runtime.docker_cli import DockerCli

QUEUE_SCHEMA = "kisia.contest.queue/1"

#: 자식이 stdout 마지막 줄에 내는 봉투. **이 모듈은 `kisia.contest.run` 을 import 하지
#: 않으므로** 이 문자열이 두 층 사이의 유일한 계약이다.
RESULT_SCHEMA = "kisia.contest.result/1"

#: 여섯. **접지 마라** — `parked`(상자를 다 썼다) · `unsolved`(사다리를 끝까지 갔는데
#: 후보가 없다) · `error`(자식이 비정상 종료했다)는 서로 다른 사실이다.
STATES: frozenset[str] = frozenset(
    {"pending", "running", "candidate", "parked", "unsolved", "error"}
)

#: 지시가 이 문자열을 그대로 지목했다. 추측한 형식으로 돌리면 **조용히 전부 오답이 된다**
#: (`O-49`: `flag_format` 은 기본값 없는 필수 통제 필드).
UNKNOWN_FLAG_FORMAT_NOTE = "flag_format 미상 — 운영자 확인 필요"

RESUMED_NOTE = "재개: 이전 실행이 running 인 채로 죽었다 — 결과를 받지 못했다. [틀렸다]가 아니다"


class QueueError(RuntimeError):
    """큐 파일을 읽을 수 없거나 계약을 만족하지 않는다."""


# ---------------------------------------------------------------------------
# 자식 프로세스 계약 — 이미 고정됐다
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChildSpec:
    """자식 하나를 띄우는 데 필요한 전부. **비밀은 여기 없다**(`O-11` — argv 에 넣지 않는다)."""

    python: str
    challenge_dir: Path
    challenge_id: str
    flag_format: str
    out_dir: Path
    max_attempts: int
    max_usd: Decimal | None


def default_argv(spec: ChildSpec) -> list[str]:
    """고정된 자식 argv. `kisia.contest.run`(W-3)이 받는 형태다."""
    argv = [
        spec.python,
        "-m",
        "kisia.contest",
        "--challenge",
        str(spec.challenge_dir),
        "--flag-format",
        spec.flag_format,
        "--challenge-id",
        spec.challenge_id,
        "--out",
        str(spec.out_dir),
        "--max-attempts",
        str(spec.max_attempts),
    ]
    if spec.max_usd is not None:
        argv += ["--max-usd", str(spec.max_usd)]
    argv.append("--json")
    return argv


#: 시험이 덮어쓰는 자리. **실제 진입점에 의존하지 않는다** — 프로세스 경계이므로
#: import 로 대신할 수 없고, 진입점이 아직 없어도 이 층은 시험할 수 있어야 한다.
ArgvBuilder = Callable[[ChildSpec], list[str]]


@dataclass(frozen=True)
class ChildOutcome:
    """자식 하나가 끝난 뒤 **우리가 관찰한** 것. 자식의 자기 보고는 `stdout` 안에 있다."""

    timed_out: bool
    returncode: int | None
    stdout: str
    stderr: str
    wall_s: float
    spawn_error: str | None = None


def parse_result(stdout: str) -> dict[str, Any] | None:
    """stdout 의 **마지막 비어 있지 않은 줄**을 결과 봉투로 읽는다. 아니면 `None`."""
    for raw in reversed(stdout.splitlines()):
        line = raw.strip()
        if not line:
            continue
        try:
            payload: Any = json.loads(line)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict) and payload.get("schema") == RESULT_SCHEMA:
            return payload
        return None
    return None


def _kill_tree(proc: subprocess.Popen[str]) -> None:
    """자식 **트리**를 죽인다. 자식만 죽이면 손자(docker exec·nc)가 살아남는다.

    POSIX 는 `start_new_session=True` 로 띄운 프로세스 그룹을 통째로 죽이고, Windows 는
    `Popen.kill()` 로 족하다. **호스트는 리눅스이고 개발은 Windows 다** — 둘 다 돈다.
    """
    if sys.platform == "win32":  # pragma: no cover - 호스트는 리눅스다
        proc.kill()
        return
    try:
        os.killpg(os.getpgid(proc.pid), 9)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()


def spawn(argv: list[str], *, timeout_s: float | None) -> ChildOutcome:
    """자식 하나를 띄우고 끝날 때까지 기다린다. `timeout_s` 를 넘기면 **죽인다**."""
    popen_kwargs: dict[str, Any] = {}
    if sys.platform != "win32":
        # 프로세스 **그룹**을 갈라야 `os.killpg` 가 손자까지 닿는다.
        popen_kwargs["start_new_session"] = True

    started = time.monotonic()
    try:
        proc = subprocess.Popen(  # noqa: S603
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **popen_kwargs,
        )
    except OSError as exc:
        return ChildOutcome(
            timed_out=False,
            returncode=None,
            stdout="",
            stderr="",
            wall_s=time.monotonic() - started,
            spawn_error=str(exc),
        )

    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        timed_out = False
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        # 죽인 뒤 남은 출력을 회수한다. 이 두 번째 `communicate` 가 문서화된 형태다.
        stdout, stderr = proc.communicate()
        timed_out = True
    return ChildOutcome(
        timed_out=timed_out,
        returncode=proc.returncode,
        stdout=stdout or "",
        stderr=stderr or "",
        wall_s=time.monotonic() - started,
    )


# ---------------------------------------------------------------------------
# 회수기 — **죽인 자식은 `finally` 를 돌지 않는다**
# ---------------------------------------------------------------------------
#
# 호스트 실측 2026-08-09 (coordinator 가 `ssh CTF-agent` 에서 큐를 두 번 돌렸다):
#
# 1. `--max-wall-s-per-challenge 75` → 두 문제 다 `parked`. **큐는 옳게 동작했다.**
# 2. 같은 문제를 다시 → 두 문제 다 `error`:
#    `docker network create --internal kisia-chal-01-02-net → rc=1
#     network with name ... already exists`
# 3. 잔존: 컨테이너 `kisia-chal-0{1,2}-02` **Up 2~3 minutes** · 네트워크 두 개 ·
#    볼륨 여섯 개.
#
# **사실 둘.** ① `Workspace.destroy()` 는 `run_attempt` 의 `finally` 에 있는데
# `SIGKILL` 된 프로세스는 `finally` 를 돌지 않는다 — 상자를 쓸 때마다 컨테이너·
# 네트워크·볼륨이 영구히 쌓인다. ② 이름이 결정적이라 그 잔존물이 **다음 실행과
# 충돌한다** — 죽였던 문제를 다시 붙을 수 없고, 그것이 `MVP_SCOPE.md` §4.1 이 요구한
# **재개**를 무력화한다. 죽이는 것이 큐의 핵심 기제인데 정리가 없으면 그 기제는 한 번
# 밖에 못 쓰인다.
#
# **왜 `docker ps --filter name=^…` 을 쓰지 않는가 — 재지 못했기 때문이다.**
# 이 저장소는 `--filter` 를 한 번도 쓴 적이 없고(`grep -rn -- --filter kisia/`: 프록시의
# 주석 한 줄뿐이다), 이 기계에는 docker 가 없어 그 정규식 문법이 접두로 앵커되는지
# **확인할 수 없다.** 대신 **이름을 만들어서 지운다** — 규칙 전부가 실측이고(아래 표),
# 그러면 접두 필터보다 **더 좁다**: 그 문제의 그 attempt 이름 말고는 아무것도 인자로
# 나가지 않으므로 동시에 도는 남의 문제를 죽일 자리가 구조적으로 없다.
# 지우는 명령 셋은 `Workspace.destroy()` 가 호스트에서 이미 행사하던 그대로다
# (`rm -f` → `network rm` → `volume rm`, 전부 `check=False`).
#
# | 자원 | 이름 | 출처(실측) |
# |---|---|---|
# | 워커 컨테이너 | `kisia-{attempt}` | `workspace.py:92` |
# | 적재용 임시 컨테이너 | `kisia-{attempt}-loader` | `workspace.py:173` |
# | 서비스 컨테이너(유형 B) | `kisia-r5-fix-b-{attempt}` | `agent_b.py:535` + `golden_b.py:66` |
# | 네트워크 | `kisia-{attempt}-net` | `workspace.py:93` |
# | 볼륨 셋 | `kisia-{attempt}-{input,work,artifacts}` | `workspace.py:94` + `MOUNT_SPEC` |
# | attempt id | `{challenge_id}-{NN:02d}` | `orchestrator.next_assignment` |
#
# **유형 B 의 서비스 컨테이너는 `kisia-<challenge_id>-` 로 시작하지 않는다.** 접두
# 하나로 좁히면 그것을 놓치고, 서비스 컨테이너가 문제마다 살아남는다.

#: `MOUNT_SPEC` 의 이름 셋. **여기서 다시 정하지 않는다** — `workspace.py` 가 정본이고
#: 이 목록은 그것의 전사다. 갈리면 회수가 조용히 볼륨을 남긴다.
VOLUME_SUFFIXES: tuple[str, ...] = ("input", "work", "artifacts")

#: 유형 B 서비스 컨테이너의 접두 (`golden_b.SERVICE_CONTAINER`). W-4 가 attempt 별로
#: 갈라 두었고(`agent_b.py:535`), 안 갈면 동시 실행 시 뒤 attempt 가 앞 attempt 의
#: 서비스를 `rm -f` 로 죽인다.
SERVICE_CONTAINER_PREFIX = "kisia-r5-fix-b"


def attempt_ids(challenge_id: str, max_attempts: int) -> list[str]:
    """이 문제가 만들 수 있는 attempt id 전부 — `<challenge_id>-<NN>` (실측).

    **범위는 `max_attempts` 가 정한다.** 앞선 실행이 더 큰 상자로 돌았다면 그보다 위의
    번호는 이 쓸기에 들어오지 않는다 — 아는 것과 모르는 것을 접지 않기 위해 그 한계를
    여기 적어 둔다.
    """
    return [f"{challenge_id}-{n:02d}" for n in range(1, max(max_attempts, 0) + 1)]


@dataclass(frozen=True)
class ReapTargets:
    """지울 이름들. **순서가 곧 계약이다** — 컨테이너가 붙어 있으면 네트워크·볼륨이
    지워지지 않는다."""

    containers: tuple[str, ...]
    networks: tuple[str, ...]
    volumes: tuple[str, ...]


def reap_targets(challenge_id: str, *, max_attempts: int) -> ReapTargets:
    containers: list[str] = []
    networks: list[str] = []
    volumes: list[str] = []
    for attempt in attempt_ids(challenge_id, max_attempts):
        containers += [
            f"kisia-{attempt}",
            f"kisia-{attempt}-loader",
            f"{SERVICE_CONTAINER_PREFIX}-{attempt}",
        ]
        networks.append(f"kisia-{attempt}-net")
        volumes += [f"kisia-{attempt}-{suffix}" for suffix in VOLUME_SUFFIXES]
    return ReapTargets(tuple(containers), tuple(networks), tuple(volumes))


@dataclass(frozen=True)
class ReapReport:
    """회수 한 번의 결과. **0 건도 적는다** — 안 적으면 회수기가 돌았는지 알 수 없다."""

    containers: int = 0
    networks: int = 0
    volumes: int = 0
    #: 지우려다 **부르지도 못한** 것들. rc≠0 은 여기 오지 않는다 — 없는 것을 지우려는
    #: 것은 오류가 아니다(멱등).
    failures: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def note(self) -> str:
        line = (
            f"회수: 컨테이너 {self.containers} · 네트워크 {self.networks} "
            f"· 볼륨 {self.volumes}"
        )
        if self.failures:
            line += f" · 실패 {len(self.failures)}: {'; '.join(self.failures[:3])}"
        return line


def reap(cli: DockerCli, challenge_id: str, *, max_attempts: int) -> ReapReport:
    """이 문제의 잔존물을 지운다. **멱등이다** — 없는 것을 지우려는 것은 오류가 아니다.

    `check=False` 로 부른다. `rc≠0` 은 *"그런 것이 없다"* 이고 그것이 정상이다. 세는
    것은 `rc==0`, 즉 **실제로 지워진 것**뿐이다. 부르지도 못한 경우(docker 없음·타임
    아웃)만 실패로 올라가고, 그 실패는 호출자가 `error` 로 만든다 — 잔존물 위에서 도는
    attempt 는 무엇을 잰 것인지 정의되지 않는다.
    """
    targets = reap_targets(challenge_id, max_attempts=max_attempts)
    failures: list[str] = []
    counts = [0, 0, 0]
    plan: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
        (("rm", "-f"), targets.containers),
        (("network", "rm"), targets.networks),
        (("volume", "rm"), targets.volumes),
    )
    for index, (verb, names) in enumerate(plan):
        for name in names:
            try:
                ran = cli.run(*verb, name, check=False)
            except Exception as exc:
                # **조용히 넘기지 않는다.** 지우지 못한 채 진행하면 다음 attempt 가
                # `already exists` 로 죽고, 그 오류가 챌린지의 성질처럼 보인다.
                failures.append(f"{name}: {type(exc).__name__}: {exc}")
                continue
            if ran.rc == 0:
                counts[index] += 1
    return ReapReport(counts[0], counts[1], counts[2], tuple(failures))


# ---------------------------------------------------------------------------
# queue.json
# ---------------------------------------------------------------------------


@dataclass
class QueueItem:
    """문제 하나의 줄. **운영자가 손으로 고치는 것이 이 줄이다.**"""

    challenge_id: str
    path: str
    category: str | None = None
    points: int | None = None
    #: 항목별 덮어쓰기. 없으면 전역 `Queue.flag_format`. 둘 다 없으면 **띄우지 않는다.**
    flag_format: str | None = None
    state: str = "pending"
    #: 자식의 **자기 보고**다 (`CLAUDE.md` §6). 판정에 쓰지 않고 상자 판단에만 쓴다.
    attempts: int = 0
    #: 같은 자기 보고. `None` 은 **미상**이고 `"0"` 과 다르다 — 죽인 자식은 보고를
    #: 내지 못했으므로 지출을 우리가 모른다. **"수행하지 못함"과 "0"을 접지 않는다.**
    usd_spent: str | None = None
    #: 큐가 **직접 잰** 벽시계. 자식의 자기 보고 `wall_s` 가 아니다.
    wall_s: float = 0.0
    candidates: list[str] = field(default_factory=list)
    #: 운영자가 준 순서. 있으면 무엇보다 우선한다.
    order: int | None = None
    note: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "path": self.path,
            "category": self.category,
            "points": self.points,
            "flag_format": self.flag_format,
            "state": self.state,
            "attempts": self.attempts,
            "usd_spent": self.usd_spent,
            "wall_s": round(self.wall_s, 3),
            "candidates": list(self.candidates),
            "order": self.order,
            "note": self.note,
        }

    @staticmethod
    def from_json(raw: dict[str, Any]) -> QueueItem:
        state = str(raw.get("state", "pending"))
        if state not in STATES:
            raise QueueError(f"알 수 없는 state {state!r} — 여섯은 {sorted(STATES)} 다")
        usd = raw.get("usd_spent")
        return QueueItem(
            challenge_id=str(raw["challenge_id"]),
            path=str(raw["path"]),
            category=None if raw.get("category") is None else str(raw["category"]),
            points=None if raw.get("points") is None else int(raw["points"]),
            flag_format=None if raw.get("flag_format") is None else str(raw["flag_format"]),
            state=state,
            attempts=int(raw.get("attempts", 0)),
            usd_spent=None if usd is None else str(usd),
            wall_s=float(raw.get("wall_s", 0.0)),
            candidates=[str(c) for c in raw.get("candidates") or []],
            order=None if raw.get("order") is None else int(raw["order"]),
            note=None if raw.get("note") is None else str(raw["note"]),
        )


@dataclass
class Queue:
    """`queue.json` 하나. **이 파일이 상태다** — 죽으면 다시 읽고 이어간다."""

    path: Path
    out_root: str
    items: list[QueueItem]
    #: 전역 기본값. 항목이 자기 것을 갖지 않으면 이것을 쓴다.
    flag_format: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {
            "schema": QUEUE_SCHEMA,
            "flag_format": self.flag_format,
            "out_root": self.out_root,
            "totals": self.totals(),
            "items": [item.as_json() for item in self.items],
        }

    def totals(self) -> dict[str, Any]:
        """합계. **미상을 0으로 접지 않고 따로 센다**(`CLAUDE.md` §6)."""
        known = [i for i in self.items if i.usd_spent is not None]
        return {
            # 자식의 자기 보고를 합친 값이다. **판정에 쓰는 것이 아니라 폭주를 막는 데
            # 쓴다** — 우리는 자식이 실제로 얼마를 썼는지 독립적으로 재지 않았다.
            "usd_spent_self_reported": str(sum((_decimal(i.usd_spent) for i in known), Decimal(0))),
            "usd_unknown_items": sum(1 for i in self.items if i.usd_spent is None),
            "wall_s": round(sum(i.wall_s for i in self.items), 3),
            "states": {s: sum(1 for i in self.items if i.state == s) for s in sorted(STATES)},
        }

    def save(self) -> None:
        """**원자적으로** 다시 쓴다 — 임시 파일 + `Path.replace`(= `os.replace`).

        운영자가 대회 중간에 이 파일을 연다. 반쯤 쓰인 상태가 보이는 자리가 없어야 하고,
        크래시가 큐 자체를 날리는 자리도 없어야 한다.
        """
        blob = json.dumps(self.as_json(), ensure_ascii=False, indent=2) + "\n"
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_bytes(blob.encode("utf-8"))
        tmp.replace(self.path)

    def by_id(self, challenge_id: str) -> QueueItem:
        for item in self.items:
            if item.challenge_id == challenge_id:
                return item
        raise KeyError(challenge_id)


def _decimal(value: object) -> Decimal:
    """문자열/숫자를 `Decimal` 로. 읽을 수 없으면 `Decimal(0)` — 자기 보고이므로 여기서
    죽지 않는다. 대신 그 값이 상자 판단에 못 들어간다는 사실이 note 에 남는다."""
    if value is None:
        return Decimal(0)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(0)


def load(path: Path) -> Queue:
    raw = json.loads(path.read_bytes().decode("utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != QUEUE_SCHEMA:
        raise QueueError(f"{path}: schema 가 {QUEUE_SCHEMA!r} 가 아니다")
    return Queue(
        path=path,
        out_root=str(raw["out_root"]),
        flag_format=None if raw.get("flag_format") is None else str(raw["flag_format"]),
        items=[QueueItem.from_json(i) for i in raw["items"]],
    )


def build(
    challenge_root: Path, *, queue_path: Path, out_root: Path, flag_format: str | None
) -> Queue:
    """`<dir>` 을 훑어 큐를 만든다. **하위 디렉터리 하나 = 문제 하나.**

    난이도를 **추정하지 않는다** — 본선 감이고 이 저장소는 난이도를 잰 적이 없다
    (`ADR-0003` "능력 계층: 여전히 아무것도 재지 않는다"). `points` 는 운영자가 손으로
    채우는 자리로 비워 둔다.
    """
    if not challenge_root.is_dir():
        raise QueueError(f"{challenge_root}: 디렉터리가 아니다")
    items = [
        QueueItem(challenge_id=d.name, path=str(d.resolve()))
        for d in sorted(challenge_root.iterdir())
        if d.is_dir() and not d.name.startswith((".", "__"))
    ]
    return Queue(
        path=queue_path,
        out_root=str(out_root.resolve()),
        flag_format=flag_format,
        items=items,
    )


# ---------------------------------------------------------------------------
# 상자와 실행
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Boxes:
    """상자. **없으면 큐가 없는 것과 같다** — 첫 문제가 전부를 먹는다(`MVP_SCOPE.md` §5)."""

    max_attempts: int
    max_wall_s_per_challenge: float
    max_usd_per_challenge: Decimal | None = None
    #: 전역 하드 스톱. 소진되면 **남은 항목은 손대지 않는다** — `pending` 으로 남는다.
    total_usd_budget: Decimal | None = None


def _sort_key(pair: tuple[int, QueueItem]) -> tuple[int, int, int, int]:
    """운영자가 준 `order` > `points` 내림차순 > 파일 순서. **그 이상 정교하게 만들지 않는다.**"""
    index, item = pair
    return (0 if item.order is not None else 1, item.order or 0, -(item.points or 0), index)


class QueueRunner:
    """큐 하나를 돌린다. 잠금은 **스레드 락 하나**이고 그것이 `queue.json` 도 지킨다."""

    def __init__(
        self,
        queue: Queue,
        *,
        boxes: Boxes,
        argv_builder: ArgvBuilder = default_argv,
        concurrency: int = 1,
        python: str | None = None,
        on_event: Callable[[str], None] | None = None,
        #: 회수기가 쓰는 손. **raw docker 소켓을 쓰지 않는다** — `DockerCli` 는
        #: `DOCKER_HOST` 를 프록시로 맞춰 주고, 그것이 `MVP_SCOPE.md` §3-2 가 canon 으로
        #: 요구하는 유일한 경로다. 시험은 여기에 가짜를 넣는다.
        docker: DockerCli | None = None,
    ) -> None:
        if concurrency < 1:
            raise QueueError(f"concurrency 는 1 이상이다: {concurrency}")
        self.queue = queue
        self.boxes = boxes
        self.argv_builder = argv_builder
        self.concurrency = concurrency
        self.python = python or sys.executable
        self.on_event = on_event
        self.docker = docker if docker is not None else DockerCli()
        self._lock = threading.Lock()
        self._stopped = False

    # -- 재개 ----------------------------------------------------------------
    def resume(self) -> list[str]:
        """`running` 으로 남아 있던 항목을 `pending` 으로 되돌린다.

        **`error` 로 되돌리지 않는다.** 크래시했으므로 실제로 돌지 않았거나 결과를 받지
        못한 것이고, **둘 다 [틀렸다]가 아니다**(`D-63`).
        """
        resumed: list[str] = []
        for item in self.queue.items:
            if item.state == "running":
                item.state = "pending"
                item.note = RESUMED_NOTE
                resumed.append(item.challenge_id)
        if resumed:
            self.queue.save()
        return resumed

    # -- 실행 ----------------------------------------------------------------
    def run(self) -> Queue:
        self.resume()

        pending = [item for _, item in sorted(enumerate(self.queue.items), key=_sort_key)]
        runnable: list[tuple[QueueItem, str]] = []
        for item in pending:
            if item.state != "pending":
                continue
            fmt = item.flag_format or self.queue.flag_format
            if not fmt:
                # **자식을 띄우지 않는다.** 추측한 형식은 조용히 전부 오답이 된다(`O-49`).
                item.state = "parked"
                item.note = UNKNOWN_FLAG_FORMAT_NOTE
                self._emit(f"{item.challenge_id:24s} parked     {UNKNOWN_FLAG_FORMAT_NOTE}")
                continue
            runnable.append((item, fmt))
        self.queue.save()

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = [pool.submit(self._run_one, item, fmt) for item, fmt in runnable]
            for future in futures:
                future.result()
        return self.queue

    def _run_one(self, item: QueueItem, flag_format: str) -> None:
        with self._lock:
            if self._stopped:
                # 전역 상한이 이미 소진됐다. **손대지 않는다** — `pending` 그대로 남는다.
                # 상자를 쓴 것이 아니므로 `parked` 로 바꾸지 않는다.
                return
            if self._budget_exhausted():
                self._stopped = True
                self._emit(
                    f"전역 상한 소진 — 남은 항목은 pending 으로 남긴다 "
                    f"(--total-usd-budget {self.boxes.total_usd_budget})"
                )
                return
            item.state = "running"
            item.note = None
            self.queue.save()

        # **(a) 시작 전 회수.** 앞선 실행이 상자를 써서 죽었다면 그 이름들이 아직 살아
        # 있고, `docker network create` 가 `already exists` 로 죽는다(호스트 실측).
        # 지우고 시작해야 **재개**가 산다.
        before = reap(self.docker, item.challenge_id, max_attempts=self.boxes.max_attempts)
        if not before.ok:
            with self._lock:
                item.state = "error"
                item.note = (
                    "시작 전 회수에 실패했다 — 잔존물 위에서 도는 attempt 는 무엇을 잰 "
                    f"것인지 정의되지 않는다. {before.note}"
                )
                self.queue.save()
                self._emit(f"{item.challenge_id:24s} {item.state:10s} {item.note}")
            return

        out_dir = Path(self.queue.out_root) / item.challenge_id
        # **문제마다 `--out` 을 가른다.** `attempt_id` 접두가 겹치면 `writeup --out` 이
        # 충돌로 죽는다(`D-64`).
        out_dir.mkdir(parents=True, exist_ok=True)
        spec = ChildSpec(
            python=self.python,
            challenge_dir=Path(item.path),
            challenge_id=item.challenge_id,
            flag_format=flag_format,
            out_dir=out_dir,
            max_attempts=self.boxes.max_attempts,
            max_usd=self.boxes.max_usd_per_challenge,
        )
        outcome = spawn(self.argv_builder(spec), timeout_s=self.boxes.max_wall_s_per_challenge)

        # **(b) 끝난 뒤 회수 — 특히 죽인 뒤.** 정상 종료면 `Workspace.destroy()` 가 이미
        # 비웠으므로 0 건이 나오고, 그것이 멱등이라는 뜻이다. 방어적으로 언제나 돈다.
        after = reap(self.docker, item.challenge_id, max_attempts=self.boxes.max_attempts)

        with self._lock:
            self._apply(item, outcome)
            self._note_reap(item, before, after)
            self.queue.save()
            self._emit(
                f"{item.challenge_id:24s} {item.state:10s} "
                f"attempts={item.attempts} usd={item.usd_spent or '미상'} "
                f"{item.wall_s:.1f}s" + (f"  {item.note}" if item.note else "")
            )

    @staticmethod
    def _note_reap(item: QueueItem, before: ReapReport, after: ReapReport) -> None:
        """회수 결과를 그 줄에 남긴다. **0 건도 적는다** — 안 적으면 회수기가 돌았는지
        알 수 없고, 다음 실행의 `already exists` 가 무엇 때문인지도 알 수 없다.

        **끝난 뒤 회수가 실패하면 그 항목은 `error` 다.** 자식이 무엇을 보고했든
        잔존물이 남았다는 사실이 다음 실행을 막으므로, 그것을 성공으로 적으면 큐가
        거짓말을 하게 된다. 후보는 지우지 않고 그 사실을 함께 적는다 — 운영자가 찾은
        flag 를 잃지 않아야 한다.
        """
        reaped = f"시작 전 {before.note} / 종료 뒤 {after.note}"
        if not after.ok:
            item.state = "error"
            reaped = f"종료 뒤 회수에 실패했다 — 잔존물이 다음 실행을 막는다. {reaped}"
            if item.candidates:
                reaped += f" · 후보 {len(item.candidates)}건은 그대로 남아 있다"
        item.note = reaped if not item.note else f"{item.note} · {reaped}"

    def _apply(self, item: QueueItem, outcome: ChildOutcome) -> None:
        """자식 하나의 결과를 줄에 적는다. **여섯 상태를 접지 않는 자리가 여기다.**"""
        item.wall_s = outcome.wall_s

        if outcome.spawn_error is not None:
            item.state = "error"
            item.note = f"자식을 띄우지 못했다: {outcome.spawn_error}"
            return

        if outcome.timed_out:
            # 상자를 다 썼다 → `parked`. 죽인 자식은 결과 봉투를 내지 못했으므로
            # **지출은 미상이다** — 0 으로 접지 않는다(`CLAUDE.md` §6).
            item.state = "parked"
            item.usd_spent = None
            item.note = (
                f"벽시계 상자 소진 — {outcome.wall_s:.1f}s 에서 자식 트리를 죽였다"
                f" (--max-wall-s-per-challenge {self.boxes.max_wall_s_per_challenge}). 지출 미상"
            )
            return

        if outcome.returncode != 0:
            item.state = "error"
            item.note = f"자식 exit {outcome.returncode}: {_tail(outcome.stderr)}"
            return

        result = parse_result(outcome.stdout)
        if result is None:
            item.state = "error"
            item.note = f"자식이 {RESULT_SCHEMA} 봉투를 내지 않았다: {_tail(outcome.stdout)}"
            return
        if str(result.get("challenge_id")) != item.challenge_id:
            # 다른 문제의 결과를 이 줄에 적으면 후보가 조용히 뒤바뀐다.
            item.state = "error"
            item.note = (
                f"자식이 다른 challenge_id 를 보고했다: {result.get('challenge_id')!r}"
            )
            return

        reported_usd = result.get("usd_spent")
        item.attempts = int(result.get("attempts") or 0)
        item.usd_spent = None if reported_usd is None else str(reported_usd)
        item.candidates = [str(c) for c in result.get("candidates") or []]
        child_state = str(result.get("state"))

        if child_state == "candidate":
            item.state = "candidate"
            item.note = "후보 flag — solved 가 아니다. 운영자가 플랫폼에서 확인한다"
            return
        if child_state == "error":
            item.state = "error"
            item.note = f"자식이 error 를 보고했다: {result.get('error')!r}"
            return
        if child_state != "unsolved":
            item.state = "error"
            item.note = f"자식이 알 수 없는 state 를 보고했다: {child_state!r}"
            return

        # 여기부터 자식은 `unsolved` 다. **그런데 상자를 다 쓴 것과 사다리를 끝까지 간
        # 것은 다르다.** 상자가 잘랐다면 사다리가 무엇을 찾았을지 우리는 모르므로
        # `parked` 로 남긴다 — 나중에 다시 붙어야 할 문제가 어느 것인지 잃지 않는다.
        spent = _decimal(item.usd_spent)
        money_box = self.boxes.max_usd_per_challenge
        if item.attempts >= self.boxes.max_attempts:
            item.state = "parked"
            item.note = (
                f"시도 상자 소진 ({item.attempts}/{self.boxes.max_attempts}) — "
                "사다리를 끝까지 갔는지는 모른다"
            )
        elif money_box is not None and spent >= money_box:
            item.state = "parked"
            item.note = f"돈 상자 소진 ({spent}/{money_box})"
        else:
            item.state = "unsolved"
            item.note = "사다리를 끝까지 갔는데 후보가 없다"

    def _budget_exhausted(self) -> bool:
        """전역 상한. 자식의 **자기 보고**를 합산한 값으로 판단한다 — 우리가 독립적으로
        잰 값이 아니고, 그 사실을 알고 쓴다(`CLAUDE.md` §6). 판정이 아니라 폭주 방지다.

        **`--concurrency > 1` 이면 상한을 정확히 지키지 못한다.** 검사는 자식을 띄우기
        직전에 하는데 이미 떠 있는 자식들의 지출은 아직 보고되지 않았으므로, 최대
        `concurrency - 1` 문제만큼 넘길 수 있다. **모르는 것을 아는 척하지 않는다** —
        정확한 상한이 필요하면 `--concurrency 1` 이다.
        """
        cap = self.boxes.total_usd_budget
        if cap is None:
            return False
        spent = sum(
            (_decimal(i.usd_spent) for i in self.queue.items if i.usd_spent is not None),
            Decimal(0),
        )
        return spent >= cap

    def _emit(self, line: str) -> None:
        if self.on_event is not None:
            self.on_event(line)


def _tail(text: str, *, limit: int = 200) -> str:
    flat = " ".join(text.split())
    return flat[-limit:] if len(flat) > limit else flat


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kisia.contest.queue", add_help=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="<dir> 을 훑어 queue.json 을 만든다")
    p_init.add_argument("challenge_root", type=Path)
    p_init.add_argument("--queue", type=Path, default=Path("queue.json"))
    p_init.add_argument("--out-root", type=Path, default=Path("out"))
    p_init.add_argument("--flag-format", default=None)

    p_run = sub.add_parser("run", help="queue.json 을 읽고 돌린다")
    p_run.add_argument("--queue", type=Path, default=Path("queue.json"))
    # **상자 둘은 필수다.** 기본값을 주면 정해진 적 없는 예산이 코드에 박히고
    # (`orchestrator.run_until_done` 이 같은 이유로 `max_attempts` 를 필수로 받는다),
    # 벽시계 상자가 없으면 `O-54` 를 막는 자리가 통째로 사라진다.
    p_run.add_argument("--max-attempts", type=int, required=True)
    p_run.add_argument("--max-wall-s-per-challenge", type=float, required=True)
    p_run.add_argument("--max-usd-per-challenge", type=Decimal, default=None)
    p_run.add_argument("--total-usd-budget", type=Decimal, default=None)
    p_run.add_argument("--concurrency", type=int, default=1)
    p_run.add_argument("--python", default=None)

    args = ap.parse_args(argv)

    if args.cmd == "init":
        queue = build(
            args.challenge_root,
            queue_path=args.queue,
            out_root=args.out_root,
            flag_format=args.flag_format,
        )
        queue.save()
        print(f"{args.queue}  ←  {len(queue.items)} 문제")
        for item in queue.items:
            print(f"  {item.challenge_id:24s} {item.path}")
        if not queue.flag_format:
            print(f"\n※ --flag-format 이 비어 있다. {UNKNOWN_FLAG_FORMAT_NOTE}")
        return 0

    queue = load(args.queue)
    runner = QueueRunner(
        queue,
        boxes=Boxes(
            max_attempts=args.max_attempts,
            max_wall_s_per_challenge=args.max_wall_s_per_challenge,
            max_usd_per_challenge=args.max_usd_per_challenge,
            total_usd_budget=args.total_usd_budget,
        ),
        concurrency=args.concurrency,
        python=args.python,
        on_event=print,
    )
    runner.run()
    totals = queue.totals()
    print(f"\n{args.queue}")
    print(f"  {totals['states']}")
    print(
        f"  usd(자기 보고) {totals['usd_spent_self_reported']}"
        f" · 미상 {totals['usd_unknown_items']}"
    )
    # `candidate` 는 판정이 아니다. 맞았는지는 운영자가 플랫폼에서 확인한다.
    return 1 if totals["states"]["error"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
