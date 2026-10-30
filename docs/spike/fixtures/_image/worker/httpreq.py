#!/usr/bin/env python3
"""worker 안의 HTTP 도구.

stdin에 요청 JSON 하나, stdout에 응답 JSON 하나. 리다이렉트를 따라가지 않고 쿠키를
스스로 저장하지 않는다 — 상태는 전부 호출자(골든 드라이버)가 들고 있어야
`http.exchanged.jar_digest_before/after`가 의미를 갖고 C-4가 관측 가능해진다.

요청  {"method","url","headers":{...},"body": <str|null>, "timeout": <s>}
응답  {"status","reason","headers":[[k,v],...],"body"}
"""
import json
import sys
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def main() -> int:
    req = json.load(sys.stdin)
    data = req.get("body")
    body = data.encode() if isinstance(data, str) else None
    r = urllib.request.Request(
        req["url"],
        data=body,
        method=req.get("method", "GET"),
        headers=req.get("headers", {}),
    )
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(r, timeout=req.get("timeout", 20)) as resp:
            out = {
                "status": resp.status,
                "reason": resp.reason,
                "headers": [[k, v] for k, v in resp.getheaders()],
                "body": resp.read().decode("utf-8", "replace"),
            }
    except urllib.error.HTTPError as e:
        # 4xx/5xx는 오류가 아니라 관측이다. 유형 C의 음성 프로브가 여기에 걸린다.
        out = {
            "status": e.code,
            "reason": e.reason,
            "headers": [[k, v] for k, v in e.headers.items()],
            "body": e.read().decode("utf-8", "replace"),
        }
    except Exception as e:  # noqa: BLE001 - 네트워크 거부도 관측이다
        out = {"status": 0, "reason": f"{type(e).__name__}: {e}", "headers": [], "body": ""}
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
