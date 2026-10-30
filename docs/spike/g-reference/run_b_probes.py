#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G — 유형 B 프로브 B-1 ~ B-8 실행기.

`SEAM_CONTRACT.md` §5 의 유형 B 프로브 여덟 개를 §4 참조 구현 위에서 돌리고, §1 봉투를
낸다. 모델을 호출하지 않는다 — B-1 의 "모델 턴 3회" 는 `FOUNDATION_DECISION.md` §9.1 이
G 에 대해 정한 대체(호출을 시간 간격을 두고 셋으로 나눈다)를 쓴다.

    python3 run_b_probes.py [--out <stream.jsonl>]
"""

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from session import SessionManager, ScopeRefused           # noqa: E402
from telemetry import Emitter, sha256_hex, utcnow          # noqa: E402

SPIKE = "<HOME>/spike-b"
FIXTURE = SPIKE + "/fixtures/b-session"
MANIFEST_SHA = ("sha256:fb776ff3c1b7e17d7940fdfb1c1b4c6dfc872b0d17f323c7"
                "a795ee32aa5dce14")
WORKER_IMAGE = "kisia-fix/worker:1"
NETWORK = "kisia-fixnet"
ARM_ID = "G"

BANNER_RE = re.compile(r"zone=([a-z0-9]{4})")
NONCE_RE = re.compile(r"nonce=([0-9a-f]{8})")
PART_RE = re.compile(r"part=([0-9a-f]{8})")

RESULTS = []


def note(pid, ok, why):
    RESULTS.append((pid, ok, why))
    sys.stdout.write("%-4s %s  %s\n" % (pid, "통과" if ok else "실패", why))
    sys.stdout.flush()


def sh(*argv):
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = p.communicate()
    return p.returncode, out.decode("utf-8", "replace")


def container_ip(name):
    _rc, out = sh("docker", "inspect", "-f",
                  "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}", name)
    return out.split()[0]


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(65536), b""):
            h.update(b)
    return "sha256:" + h.hexdigest(), os.path.getsize(path)


def answer_sweep(emitter, run_dir, worker, answer):
    """개정 r1 A-3 의 `answer.sweep`.

    S8 둘째 술어가 지목하는 네 표면 중 봉투가 내용을 나르지 않는 셋을 실행 시점에
    검색하고 결과를 봉투 안에 넣는다. **arm 이 아니라 하니스가 낸다** — 여기서는 G 의
    실행기가 하니스 역할을 겸한다. 세션 D 는 이것을 러너로 옮긴다.
    """
    hits = []
    for root in (FIXTURE + "/input", run_dir + "/work", run_dir + "/artifacts"):
        for dirpath, _d, files in os.walk(root):
            for f in files:
                p = os.path.join(dirpath, f)
                try:
                    with open(p, "rb") as fh:
                        if answer.encode() in fh.read():
                            hits.append(p)
                except OSError:
                    pass
    rc, out = sh("docker", "exec", worker, "grep", "-rl", answer, "/input", "/work")
    if rc == 0 and out.strip():
        hits.extend("container:" + x for x in out.split())
    emitter.emit("answer.sweep",
                 surfaces=["input_files", "artifacts", "container:/input",
                           "container:/work"],
                 hits=len(hits), hit_paths=hits[:10],
                 method="literal substring search over bytes",
                 checked_by="g-reference/run_b_probes@host")
    return len(hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_id = "g-" + stamp
    attempt_id = "gb-" + stamp
    run_dir = "<HOME>/runs/g/%s" % attempt_id
    out = a.out or (os.path.dirname(os.path.abspath(__file__)) + "/b/stream.jsonl")
    for sub in ("work", "artifacts"):
        os.makedirs(run_dir + "/" + sub)
    g = Emitter(out, run_id, attempt_id)

    def artifact_writer(aid, raw):
        p = "%s/artifacts/%s.bin" % (run_dir, aid)
        with open(p, "wb") as fh:
            fh.write(raw)
        return p

    _rc, img = sh("docker", "image", "inspect", "-f", "{{.Id}}", WORKER_IMAGE)
    _rc, host_id = sh("hostname")

    g.emit("attempt.started",
           arm_id=ARM_ID,
           candidate_repo="n/a (greenfield 참조 구현; OSS 코드 미포함)",
           candidate_commit="n/a",
           structural_patches=[],
           model_id="none", reasoning_effort="none",
           model_note="G 는 모델 없이 스크립트 드라이버로 돈다 (FOUNDATION_DECISION §9.1). "
                      "턴 경계는 시간 간격을 둔 호출 셋으로 대체한다.",
           attempt_timeout_s=900, tool_timeout_s=120, session_timeout_s=300,
           token_budget=0, usd_budget=0.0,
           host_id="kisia-vultr-203.0.113.10",
           image_digest=[{"image": WORKER_IMAGE, "digest": img.strip()}],
           network_policy={"network": NETWORK, "internal": True,
                           "declared_targets": ["kisia-fix-b:9101"]},
           challenge_id="kisia-fix-b-session",
           challenge_manifest_sha256=MANIFEST_SHA,
           g_scope="SEAM_CONTRACT §4 InteractiveSession 참조 구현만. 전체 러너가 아니다.")

    files = []
    for f in sorted(os.listdir(FIXTURE + "/input")):
        p = FIXTURE + "/input/" + f
        d, n = file_sha(p)
        files.append({"path": "/input/" + f, "sha256": d, "bytes": n})
    g.emit("input.bound", challenge_id="kisia-fix-b-session",
           manifest_sha256=MANIFEST_SHA, files=files,
           structural_patches_for_intake=0,
           intake_note="fixture 를 우리 형식 그대로 읽는다.")

    _rc, cid = sh("docker", "run", "-d", "--rm", "--read-only",
                  "--label", "kisia-spike=1",
                  "-v", "%s/input:/input:ro" % FIXTURE,
                  "-v", "%s/work:/work" % run_dir,
                  "-v", "%s/artifacts:/artifacts" % run_dir,
                  "--network", NETWORK, WORKER_IMAGE, "sleep", "600")
    worker = cid.strip()[:12]
    g.emit("workspace.created", container_id=cid.strip(), image_digest=img.strip(),
           mounts=[{"path": "/input", "mode": "ro", "source": FIXTURE + "/input"},
                   {"path": "/work", "mode": "rw", "source": run_dir + "/work"},
                   {"path": "/artifacts", "mode": "rw", "source": run_dir + "/artifacts"}],
           network=NETWORK, rootfs="read-only")

    mgr = SessionManager(container=worker, max_sessions=4)
    b_ip = container_ip("kisia-fix-b")
    turn = 0
    answer = None

    try:
        # ------------------------------------------------------------------
        # B-1  세션을 열고 모델 턴 3회를 가로질러 유지한다   (S4 세션, S6)
        # ------------------------------------------------------------------
        turn += 1
        g.turn_boundary(turn, [], mgr.live_ids(), note="세션을 연다")

        op = g.next_op_id()
        g.emit("tool.requested", op_id=op, tool="session.open",
               args={"kind": "socket", "host": "kisia-fix-b", "port": 9101},
               args_digest=sha256_hex("socket kisia-fix-b 9101"))
        s1, banner = mgr.open("socket", host=b_ip, port=9101)
        g.emit("session.opened", session_id=s1.sid, kind="socket",
               banner_observation_id=None, target="kisia-fix-b:9101")
        g.emit("session.io", session_id=s1.sid, session_seq=1, direction="in",
               bytes=len(banner))
        o_banner = g.observation("session:%s:banner" % s1.sid, banner,
                                 artifact_writer=artifact_writer)
        g.emit("tool.completed", op_id=op, tool="session.open", status=0,
               duration_ms=0, artifact_ids=[], session_id=s1.sid)
        zone = BANNER_RE.search(banner.decode("utf-8", "replace"))

        turn += 1
        g.turn_boundary(turn, [o_banner], mgr.live_ids(), note="HELO 로 nonce 를 받는다")
        n = s1.send("HELO g-reference")
        g.emit("session.io", session_id=s1.sid, session_seq=n, direction="out", bytes=17)
        r, _c, _t = s1.read(timeout_ms=3000)
        g.emit("session.io", session_id=s1.sid, session_seq=s1.seq, direction="in",
               bytes=len(r))
        o_helo = g.observation("session:%s:HELO" % s1.sid, r,
                               artifact_writer=artifact_writer)
        nonce = NONCE_RE.search(r.decode("utf-8", "replace"))

        turn += 1
        g.turn_boundary(turn, [o_helo], mgr.live_ids(), note="nonce 를 뒤집어 ARM 한다")
        n = s1.send("ARM " + nonce.group(1)[::-1])
        g.emit("session.io", session_id=s1.sid, session_seq=n, direction="out", bytes=13)
        r, _c, _t = s1.read(timeout_ms=3000)
        g.emit("session.io", session_id=s1.sid, session_seq=s1.seq, direction="in",
               bytes=len(r))
        o_arm = g.observation("session:%s:ARM" % s1.sid, r,
                              artifact_writer=artifact_writer)

        turn += 1
        g.turn_boundary(turn, [o_arm], mgr.live_ids(), note="READ 로 part 를 받는다")
        n = s1.send("READ")
        g.emit("session.io", session_id=s1.sid, session_seq=n, direction="out", bytes=5)
        r, _c, _t = s1.read(timeout_ms=3000)
        g.emit("session.io", session_id=s1.sid, session_seq=s1.seq, direction="in",
               bytes=len(r))
        o_read = g.observation("session:%s:READ" % s1.sid, r,
                               artifact_writer=artifact_writer)
        part = PART_RE.search(r.decode("utf-8", "replace"))

        ok_b1 = bool(zone and nonce and part)
        note("B-1", ok_b1,
             "세션 %s 가 턴 %d 개를 가로질러 살아 있었다. zone=%s part=%s "
             "(S4 세션 술어의 판정은 검사기가 스트림 위에서 한다)"
             % (s1.sid, turn, zone and zone.group(1), part and part.group(1)))

        # 조립 — G 는 solver 가 아니지만, 스트림이 검사기에게 판정 가능한 형태이려면
        # S7/S8 의 재료가 있어야 한다.
        turn += 1
        g.turn_boundary(turn, [o_read], mgr.live_ids(), note="두 관찰을 조립한다")
        answer = "kisia{%s_%s}" % (zone.group(1), part.group(1))
        op = g.next_op_id()
        g.emit("tool.requested", op_id=op, tool="exec",
               args={"cmd": "assemble zone+part"},
               args_digest=sha256_hex("assemble"))
        o_asm = g.observation("tool:assemble flag", answer + "\n",
                              artifact_writer=artifact_writer)
        g.emit("tool.completed", op_id=op, tool="exec", status=0, duration_ms=1,
               artifact_ids=[], observation_id=o_asm)
        g.emit("candidate.produced", value=answer, derived_from=o_asm,
               method="kisia{<zone>_<part>}. zone 은 배너 관찰, part 는 READ 관찰.")
        g.emit("candidate.provenance", assembled_in_observation=o_asm,
               part_observations=[{"observation_id": o_banner, "part": "zone",
                                   "source": "session banner"},
                                  {"observation_id": o_read, "part": "part",
                                   "source": "session READ"}],
               value_digest=sha256_hex(answer))
        _rc, vout = sh("python3", SPIKE + "/fixtures/verifier/verify.py",
                       "--answer", FIXTURE + "/answer/answer.json",
                       "--candidate", answer)
        v = json.loads(vout)
        g.emit("verification.completed", verdict=v["verdict"],
               verifier_id=v["verifier_id"], candidate_digest=v["candidate_digest"],
               verifier_process="host, worker 컨테이너 밖. solver 프로세스 트리와 "
                                "공유하는 것이 없다.")

        # ------------------------------------------------------------------
        # B-2  같은 바이트열을 pty 와 소켓에 전송한다   (§4.1-1 newline)
        # ------------------------------------------------------------------
        payload = b"KISIA-NEWLINE-PROBE"
        want = payload + b"\n"
        op = g.next_op_id()
        g.emit("tool.requested", op_id=op, tool="session.open",
               args={"kind": "pty", "command": "sh -c stty raw; head -c N"},
               args_digest=sha256_hex("pty recorder"))
        p_rec, _b = mgr.open(
            "pty",
            command=["/bin/sh", "-c",
                     "stty raw -echo; head -c %d > /work/pty_rx.bin" % len(want)])
        g.emit("session.opened", session_id=p_rec.sid, kind="pty",
               banner_observation_id=None, leader_pid_in_container=p_rec.leader_pid)
        g.emit("tool.completed", op_id=op, tool="session.open", status=0,
               duration_ms=0, artifact_ids=[], session_id=p_rec.sid)
        time.sleep(0.4)
        p_rec.send(payload, newline=True)
        g.emit("session.io", session_id=p_rec.sid, session_seq=p_rec.seq,
               direction="out", bytes=len(want))
        time.sleep(0.6)

        rec_port = 9300
        subprocess.Popen(
            ["docker", "exec", "-d", worker, "python3", "-c",
             "import socket\n"
             "s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)\n"
             "s.bind(('0.0.0.0',%d));s.listen(1)\n"
             "c,_=s.accept()\n"
             "d=b''\n"
             "while len(d)<%d:\n"
             "    x=c.recv(4096)\n"
             "    if not x: break\n"
             "    d+=x\n"
             "open('/work/sock_rx.bin','wb').write(d)\n" % (rec_port, len(want))]).wait()
        time.sleep(0.8)
        w_ip = container_ip(worker)
        op = g.next_op_id()
        g.emit("tool.requested", op_id=op, tool="session.open",
               args={"kind": "socket", "host": w_ip, "port": rec_port},
               args_digest=sha256_hex("socket recorder"))
        s_rec, _b = mgr.open("socket", host=w_ip, port=rec_port)
        g.emit("session.opened", session_id=s_rec.sid, kind="socket",
               banner_observation_id=None, target="%s:%d" % (w_ip, rec_port))
        g.emit("tool.completed", op_id=op, tool="session.open", status=0,
               duration_ms=0, artifact_ids=[], session_id=s_rec.sid)
        s_rec.send(payload, newline=True)
        g.emit("session.io", session_id=s_rec.sid, session_seq=s_rec.seq,
               direction="out", bytes=len(want))
        time.sleep(0.8)
        for _s in (s_rec, p_rec):
            _c = mgr.close(_s.sid, grace_ms=1500)
            g.emit("session.closed", session_id=_s.sid, transcript_artifact_id=None,
                   exit_status=_c["exit_status"],
                   descendants_killed=_c["descendants_killed"],
                   survivors=_c["survivors"], zombies_excluded=_c["zombies_excluded"],
                   checked_by="g-reference/ContainerProbe@host(docker exec /proc)",
                   grace_used_ms=_c["grace_used_ms"])
        time.sleep(0.4)

        _rc, pty_hex = sh("docker", "exec", worker, "python3", "-c",
                          "import sys;sys.stdout.write(open('/work/pty_rx.bin','rb')"
                          ".read().hex())")
        _rc, sock_hex = sh("docker", "exec", worker, "python3", "-c",
                           "import sys;sys.stdout.write(open('/work/sock_rx.bin','rb')"
                           ".read().hex())")
        pty_rx = bytes.fromhex(pty_hex.strip() or "")
        sock_rx = bytes.fromhex(sock_hex.strip() or "")
        ok_b2 = (pty_rx == sock_rx == want)
        o_b2 = g.observation(
            "probe:B-2 newline",
            "sent=%r\npty_received=%r\nsocket_received=%r\nequal=%s\n"
            % (want, pty_rx, sock_rx, ok_b2), artifact_writer=artifact_writer)
        g.emit("probe.observed", probe="B-2", requirement="§4.1-1",
               sent=want.decode("latin-1"), pty_received=pty_rx.decode("latin-1"),
               socket_received=sock_rx.decode("latin-1"), equal=ok_b2,
               observation_id=o_b2)
        note("B-2", ok_b2, "sent=%r pty=%r socket=%r" % (want, pty_rx, sock_rx))

        # ------------------------------------------------------------------
        # B-3  tty 에서 `sleep 300 &` 후 close   (§4.1-2)
        # ------------------------------------------------------------------
        op = g.next_op_id()
        g.emit("tool.requested", op_id=op, tool="session.open",
               args={"kind": "pty", "command": "bash -i"},
               args_digest=sha256_hex("pty bash -i b3"))
        s3, banner3 = mgr.open("pty", command=["/bin/bash", "-i"])
        g.emit("session.opened", session_id=s3.sid, kind="pty=true,shell=bash -i",
               banner_observation_id=None, leader_pid_in_container=s3.leader_pid)
        g.emit("tool.completed", op_id=op, tool="session.open", status=0,
               duration_ms=0, artifact_ids=[], session_id=s3.sid)
        s3.send("bash /input/spawn_bg.sh")
        r, _c, _t = s3.read(timeout_ms=4000, quiet_ms=600)
        o3 = g.observation("session:%s:spawn_bg" % s3.sid, r,
                           artifact_writer=artifact_writer)
        before = [x for x in mgr.probe.table() if x[5] == s3.leader_sid]
        c3 = mgr.close(s3.sid, grace_ms=2000)
        g.emit("session.closed", session_id=s3.sid, transcript_artifact_id=None,
               exit_status=c3["exit_status"],
               descendants_killed=c3["descendants_killed"],
               survivors=c3["survivors"], zombies_excluded=c3["zombies_excluded"],
               checked_by="g-reference/ContainerProbe@host(docker exec /proc)",
               probe="B-3", requirement="§4.1-2",
               session_members_at_close=c3.get("session_members_at_close"),
               pgid_only_would_have_killed=c3["pgid_only_would_have_killed"],
               grace_used_ms=c3["grace_used_ms"], observation_id=o3)
        bg = [x for x in before if x[1].startswith("sleep")]
        missed = [p for p in (x[0] for x in bg)
                  if p not in (c3["pgid_only_would_have_killed"] or [])]
        note("B-3", c3["survivors"] == [],
             "close 후 생존자 %s. 세션 구성원 %d개, 프로세스 그룹만 정리했다면 놓쳤을 "
             "백그라운드 잡 pid %s" % (c3["survivors"], len(before), missed))

        # ------------------------------------------------------------------
        # B-4  즉시 종료하는 자식 생성 후 close   (§4.1-3, grace 소모 관측)
        # ------------------------------------------------------------------
        op = g.next_op_id()
        g.emit("tool.requested", op_id=op, tool="session.open",
               args={"kind": "pty", "command": "bash -i"},
               args_digest=sha256_hex("pty bash -i b4"))
        # 리더를 비대화형 셸로 둔다. `bash -i` 는 SIGTERM 을 무시하므로 리더가 grace 를
        # 전부 쓰게 되고, 그러면 §4.1-3 이 재려는 것(좀비 회계) 대신 셸의 시그널 처리를
        # 재게 된다. B-3 은 job control 이 필요해 `bash -i` 를 쓰지만 B-4 는 아니다.
        s4, _b = mgr.open("pty",
                          command=["/bin/sh", "-c", "exec bash /input/spawn_zombie.sh"])
        g.emit("session.opened", session_id=s4.sid, kind="pty=true,shell=bash -i",
               banner_observation_id=None, leader_pid_in_container=s4.leader_pid)
        g.emit("tool.completed", op_id=op, tool="session.open", status=0,
               duration_ms=0, artifact_ids=[], session_id=s4.sid)
        r, _c, _t = s4.read(timeout_ms=5000, quiet_ms=800)
        o4 = g.observation("session:%s:spawn_zombie" % s4.sid, r,
                           artifact_writer=artifact_writer)
        tbl = [x for x in mgr.probe.table() if x[5] == s4.leader_sid]
        zombies_before = [x[0] for x in tbl if x[2] == "Z"]
        c4 = mgr.close(s4.sid, grace_ms=2000)
        g.emit("session.closed", session_id=s4.sid, transcript_artifact_id=None,
               exit_status=c4["exit_status"],
               descendants_killed=c4["descendants_killed"],
               survivors=c4["survivors"], zombies_excluded=c4["zombies_excluded"],
               checked_by="g-reference/ContainerProbe@host(docker exec /proc)",
               probe="B-4", requirement="§4.1-3",
               zombies_before_close=zombies_before,
               grace_ms=c4["grace_ms"], grace_used_ms=c4["grace_used_ms"],
               grace_used_if_zombies_counted_ms=c4["grace_used_if_zombies_counted_ms"],
               observation_id=o4)
        note("B-4",
             c4["survivors"] == [] and bool(c4["zombies_excluded"])
             and c4["grace_used_ms"] < c4["grace_ms"],
             "생존자 %s, 좀비로 제외 %s, grace %dms 중 %dms 사용 "
             "(좀비를 생존자로 셌다면 %s)"
             % (c4["survivors"], c4["zombies_excluded"], c4["grace_ms"],
                c4["grace_used_ms"],
                ("%dms 전부" % c4["grace_used_if_zombies_counted_ms"])
                if c4["grace_used_if_zombies_counted_ms"] else "n/a"))

        # ------------------------------------------------------------------
        # B-5  상태 0 종료 프로세스와 실행 중 프로세스에 snapshot   (§4.1-4)
        # ------------------------------------------------------------------
        s_run, _b = mgr.open("pty", command=["/bin/sh", "-c", "sleep 120"])
        g.emit("session.opened", session_id=s_run.sid, kind="pty",
               banner_observation_id=None, leader_pid_in_container=s_run.leader_pid)
        s_exit, _b = mgr.open("pty", command=["/bin/sh", "-c", "exit 0"])
        g.emit("session.opened", session_id=s_exit.sid, kind="pty",
               banner_observation_id=None, leader_pid_in_container=s_exit.leader_pid)
        time.sleep(1.2)
        snap_run = s_run.snapshot()
        snap_exit = s_exit.snapshot()
        ok_b5 = (snap_run["live"] is True and snap_exit["live"] is False)
        o5 = g.observation("probe:B-5 snapshot.live",
                           json.dumps({"running": snap_run, "exited0": snap_exit},
                                      ensure_ascii=False, indent=1),
                           artifact_writer=artifact_writer)
        g.emit("probe.observed", probe="B-5", requirement="§4.1-4",
               running=snap_run, exited0=snap_exit, correct=ok_b5,
               observation_id=o5)
        note("B-5", ok_b5,
             "실행 중: live=%s naive_waitpid=(%s,%s) / 상태 0 종료: live=%s "
             "naive_waitpid=(%s,%s) — 두 경우의 waitpid status 가 같은 값인데 live 는 "
             "다르다. live 를 상태값으로 추론하지 않았다는 증거다."
             % (snap_run["live"], snap_run["naive_waitpid_pid"],
                snap_run["naive_waitpid_status"], snap_exit["live"],
                snap_exit["naive_waitpid_pid"], snap_exit["naive_waitpid_status"]))
        for _s in (s_run, s_exit):
            _c = mgr.close(_s.sid, grace_ms=1500)
            g.emit("session.closed", session_id=_s.sid, transcript_artifact_id=None,
                   exit_status=_c["exit_status"],
                   descendants_killed=_c["descendants_killed"],
                   survivors=_c["survivors"], zombies_excluded=_c["zombies_excluded"],
                   checked_by="g-reference/ContainerProbe@host(docker exec /proc)",
                   grace_used_ms=_c["grace_used_ms"])

        # ------------------------------------------------------------------
        # B-6  세션 2개를 번갈아 읽는다   (§4.2)
        # ------------------------------------------------------------------
        x1, b1 = mgr.open("socket", host=b_ip, port=9101)
        x2, b2 = mgr.open("socket", host=b_ip, port=9101)
        g.emit("session.opened", session_id=x1.sid, kind="socket",
               banner_observation_id=None, target="kisia-fix-b:9101")
        g.emit("session.opened", session_id=x2.sid, kind="socket",
               banner_observation_id=None, target="kisia-fix-b:9101")
        x1.send("HELO alpha")
        r1, _c, _t = x1.read(timeout_ms=3000)
        x2.send("HELO bravo")
        r2, _c, _t = x2.read(timeout_ms=3000)
        n1 = NONCE_RE.search(r1.decode("utf-8", "replace"))
        n2 = NONCE_RE.search(r2.decode("utf-8", "replace"))
        z1 = BANNER_RE.search(b1.decode("utf-8", "replace"))
        z2 = BANNER_RE.search(b2.decode("utf-8", "replace"))
        ok_b6 = bool(n1 and n2 and n1.group(1) != n2.group(1)
                     and b"alpha" not in r2 and b"bravo" not in r1)
        o6 = g.observation("probe:B-6 두 세션 번갈아 읽기",
                           "s1 banner zone=%s nonce=%s\ns2 banner zone=%s nonce=%s\n"
                           "s1_read=%r\ns2_read=%r\n"
                           % (z1 and z1.group(1), n1 and n1.group(1),
                              z2 and z2.group(1), n2 and n2.group(1), r1, r2),
                           artifact_writer=artifact_writer)
        g.emit("probe.observed", probe="B-6", requirement="§4.2",
               concurrent_sessions=len(mgr.live_ids()),
               session_ids=mgr.live_ids(), nonce_1=n1 and n1.group(1),
               nonce_2=n2 and n2.group(1), bytes_mixed=False, correct=ok_b6,
               observation_id=o6)
        note("B-6", ok_b6,
             "동시 세션 %d개. 서로 다른 연결 스코프 nonce %s / %s 를 받았고 두 read 가 "
             "서로의 바이트를 담지 않았다" % (len(mgr.live_ids()),
                                             n1 and n1.group(1), n2 and n2.group(1)))

        # §4.2 상한: 초과는 거부이고 대기가 아니다
        t0 = time.time()
        refused = None
        try:
            while len(mgr.live_ids()) < mgr.max_sessions:
                _f, _b = mgr.open("socket", host=b_ip, port=9101)
                # 상한을 채우는 세션도 반드시 알린다. 첫 run 에서 이것을 빼먹어 뒤의
                # session.closed 가 열린 적 없는 세션을 가리켰고 검사기가 S6.3 으로
                # 잡아냈다 (CHECKER.md §6).
                g.emit("session.opened", session_id=_f.sid, kind="socket",
                       banner_observation_id=None, target="kisia-fix-b:9101",
                       note="§4.2 상한 시험용")
            mgr.open("socket", host=b_ip, port=9101)
        except ScopeRefused as exc:
            refused = exc
        dt = int((time.time() - t0) * 1000)
        g.emit("scope.refused", action="session.open",
               reason_code=refused.reason_code if refused else "none",
               detail=str(refused) if refused else "",
               limit=mgr.max_sessions, elapsed_ms_before_refusal=dt,
               checked_by="g-reference/SessionManager")
        note("§4.2", refused is not None and refused.reason_code == "session_limit",
             "상한 %d, 초과 요청은 %dms 만에 거부됐다 (대기하지 않는다). reason=%s"
             % (mgr.max_sessions, dt, refused and refused.reason_code))
        # 상한 시험용으로 연 세션만 닫는다. B-1 의 세션(s1)은 턴을 가로질러 살아 있어야
        # 하므로 여기서 닫지 않는다 — 닫으면 S6 이 "턴 n+3 에도 live" 를 잃는다.
        # 그리고 **닫을 때마다 session.closed 를 낸다.** 첫 run 에서 이 이벤트를 빼먹었고
        # 검사기가 S6.2 로 잡아냈다 (CHECKER.md §6).
        for sid in list(mgr.live_ids()):
            if sid not in (x1.sid, s1.sid):
                c = mgr.close(sid, grace_ms=800)
                g.emit("session.closed", session_id=sid, transcript_artifact_id=None,
                       exit_status=c["exit_status"],
                       descendants_killed=c["descendants_killed"],
                       survivors=c["survivors"], zombies_excluded=c["zombies_excluded"],
                       checked_by="g-reference/ContainerProbe@host(docker exec /proc)",
                       grace_used_ms=c["grace_used_ms"])

        # ------------------------------------------------------------------
        # B-7  장시간 명령을 interrupt 한다
        # ------------------------------------------------------------------
        s7, _b = mgr.open("pty", command=["/bin/bash", "-i"])
        g.emit("session.opened", session_id=s7.sid, kind="pty=true,shell=bash -i",
               banner_observation_id=None, leader_pid_in_container=s7.leader_pid)
        s7.send("sleep 120; echo AFTER_INTERRUPT_MARKER")
        time.sleep(1.0)
        s7.interrupt(signal.SIGINT)
        time.sleep(0.6)
        s7.send("echo PROMPT_BACK=$?")
        r7, _c, _t = s7.read(timeout_ms=4000, quiet_ms=700)
        # tty 는 입력한 명령줄을 에코하므로 마커 문자열은 **실행하지 않아도** 한 번
        # 나타난다. 실행 여부를 가르는 것은 그 다음 명령이 보는 종료 코드 130(SIGINT)이다.
        ok_b7 = b"PROMPT_BACK=130" in r7 and r7.count(b"AFTER_INTERRUPT_MARKER") <= 1
        o7 = g.observation("session:%s:interrupt" % s7.sid, r7,
                           artifact_writer=artifact_writer)
        g.emit("probe.observed", probe="B-7", requirement="프롬프트 복귀",
               interrupted="sleep 120", prompt_returned=ok_b7,
               observation_id=o7)
        note("B-7", ok_b7, "interrupt 후 프롬프트가 돌아왔다: %r" % r7[-70:])
        c7 = mgr.close(s7.sid, grace_ms=1500)
        g.emit("session.closed", session_id=s7.sid, transcript_artifact_id=None,
               exit_status=c7["exit_status"],
               descendants_killed=c7["descendants_killed"],
               survivors=c7["survivors"], zombies_excluded=c7["zombies_excluded"],
               checked_by="g-reference/ContainerProbe@host(docker exec /proc)",
               grace_used_ms=c7["grace_used_ms"])

        # ------------------------------------------------------------------
        # B-8  닫힌 session_id 를 참조한다   (S6 unknown_session 거부)
        # ------------------------------------------------------------------
        dead = s7.sid
        made_new = False
        try:
            mgr.get(dead)
            refused8 = None
        except ScopeRefused as exc:
            refused8 = exc
        made_new = dead in mgr.live_ids()
        g.emit("scope.refused", action="session.get(%s)" % dead,
               reason_code=refused8.reason_code if refused8 else "none",
               detail=str(refused8) if refused8 else "거부되지 않았다",
               silently_created_new_session=made_new,
               checked_by="g-reference/SessionManager")
        ok_b8 = refused8 is not None and refused8.reason_code == "unknown_session" \
            and not made_new
        note("B-8", ok_b8,
             "닫힌 %s 참조 -> %s. 조용히 새 세션을 만들지 않았다(%s)"
             % (dead, refused8 and refused8.reason_code, not made_new))

        # ------------------------------------------------------------------
        turn += 1
        g.turn_boundary(turn, [], mgr.live_ids(), note="프로브 종료")
        for sid in list(mgr.live_ids()):
            c = mgr.close(sid, grace_ms=1500)
            g.emit("session.closed", session_id=sid, transcript_artifact_id=None,
                   exit_status=c["exit_status"],
                   descendants_killed=c["descendants_killed"],
                   survivors=c["survivors"], zombies_excluded=c["zombies_excluded"],
                   checked_by="g-reference/ContainerProbe@host(docker exec /proc)",
                   grace_used_ms=c["grace_used_ms"])

        hits = answer_sweep(g, run_dir, worker, answer)
        note("sweep", hits == 0, "정답 문자열 적중 %d 건 (네 표면)" % hits)

        ok_all = all(r[1] for r in RESULTS)
        g.emit("attempt.finished",
               outcome="solved" if v["verdict"] else "failed",
               reason="G 는 §4 참조 구현이다. B-1~B-8 결과: %s"
                      % ", ".join("%s=%s" % (p, "ok" if o else "NG")
                                  for p, o, _ in RESULTS),
               wall_clock_s=round(time.time() - g_t0, 3))
    finally:
        tbl_before = []
        try:
            tbl_before = mgr.probe.table() if mgr.probe else []
        except Exception:
            pass
        sh("docker", "kill", worker)
        time.sleep(0.5)
        _rc, still = sh("docker", "ps", "-aq", "--filter", "id=" + worker)
        g.emit("workspace.destroyed", surviving_processes=0,
               surviving_containers=len([x for x in still.split() if x]),
               checked_by="g-reference@host(docker ps -a / docker exec /proc)",
               processes_before_destroy=[{"pid": r[0], "comm": r[1], "stat": r[2]}
                                         for r in tbl_before][:12],
               checked_note="컨테이너가 사라지면 그 pid namespace 의 프로세스도 사라진다. "
                            "관측은 컨테이너 밖에서 했다 (§0.1 규칙 3).")
        g.close()

    sys.stdout.write("\nstream: %s\n" % out)
    return 0 if all(r[1] for r in RESULTS) else 1


g_t0 = time.time()

if __name__ == "__main__":
    sys.exit(main())
