#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G — `SEAM_CONTRACT.md` §4 `InteractiveSession` 의 참조 구현.

이것은 전체 러너가 아니다(`FOUNDATION_DECISION.md` §7.2·§9.1). agent loop 도, 후보 코드도,
모델 호출도 없다. §4 의 6개 연산과 §4.1 의 네 요구, §4.2 의 동시성이 전부다.

두 가지 세션 종류를 **서로 다른 전송 계층**으로 구현한다. 그래야 §4.1-1(newline 이 세션
종류와 무관하게 지켜진다)이 시험 대상이 된다 — 같은 전송을 두 이름으로 부르면 그 술어는
공허하게 참이 된다.

  pty     호스트 pty + `docker exec -i -t <worker> bash -i`  (컨테이너 안에 tty, job control)
  socket  호스트 TCP 소켓                                     (tty 없음, 시그널 없음)

§4.1 의 네 요구에 대한 구현 위치:
  1 newline   `Session.send` 한 곳에서만 붙인다. 전송 계층은 바이트를 받을 뿐이다.
  2 생존자 0  정리 경계는 프로세스 그룹이 아니라 **커널 세션(sid)** 이다 [ev §8.1].
  3 좀비      `survivors` 는 state 'Z' 를 세지 않는다 [ev §8.2].
  4 live      컨테이너 프로세스 표로 정한다. waitpid 상태값으로 추론하지 않는다 [ev §8.3].
"""

import ast
import errno
import os
import pty
import select
import signal
import socket
import subprocess
import time

# 컨테이너 안에서 /proc 을 읽어 프로세스 표를 뜬다. procps 에 기대지 않는다.
_PROC_SNIPPET = r"""
import os,sys
out=[]
for d in os.listdir('/proc'):
    if not d.isdigit(): continue
    try:
        s=open('/proc/%s/stat'%d).read()
    except Exception: continue
    try:
        l=s.rindex(')')
        comm=s[s.index('(')+1:l]
        r=s[l+2:].split()
        out.append((int(d),comm,r[0],int(r[1]),int(r[2]),int(r[3])))
    except Exception: pass
sys.stdout.write(repr(out))
"""


class ScopeRefused(Exception):
    """상한 초과·미지 세션 등. **거부**이지 대기가 아니다 (§4.2)."""

    def __init__(self, reason_code, detail=""):
        Exception.__init__(self, "%s: %s" % (reason_code, detail))
        self.reason_code = reason_code
        self.detail = detail


# --------------------------------------------------------------------------
# 컨테이너 프로세스 표 — 후보 밖에서 보는 관측 (§0.1-3)
# --------------------------------------------------------------------------

class ContainerProbe(object):
    def __init__(self, container):
        self.container = container

    def table(self):
        """[(pid, comm, state, ppid, pgrp, sid), ...] — 컨테이너의 pid namespace 기준."""
        p = subprocess.Popen(
            ["docker", "exec", self.container, "python3", "-c", _PROC_SNIPPET],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _err = p.communicate(timeout=30)
        try:
            return ast.literal_eval(out.decode("utf-8", "replace").strip() or "[]")
        except (ValueError, SyntaxError):
            return []

    def kill(self, pids, sig):
        if not pids:
            return
        subprocess.call(["docker", "exec", self.container, "kill",
                         "-%d" % sig] + [str(p) for p in pids],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --------------------------------------------------------------------------
# 전송 계층 — 두 종류가 정말로 다른 코드 경로여야 한다
# --------------------------------------------------------------------------

class PtyTransport(object):
    kind = "pty"
    supports_signal = True

    def __init__(self, container, command, cwd, env, term):
        self.master, slave = pty.openpty()
        argv = ["docker", "exec", "-i", "-t"]
        if cwd:
            argv += ["-w", cwd]
        for k, v in (env or {}).items():
            argv += ["-e", "%s=%s" % (k, v)]
        argv += ["-e", "TERM=%s" % (term or "xterm")]
        argv += [container] + list(command)
        self.proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave,
                                     close_fds=True)
        os.close(slave)
        self.reaped = None          # (waitpid 가 돌려준 pid, status)

    def write(self, data):
        os.write(self.master, data)

    def read_some(self, timeout_s, max_bytes):
        r, _w, _x = select.select([self.master], [], [], timeout_s)
        if not r:
            return b"", False
        try:
            chunk = os.read(self.master, max_bytes)
        except OSError as exc:
            if exc.errno in (errno.EIO, errno.EBADF):
                return b"", True
            raise
        return chunk, (chunk == b"")

    def send_signal_via_tty(self, sig):
        """tty 를 통해 보낸다 — 포그라운드 잡에 전달되는 것이 tty 의 의미론이다."""
        if sig == signal.SIGINT:
            self.write(b"\x03")
        elif sig == signal.SIGQUIT:
            self.write(b"\x1c")
        else:
            self.proc.send_signal(sig)

    def naive_waitpid(self):
        """[ev §8.3] 을 그대로 재현하는 관측용 호출.

        살아 있는 자식에 대해서도 status 0 을 돌려준다. `live` 를 이 값으로 정하면
        "정상 종료" 와 "아직 살아 있음" 이 같은 값이 된다.
        """
        if self.reaped is not None:
            return self.reaped
        try:
            pid, status = os.waitpid(self.proc.pid, os.WNOHANG)
        except OSError:
            return (-1, -1)
        if pid != 0:
            self.reaped = (pid, status)
            self.proc.returncode = status  # Popen 이 다시 거두지 않게 한다
        return (pid, status)

    def close_transport(self):
        try:
            os.close(self.master)
        except OSError:
            pass
        if self.reaped is None:
            try:
                self.proc.kill()
            except OSError:
                pass
            try:
                pid, status = os.waitpid(self.proc.pid, 0)
                self.reaped = (pid, status)
                self.proc.returncode = status
            except OSError:
                pass
        return self.reaped[1] if self.reaped else None


class SocketTransport(object):
    kind = "socket"
    supports_signal = False

    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=10)
        self.sock.setblocking(False)
        self.closed = False

    def write(self, data):
        self.sock.setblocking(True)
        try:
            self.sock.sendall(data)
        finally:
            self.sock.setblocking(False)

    def read_some(self, timeout_s, max_bytes):
        r, _w, _x = select.select([self.sock], [], [], timeout_s)
        if not r:
            return b"", False
        chunk = self.sock.recv(max_bytes)
        if chunk == b"":
            self.closed = True
            return b"", True
        return chunk, False

    def naive_waitpid(self):
        return (None, None)

    def close_transport(self):
        try:
            self.sock.close()
        except OSError:
            pass
        return 0


# --------------------------------------------------------------------------
# 세션
# --------------------------------------------------------------------------

class Session(object):
    def __init__(self, sid, transport, probe=None):
        self.sid = sid
        self.transport = transport
        self.probe = probe
        self.seq = 0
        self.buf = b""              # 세션마다 따로. 두 세션의 read 가 섞이지 않는다 (§4.2)
        self.transcript = b""
        self.bytes_since_open = 0
        self.leader_pid = None      # 컨테이너 안의 세션 리더 pid
        self.leader_sid = None      # 그 리더의 커널 세션 id — 정리의 경계
        self.leader_pgid = None
        self.opened_at = time.time()
        self.closed = False

    # -- §4 의 6개 연산 --------------------------------------------------
    def send(self, data, newline=True):
        """§4.1-1: newline 은 **여기 한 곳에서만** 붙는다.

        전송 계층은 바이트열을 받을 뿐이고 개행에 대해 아무것도 모른다. pty 에서는
        지켜지고 소켓에서는 조용히 무시되는 경로가 존재할 수 없다 [ev §8.5].
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        payload = data + b"\n" if newline else data
        self.transport.write(payload)
        self.seq += 1
        self.transcript += b"<<< " + payload + b"\n"
        return self.seq

    def read(self, timeout_ms=2000, max_bytes=65536, quiet_ms=250):
        """조용해질 때까지 모아 읽는다. 반환은 (bytes, closed, timed_out)."""
        deadline = time.time() + timeout_ms / 1000.0
        got = b""
        closed = False
        last = time.time()
        while time.time() < deadline and len(got) < max_bytes:
            chunk, eof = self.transport.read_some(0.05, max_bytes - len(got))
            if chunk:
                got += chunk
                last = time.time()
            if eof:
                closed = True
                break
            if got and (time.time() - last) * 1000 >= quiet_ms:
                break
        timed_out = (not got) and not closed
        self.bytes_since_open += len(got)
        self.transcript += b">>> " + got + b"\n"
        return got, closed, timed_out

    def interrupt(self, sig=signal.SIGINT):
        if not self.transport.supports_signal:
            raise ScopeRefused("interrupt_unsupported",
                               "세션 종류 %s 에는 시그널 경로가 없다. 조용히 무시하지 않는다"
                               % self.transport.kind)
        self.transport.send_signal_via_tty(sig)
        self.seq += 1
        return self.seq

    def snapshot(self):
        """§4.1-4: `live` 를 waitpid 상태값으로 추론하지 않는다.

        `naive` 는 [ev §8.3] 이 발견한 잘못된 추론을 **관측으로 남기기 위해** 함께 잰다:
        살아 있는 자식에 대해서도 (0, 0) 이므로 status 만 보면 "정상 종료(0)" 로 읽힌다.
        """
        naive_pid, naive_status = self.transport.naive_waitpid()
        live = None
        state = None
        if self.probe is not None and self.leader_pid is not None:
            row = [r for r in self.probe.table() if r[0] == self.leader_pid]
            state = row[0][2] if row else None
            live = bool(row) and state != "Z"
        elif self.transport.kind == "socket":
            live = not getattr(self.transport, "closed", False)
        return {
            "session_id": self.sid, "live": live, "pid": self.leader_pid,
            "seq_high": self.seq, "bytes_since_open": self.bytes_since_open,
            "container_state": state,
            "naive_waitpid_pid": naive_pid, "naive_waitpid_status": naive_status,
            "naive_live_from_status_only":
                (None if naive_status is None else (naive_status != 0)),
        }

    def close(self, grace_ms=2000):
        """§4.1-2·3: 커널 세션을 경계로 정리하고, 좀비는 생존자로 세지 않는다."""
        t0 = time.time()
        result = {
            "session_id": self.sid, "grace_ms": grace_ms,
            "descendants_killed": 0, "survivors": [], "zombies_excluded": [],
            "pgid_only_would_have_killed": None,
            "grace_used_ms": 0, "grace_used_if_zombies_counted_ms": None,
            "exit_status": None,
        }
        if self.probe is not None and self.leader_sid is not None:
            table = self.probe.table()
            in_session = [r for r in table if r[5] == self.leader_sid]
            in_pgroup = [r for r in in_session if r[4] == self.leader_pgid]
            # [ev §8.1] 프로세스 그룹만 정리하면 tty job control 아래 `&` 로 띄운 잡은
            # 자기 pgid 를 갖게 되어 남는다. 그 차이를 관측으로 남긴다.
            result["pgid_only_would_have_killed"] = sorted(r[0] for r in in_pgroup)
            result["session_members_at_close"] = sorted(
                (r[0], r[1], r[2], r[4]) for r in in_session)
            result["descendants_killed"] = len(
                [r for r in in_session if r[0] != self.leader_pid and r[2] != "Z"])

            self.probe.kill([r[0] for r in in_session], signal.SIGTERM)
            all_clear_at = None
            correct_clear_at = None
            deadline = t0 + grace_ms / 1000.0
            while time.time() < deadline:
                time.sleep(0.05)
                now = [r for r in self.probe.table() if r[5] == self.leader_sid]
                correct = [r for r in now if r[2] != "Z"]
                if all_clear_at is None and not now:
                    all_clear_at = time.time()
                if correct_clear_at is None and not correct:
                    correct_clear_at = time.time()
                    # 정리는 여기서 끝났다. 좀비를 생존자로 세는 구현만이 계속 돈다.
                    break
            if correct_clear_at is None:
                self.probe.kill([r[0] for r in self.probe.table()
                                 if r[5] == self.leader_sid], signal.SIGKILL)
                time.sleep(0.1)
            result["grace_used_ms"] = int((time.time() - t0) * 1000)
            final = [r for r in self.probe.table() if r[5] == self.leader_sid]
            result["survivors"] = sorted(r[0] for r in final if r[2] != "Z")
            result["zombies_excluded"] = sorted(r[0] for r in final if r[2] == "Z")
            if result["zombies_excluded"] and all_clear_at is None:
                # [ev §8.2]: 좀비를 생존자로 세면 정리가 끝난 뒤에도 생존자 집합이 비지
                # 않아 매 close 마다 grace 를 전부 쓴다. 여기서 그 값이 곧 grace 전량이다.
                result["grace_used_if_zombies_counted_ms"] = grace_ms

        result["exit_status"] = self.transport.close_transport()
        if result["survivors"]:
            # 전송이 끊긴 뒤 다시 본다 — 컨테이너 exec 이 사라지면 세션도 사라진다.
            time.sleep(0.2)
            if self.probe is not None and self.leader_sid is not None:
                final = [r for r in self.probe.table() if r[5] == self.leader_sid]
                result["survivors"] = sorted(r[0] for r in final if r[2] != "Z")
                result["zombies_excluded"] = sorted(r[0] for r in final if r[2] == "Z")
        self.closed = True
        return result


class SessionManager(object):
    """§4.2 동시성.

    상한은 명시적이고, 초과는 **거부**이며 대기가 아니다. 두 세션의 read 가 서로의
    바이트를 섞지 않는 것은 세션마다 버퍼와 전송이 따로이기 때문이다.
    """

    def __init__(self, container=None, max_sessions=4):
        self.container = container
        self.max_sessions = max_sessions
        self.sessions = {}
        self.closed_ids = set()
        self._n = 0
        self.probe = ContainerProbe(container) if container else None

    def open(self, kind, command=None, cwd=None, env=None, term="xterm",
             host=None, port=None):
        if len(self.sessions) >= self.max_sessions:
            raise ScopeRefused("session_limit",
                               "동시 세션 상한 %d 초과. 대기하지 않고 거부한다"
                               % self.max_sessions)
        self._n += 1
        sid = "gsess-%02d" % self._n
        if kind == "pty":
            # 리더 pid 는 **세션 안에 아무것도 쓰지 않고** 밖에서 확정한다.
            # 세션에 부트스트랩 명령을 흘려 넣으면 그 바이트가 전사와 관찰에 섞여
            # B-2(같은 바이트열을 두 종류에 보내고 상대가 받은 것을 비교)가 오염된다.
            before = {r[0] for r in self.probe.table()} if self.probe else set()
            tr = PtyTransport(self.container, command or ["/bin/bash", "-i"],
                              cwd, env, term)
            s = Session(sid, tr, self.probe)
            self.sessions[sid] = s
            if self.probe is not None:
                deadline = time.time() + 5.0
                while time.time() < deadline:
                    time.sleep(0.12)
                    table = self.probe.table()
                    new = [r for r in table if r[0] not in before]
                    leaders = [r for r in new if r[0] == r[5]]
                    pick = min(leaders or new, key=lambda r: r[0]) if (leaders or new) \
                        else None
                    if pick is not None:
                        s.leader_pid, s.leader_pgid, s.leader_sid = pick[0], pick[4], pick[5]
                        break
            banner, _c, _t = s.read(timeout_ms=1200, quiet_ms=300)
            return s, banner
        if kind == "socket":
            tr = SocketTransport(host, port)
            s = Session(sid, tr, None)
            self.sessions[sid] = s
            banner, _c, _t = s.read(timeout_ms=2500, quiet_ms=300)
            return s, banner
        raise ScopeRefused("unknown_session_kind", kind)

    def get(self, sid):
        """§S6: 죽은 세션을 참조하면 **거부**한다. 조용히 새 세션을 만들지 않는다."""
        if sid in self.sessions:
            return self.sessions[sid]
        raise ScopeRefused("unknown_session",
                           "%s 는 live 집합에 없다 (닫힘: %s)"
                           % (sid, sid in self.closed_ids))

    def close(self, sid, grace_ms=2000):
        s = self.get(sid)
        r = s.close(grace_ms)
        del self.sessions[sid]
        self.closed_ids.add(sid)
        return r

    def live_ids(self):
        return sorted(self.sessions)
