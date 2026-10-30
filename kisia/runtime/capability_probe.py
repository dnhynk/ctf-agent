"""capability probe — endpoint 와 parameter 의 조합이 실제로 무엇을 하는가.

ADR-0001 이 `/v1/chat/completions` 에 대해 여섯 칸을 실측했고, **그 표가 이 프로젝트의
모델 설정 전체의 근거**다. `SEAM_IMPLEMENTATION_MAP.md` §7.1-1 이 endpoint 를
`/v1/responses` 로 옮기라고 하므로 같은 표를 다시 재야 한다 — 옮긴 뒤의 값을 앞의
표에서 연역하면 그것이 경고 9("연역한 것을 관측 없이 실행하지 마라")다.

ADR-0001 §4: **capability probe 는 메모가 아니라 artifact 다.** 통제 블록은 그것을
`capability_probe_id` 로 가리키고, `model_snapshot` 은 그 artifact 가 관측한
`response.model` 이다.

재빌드-7의 실측이 실제로 ADR-0001 의 표와 **두 칸 갈렸다**:

| 조합 | `/v1/chat/completions` (ADR-0001) | `/v1/responses` (여기) |
|---|---|---|
| tools + `medium` | **FAIL** | OK |
| tools + effort **부재** | **FAIL** | **OK — 서버가 `medium` 으로 채운다** |

둘째가 위험하다. chat/completions 에서는 effort 를 빠뜨리면 요청이 죽어서 **실수가
드러났다.** Responses 에서는 200 이 오고 통제 블록이 `none` 이라고 적는 동안 medium 이
돈다 — S3.5 가 막으려는 오염이 반대 방향으로 열린다. 그래서 `model.py` 는 effort 를
언제나 명시적으로 싣는다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BASE = "https://api.openai.com/v1/responses"

_TOOL = {
    "type": "function",
    "name": "noop",
    "description": "Does nothing. Present only to exercise the function-tool path.",
    "parameters": {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
        "additionalProperties": False,
    },
}

#: `None` 은 **`reasoning` 을 아예 보내지 않는다**는 뜻이다. 그 칸이 ADR-0001 표
#: 3행에 해당하고, 여기서 값이 갈린다.
EFFORTS: tuple[str | None, ...] = ("none", "medium", None)


def _call(key: str, model: str, effort: str | None, tools: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "input": [{"role": "user", "content": "Reply with exactly: ok"}],
        "store": False,
        "stream": False,
    }
    if effort is not None:
        body["reasoning"] = {"effort": effort}
    if tools:
        body["tools"] = [_TOOL]
    req = urllib.request.Request(
        BASE,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            status, payload = resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status, payload = exc.code, exc.read().decode("utf-8", "replace")
    latency = int((time.monotonic() - started) * 1000)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = {"_unparsed": payload[:2000]}

    cell: dict[str, Any] = {
        "model_id": model,
        "endpoint": "/v1/responses",
        "tools": tools,
        "reasoning_effort_sent": effort,
        "status": status,
        "latency_ms": latency,
        "result": "OK" if status == 200 else "FAIL",
    }
    if status == 200:
        usage = data.get("usage") or {}
        cell["observed_model"] = data.get("model")
        cell["observed_effort"] = (data.get("reasoning") or {}).get("effort")
        cell["reasoning_tokens"] = (usage.get("output_tokens_details") or {}).get(
            "reasoning_tokens"
        )
        cell["usage_keys"] = sorted(usage)
        cell["input_tokens_details_keys"] = sorted(usage.get("input_tokens_details") or {})
    else:
        cell["error"] = (data.get("error") or {}).get("message", "")[:400]
    cell["raw"] = data
    return cell


def build(
    key: str, models: list[str], efforts: tuple[str | None, ...] = EFFORTS
) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    for model in models:
        for tools in (True, False):
            for effort in efforts:
                cell = _call(key, model, effort, tools)
                print(
                    f"  {model:<15} tools={tools!s:<5} effort={effort!s:<7} "
                    f"-> {cell['result']} observed_effort={cell.get('observed_effort')} "
                    f"reasoning_tokens={cell.get('reasoning_tokens')}",
                    flush=True,
                )
                cells.append(cell)
    return {
        "probe_id": "",  # 호출자가 채운다
        "endpoint": "/v1/responses",
        "models": models,
        "cells": cells,
    }


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    ap = argparse.ArgumentParser(description="Responses capability probe (ADR-0001 §4)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--probe-id", required=True)
    ap.add_argument("--models", nargs="+", default=["gpt-5.6-terra", "gpt-5.6-luna"])
    ap.add_argument(
        "--efforts",
        nargs="+",
        default=None,
        help=(
            "보낼 reasoning effort 목록. 'omit' 은 reasoning 블록을 아예 보내지 않는다는 "
            "뜻이고 그 칸이 ADR-0001 표 3행이다. 생략하면 EFFORTS 그대로다"
        ),
    )
    args = ap.parse_args(argv)

    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        print("OPENAI_API_KEY 가 비어 있다")
        return 2
    efforts = (
        EFFORTS
        if args.efforts is None
        else tuple(None if e == "omit" else e for e in args.efforts)
    )
    doc = build(key, list(args.models), efforts)
    doc["probe_id"] = args.probe_id
    blob = json.dumps(doc, ensure_ascii=False, indent=2)
    if key in blob:
        print("probe 원문에 키가 들어 있다 — 저장하지 않는다")
        return 3
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(blob, encoding="utf-8")
    print(f"-> {args.out}  ({len(doc['cells'])} 칸)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
