"""대회 챌린지 디렉터리 → `kisia.fixture/1` 매니페스트. **attempt 앞에 있어야 한다.**

`O-49` 가 그 이유다 — `flag_format` 은 기본값 없는 필수 통제 필드이고, 매니페스트가
없으면 attempt 가 **시작조차 못 한다.** 그래서 이 모듈은 판정 계층이 아니라 진입점의
첫 단계다.

---

**실측 (2026-08-09, 코드를 읽어 확인했다. 기억으로 답하지 않았다 — `CLAUDE.md` §7).**

`run_attempt(fixture=...)` 가 받는 것은 `kisia.runtime.golden_a.Fixture` 이고
`kisia.checker.fixture.Fixture` 와 **다른 물건**이다. 전자는 `root: Path` 하나를 쥔
dataclass 이고 세 자리를 이름으로 안다:

| 속성 | 경로 | 누가 읽는가 |
|---|---|---|
| `manifest_path` | `<root>/manifest.json` | `description`·`flag_format`·`display_limit_bytes` |
| `bundle` | `<root>/input/bundle.tar.gz` | 통째로 `/input` 에 들어간다 |
| `answer_path` | `<root>/answer/answer.json` | `_verify`·`_sweep`. 무정답 모드에서는 안 돈다 |

그러므로 **이 모듈이 만드는 것은 golden_a 쪽 형태**이고, 챌린지 디렉터리의 파일들은
`bundle.tar.gz` **하나로 묶인다.** 묶는 것은 취향이 아니라 실측의 결과다 —
`agent_a.run_attempt` 는 `/input` 에 그 파일 하나만 넣고, 모델에게 주는 문장도
*"The challenge input is mounted at /input/bundle.tar.gz"* 로 고정돼 있다. 파일을 흩어
두면 그 문장이 거짓이 된다.

**`inputs[]` 는 실제로 `/input` 에 들어가는 것만 적는다** — 즉 bundle 하나다.
`MANIFEST.md` §2.4 가 *"손으로 쓰지 않는다. 실제 디렉터리를 읽어 채운다"* 로 못박은
필드이고, 마운트되지 않는 파일을 여기 적으면 `input.bound` 와 어긋나 S1 이 잡는 것이
**챌린지의 사실이 아니라 우리의 거짓말**이 된다. 원본 파일별 경로·sha256·바이트는
`contest_source_files[]` 가 나른다 — 매니페스트에 없는 이름이지만 세 fixture 가 이미
`nyuctf` 블록으로 같은 일을 하고 있고(§2.7), 그쪽처럼 **재빌드의 판정 경로는 이것을
읽지 않는다.**

**`R5-10` 두 줄에 기댄다** (`MVP_SCOPE.md` §4 의 A·B):

- `provenance: contest-derived` 를 `challenge_set: contest` 에서 허용한다.
- `challenge_set` 열거에 `contest` 를 더한다.
- `solution_path` 는 면제된다 — 풀어야 나오는 것을 풀기 전에 요구할 수 없다.

**문제를 지어내지 않는다.** `description` 은 운영자가 준 파일, 없으면 챌린지 디렉터리의
README, 그것도 없으면 **관측한 사실 한 문단**(어떤 파일이 몇 바이트로 들어 있는가)이다.
셋째 갈래가 챌린지를 설명하지 않는다는 사실은 그 문장이 스스로 적는다.
"""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

SCHEMA = "kisia.fixture/1"

#: `R5-10` 이 더한 값 둘. `MANIFEST.md` §2.1 · `TELEMETRY_SCHEMA.md` §2.
CHALLENGE_SET = "contest"
PROVENANCE = "contest-derived"

#: `/input` 에 놓이는 유일한 파일. `golden_a.Fixture.bundle` 이 이 이름을 안다.
BUNDLE_NAME = "bundle.tar.gz"

#: `MANIFEST.md` §2.6 — 값은 자유이되 **결정론은 필수**다. 세 fixture 와 같은 값을 쓴다.
DISPLAY_LIMIT_BYTES = 4096

#: `spec.md` §5 하중표의 두 행. **여기서 새로 정하지 않았다** — 봉인된 fixture 의
#: `seams_loaded` 를 그대로 읽어 왔다(`docs/spike/fixtures/{a-static,b-session}/
#: manifest.json`). 유형 B 에 `S1` 이 없고 `S6`(세션)이 있는 것이 그 행의 사실이다.
SEAMS_A: tuple[str, ...] = ("S1", "S2", "S3", "S4", "S5", "S7", "S8", "S9")
SEAMS_B: tuple[str, ...] = ("S2", "S4", "S5", "S6", "S7", "S8", "S9")

#: 이 저장소는 난이도를 잰 적이 없다(`ADR-0003` "능력 계층: 여전히 아무것도 재지
#: 않는다"). `MVP_SCOPE.md` §4.1 이 자동 난이도 추정을 명시적으로 금지하므로 값을
#: 고르지 않고 **재지 않았다는 사실**을 적는다.
DIFFICULTY = "unmeasured"

#: `description` 을 찾을 때 보는 이름 — 대소문자 무시, 이 순서로.
README_NAMES = ("readme.md", "readme.txt", "readme", "description.md")

#: `challenge_id` 로 쓸 수 있는 모양. `EvidenceStore.path_for` 가 `attempt_id` 를 경로
#: 요소로 쓰고 그 id 는 여기서 파생되므로, 여기서 막지 않으면 저장 루트 밖에 쓸 수 있다.
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ManifestError(ValueError):
    """매니페스트를 합성할 수 없다."""


@dataclass(frozen=True)
class SourceFile:
    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True)
class ServiceTarget:
    """살아 있는 서비스 하나 — `MANIFEST.md` §2.5 의 `target`.

    **이미지가 아니라 주소다.** 이미지는 `--service` 가 주고 통제 블록의 `image_digest`
    로 가며, 여기 오는 것은 worker 가 붙을 `host:port` 다. `agent_b.run_attempt` 는 이
    둘을 **매니페스트에서만** 읽고 없으면 죽는다(실측 `agent_b.py:510-517`) — 선언
    없는 대상에 붙는 것을 `SAFETY_SCOPE.md` "Allowed targets" 가 금지하기 때문이다.

    `host` 는 우리가 서비스 컨테이너에 붙이는 **네트워크 별칭**이다
    (`agent_b._start_service(..., alias=service_host)`). 대회가 주는 값이 아니라 우리가
    고르는 값이고, 그래서 기본값을 상수에서 가져와도 거짓이 되지 않는다. **`port` 는
    반대로 챌린지의 사실이다** — 서비스 이미지가 어느 포트를 여는지는 운영자가 안다.
    """

    host: str
    port: int


@dataclass(frozen=True)
class Synthesized:
    """디스크에 앉은 매니페스트 하나와 그것을 지목하는 값들."""

    root: Path
    challenge_id: str
    manifest_sha256: str
    source_files: tuple[SourceFile, ...]

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"


def synthesize(
    *,
    challenge_dir: Path,
    root: Path,
    flag_format: str,
    challenge_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    probes: tuple[str, ...] = (),
    #: 서비스가 있으면 유형 B, 없으면 유형 A. **유형은 여기서 파생되고 인자로 받지
    #: 않는다** — 두 벌로 두면 `--service` 는 줬는데 `type: "A"` 인 매니페스트가 만들어질
    #: 수 있고, 그러면 solver 선택과 매니페스트가 조용히 갈린다.
    service: ServiceTarget | None = None,
    seams_loaded: tuple[str, ...] | None = None,
) -> Synthesized:
    """`challenge_dir` 을 읽어 `root` 에 fixture 한 벌을 쓴다.

    `seams_loaded` 를 주지 않으면 **유형의 하중표 행**을 쓴다(`SEAMS_A`/`SEAMS_B`).
    S7·S8 이 이 챌린지에서 침묵한다는 사실은 여기 적지 않는다 — `MANIFEST.md` §2.3.a 가
    그것을 `provenance` 에서 **파생시키므로 선언이 아니다.**
    """
    if not challenge_dir.is_dir():
        raise ManifestError(f"챌린지 디렉터리가 없다: {challenge_dir}")
    if not flag_format.strip():
        raise ManifestError(
            "flag_format 이 비어 있다 — 기본값 없는 필수 통제 필드이고 (O-49) "
            "미상이면 attempt 가 시작조차 못 한다. 운영자에게 받아라"
        )

    cid = challenge_id or _derive_id(challenge_dir)
    if not _SAFE_ID.match(cid):
        raise ManifestError(
            f"challenge_id 가 경로 요소로 쓸 수 없는 모양이다: {cid!r} — "
            "attempt_id 가 여기서 파생되고 evidence store 가 그것을 경로로 쓴다"
        )

    root.mkdir(parents=True, exist_ok=True)
    (root / "input").mkdir(parents=True, exist_ok=True)
    bundle_path = root / "input" / BUNDLE_NAME
    sources = _pack(challenge_dir, bundle_path)
    if not sources:
        # **서비스 문제는 첨부가 없을 수 있다** — `nc host port` 하나가 전부인 문항이
        # 실제로 그렇다. `MANIFEST.md` §2.4 가 `inputs: []` 를 유효하다고 적고 그 경우
        # S1 은 `N/A` 다(R2-16). 유형 A 에서는 여전히 오류다: 파일도 서비스도 없으면
        # 풀 대상 자체가 없다.
        if service is None:
            raise ManifestError(
                f"챌린지 디렉터리에 파일이 없다: {challenge_dir} — "
                "서비스도 선언되지 않았으므로 이 attempt 에는 풀 대상이 없다"
            )
        bundle_path.unlink()

    bundle = bundle_path.read_bytes() if sources else b""
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "challenge_id": cid,
        # **유형은 서비스의 유무에서 파생된다.** `spec.md` §5 하중표의 행을 고르는 값이고
        # (`MANIFEST.md` §2.1), `kisia.contest.run` 이 이 값으로 solver 를 고른다.
        "type": "B" if service is not None else "A",
        "title": title or challenge_dir.name,
        "provenance": PROVENANCE,
        "provenance_note": (
            "라이브 대회에서 받은 입력물이다. 자작이 아니므로 dev·regression-private·"
            "final-holdout 어느 세트에도 들어가지 않는다 (HOLDOUT.md §1.1 — 이동은 한 "
            "방향뿐이다). challenge_set 은 contest 이고 그 짝은 accounting_label: "
            "contest 다 (R5-9 · R5-10)."
        ),
        "difficulty": DIFFICULTY,
        "description": _description(description, challenge_dir, sources, service),
        "challenge_set": CHALLENGE_SET,
        "flag_format": flag_format,
        # `solution_path` 는 **없다.** R5-10 이 contest-derived 에 한해 면제한다 —
        # 풀어야 나오는 것을 풀기 전에 요구할 수 없다 (O-49).
        "answer": {
            "verification": "deferred-manual",
            "note": (
                "정답을 저작자가 모른다. 후보 flag 는 운영자가 플랫폼에서 확인하고 "
                "결과를 밖에 기록한다 (MANIFEST.md §2.3.a). S8 verifier · S8.3 스윕 · "
                "S7 파생 검증은 돌지 않으며 판정은 N/A 이지 FAIL 이 아니다."
            ),
        },
        "inputs": (
            [
                {
                    "path": BUNDLE_NAME,
                    "sha256": hashlib.sha256(bundle).hexdigest(),
                    "bytes": len(bundle),
                }
            ]
            if sources
            else []
        ),
        "inputs_note": (
            f"대회 챌린지 파일 {len(sources)}개를 {BUNDLE_NAME} 하나로 묶었다. "
            "러너가 /input 에 넣는 것이 그 파일 하나이므로 inputs[] 는 실제로 마운트되는 "
            "것만 적는다. 원본 파일별 해시는 contest_source_files[] 다."
            if sources
            else (
                "이 챌린지에는 첨부 파일이 없다 — 서비스 하나가 전부다. "
                "inputs: [] 는 유효하고 그 경우 S1 은 N/A 다 (MANIFEST.md §2.4, R2-16)."
            )
        ),
        "contest_source_files": [
            {"path": s.path, "sha256": s.sha256, "bytes": s.bytes} for s in sources
        ],
        # `SAFETY_SCOPE.md` "Allowed targets" 가 말하는 선언이다. `null` 이면 이 attempt
        # 에 허용 대상이 없고, P-S2-c 가 그 사실을 행사한다.
        "target": (
            None
            if service is None
            else {
                "id": service.host,
                "host": service.host,
                "port": service.port,
                "proto": "tcp",
            }
        ),
        "workspace": {
            "input": "/input",
            "input_mode": "ro",
            "work": "/work",
            "artifacts": "/artifacts",
            "rootfs": "read-only",
            "network": "kisia-fixnet",
            "network_internal": True,
            # **여기 있는 것에는 닿고 없는 것에는 닿지 않아야 한다** (S2.4 / P-S2-c).
            # 유형 A 에는 하나도 없고, 유형 B 에는 선언된 서비스 하나뿐이다 —
            # `agent_b._control` 이 같은 값을 통제 블록에 싣는다.
            "declared_targets": (
                [] if service is None else [f"{service.host}:{service.port}"]
            ),
        },
        "display_limit_bytes": DISPLAY_LIMIT_BYTES,
        "seams_loaded": list(
            seams_loaded if seams_loaded is not None
            else (SEAMS_B if service is not None else SEAMS_A)
        ),
        "probes": list(probes),
    }
    return _write(root, cid, manifest, sources)


def respin(src: Synthesized, *, root: Path, description: str) -> Synthesized:
    """같은 입력물에 **다른 문제 기술**로 매니페스트를 다시 앉힌다.

    승격 사다리가 escalation 패킷을 다음 attempt 로 나르는 통로다. 패킷을 실을 자리는
    `description` 뿐이다 — `agent_a.TASK_PROMPT` 가 프롬프트에 싣는 것이 그 필드이고
    (그 모듈의 주석: *"챌린지 서술은 매니페스트에서 온다"*), 그 밖에 우리가 쓸 수 있는
    자리는 `kisia/runtime/` 편집을 요구한다.

    **새 디렉터리에 쓴다.** 같은 자리에 덮어쓰면 앞 attempt 의 통제 블록이 지목한
    `challenge_manifest_sha256` 이 가리키는 바이트가 사라지고, 그 스트림은 무엇을 푼
    기록인지 되짚을 수 없게 된다.
    """
    manifest = json.loads(src.manifest_path.read_text(encoding="utf-8"))
    manifest["description"] = description
    root.mkdir(parents=True, exist_ok=True)
    (root / "input").mkdir(parents=True, exist_ok=True)
    # 첨부가 없는 서비스 문제에는 bundle 자체가 없다 (`inputs: []`). **없는 것을 옮기려
    # 들지 않는다** — 없다는 사실이 이미 매니페스트에 적혀 있다.
    bundle = src.root / "input" / BUNDLE_NAME
    if bundle.is_file():
        (root / "input" / BUNDLE_NAME).write_bytes(bundle.read_bytes())
    return _write(root, src.challenge_id, manifest, src.source_files)


def _write(
    root: Path, cid: str, manifest: dict[str, Any], sources: tuple[SourceFile, ...]
) -> Synthesized:
    raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (root / "manifest.json").write_bytes(raw)
    return Synthesized(
        root=root,
        challenge_id=cid,
        manifest_sha256=hashlib.sha256(raw).hexdigest(),
        source_files=sources,
    )


def _pack(challenge_dir: Path, dest: Path) -> tuple[SourceFile, ...]:
    """디렉터리를 tar.gz 하나로 묶고 **원본 파일별 해시를 함께 돌려준다.**

    바이트가 재현 가능하도록 이름 순으로 넣고 mtime·uid·gid 를 지운다. 그러지 않으면
    같은 챌린지를 두 번 합성했을 때 `challenge_manifest_sha256` 이 달라지고, 두 스트림이
    같은 문제의 것인지 해시로 확인할 수 없게 된다.
    """
    # **경로 문자열로 정렬한다.** `Path` 끼리 비교하면 Windows 에서 대소문자를 무시해
    # 순서가 리눅스와 갈리고, 그러면 같은 챌린지의 매니페스트 해시가 기계마다 달라진다.
    files = sorted(
        (p.relative_to(challenge_dir).as_posix(), p)
        for p in challenge_dir.rglob("*")
        if p.is_file()
    )
    out: list[SourceFile] = []
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=9) as tf:
        # gzip 헤더의 mtime 을 0 으로 — `tarfile` 은 그것을 노출하지 않으므로 아래에서
        # 헤더 바이트를 직접 고친다.
        for name, path in files:
            data = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tf.addfile(info, BytesIO(data))
            out.append(
                SourceFile(path=name, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            )
    raw = bytearray(buf.getvalue())
    # gzip 헤더 4~7 바이트가 mtime 이다 (RFC 1952 §2.3.1).
    raw[4:8] = b"\x00\x00\x00\x00"
    dest.write_bytes(bytes(raw))
    return tuple(out)


def _description(
    given: str | None,
    challenge_dir: Path,
    sources: tuple[SourceFile, ...],
    service: ServiceTarget | None,
) -> str:
    """문제 기술 하나. **환경의 사실만 덧붙이고 문제는 지어내지 않는다.**

    유형 B 에 한 줄을 덧붙이는 이유는 실측이다: `agent_b` 의 SYSTEM/TASK 프롬프트는
    서비스 주소는 말하지만 **`/input` 을 한 번도 말하지 않는다**(`agent_b.py:66-92`).
    유형 A 의 프롬프트가 *"The challenge input is mounted at /input/bundle.tar.gz"* 로
    그것을 나르는 것과 갈리는 자리다. 첨부가 있는 서비스 문제에서 그 한 줄이 없으면
    모델은 파일이 있다는 사실 자체를 모른다. **이것은 챌린지에 대한 진술이 아니라
    컨테이너에 대한 진술이므로 지어낸 것이 아니다.**
    """
    base = given or _describe(challenge_dir, sources)
    if service is None or not sources:
        return base
    return (
        f"{base}\n\n"
        f"The challenge files are mounted read-only at /input/{BUNDLE_NAME} "
        f"({len(sources)} file(s) inside). Extract them into /work if you need them."
    )


def _describe(challenge_dir: Path, sources: tuple[SourceFile, ...]) -> str:
    """`--description-file` 이 없을 때. **문제를 지어내지 않는다.**"""
    by_name = {s.path.rsplit("/", 1)[-1].lower(): s.path for s in sources}
    for name in README_NAMES:
        rel = by_name.get(name)
        if rel is None:
            continue
        text = (challenge_dir / rel).read_text(encoding="utf-8", errors="replace").strip()
        if text:
            return text
    if not sources:
        # 첨부가 없는 서비스 문제. **"파일이 0개다"를 "파일 목록이 비었다"로 적지 않는다.**
        return (
            "No challenge description was provided with this challenge, and it ships "
            "no files — the service is the whole challenge. Nothing else about the "
            "intended solution is known to the harness."
        )
    listing = ", ".join(f"{s.path} ({s.bytes} B)" for s in sources[:20])
    if len(sources) > 20:
        listing += f", … (+{len(sources) - 20} more)"
    return (
        "No challenge description was provided with this challenge. "
        f"The bundle contains {len(sources)} file(s): {listing}. "
        "Nothing else about the intended solution is known to the harness."
    )


def _derive_id(challenge_dir: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", challenge_dir.resolve().name).strip("-")
    if not slug:
        raise ManifestError(
            f"디렉터리 이름에서 challenge_id 를 만들 수 없다: {challenge_dir} — "
            "--challenge-id 로 직접 줘라"
        )
    return f"contest-{slug}"
