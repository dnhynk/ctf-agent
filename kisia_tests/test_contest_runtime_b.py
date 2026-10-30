"""유형 B 대회 런타임의 smoke — 무정답 모드와 파라미터화한 시그니처.

`test_contest_runtime.py` 가 유형 A 에 대해 재는 것을 유형 B 에 대해 잰다. **smoke 다**
(`MVP_SCOPE.md` §2-8). 모델도 컨테이너도 docker 도 부르지 않는다 — 여기서 재는 것은
`run_attempt` 이 **어디서 값을 얻는가**와 `submit_flag` 이 **판정 없이 무엇을 내는가**뿐이다.

유형 B 가 유형 A 와 갈리는 자리 둘을 따로 잰다.

1. **서비스 대상**(`host`/`port`)이 모듈 상수가 아니라 매니페스트 §2.5 의 `target` 에서
   온다. 상수로 두면 대회 챌린지의 worker 가 dev 픽스처의 주소로 붙으려 한다.
2. **음성 프로브가 없다.** `agent_b` 의 `PROBES` 는 `B-1`·`B-3`·`B-4`·`B-11` 이고 전부
   세션 런타임 프로브다 — 정답에 기대지 않으므로 무정답 모드에서도 집합이 갈리지 않는다.
   `agent_a` 가 `A-4` 를 빼며 `probes` 를 인자로 연 것과 다른 이유가 그것이다.

**이 파일은 어떤 seam 판정도 인용하지 못한다** (`CLAUDE.md` §6.1-3).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from kisia.runtime import agent_b, golden_b
from kisia.runtime.golden_a import Fixture

FLAG = "kisia{zone_part}"


class _Writer:
    """`EnvelopeWriter` 자리의 가짜. **낸 이벤트를 순서대로 쥔다.**"""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))

    def types(self) -> list[str]:
        return [t for t, _ in self.events]


class _Rec:
    """`TrackingRecorder` 자리의 가짜. `submit_flag` 은 `ids` 만 읽는다."""

    def __init__(self) -> None:
        self.ids: list[str] = ["obs-0001"]
        self.limit = 4096


class _StubFixture:
    def __init__(self, answer_path: Path) -> None:
        self.answer_path = answer_path


def _submit_flag(
    monkeypatch: pytest.MonkeyPatch, verdict: bool | None
) -> tuple[_Writer, dict[str, Any], Any]:
    """`submit_flag` 하나를 꺼내 온다. `_verify` 는 가짜다 — 별도 프로세스를 부르지 않는다.

    `ws`·`registry` 는 `submit_flag` 의 클로저가 읽지 않는다(실측: 그 함수는
    `state`·`w`·`rec.ids`·`fixture.answer_path` 만 쓴다).
    """
    w = _Writer()
    state: dict[str, Any] = {
        "submitted": [],
        "solved": False,
        "sessions_opened": 0,
        "closed": 0,
    }
    monkeypatch.setattr(agent_b, "_verify", lambda *_args: verdict)
    tools = agent_b._build_tools(
        w=w,  # type: ignore[arg-type]
        rec=_Rec(),  # type: ignore[arg-type]
        ws=None,  # type: ignore[arg-type]
        registry=None,  # type: ignore[arg-type]
        fixture=_StubFixture(Path("nope.json")),  # type: ignore[arg-type]
        state=state,
        service_host="svc.example",
        service_port=1234,
    )
    submit = next(t for t in tools if t.name == "submit_flag")
    return w, state, submit


# ---------------------------------------------------------------------------
# 1. 무정답 모드 — 판정하지 않은 것을 오답으로 적지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_no_verification_event_when_the_verdict_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`MANIFEST.md` §2.3.a — *"S8 의 verifier 는 돌지 않는다. 판정은 `N/A` 이지 FAIL 이
    아니다."* `verdict: false` 를 내면 라이브 대회의 모든 후보가 오답으로 **기록된다.**
    """
    w, state, submit = _submit_flag(monkeypatch, None)
    out = submit.run({"value": FLAG})

    assert "verification.completed" not in w.types(), (
        "판정하지 않았는데 판정 이벤트를 냈다 — ' 모른다'를 '틀렸다'로 접은 것이다"
    )
    assert state["solved"] is False
    assert out.terminal is False
    assert out.reply == "recorded"


@pytest.mark.contract
def test_the_candidate_is_still_reported_without_a_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """후보 보고는 판정과 다른 일이다 — 그것이 무정답 모드가 **하는** 것이다."""
    w, state, submit = _submit_flag(monkeypatch, None)
    submit.run({"value": FLAG})

    produced = [p for t, p in w.events if t == "candidate.produced"]
    assert len(produced) == 1
    assert produced[0]["value"] == FLAG
    assert state["submitted"] == [FLAG]


@pytest.mark.contract
@pytest.mark.parametrize(("verdict", "terminal"), [(True, True), (False, False)])
def test_a_known_answer_still_emits_the_verdict(
    monkeypatch: pytest.MonkeyPatch, verdict: bool, terminal: bool
) -> None:
    """**회귀 방지.** 무정답 모드를 더한 것이 정답이 있는 판정을 바꾸지 않는다."""
    w, state, submit = _submit_flag(monkeypatch, verdict)
    out = submit.run({"value": FLAG})

    events = [p for t, p in w.events if t == "verification.completed"]
    assert len(events) == 1
    assert events[0]["verdict"] is verdict
    assert state["solved"] is verdict
    assert out.terminal is terminal


# ---------------------------------------------------------------------------
# 2. 시그니처 — 라벨에 기본값을 두지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_attempt_takes_the_accounting_label_and_k_without_defaults() -> None:
    """`control.DEFAULTS` 말미: *"라벨의 기본값은 지표 전체를 오염시킨다."*"""
    params = inspect.signature(agent_b.run_attempt).parameters
    for name in ("accounting_label", "solve_k"):
        assert name in params, f"{name} 을 받지 않는다"
        assert params[name].default is inspect.Parameter.empty, (
            f"{name} 에 기본값이 있다 — 라벨의 기본값은 지표 전체를 오염시킨다"
        )
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.unit
def test_run_attempt_takes_challenge_set_and_provenance_with_todays_values() -> None:
    """뒤 둘은 기본값이 있다 — 지금까지 박혀 있던 값 그대로여야 기존 스트림이 갈리지
    않는다 (`R5-10` 소급)."""
    params = inspect.signature(agent_b.run_attempt).parameters
    assert params["challenge_set"].default == "dev"
    assert params["provenance"].default == "synthetic"


@pytest.mark.unit
def test_the_service_image_is_an_argument_not_a_constant() -> None:
    """대회 진입점의 `--service <img>` 가 오는 자리다. **기본값이 없다** — 유형 B 는
    서비스 없이 돌 수 없으므로 미선언이 조용히 통과해서는 안 된다."""
    params = inspect.signature(agent_b.run_attempt).parameters
    assert params["service_image"].default is inspect.Parameter.empty
    assert params["service_image"].kind is inspect.Parameter.KEYWORD_ONLY
    # 이름 쪽은 매니페스트에 없어 기본값을 둔다 — 지금까지 박혀 있던 값 그대로다.
    assert params["service_image_name"].default == "kisia/fix-b-service"
    assert params["image_name"].default == "kisia/worker-b"


# ---------------------------------------------------------------------------
# 3. 챌린지의 사실은 챌린지에서 온다 (`O-57`)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_challenge_facts_come_from_the_manifest() -> None:
    """소스를 읽어 잰다. 컨테이너도 모델도 없이 `run_attempt` 을 부를 수 없고, 이것은
    **그 함수가 어디서 값을 얻는가**의 문제다."""
    src = inspect.getsource(agent_b.run_attempt)
    assert 'manifest["challenge_id"]' in src
    assert 'manifest["flag_format"]' in src
    assert 'target["host"]' in src
    assert 'target["port"]' in src
    assert "CHALLENGE_ID" not in src, "모듈 상수가 아직 남아 있다"


def _fixture_without_target(root: Path) -> Fixture:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "challenge_id": "kisia-contest-b",
                "flag_format": "kisia{...}",
                "display_limit_bytes": 4096,
                "inputs": [],
            }
        ),
        encoding="utf-8",
    )
    return Fixture(root)


@pytest.mark.contract
def test_a_manifest_without_a_target_dies_before_anything_starts(tmp_path: Path) -> None:
    """**선언 없는 대상에 붙지 않는다** (`SAFETY_SCOPE.md` "Allowed targets").

    상수 fallback 을 두면 대회 챌린지의 worker 가 dev 픽스처의 주소로 붙으려 하고,
    그것은 "닿지 못했다"로 죽거나 — 더 나쁘게 — 남의 서비스에 닿는다. 여기서 죽는 것이
    옳고, 컨테이너가 서기 **전에** 죽는다.
    """
    with pytest.raises(SystemExit) as caught:
        agent_b.run_attempt(
            out_path=tmp_path / "out.jsonl",
            attempt="smoke-b-01",
            fixture=_fixture_without_target(tmp_path / "fix"),
            pricing=tmp_path / "pricing.yaml",
            image="sha256:0",
            service_image="sha256:1",
            host_id="smoke",
            api_key="",
            model_id="gpt-5.6-terra",
            effort="none",
            capability_probe=tmp_path / "probe.json",
            capability_probe_id="none",
            accounting_label="contest",
            solve_k=1,
        )
    assert "target.host" in str(caught.value)


# ---------------------------------------------------------------------------
# 4. 서비스 컨테이너 — 골든의 호출은 한 글자도 바뀌지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_service_helpers_keep_goldens_behaviour_by_default() -> None:
    """`golden_b` 는 자기 상수를 그대로 쓴다. 열기만 하고 바꾸지 않았다."""
    start = inspect.signature(golden_b._start_service).parameters
    assert start["container"].default == golden_b.SERVICE_CONTAINER
    assert start["alias"].default == golden_b.SERVICE_NAME

    wait = inspect.signature(golden_b._wait_for_service).parameters
    assert wait["host"].default == golden_b.SERVICE_NAME
    assert wait["port"].default == golden_b.SERVICE_PORT


@pytest.mark.unit
def test_the_service_container_name_is_split_per_attempt() -> None:
    """`MVP_SCOPE.md` §4.1 이 동시 실행 2~4 를 요구한다. 이름이 상수면 뒤 attempt 의
    `rm -f` 가 앞 attempt 의 서비스를 죽인다 — `D-64` 와 같은 족속이다."""
    src = inspect.getsource(agent_b.run_attempt)
    assert 'f"{SERVICE_CONTAINER}-{attempt}"' in src
