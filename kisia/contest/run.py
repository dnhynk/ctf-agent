"""`python -m kisia.contest` — 챌린지 **하나**를 승격 사다리에 태운다.

`MVP_SCOPE.md` §5 의 임계 경로 3과 4다. *"3과 4를 가르지 마라 — 사다리 없는 3은 성능이
깎인 물건이다."* 그래서 이 모듈은 진입점이면서 사다리를 도는 코드다.

```
python -m kisia.contest --challenge <dir> --flag-format <fmt> [--challenge-id <id>]
       --out <dir> --max-attempts <n> [--max-usd <d>] [--description-file <f>]
       [--service <img> [--service-host <alias>] [--service-port <n>]] --json
```

**`--service` 가 유형을 가른다.** 주면 매니페스트가 `type: "B"` 가 되고 solver 가
`agent_b.run_attempt` 로 갈린다(`solver_impl`). 주지 않으면 유형 A 이고 그 경로는
이 변경 전과 **한 줄도 다르지 않다.** 예선에 서비스(nc/http) 문항이 있고, 배선이 없으면
그 범주를 통째로 0점 처리한다 — 그것은 *문제를 덜 푸는* 결과이므로 `MVP_SCOPE.md` §1.5
가 금지한 트레이드 오프다.

**stdout 의 마지막 줄은 결과 JSON 한 줄이고 그 밖에 stdout 으로 나가는 것은 없다.**
`kisia.contest.queue` 가 이 프로세스를 자식으로 띄워 그 줄을 읽는다
(`kisia/contest/__init__.py`: 두 층은 프로세스 경계로 갈린다). 로그는 전부 stderr 다.

---

**사다리를 어떻게 도는가** — `R5-8` 역할표를 실제로 도는 코드는 여기가 처음이다.

1. **rung 1~3 은 순서대로.** 분류 → 계획 → 실행.
2. **rung 4(deepen)는 stall 이 관측돼야 오른다.** 운영자가 그 조건을 *"새 증거 없이
   3회 반복 / 같은 가설 2회"* 로 적었고, 그 둘은 이미 세고 있는 값이다 —
   `stall.observed`(발행자 `kisia/runtime/loop.py::_observe_stalls`, 창 3턴)와
   같은 진술 2회(`native.SAME_HYPOTHESIS_MIN`). **새 숫자를 고르지 않았다.**
3. **rung 5(escalate) 이상으로 오를 때 escalation 패킷을 들려 보낸다.** 없으면 강한
   모델이 맥락 없이 맨몸으로 받고, 그것은 문제를 덜 푸는 결과이므로 금지된 트레이드
   오프다(`MVP_SCOPE.md` §1.5). 패킷은 **프로세스 안에서 다음 attempt 로만** 간다 —
   egress 는 canon 상 비활성이다(`SAFETY_SCOPE.md` "Escalation egress: Currently inert").
4. **rung 5·6 은 `reasoning_effort` 가 미정이라 `PromotionBlockedError` 가 난다.**
   그것을 크래시로 두지 않고 **"사다리가 여기서 끝났다"**로 받아 정상 종료한다. 값은
   운영자에게서 오고 이 모듈이 고르지 않는다(`scheduler.py` 머리말).

**후보가 하나라도 나오면 그 문제의 사다리를 멈춘다.** 대회에는 문제가 수십 개이고,
이미 후보를 낸 문제에 예산을 더 태우는 것은 순손실이다. 후보가 틀렸으면 운영자가
`queue.json` 에서 되돌린다 — 그것이 `MVP_SCOPE.md` §4.1 이 말한 수동 인터페이스다.

**`solved` 를 말하지 않는다.** 라이브 대회에서 우리는 정답을 모르고(무정답 모드에서
verifier 는 돌지 않는다), 맞았는지는 운영자가 플랫폼에서 확인한다. 그래서 상태는
`candidate | unsolved | error` 셋이다 — *"모른다"를 "틀렸다"로 접지 않는다.*

---

**`O-54` 와 벽시계 상한.** 통제 블록은 `attempt_timeout_s: 900` 을 **선언만** 하고
강제하는 코드가 없다(실측: 그 이름은 통제 블록 dict 셋과 검사기의 필드 목록에만
나온다). 그래서 이 모듈이 attempt 하나에 벽시계 상한을 건다 — 값은 **그 선언된 값
그대로**이고 새로 고른 숫자가 아니다. 걸지 않으면 도달 불가 endpoint 하나에 대회가
끝난다.

**`SIGALRM` 으로 건다.** 신호는 블로킹 소켓 읽기를 깨우고, 깨운 자리에서 예외가 오르면
`run_attempt` 의 `finally: ws.destroy()` 가 **실제로 돈다** — 워크스페이스가 고아로
남지 않는다. `SIGALRM` 이 없는 플랫폼(Windows 개발 기계)에서는 걸지 못하고, 그 사실을
stderr 에 적는다. **"걸었다"고 적지 않는다.**
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from types import FrameType
from typing import Any

from kisia.checker.model import StreamVoidError, load_stream
from kisia.contest import manifest as manifest_mod
from kisia.escalation.compile import compile_packet
from kisia.escalation.render import render_markdown
from kisia.evidence.store import EvidenceStore
from kisia.orchestrator import (
    OPERATOR_LADDER,
    Assignment,
    AttemptResult,
    Orchestrator,
    PromotionBlockedError,
    Rung,
    Scheduler,
)
from kisia.orchestrator.model import CONTEST
from kisia.orchestrator.native import DEFAULT_RUN_ATTEMPT, NativeHarnessWorker
from kisia.runtime import agent_a
from kisia.runtime.golden_a import Fixture

#: 결과 한 줄의 스키마. `kisia.contest.queue` 가 이 값으로 읽는다.
RESULT_SCHEMA = "kisia.contest.result/1"

#: stall 이 관측돼야 오르는 rung. 운영자 사다리의 넷째다.
STALL_RUNG = "deepen"

#: 이 rung 부터 escalation 패킷을 들려 보낸다. 운영자 사다리의 다섯째.
ESCALATE_FROM = "escalate"

#: attempt 하나의 벽시계 상한. **통제 블록이 이미 선언한 값 그대로다**
#: (`agent_a._control` 의 `attempt_timeout_s`). 새로 고른 숫자가 아니다.
ATTEMPT_WALL_S = 900

#: 문제 기술에 싣는 패킷의 문자 상한. 넘으면 **잘랐다는 사실을 본문에 적는다** —
#: 조용히 자르면 받는 쪽이 목록을 전부로 읽는다(`loop.STALL_REQUEST_MAX_IDS` 와 같은 자세).
PACKET_CHARS_MAX = 40_000

#: 결과 줄의 `error` 문면 상한. 실측에서 docker 의 Go 패닉 전문 2.2KB 가 그대로 실렸다 —
#: 그 줄은 큐의 상태 파일로 들어가고 운영자가 읽는 것이다. **전문은 stderr 에 남는다.**
ERROR_CHARS_MAX = 600

#: `fixed` 로 넘어가는 것 중 이 모듈이 환경에서 읽는 것들. **비밀은 argv 에 넣지
#: 않는다**(`MVP_SCOPE.md` §3-5, `O-11`) — 그래서 키는 언제나 환경변수다.
ENV_API_KEY = "OPENAI_API_KEY"
ENV_PRICING = "KISIA_PRICING"
ENV_IMAGE = "KISIA_WORKER_IMAGE"
ENV_PROBE = "KISIA_CAPABILITY_PROBE"
ENV_PROBE_ID = "KISIA_CAPABILITY_PROBE_ID"
ENV_HOST_ID = "KISIA_HOST_ID"


class ContestError(RuntimeError):
    """이 챌린지를 시작할 수 없다."""


class AttemptTimeoutError(RuntimeError):
    """attempt 하나가 벽시계 상한을 넘겼다 (`O-54`)."""


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


@dataclass
class _Run:
    """사다리를 도는 동안의 상태. **파일로 남기지 않는다** — 재개는 큐의 일이다."""

    fixture: manifest_mod.Synthesized
    streams: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    spent: Decimal = Decimal(0)
    last_rung: str | None = None
    last_stream: Path | None = None
    last_attempt_id: str | None = None
    error: str | None = None


def run_contest(
    *,
    challenge_dir: Path,
    out_dir: Path,
    flag_format: str,
    max_attempts: int,
    challenge_id: str | None = None,
    max_usd: Decimal | None = None,
    description_file: Path | None = None,
    fixed: Mapping[str, Any] | None = None,
    #: 서비스 이미지. 주면 **유형 B** 다 — 매니페스트가 `type: "B"` 가 되고 solver 가
    #: `agent_b.run_attempt` 로 갈린다.
    service_image: str | None = None,
    service_host: str | None = None,
    service_port: int | None = None,
    #: `None` 이면 유형에 맞는 것을 **부를 때** 찾는다. 기본값 자리에 박으면 import
    #: 시점에 묶여 시험이 가짜를 끼울 자리가 사라진다.
    run_attempt: Callable[..., dict[str, Any]] | None = None,
    ladder: tuple[Rung, ...] = OPERATOR_LADDER,
    attempt_wall_s: int = ATTEMPT_WALL_S,
) -> dict[str, Any]:
    """챌린지 하나를 사다리에 태우고 **결과 한 줄을 돌려준다. 던지지 않는다.**

    던지지 않는 이유: 이 프로세스는 큐의 자식이고, 예외로 죽으면 큐가 읽을 줄이 없어
    *"무슨 일이 있었는지 모른다"* 와 *"실패했다"* 가 구분되지 않는다. 막힌 것은
    `error` 필드가 나른다.
    """
    if max_attempts < 1:
        raise ContestError(f"max_attempts 는 1 이상이다: {max_attempts}")
    started = time.monotonic()

    description = None
    if description_file is not None:
        description = description_file.read_text(encoding="utf-8").strip()
        if not description:
            raise ContestError(f"--description-file 이 비어 있다: {description_file}")

    service = _service_target(service_image, service_host, service_port)

    # **매니페스트가 attempt 앞에 있다** (`O-49`).
    synthesized = manifest_mod.synthesize(
        challenge_dir=challenge_dir,
        root=out_dir / "fixture",
        flag_format=flag_format,
        challenge_id=challenge_id,
        description=description,
        # 매니페스트는 **켤 프로브 집합**을 선언한다. 값의 출처는 실제로 그것을 켜는
        # 코드 하나뿐이다 — 여기서 다시 적으면 두 벌이 되고 조용히 갈린다.
        probes=_probes_for(service_image),
        service=service,
    )
    _log(
        f"manifest {synthesized.manifest_path} sha256={synthesized.manifest_sha256} "
        f"type={'B' if service is not None else 'A'}"
        + ("" if service is None else f" target={service.host}:{service.port}")
    )

    store = EvidenceStore(out_dir / "evidence")
    streams_dir = out_dir / "streams"
    scheduler = Scheduler(ladder, stall_rung=_stall_rung_of(ladder))
    escalate_at = _index_or_none(scheduler, ESCALATE_FROM)
    run = _Run(fixture=synthesized)

    def solver(assignment: Assignment) -> AttemptResult:
        fixture = _fixture_for(
            assignment,
            run=run,
            base=synthesized,
            scheduler=scheduler,
            escalate_at=escalate_at,
            store=store,
            out_dir=out_dir,
        )
        per_attempt: dict[str, Any] = {
            **dict(fixed or {}),
            "fixture": Fixture(fixture.root),
            # **통제 블록의 두 갈래를 배정이 아니라 배치에서 넘긴다.** 러너의 기본값은
            # `dev`/`synthetic` 이고, 그것이 그대로 남으면 대회 스트림이 dev 세트의
            # 자작 챌린지로 기록된다 — `R5-10` 이 두 값을 만든 이유가 그 오염이고,
            # `MANIFEST.md` §2.3.a 의 S7·S8 침묵도 `provenance` 에서 파생된다.
            "challenge_set": manifest_mod.CHALLENGE_SET,
            "provenance": manifest_mod.PROVENANCE,
        }
        if service_image is not None:
            per_attempt["service_image"] = service_image
        if max_usd is not None and "usd_budget" not in per_attempt:
            # **상자는 attempt 안에서도 걸려야 한다.** 사이에서만 보면 첫 attempt 가
            # solver 의 기본 예산까지 쓰고 나서야 상한을 넘긴 것이 보인다 — 그때는 이미
            # 썼다. 남은 만큼을 그 attempt 의 예산으로 준다.
            per_attempt["usd_budget"] = max_usd - run.spent
        worker = NativeHarnessWorker(
            out_dir=streams_dir,
            fixed=per_attempt,
            run_attempt=run_attempt or solver_impl(service_image),
        )
        return worker(assignment)

    orchestrator = Orchestrator(store=store, scheduler=scheduler, solver=solver)
    challenge = orchestrator.submit(synthesized.challenge_id, challenge_set=CONTEST)

    for _ in range(max_attempts):
        if max_usd is not None and run.spent >= max_usd:
            _log(f"돈 상자 소진 {run.spent}/{max_usd} — 사다리를 멈춘다")
            break
        try:
            with _deadline(attempt_wall_s):
                attempt = orchestrator.run_one(challenge)
        except PromotionBlockedError as exc:
            # **크래시가 아니다.** 사다리가 여기서 끝났다는 사실이고, 값은 운영자가 준다.
            _log(f"사다리 끝 (승격 막힘): {exc}")
            break
        except AttemptTimeoutError as exc:
            run.error = f"attempt_timeout: {exc}"
            _log(str(exc))
            break
        except Exception as exc:
            # 큐가 읽을 줄은 언제나 나가야 한다 — 예외로 죽으면 *"무슨 일이 있었는지
            # 모른다"* 와 *"실패했다"* 가 구분되지 않는다.
            full = f"{type(exc).__name__}: {exc}"
            _log(f"attempt 가 죽었다: {full}")
            run.error = _clip(full)
            break
        if attempt is None:
            _log("사다리가 끝났다 — 더 오를 rung 이 없다")
            break
        _absorb(run, attempt.assignment, attempt.result)
        if run.candidates:
            _log(f"후보가 나왔다 ({len(run.candidates)}건) — 이 문제의 사다리를 멈춘다")
            break

    return _result(run, synthesized.challenge_id, wall_s=time.monotonic() - started)


def _clip(text: str) -> str:
    """결과 줄에 실을 오류 문면. **전문은 이미 stderr 에 있다** — 자르는 것은 큐의
    `queue.json` 에 들어갈 한 줄이고, 잘랐다는 사실은 표시가 나른다."""
    if len(text) <= ERROR_CHARS_MAX:
        return text
    return text[:ERROR_CHARS_MAX] + f" [...+{len(text) - ERROR_CHARS_MAX} chars on stderr]"


def _absorb(run: _Run, assignment: Assignment, result: AttemptResult | None) -> None:
    run.last_rung = assignment.rung_name
    run.last_attempt_id = assignment.attempt_id
    if result is None:  # pragma: no cover - run_one 은 결과를 채우고 돌아온다
        return
    if result.stream_path is not None:
        run.streams.append(str(result.stream_path))
        run.last_stream = result.stream_path
    run.spent += Decimal(result.usd_total)
    for value in result.candidates:
        if value not in run.candidates:
            run.candidates.append(value)
    _log(
        f"{assignment.attempt_id} rung={assignment.rung_name} "
        f"label={assignment.accounting_label} solve_k={assignment.solve_k} "
        f"outcome={result.outcome} usd={result.usd_total} calls={result.model_calls} "
        f"stall={list(result.stall_signals)} candidates={len(result.candidates)}"
    )


def _result(run: _Run, challenge_id: str, *, wall_s: float) -> dict[str, Any]:
    if run.candidates:
        state = "candidate"
    elif run.error is not None:
        state = "error"
    else:
        state = "unsolved"
    return {
        "schema": RESULT_SCHEMA,
        "challenge_id": challenge_id,
        "state": state,
        "attempts": len(run.streams),
        "candidates": list(run.candidates),
        "usd_spent": f"{run.spent:.4f}",
        "wall_s": round(wall_s, 1),
        "streams": list(run.streams),
        "last_rung": run.last_rung,
        "error": run.error,
    }


# ---------------------------------------------------------------------------
# 승격 — escalation 패킷을 들려 올린다
# ---------------------------------------------------------------------------


def _fixture_for(
    assignment: Assignment,
    *,
    run: _Run,
    base: manifest_mod.Synthesized,
    scheduler: Scheduler,
    escalate_at: int | None,
    store: EvidenceStore,
    out_dir: Path,
) -> manifest_mod.Synthesized:
    """이 attempt 가 받을 fixture. rung 5 이상이면 패킷을 실은 매니페스트다."""
    if escalate_at is None or run.last_stream is None or run.last_attempt_id is None:
        return base
    if scheduler.index_of(assignment.rung_name) < escalate_at:
        return base
    packet = _packet_text(run.last_stream, run.last_attempt_id, store)
    if packet is None:
        return base
    original = json.loads(base.manifest_path.read_text(encoding="utf-8"))
    spun = manifest_mod.respin(
        base,
        root=out_dir / f"fixture-{assignment.attempt_id}",
        description=f"{original['description']}\n\n---\n\n{packet}",
    )
    _log(f"{assignment.attempt_id}: escalation 패킷을 문제 기술에 실었다 ({spun.root})")
    return spun


def _packet_text(stream_path: Path, attempt_id: str, store: EvidenceStore) -> str | None:
    """직전 attempt 의 스트림 → 패킷 마크다운. 못 만들면 `None` 이고 그 사실을 적는다.

    패킷을 evidence store 의 자리(`PATH_SCOPE.md` §3.7)에도 넣는다 — 다음 attempt 의
    프롬프트에만 실어 두면 무엇을 들려 보냈는지가 기록에 남지 않는다.
    """
    try:
        stream = load_stream(stream_path)
    except StreamVoidError as exc:
        _log(f"패킷을 만들 수 없다 (S9.2 무효 스트림): {exc}")
        return None
    packet = compile_packet(stream)
    try:
        store.put(
            attempt_id,
            "escalation_packet",
            "packet.json",
            (json.dumps(packet.as_json(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
    except Exception as exc:
        _log(f"패킷을 보관하지 못했다: {type(exc).__name__}: {exc}")
    text = render_markdown(packet)
    if len(text) > PACKET_CHARS_MAX:
        dropped = len(text) - PACKET_CHARS_MAX
        text = text[:PACKET_CHARS_MAX] + f"\n\n[...{dropped} chars truncated by the harness]\n"
    return (
        "The harness escalated this challenge after the previous attempt stalled. "
        "What follows is the compiled escalation packet from that attempt: what was "
        "CONFIRMED (bytes actually observed), what was INFERRED (hypotheses), and what "
        "was REJECTED. Treat CONFIRMED as fact and everything else as unverified.\n\n"
        + text
    )


# ---------------------------------------------------------------------------
# 유형 A / 유형 B — **하나로 덮는 디스패처를 세우지 않는다**
# ---------------------------------------------------------------------------
#
# `native.py` 머리말이 그 자세를 적는다: *"셋을 하나로 덮는 디스패처를 지금 만들지
# 않는다 — 호출자가 어느 것을 쓸지 알고 있고, 여분 인자는 `fixed` 로 그대로 넘어간다."*
# 여기가 그 **호출자**다. 두 `run_attempt` 의 시그니처는 서로 다르고(유형 B 는
# `service_image` 가 더 있고 `probes` 인자가 없다) 그것을 그대로 둔다. 갈리는 것은
# 이 파일의 함수 둘뿐이다.


def solver_impl(service_image: str | None) -> Callable[..., dict[str, Any]]:
    """이 챌린지를 돌릴 `run_attempt`. 서비스가 있으면 유형 B 다.

    **`agent_b` 를 지연 import 한다.** 그 모듈은 `session.py` 를 통해 vendored 트리를
    import 시점에 끌고 오고(그 트리는 stderr 에 `keys.cfg not found` 를 뱉는다), 유형 A
    챌린지에는 그것이 필요 없다. `main()` 의 stdout 잠금 **안**에서 일어나야 한다는
    이유도 있다 — 모듈 상수로 두면 그 import 가 잠금 밖에서 먼저 일어난다.
    """
    if service_image is None:
        return DEFAULT_RUN_ATTEMPT
    from kisia.runtime import agent_b

    return agent_b.run_attempt


def _probes_for(service_image: str | None) -> tuple[str, ...]:
    """매니페스트가 선언할 프로브 집합. **실제로 켜는 코드에서만 온다.**"""
    if service_image is None:
        return tuple(agent_a.PROBES)
    from kisia.runtime import agent_b

    return tuple(agent_b.PROBES)


def _service_target(
    image: str | None, host: str | None, port: int | None
) -> manifest_mod.ServiceTarget | None:
    """`--service*` 셋에서 매니페스트의 `target` 을 만든다.

    **주소의 기본값은 지어낸 것이 아니라 실측한 상수다** — `golden_b.SERVICE_NAME`
    (`kisia-fix-b`)과 `golden_b.SERVICE_PORT`(`9101`). `host` 는 우리가 서비스 컨테이너에
    붙이는 네트워크 별칭이므로 기본값을 써도 거짓이 되지 않는다(`ServiceTarget` 머리말).
    **`port` 는 챌린지의 사실이므로 대회 서비스가 다른 포트를 열면 `--service-port` 를
    줘야 한다** — 그래서 기본값을 쓸 때 stderr 에 그 사실을 적는다.
    """
    if image is None:
        if host is not None or port is not None:
            raise ContestError(
                "--service-host/--service-port 는 --service 없이 뜻이 없다 — "
                "서비스 이미지가 없으면 띄울 서비스가 없다"
            )
        return None
    from kisia.runtime.golden_b import SERVICE_NAME, SERVICE_PORT

    if port is None:
        _log(
            f"--service-port 를 주지 않았다 — golden_b.SERVICE_PORT({SERVICE_PORT}) 를 "
            "쓴다. 대회 서비스가 다른 포트를 열면 worker 가 닿지 못한다"
        )
    return manifest_mod.ServiceTarget(
        host=host or SERVICE_NAME, port=SERVICE_PORT if port is None else port
    )


def _stall_rung_of(ladder: tuple[Rung, ...]) -> str | None:
    return STALL_RUNG if any(r.name == STALL_RUNG for r in ladder) else None


def _index_or_none(scheduler: Scheduler, name: str) -> int | None:
    return scheduler.index_of(name) if any(r.name == name for r in scheduler.ladder) else None


# ---------------------------------------------------------------------------
# 벽시계 상한 — `O-54`
# ---------------------------------------------------------------------------


@contextmanager
def _deadline(seconds: int) -> Iterator[bool]:
    """`SIGALRM` 으로 상한을 건다. 걸었으면 `True`.

    **걸지 못한 경우를 걸었다고 적지 않는다** — `SIGALRM` 이 없는 플랫폼에서는 이
    프로세스를 밖에서 죽이는 것(큐의 `--max-wall-s-per-challenge`)만 남는다.
    """
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        if seconds > 0:
            _log(
                f"이 플랫폼에는 SIGALRM 이 없다 — attempt 벽시계 상한 {seconds}s 를 "
                "걸지 못했다. 큐의 프로세스 상한만 남는다 (O-54)"
            )
        yield False
        return

    def _fire(_signum: int, _frame: FrameType | None) -> None:
        raise AttemptTimeoutError(f"attempt 가 {seconds}s 를 넘겼다 — 벽시계 상한 (O-54)")

    previous = signal.signal(signal.SIGALRM, _fire)
    signal.alarm(seconds)
    try:
        yield True
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m kisia.contest",
        description="대회 챌린지 하나를 승격 사다리에 태운다",
    )
    ap.add_argument("--challenge", required=True, type=Path, help="챌린지 디렉터리")
    ap.add_argument("--flag-format", required=True, help="예: kisia{...}")
    ap.add_argument("--challenge-id", default=None)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--max-attempts", required=True, type=int)
    ap.add_argument("--max-usd", default=None)
    ap.add_argument("--description-file", default=None, type=Path)
    ap.add_argument(
        "--service",
        default=None,
        help="챌린지 서비스 이미지. 주면 유형 B 로 돈다 (nc/http 문항)",
    )
    ap.add_argument(
        "--service-host",
        default=None,
        help="서비스 컨테이너에 붙일 네트워크 별칭. 기본값 golden_b.SERVICE_NAME",
    )
    ap.add_argument(
        "--service-port",
        type=int,
        default=None,
        help="서비스가 여는 포트. **챌린지의 사실이다.** 기본값 golden_b.SERVICE_PORT",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="큐의 호출 계약. 결과 줄은 이 값과 무관하게 언제나 stdout 마지막 줄이다",
    )
    ap.add_argument(
        "--attempt-wall-s",
        type=int,
        default=ATTEMPT_WALL_S,
        help="attempt 하나의 벽시계 상한. 통제 블록의 attempt_timeout_s 와 같은 값",
    )
    return ap


def _fixed_from_env() -> dict[str, Any]:
    """`Assignment` 에 담기지 않는 것 전부 — 배치의 사실이다 (`native.py` 머리말).

    **argv 로 받지 않는다.** 키는 `O-11` 이 금지하고, 나머지는 문제마다 달라지지 않는
    배치의 값이라 큐가 문제마다 다시 넘길 이유가 없다.
    """
    missing = [
        name
        for name in (ENV_API_KEY, ENV_IMAGE, ENV_PROBE, ENV_PROBE_ID)
        if not os.environ.get(name)
    ]
    if missing:
        raise ContestError(
            f"환경변수가 비어 있다: {missing} — 이 값들 없이는 attempt 가 시작할 수 없다 "
            "(모델 키·워커 이미지 digest·capability probe artifact 와 그 id)"
        )
    return {
        "pricing": Path(os.environ.get(ENV_PRICING) or "config/pricing.openai.yaml"),
        "image": os.environ[ENV_IMAGE],
        "host_id": os.environ.get(ENV_HOST_ID) or socket.gethostname(),
        "api_key": os.environ[ENV_API_KEY],
        "capability_probe": Path(os.environ[ENV_PROBE]),
        "capability_probe_id": os.environ[ENV_PROBE_ID],
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    try:
        fixed = _fixed_from_env()
        # **stdout 을 잠근다.** 아래에서 무엇이 print 하든 stderr 로 간다 — 결과 한 줄은
        # 이 블록 밖에서 낸다. 큐가 읽는 것은 그 줄 하나다.
        with redirect_stdout(sys.stderr):
            result = run_contest(
                challenge_dir=args.challenge,
                out_dir=args.out,
                flag_format=args.flag_format,
                max_attempts=args.max_attempts,
                challenge_id=args.challenge_id,
                max_usd=None if args.max_usd is None else Decimal(str(args.max_usd)),
                description_file=args.description_file,
                fixed=fixed,
                service_image=args.service,
                service_host=args.service_host,
                service_port=args.service_port,
                attempt_wall_s=args.attempt_wall_s,
            )
    except Exception as exc:
        _log(f"{type(exc).__name__}: {exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
