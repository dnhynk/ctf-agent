"""대회 런타임의 smoke — 무정답 모드와 파라미터화한 시그니처.

**smoke 다.** `MVP_SCOPE.md` §2-8 이 신규 contest 경로의 커버리지를 **smoke 만**으로
잘랐고, 그 부채는 §2 의 표에 8번으로 적혀 있다. 여기서 재는 것은 셋뿐이다.

1. **verifier 가 "모른다"를 "틀렸다"로 접지 않는다** — `n/a` 이지 `false` 가 아니다.
   접으면 라이브 대회의 모든 후보가 오답으로 **기록되고** 그 기록은 되돌릴 수 없다
   (`MANIFEST.md` §2.3.a, `spec.md` R2-3).
2. **`_verify` 가 그 사실을 `None` 으로 나른다** — `False` 가 아니다.
3. **`run_attempt` 이 `accounting_label`·`solve_k` 를 기본값 없이 받는다** —
   `control.DEFAULTS` 말미: *"라벨의 기본값은 지표 전체를 오염시킨다."*

**이 파일은 어떤 seam 판정도 인용하지 못한다** (`CLAUDE.md` §6.1-3).
"""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from kisia.runtime import agent_a
from kisia.runtime.golden_a import _verify

FLAG = "kisia{5o9v_1472742}"


def _run_verifier(answer: Path, candidates: list[str]) -> list[str]:
    """verifier 를 **별도 프로세스로** 부른다 — 그것이 S8 의 배치다."""
    proc = subprocess.run(
        [sys.executable, "-m", "kisia.runtime.verifier", "--answer", str(answer)],
        input=("\n".join(candidates) + "\n").encode("utf-8"),
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    return proc.stdout.decode("utf-8").splitlines()


def _answer_file(tmp_path: Path) -> Path:
    path = tmp_path / "answer.json"
    path.write_text(
        json.dumps(
            {
                "challenge_id": "kisia-fix-a-static",
                "flag": FLAG,
                "flag_sha256": hashlib.sha256(FLAG.encode("utf-8")).hexdigest(),
                "parts": {"from_notes_bin": "5o9v", "from_ledger_csv": "1472742"},
            }
        ),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# 1. verifier — 무정답 모드
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_a_missing_answer_file_yields_n_a_not_false(tmp_path: Path) -> None:
    """대회 챌린지에는 `answer/` 가 없다. 없는 것은 오답이 아니다."""
    lines = _run_verifier(tmp_path / "nope.json", [FLAG, "kisia{wrong}"])
    assert lines == ["n/a", "n/a"]


@pytest.mark.contract
def test_an_answer_without_a_flag_key_yields_n_a(tmp_path: Path) -> None:
    """`MANIFEST.md` §2.3.a 의 `verification: deferred-manual` 형태다 —
    파일은 있고 `flag`·`flag_sha256`·`parts` 가 없다."""
    path = tmp_path / "answer.json"
    path.write_text(
        json.dumps(
            {
                "verification": "deferred-manual",
                "note": "정답을 저작자가 모른다. 후보는 운영자가 플랫폼에서 확인한다.",
            }
        ),
        encoding="utf-8",
    )
    assert _run_verifier(path, [FLAG]) == ["n/a"]


@pytest.mark.contract
def test_a_real_answer_still_judges_true_and_false(tmp_path: Path) -> None:
    """**회귀 방지.** 무정답 모드를 더한 것이 있는 정답의 판정을 바꾸지 않는다."""
    answer = _answer_file(tmp_path)
    assert _run_verifier(answer, [FLAG, "kisia{5o9v_1472743}", ""]) == [
        "true",
        "false",
        "false",
    ]


@pytest.mark.contract
def test_every_candidate_gets_exactly_one_line(tmp_path: Path) -> None:
    """줄 수가 어긋나면 호출자가 어느 후보의 답인지 잃는다."""
    assert len(_run_verifier(tmp_path / "nope.json", ["a", "b", "c"])) == 3


# ---------------------------------------------------------------------------
# 2. `_verify` — `None` 은 `False` 가 아니다
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_verify_returns_none_when_the_answer_is_unknown(tmp_path: Path) -> None:
    verdict = _verify(tmp_path / "nope.json", FLAG)
    assert verdict is None, "'판정하지 않았다'를 False 로 접으면 거짓 관측이다"


@pytest.mark.contract
def test_verify_still_returns_true_and_false_with_an_answer(tmp_path: Path) -> None:
    answer = _answer_file(tmp_path)
    assert _verify(answer, FLAG) is True
    assert _verify(answer, "kisia{nope}") is False


@pytest.mark.contract
def test_the_no_answer_probe_asks_the_verifier_rather_than_reading_the_file(
    tmp_path: Path,
) -> None:
    """`_answer_is_known` 은 `answer.json` 을 **열지 않는다** (`PATH_SCOPE.md` §1).

    여는지 아닌지는 소스로 재지 않는다 — 있는 정답과 없는 정답 둘 다에서 옳은 답을
    내는지로 잰다. 파일을 여는 구현이라면 없는 파일에서 죽는다.
    """

    class _F:
        def __init__(self, path: Path) -> None:
            self.answer_path = path

    assert agent_a._answer_is_known(_F(tmp_path / "nope.json")) is False  # type: ignore[arg-type]
    assert agent_a._answer_is_known(_F(_answer_file(tmp_path))) is True  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 3. 시그니처 — 라벨에 기본값을 두지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_attempt_takes_the_accounting_label_and_k_without_defaults() -> None:
    """`control.DEFAULTS` 말미: *"라벨의 기본값은 지표 전체를 오염시킨다."*

    선언하지 않은 run 이 조용히 계기의 숫자로 세어지는 것을 막는 자리가 두 곳이다 —
    `ControlBlock.build` 가 발행 시점에 죽고, 이 시그니처가 **호출 시점에** 죽는다.
    """
    params = inspect.signature(agent_a.run_attempt).parameters
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
    params = inspect.signature(agent_a.run_attempt).parameters
    assert params["challenge_set"].default == "dev"
    assert params["provenance"].default == "synthetic"


@pytest.mark.unit
def test_the_challenge_id_and_flag_format_come_from_the_manifest() -> None:
    """`O-57` — 모듈 상수로 박아 두면 대회 챌린지의 통제 블록이 fixture 를 재구성한다.

    소스를 읽어 잰다. 컨테이너도 모델도 없이 `run_attempt` 을 부를 수 없고, 이것은
    **그 함수가 어디서 값을 얻는가**의 문제다.
    """
    src = inspect.getsource(agent_a.run_attempt)
    assert 'manifest["challenge_id"]' in src
    assert 'manifest["flag_format"]' in src
    assert "CHALLENGE_ID" not in src, "모듈 상수가 아직 남아 있다"
