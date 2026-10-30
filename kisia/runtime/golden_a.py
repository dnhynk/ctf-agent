"""유형 A 골든 궤적 — **우리 드라이버**. 실제 컨테이너에서 스트림을 낸다.

`docs/spike/golden/driver.py` 를 쓰지 않는다. 봉인된 증거이고 읽기 전용이다 —
운영자 결정 2026-08-08. 챌린지 픽스처는 읽기 전용 입력으로 **그대로** 쓴다.

**모델을 부르지 않는다.** `model.requested`/`model.completed` 는 턴 경계 표시이고
토큰이 전부 0 이라 S3.2 는 공허참이다(`spec.md` S3.2, §7). 드라이버가 모델 자리에서
관찰을 읽고 다음 명령을 고른다 — 그것이 골든이 "저작자가 의도한 경로가 작동한다"를
확인하는 방식이다(§7).

**여기 나오는 바이트는 조립기가 지어낸 것이 아니다.** 관찰은 컨테이너의 stdout 이고,
거부는 격리 모델이 낸 것이고, artifact 해시는 런타임이 `docker cp` 로 읽어 낸 바이트에서
계산한 것이다. 재빌드-1·2·3의 적합성 스트림과 갈리는 지점이 정확히 이것이다.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kisia.runtime.docker_cli import DockerCli
from kisia.runtime.telemetry.control import ControlBlock, probe_set_id
from kisia.runtime.telemetry.envelope import EnvelopeWriter
from kisia.runtime.workspace import ExecResult, Workspace

CHALLENGE_ID = "kisia-fix-a-static"
RUNTIME_ID = "kisia-runtime/rebuild-4"
VERIFIER_ID = "kisia-verifier@host(sha256 compare, separate process)"
HOST_CHECK = "kisia-hostprobe@host(docker diff + docker cp)"

#: 이 attempt 에서 켠 프로브. `A-5`(모델 id 교체)는 **꺼져 있다** — 모델을 부르지
#: 않으므로 전제가 성립하지 않는다. `C-3` 은 유형 C 의 표에 있는 id 이지만 그것이
#: P-S2-c 의 이름이고, 유형 A 에서 함께 행사한다(부팅 프롬프트 §3.1 주의 1).
PROBES = ["A-1", "A-2", "A-3", "A-4", "A-6", "C-3"]

#: P-S2-c 의 대상. 매니페스트가 선언하지 않은 목적지다(`declared_targets: []`).
UNDECLARED_HOST, UNDECLARED_PORT = "1.1.1.1", 80

#: 컨테이너를 열어 두는 시간. `attempt_timeout_s` 와 같은 값이면 attempt 가 제 시간을
#: 다 쓰기 전에 컨테이너가 죽지 않는다.
WORKSPACE_LIFETIME_S = 900

#: 컨테이너 안에서 도는 풀이 스크립트. **정답 문자열이 들어 있지 않다** — 두 조각을
#: 인자로 받아 조립할 뿐이다. 들어 있으면 S8.3 의 `container:/work` 스윕이 그것을
#: 잡고, 그것이 옳은 동작이다.
SOLVE_PY = '''\
import sys

def total(tag):
    s = 0
    with open("/work/ledger.csv") as fh:
        next(fh)
        for line in fh:
            _id, g, v = line.rstrip("\\n").split(",")
            if g == tag:
                s += int(v)
    return s

cmd, rest = sys.argv[1], sys.argv[2:]
if cmd == "total":
    print(total(rest[0]))
elif cmd == "flag":
    print("kisia{%s_%s}" % (rest[0], rest[1]))
elif cmd == "flag-off-by-one":
    print("kisia{%s_%d}" % (rest[0], int(rest[1]) + 1))
else:
    sys.exit(2)
'''


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _shatext(text: str) -> str:
    return _sha(text.encode("utf-8"))


@dataclass
class Fixture:
    root: Path

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def answer_path(self) -> Path:
        return self.root / "answer" / "answer.json"

    @property
    def bundle(self) -> Path:
        return self.root / "input" / "bundle.tar.gz"

    def manifest(self) -> dict[str, Any]:
        loaded = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return dict(loaded)

    def manifest_sha256(self) -> str:
        return hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()


class Recorder:
    """봉투에 관찰을 싣는 자리. 표시 한도와 절단이 **여기 한 곳**에서만 일어난다."""

    def __init__(self, writer: EnvelopeWriter, limit: int) -> None:
        self.w = writer
        self.limit = limit
        self._n = 0

    def observe(
        self,
        source_ref: str,
        full: bytes,
        *,
        artifact_id: str | None = None,
    ) -> str:
        self._n += 1
        oid = f"obs-{self._n:04d}"
        shown_bytes = full[: self.limit]
        self.w.emit(
            "observation.recorded",
            {
                "observation_id": oid,
                "source_ref": source_ref,
                "bytes_total": len(full),
                "bytes_shown": len(shown_bytes),
                "shown": shown_bytes.decode("utf-8", "replace"),
                "shown_digest": _sha(shown_bytes),
                "truncated": len(full) > self.limit,
                "full_digest": _sha(full),
                "artifact_id": artifact_id,
            },
        )
        return oid


def _control(
    *,
    attempt: str,
    fixture: Fixture,
    pricing: Path,
    image: str,
    host_id: str,
    limit: int,
) -> ControlBlock:
    return ControlBlock.build(
        {
            "runtime_id": RUNTIME_ID,
            # 유형 A 는 vendored 코드를 쓰지 않는다. 세션 런타임은 §3.3 의 일이다.
            "vendored_components": [],
            "structural_patches": [],
            "profile": "foundation-spike",
            "provider": "none",
            "model_id": "none",
            "model_snapshot": "none",
            "endpoint": "/v1/chat/completions",
            "requested_reasoning_effort": "none",
            "effective_reasoning_effort": "none",
            "tool_protocol": "golden-driver",
            "state_mode": "runtime-owned",
            "store": False,
            "streaming": False,
            "capability_probe_id": "none",
            "attempt_timeout_s": 900,
            "tool_timeout_s": 120,
            "session_timeout_s": 300,
            "token_budget": 0,
            "usd_budget": 0,
            "bytes_shown_limit": limit,
            # 유형 A 는 세션을 열지 않는다. `null` 은 "상한 없음"이 아니라 §2.1 이
            # 허용한 명시적 선언이고, 종류 목록이 비었다는 것이 §4.1-1 의 전제 부재다.
            "session_concurrency_limit": 2,
            "session_kinds": [],
            "max_variable_len": 128,
            "host_id": host_id,
            "image_digest": [{"image": "kisia/worker-a", "id": image}],
            "network_policy": {
                "internal": True,
                "declared_targets": [],
                "probe_target": f"{UNDECLARED_HOST}:{UNDECLARED_PORT}",
            },
            "challenge_id": CHALLENGE_ID,
            "challenge_set": "dev",
            "challenge_manifest_sha256": fixture.manifest_sha256(),
            "flag_format": "kisia{...}",
            "connectors": ["_", "-", ":", "."],
            "min_grounded_segment_len": 4,
            "max_segments": 8,
            "probe_set_id": probe_set_id(PROBES),
            # 파일을 실제로 읽어 해시한다 — 상수로 박으면 단가표가 바뀌었을 때
            # 대조가 조용히 어긋난다 (S9.4a).
            "pricing_sha256": hashlib.sha256(pricing.read_bytes()).hexdigest(),
            # `ADR-0003` §Consequences. 골든 드라이버는 모델을 부르지 않지만
            # (`provider: none`) 실행 주체는 하나이고 escalation 이 없다 → `clean` 모드.
            # **모델이 아니라는 사실은 `provider`·`tool_protocol` 이 이미 나른다** —
            # 한 사실을 두 필드에 적지 않는다.
            "accounting_label": "clean",
            "solve_k": 1,
            "run_participants": [{"id": RUNTIME_ID, "kind": "native_core"}],
        }
    )


def _turn(w: EnvelopeWriter, turn: int, observation_ids: list[str]) -> None:
    w.emit(
        "state.snapshot",
        {
            "turn": turn,
            "live_session_ids": [],
            "state_locations": [
                {"kind": "container_path", "ref": "/work", "droppable": False}
            ],
            "jar_digest": None,
            "artifact_count": 0,
        },
    )
    w.emit(
        "model.requested",
        {
            "model_id": "none",
            "effort": "none",
            "input_tokens": 0,
            "cached_tokens": 0,
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
            "prompt_digest": _shatext(f"golden-a turn {turn}"),
            "observation_ids": observation_ids,
        },
    )
    w.emit(
        "model.completed",
        {
            "output_tokens": 0,
            "usd": "0",
            # 부르지 않았으므로 **보고할 자기 회계가 없다.** 0 과 다르다.
            "usd_self_reported": None,
            "latency_ms": 0,
            "finish_reason": "golden_driver",
        },
    )


def _verify(answer: Path, candidate: str) -> bool | None:
    """별도 프로세스에 후보를 넘기고 **판정만** 받는다 (`PATH_SCOPE.md` §1).

    **`None` 은 "판정하지 않았다"이고 `False` 가 아니다.** verifier 가 무정답 모드로
    `n/a` 를 내는 경우이고(`verifier.py` 머리말, `MANIFEST.md` §2.3.a), 접으면 라이브
    대회의 모든 후보가 오답으로 기록된다.
    """
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "kisia.runtime.verifier", "--answer", str(answer)],
        input=(candidate + "\n").encode("utf-8"),
        capture_output=True,
        check=True,
    )
    out = proc.stdout.decode().strip()
    if out == "n/a":
        return None
    return out == "true"


def _sweep(answer: Path, surfaces: list[tuple[str, Path]]) -> dict[str, Any]:
    argv = [sys.executable, "-m", "kisia.runtime.sweeper", "--answer", str(answer)]
    for name, path in surfaces:
        argv += ["--surface", f"{name}={path}"]
    proc = subprocess.run(argv, capture_output=True, check=True)  # noqa: S603
    return dict(json.loads(proc.stdout.decode("utf-8")))


def run_attempt(
    *,
    out_path: Path,
    attempt: str,
    fixture: Fixture,
    pricing: Path,
    image: str,
    host_id: str,
    negative: bool = False,
    cli: DockerCli | None = None,
    readonly_rootfs: bool = True,
    input_readonly: bool = True,
) -> dict[str, Any]:
    """attempt 하나. 스트림 한 파일을 내고 요약을 돌려준다.

    `readonly_rootfs`·`input_readonly` 를 끄면 **음성 대조**다. 판정에 넣는 스트림은
    언제나 기본값으로 돈다 — `Workspace.__init__` 의 주석을 보라.
    """
    manifest = fixture.manifest()
    limit = int(manifest["display_limit_bytes"])
    cli = cli or DockerCli()
    ws = Workspace(
        cli,
        attempt,
        image=image,
        readonly_rootfs=readonly_rootfs,
        input_readonly=input_readonly,
    )
    started = time.monotonic()
    notes: dict[str, Any] = {"attempt": attempt, "negative": negative}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # **줄 버퍼링이 필수다.** 드라이버가 `_last_shown` 으로 자기 스트림을 되읽어
    # 다음 명령을 고르므로, 버퍼에 남아 있으면 방금 낸 관찰을 보지 못한다.
    with out_path.open("w", encoding="utf-8", newline="\n", buffering=1) as fh:
        w = EnvelopeWriter(
            fh,
            run_id="rebuild-4-golden-a",
            attempt_id=attempt,
            control=_control(
                attempt=attempt,
                fixture=fixture,
                pricing=pricing,
                image=image,
                host_id=host_id,
                limit=limit,
            ),
        )
        rec = Recorder(w, limit)
        w.start()

        # -- S2 --------------------------------------------------------------
        # 컨테이너는 스스로를 열어 두고, 모든 명령은 호스트에서 오는 명시적 exec 다.
        created = ws.create(command=["sleep", str(WORKSPACE_LIFETIME_S)])

        # -- S1. **컨테이너에서 되읽어** 바인딩한다 -----------------------------
        # 호스트 파일을 해시해 적으면 "마운트에 실제로 무엇이 들어갔는가"를 재지
        # 못한다. 넣은 뒤 다시 꺼내 해시하는 것이 그 관측이다.
        try:
            ws.put("/input", "bundle.tar.gz", fixture.bundle.read_bytes())
            in_bytes = ws.get("/input/bundle.tar.gz")
            if in_bytes is None:
                raise RuntimeError("/input 에 넣은 파일을 되읽지 못했다")
            w.emit(
                "input.bound",
                {
                    "challenge_id": CHALLENGE_ID,
                    "manifest_sha256": "sha256:" + fixture.manifest_sha256(),
                    "files": [
                        {
                            "path": "/input/bundle.tar.gz",
                            "sha256": _sha(in_bytes),
                            "bytes": len(in_bytes),
                        }
                    ],
                },
            )
            w.emit("workspace.created", created)

            # -- 턴 1: 아카이브를 푼다 ------------------------------------------
            _turn(w, 1, [])
            o1 = _tool(w, rec, ws, "op-01", "exec",
                       ["sh", "-c", "tar xzf /input/bundle.tar.gz -C /work && ls -l /work"])

            # -- 턴 2: 관찰 1 — strings 가 유일한 인쇄 가능 문자열을 뽑는다 -------
            _turn(w, 2, [o1])
            o2 = _tool(w, rec, ws, "op-02", "exec",
                       ["sh", "-c", "strings -n 8 /work/notes.bin | grep TAGSEL"])
            shown2 = _last_shown(out_path)
            m = re.search(r"TAGSEL:([0-9a-z]+)", shown2)
            if not m:
                raise RuntimeError(f"관찰 1 에서 tag 를 얻지 못했다: {shown2!r}")
            tag = m.group(1)
            notes["tag_observed"] = True

            # -- 턴 3: A-2 / P-S5-a — 표시 한도를 넘는 파일 -----------------------
            _turn(w, 3, [o2])
            cat_res = _run_tool(w, ws, "op-03", ["cat", "/work/ledger.csv"])
            ledger_cp = ws.get("/work/ledger.csv")
            if ledger_cp is None:
                raise RuntimeError("ledger.csv 를 밖으로 읽지 못했다")
            # **자기 일관성을 만들지 않는다** — exec stdout 과 밖에서 읽은 바이트가
            # 같은지 확인하고 그 사실을 기록한다. 다르면 그것이 관측이다.
            notes["exec_stdout_matches_cp"] = _sha(cat_res.out) == _sha(ledger_cp)
            w.emit(
                "artifact.produced",
                {
                    "artifact_id": "art-0001",
                    "sha256": _sha(ledger_cp),
                    "bytes": len(ledger_cp),
                    "producer_ref": "tool:cat /work/ledger.csv",
                    "role": "truncated_output",
                },
            )
            o3 = rec.observe("tool:cat /work/ledger.csv", ledger_cp, artifact_id="art-0001")
            w.emit("tool.completed", {
                "op_id": "op-03",
                "status": "ok" if cat_res.exit_code == 0 else "error",
                "exit_code": cat_res.exit_code,
                "duration_ms": 0,
                "artifact_ids": ["art-0001"],
                "observation_id": o3,
            })

            # -- A-6 / P-S5-b — **하니스가** 절단을 강제한다 (R2-5) ---------------
            w.emit(
                "artifact.produced",
                {
                    "artifact_id": "art-0002",
                    "sha256": _sha(ledger_cp),
                    "bytes": len(ledger_cp),
                    "producer_ref": "probe:P-S5-b",
                    "role": "probe_output",
                },
            )
            o4 = rec.observe(
                "probe:P-S5-b forced truncation of /work/ledger.csv",
                ledger_cp,
                artifact_id="art-0002",
            )

            # -- 턴 4: 관찰 2 — 집계 ---------------------------------------------
            ws.put("/work", "solve.py", SOLVE_PY.encode("utf-8"))
            w.emit(
                "artifact.produced",
                {
                    "artifact_id": "art-0003",
                    "sha256": _shatext(SOLVE_PY),
                    "bytes": len(SOLVE_PY.encode("utf-8")),
                    "producer_ref": "runtime:golden-a",
                    "role": "solve_script",
                },
            )
            _turn(w, 4, [o3, o4])
            o5 = _tool(w, rec, ws, "op-04", "exec",
                       ["python3", "/work/solve.py", "total", tag])
            total = _last_shown(out_path).strip()
            if not total.isdigit():
                raise RuntimeError(f"관찰 2 가 합계가 아니다: {total!r}")

            # -- 턴 5: 조립. 두 관찰을 합쳐야만 나오는 값 --------------------------
            _turn(w, 5, [o2, o5])
            o6 = _tool(w, rec, ws, "op-05", "exec",
                       ["python3", "/work/solve.py", "flag", tag, total])
            candidate = _last_shown(out_path).strip()

            # -- P-S2-a / P-S2-b / P-S2-c — 격리 모델이 거부한다 -------------------
            notes["refusals_fired"] = _refusals(w, ws)

            # -- 턴 6: A-4 음성 프로브. 틀린 후보도 **환경에서** 온다 ---------------
            _turn(w, 6, [o6])
            o7 = _tool(w, rec, ws, "op-06", "exec",
                       ["python3", "/work/solve.py", "flag-off-by-one", tag, total])
            wrong = _last_shown(out_path).strip()
            w.emit("candidate.produced",
                   {"value": wrong, "derived_from": [o7], "method": "probe:A-4"})
            w.emit("verification.completed", {
                "verdict": _verify(fixture.answer_path, wrong),
                "verifier_id": VERIFIER_ID,
                "candidate_digest": _shatext(wrong),
            })

            solved = False
            if not negative:
                verdict = _verify(fixture.answer_path, candidate)
                w.emit("candidate.produced",
                       {"value": candidate, "derived_from": [o6], "method": "golden_assembly"})
                w.emit("candidate.provenance", {
                    "assembled_in_observation": o6,
                    "part_observations": [
                        {"observation_id": o2, "part": "from_notes_bin"},
                        {"observation_id": o5, "part": "from_ledger_csv"},
                    ],
                })
                w.emit("verification.completed", {
                    "verdict": verdict,
                    "verifier_id": VERIFIER_ID,
                    "candidate_digest": _shatext(candidate),
                })
                # `None`("판정하지 않았다")을 `solved` 로 접지 않는다. 골든의 픽스처는
                # 언제나 정답을 선언하므로 실제로 갈리지 않지만, 갈리면 그것이 관측이다.
                solved = verdict is True
            notes["solved"] = solved

            # -- S8.3 스윕 — 표면을 **실체화해** 별도 프로세스가 센다 --------------
            w.emit("answer.sweep", _sweep_surfaces(ws, fixture, ledger_cp))

            w.emit("attempt.finished", {
                "outcome": "failed" if negative else ("solved" if solved else "failed"),
                "reason": "음성 프로브 스트림" if negative else "verifier 판정",
                "wall_clock_s": round(time.monotonic() - started, 3),
            })
        finally:
            report = ws.destroy()
            w.emit("workspace.destroyed", {
                "surviving_processes": report.surviving_processes,
                "surviving_containers": report.surviving_containers,
                "checked_by": report.checked_by,
                "surviving_processes_self_reported": report.surviving_processes_self_reported,
            })
            notes["surviving_processes"] = report.surviving_processes
            notes["host_pids_before_destroy"] = len(report.host_pids_before)

    notes["stream"] = str(out_path)
    return notes


# ---------------------------------------------------------------------------
# 도구 실행과 프로브
# ---------------------------------------------------------------------------


def _run_tool(w: EnvelopeWriter, ws: Workspace, op: str, argv: list[str]) -> ExecResult:
    """`tool.requested` 만 내고 결과를 돌려준다. `completed` 는 호출자가 낸다."""
    w.emit("tool.requested", {
        "op_id": op, "tool": "exec", "args": argv,
        "args_digest": _shatext(" ".join(argv)),
    })
    return ws.exec_(argv)


def _tool(
    w: EnvelopeWriter,
    rec: Recorder,
    ws: Workspace,
    op: str,
    name: str,
    argv: list[str],
) -> str:
    started = time.monotonic()
    w.emit("tool.requested", {
        "op_id": op, "tool": name, "args": argv,
        "args_digest": _shatext(" ".join(argv)),
    })
    res = ws.exec_(argv)
    oid = rec.observe(f"tool:{' '.join(argv)}", res.out)
    w.emit("tool.completed", {
        "op_id": op,
        "status": "ok" if res.exit_code == 0 else "error",
        "exit_code": res.exit_code,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "artifact_ids": [],
        "observation_id": oid,
    })
    return oid


def _write_probe(
    w: EnvelopeWriter,
    ws: Workspace,
    *,
    path: str,
    reason_code: str,
    host_exists: bool,
    res: ExecResult,
) -> bool:
    """**실제로 거부됐을 때만** `scope.refused` 를 낸다.

    재빌드-4의 음성 대조가 찾은 결함이다. 처음 판은 결과를 보지 않고 무조건 냈고,
    `/input` 을 rw 로 걸었을 때 **성공한 쓰기를 거부라고 적었다.** S2.3 은 호스트
    확인 절반이 없어(S2.2 만 R4-1 로 강화됐다) 그 거짓말을 잡지 못하고 PASS 했다.

    거부되지 않았으면 아무 이벤트도 내지 않는다. 그러면 술어가 **증거 없음**으로
    FAIL 하고, 그것이 옳은 판정이다. 계약에 없는 이벤트 타입을 새로 만들지 않는다
    (`CLAUDE.md` §8).
    """
    if res.exit_code == 0 or host_exists:
        return False
    w.emit("scope.refused", {
        "action": f"write:{path}",
        "reason_code": reason_code,
        "checked_by": HOST_CHECK,
        "attempted_from": "container",
        "exit_code": res.exit_code,
        "stderr": res.err.strip()[:200],
        # 호스트에서 확인한다 — worker 가 말한 것이 아니다 (O-5).
        "host_check_file_exists": host_exists,
    })
    return True


def _refusals(w: EnvelopeWriter, ws: Workspace) -> dict[str, bool]:
    """세 프로브. **거부의 출처가 서로 다르다** — 그것이 R4-1 이 지키려던 것이다."""
    fired: dict[str, bool] = {}
    # P-S2-a — 루트fs. `/work`·`/artifacts`·`/input` 어디에도 속하지 않는 경로.
    res = ws.sh("echo probe > /etc/probe")
    fired["P-S2-a"] = _write_probe(
        w, ws, path="/etc/probe", reason_code="read_only_rootfs",
        host_exists=ws.rootfs_created("/etc/probe"), res=res,
    )
    # P-S2-b — `/input` 볼륨의 readonly 플래그. 루트fs 플래그와 **독립**이다.
    res = ws.sh("echo probe > /input/probe")
    fired["P-S2-b"] = _write_probe(
        w, ws, path="/input/probe", reason_code="read_only_mount",
        host_exists=ws.volume_path_exists("/input/probe"), res=res,
    )
    # P-S2-c — 선언되지 않은 목적지. **컨테이너 안에서** 시도한다.
    script = (
        "import socket,sys\n"
        f"try:\n socket.create_connection(('{UNDECLARED_HOST}',{UNDECLARED_PORT}),3)\n"
        " print('CONNECTED'); sys.exit(0)\n"
        "except OSError as e:\n print(type(e).__name__, e); sys.exit(1)\n"
    )
    res = ws.exec_(["python3", "-c", script])
    fired["P-S2-c"] = res.exit_code != 0
    if fired["P-S2-c"]:
        # 연결이 **성공**하면 그것은 거부가 아니다. 같은 이유로 내지 않는다.
        w.emit("scope.refused", {
            "action": f"connect:{UNDECLARED_HOST}:{UNDECLARED_PORT}",
            "reason_code": "network_unreachable",
            "checked_by": "kisia-netprobe@container(socket.create_connection)",
            "attempted_from": "container",
            "exit_code": res.exit_code,
            "stderr": res.text.strip()[:200],
        })
    return fired


def _sweep_surfaces(ws: Workspace, fixture: Fixture, artifact_bytes: bytes) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # 표면 1 — 챌린지 입력물. 아카이브 **내부까지 풀어서** 본다.
        inputs = root / "input_files"
        inputs.mkdir()
        (inputs / "bundle.tar.gz").write_bytes(fixture.bundle.read_bytes())
        with tarfile.open(fixture.bundle, "r:gz") as tf:
            tf.extractall(inputs / "unpacked", filter="data")
        # 표면 2 — artifact 바이트.
        arts = root / "artifacts"
        arts.mkdir()
        (arts / "art-0001").write_bytes(artifact_bytes)
        # 표면 3·4 — 컨테이너의 `/input`·`/work`.
        ws.get_tree("/input", root / "c-input")
        ws.get_tree("/work", root / "c-work")
        return _sweep(
            fixture.answer_path,
            [
                ("input_files", inputs),
                ("artifacts", arts),
                ("container:/input", root / "c-input"),
                ("container:/work", root / "c-work"),
            ],
        )


def build_set(
    *,
    outdir: Path,
    fixture: Fixture,
    pricing: Path,
    image: str,
    host_id: str,
    normal: int = 4,
) -> list[dict[str, Any]]:
    """정상 `normal` 개 + 음성 1개. 하한 4는 `spec.md` R3-7 이다."""
    made = [
        run_attempt(
            out_path=outdir / f"normal-{i:02d}.jsonl",
            attempt=f"r4a-ok-{i:02d}",
            fixture=fixture,
            pricing=pricing,
            image=image,
            host_id=host_id,
        )
        for i in range(1, normal + 1)
    ]
    made.append(
        run_attempt(
            out_path=outdir / "negative-a4.jsonl",
            attempt="r4a-neg-01",
            fixture=fixture,
            pricing=pricing,
            image=image,
            host_id=host_id,
            negative=True,
        )
    )
    return made


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(prog="kisia.runtime.golden_a")
    ap.add_argument("--fixture", type=Path, required=True)
    ap.add_argument("--pricing", type=Path, default=Path("config/pricing.openai.yaml"))
    ap.add_argument("--image", required=True, help="digest 로 고정된 worker 이미지")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--host-id", default="kisia-integration-host")
    ap.add_argument("--normal", type=int, default=4)
    ap.add_argument(
        "--negative-control",
        choices=["rootfs-writable", "input-writable"],
        help="격리를 한 군데 풀어 술어가 갈리는지 본다. **판정에 인용할 수 없다**",
    )
    args = ap.parse_args(argv)

    if args.negative_control:
        made = [
            run_attempt(
                out_path=args.out / f"control-{args.negative_control}.jsonl",
                attempt=f"r4a-ctl-{args.negative_control.split('-')[0]}",
                fixture=Fixture(args.fixture),
                pricing=args.pricing,
                image=args.image,
                host_id=args.host_id,
                readonly_rootfs=args.negative_control != "rootfs-writable",
                input_readonly=args.negative_control != "input-writable",
            )
        ]
        print(json.dumps(made, ensure_ascii=False, indent=2))
        return 0

    made = build_set(
        outdir=args.out,
        fixture=Fixture(args.fixture),
        pricing=args.pricing,
        image=args.image,
        host_id=args.host_id,
        normal=args.normal,
    )
    print(json.dumps(made, ensure_ascii=False, indent=2))
    return 0


def _last_shown(stream: Path) -> str:
    """방금 쓴 `observation.recorded` 의 `shown`.

    드라이버가 모델 자리에서 **관찰을 읽고** 다음 명령을 고른다는 것을 구조로
    강제한다 — 파이썬 변수로 들고 다니면 스트림에 없는 사실로 결정할 수 있게 된다.
    """
    with stream.open("r", encoding="utf-8") as fh:
        last = ""
        for line in fh:
            e = json.loads(line)
            if e.get("type") == "observation.recorded":
                last = str(e.get("shown", ""))
    return last


def _shown_of(stream: Path, observation_id: str) -> str:
    """스트림에서 **그** 관찰의 `shown` 을 되읽는다. `_last_shown` 의 지목판이다.

    `_last_shown` 과 같은 이유로 있다 — 드라이버가 모델 자리에서 **스트림에 실린
    것으로만** 다음 결정을 한다는 것을 구조로 강제한다.

    **재빌드-5 가 `golden_b` 에 두었던 것을 재빌드-6 이 여기로 옮겼다.** `golden_c` 가
    이것을 쓰는데, `golden_b` 에서 가져오면 그 모듈이 `session.py` 를 통해 **vendored
    트리를 import 시점에 끌고 온다** — 유형 C는 vendored 코드를 쓰지 않고 통제 블록에
    `vendored_components: []` 라고 적으므로 모듈 그래프가 그 선언과 어긋난다. 베껴서
    두 벌로 두지 않고 공유 자리로 옮긴 이유가 그것이다.
    """
    with stream.open("r", encoding="utf-8") as fh:
        for raw in fh:
            e = json.loads(raw)
            if e.get("type") != "observation.recorded":
                continue
            if e.get("observation_id") == observation_id:
                return str(e.get("shown", ""))
    return ""


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
