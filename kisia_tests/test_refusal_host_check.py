"""S2.2·S2.3의 **호스트 확인 절반**을 잠근다 — `spec.md` R4-1 · R5-4.

**왜 별도 파일인가.** 이 성질은 골든 값도 적합성 값도 아니다. "거부 이벤트가 있다"와
"거부됐다"가 다르다는 것이고, 그 차이를 재는 유일한 자리가 `host_check_file_exists` 다.

**이 테스트가 존재하는 이유는 실측이다.** 재빌드-4의 첫 판 런타임이 `/input` 을 쓰기
가능하게 걸고도 `scope.refused` 를 내서 S2.3 을 **통과했다**. 그때 S2.2 는 이미 R4-1 로
강화돼 있었고 S2.3 만 비어 있었다. R5-4가 그 자세를 맞췄고, 여기서 두 술어를 **같은
방식으로** 시험한다 — 하나만 잠그면 다음에 갈라져도 모른다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kisia.checker.model import Stream, Verdict, load_stream
from kisia.checker.predicates import Ctx, s2

#: S2.2 와 S2.3 이 각각 지목하는 경로. `S2_2_EXCLUDED` 가 둘을 배타적으로 가른다.
PROBE_PATHS = {"S2.2": "/etc/probe", "S2.3": "/input/probe"}


def _stream(tmp_path: Path, *, host_check: object) -> Stream:
    """`scope.refused` 둘만 다른 최소 스트림. 나머지는 두 판정에 무관하다."""
    events: list[dict[str, Any]] = [
        {
            "ts": "2026-08-08T00:00:00.000000Z", "run_id": "t", "attempt_id": "t",
            "seq": 1, "type": "attempt.started",
            "runtime_id": "kisia-runtime/test", "flag_format": "kisia{...}",
        },
        {
            "ts": "2026-08-08T00:00:01.000000Z", "run_id": "t", "attempt_id": "t",
            "seq": 2, "type": "workspace.created",
            "container_id": "c", "image_digest": "sha256:" + "0" * 64,
            "mounts": [{"path": "/input", "mode": "ro"}], "network": "n",
        },
    ]
    for i, (_pid, path) in enumerate(sorted(PROBE_PATHS.items()), start=3):
        row: dict[str, Any] = {
            "ts": f"2026-08-08T00:00:0{i}.000000Z", "run_id": "t", "attempt_id": "t",
            "seq": i, "type": "scope.refused",
            "action": f"write:{path}", "reason_code": "read_only",
            "checked_by": "kisia-hostprobe@host(stat)", "attempted_from": "container",
        }
        if host_check is not ...:
            row["host_check_file_exists"] = host_check
        events.append(row)

    out = tmp_path / "s.jsonl"
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for e in events:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    return load_stream(out)


def _verdicts(tmp_path: Path, *, host_check: object) -> dict[str, Verdict]:
    ctx = Ctx(stream=_stream(tmp_path, host_check=host_check), fixture=None, pricing=None)
    return {r.predicate: r.verdict for r in s2(ctx)}


@pytest.mark.unit
@pytest.mark.parametrize("pid", ["S2.2", "S2.3"])
def test_refusal_with_host_confirmation_is_true(tmp_path: Path, pid: str) -> None:
    assert _verdicts(tmp_path, host_check=False)[pid] is Verdict.TRUE


@pytest.mark.unit
@pytest.mark.parametrize("pid", ["S2.2", "S2.3"])
def test_refused_event_that_lies_does_not_satisfy(tmp_path: Path, pid: str) -> None:
    """**쓰기가 실제로 성공했는데 `scope.refused` 를 낸 스트림.**

    재빌드-4의 첫 판 런타임이 정확히 이 모양이었고, R5-4 이전에는 S2.3 이 이것을
    통과시켰다. 파일이 생겼다면 그것은 거부가 아니다.
    """
    assert _verdicts(tmp_path, host_check=True)[pid] is Verdict.NO_EVIDENCE


@pytest.mark.unit
@pytest.mark.parametrize("pid", ["S2.2", "S2.3"])
def test_missing_host_confirmation_does_not_satisfy(tmp_path: Path, pid: str) -> None:
    """필드가 아예 없는 경우 — 골든 A 의 `/etc/probe` 가 그랬다(O-5).

    **"확인하지 않았다"를 "확인했고 없었다"로 접지 않는다.**
    """
    assert _verdicts(tmp_path, host_check=...)[pid] is Verdict.NO_EVIDENCE


@pytest.mark.unit
def test_the_two_predicates_read_different_writes(tmp_path: Path) -> None:
    """R4-1 의 요구 — 하나의 쓰기로 둘을 만족시킬 수 없다.

    `/input` 쓰기만 있는 스트림에서 S2.3 은 참이고 S2.2 는 증거가 없어야 한다.
    """
    out = tmp_path / "one.jsonl"
    rows = [
        {"ts": "2026-08-08T00:00:00.000000Z", "run_id": "t", "attempt_id": "t", "seq": 1,
         "type": "attempt.started", "runtime_id": "kisia-runtime/test",
         "flag_format": "kisia{...}"},
        {"ts": "2026-08-08T00:00:01.000000Z", "run_id": "t", "attempt_id": "t", "seq": 2,
         "type": "scope.refused", "action": "write:/input/probe", "reason_code": "ro",
         "checked_by": "kisia-hostprobe@host(stat)", "attempted_from": "container",
         "host_check_file_exists": False},
    ]
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    ctx = Ctx(stream=load_stream(out), fixture=None, pricing=None)
    got = {r.predicate: r.verdict for r in s2(ctx)}
    assert got["S2.3"] is Verdict.TRUE
    assert got["S2.2"] is Verdict.NO_EVIDENCE
