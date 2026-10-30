"""본문을 파싱하는 docker 소켓 프록시.

    python3 docker_proxy.py --listen /run/kisia/docker-proxy.sock \
                            --upstream /var/run/docker.sock

**왜 본문을 파싱하는가.** canon(`SAFETY_SCOPE.md` "Time-limited exception: product
rebuild")이 거부하라고 적은 넷 중 셋은 `POST /containers/create` 의 **JSON 본문**에
있고 넷째는 대상의 **소유권**이다. 메서드+경로만 보는 endpoint ACL 방식으로는 넷 중
하나도 만족되지 않는다 — `HOST_EXCEPTIONS.md` §2.1.a-1.

**소유권은 상태가 아니라 라벨에서 나온다.** `create` 마다 `kisia-rebuild=1` 을 강제로
붙이고 이후 모든 지목 연산에서 대상의 라벨을 확인한다. 레지스트리를 두지 않으므로
프록시가 재시작해도 판정이 살아 있고, `rebuild-close` 가 쓰는 것과 같은 라벨이라
정리 대상과 접근 대상이 어긋나지 않는다 — §2.1.a-3.

**하이재킹은 선택이 아니다.** `docker exec -i` 가 `POST /exec/{id}/start` 에서 연결을
raw 스트림으로 바꾸고, vendored `get_interactive_session` 이 정확히 그 CLI 를 쓴다.
통과시키지 못하면 유형 B 세션 런타임이 아예 서지 않는다 — §2.1.a-4.

**이 파일이 "닫혔다"의 근거가 아니다.** 근거는 `ctf-host-user` 계정이 프록시 소켓을 통해
관측하는 §2.1.c 의 양방향 시험이고, 구현의 자기 보고는 증거가 아니다
(`CLAUDE.md` §6, `spec.md` §0.3-3).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import re
import socket
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

#: `rebuild-close` 가 정리 대상을 찾는 것과 **같은** 라벨이다. 갈리면 접근 대상과
#: 정리 대상이 어긋난다(§2.1.a-3).
LABEL_KEY = "kisia-rebuild"
LABEL_VALUE = "1"

#: 소켓 자격. `ctf-host-user` 는 `kisia-proxy` 에만 속하고 `docker` 에는 속하지 않는다.
SOCKET_GROUP = "kisia-proxy"
SOCKET_MODE = 0o660

_RECV = 65536
_LOG = logging.getLogger("kisia.proxy")

#: `/v1.51/containers/create` 처럼 CLI 가 붙이는 API 버전 접두.
_VERSION_RE = re.compile(r"^/v\d+(?:\.\d+)*(?=/)")
#: 컨테이너·네트워크 id 와 이름.
_ID = r"[A-Za-z0-9][A-Za-z0-9_.-]*"

_CONTAINER_VERB = re.compile(rf"^/containers/({_ID})/(start|stop|kill|wait)$")
_CONTAINER_DELETE = re.compile(rf"^/containers/({_ID})$")
_CONTAINER_READ = re.compile(rf"^/containers/({_ID})/(json|logs)$")
_CONTAINER_EXEC = re.compile(rf"^/containers/({_ID})/exec$")
_CONTAINER_ATTACH = re.compile(rf"^/containers/({_ID})/attach$")
_EXEC_START = re.compile(rf"^/exec/({_ID})/start$")
#: `docker exec` 가 raw 스트림이 끝난 뒤 **종료 코드를 읽는** 자리다. §2.1.a-3 의 표에
#: 없었고, 없으면 `docker exec` 가 명령을 실행하고도 rc=1 로 끝난다(실측 2026-08-08).
#: `spec.md` §4 의 close 가 `exit_status` 를 요구하므로 이것 없이는 그 연산이 서지 않는다.
_EXEC_INSPECT = re.compile(rf"^/exec/({_ID})/json$")
_NETWORK_DELETE = re.compile(rf"^/networks/({_ID})$")
_IMAGE_INSPECT = re.compile(r"^/images/(.+)/json$")
#: 재빌드-4가 더한 셋 — §2.1.a-3.c. 계약이 요구하는 세 마운트를 bind 없이 세우려면
#: 볼륨을 **채우고**(PUT) artifact 를 **읽어 내고**(GET) 루트fs 쓰기 거부를 **호스트에서
#: 확인**해야(changes) 한다. 셋 다 `json`·`logs` 와 **같은 소유권 검사**를 받는다.
_CONTAINER_ARCHIVE = re.compile(rf"^/containers/({_ID})/archive$")
_CONTAINER_CHANGES = re.compile(rf"^/containers/({_ID})/changes$")
#: 볼륨 하나를 지목하는 연산. 목록(`/volumes`)은 따로 처리한다 — 응답을 좁힌다.
_VOLUME_ONE = re.compile(rf"^/volumes/({_ID})$")


class ProxyError(Exception):
    """상류와 말하다 끊겼다."""


# --------------------------------------------------------------------------
# HTTP — 최소한의 프레이밍만 안다
# --------------------------------------------------------------------------


class Conn:
    """소켓 하나에 대한 버퍼 읽기.

    `http.client` 를 쓰지 않는 이유는 하이재킹 때문이다 — 응답 헤더 뒤에 남은 바이트를
    **그대로 돌려받아야** raw 스트림으로 이어붙일 수 있고, 표준 클라이언트는 그 경계를
    감춘다.
    """

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._buf = bytearray()

    def _fill(self) -> bool:
        chunk = self._sock.recv(_RECV)
        if not chunk:
            return False
        self._buf += chunk
        return True

    def read_head(self) -> bytes | None:
        """헤더 블록 전부(끝의 빈 줄 포함). 연결이 조용히 닫히면 `None`."""
        while b"\r\n\r\n" not in self._buf:
            if not self._fill():
                return None
        head, _, rest = bytes(self._buf).partition(b"\r\n\r\n")
        self._buf = bytearray(rest)
        return head + b"\r\n\r\n"

    def read_line(self) -> bytes:
        while b"\r\n" not in self._buf:
            if not self._fill():
                raise ProxyError("줄이 끝나기 전에 연결이 닫혔다")
        line, _, rest = bytes(self._buf).partition(b"\r\n")
        self._buf = bytearray(rest)
        return line

    def read_exactly(self, n: int) -> bytes:
        while len(self._buf) < n:
            if not self._fill():
                raise ProxyError("본문이 끝나기 전에 연결이 닫혔다")
        out = bytes(self._buf[:n])
        self._buf = bytearray(self._buf[n:])
        return out

    def read_to_eof(self) -> bytes:
        while self._fill():
            pass
        out = bytes(self._buf)
        self._buf = bytearray()
        return out

    def read_chunked(self) -> bytes:
        """청크 인코딩을 풀어서 돌려준다. 재조립은 호출자가 `content-length` 로 한다."""
        out = bytearray()
        while True:
            size_line = self.read_line().split(b";", 1)[0].strip()
            try:
                size = int(size_line, 16)
            except ValueError as exc:
                raise ProxyError(f"청크 길이를 읽을 수 없다: {size_line!r}") from exc
            if size == 0:
                while self.read_line():  # 트레일러
                    pass
                return bytes(out)
            out += self.read_exactly(size)
            self.read_line()  # 청크 뒤의 CRLF

    def pending(self) -> bytes:
        """아직 넘기지 않은 바이트. 하이재킹으로 넘어갈 때 이어붙인다."""
        out = bytes(self._buf)
        self._buf = bytearray()
        return out


Headers = list[tuple[str, str]]


def parse_head(block: bytes) -> tuple[str, Headers]:
    """시작 줄과 헤더 목록. **dict 로 접지 않는다** — 중복 헤더와 순서가 살아야 한다."""
    text = block.decode("latin-1")
    lines = text.split("\r\n")
    headers: Headers = []
    for line in lines[1:]:
        if not line:
            continue
        key, sep, value = line.partition(":")
        if sep:
            headers.append((key.strip(), value.strip()))
    return lines[0], headers


def get_header(headers: Headers, name: str) -> str:
    want = name.lower()
    for key, value in headers:
        if key.lower() == want:
            return value
    return ""


def read_body(conn: Conn, headers: Headers, *, allow_eof: bool) -> bytes:
    if "chunked" in get_header(headers, "transfer-encoding").lower():
        return conn.read_chunked()
    raw = get_header(headers, "content-length")
    if raw:
        try:
            return conn.read_exactly(int(raw))
        except ValueError as exc:
            raise ProxyError(f"content-length 를 읽을 수 없다: {raw!r}") from exc
    return conn.read_to_eof() if allow_eof else b""


def build(start: str, headers: Headers, body: bytes, *, with_length: bool = True) -> bytes:
    """길이를 다시 계산해 메시지를 조립한다.

    본문을 고쳤을 때 원래 `content-length` 를 그대로 두면 상류가 다음 요청의 앞부분을
    본문으로 읽는다. 청크 인코딩도 함께 지운다 — 여기서는 이미 풀린 바이트다.
    """
    out = [start]
    for key, value in headers:
        low = key.lower()
        if low in ("content-length", "transfer-encoding"):
            continue
        out.append(f"{key}: {value}")
    if with_length:
        out.append(f"Content-Length: {len(body)}")
    return ("\r\n".join(out) + "\r\n\r\n").encode("latin-1") + body


def status_code(start_line: str) -> int:
    parts = start_line.split(" ", 2)
    if len(parts) < 2:
        return 0
    try:
        return int(parts[1])
    except ValueError:
        return 0


def is_hijack(start_line: str, headers: Headers) -> bool:
    """상류가 연결을 raw 스트림으로 바꿨는가.

    docker 는 `Upgrade: tcp` 를 받으면 `101`, 아니면 `200` + docker 전용
    content-type 으로 답하고 그 뒤부터 HTTP 가 아니다.
    """
    if status_code(start_line) == 101:
        return True
    ctype = get_header(headers, "content-type").lower()
    return ctype.startswith("application/vnd.docker.")


# --------------------------------------------------------------------------
# 정책 — §2.1.a-3
# --------------------------------------------------------------------------


class DeniedError(Exception):
    """거부. 메시지가 그대로 클라이언트에 간다."""


def strip_version(path: str) -> str:
    return _VERSION_RE.sub("", path, count=1)


def split_query(path: str) -> tuple[str, str]:
    head, _, query = path.partition("?")
    return head, query


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def labels_of(obj: dict[str, Any]) -> dict[str, Any]:
    """컨테이너는 `Config.Labels`, 네트워크는 최상위 `Labels`."""
    top = _as_dict(obj.get("Labels"))
    if top:
        return top
    return _as_dict(_as_dict(obj.get("Config")).get("Labels"))


def is_ours(obj: dict[str, Any] | None) -> bool:
    if obj is None:
        return False
    return labels_of(obj).get(LABEL_KEY) == LABEL_VALUE


def check_host_config(body: dict[str, Any]) -> None:
    """`create` 본문에서 거부하는 여덟 (§2.1.a-3).

    canon 은 넷을 적었고 여기는 여덟이다. **늘린 것이지 줄인 것이 아니다** — 뒤의 넷은
    앞의 넷과 **같은 탈출을 다른 이름으로** 얻는 경로다. 확장의 비준 자리는 §4.2.
    """
    host = _as_dict(body.get("HostConfig"))

    if _as_list(host.get("Binds")):
        raise DeniedError("HostConfig.Binds — host bind mount 는 거부된다 (canon)")

    for mount in _as_list(host.get("Mounts")):
        if _as_dict(mount).get("Type") == "bind":
            raise DeniedError("HostConfig.Mounts[].Type=bind — host bind mount 는 거부된다 (canon)")

    if host.get("Privileged") is True:
        raise DeniedError("HostConfig.Privileged — 거부된다 (canon)")

    mode = str(host.get("NetworkMode") or "")
    if mode == "host" or mode.startswith("container:"):
        raise DeniedError(f"HostConfig.NetworkMode={mode!r} — 거부된다 (canon)")

    for field in ("PidMode", "IpcMode", "UTSMode"):
        if str(host.get(field) or "") == "host":
            raise DeniedError(f"HostConfig.{field}=host — 같은 탈출의 다른 철자다")

    for field in ("CapAdd", "Devices", "DeviceRequests"):
        if _as_list(host.get(field)):
            raise DeniedError(f"HostConfig.{field} — 같은 탈출의 다른 철자다")

    if str(host.get("UsernsMode") or "") == "host":
        raise DeniedError("HostConfig.UsernsMode=host — 같은 탈출의 다른 철자다")

    for opt in _as_list(host.get("SecurityOpt")):
        # **철자가 둘이다.** docker CLI 는 `seccomp=unconfined`(등호)와
        # `apparmor:unconfined`(콜론)를 **둘 다** 받아 그대로 API 에 싣는다(실측
        # 2026-08-08). §2.1.a-3 의 문면은 `*:unconfined` 로 콜론만 적었고, 콜론만
        # 자르면 등호 철자가 그대로 통과한다 — 재빌드-3이 §2.1.c 에서 실제로 통과시켰다.
        if re.split(r"[:=]", str(opt))[-1].strip() == "unconfined":
            raise DeniedError(f"HostConfig.SecurityOpt={opt!r} — 같은 탈출의 다른 철자다")


def stamp_label(body: dict[str, Any]) -> dict[str, Any]:
    labels = _as_dict(body.get("Labels"))
    labels[LABEL_KEY] = LABEL_VALUE
    body["Labels"] = labels
    return body


def rewrite_container_create(raw: bytes) -> bytes:
    body = _as_dict(json.loads(raw or b"{}"))
    check_host_config(body)
    return json.dumps(stamp_label(body)).encode("utf-8")


def rewrite_network_create(raw: bytes) -> bytes:
    """`Internal: true` 를 **강제**한다 — 선언되지 않은 목적지로 나가지 못하게."""
    body = _as_dict(json.loads(raw or b"{}"))
    body["Internal"] = True
    return json.dumps(stamp_label(body)).encode("utf-8")


def rewrite_volume_create(raw: bytes) -> bytes:
    """볼륨에도 라벨을 **강제로** 붙인다 — §2.1.a-3.c.

    자동 생성 볼륨(`--mount type=volume,source=…` 이 없는 이름을 가리킬 때 daemon 이
    만드는 것)은 **라벨이 없다.** 재빌드-4가 실측했다: 그렇게 만든 볼륨 둘이
    `docker volume ls --filter label=kisia-rebuild=1` 에 **0으로 보였고**, `ctf-host-user`
    계정은 그것을 보지도 지우지도 못했다. 잔존 검사가 통과하는데 잔존이 있는 상태다.
    """
    body = _as_dict(json.loads(raw or b"{}"))
    return json.dumps(stamp_label(body)).encode("utf-8")


def filter_networks(raw: bytes) -> bytes:
    """`GET /networks` 는 **우리 라벨만** 돌려준다.

    목록은 거부/허용으로 갈리지 않으므로 응답 쪽에서 좁힌다. 열어 두면 남의 네트워크
    이름이 샌다.
    """
    loaded = json.loads(raw or b"[]")
    if not isinstance(loaded, list):
        return raw
    kept = [n for n in loaded if is_ours(_as_dict(n))]
    return json.dumps(kept).encode("utf-8")


def filter_containers(raw: bytes) -> bytes:
    """`GET /containers/json`(목록)도 응답을 좁힌다 — D-15 와 같은 형태.

    **막아 두면 `docker ps` 가 실패하면서 빈 출력을 내고, `| wc -l` 이 0 을 낸다.**
    즉 잔존 검사가 "수행하지 못함"을 "0"으로 접는다 — 이 저장소가 절대 규칙으로 두는
    실패다(`TELEMETRY_SCHEMA.md` §7.1). 검사가 언제나 통과하면 그것은 검사가 아니다.
    """
    loaded = json.loads(raw or b"[]")
    if not isinstance(loaded, list):
        return raw
    return json.dumps([c for c in loaded if is_ours(_as_dict(c))]).encode("utf-8")


def filter_volumes(raw: bytes) -> bytes:
    """`GET /volumes` 도 같은 이유로 응답을 좁힌다 (D-15 와 같은 형태).

    봉투가 다르다 — 네트워크는 최상위가 배열이고 볼륨은 `{"Volumes": [...]}` 다.
    `Volumes` 가 `null` 로 오는 경우가 있어 빈 배열로 접는다.
    """
    loaded = json.loads(raw or b"{}")
    if not isinstance(loaded, dict):
        return raw
    loaded["Volumes"] = [v for v in _as_list(loaded.get("Volumes")) if is_ours(_as_dict(v))]
    return json.dumps(loaded).encode("utf-8")


#: 상류에 짧은 질의를 하나 던져 JSON 을 받아 오는 함수. 소유권 판정에만 쓴다.
Inspector = Callable[[str], "dict[str, Any] | None"]


class Decision:
    """전달해도 되는가, 본문을 어떻게 고치는가, 응답을 어떻게 좁히는가."""

    __slots__ = ("body", "response_filter")

    def __init__(
        self,
        body: bytes | None = None,
        response_filter: Callable[[bytes], bytes] | None = None,
    ) -> None:
        self.body = body
        self.response_filter = response_filter


def _require_container(inspect: Inspector, cid: str) -> None:
    if not is_ours(inspect(f"/containers/{cid}/json")):
        raise DeniedError(f"컨테이너 {cid} 는 우리 것이 아니다 ({LABEL_KEY}={LABEL_VALUE} 없음)")


def decide(method: str, path: str, body: bytes, inspect: Inspector) -> Decision:
    """§2.1.a-3 의 표 그대로. **허용 목록에 없으면 거부**가 기본값이다."""
    if method == "GET" and path in ("/_ping", "/version"):
        return Decision()
    if method == "HEAD" and path == "/_ping":
        return Decision()

    if method == "POST" and path == "/containers/create":
        return Decision(body=rewrite_container_create(body))

    if method == "POST" and path == "/networks/create":
        return Decision(body=rewrite_network_create(body))

    if method == "GET" and path == "/networks":
        return Decision(response_filter=filter_networks)

    # 목록 셋은 같은 자세다 — 거부하지 않고 **우리 라벨로 좁힌다**(D-15).
    if method == "GET" and path == "/containers/json":
        return Decision(response_filter=filter_containers)

    # 볼륨 셋 — §2.1.a-3.c. `/input` 을 bind 없이 세우는 유일한 경로이고, 라벨을
    # 붙이지 않으면 잔존 검사가 통과하는데 잔존이 남는다.
    if method == "POST" and path == "/volumes/create":
        return Decision(body=rewrite_volume_create(body))

    if method == "GET" and path == "/volumes":
        return Decision(response_filter=filter_volumes)

    match = _VOLUME_ONE.match(path)
    if match and method == "DELETE":
        if not is_ours(inspect(f"/volumes/{match.group(1)}")):
            raise DeniedError(f"볼륨 {match.group(1)} 는 우리 것이 아니다")
        return Decision()

    if method == "GET" and _IMAGE_INSPECT.match(path):
        return Decision()

    if method == "POST" and path in ("/build", "/images/create"):
        raise DeniedError(
            "이미지 빌드는 프록시를 지나지 않는다 (§2.1.b). "
            "운영자·ctf 가 빌드하고 제품은 digest 로 실행만 한다"
        )

    for pattern, verbs in (
        (_CONTAINER_VERB, ("POST",)),
        (_CONTAINER_EXEC, ("POST",)),
        (_CONTAINER_ATTACH, ("POST",)),
        (_CONTAINER_READ, ("GET",)),
        (_CONTAINER_DELETE, ("DELETE",)),
        # `docker cp` 는 안팎 둘 다 쓰고, CLI 가 PUT 앞에 HEAD 를 먼저 던진다(실측).
        (_CONTAINER_ARCHIVE, ("GET", "HEAD", "PUT")),
        (_CONTAINER_CHANGES, ("GET",)),
    ):
        match = pattern.match(path)
        if match and method in verbs:
            _require_container(inspect, match.group(1))
            return Decision()

    for pattern, verb in ((_EXEC_START, "POST"), (_EXEC_INSPECT, "GET")):
        match = pattern.match(path)
        if match and method == verb:
            # exec id 는 컨테이너 id 가 아니다. 한 번 더 물어 대상을 찾는다 — 이것이
            # 없으면 남의 컨테이너에 붙은 exec 를 id 만 알면 시작하거나 들여다볼 수 있다.
            info = inspect(f"/exec/{match.group(1)}/json")
            cid = str(_as_dict(info).get("ContainerID") or "") if info else ""
            if not cid:
                raise DeniedError(f"exec {match.group(1)} 의 대상을 확인할 수 없다")
            _require_container(inspect, cid)
            return Decision()

    match = _NETWORK_DELETE.match(path)
    if match and method == "DELETE":
        if not is_ours(inspect(f"/networks/{match.group(1)}")):
            raise DeniedError(f"네트워크 {match.group(1)} 는 우리 것이 아니다")
        return Decision()

    raise DeniedError(f"{method} {path} — 허용 목록에 없다 (§2.1.a-3 의 기본값은 거부다)")


# --------------------------------------------------------------------------
# 중계
# --------------------------------------------------------------------------


def deny_response(reason: str) -> bytes:
    payload = json.dumps({"message": f"kisia-proxy: {reason}"}).encode("utf-8")
    head = (
        "HTTP/1.1 403 Forbidden\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n"
        "\r\n"
    )
    return head.encode("latin-1") + payload


def splice(left: socket.socket, right: socket.socket) -> None:
    """양방향으로 붓는다. 하이재킹된 뒤에는 HTTP 가 아니므로 바이트만 옮긴다."""

    def pump(src: socket.socket, dst: socket.socket) -> None:
        # 한쪽이 닫히면 반대쪽도 닫는 것이 정상 종료다. 세션이 살아 있는 동안은
        # 어느 쪽도 EOF 를 내지 않으므로, 여기서 나온다는 것은 세션이 끝났다는 뜻이다.
        with contextlib.suppress(OSError):
            while True:
                chunk = src.recv(_RECV)
                if not chunk:
                    break
                dst.sendall(chunk)
        with contextlib.suppress(OSError):
            dst.shutdown(socket.SHUT_WR)

    threads = [
        threading.Thread(target=pump, args=(left, right), daemon=True),
        threading.Thread(target=pump, args=(right, left), daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


class Proxy:
    def __init__(self, upstream: Path) -> None:
        self.upstream = upstream

    def connect(self) -> socket.socket:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(self.upstream))
        return sock

    def inspect(self, path: str) -> dict[str, Any] | None:
        """소유권 판정 전용 질의. **중계 연결과 따로** 연다 — 섞으면 프레이밍이 깨진다."""
        try:
            sock = self.connect()
        except OSError as exc:
            _LOG.warning("상류에 닿지 못했다: %s", exc)
            return None
        try:
            request = f"GET {path} HTTP/1.1\r\nHost: docker\r\nConnection: close\r\n\r\n"
            sock.sendall(request.encode("latin-1"))
            conn = Conn(sock)
            head = conn.read_head()
            if head is None:
                return None
            start, headers = parse_head(head)
            if status_code(start) != 200:
                return None
            body = read_body(conn, headers, allow_eof=True)
            loaded = json.loads(body or b"{}")
            return dict(loaded) if isinstance(loaded, dict) else None
        except (OSError, ProxyError, ValueError) as exc:
            _LOG.warning("질의 %s 실패: %s", path, exc)
            return None
        finally:
            sock.close()

    def serve_client(self, client: socket.socket) -> None:
        try:
            upstream = self.connect()
        except OSError as exc:
            _LOG.error("상류 연결 실패: %s", exc)
            client.close()
            return
        try:
            self._pump_requests(client, upstream)
        except (OSError, ProxyError) as exc:
            _LOG.debug("연결 종료: %s", exc)
        finally:
            client.close()
            upstream.close()

    def _pump_requests(self, client: socket.socket, upstream: socket.socket) -> None:
        cconn = Conn(client)
        uconn = Conn(upstream)
        while True:
            head = cconn.read_head()
            if head is None:
                return
            start, headers = parse_head(head)
            parts = start.split(" ")
            if len(parts) < 3:
                return
            method, raw_path = parts[0], parts[1]
            body = read_body(cconn, headers, allow_eof=False)
            path, _ = split_query(strip_version(raw_path))

            try:
                decision = decide(method, path, body, self.inspect)
            except DeniedError as exc:
                _LOG.info("거부 %s %s — %s", method, path, exc)
                client.sendall(deny_response(str(exc)))
                continue
            except ValueError as exc:  # 본문이 JSON 이 아니다
                _LOG.info("거부 %s %s — 본문을 읽을 수 없다: %s", method, path, exc)
                client.sendall(deny_response(f"본문을 읽을 수 없다: {exc}"))
                continue

            out = decision.body if decision.body is not None else body
            upstream.sendall(build(start, headers, out))

            rhead = uconn.read_head()
            if rhead is None:
                return
            rstart, rheaders = parse_head(rhead)

            if is_hijack(rstart, rheaders):
                # 헤더 뒤에 이미 들어온 바이트가 있으면 그것부터 넘기고 raw 로 간다.
                client.sendall(rhead + uconn.pending())
                leftover = cconn.pending()
                if leftover:
                    upstream.sendall(leftover)
                splice(client, upstream)
                return

            if method == "HEAD":
                # **HEAD 응답에는 본문이 없다.** 그런데 `Content-Length` 는 GET 이
                # 돌려줄 길이를 그대로 싣는다 — 여기서 본문을 읽으려 들면 오지 않는
                # 바이트를 기다리며 연결이 멈춘다. 지금까지 살아 있던 것은 허용된
                # HEAD 가 `/_ping`(길이 0) 하나였기 때문이고, `HEAD /archive` 를 여는
                # 순간 그 자리에서 막힌다. 머리를 **그대로** 넘기는 것이 맞다.
                client.sendall(rhead)
                continue

            code = status_code(rstart)
            rbody = read_body(uconn, rheaders, allow_eof=False)
            if decision.response_filter is not None and code == 200:
                rbody = decision.response_filter(rbody)
            client.sendall(build(rstart, rheaders, rbody, with_length=code not in (204, 304)))


# --------------------------------------------------------------------------
# 소켓과 진입점
# --------------------------------------------------------------------------


def bind_listener(path: Path) -> socket.socket:
    """bind 직후 소유·모드를 **스스로** 잡는다.

    systemd 유닛에 맡기면 bind 와 chown 사이에 창이 열린다(§2.1.e-2).

    `grp` 를 여기서 import 하는 이유: 유닉스 전용 모듈이라 모듈 수준에 두면 Windows
    워크스테이션에서 **정책 자체를 시험할 수 없다.** 정책은 플랫폼 독립이고 소켓만
    리눅스다(`PATH_SCOPE.md` §4.3).
    """
    import grp

    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(path))
    try:
        gid = grp.getgrnam(SOCKET_GROUP).gr_gid
    except KeyError:
        sock.close()
        path.unlink(missing_ok=True)
        raise SystemExit(
            f"그룹 {SOCKET_GROUP} 이 없다. §2.1.e-1 이 먼저다 — groupadd {SOCKET_GROUP}"
        ) from None
    os.chown(path, 0, gid)
    path.chmod(SOCKET_MODE)
    sock.listen(64)
    return sock


def serve(listen: Path, upstream: Path) -> None:
    if not upstream.exists():
        raise SystemExit(f"상류 소켓이 없다: {upstream}")
    proxy = Proxy(upstream)
    server = bind_listener(listen)
    _LOG.info("listening on %s → %s", listen, upstream)
    try:
        while True:
            client, _ = server.accept()
            threading.Thread(
                target=proxy.serve_client, args=(client,), daemon=True
            ).start()
    except KeyboardInterrupt:
        _LOG.info("종료")
    finally:
        server.close()
        listen.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="docker_proxy", add_help=True)
    ap.add_argument("--listen", type=Path, required=True)
    ap.add_argument("--upstream", type=Path, default=Path("/var/run/docker.sock"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    serve(args.listen, args.upstream)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
