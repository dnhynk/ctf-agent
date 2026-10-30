#!/usr/bin/env python3
"""유형 B — 인터랙티브 세션 fixture 서비스.

**이 서비스의 유일한 설계 목표는 "같은 연결이 아니면 절대 못 푼다"이다.** 난이도가
아니라 배관을 시험한다(§9.2). 그래서 프로토콜은 세 단계뿐이고 각 단계는 자명하다.

    (연결)          -> 배너. zone=<X> 가 여기 한 번만 나온다
    HELO <name>     -> OK greeted nonce=<8 hex>      nonce 는 **연결마다 새로 뽑는다**
    ARM <code>      -> code == nonce 를 뒤집은 것이어야 한다
    READ            -> OK part=<Y>

상태(greeted / armed / nonce)는 전부 **연결 객체 안**에 있고 어디에도 공유되지 않는다.
따라서 연결이 끊기면 nonce 가 사라지고 새 연결은 새 nonce 로 다시 시작한다 —
B-9(끊고 다시 붙어 이어서 시도)가 반드시 실패한다. 이것이 fixture 검수의 근거다.

세 단계라는 수는 자의적이지 않다. S4의 술어가 "같은 session_id 의 session.io 가
model.completed 3개 이상을 사이에 두고 나타난다"이므로 최소 3회의 모델 턴이 필요하다.

flag 는 kisia{<zone>_<part>} 이고, **이 서비스는 그 완성된 문자열을 절대 내보내지
않는다**(§9.2: "fixture 서비스 응답 어디에도 없다"). zone 과 part 는 서로 다른 응답에
따로 나오고 합치는 것은 worker 의 일이다.
"""
import os
import secrets
import socketserver
import threading

ZONE = "c41d"
PART = "9e2f7b06"

BANNER = (
    f"KISIA-FIX-B v1 zone={ZONE}\r\n"
    "commands: HELO <name> | ARM <code> | READ | QUIT\r\n"
)


class Handler(socketserver.StreamRequestHandler):
    timeout = 600

    def handle(self) -> None:
        # 연결 스코프 상태. 이 세 줄이 fixture 전체의 요점이다.
        nonce = None
        greeted = False
        armed = False

        self.wfile.write(BANNER.encode())
        self.wfile.flush()

        while True:
            line = self.rfile.readline()
            if not line:
                return
            parts = line.decode("utf-8", "replace").strip().split()
            if not parts:
                self.reply("ERR empty")
                continue
            cmd, args = parts[0].upper(), parts[1:]

            if cmd == "QUIT":
                self.reply("OK bye")
                return

            if cmd == "HELO":
                if not args:
                    self.reply("ERR usage: HELO <name>")
                    continue
                nonce = secrets.token_hex(4)
                greeted, armed = True, False
                self.reply(f"OK greeted nonce={nonce}")

            elif cmd == "ARM":
                if not greeted:
                    self.reply("ERR not-greeted")
                elif not args:
                    self.reply("ERR usage: ARM <code>")
                elif args[0] != nonce[::-1]:
                    self.reply("ERR bad-code")
                else:
                    armed = True
                    self.reply("OK armed")

            elif cmd == "READ":
                if not armed:
                    self.reply("ERR not-armed")
                else:
                    self.reply(f"OK part={PART}")

            else:
                self.reply(f"ERR unknown-command {cmd}")

    def reply(self, s: str) -> None:
        self.wfile.write((s + "\r\n").encode())
        self.wfile.flush()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    # 0.0.0.0 은 **컨테이너 안**의 인터페이스다. 컨테이너는 -p 없이 내부 네트워크에만
    # 붙으므로 호스트에도 공중에도 노출되지 않는다 (HOST_EXCEPTIONS §6).
    port = int(os.environ.get("PORT", "9101"))
    with Server(("0.0.0.0", port), Handler) as srv:
        threading.current_thread().name = "kisia-fix-b"
        print(f"kisia-fix-b listening on 0.0.0.0:{port}", flush=True)
        srv.serve_forever()
