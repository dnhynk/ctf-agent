"""프록시 정책 — `HOST_EXCEPTIONS.md` §2.1.a-3 의 표를 잠근다.

**이 테스트가 통과한다는 사실은 프록시가 닫혔다는 증거가 아니다**(`CLAUDE.md` §6.1-3).
"닫혔다"의 근거는 §2.1.c 의 양방향 시험 — `ctf-host-user` 계정이 **프록시 소켓을 통해**
허용 1 + 거부 5 + raw 소켓 차단을 관측하는 것 — 뿐이고, 여기서 재는 것은 그보다
훨씬 좁다: **정책 함수가 표대로 갈리는가.**

그래도 두는 이유는 거부 목록이 **제품의 영구 자세**가 되기 때문이다. 여덟 중 하나가
조용히 사라지면 §2.1.c 는 그 항목을 시험하지 않으므로(거부 5개만 본다) 발견되지
않는다. 그 자리를 이 파일이 메운다.

정책은 플랫폼 독립이라 워크스테이션에서도 돈다. 소켓만 리눅스다(`PATH_SCOPE.md` §4.3).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from kisia.proxy.docker_proxy import (
    LABEL_KEY,
    LABEL_VALUE,
    Conn,
    DeniedError,
    build,
    check_host_config,
    decide,
    filter_containers,
    filter_networks,
    filter_volumes,
    get_header,
    is_hijack,
    parse_head,
    rewrite_container_create,
    rewrite_network_create,
    rewrite_volume_create,
    split_query,
    status_code,
    strip_version,
)

OURS = {"Config": {"Labels": {LABEL_KEY: LABEL_VALUE}}}
THEIRS = {"Config": {"Labels": {"someone-else": "1"}}}


def _inspector(table: dict[str, dict[str, Any]]) -> Any:
    def inspect(path: str) -> dict[str, Any] | None:
        return table.get(path)

    return inspect


DENY_NOTHING = _inspector({})


# -- 거부 목록 여덟 ---------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("host_config", "why"),
    [
        ({"Binds": ["/:/host"]}, "canon — host bind mount"),
        ({"Mounts": [{"Type": "bind", "Source": "/", "Target": "/host"}]}, "canon — 같은 탈출"),
        ({"Privileged": True}, "canon — privileged"),
        ({"NetworkMode": "host"}, "canon — network=host"),
        ({"NetworkMode": "container:abc"}, "canon — 남의 네트워크 네임스페이스"),
        ({"PidMode": "host"}, "확장 — 호스트 프로세스 표"),
        ({"IpcMode": "host"}, "확장"),
        ({"UTSMode": "host"}, "확장"),
        ({"CapAdd": ["SYS_ADMIN"]}, "확장 — cap-add 로 마운트"),
        ({"Devices": [{"PathOnHost": "/dev/sda"}]}, "확장 — 호스트 장치"),
        ({"DeviceRequests": [{"Driver": "nvidia"}]}, "확장"),
        ({"UsernsMode": "host"}, "확장"),
        ({"SecurityOpt": ["seccomp:unconfined"]}, "확장 — seccomp 해제"),
        ({"SecurityOpt": ["apparmor:unconfined"]}, "확장 — apparmor 해제"),
        # 등호 철자. §2.1.c 에서 실제로 **통과했던** 자리다 — 회귀 잠금.
        ({"SecurityOpt": ["seccomp=unconfined"]}, "확장 — 등호 철자"),
        ({"SecurityOpt": ["apparmor=unconfined"]}, "확장 — 등호 철자"),
    ],
)
def test_create_body_denials(host_config: dict[str, Any], why: str) -> None:
    """canon 의 넷 + 같은 탈출의 다른 철자 넷. 전부 `create` **본문**에 있다."""
    with pytest.raises(DeniedError):
        check_host_config({"Image": "x", "HostConfig": host_config})


@pytest.mark.unit
def test_benign_create_passes() -> None:
    """거부 목록이 정상 생성까지 막으면 "전부 막힌 프록시"가 된다 — 양방향이어야 한다."""
    check_host_config(
        {
            "Image": "sha256:abc",
            "HostConfig": {
                "ReadonlyRootfs": True,
                "NetworkMode": "kisia-internal",
                "Binds": [],
                "Mounts": [{"Type": "volume", "Source": "work", "Target": "/work"}],
            },
        }
    )


@pytest.mark.unit
def test_create_stamps_our_label() -> None:
    out = json.loads(rewrite_container_create(json.dumps({"Image": "x"}).encode()))
    assert out["Labels"][LABEL_KEY] == LABEL_VALUE


@pytest.mark.unit
def test_create_label_survives_existing_labels() -> None:
    raw = json.dumps({"Image": "x", "Labels": {"mine": "keep"}}).encode()
    out = json.loads(rewrite_container_create(raw))
    assert out["Labels"] == {"mine": "keep", LABEL_KEY: LABEL_VALUE}


@pytest.mark.unit
def test_create_label_cannot_be_overridden_by_client() -> None:
    """클라이언트가 라벨을 다른 값으로 보내도 프록시 값이 이긴다 — 소유권의 뿌리다."""
    raw = json.dumps({"Image": "x", "Labels": {LABEL_KEY: "0"}}).encode()
    out = json.loads(rewrite_container_create(raw))
    assert out["Labels"][LABEL_KEY] == LABEL_VALUE


@pytest.mark.unit
def test_network_create_forces_internal() -> None:
    out = json.loads(rewrite_network_create(json.dumps({"Name": "n"}).encode()))
    assert out["Internal"] is True
    assert out["Labels"][LABEL_KEY] == LABEL_VALUE


@pytest.mark.unit
def test_network_create_overrides_internal_false() -> None:
    """`Internal: false` 로 요청해도 강제된다. 이것이 worker egress 강제의 한쪽이다."""
    out = json.loads(rewrite_network_create(json.dumps({"Name": "n", "Internal": False}).encode()))
    assert out["Internal"] is True


# -- 라우팅 ----------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/build"),
        ("POST", "/images/create"),
        ("POST", "/containers/prune"),
        ("GET", "/info"),
        ("GET", "/events"),
        ("POST", "/swarm/init"),
        ("POST", "/commit"),
        # 볼륨 셋을 열었어도 그 이웃은 그대로 막힌다 — 문 하나를 열면 복도가 열리는
        # 것이 아니다.
        ("POST", "/volumes/prune"),
        ("GET", "/volumes/kisia-a1-input"),
        ("PUT", "/volumes/kisia-a1-input"),
        # `docker cp` 를 열었어도 export 는 다른 연산이다.
        ("GET", "/containers/abc/export"),
        ("POST", "/containers/abc/archive"),
    ],
)
def test_default_is_deny(method: str, path: str) -> None:
    """허용 목록에 없으면 막힌다. **기본값이 거부**라는 성질을 잠근다."""
    with pytest.raises(DeniedError):
        decide(method, path, b"", DENY_NOTHING)


@pytest.mark.unit
@pytest.mark.parametrize("path", ["/_ping", "/version"])
def test_ping_and_version_allowed(path: str) -> None:
    """CLI 의 버전 협상이 이것을 요구한다. 막으면 아무것도 못 한다."""
    decide("GET", path, b"", DENY_NOTHING)


@pytest.mark.unit
def test_version_prefix_is_stripped() -> None:
    assert strip_version("/v1.51/containers/create") == "/containers/create"
    assert strip_version("/containers/create") == "/containers/create"


@pytest.mark.unit
def test_query_string_does_not_defeat_routing() -> None:
    path, query = split_query("/containers/create?name=worker")
    assert path == "/containers/create"
    assert query == "name=worker"


# -- 소유권 ----------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/containers/abc/start"),
        ("POST", "/containers/abc/stop"),
        ("POST", "/containers/abc/kill"),
        ("POST", "/containers/abc/wait"),
        ("POST", "/containers/abc/exec"),
        ("POST", "/containers/abc/attach"),
        ("GET", "/containers/abc/json"),
        ("GET", "/containers/abc/logs"),
        ("DELETE", "/containers/abc"),
    ],
)
def test_owned_container_allowed(method: str, path: str) -> None:
    decide(method, path, b"", _inspector({"/containers/abc/json": OURS}))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/containers/kisia-fix-b/start"),
        ("POST", "/containers/kisia-fix-b/exec"),
        ("DELETE", "/containers/kisia-fix-b"),
        ("GET", "/containers/kisia-fix-b/logs"),
    ],
)
def test_foreign_container_denied(method: str, path: str) -> None:
    """§2.1.c 거부 4 가 쓰는 그 컨테이너다 — 스파이크의 것이고 우리 것이 아니다."""
    with pytest.raises(DeniedError):
        decide(method, path, b"", _inspector({"/containers/kisia-fix-b/json": THEIRS}))


@pytest.mark.unit
def test_unknown_container_denied() -> None:
    """상류가 답하지 않으면 **거부**로 넘어간다. 모르면 여는 쪽으로 기울지 않는다."""
    with pytest.raises(DeniedError):
        decide("POST", "/containers/ghost/start", b"", DENY_NOTHING)


@pytest.mark.unit
def test_exec_start_resolves_container_then_checks_label() -> None:
    """exec id 는 컨테이너 id 가 아니다 — 한 번 더 물어야 소유권을 안다."""
    table = {"/exec/e1/json": {"ContainerID": "abc"}, "/containers/abc/json": OURS}
    decide("POST", "/exec/e1/start", b"", _inspector(table))


@pytest.mark.unit
def test_exec_start_on_foreign_container_denied() -> None:
    """id 만 알면 남의 컨테이너 exec 를 시작할 수 있는 구멍을 막는다."""
    table = {
        "/exec/e9/json": {"ContainerID": "kisia-fix-b"},
        "/containers/kisia-fix-b/json": THEIRS,
    }
    with pytest.raises(DeniedError):
        decide("POST", "/exec/e9/start", b"", _inspector(table))


@pytest.mark.unit
def test_exec_start_without_resolvable_target_denied() -> None:
    with pytest.raises(DeniedError):
        decide("POST", "/exec/e0/start", b"", DENY_NOTHING)


@pytest.mark.unit
def test_exec_inspect_allowed_for_our_container() -> None:
    """`docker exec` 는 raw 스트림이 끝난 뒤 여기서 종료 코드를 읽는다.

    §2.1.a-3 의 표에 없었고, 없으면 명령이 실행되고도 CLI 가 rc=1 로 끝난다(실측).
    `spec.md` §4 의 close 가 `exit_status` 를 요구하므로 그 연산이 서지 않는다.
    """
    table = {"/exec/e1/json": {"ContainerID": "abc", "ExitCode": 0}, "/containers/abc/json": OURS}
    decide("GET", "/exec/e1/json", b"", _inspector(table))


@pytest.mark.unit
def test_exec_inspect_on_foreign_container_denied() -> None:
    """읽기라고 열어 두지 않는다 — start 와 **같은** 소유권 검사를 받는다."""
    table = {
        "/exec/e9/json": {"ContainerID": "kisia-fix-b"},
        "/containers/kisia-fix-b/json": THEIRS,
    }
    with pytest.raises(DeniedError):
        decide("GET", "/exec/e9/json", b"", _inspector(table))


@pytest.mark.unit
def test_network_list_is_filtered_to_ours() -> None:
    raw = json.dumps(
        [
            {"Name": "ours", "Labels": {LABEL_KEY: LABEL_VALUE}},
            {"Name": "bridge", "Labels": {}},
            {"Name": "ctfnet", "Labels": {"spike": "1"}},
        ]
    ).encode()
    kept = json.loads(filter_networks(raw))
    assert [n["Name"] for n in kept] == ["ours"]


@pytest.mark.unit
def test_foreign_network_delete_denied() -> None:
    with pytest.raises(DeniedError):
        decide("DELETE", "/networks/ctfnet", b"", _inspector({"/networks/ctfnet": {"Labels": {}}}))


# -- 재빌드-4가 더한 일곱 — §2.1.a-3.c ---------------------------------------
#
# 계약이 요구하는 세 마운트(`PATH_SCOPE.md` §2.1)를 bind 없이 세우는 데 필요한 것들이다.
# 넓히는 변경이므로 **거부 쪽도 함께** 잠근다 — 여는 항목만 세면 §2.4(a) 와 같은 형태의
# 결함(문면과 구현이 같은 구멍을 공유)이 다시 난다.


@pytest.mark.unit
def test_container_list_is_filtered_to_ours() -> None:
    """막아 두면 `docker ps` 가 실패하며 빈 출력을 내고 `wc -l` 이 **0** 을 낸다 —
    잔존 검사가 "수행하지 못함"을 "0"으로 접는다. 그래서 막지 않고 좁힌다(D-15·D-25)."""
    raw = json.dumps(
        [
            {"Names": ["/kisia-r4a-ok-01"], "Labels": {LABEL_KEY: LABEL_VALUE}},
            {"Names": ["/kisia-fix-b"], "Labels": {"spike": "1"}},
            {"Names": ["/other"], "Labels": {}},
        ]
    ).encode()
    kept = json.loads(filter_containers(raw))
    assert [c["Names"][0] for c in kept] == ["/kisia-r4a-ok-01"]


@pytest.mark.unit
def test_container_list_allowed_without_ownership_lookup() -> None:
    """목록은 대상이 없으므로 소유권 질의를 하지 않는다 — 응답 쪽에서 좁힌다."""
    decide("GET", "/containers/json", b"", DENY_NOTHING)


@pytest.mark.unit
def test_volume_create_stamps_our_label() -> None:
    """자동 생성 볼륨은 **라벨이 없다** — 실측(재빌드-4). 그래서 create 를 지나게 한다."""
    out = json.loads(rewrite_volume_create(json.dumps({"Name": "kisia-a1-input"}).encode()))
    assert out["Labels"][LABEL_KEY] == LABEL_VALUE


@pytest.mark.unit
def test_volume_create_label_cannot_be_overridden_by_client() -> None:
    raw = json.dumps({"Name": "v", "Labels": {LABEL_KEY: "0", "mine": "keep"}}).encode()
    out = json.loads(rewrite_volume_create(raw))
    assert out["Labels"] == {"mine": "keep", LABEL_KEY: LABEL_VALUE}


@pytest.mark.unit
def test_volume_list_is_filtered_to_ours() -> None:
    """봉투가 네트워크와 다르다 — 최상위가 배열이 아니라 `{"Volumes": [...]}` 다."""
    raw = json.dumps(
        {
            "Volumes": [
                {"Name": "kisia-a1-input", "Labels": {LABEL_KEY: LABEL_VALUE}},
                {"Name": "spike-vol", "Labels": {"spike": "1"}},
                {"Name": "bare", "Labels": None},
            ],
            "Warnings": [],
        }
    ).encode()
    kept = json.loads(filter_volumes(raw))
    assert [v["Name"] for v in kept["Volumes"]] == ["kisia-a1-input"]
    assert kept["Warnings"] == []


@pytest.mark.unit
def test_volume_list_handles_null_volumes() -> None:
    """`Volumes: null` 로 오는 경우가 있다. 빈 배열로 접는다."""
    assert json.loads(filter_volumes(json.dumps({"Volumes": None}).encode()))["Volumes"] == []


@pytest.mark.unit
def test_our_volume_delete_allowed() -> None:
    table = {"/volumes/kisia-a1-input": {"Labels": {LABEL_KEY: LABEL_VALUE}}}
    decide("DELETE", "/volumes/kisia-a1-input", b"", _inspector(table))


@pytest.mark.unit
def test_foreign_volume_delete_denied() -> None:
    """`ctf`·스파이크의 볼륨을 지우지 못한다. 라벨 없는 것도 우리 것이 아니다."""
    with pytest.raises(DeniedError):
        decide("DELETE", "/volumes/spike-vol", b"", _inspector({"/volumes/spike-vol": {}}))


@pytest.mark.unit
def test_unknown_volume_delete_denied() -> None:
    with pytest.raises(DeniedError):
        decide("DELETE", "/volumes/ghost", b"", DENY_NOTHING)


@pytest.mark.unit
@pytest.mark.parametrize("method", ["GET", "HEAD", "PUT"])
def test_archive_allowed_on_our_container(method: str) -> None:
    """`docker cp` 는 안팎 둘 다 쓰고, CLI 가 PUT 앞에 HEAD 를 먼저 던진다(실측)."""
    decide(method, "/containers/abc/archive", b"", _inspector({"/containers/abc/json": OURS}))


@pytest.mark.unit
@pytest.mark.parametrize("method", ["GET", "HEAD", "PUT"])
def test_archive_denied_on_foreign_container(method: str) -> None:
    """**쓰기가 열린다는 것이 이 항목의 값이자 비용이다** — 소유권 검사가 유일한 방벽이다."""
    table = {"/containers/kisia-fix-b/json": THEIRS}
    with pytest.raises(DeniedError):
        decide(method, "/containers/kisia-fix-b/archive", b"", _inspector(table))


@pytest.mark.unit
def test_changes_allowed_on_our_container() -> None:
    """S2.2 의 "호스트에서 확인" 이 서는 유일한 도구다 — `docker diff`."""
    decide("GET", "/containers/abc/changes", b"", _inspector({"/containers/abc/json": OURS}))


@pytest.mark.unit
def test_changes_denied_on_foreign_container() -> None:
    """남의 컨테이너 파일시스템 변경을 읽는 것은 정보 유출이다."""
    table = {"/containers/kisia-fix-b/json": THEIRS}
    with pytest.raises(DeniedError):
        decide("GET", "/containers/kisia-fix-b/changes", b"", _inspector(table))


@pytest.mark.unit
def test_archive_and_changes_denied_when_target_unknown() -> None:
    """상류가 답하지 않으면 거부로 기운다 — 기존 항목과 같은 자세."""
    for method, path in (
        ("PUT", "/containers/ghost/archive"),
        ("GET", "/containers/ghost/changes"),
    ):
        with pytest.raises(DeniedError):
            decide(method, path, b"", DENY_NOTHING)


# -- HTTP 프레이밍 ----------------------------------------------------------


@pytest.mark.unit
def test_build_recomputes_content_length() -> None:
    """본문을 고쳤는데 길이를 그대로 두면 상류가 다음 요청의 앞부분을 본문으로 읽는다."""
    head, headers = parse_head(
        b"POST /containers/create HTTP/1.1\r\nHost: docker\r\nContent-Length: 2\r\n\r\n"
    )
    out = build(head, headers, b'{"Image":"x"}')
    assert b"Content-Length: 13\r\n" in out
    assert out.count(b"Content-Length") == 1
    assert out.endswith(b'{"Image":"x"}')


@pytest.mark.unit
def test_build_drops_transfer_encoding() -> None:
    head, headers = parse_head(
        b"POST /containers/create HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n"
    )
    out = build(head, headers, b"{}")
    assert b"Transfer-Encoding" not in out
    assert b"Content-Length: 2" in out


@pytest.mark.unit
def test_duplicate_headers_survive() -> None:
    """dict 로 접으면 중복이 사라진다. 순서와 중복이 살아야 한다."""
    _, headers = parse_head(b"GET /_ping HTTP/1.1\r\nX-A: 1\r\nX-A: 2\r\n\r\n")
    assert headers == [("X-A", "1"), ("X-A", "2")]


@pytest.mark.unit
def test_header_lookup_is_case_insensitive() -> None:
    _, headers = parse_head(b"GET /_ping HTTP/1.1\r\nCoNtEnT-TyPe: application/json\r\n\r\n")
    assert get_header(headers, "content-type") == "application/json"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("start", "ctype", "expected"),
    [
        ("HTTP/1.1 101 UPGRADED", "", True),
        ("HTTP/1.1 200 OK", "application/vnd.docker.raw-stream", True),
        ("HTTP/1.1 200 OK", "application/vnd.docker.multiplexed-stream", True),
        ("HTTP/1.1 200 OK", "application/json", False),
        ("HTTP/1.1 404 Not Found", "application/json", False),
    ],
)
def test_hijack_detection(start: str, ctype: str, expected: bool) -> None:
    """놓치면 유형 B 세션이 아예 서지 않는다 — §2.1.a-4."""
    headers = [("Content-Type", ctype)] if ctype else []
    assert is_hijack(start, headers) is expected


@pytest.mark.unit
def test_status_code_parsing() -> None:
    assert status_code("HTTP/1.1 204 No Content") == 204
    assert status_code("garbage") == 0


class _FakeSock:
    """`recv` 만 흉내 낸다. 프레이밍이 소켓 경계에 의존하지 않는지 보려고 조각내 준다."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    def recv(self, _n: int) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""


@pytest.mark.unit
def test_head_reassembles_across_recv_boundaries() -> None:
    sock = _FakeSock([b"GET /_pi", b"ng HTTP/1.1\r\nHo", b"st: d\r\n\r\nLEFT"])
    conn = Conn(sock)  # type: ignore[arg-type]
    head = conn.read_head()
    assert head == b"GET /_ping HTTP/1.1\r\nHost: d\r\n\r\n"
    assert conn.pending() == b"LEFT"


@pytest.mark.unit
def test_chunked_body_is_unwrapped() -> None:
    sock = _FakeSock([b"5\r\nhello\r\n3\r\n wo\r\n0\r\n\r\n"])
    conn = Conn(sock)  # type: ignore[arg-type]
    assert conn.read_chunked() == b"hello wo"
