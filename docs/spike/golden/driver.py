#!/usr/bin/env python3
"""골든 트라젝토리 드라이버 — 도구 계층 + SEAM_CONTRACT §1 봉투 emitter.

**이것이 무엇이 아닌지부터.**

- **검사기가 아니다.** 술어를 하나도 평가하지 않는다. 이벤트를 낼 뿐이다. 판정은
  세션 C의 산출물이다.
- **G(참조 구현)가 아니다.** SEAM_CONTRACT §4.1의 네 요구(newline 동일성, 백그라운드
  잡까지 포함한 생존자 0, 좀비 제외, waitpid 상태값에 의존하지 않는 live 판정)를
  구현하지 않는다. 그것은 세션 C가 만드는 G의 전부다. 여기서는 세션을 열고 닫을 뿐이고,
  close 시점의 자손 상태는 **관측해서 기록**할 뿐 보장하지 않는다.
- **arm이 아니다.** 모델을 호출하지 않는다. 세션 B는 모델 비용을 0으로 끝낸다.

**이것이 무엇인지.** §9.2.1이 요구하는 "완벽한 에이전트의 궤적"을 재생하는 최소 장치다.
정답을 하드코딩하지 않고, 호스트에서 파일을 직접 읽지 않고, 정답 파일을 들여다보지
않는다. 모든 관찰은 worker 컨테이너 안에서 나오고, worker 가 보는 것은 에이전트가 보게
될 것과 같다.

**모델 턴의 대체.** `FOUNDATION_DECISION.md` §9.1이 G에 대해 이미 정한 것을 그대로
쓴다 — 모델이 없으므로 턴 경계를 시간 간격을 둔 호출 경계로 대체한다. `turn()`은
`model.requested`/`model.completed` 쌍을 `model_id="none"`,
`finish_reason="golden_turn_boundary"`, 토큰·비용 0으로 낸다. **가짜 모델 호출이
아니라 턴 경계의 표시다.** 이렇게 하지 않으면 S4의 "session.io 가 model.completed
3개 이상을 사이에 두고 나타난다"를 골든 스트림 위에서 평가할 수 없고, 세션 C가 그
평가 불능을 술어의 결함으로 오독하게 된다.

**§1.3에 없는 필드를 두 개 더 싣는다.** 둘 다 §1.3이 "핵심 필드"의 최소 집합이라는
전제 위에서 더한 것이고, 없으면 세션 C가 술어를 아예 평가할 수 없어서 더한다.
  observation.recorded.shown  표시된 바이트 원문. S7의 "후보 문자열이 그 관찰 안에
                              실제로 들어 있다"와 S8의 "검사기가 실제로 검색해서
                              확인한다"는 내용 없이는 평가 불가능하다. SEAM_CONTRACT
                              §7-5가 합성 챌린지에서는 원문 기록을 허용한다.
  tool.requested.args         args_digest 만으로는 스트림을 다른 기계에서 재생할 수
                              없다(P-S9-a). 합성이므로 원문을 남긴다.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import threading
import time
from datetime import datetime, timezone

TOOL_TIMEOUT_S = 120
SESSION_TIMEOUT_S = 300
ATTEMPT_TIMEOUT_S = 900


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode())


def run(argv: list[str], timeout: int = TOOL_TIMEOUT_S, stdin: bytes | None = None):
    return subprocess.run(argv, capture_output=True, timeout=timeout, input=stdin)


# --------------------------------------------------------------------------- #
# emitter
# --------------------------------------------------------------------------- #


class Emitter:
    """§1.1의 공통 필드를 붙여 JSONL 한 줄씩 쓴다.

    `seq`는 1부터 빈틈없이 증가한다(§1.1). 빈틈이 생길 수 있는 유일한 경로는 예외로
    중간에 죽는 것인데, 그 경우 스트림은 끝이 잘릴 뿐 빈틈이 생기지 않는다 —
    seq는 emit 시점에만 증가하고 매 줄 flush 한다.
    """

    def __init__(self, path: pathlib.Path, run_id: str, attempt_id: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f = path.open("w", encoding="utf-8")
        self.run_id = run_id
        self.attempt_id = attempt_id
        self.seq = 0

    def emit(self, type_: str, **fields) -> int:
        self.seq += 1
        ev = {
            "ts": utcnow(),
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "seq": self.seq,
            "type": type_,
        }
        ev.update(fields)
        self._f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        self._f.flush()
        return self.seq

    def close(self) -> None:
        self._f.close()


# --------------------------------------------------------------------------- #
# 지속 세션
# --------------------------------------------------------------------------- #


class Session:
    """worker 안에서 `docker exec -i` 로 연 하나의 지속 프로세스.

    유형 B의 요점은 이 프로세스가 턴을 가로질러 살아 있어야 한다는 것이다. TCP 연결은
    이 프로세스가 든 fd 3 위에 있으므로, 프로세스가 죽으면 연결도 죽고 nonce 도 사라진다.
    """

    def __init__(self, golden: "Golden", session_id: str, argv: list[str], kind: str):
        self.g = golden
        self.session_id = session_id
        self.kind = kind
        self.session_seq = 0
        self.leader_pid: int | None = None
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._transcript = bytearray()

        self.proc = subprocess.Popen(
            ["docker", "exec", "-i", golden.container, *argv],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        while True:
            chunk = self.proc.stdout.read(1)
            if not chunk:
                return
            with self._lock:
                self._buf.extend(chunk)
                self._transcript.extend(chunk)

    def _send_raw(self, data: str) -> None:
        self.session_seq += 1
        b = data.encode()
        self.proc.stdin.write(b)
        self.proc.stdin.flush()
        self.g.em.emit(
            "session.io",
            session_id=self.session_id,
            session_seq=self.session_seq,
            direction="out",
            bytes=len(b),
        )

    def _read_until(self, pattern: re.Pattern, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                m = pattern.search(bytes(self._buf))
                if m:
                    out = bytes(self._buf[: m.end()])
                    del self._buf[: m.end()]
                    return out
            if time.monotonic() > deadline:
                with self._lock:
                    out = bytes(self._buf)
                    self._buf.clear()
                raise TimeoutError(f"session read timeout; partial={out[-200:]!r}")
            time.sleep(0.02)

    def _exchange(self, cmd: str) -> tuple[bytes, int]:
        """명령 하나를 보내고 sentinel 까지 읽는다. 이벤트를 내지 않는다."""
        marker = f"__KSEQ{self.session_seq + 1}__"
        self._send_quiet(f"{cmd}\nprintf '{marker}%s\\n' $?\n")
        pat = re.compile(re.escape(marker.encode()) + rb"(\d+)\r?\n")
        raw = self._read_until(pat, SESSION_TIMEOUT_S)
        m = pat.search(raw)
        return raw[: m.start()], int(m.group(1))

    def _send_quiet(self, data: str) -> None:
        self.proc.stdin.write(data.encode())
        self.proc.stdin.flush()

    def probe_leader_pid(self) -> int | None:
        """세션 자신의 in-container pid. §4의 `snapshot(session_id) -> pid` 에 해당하는
        런타임 자기 인식이고 에이전트의 관찰이 아니므로 이벤트를 내지 않는다."""
        body, _ = self._exchange("printf 'pid=%s\\n' $$")
        m = re.search(rb"pid=(\d+)", body)
        self.leader_pid = int(m.group(1)) if m else None
        return self.leader_pid

    def run(self, cmd: str, source_ref: str) -> tuple[str, str]:
        """명령 하나를 보내고 그 출력을 관찰로 기록한다. -> (obs_id, 출력 텍스트)"""
        marker = f"__KSEQ{self.session_seq + 1}__"
        self._send_raw(f"{cmd}\nprintf '{marker}%s\\n' $?\n")
        pat = re.compile(re.escape(marker.encode()) + rb"(\d+)\r?\n")
        raw = self._read_until(pat, SESSION_TIMEOUT_S)
        m = pat.search(raw)
        status = int(m.group(1))
        body = raw[: m.start()]

        self.session_seq += 1
        self.g.em.emit(
            "session.io",
            session_id=self.session_id,
            session_seq=self.session_seq,
            direction="in",
            bytes=len(body),
            exit_status=status,
        )
        obs = self.g.observe(source_ref, body)
        return obs, body.decode("utf-8", "replace")

    def close(self, grace_ms: int = 3000) -> None:
        """닫고, **후보 밖에서** 자손 상태를 관측한다.

        관측만 한다. 정리를 보장하지 않는다 — 그것은 §4.1-2의 요구이고 G의 몫이다.
        여기서 남기는 숫자는 세션 C가 자기 구현을 비교할 기준선이다.
        """
        before = self.g.descendants(self.leader_pid)
        try:
            self._send_raw("exit\n")
        except (BrokenPipeError, OSError):
            pass
        try:
            self.proc.wait(timeout=grace_ms / 1000)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
        time.sleep(0.3)
        after = self.g.descendants(self.leader_pid)

        with self._lock:
            transcript = bytes(self._transcript)
        art = self.g.artifact(transcript, producer_ref=f"session:{self.session_id}")

        alive_after = {p["pid"] for p in after if not p["stat"].startswith("Z")}
        gone = [p for p in before if p["pid"] not in alive_after]

        self.g.live_sessions.discard(self.session_id)
        self.g.em.emit(
            "session.closed",
            session_id=self.session_id,
            transcript_artifact_id=art,
            exit_status=self.proc.returncode,
            descendants_killed=len(gone),
            survivors=[p for p in after if not p["stat"].startswith("Z")],
            zombies_excluded=[p for p in after if p["stat"].startswith("Z")],
            checked_by="golden-driver@host(docker top)",
            checked_note="후보 밖 관측이다. 정리를 보장하지 않는다 — §4.1-2는 G의 요구다.",
        )


# --------------------------------------------------------------------------- #
# 골든 실행 컨텍스트
# --------------------------------------------------------------------------- #


class Golden:
    def __init__(
        self,
        fixture_dir: pathlib.Path,
        run_dir: pathlib.Path,
        emitter: Emitter,
        worker_image: str,
        network: str,
        host_id: str,
        arm_id: str,
    ):
        self.fixture = fixture_dir
        self.manifest = json.loads((fixture_dir / "manifest.json").read_text(encoding="utf-8"))
        self.manifest_bytes = (fixture_dir / "manifest.json").read_bytes()
        self.run_dir = run_dir
        self.em = emitter
        self.worker_image = worker_image
        self.network = network
        self.host_id = host_id
        self.arm_id = arm_id

        self.limit = int(self.manifest["display_limit_bytes"])
        self.container = f"golden-worker-{emitter.attempt_id}"
        self.container_id: str | None = None
        self.jar: dict[str, str] = {}
        self.live_sessions: set[str] = set()
        self.turn_no = 0
        self._pending_obs: list[str] = []
        self._n_obs = 0
        self._n_art = 0
        self._n_sess = 0
        self.t0 = time.monotonic()

        self.work_dir = run_dir / "work"
        self.art_dir = run_dir / "artifacts"
        self.stream_art_dir = run_dir / "stream-artifacts"
        for d in (self.work_dir, self.art_dir, self.stream_art_dir):
            d.mkdir(parents=True, exist_ok=True)

    # -- 관찰과 artifact ---------------------------------------------------- #

    def artifact(self, data: bytes, producer_ref: str) -> str:
        self._n_art += 1
        aid = f"art-{self._n_art:04d}"
        (self.stream_art_dir / aid).write_bytes(data)
        self.em.emit(
            "artifact.produced",
            artifact_id=aid,
            sha256=sha256_bytes(data),
            bytes=len(data),
            producer_ref=producer_ref,
        )
        return aid

    def observe(self, source_ref: str, data: bytes) -> str:
        """§1.3 `observation.recorded`. 절단은 결정론적 — 앞에서 limit 바이트."""
        self._n_obs += 1
        oid = f"obs-{self._n_obs:04d}"
        truncated = len(data) > self.limit
        shown = data[: self.limit]
        aid = self.artifact(data, producer_ref=source_ref) if truncated else None
        self.em.emit(
            "observation.recorded",
            observation_id=oid,
            source_ref=source_ref,
            bytes_total=len(data),
            bytes_shown=len(shown),
            truncated=truncated,
            full_digest=sha256_bytes(data),
            artifact_id=aid,
            shown=shown.decode("utf-8", "replace"),
            shown_digest=sha256_bytes(shown),
        )
        self._pending_obs.append(oid)
        return oid

    # -- attempt 경계 ------------------------------------------------------- #

    def attempt_started(self, note: str) -> None:
        img = run(["docker", "image", "inspect", "--format", "{{.Id}}", self.worker_image])
        worker_digest = img.stdout.decode().strip()
        digests = [{"image": self.worker_image, "id": worker_digest}]
        tgt = self.manifest.get("target")
        if tgt:
            svc = run(
                ["docker", "inspect", "--format", "{{.Image}}", tgt["id"]]
            ).stdout.decode().strip()
            digests.append({"image": f"container:{tgt['id']}", "id": svc})

        self.em.emit(
            "attempt.started",
            arm_id=self.arm_id,
            candidate_repo="n/a (golden trajectory; 후보를 실행하지 않는다)",
            candidate_commit="n/a",
            structural_patches=[],
            model_id="none",
            reasoning_effort="none",
            model_note=(
                "세션 B는 모델을 호출하지 않는다. 턴 경계는 FOUNDATION_DECISION §9.1이 "
                "G에 대해 정한 대체(호출을 시간 간격을 두고 나눈다)를 그대로 쓴다."
            ),
            attempt_timeout_s=ATTEMPT_TIMEOUT_S,
            tool_timeout_s=TOOL_TIMEOUT_S,
            session_timeout_s=SESSION_TIMEOUT_S,
            token_budget=0,
            usd_budget=0.0,
            host_id=self.host_id,
            image_digest=digests,
            network_policy={
                "network": self.network,
                "internal": bool(self.manifest["workspace"].get("network_internal")),
                "declared_targets": self.manifest["workspace"].get("declared_targets", []),
                "note": "--internal 네트워크이므로 컨테이너에 외부 경로가 없다. 호스트 egress는 별개이며 네트워크 계층에서 강제되지 않는다 (HOST_EXCEPTIONS §10.2).",
            },
            challenge_id=self.manifest["challenge_id"],
            challenge_manifest_sha256=sha256_bytes(self.manifest_bytes),
            golden_note=note,
        )

    def attempt_finished(self, outcome: str, reason: str) -> None:
        self.em.emit(
            "attempt.finished",
            outcome=outcome,
            reason=reason,
            wall_clock_s=round(time.monotonic() - self.t0, 3),
        )

    def bind_input(self) -> None:
        """S1 — `/input`의 모든 파일을 해시와 바이트 수로 바인딩한다.

        첫 `model.requested`·첫 `tool.requested`보다 앞에 온다.
        """
        indir = self.fixture / "input"
        files = []
        if indir.is_dir():
            for p in sorted(indir.rglob("*")):
                if p.is_file():
                    files.append(
                        {
                            "path": "/input/" + str(p.relative_to(indir)).replace("\\", "/"),
                            "sha256": sha256_bytes(p.read_bytes()),
                            "bytes": p.stat().st_size,
                        }
                    )
        self.em.emit(
            "input.bound",
            challenge_id=self.manifest["challenge_id"],
            manifest_sha256=sha256_bytes(self.manifest_bytes),
            files=files,
            structural_patches_for_intake=0,
            intake_note="fixture 를 우리 형식 그대로 읽는다. 후보의 벤치마크 형식으로 변환하지 않았다 — 그 변환 비용은 arm 세션이 잰다.",
        )

    # -- workspace ---------------------------------------------------------- #

    def create_workspace(self) -> None:
        indir = self.fixture / "input"
        indir.mkdir(parents=True, exist_ok=True)
        mounts = [
            {"path": "/input", "mode": "ro", "source": str(indir)},
            {"path": "/work", "mode": "rw", "source": str(self.work_dir)},
            {"path": "/artifacts", "mode": "rw", "source": str(self.art_dir)},
        ]
        argv = [
            "docker", "run", "-d",
            "--name", self.container,
            "--label", "kisia-spike=1",
            "--network", self.network,
            "--read-only",
            "-v", f"{indir}:/input:ro",
            "-v", f"{self.work_dir}:/work",
            "-v", f"{self.art_dir}:/artifacts",
            "-w", "/work",
            self.worker_image,
            "sleep", "infinity",
        ]
        r = run(argv)
        if r.returncode != 0:
            raise RuntimeError(f"worker 기동 실패: {r.stderr.decode()}")
        self.container_id = r.stdout.decode().strip()
        self.em.emit(
            "workspace.created",
            container_id=self.container_id,
            image_digest=run(
                ["docker", "image", "inspect", "--format", "{{.Id}}", self.worker_image]
            ).stdout.decode().strip(),
            mounts=mounts,
            network=self.network,
            rootfs="read-only",
        )

    def destroy_workspace(self) -> None:
        """종료 시 잔존 0을 **후보 밖에서** 확인한다 (S2)."""
        inside = self.container_procs()
        run(["docker", "rm", "-f", self.container])
        left = run(
            ["docker", "ps", "-a", "-q", "--filter", f"name=^{self.container}$"]
        ).stdout.decode().split()
        self.em.emit(
            "workspace.destroyed",
            surviving_processes=0 if not left else len(inside),
            surviving_containers=len(left),
            checked_by="golden-driver@host(docker ps -a / docker top)",
            processes_before_destroy=inside,
            checked_note="컨테이너가 사라지면 그 pid namespace 의 프로세스도 사라진다. 관측은 호스트에서 했다 — 후보의 자기 보고가 아니다 (§0.1 규칙 3).",
        )

    def container_procs(self) -> list[dict]:
        r = run(["docker", "top", self.container, "-eo", "pid,ppid,stat,comm"])
        if r.returncode != 0:
            return []
        out = []
        for line in r.stdout.decode().splitlines()[1:]:
            f = line.split(None, 3)
            if len(f) == 4:
                out.append({"pid": int(f[0]), "ppid": int(f[1]), "stat": f[2], "comm": f[3]})
        return out

    def descendants(self, leader_pid: int | None) -> list[dict]:
        """leader 를 조상으로 갖는 프로세스. leader 자신은 제외한다."""
        if leader_pid is None:
            return []
        procs = self.container_procs()
        by_pid = {p["pid"]: p for p in procs}
        out = []
        for p in procs:
            if p["pid"] == leader_pid:
                continue
            cur, hops = p, 0
            while cur and hops < 64:
                if cur["ppid"] == leader_pid:
                    out.append(p)
                    break
                cur = by_pid.get(cur["ppid"])
                hops += 1
        return out

    # -- 도구 계층 ----------------------------------------------------------- #

    def exec(self, argv: list[str], source_ref: str) -> tuple[str, str, int]:
        """1회 실행. -> (obs_id, 출력 텍스트, exit code)"""
        full = ["docker", "exec", self.container, *argv]
        self.em.emit(
            "tool.requested",
            tool="exec",
            args_digest=sha256_text(json.dumps(argv)),
            args=argv,
        )
        t = time.monotonic()
        r = run(full)
        data = r.stdout + r.stderr
        obs = self.observe(source_ref, data)
        self.em.emit(
            "tool.completed",
            tool="exec",
            status=r.returncode,
            duration_ms=int((time.monotonic() - t) * 1000),
            artifact_ids=[],
            observation_id=obs,
        )
        return obs, data.decode("utf-8", "replace"), r.returncode

    def refused_write(self, path: str, reason_code: str) -> None:
        """A-3 — 쓰기가 거부되는지 보고, 호스트에서도 파일이 없음을 확인한다 (S2-a/b)."""
        obs, text, rc = self.exec(
            ["sh", "-c", f"echo probe > {path}"], source_ref=f"probe:write {path}"
        )
        if rc == 0:
            self.em.emit(
                "scope.refused",
                action=f"write:{path}",
                reason_code="NOT_REFUSED",
                observation_id=obs,
                host_check="쓰기가 성공했다. fixture 의 격리 선언과 실제가 어긋난다.",
            )
            return
        host_seen = None
        if path.startswith("/input/"):
            host_seen = (self.fixture / "input" / path[len("/input/"):]).exists()
        self.em.emit(
            "scope.refused",
            action=f"write:{path}",
            reason_code=reason_code,
            observation_id=obs,
            exit_status=rc,
            host_check_file_exists=host_seen,
            checked_by="golden-driver@host",
        )

    def open_session(self, argv: list[str], kind: str) -> Session:
        self._n_sess += 1
        sid = f"sess-{self._n_sess:02d}"
        self.em.emit("tool.requested", tool="session.open", args_digest=sha256_text(json.dumps(argv)), args=argv)
        s = Session(self, sid, argv, kind)
        self.live_sessions.add(sid)
        s.probe_leader_pid()
        self.em.emit(
            "session.opened",
            session_id=sid,
            kind=kind,
            banner_observation_id=None,
            banner_note="이 세션의 배너는 셸 프롬프트가 아니라 대상 서비스의 배너이고, 첫 session.io 관찰로 나온다.",
            leader_pid_in_container=s.leader_pid,
        )
        self.em.emit("tool.completed", tool="session.open", status=0, duration_ms=0, artifact_ids=[], session_id=sid)
        return s

    # -- HTTP --------------------------------------------------------------- #

    def jar_digest(self) -> str:
        canon = "".join(f"{k}={v}\n" for k, v in sorted(self.jar.items()))
        return sha256_text(canon)

    def http(
        self,
        method: str,
        path: str,
        body: str | None = None,
        use_jar: bool = True,
    ) -> tuple[str, dict]:
        tgt = self.manifest["target"]
        url = f"http://{tgt['host']}:{tgt['port']}{path}"
        headers: dict[str, str] = {}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if use_jar and self.jar:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in sorted(self.jar.items()))

        req = {"method": method, "url": url, "headers": headers, "body": body, "timeout": 20}
        before = self.jar_digest()

        self.em.emit(
            "tool.requested",
            tool="http",
            args_digest=sha256_text(json.dumps(req, sort_keys=True)),
            args={"method": method, "url": url, "headers": headers, "body": body},
        )
        t = time.monotonic()
        r = run(
            ["docker", "exec", "-i", self.container, "python3", "/opt/httpreq.py"],
            stdin=json.dumps(req).encode(),
        )
        resp = json.loads(r.stdout.decode())

        for k, v in resp["headers"]:
            if k.lower() == "set-cookie":
                nv = v.split(";", 1)[0]
                ck, _, cv = nv.partition("=")
                self.jar[ck.strip()] = cv.strip()
        after = self.jar_digest()

        rendered = f"HTTP {resp['status']} {resp['reason']}\n" + resp["body"]
        obs = self.observe(f"http:{method} {path}", rendered.encode())
        aid = None  # 절단되지 않으면 artifact 가 없다. observe 가 이미 판단했다.

        self.em.emit(
            "http.exchanged",
            target_id=tgt["id"],
            method=method,
            host=tgt["host"],
            path=path,
            status=resp["status"],
            jar_digest_before=before,
            jar_digest_after=after,
            artifact_id=aid,
            observation_id=obs,
        )
        self.em.emit(
            "tool.completed",
            tool="http",
            status=resp["status"],
            duration_ms=int((time.monotonic() - t) * 1000),
            artifact_ids=[],
            observation_id=obs,
        )
        return obs, resp

    def drop_jar(self, why: str) -> None:
        """C-4 (음성 프로브) — 턴 사이에 쿠키 항아리를 버린다."""
        before = self.jar_digest()
        self.jar.clear()
        self.em.emit(
            "scope.refused",
            action="jar.dropped",
            reason_code="NEGATIVE_PROBE_C4",
            jar_digest_before=before,
            jar_digest_after=self.jar_digest(),
            note=why,
        )

    # -- 턴 경계 ------------------------------------------------------------- #

    def turn(self, intent: str) -> None:
        obs = self._pending_obs
        self._pending_obs = []
        self.turn_no += 1
        self.em.emit(
            "model.requested",
            model_id="none",
            effort="none",
            input_tokens=0,
            cached_tokens=0,
            prompt_digest=sha256_text(f"golden-turn:{self.turn_no}:{intent}"),
            observation_ids=obs,
            golden_intent=intent,
        )
        self.em.emit(
            "model.completed",
            output_tokens=0,
            usd=0.0,
            latency_ms=0,
            finish_reason="golden_turn_boundary",
        )
        self.em.emit(
            "state.snapshot",
            turn=self.turn_no,
            live_session_ids=sorted(self.live_sessions),
            jar_digest=self.jar_digest(),
            artifact_count=self._n_art,
        )

    # -- 후보와 검증 ---------------------------------------------------------- #

    def candidate(self, value: str, derived_from: str, method: str) -> None:
        self.em.emit(
            "candidate.produced",
            value=value,
            derived_from=derived_from,
            method=method,
        )

    def verify(self, value: str) -> bool:
        """verifier 는 호스트에서 별도 프로세스로 돈다. solver 트리 밖이다 (S8)."""
        vpath = self.fixture.parent / "verifier" / "verify.py"
        r = run(
            [
                "python3",
                str(vpath),
                "--answer",
                str(self.fixture / "answer" / "answer.json"),
                "--candidate",
                value,
            ]
        )
        out = json.loads(r.stdout.decode())
        self.em.emit(
            "verification.completed",
            verdict=out["verdict"],
            verifier_id=out["verifier_id"],
            candidate_digest=out["candidate_digest"],
            verifier_process="host, worker 컨테이너 밖. solver 프로세스 트리와 공유하는 것이 없다.",
        )
        return bool(out["verdict"])
