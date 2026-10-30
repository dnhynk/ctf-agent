#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G 참조 구현 — §1 봉투 emitter.

`golden/driver.py` 를 재사용하지 않고 새로 썼다. 이유와 그 대가는 `G_REPORT.md` §2.
"골든 궤적이 검사기를 검증한다"(FOUNDATION_DECISION §9.2.1-2)의 독립성을 지키려면
골든 스트림의 생산자와 G 의 생산자가 같아서는 안 된다. 대가는 이 파일 하나(약 90줄)의
중복이다 — 도구 계층은 어차피 공유할 수 없다(driver.py 에는 pty 가 없다).
"""

import hashlib
import json
import os
import time


def sha256_hex(b):
    if isinstance(b, str):
        b = b.encode("utf-8")
    return "sha256:" + hashlib.sha256(b).hexdigest()


def utcnow():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + \
        ".%06dZ" % (int(time.time() * 1000000) % 1000000)


class Emitter(object):
    """§1.1 공통 필드를 앞에 붙이고 seq 를 1부터 빈틈없이 매긴다."""

    def __init__(self, path, run_id, attempt_id):
        self.path = path
        self.run_id = run_id
        self.attempt_id = attempt_id
        self.seq = 0
        self._obs = 0
        self._art = 0
        self._op = 0
        d = os.path.dirname(path)
        if d:
            try:
                os.makedirs(d)
            except OSError:
                pass
        self.fh = open(path, "w", encoding="utf-8")

    def emit(self, etype, **fields):
        self.seq += 1
        ev = {"ts": utcnow(), "run_id": self.run_id, "attempt_id": self.attempt_id,
              "seq": self.seq, "type": etype}
        ev.update(fields)
        self.fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        self.fh.flush()
        return ev

    # -- id 발급 ---------------------------------------------------------
    def next_obs_id(self):
        self._obs += 1
        return "obs-%04d" % self._obs

    def next_art_id(self):
        self._art += 1
        return "art-%04d" % self._art

    def next_op_id(self):
        """개정 r1 A-2. 동시 세션에서 *.requested/*.completed 를 짝짓는 유일한 수단."""
        self._op += 1
        return "op-%04d" % self._op

    # -- 자주 쓰는 조합 --------------------------------------------------
    def observation(self, source_ref, raw, limit=4096, artifact_writer=None):
        """§1.3 + 개정 r1 A-9(`shown`/`shown_digest`)."""
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        shown = raw[:limit]
        truncated = len(raw) > limit
        aid = None
        if truncated and artifact_writer is not None:
            aid = self.next_art_id()
            path = artifact_writer(aid, raw)
            self.emit("artifact.produced", artifact_id=aid, sha256=sha256_hex(raw),
                      bytes=len(raw), producer_ref=source_ref, path=path)
        oid = self.next_obs_id()
        self.emit("observation.recorded", observation_id=oid, source_ref=source_ref,
                  bytes_total=len(raw), bytes_shown=len(shown),
                  shown=shown.decode("utf-8", "replace"),
                  shown_digest=sha256_hex(shown), truncated=truncated,
                  full_digest=sha256_hex(raw), artifact_id=aid)
        return oid

    def turn_boundary(self, turn, observation_ids, live_session_ids, jar_digest=None,
                      note=""):
        """모델이 없으므로 호출을 시간 간격을 두고 나눈다 — FOUNDATION_DECISION §9.1.

        가짜 모델 호출이 아니라 **턴 경계의 표시**다. 이렇게 하지 않으면 S4 의
        "model.completed 3개 이상을 사이에 두고" 를 G 의 스트림 위에서 평가할 수 없다.
        `FIXTURES.md` §4.2(1) 이 골든에 대해 쓴 것과 같은 대체다.
        """
        self.emit("model.requested", model_id="none", effort="none",
                  input_tokens=0, cached_tokens=0, cache_write_tokens=0,
                  prompt_digest=sha256_hex("g-turn-%d" % turn),
                  observation_ids=list(observation_ids), g_intent=note)
        time.sleep(0.05)
        self.emit("model.completed", output_tokens=0, usd=0.0, latency_ms=0,
                  finish_reason="g_turn_boundary")
        self.emit("state.snapshot", turn=turn,
                  live_session_ids=list(live_session_ids),
                  jar_digest=jar_digest or sha256_hex(""),
                  artifact_count=self._art)

    def close(self):
        self.fh.close()
