"""프록시 소켓을 통해 docker 를 부르는 얇은 감싸개.

**왜 HTTP API 를 직접 말하지 않고 CLI 를 부르는가.** vendored `get_interactive_session`
이 `docker exec -i` 를 `subprocess.Popen` 으로 띄운다(`SEAM_IMPLEMENTATION_MAP.md`
§3.4). 따라서 CLI 경로는 어차피 서야 하고, `HOST_EXCEPTIONS.md` §2.1.c 가 실측으로
확인한 것도 CLI 왕복이다. 두 경로를 함께 두면 프록시 허용 목록이 무엇을 지탱해야
하는지가 두 벌이 된다.

**`ctf-host-user` 는 raw 소켓에 닿지 못한다** — 2026-08-08T10:21Z 회수됨. `DOCKER_HOST` 가
프록시를 가리키지 않으면 여기서 바로 막히고, 그것이 정상이다.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

#: `HOST_EXCEPTIONS.md` §2.1.a-2 의 배치.
DEFAULT_HOST = "unix:///run/kisia/docker-proxy.sock"


class DockerError(RuntimeError):
    """docker 가 0 이 아닌 값으로 끝났고 호출자가 그것을 예상하지 않았다."""


@dataclass(frozen=True)
class Ran:
    argv: tuple[str, ...]
    rc: int
    out: bytes
    err: str

    @property
    def text(self) -> str:
        return self.out.decode("utf-8", "replace")


class DockerCli:
    """`docker` 호출 하나하나가 프록시의 판정을 한 번씩 받는다."""

    def __init__(self, *, host: str | None = None, timeout: float = 300.0) -> None:
        self.host = host or os.environ.get("DOCKER_HOST") or DEFAULT_HOST
        self.timeout = timeout
        self.log: list[Ran] = []

    def run(
        self,
        *args: str,
        stdin: bytes | None = None,
        check: bool = True,
        timeout: float | None = None,
    ) -> Ran:
        argv = ("docker", *args)
        env = dict(os.environ)
        env["DOCKER_HOST"] = self.host
        proc = subprocess.run(  # noqa: S603
            argv,
            input=stdin,
            capture_output=True,
            timeout=timeout or self.timeout,
            env=env,
            check=False,
        )
        ran = Ran(argv, proc.returncode, proc.stdout, proc.stderr.decode("utf-8", "replace"))
        self.log.append(ran)
        if check and ran.rc != 0:
            raise DockerError(f"{' '.join(argv)} → rc={ran.rc}\n{ran.err.strip()}")
        return ran
