"""S2 — workspace 격리. `PATH_SCOPE.md` §2 를 그대로 세운다.

**정책 계층을 만들지 않는다.** `--read-only` + 볼륨 `readonly` + `--internal` 네트워크면
P-S2-a/b/c 의 참·거짓이 격리 모델에서 갈린다(§2.1). 여기 있는 코드는 그 배치를 세우고
**밖에서** 관측할 뿐, 무엇을 거부할지 판단하지 않는다.

**세 마운트가 전부 볼륨인 이유 — 재빌드-4의 실측.**

- host bind mount 는 프록시가 거부한다(canon). 스파이크의 `-v <fixture>/input:/input:ro`
  형태는 재빌드에서 서지 않는다.
- tmpfs 는 쓰기는 되지만 **`docker cp` 의 경로 해소가 보지 못한다**(daemon 404 실측).
  `/artifacts` 를 tmpfs 로 두면 artifact 바이트를 런타임이 읽을 수 없어
  `artifact.produced.sha256` 이 **컨테이너 자기 보고**가 된다 —
  `TELEMETRY_SCHEMA.md` §7.1 이 이름으로 경고한 자리다. S8.3 의 `container:/work`
  스윕도 같은 이유로 막힌다.
- 볼륨은 둘 다 된다. 그리고 `POST /volumes/create` 를 지나게 하면 프록시가 라벨을
  붙여 잔존 검사에 잡힌다 — **자동 생성 볼륨은 라벨이 없어 보이지 않는다**(실측).

**자기 보고를 쓰지 않는다.** `surviving_processes` 는 컨테이너가 세는 값이 아니라
호스트의 `/proc` 를 읽어 얻는다. 둘을 같은 출처에서 만들면 스트림이 자기 일관적이 되어
검사기가 통과시킨다(`TELEMETRY_SCHEMA.md` §7.1).
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kisia.runtime.docker_cli import DockerCli, DockerError

#: 컨테이너 안의 세 경로와 그 모드 — `PATH_SCOPE.md` §2.1. 이 표가 곧
#: `workspace.created.mounts[]` 다.
MOUNT_SPEC: tuple[tuple[str, str, str], ...] = (
    ("input", "/input", "ro"),
    ("work", "/work", "rw"),
    ("artifacts", "/artifacts", "rw"),
)


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    out: bytes
    err: str

    @property
    def text(self) -> str:
        return self.out.decode("utf-8", "replace")


@dataclass
class DestroyReport:
    """`workspace.destroyed` 의 재료. **밖에서 읽은 값과 안에서 받은 값을 나눈다.**"""

    surviving_processes: int
    surviving_containers: int
    checked_by: str
    #: 컨테이너가 스스로 보고한 값. 판정에 쓰지 않고 나란히 싣는다(§0.3-3).
    surviving_processes_self_reported: int | None = None
    #: 정리 전에 호스트에서 본 프로세스들. 근거로 남긴다.
    host_pids_before: list[int] = field(default_factory=list)


class Workspace:
    """한 attempt 의 컨테이너·네트워크·볼륨 셋을 소유한다."""

    def __init__(
        self,
        cli: DockerCli,
        attempt: str,
        *,
        image: str,
        readonly_rootfs: bool = True,
        input_readonly: bool = True,
    ) -> None:
        """`readonly_rootfs`·`input_readonly` 의 기본값이 계약의 자세다.

        **끄는 자리는 음성 대조 하나뿐이다.** 술어에 이빨이 있는지 재려면 격리를 한
        군데씩 풀어 보고 해당 술어가 갈리는지 봐야 한다 — `CHECKER.md` §6 이 P-S2-c 를
        arm 없이 **양방향으로** 확인한 것과 같은 형태다. 판정에 넣는 스트림은 언제나
        기본값으로 돈다. 이 두 인자가 참이 아닌 스트림은 진단이지 증거가 아니다.
        """
        self.cli = cli
        self.attempt = attempt
        self.image = image
        self.readonly_rootfs = readonly_rootfs
        self.input_readonly = input_readonly
        self.container = f"kisia-{attempt}"
        self.network = f"kisia-{attempt}-net"
        self.volumes = {name: f"kisia-{attempt}-{name}" for name, _, _ in MOUNT_SPEC}
        self.container_id = ""
        self.init_pid = 0

    # -- 세우기 --------------------------------------------------------------
    def create(self, *, command: list[str]) -> dict[str, Any]:
        """`workspace.created` 가 실을 사실을 만들고 돌려준다."""
        for vol in self.volumes.values():
            # **명시적으로 만든다.** `--mount source=<없는 이름>` 은 daemon 이 라벨
            # 없이 자동 생성하고, 그러면 잔존 검사에 보이지 않는다(실측).
            self.cli.run("volume", "create", vol)
        self.cli.run("network", "create", "--internal", self.network)

        args = [
            "create",
            "--name", self.container,
            "--network", self.network,
            "--label", f"kisia-attempt={self.attempt}",
            # 아래 다섯은 프로토타입 `src/kisia_agent/runtime/spec.py` 와 대조한 뒤
            # 채택했다 — 근거와 채택하지 않은 것은 `docs/rebuild/reuse/S2.md`.
            # `--init` 이 가장 중요하다: pty 세션이 백그라운드 잡을 고아로 남기고
            # `sleep` 은 그것을 거두지 않아 pid 슬롯을 문 채로 컨테이너 수명 내내
            # `/proc` 에 남는다. `spec.md` §4.1-2 가 세는 바로 그 프로세스다.
            "--init",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "256",
            "--memory", "1g", "--memory-swap", "1g",
        ]
        if self.readonly_rootfs:
            args.append("--read-only")
        for name, target, mode in MOUNT_SPEC:
            spec = f"type=volume,source={self.volumes[name]},target={target}"
            if mode == "ro" and self.input_readonly:
                spec += ",readonly"
            args += ["--mount", spec]
        args += [self.image, *command]
        self.container_id = self.cli.run(*args).text.strip()
        self.cli.run("start", self.container)
        self.init_pid = int(self.inspect().get("State", {}).get("Pid") or 0)

        return {
            "container_id": self.container_id,
            "image_digest": self.image,
            # **실제로 건 모드를 적는다.** 음성 대조에서 `/input` 을 rw 로 걸고도
            # `ro` 라고 적으면 스트림이 거짓말을 하고, 그러면 대조가 재는 것이
            # 격리가 아니라 우리 문자열이 된다.
            "mounts": [{"path": t, "mode": self._mode_for(t)} for _, t, _ in MOUNT_SPEC],
            "readonly_rootfs": self.readonly_rootfs,
            "network": self.network,
        }

    def inspect(self) -> dict[str, Any]:
        raw = self.cli.run("inspect", self.container).text
        loaded = json.loads(raw)
        return dict(loaded[0]) if isinstance(loaded, list) and loaded else {}

    # -- 컨테이너 안 --------------------------------------------------------
    def exec_(self, argv: list[str], *, timeout: float | None = None) -> ExecResult:
        ran = self.cli.run("exec", self.container, *argv, check=False, timeout=timeout)
        return ExecResult(ran.rc, ran.out, ran.err)

    def sh(self, script: str, *, timeout: float | None = None) -> ExecResult:
        return self.exec_(["sh", "-c", script], timeout=timeout)

    # -- 안팎으로 바이트 옮기기 ----------------------------------------------
    def put(self, target_dir: str, name: str, data: bytes) -> None:
        """`docker cp` 안으로. `/input` 은 worker 에게 `ro` 이므로 **로더**를 쓴다.

        로더는 같은 볼륨을 쓰기 가능으로 붙인 짧은 수명의 컨테이너다. worker 쪽
        마운트 모드를 바꾸지 않고 볼륨을 채우는 유일한 경로이고, 채운 뒤 지운다.
        """
        vol = self._volume_for(target_dir)
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / name
            src.write_bytes(data)
            if vol is None or self._mode_for(target_dir) == "rw":
                self.cli.run("cp", str(src), f"{self.container}:{target_dir}/{name}")
                return
            loader = f"kisia-{self.attempt}-loader"
            self.cli.run(
                "create", "--name", loader,
                "--mount", f"type=volume,source={vol},target={target_dir}",
                self.image, "true",
            )
            try:
                self.cli.run("cp", str(src), f"{loader}:{target_dir}/{name}")
            finally:
                self.cli.run("rm", "-f", loader, check=False)

    def get(self, path: str) -> bytes | None:
        """`docker cp` 밖으로. 없으면 `None`.

        **이것이 호스트 확인의 도구다.** 돌려주는 것은 daemon 이 읽은 바이트이지
        worker 가 말한 것이 아니다. 부재도 마찬가지로 daemon 의 판정이다.
        """
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "out.bin"
            ran = self.cli.run("cp", f"{self.container}:{path}", str(dst), check=False)
            if ran.rc != 0:
                return None
            return dst.read_bytes() if dst.is_file() else None

    def get_tree(self, path: str, dest: Path) -> bool:
        """디렉터리를 통째로 밖으로. S8.3 의 `container:/…` 표면을 실체화한다."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        return self.cli.run("cp", f"{self.container}:{path}", str(dest), check=False).rc == 0

    def changes(self) -> list[str]:
        """`docker diff` — 루트fs 층의 변경. 마운트 지점은 항상 `A` 로 나온다."""
        return [ln for ln in self.cli.run("diff", self.container).text.splitlines() if ln]

    def rootfs_created(self, path: str) -> bool:
        """루트fs 에 `path` 가 생겼는가 — **호스트에서** 본 값. S2.2 의 나머지 절반.

        두 관측을 함께 쓴다. `docker diff` 는 루트fs 층의 변경 목록이고,
        `docker cp` 는 그 경로를 실제로 읽어 본 결과다. 하나만 쓰면 마운트 지점과
        진짜 생성을 가르지 못하거나(전자) 이미지에 원래 있던 파일과 새로 생긴
        파일을 가르지 못한다(후자).
        """
        marked = any(ln[2:] == path for ln in self.changes() if ln[:1] in ("A", "C"))
        return marked or self.get(path) is not None

    def volume_path_exists(self, path: str) -> bool:
        """볼륨 위의 경로가 있는가 — 같은 이유로 `docker cp` 로 본다."""
        return self.get(path) is not None

    # -- 허물기 --------------------------------------------------------------
    def destroy(self, *, self_reported: int | None = None) -> DestroyReport:
        before = _descendants(self.init_pid) if self.init_pid else set()
        self.cli.run("stop", "-t", "5", self.container, check=False)
        self.cli.run("rm", "-f", self.container, check=False)
        self.cli.run("network", "rm", self.network, check=False)
        for vol in self.volumes.values():
            self.cli.run("volume", "rm", vol, check=False)

        alive = sorted(p for p in before if Path(f"/proc/{p}").exists())
        if self.init_pid and Path(f"/proc/{self.init_pid}").exists():
            alive.append(self.init_pid)
        try:
            self.inspect()
            containers = 1
        except (DockerError, json.JSONDecodeError):
            containers = 0

        return DestroyReport(
            surviving_processes=len(alive),
            surviving_containers=containers,
            checked_by="kisia-hostprobe@host(/proc + docker inspect)",
            surviving_processes_self_reported=self_reported,
            host_pids_before=sorted(before),
        )

    # -- 내부 ----------------------------------------------------------------
    def _volume_for(self, target_dir: str) -> str | None:
        for name, target, _ in MOUNT_SPEC:
            if target == target_dir:
                return self.volumes[name]
        return None

    def _mode_for(self, target_dir: str) -> str:
        for _, target, mode in MOUNT_SPEC:
            if target == target_dir:
                return mode if (mode == "rw" or self.input_readonly) else "rw"
        return "rw"


def _descendants(pid: int) -> set[int]:
    """호스트의 `/proc` 에서 `pid` 의 자손을 모은다.

    컨테이너 안에서 세지 않는다 — 그것은 자기 보고다. 커널 세션(sid) 경계까지는
    가지 않는데, 그 요구(`spec.md` §4.1-2)는 세션 런타임의 것이고 이 세션의
    범위(§3.1)가 아니다. **여기서 세는 것은 컨테이너 init 의 자손뿐이고 그 사실을
    적어 둔다** — 접으면 거짓 관측이 된다.
    """
    children: dict[int, list[int]] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # comm 에 공백·괄호가 들어갈 수 있어 마지막 ')' 뒤부터 자른다.
        tail = stat.rpartition(")")[2].split()
        if len(tail) < 2:
            continue
        children.setdefault(int(tail[1]), []).append(int(entry.name))

    out: set[int] = set()
    stack = list(children.get(pid, ()))
    while stack:
        cur = stack.pop()
        if cur in out:
            continue
        out.add(cur)
        stack.extend(children.get(cur, ()))
    return out


def docker_available() -> bool:
    return shutil.which("docker") is not None
