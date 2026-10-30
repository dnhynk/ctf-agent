"""유형 C 모델 주도 — `agent_c`. 재빌드-7·8이 두 번 미룬 자리를 프로덕션-1이 연다.

**이 파일이 재는 것 넷.** 넷 다 "실행이 잡기 전에 잡는다"가 목적이고, 그중 첫째는
**어떤 계약 술어도 재지 않는 것**이다(`O-26`).

1. **vendored 트리를 끌고 오지 않는가.** 통제 블록이 `vendored_components: []` 를
   선언하는데 `golden_b`/`agent_b` 에서 무엇을 가져오면 `session.py` 를 통해 vendored
   코드가 **import 시점에** 딸려 온다. 선언과 모듈 그래프의 어긋남을 검사기가 재지
   않으므로 이 시험이 유일한 계기다.
2. **`S6.5` 가 기대는 프로브를 켜는가.** 첫 판이 `C-4` 를 뺐고 유형 C 집합이
   `S6 FAIL(S6.5)[no-evidence]` 가 됐다 — **실행이 잡았고 유추로는 갈 수 없었다.**
3. **항아리를 절대 경로로 선언하는가** (R3-9). 없으면 S6 이 재려는 상태 소재가
   스트림에 없다.
4. **도구 표면이 §4-2 를 지키는가** — 완성된 호출문이 설명에 있다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs" / "spike" / "fixtures" / "c-web"


@pytest.mark.contract
def test_agent_c_does_not_import_the_vendored_tree() -> None:
    """**`O-26` 이 지목한 어긋남을 막는 유일한 계기다.**

    별개 프로세스에서 본다 — 이 파일이 이미 `agent_b` 를 열어 두었으면 `sys.modules`
    가 오염돼 아무것도 재지 못한다. `golden_c` 에 대한 같은 시험이
    `test_golden_c.py` 에 있고, 이것은 그 위층이다.
    """
    probe = (
        "import sys, kisia.runtime.agent_c;"
        "print([m for m in sys.modules if m.split('.')[0] == 'vendor'])"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, check=True, cwd=ROOT
    )
    assert proc.stdout.decode().strip() == "[]"


@pytest.mark.contract
def test_agent_c_does_not_import_the_type_b_modules() -> None:
    """vendored 가 안 딸려 오는 것과 **B 모듈을 안 쓰는 것**은 다른 사실이다.

    지금은 앞 시험이 이것을 함께 잡지만, `golden_b` 가 언젠가 vendored 를 지연
    import 하게 되면 앞 시험만으로는 통과한다. 그때 이 줄이 남는다.
    """
    probe = (
        "import sys, kisia.runtime.agent_c;"
        "print(sorted(m for m in sys.modules "
        "if m in ('kisia.runtime.golden_b', 'kisia.runtime.agent_b')))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, check=True, cwd=ROOT
    )
    assert proc.stdout.decode().strip() == "[]"


@pytest.mark.unit
def test_the_agent_set_runs_the_probe_that_s6_5_depends_on() -> None:
    """**S6.5 의 증거는 P-S6-a 에서만 나온다.**

    이 시험이 있는 이유는 그것을 빼 봤기 때문이다 — 빼면 유형 C 집합이
    `S6 FAIL(S6.5)[no-evidence]` 가 된다. 프로브를 줄일 때 어느 술어가 비는지는
    **판정을 돌려 봐야** 알 수 있고, 유형 B 의 `B-9` 에서 유추할 수 없었다.
    """
    from kisia.runtime.agent_c import PROBES as AGENT
    from kisia.runtime.golden_c import PROBES as GOLDEN

    # **`C-4` 를 뺐다가 실행이 되돌렸다.** 유형 C 집합이 `S6 FAIL(S6.5)[no-evidence]`
    # 가 됐고, `S6.5` 의 세 신호는 P-S6-a(= C-4)에서만 나온다. `agent_b` 가 `B-9` 를
    # 빼도 아무 술어가 비지 않았던 것과 다른 자리다 — 유추로 갈 수 없었다.
    assert "C-4" in AGENT
    assert set(AGENT) == set(GOLDEN)


@pytest.mark.unit
def test_the_cookie_jar_is_declared_as_an_absolute_path() -> None:
    """R3-9 — E·X 가 P-S6-a 의 개입을 확인하지 못한 원인이 상대 경로였다."""
    import inspect

    from kisia.runtime import agent_c
    from kisia.runtime.golden_c import JAR_PATH

    src = inspect.getsource(agent_c.run_attempt)
    assert "state_locations=lambda" in src
    assert "JAR_PATH" in src and "droppable" in src
    assert JAR_PATH.startswith("/"), JAR_PATH


@pytest.mark.unit
def test_every_tool_description_carries_a_completed_call() -> None:
    """§4-2 — 설명문만으로는 모델이 도구를 쓰지 않았다(스파이크 X 0/4)."""
    import inspect

    from kisia.runtime import agent_c

    src = inspect.getsource(agent_c._build_tools)
    names = ("http_request", "run_command", "write_file", "submit_flag")
    for name in names:
        assert f'name="{name}"' in src, name
    # 도구 넷, 완성된 호출문 넷.
    assert src.count("Example: ") == len(names)


@pytest.mark.unit
def test_the_sweep_surface_lists_only_what_the_harness_actually_placed() -> None:
    """`golden_c` 는 `assemble.py` 를 굽지만 모델 주도는 넣지 않는다.

    없는 파일을 표면에 넣으면 **재지 않은 것을 잰 것으로** 적게 된다 — `D-63` 과 같은
    족속이다. 빈 `input_files` 는 반대로 **빼지 않는다**: 빠지면 "쟀는데 0"과 "재지
    않았다"가 갈리지 않는다.
    """
    import ast
    import inspect

    from kisia.runtime import agent_c

    # **docstring 을 빼고 본다.** 그 문장이 `assemble.py` 가 **없는 이유**를 적으므로,
    # 원문 그대로 세면 설명문에 걸린다 — 검사가 재려는 것과 다른 것을 재는 자리다.
    fn = ast.parse(inspect.getsource(agent_c._sweep_surfaces)).body[0]
    assert isinstance(fn, ast.FunctionDef)
    body = fn.body[1:] if ast.get_docstring(fn) else fn.body
    code = "\n".join(ast.unparse(node) for node in body)

    assert "httpreq.py" in code
    assert "assemble.py" not in code
    for surface in ("input_files", "artifacts", "container:/input", "container:/work"):
        assert surface in code, surface


@pytest.mark.unit
def test_the_manifest_declares_no_inputs_for_type_c() -> None:
    """R2-16 — 빈 `files[]` 는 위반이 아니다. 그 전제를 여기서 잠근다."""
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["inputs"] == []
