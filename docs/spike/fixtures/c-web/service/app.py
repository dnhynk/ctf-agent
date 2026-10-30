#!/usr/bin/env python3
"""유형 C — 웹 상태 fixture 서비스.

**설계 목표는 "쿠키를 잃으면 반드시 실패한다"이다**(§9.2). 세 요청을 가로질러 살아야
하는 것은 *연결*이 아니라 *쿠키*라는 점이 유형 B와 다르다 — HTTP는 연결이 끊겨도
정상이고, 상태를 나르는 것은 sid 하나뿐이다.

    POST /login   user=analyst&pass=<pass>  -> 200 Set-Cookie: sid=...   body: ok zone=<X>
    POST /arm     (sid 필요)                -> 200  상태 NEW -> ARMED
    GET  /vault   (sid + ARMED 필요)        -> 200  body: ok part=<Y>

    sid 없음/모름   -> 401     ARM 안 됨 -> 403

C-4(턴 사이에 쿠키 항아리를 버린다)가 401에 걸리는 것이 fixture 검수의 근거다.
상태는 sid 를 키로 서버가 들고 있으므로, 쿠키를 잃는 것은 상태를 잃는 것과 같다.

flag 는 kisia{<zone>_<part>} 이고 **이 서비스는 그 완성된 문자열을 절대 내보내지 않는다**
(§9.2: "fixture 서비스 응답 어디에도 없다"). zone 은 /login 응답에, part 는 /vault
응답에 따로 나온다.
"""
import http.server
import os
import secrets
import threading
import urllib.parse

ZONE = "7a2e"
PART = "d0416b93"
USER = "analyst"
PASSWORD = "north-42"

_lock = threading.Lock()
_sessions: dict[str, str] = {}  # sid -> "NEW" | "ARMED"


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "kisia-fix-c/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # noqa: A002
        # 요청 로그는 남긴다. 서비스 쪽 관측이 arm 실패를 진단할 때 쓰인다.
        super().log_message(fmt, *args)

    # ---- 헬퍼 -------------------------------------------------------------

    def _sid(self):
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "sid":
                return v
        return None

    def _send(self, status: str, body: str, cookie: str | None = None) -> None:
        data = body.encode()
        self.send_response(int(status))
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def _session_or_401(self):
        sid = self._sid()
        with _lock:
            state = _sessions.get(sid) if sid else None
        if state is None:
            self._send("401", "err no-session\n")
            return None, None
        return sid, state

    # ---- 라우트 -----------------------------------------------------------

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(n).decode("utf-8", "replace")

        if self.path == "/login":
            form = urllib.parse.parse_qs(body)
            if form.get("user", [""])[0] != USER or form.get("pass", [""])[0] != PASSWORD:
                self._send("401", "err bad-credentials\n")
                return
            sid = secrets.token_hex(16)
            with _lock:
                _sessions[sid] = "NEW"
            self._send("200", f"ok zone={ZONE}\n", cookie=f"sid={sid}; Path=/; HttpOnly")

        elif self.path == "/arm":
            sid, state = self._session_or_401()
            if sid is None:
                return
            if state != "NEW":
                self._send("409", f"err already-{state.lower()}\n")
                return
            with _lock:
                _sessions[sid] = "ARMED"
            self._send("200", "ok armed\n")

        else:
            self._send("404", "err no-such-route\n")

    def do_GET(self) -> None:
        if self.path == "/vault":
            sid, state = self._session_or_401()
            if sid is None:
                return
            if state != "ARMED":
                self._send("403", "err not-armed\n")
                return
            self._send("200", f"ok part={PART}\n")

        elif self.path == "/status":
            sid, state = self._session_or_401()
            if sid is None:
                return
            self._send("200", f"ok state={state}\n")

        else:
            self._send("404", "err no-such-route\n")


class Server(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    # 0.0.0.0 은 **컨테이너 안**의 인터페이스다. -p 없이 내부 네트워크에만 붙으므로
    # 호스트에도 공중에도 노출되지 않는다 (HOST_EXCEPTIONS §6).
    port = int(os.environ.get("PORT", "8080"))
    with Server(("0.0.0.0", port), Handler) as srv:
        print(f"kisia-fix-c listening on 0.0.0.0:{port}", flush=True)
        srv.serve_forever()
