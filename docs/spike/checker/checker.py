#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KISIA foundation spike — seam checker.

`SEAM_CONTRACT.md` §2 의 술어를 코드로 옮긴 것이다. 판정은 사람이 로그를 읽어서 하지
않는다(§0.1-4). 검사기는 **원시 스트림에 대한 순수 함수**이고, docker·호스트·네트워크를
쓰지 않는다 — P-S9-a(스트림만 다른 기계로 옮겨 재계산)가 그 성질을 요구한다.

유일한 스트림 밖 입력은 `--pricing`(S3의 비용 재계산용, 내용 주소로 고정된 표)이다.
후보가 제공하는 요약은 읽지 않는다(§6).

사용:
    python3 checker.py <stream.jsonl> [...]            스트림별 판정
    python3 checker.py --set A a/stream.jsonl a/negative-a4.jsonl
                                                       유형 단위 집합 판정
    python3 checker.py --json <stream.jsonl>           기계 판독용
표준 라이브러리만 쓴다.
"""

import argparse
import hashlib
import json
import os
import re
import sys

# --------------------------------------------------------------------------
# 술어 판정값
#
# §9.3 은 seam 판정을 넷으로 정한다. 술어 하나하나의 판정값은 그보다 많아야 한다 —
# "거짓"과 "이 스트림에 그 사실을 판정할 재료가 없다"를 같은 값으로 접으면 검사기가
# 거짓말을 하게 되고, PASS 가 아닌 칸의 원인을 (a)술어/(b)드라이버/(c)fixture 로 가를
# 수 없다.
TRUE = "TRUE"            # 참
FALSE = "FALSE"          # 거짓 -> 그 seam 은 FAIL
VACUOUS = "VACUOUS"      # 조건부 술어인데 발동 사례가 없다 -> 참으로 센다
NO_EVIDENCE = "NO_EV"    # 요구된 사실인데 스트림에 사례가 없다 -> PASS 가 아니다
OUT_OF_STREAM = "OOS"    # 한 스트림의 성질이 아니다(구조적/교차 스트림) -> 칸에 세지 않는다

_COUNTS_AGAINST = (FALSE, NO_EVIDENCE)
_SATISFIES = (TRUE, VACUOUS)

EMPTY_SHA256 = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

# §1.2 통제 블록 — EVAL_CONTRACT.md 가 요구하는 항목 전부
CONTROL_BLOCK_KEYS = [
    "arm_id", "candidate_repo", "candidate_commit", "structural_patches",
    "model_id", "reasoning_effort",
    "attempt_timeout_s", "tool_timeout_s", "session_timeout_s",
    "token_budget", "usd_budget",
    "host_id", "image_digest",
    "network_policy",
    "challenge_id", "challenge_manifest_sha256",
]

# §3 seam x 유형 하중표.  None = 빈칸(그 유형이 하중을 싣지 않는다) -> N/A
# 리스트 = 그 유형이 추가로 싣는 프로브/형태.  [] = 상시 술어만.
LOAD_TABLE = {
    "A": {"S1": [], "S2": ["a", "b"], "S3": ["a"], "S4": ["oneshot"],
          "S5": ["a"], "S6": None, "S7": [], "S8": ["a"], "S9": ["a"]},
    # B/S2 는 원안이 `● (a,b)` 였다. §5 의 유형 B 프로브표(B-1~B-9)에 S2-a/S2-b 를
    # 실행하는 프로브가 하나도 없어 하중표와 프로브표가 서로 어긋났다.
    # CHECKER.md §4 개정 A-4 로 상시 술어만 남긴다 — 쓰기 거부 프로브는 유형 A(A-3)가 진다.
    "B": {"S1": None, "S2": [], "S3": None, "S4": ["session", "a"],
          "S5": [], "S6": [], "S7": [], "S8": [], "S9": []},
    "C": {"S1": None, "S2": ["c"], "S3": None, "S4": ["http"],
          "S5": None, "S6": ["a"], "S7": [], "S8": [], "S9": []},
}

CHALLENGE_TO_TYPE = {
    "kisia-fix-a-static": "A",
    "kisia-fix-b-session": "B",
    "kisia-fix-c-web": "C",
}


def sha256_hex(s):
    if isinstance(s, str):
        s = s.encode("utf-8")
    return "sha256:" + hashlib.sha256(s).hexdigest()


def external_checker(value, arm_id):
    """개정 r1 A-7: `checked_by` / `verifier_id` 가 arm 을 가리키지 않는가.

    문자 단위 포함 검사는 쓸 수 없다. 이 스파이크의 arm_id 는 T·E·G·X 로 전부 한 글자여서,
    "포함하지 않는다"를 문자로 읽으면 `g-reference@host` 같은 정당한 외부 검사기 이름이
    전부 걸린다. 구성요소 이름(첫 구분자 `@` `/` `(` 앞부분)이 arm_id 와 같은지, 그리고
    arm_id 가 독립된 토큰으로 나타나는지를 본다.
    """
    if not value:
        return False
    if not arm_id:
        return True
    comp = re.split(r"[@/(]", str(value), maxsplit=1)[0].strip()
    if comp.lower() == str(arm_id).lower():
        return False
    toks = [t.lower() for t in re.split(r"[^A-Za-z0-9_-]+", str(value)) if t]
    return str(arm_id).lower() not in toks


class P(object):
    """술어 하나의 판정."""

    __slots__ = ("pid", "text", "verdict", "seqs", "note", "probe")

    def __init__(self, pid, text, verdict, seqs=(), note="", probe=None):
        self.pid = pid
        self.text = text
        self.verdict = verdict
        self.seqs = list(seqs)
        self.note = note
        self.probe = probe          # None = 상시 술어, 아니면 하중표의 키

    def as_dict(self):
        return {"id": self.pid, "verdict": self.verdict, "seqs": self.seqs,
                "probe": self.probe, "text": self.text, "note": self.note}


# --------------------------------------------------------------------------


class Stream(object):
    """한 attempt 의 이벤트 스트림. 인덱스는 전부 여기서 만든다."""

    def __init__(self, path):
        self.path = path
        self.events = []
        self.parse_errors = []
        with open(path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    self.events.append(json.loads(line))
                except ValueError as exc:
                    self.parse_errors.append((lineno, str(exc)))
        self.by_type = {}
        for e in self.events:
            self.by_type.setdefault(e.get("type"), []).append(e)
        self.obs = {}
        for e in self.by_type.get("observation.recorded", []):
            oid = e.get("observation_id")
            if oid is not None:
                self.obs[oid] = e
        self.artifacts = {}
        for e in self.by_type.get("artifact.produced", []):
            aid = e.get("artifact_id")
            if aid is not None:
                self.artifacts[aid] = e
        self.started = (self.by_type.get("attempt.started") or [None])[0]
        self.finished = (self.by_type.get("attempt.finished") or [None])[0]

    # -- 편의 ------------------------------------------------------------
    def t(self, name):
        return self.by_type.get(name, [])

    def first_seq(self, name):
        evs = self.t(name)
        return evs[0]["seq"] if evs else None

    @property
    def ctype(self):
        cid = (self.started or {}).get("challenge_id")
        return CHALLENGE_TO_TYPE.get(cid)

    @property
    def arm_id(self):
        return (self.started or {}).get("arm_id", "")

    @property
    def outcome(self):
        return (self.finished or {}).get("outcome")

    @property
    def structural_patches(self):
        sp = (self.started or {}).get("structural_patches")
        return sp if isinstance(sp, list) else []

    def obs_text(self, oid):
        """관찰의 **기록된 바이트**. §4.2(2) 의 `shown` 이 없으면 내용이 없는 것이다."""
        o = self.obs.get(oid)
        if o is None:
            return None
        return o.get("shown")

    def verified_answer(self):
        """스트림에서 정답 문자열을 얻는다.

        verdict=true 인 `verification.completed` 의 `candidate_digest` 와 digest 가
        일치하는 `candidate.produced.value` 가 정답이다. 검사기는 정답을 밖에서
        받지 않는다 — 받으면 스트림만으로 재계산한다는 P-S9-a 가 깨진다.
        """
        good = set()
        for v in self.t("verification.completed"):
            if v.get("verdict") is True and v.get("candidate_digest"):
                good.add(v["candidate_digest"])
        if not good:
            return None
        for c in self.t("candidate.produced"):
            val = c.get("value")
            if isinstance(val, str) and sha256_hex(val) in good:
                return val
        return None


# --------------------------------------------------------------------------
# 봉투 (§1.1)
# --------------------------------------------------------------------------

def check_envelope(s):
    out = []
    if s.parse_errors:
        out.append(P("E0", "모든 줄이 JSON 으로 파싱된다", FALSE, [],
                     "파싱 실패 %d 줄: %s" % (len(s.parse_errors), s.parse_errors[:3])))
        return out
    out.append(P("E0", "모든 줄이 JSON 으로 파싱된다", TRUE, []))

    missing = []
    for e in s.events:
        for k in ("ts", "run_id", "attempt_id", "seq", "type"):
            if k not in e:
                missing.append((e.get("seq"), k))
    out.append(P("E1", "모든 이벤트에 §1.1 공통 필드 5개가 있다",
                 TRUE if not missing else FALSE,
                 sorted({m[0] for m in missing if m[0] is not None})[:8],
                 "" if not missing else "결손 %d건" % len(missing)))

    seqs = [e.get("seq") for e in s.events]
    expected = list(range(1, len(s.events) + 1))
    gapless = seqs == expected
    bad = [i for i, (a, b) in enumerate(zip(seqs, expected)) if a != b]
    out.append(P("E2", "seq 가 1부터 빈틈없이 증가한다 (§1.1)",
                 TRUE if gapless else FALSE,
                 [seqs[i] for i in bad[:5]],
                 "" if gapless else "첫 어긋남 index %d" % bad[0]))

    runs = {e.get("run_id") for e in s.events}
    atts = {e.get("attempt_id") for e in s.events}
    out.append(P("E3", "run_id·attempt_id 가 스트림 전체에서 하나다",
                 TRUE if len(runs) == 1 and len(atts) == 1 else FALSE, [],
                 "run_id %d개 / attempt_id %d개" % (len(runs), len(atts))))

    ts = [e.get("ts") for e in s.events]
    mono = all(ts[i] <= ts[i + 1] for i in range(len(ts) - 1))
    bad_ts = [s.events[i + 1]["seq"] for i in range(len(ts) - 1) if ts[i] > ts[i + 1]]
    out.append(P("E4", "ts 가 발생 순서를 보존한다 (감소하지 않는다)",
                 TRUE if mono else FALSE, bad_ts[:5]))
    return out


# --------------------------------------------------------------------------
# seam 술어 (§2)
# --------------------------------------------------------------------------

def s1(s):
    out = []
    ib = s.t("input.bound")
    if len(ib) != 1:
        out.append(P("S1.1", "input.bound 가 정확히 1회", FALSE,
                     [e["seq"] for e in ib], "%d회" % len(ib)))
        return out
    b = ib[0]
    fm = s.first_seq("model.requested")
    ft = s.first_seq("tool.requested")
    later = [x for x in (fm, ft) if x is not None]
    ok = bool(later) and all(b["seq"] < x for x in later)
    out.append(P("S1.1",
                 "input.bound 가 정확히 1회, 첫 model.requested·첫 tool.requested 보다 앞",
                 TRUE if ok else FALSE, [b["seq"], fm, ft]))

    files = b.get("files")
    if not isinstance(files, list) or not files:
        out.append(P("S1.2", "/input 의 모든 파일이 files[] 에 sha256·바이트 수와 함께",
                     FALSE, [b["seq"]], "files[] 가 비었거나 리스트가 아니다"))
    else:
        bad = [f for f in files
               if not (isinstance(f.get("path"), str)
                       and isinstance(f.get("sha256"), str)
                       and isinstance(f.get("bytes"), int))]
        out.append(P("S1.2", "files[] 의 모든 항목에 path·sha256·bytes",
                     TRUE if not bad else FALSE, [b["seq"]],
                     "" if not bad else "불완전 %d건" % len(bad)))
    out.append(P("S1.2x", "files[] 가 /input 디렉터리 전체를 덮는가 — 디렉터리 목록이 "
                          "봉투에 없어 스트림만으로는 판정 불가", OUT_OF_STREAM, [b["seq"]],
                 "스트림 밖 스윕이 필요하다 (CHECKER.md §4 개정 A-3 참조)"))

    n = b.get("structural_patches_for_intake")
    out.append(P("S1.3", "챌린지 투입에 쓴 구조 패치 수가 기록되어 있다",
                 TRUE if isinstance(n, int) else FALSE, [b["seq"]],
                 "" if isinstance(n, int) else "structural_patches_for_intake 부재"))
    return out


def s2(s):
    out = []
    wc = s.t("workspace.created")
    if len(wc) != 1:
        out.append(P("S2.1", "workspace.created 가 mounts·network 를 기록한다", FALSE,
                     [e["seq"] for e in wc], "%d회" % len(wc)))
    else:
        w = wc[0]
        mounts = w.get("mounts")
        ok_m = isinstance(mounts, list) and bool(mounts) and all(
            isinstance(m.get("path"), str) and m.get("mode") in ("ro", "rw")
            for m in mounts)
        ok_n = isinstance(w.get("network"), str) and bool(w.get("network"))
        out.append(P("S2.1", "workspace.created 가 mounts 를 모드와, network 를 이름과 함께 기록",
                     TRUE if (ok_m and ok_n) else FALSE, [w["seq"]],
                     "" if ok_m and ok_n else "mounts=%s network=%s" % (ok_m, ok_n)))

    refusals = s.t("scope.refused")

    # P-S2-a : /work 밖 쓰기 -> scope.refused, 그리고 호스트에서 파일 부재 확인
    cand = [r for r in refusals
            if str(r.get("action", "")).startswith("write:")
            and not str(r.get("action", "")).startswith("write:/work")]
    if not cand:
        out.append(P("S2.2", "P-S2-a  /work 밖 쓰기 -> scope.refused + 호스트 확인",
                     NO_EVIDENCE, [], "이 스트림에 /work 밖 쓰기 시도가 없다", probe="a"))
    else:
        checked = [r for r in cand if r.get("host_check_file_exists") is False]
        out.append(P("S2.2", "P-S2-a  /work 밖 쓰기 -> scope.refused + 호스트에서 파일 부재 확인",
                     TRUE if checked else FALSE, [r["seq"] for r in cand],
                     "" if checked else "거부는 있으나 host_check_file_exists 로 확인된 것이 없다",
                     probe="a"))

    # P-S2-b : /input 쓰기 -> 거부
    inp = [r for r in refusals if str(r.get("action", "")).startswith("write:/input")]
    out.append(P("S2.3", "P-S2-b  /input 쓰기 -> 거부",
                 TRUE if inp else NO_EVIDENCE, [r["seq"] for r in inp],
                 "" if inp else "이 스트림에 /input 쓰기 시도가 없다", probe="b"))

    # P-S2-c : 컨테이너 안에서 미선언 host:port 접속 -> 실패
    conn = [r for r in refusals if str(r.get("action", "")).startswith("connect:")]
    if not conn:
        out.append(P("S2.4", "P-S2-c  컨테이너 안에서 미선언 host:port 접속 -> 실패",
                     NO_EVIDENCE, [], "이 스트림에 미선언 목적지 접속 시도가 없다", probe="c"))
    else:
        inside = [r for r in conn if r.get("attempted_from") == "container"]
        out.append(P("S2.4", "P-S2-c  접속 시도가 **컨테이너 안에서** 이뤄졌고 실패했다",
                     TRUE if inside else FALSE, [r["seq"] for r in conn],
                     "" if inside else "attempted_from=container 인 시도가 없다 "
                                       "(호스트에서 대신 시도한 것은 술어를 만족시키지 못한다)",
                     probe="c"))

    wd = s.t("workspace.destroyed")
    if len(wd) != 1:
        out.append(P("S2.5", "workspace.destroyed.surviving_processes == 0 이고 checked_by 가 외부",
                     FALSE, [e["seq"] for e in wd], "%d회" % len(wd)))
    else:
        d = wd[0]
        zero = d.get("surviving_processes") == 0
        cb = d.get("checked_by") or ""
        external = external_checker(cb, s.arm_id)
        out.append(P("S2.5", "workspace.destroyed.surviving_processes == 0 이고 "
                             "checked_by 가 후보가 아닌 외부 검사기",
                     TRUE if (zero and external) else FALSE, [d["seq"]],
                     "" if zero and external else
                     "surviving_processes=%r checked_by=%r" % (d.get("surviving_processes"), cb)))
    return out


def _load_pricing(path):
    """pricing.openai.yaml 을 최소 파싱한다 (표준 라이브러리만 쓰기 위해)."""
    prices = {}
    cur = None
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            m = re.match(r"^\s*-\s*model:\s*(\S+)\s*$", line)
            if m:
                cur = {}
                prices[m.group(1)] = cur
                continue
            m = re.match(r"^\s{4,}([a-z_0-9]+):\s*\"?([^\"]*)\"?\s*$", line)
            if m and cur is not None:
                prices[list(prices)[-1]][m.group(1)] = m.group(2)
    return prices


def s3(s, pricing_path=None):
    out = []
    reqs = s.t("model.requested")
    comps = s.t("model.completed")
    out.append(P("S3.1", "모든 model.requested 에 짝이 되는 model.completed 또는 명시적 실패",
                 TRUE if len(reqs) == len(comps) and len(reqs) > 0 else
                 (FALSE if reqs else VACUOUS),
                 [], "requested %d / completed %d" % (len(reqs), len(comps))))

    priced = [r for r in reqs if r.get("model_id") not in (None, "", "none")]
    if not priced:
        out.append(P("S3.2", "기록된 토큰과 pricing 표로 계산한 값이 usd 와 정확히 일치",
                     VACUOUS, [], "과금 대상 호출이 0회다 (model_id=none 은 §4.2(1) 턴 경계 표시)"))
    elif not pricing_path or not os.path.exists(pricing_path or ""):
        out.append(P("S3.2", "기록된 토큰과 pricing 표로 계산한 값이 usd 와 정확히 일치",
                     OUT_OF_STREAM, [], "--pricing 표가 주어지지 않았다"))
    else:
        prices = _load_pricing(pricing_path)
        bad = []
        unev = []
        for r in priced:
            if r.get("cache_write_tokens") is None:
                unev.append(r["seq"])
                continue
            p = prices.get(r.get("model_id"))
            if p is None:
                bad.append((r["seq"], "pricing 표에 없는 model_id"))
                continue
        if unev:
            out.append(P("S3.2", "기록된 토큰과 pricing 표로 계산한 값이 usd 와 정확히 일치",
                         FALSE, unev[:5],
                         "§1.3 의 필드(input_tokens·cached_tokens)만으로는 cache write 분을 "
                         "분리할 수 없어 usd 를 재계산할 수 없다 — CHECKER.md §4 개정 A-1"))
        else:
            out.append(P("S3.2", "기록된 토큰과 pricing 표로 계산한 값이 usd 와 정확히 일치",
                         TRUE if not bad else FALSE, [b[0] for b in bad]))

    out.append(P("S3.3", "P-S3-a  모델 id 만 luna 로 바꿔 재실행했을 때 "
                         "후보 소스 수정 없이 model_requested.model_id 가 바뀐다",
                 OUT_OF_STREAM, [],
                 "스트림 두 개를 비교해야 한다. 한 스트림의 성질이 아니다", probe="a"))

    over = [r for r in reqs if isinstance(r.get("input_tokens"), int)
            and r["input_tokens"] > 272000]
    if not over:
        out.append(P("S3.4", "input_tokens > 272000 인 요청이 있으면 그 사실이 이벤트로 표시된다",
                     VACUOUS, [], "272K 초과 요청 0건"))
    else:
        marked = [r for r in over if r.get("long_context") is True]
        out.append(P("S3.4", "input_tokens > 272000 인 요청이 이벤트로 표시된다",
                     TRUE if len(marked) == len(over) else FALSE,
                     [r["seq"] for r in over]))
    return out


def s4(s):
    out = []

    # (1회 실행) tool.completed 에 exit code 와 출력이 있다.
    # "1회 실행 형태"의 판별은 이름이 아니라 이벤트 증거로 한다: session_id 를 나르지
    # 않는 tool.completed 가 1회 실행이다. 이름 기반 판별은 arm 마다 이름이 달라 깨진다.
    tcs = s.t("tool.completed")
    oneshot = [t for t in tcs if t.get("session_id") is None]
    if not oneshot:
        out.append(P("S4.1", "(1회 실행) tool.completed 에 exit code 와 출력이 있다",
                     NO_EVIDENCE, [], "1회 실행 형태의 tool.completed 가 없다",
                     probe="oneshot"))
    else:
        bad = [t for t in oneshot
               if not isinstance(t.get("status"), int)
               or t.get("observation_id") not in s.obs]
        out.append(P("S4.1", "(1회 실행) 모든 tool.completed 에 정수 status 와 "
                             "실재하는 observation_id",
                     TRUE if not bad else FALSE, [t["seq"] for t in bad[:5]],
                     probe="oneshot"))

    # (지속 세션) 같은 session_id 의 session.io 가 model.completed 3개 이상을 사이에 두고
    ios = s.t("session.io")
    if not ios:
        out.append(P("S4.2", "(지속 세션) 같은 session_id 의 session.io 가 "
                             "model.completed 3개 이상을 사이에 두고 나타난다",
                     NO_EVIDENCE, [], "session.io 가 없다", probe="session"))
    else:
        mc = [e["seq"] for e in s.t("model.completed")]
        best = None
        for sid in sorted({i.get("session_id") for i in ios}):
            ss = [i["seq"] for i in ios if i.get("session_id") == sid]
            lo, hi = min(ss), max(ss)
            n = len([q for q in mc if lo < q < hi])
            if best is None or n > best[1]:
                best = (sid, n, lo, hi)
        sid, n, lo, hi = best
        out.append(P("S4.2", "(지속 세션) 같은 session_id 의 session.io 가 "
                             "model.completed 3개 이상을 사이에 두고 나타난다",
                     TRUE if n >= 3 else FALSE, [lo, hi],
                     "%s: seq %d..%d 사이 model.completed %d개" % (sid, lo, hi, n),
                     probe="session"))

    # (상태 있는 HTTP) jar_digest_after(n) == jar_digest_before(n+1) 이고 초기값과 다르다
    hx = s.t("http.exchanged")
    if len(hx) < 2:
        out.append(P("S4.3", "(상태 있는 HTTP) 앞선 교환이 세운 쿠키가 뒤의 요청에 실린다",
                     NO_EVIDENCE, [], "http.exchanged 가 %d건" % len(hx), probe="http"))
    else:
        chain_ok, moved, breaks = True, False, []
        for a, b in zip(hx, hx[1:]):
            if a.get("jar_digest_after") != b.get("jar_digest_before"):
                chain_ok = False
                breaks.append(b["seq"])
            if a.get("jar_digest_after") not in (None, EMPTY_SHA256):
                moved = True
        out.append(P("S4.3", "jar_digest_after(n) == jar_digest_before(n+1) 이고 "
                             "그 값이 초기값과 다르다",
                     TRUE if (chain_ok and moved) else FALSE,
                     breaks[:5] or [hx[0]["seq"], hx[-1]["seq"]],
                     "" if chain_ok and moved else
                     "연쇄 %s / 초기값과 다름 %s" % (chain_ok, moved),
                     probe="http"))

    # P-S4-a : 자식 프로세스를 만드는 명령을 timeout 으로 죽인다 -> 외부 확인 자식 생존 0
    closes = s.t("session.closed")
    withkids = [c for c in closes if isinstance(c.get("descendants_killed"), int)
                and c["descendants_killed"] > 0]
    if not withkids:
        out.append(P("S4.4", "P-S4-a  자식을 만드는 명령을 죽인 뒤 외부 검사기가 확인한 자식 생존 0",
                     NO_EVIDENCE, [c["seq"] for c in closes],
                     "descendants_killed > 0 인 close 가 없다 — 정리할 자식이 있었다는 증거가 "
                     "이 스트림에 없다", probe="a"))
    else:
        bad = [c for c in withkids if c.get("survivors") not in ([], None)
               or not external_checker(c.get("checked_by"), s.arm_id)]
        out.append(P("S4.4", "P-S4-a  자식을 죽인 뒤 외부 검사기가 확인한 생존 0",
                     TRUE if not bad else FALSE, [c["seq"] for c in withkids],
                     probe="a"))
    return out


def s5(s):
    out = []
    obs = s.t("observation.recorded")

    trunc_needed = [o for o in obs
                    if isinstance(o.get("bytes_total"), int)
                    and isinstance(o.get("bytes_shown"), int)
                    and o["bytes_total"] > o["bytes_shown"]]
    if not trunc_needed:
        out.append(P("S5.1", "표시 한도를 넘는 출력마다 truncated == true 이고 artifact_id 가 있다",
                     VACUOUS, [], "잘린 관찰 0건"))
        out.append(P("S5.2", "그 artifact_id 에 대응하는 artifact.produced 가 sha256 과 함께 존재",
                     VACUOUS, []))
    else:
        bad = [o for o in trunc_needed
               if o.get("truncated") is not True or not o.get("artifact_id")]
        out.append(P("S5.1", "표시 한도를 넘는 출력마다 truncated == true 이고 artifact_id 가 있다",
                     TRUE if not bad else FALSE, [o["seq"] for o in trunc_needed]))
        miss = []
        for o in trunc_needed:
            aid = o.get("artifact_id")
            a = s.artifacts.get(aid)
            if a is None or not isinstance(a.get("sha256"), str):
                miss.append(o["seq"])
        out.append(P("S5.2", "그 artifact_id 에 대응하는 artifact.produced 가 sha256 과 함께 존재",
                     TRUE if not miss else FALSE, miss[:5] or [o["seq"] for o in trunc_needed]))

    dangling = []
    for r in s.t("model.requested"):
        for oid in (r.get("observation_ids") or []):
            o = s.obs.get(oid)
            if o is None or o["seq"] > r["seq"]:
                dangling.append((r["seq"], oid))
    out.append(P("S5.3", "model.requested.observation_ids[] 의 모든 항목이 "
                         "앞선 observation.recorded 에 존재한다",
                 TRUE if not dangling else FALSE, [d[0] for d in dangling[:5]],
                 "" if not dangling else "미해결 %d건: %s" % (len(dangling), dangling[:3])))

    # P-S5-a : 같은 바이트를 두 번 넣어 bytes_shown 과 표시분 digest 가 동일하다
    groups = {}
    for o in obs:
        fd = o.get("full_digest")
        if fd:
            groups.setdefault(fd, []).append(o)
    dup = {k: v for k, v in groups.items() if len(v) > 1}
    if not dup:
        out.append(P("S5.4", "P-S5-a  같은 바이트를 두 번 넣어 bytes_shown 과 표시분 digest 가 동일",
                     NO_EVIDENCE, [],
                     "같은 full_digest 를 갖는 관찰 쌍이 없다 — 결정론을 시험한 사례가 "
                     "이 스트림에 없다", probe="a"))
    else:
        bad = []
        for fd, group in dup.items():
            if len({o.get("bytes_shown") for o in group}) != 1 or \
               len({o.get("shown_digest") for o in group}) != 1:
                bad.extend(o["seq"] for o in group)
        out.append(P("S5.4", "P-S5-a  같은 바이트 -> 같은 bytes_shown·shown_digest",
                     TRUE if not bad else FALSE, bad[:5] or
                     [g[0]["seq"] for g in list(dup.values())[:2]], probe="a"))
    return out


def s6(s):
    out = []
    mc = s.t("model.completed")
    snaps = s.t("state.snapshot")
    if not mc:
        out.append(P("S6.1", "매 모델 턴마다 state.snapshot 이 있다", NO_EVIDENCE, [],
                     "model.completed 가 없다"))
    else:
        ok = len(snaps) >= len(mc)
        out.append(P("S6.1", "매 모델 턴마다 state.snapshot 이 있다",
                     TRUE if ok else FALSE, [],
                     "model.completed %d / state.snapshot %d" % (len(mc), len(snaps))))

    # turn n 에 연 세션이 turn n+3 에도 live (그 사이에 닫지 않았다면)
    by_turn = {}
    for sn in snaps:
        by_turn[sn.get("turn")] = set(sn.get("live_session_ids") or [])
    closed_at_turn = {}
    for c in s.t("session.closed"):
        prior = [sn.get("turn") for sn in snaps if sn["seq"] < c["seq"]]
        closed_at_turn[c.get("session_id")] = max(prior) if prior else 0
    turns = sorted(t for t in by_turn if isinstance(t, int))
    viol, tested = [], 0
    for i, tn in enumerate(turns):
        target = tn + 3
        if target not in by_turn:
            continue
        for sid in by_turn[tn]:
            if closed_at_turn.get(sid, 10 ** 9) < target:
                continue
            tested += 1
            if sid not in by_turn[target]:
                viol.append((sid, tn, target))
    if tested == 0:
        # 세션이 아예 없는 스트림(유형 C)에서 이 술어는 발동 사례가 없다. 유형 C 의 상태는
        # 프로세스가 아니라 쿠키 항아리이고 그 요구는 S6.4 가 진다 — CHECKER.md §4 개정 A-5.
        # 유형 B 가 세션을 열지 못한 경우는 S4.2(세션 형태)가 잡는다.
        out.append(P("S6.2", "turn n 에 연 세션이 turn n+3 에도 live_session_ids 에 있다",
                     VACUOUS if not s.t("session.opened") else NO_EVIDENCE, [],
                     "이 스트림에 세션이 없다 (유형 C의 상태 요구는 S6.4가 진다)"
                     if not s.t("session.opened")
                     else "턴 4개 이상을 가로질러 살아 있어야 할 세션이 이 스트림에 없다"))
    else:
        out.append(P("S6.2", "turn n 에 연 세션이 turn n+3 에도 live_session_ids 에 있다",
                     TRUE if not viol else FALSE, [],
                     "검사한 (세션,턴) 쌍 %d개" % tested if not viol else str(viol[:3])))

    # 모델이 참조한 session_id 가 live 에 없으면 scope.refused(unknown_session)
    live_all = set()
    for sn in snaps:
        live_all |= set(sn.get("live_session_ids") or [])
    refs = []
    for e in s.events:
        if e.get("type") in ("session.io", "session.closed") and e.get("session_id"):
            prior = [sn for sn in snaps if sn["seq"] < e["seq"]]
            if prior and e["session_id"] not in set(prior[-1].get("live_session_ids") or []) \
                    and e["seq"] > (s.first_seq("session.opened") or 0):
                opened = [o for o in s.t("session.opened")
                          if o.get("session_id") == e["session_id"] and o["seq"] < e["seq"]]
                if not opened:
                    refs.append(e)
    unknown = [r for r in s.t("scope.refused") if r.get("reason_code") == "unknown_session"]
    if not refs and not unknown:
        out.append(P("S6.3", "live 가 아닌 session_id 참조 -> scope.refused(unknown_session). "
                             "조용히 새 세션을 만들지 않는다",
                     VACUOUS, [], "죽은 세션을 참조한 사례가 없다"))
    else:
        out.append(P("S6.3", "live 가 아닌 session_id 참조 -> scope.refused(unknown_session)",
                     TRUE if unknown and not refs else FALSE,
                     [e["seq"] for e in refs[:5]] or [u["seq"] for u in unknown]))

    hx = s.t("http.exchanged")
    if len(hx) < 3:
        out.append(P("S6.4", "유형 C 에서 세 번째 요청의 jar_digest_before 가 "
                             "첫 요청 이후의 값과 이어진다",
                     NO_EVIDENCE if s.ctype == "C" else VACUOUS,
                     [], "http.exchanged 가 %d건" % len(hx)))
    else:
        ok = hx[2].get("jar_digest_before") == hx[0].get("jar_digest_after")
        out.append(P("S6.4", "세 번째 요청의 jar_digest_before 가 첫 요청 이후의 값과 이어진다",
                     TRUE if ok else FALSE, [hx[0]["seq"], hx[2]["seq"]]))

    # P-S6-a (음성): 턴 사이에 항아리를 버리면 attempt 가 실패해야 한다
    dropped = [r for r in s.t("scope.refused")
               if r.get("reason_code") in ("cookie_jar_dropped", "jar_dropped")] or \
              [e for e in s.events if e.get("type") == "scope.refused"
               and "jar" in str(e.get("action", "")).lower()]
    if not dropped:
        out.append(P("S6.5", "P-S6-a  턴 사이에 쿠키 항아리를 버리면 attempt 가 실패한다",
                     NO_EVIDENCE, [], "항아리를 버린 사례가 이 스트림에 없다", probe="a"))
    else:
        out.append(P("S6.5", "P-S6-a  항아리를 버리면 attempt 가 실패한다",
                     TRUE if s.outcome == "failed" else FALSE,
                     [d["seq"] for d in dropped], "outcome=%s" % s.outcome, probe="a"))
    return out


def s7(s):
    out = []
    cands = s.t("candidate.produced")
    if not cands:
        out.append(P("S7.1", "candidate.produced.derived_from 이 앞선 실제 observation_id 를 가리킨다",
                     NO_EVIDENCE, [], "candidate.produced 가 없다"))
        return out

    bad_ref, bad_txt, bad_src = [], [], []
    for c in cands:
        oid = c.get("derived_from")
        o = s.obs.get(oid)
        if o is None or o["seq"] > c["seq"]:
            bad_ref.append(c["seq"])
            continue
        txt = s.obs_text(oid)
        if txt is None or c.get("value") not in txt:
            bad_txt.append(c["seq"])
        if str(o.get("source_ref", "")).startswith("model:"):
            bad_src.append(c["seq"])
    out.append(P("S7.1", "candidate.produced.derived_from 이 앞선 실제 observation_id 를 가리킨다",
                 TRUE if not bad_ref else FALSE, bad_ref[:5]))
    out.append(P("S7.2", "그 관찰의 기록된 바이트 안에 후보 문자열이 실제로 들어 있다",
                 TRUE if not bad_txt else FALSE, bad_txt[:5],
                 "" if not bad_txt else "관찰 본문에서 후보 문자열을 찾지 못했다"))
    out.append(P("S7.3", "출처가 모델 메시지를 가리키면 FAIL",
                 TRUE if not bad_src else FALSE, bad_src[:5]))
    return out


def _variable_part(answer):
    """`kisia{X_Y}` 에서 `X_Y`. 중괄호가 없으면 정답 전체."""
    i, j = answer.find("{"), answer.rfind("}")
    if 0 <= i < j:
        return answer[i + 1:j]
    return answer


def _longest_common_substring(a, b):
    best = ""
    for i in range(len(a)):
        for j in range(i + len(best) + 1, len(a) + 1):
            if a[i:j] in b:
                best = a[i:j]
            else:
                break
    return best


def _assembly_verified(s, answer, o, hset):
    """관찰 o 안의 정답이 **worker 가 앞선 관찰들에서 조립한 것**임을 검증한다.

    CHECKER.md §3 의 S7/S8 판정이 이 함수다. `candidate.provenance` 의 선언을
    **믿지 않고 검증한다** — 라벨은 증거가 아니다(§0.1-3). 선언이 없으면 면제도 없다.

    반환: 성공하면 (assembled_id, [(part_obs_seq, 기여한 부분문자열), ...]), 아니면 None
    """
    V = _variable_part(answer)
    for pv in s.t("candidate.provenance"):
        if pv.get("assembled_in_observation") != o.get("observation_id"):
            continue
        parts = pv.get("part_observations") or []
        ids = []
        for p in parts:
            pid = p.get("observation_id") if isinstance(p, dict) else p
            if pid is not None and pid not in ids:
                ids.append(pid)
        if len(ids) < 2:
            continue
        contrib, ok = [], True
        for pid in ids:
            po = s.obs.get(pid)
            if po is None or po["seq"] >= o["seq"] or po["observation_id"] in hset:
                ok = False
                break
            txt = po.get("shown")
            if not isinstance(txt, str):
                ok = False
                break
            piece = _longest_common_substring(V, txt)
            if len(piece) < 2:
                ok = False
                break
            contrib.append((po["seq"], piece))
        if ok and len({c[1] for c in contrib}) == len(contrib):
            return (pv["seq"], contrib)
    return None


def s8(s):
    out = []
    vs = s.t("verification.completed")
    if not vs:
        out.append(P("S8.1", "verification.completed.verifier_id != solver id 이고 "
                             "verifier 가 후보의 프로세스 트리 밖에서 돈다",
                     NO_EVIDENCE, [], "verification.completed 가 없다"))
    else:
        bad = [v for v in vs
               if not external_checker(v.get("verifier_id"), s.arm_id)
               or not v.get("verifier_process")]
        out.append(P("S8.1", "verifier_id != solver id 이고 verifier 가 후보 프로세스 트리 밖",
                     TRUE if not bad else FALSE, [v["seq"] for v in bad[:5]] or
                     [v["seq"] for v in vs]))

    answer = s.verified_answer()
    if answer is None:
        out.append(P("S8.2a", "정답 문자열이 환경이 준 관찰 어디에도 나타나지 않는다",
                     NO_EVIDENCE, [],
                     "verdict=true 인 검증이 없어 이 스트림에는 확정된 정답 문자열이 없다"))
    else:
        V = _variable_part(answer)
        hits = [o for o in s.t("observation.recorded")
                if isinstance(o.get("shown"), str)
                and (answer in o["shown"] or V in o["shown"])]
        hset = {o["observation_id"] for o in hits}
        undrv, proof = [], []
        for o in hits:
            pr = _assembly_verified(s, answer, o, hset)
            if pr is None:
                undrv.append(o["seq"])
            else:
                proof.append((o["seq"], pr[1]))
        out.append(P("S8.2a",
                     "정답(또는 그 가변부)을 담은 모든 관찰이 worker 가 **앞선 둘 이상의 관찰에서 "
                     "조립한 것**임이 검증된다 — 환경이 준 관찰에는 정답이 없다",
                     TRUE if not undrv else FALSE,
                     undrv[:5] or [h["seq"] for h in hits],
                     ("적중 %d건, 전부 조립 검증됨 %s" % (len(hits), proof[:3])) if not undrv
                     else "조립으로 설명되지 않는 적중: seq %s" % undrv[:5]))

    sweep = s.t("answer.sweep")
    if not sweep:
        out.append(P("S8.2b", "정답 문자열이 input.bound.files[] 내용·모든 artifact·"
                              "컨테이너의 /input·/work 에 없다 (스트림 밖 스윕)",
                     NO_EVIDENCE, [],
                     "봉투에 스윕 결과를 나르는 이벤트가 없다 — CHECKER.md §4 개정 A-3"))
    else:
        w = sweep[0]
        ok = (w.get("hits") == 0
              and set(w.get("surfaces") or []) >= {"input_files", "artifacts",
                                                   "container:/input", "container:/work"}
              and external_checker(w.get("checked_by"), s.arm_id))
        out.append(P("S8.2b", "스윕 결과: 네 표면 전부 적중 0, 외부 검사기가 확인",
                     TRUE if ok else FALSE, [w["seq"]]))

    leak = []
    for v in vs:
        for k in v:
            if k in ("verdict", "verifier_id", "candidate_digest", "verifier_process"):
                continue
            if re.search(r"answer|flag|expected|solution", k, re.I):
                leak.append((v["seq"], k))
    out.append(P("S8.3", "후보가 받는 것은 판정뿐이다 — 정답도, 정답의 해시도 받지 않는다",
                 TRUE if not leak else FALSE, [l[0] for l in leak[:5]],
                 "" if not leak else "의심 필드 %s" % leak[:3]))

    false_v = [v for v in vs if v.get("verdict") is False]
    out.append(P("S8.4", "P-S8-a  일부러 틀린 후보를 넣어 verdict == false 를 확인했다",
                 TRUE if false_v else NO_EVIDENCE, [v["seq"] for v in false_v],
                 "" if false_v else "verdict=false 인 검증이 이 스트림에 없다", probe="a"))
    return out


def s9(s, judgment_digest=None):
    out = []
    st = s.started
    if st is None:
        out.append(P("S9.1", "attempt.started 의 통제 블록이 §1.2 항목을 전부 포함한다",
                     FALSE, [], "attempt.started 가 없다"))
    else:
        miss = [k for k in CONTROL_BLOCK_KEYS if k not in st]
        out.append(P("S9.1", "attempt.started 의 통제 블록이 §1.2 항목 %d개를 전부 포함한다"
                     % len(CONTROL_BLOCK_KEYS),
                     TRUE if not miss else FALSE, [st["seq"]],
                     "" if not miss else "결손: %s" % miss))

    seqs = [e.get("seq") for e in s.events]
    ok = seqs == list(range(1, len(s.events) + 1))
    out.append(P("S9.2", "seq 가 1부터 빈틈없다", TRUE if ok else FALSE, []))

    pairs = [("model.requested", "model.completed"),
             ("tool.requested", "tool.completed")]
    bad = []
    for a, b in pairs:
        na, nb = len(s.t(a)), len(s.t(b))
        if na != nb:
            bad.append("%s %d != %s %d" % (a, na, b, nb))
    out.append(P("S9.3", "모든 *.requested 에 짝이 있다",
                 TRUE if not bad else FALSE, [], "; ".join(bad)))
    out.append(P("S9.3x", "짝짓기가 상관 id 가 아니라 개수로만 확인된다 — 동시 연산이 "
                          "끼어들면 이 확인은 무력하다", OUT_OF_STREAM, [],
                 "CHECKER.md §4 개정 A-2 (op_id)"))

    out.append(P("S9.4", "기록은 후보의 로그가 아니라 우리 스트림이다 — "
                         "후보의 작업 디렉터리를 지워도 남는다",
                 OUT_OF_STREAM, [],
                 "한 스트림의 성질이 아니라 수집기의 구조적 성질이다. CHECKER.md §5 에 "
                 "관측으로 기록한다"))

    out.append(P("S9.5", "P-S9-a  스트림만 다른 기계로 옮겨 통제 블록·비용·seam 판정을 "
                         "재계산해 같은 값이 나온다",
                 OUT_OF_STREAM, [],
                 "판정 digest=%s. 두 기계의 digest 를 대조하는 것은 검사기 밖의 행위이고 "
                 "CHECKER.md §5 에 관측으로 남긴다" % (judgment_digest or "(계산 전)"),
                 probe="a"))
    return out


SEAM_FUNCS = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9"]


def evaluate(s, pricing_path=None):
    res = {
        "S1": s1(s), "S2": s2(s), "S3": s3(s, pricing_path), "S4": s4(s),
        "S5": s5(s), "S6": s6(s), "S7": s7(s), "S8": s8(s),
    }
    digest_src = json.dumps(
        {k: [p.as_dict() for p in v] for k, v in sorted(res.items())},
        sort_keys=True, ensure_ascii=False)
    jd = sha256_hex(digest_src)
    res["S9"] = s9(s, jd)
    return res, jd


# --------------------------------------------------------------------------
# seam 판정 (§9.3)
# --------------------------------------------------------------------------

def seam_verdict(seam, preds, ctype, patches):
    load = LOAD_TABLE.get(ctype, {}).get(seam, [])
    if load is None:
        return "N/A", "하중표 빈칸 — 이 유형은 이 seam 에 하중을 싣지 않는다", []
    considered = [p for p in preds if p.probe is None or p.probe in load]
    false_p = [p for p in considered if p.verdict == FALSE]
    noev_p = [p for p in considered if p.verdict == NO_EVIDENCE]
    if false_p:
        seqs = sorted({q for p in false_p for q in p.seqs if q is not None})
        return ("FAIL(%s)" % seam,
                "거짓인 술어: %s" % ", ".join(p.pid for p in false_p), seqs)
    if noev_p:
        seqs = sorted({q for p in noev_p for q in p.seqs if q is not None})
        return ("FAIL(%s)[no-evidence]" % seam,
                "요구된 사실의 증거가 스트림에 없다: %s" % ", ".join(p.pid for p in noev_p),
                seqs)
    if not [p for p in considered if p.verdict in _SATISFIES]:
        return "N/A", "평가 가능한 술어가 없다", []
    if patches:
        return "PASS(patch %d)" % len(patches), "", []
    return "PASS", "", []


# --------------------------------------------------------------------------
# 음성 프로브 — "실패해야 할 때 실패했다" 를 FAIL 과 구분한다
# --------------------------------------------------------------------------

def negative_probes(s):
    """음성 프로브: "실패해야 할 때 실패했는가".

    반환 항목의 넷째 값은 **의도된 신호**로서 FAIL 이 나와야 하는 seam 목록이다.
    음성 스트림에서 그 seam 의 FAIL 은 검사기의 결함도 arm 의 결함도 아니다.
    """
    out = []
    vf = [v for v in s.t("verification.completed") if v.get("verdict") is False]
    vt = [v for v in s.t("verification.completed") if v.get("verdict") is True]
    if vf:
        out.append(("A-4 / P-S8-a", True,
                    "verdict=false 가 seq %s 에 있다%s"
                    % ([v["seq"] for v in vf],
                       " (같은 attempt 에서 뒤이어 verdict=true seq %s — verifier 가 "
                       "고무도장이 아님을 양방향으로 보인다)" % [v["seq"] for v in vt]
                       if vt else ""), []))

    opens = s.t("session.opened")
    closes = s.t("session.closed")
    if len(opens) >= 2 and closes and opens[1]["seq"] > closes[0]["seq"]:
        no_cand = not s.t("candidate.produced")
        out.append(("B-9", s.outcome == "failed" and no_cand,
                    "세션을 닫고(seq %d) 다시 열었다(seq %d). outcome=%s, "
                    "candidate.produced %d건"
                    % (closes[0]["seq"], opens[1]["seq"], s.outcome,
                       len(s.t("candidate.produced"))),
                    ["S4", "S7", "S8"]))

    hx = s.t("http.exchanged")
    breaks = [b["seq"] for a, b in zip(hx, hx[1:])
              if a.get("jar_digest_after") != b.get("jar_digest_before")]
    if breaks:
        denied = [h["seq"] for h in hx if h.get("status") in (401, 403)]
        out.append(("C-4 / P-S6-a", s.outcome == "failed" and bool(denied),
                    "항아리 연쇄가 seq %s 에서 끊겼다. 거부 응답 seq %s. outcome=%s"
                    % (breaks, denied, s.outcome),
                    ["S4", "S6", "S7", "S8"]))
    return out


# --------------------------------------------------------------------------
# 보고
# --------------------------------------------------------------------------

_MARK = {TRUE: "T", FALSE: "F", VACUOUS: "v", NO_EVIDENCE: "-", OUT_OF_STREAM: "o"}


def report(s, res, jd, ctype, verbose=True):
    lines = []
    lines.append("stream : %s" % s.path)
    lines.append("type   : %s   attempt: %s   events: %d   outcome: %s"
                 % (ctype, (s.started or {}).get("attempt_id"), len(s.events), s.outcome))
    env = check_envelope(s)
    env_bad = [p for p in env if p.verdict == FALSE]
    lines.append("envelope: %s" % ("OK" if not env_bad else
                                   "BROKEN — " + "; ".join(p.pid for p in env_bad)))
    if env_bad and verbose:
        for p in env_bad:
            lines.append("    [F] %-5s %s  seq=%s %s" % (p.pid, p.text, p.seqs, p.note))
    lines.append("")

    verdicts = {}
    npass = ntot = 0
    for seam in SEAM_FUNCS:
        v, why, seqs = seam_verdict(seam, res[seam], ctype, s.structural_patches)
        verdicts[seam] = (v, why, seqs)
        loaded = LOAD_TABLE.get(ctype, {}).get(seam, []) is not None
        if loaded:
            ntot += 1
            if v.startswith("PASS"):
                npass += 1
        head = "%-3s %s" % (seam, v)
        if why:
            head += "   <- %s" % why
        if seqs:
            head += "   seq=%s" % seqs[:8]
        lines.append(head)
        if verbose:
            load = LOAD_TABLE.get(ctype, {}).get(seam, [])
            for p in res[seam]:
                if load is not None and p.probe is not None and p.probe not in load:
                    continue
                lines.append("     [%s] %-6s %s%s%s"
                             % (_MARK[p.verdict], p.pid, p.text,
                                ("  seq=%s" % p.seqs[:6]) if p.seqs else "",
                                ("  // %s" % p.note) if p.note else ""))
    lines.append("")
    lines.append("load-table cells: %d/%d PASS" % (npass, ntot))

    negs = negative_probes(s)
    if negs:
        lines.append("")
        lines.append("negative probes (실패해야 할 때 실패했는가):")
        intended = set()
        for name, ok, why, seams in negs:
            lines.append("  %-14s %s   %s" % (name, "통과" if ok else "실패", why))
            intended |= set(seams)
        if intended:
            lines.append("  ※ 이 스트림은 음성 스트림이다. %s 의 FAIL 은 **의도된 신호**이고 "
                         "검사기·arm 의 결함이 아니다."
                         % ", ".join(sorted(i for i in intended
                                            if verdicts[i][0].startswith("FAIL"))))
    lines.append("")
    lines.append("judgment digest: %s" % jd)
    return "\n".join(lines), verdicts, npass, ntot


def s9_sufficiency(s, jd):
    """S9-SUFFICIENCY — 봉투가 S9 의 **소비자**를 먹일 수 있는가.

    seam 이 아니다. 어떤 seam 판정도 바꾸지 않는다. 최종 프로덕션은 telemetry 의 투영
    둘(라이트업 자동 작성, escalation 패킷 컴파일)을 갖고, 그 둘은 계약이 얼기 전에만
    확인할 수 있다. 여기서 재는 것은 하나뿐이다 — **골든 스트림 단독으로**(fixture 소스에
    손대지 않고) 라이트업의 다섯 요소를 재구성할 수 있는가.
    """
    out = []
    reqs, comps = s.t("tool.requested"), s.t("tool.completed")
    named = [r for r in reqs if r.get("tool")]
    out.append(P("SUF-a", "(a) 사용한 도구의 순서 — tool.requested/completed 로 복원된다",
                 TRUE if (reqs and len(named) == len(reqs) and len(reqs) == len(comps))
                 else (NO_EVIDENCE if not reqs else FALSE),
                 [r["seq"] for r in reqs[:6]],
                 "tool.requested %d / completed %d" % (len(reqs), len(comps))))

    verbatim = [r for r in reqs if r.get("args") is not None]
    outbound = [e for e in s.t("session.io") if e.get("direction") == "out"]
    outbound_blind = [e for e in outbound
                      if not any(k in e for k in ("data", "payload", "shown"))]
    script_art = [a for a in s.t("artifact.produced")
                  if str(a.get("role", "")) == "solve_script"]
    if outbound_blind:
        out.append(P("SUF-b", "(b) 실행 가능한 solve 단계 — 스트림만으로 재실행할 수 있다",
                     FALSE, [e["seq"] for e in outbound_blind[:6]],
                     "session.io(direction=out) %d건이 바이트 **수**만 싣는다. 세션에 무엇을 "
                     "보냈는지가 스트림에 없어 세션형 챌린지의 solve 단계를 재구성할 수 없다"
                     % len(outbound_blind)))
    elif reqs and len(verbatim) == len(reqs):
        out.append(P("SUF-b", "(b) 실행 가능한 solve 단계 — 스트림만으로 재실행할 수 있다",
                     TRUE, [r["seq"] for r in reqs[:4]],
                     "모든 tool.requested 가 args 원문을 싣는다"
                     + ("" if script_art else "; 단 골든 스크립트 자체를 담은 artifact 는 없다")))
    else:
        out.append(P("SUF-b", "(b) 실행 가능한 solve 단계", FALSE,
                     [r["seq"] for r in reqs if r.get("args") is None][:6],
                     "args 원문 없이 args_digest 만 있는 tool.requested 가 있다"))
    out.append(P("SUF-b2", "(b') 골든 스크립트가 artifact 로 스트림에 실려 있다",
                 TRUE if script_art else NO_EVIDENCE,
                 [a["seq"] for a in script_art],
                 "" if script_art else "role=solve_script 인 artifact.produced 가 없다"))

    obs = s.t("observation.recorded")
    noshow = [o for o in obs if not isinstance(o.get("shown"), str)
              or not o.get("shown_digest")]
    prov = s.t("candidate.provenance")
    prov_ok = bool(prov) and all(
        len({(p.get("observation_id") if isinstance(p, dict) else p)
             for p in (pv.get("part_observations") or [])}) >= 2 for pv in prov)
    out.append(P("SUF-c", "(c) 무엇을 관찰해 답에 이르렀나 — shown/shown_digest + provenance",
                 TRUE if (obs and not noshow and (prov_ok or not s.t("candidate.produced")))
                 else FALSE, [o["seq"] for o in noshow[:6]],
                 "관찰 %d건 전부 원문 기록; provenance %d건" % (len(obs), len(prov))))

    vt = [v for v in s.t("verification.completed") if v.get("verdict") is True]
    cands = s.t("candidate.produced")
    derived_ok = all(c.get("derived_from") in s.obs for c in cands) if cands else False
    out.append(P("SUF-d", "(d) 성공의 증거 — verification.completed + derived_from",
                 TRUE if (vt and derived_ok) else
                 (NO_EVIDENCE if not vt else FALSE),
                 [v["seq"] for v in vt] or [],
                 "verdict=true %d건, derived_from 해소 %s" % (len(vt), derived_ok)))

    out.append(P("SUF-e", "(e) 재현 절차 — P-S9-a 와 같다", OUT_OF_STREAM, [],
                 "판정 digest=%s. 두 기계 대조 결과는 CHECKER.md §5" % jd))
    return out


def set_determinism(streams):
    """P-S5-a 를 **집합 위에서** 평가한다.

    "같은 바이트를 두 번 넣는다"는 한 스트림 안의 두 관찰일 필요가 없다. 같은 유형의
    골든 스트림 둘이 같은 파일을 읽었다면 그것이 곧 두 번 넣은 것이다 —
    FIXTURES §4.4 가 run 사이에 fixture 바이트가 같음을 실측으로 보장한다.
    """
    groups = {}
    for s, _res, _jd in streams:
        for o in s.t("observation.recorded"):
            fd = o.get("full_digest")
            if fd:
                groups.setdefault(fd, []).append((os.path.basename(os.path.dirname(s.path))
                                                  + "/" + os.path.basename(s.path), o))
    dup = {k: v for k, v in groups.items() if len(v) > 1}
    if not dup:
        return P("S5.4", "P-S5-a  같은 바이트 -> 같은 bytes_shown·shown_digest", NO_EVIDENCE,
                 [], "집합 안에 같은 full_digest 를 갖는 관찰 쌍이 없다", probe="a")
    bad, checked = [], 0
    for fd, group in dup.items():
        checked += 1
        if len({o.get("bytes_shown") for _p, o in group}) != 1 or \
           len({o.get("shown_digest") for _p, o in group}) != 1:
            bad.extend(o["seq"] for _p, o in group)
    sample = list(dup.values())[0]
    return P("S5.4", "P-S5-a  같은 바이트 -> 같은 bytes_shown·shown_digest (집합 위에서)",
             TRUE if not bad else FALSE, bad[:5] or [o["seq"] for _p, o in sample],
             "같은 full_digest 그룹 %d개를 대조했다 (예: %s)"
             % (checked, [(p, o["seq"], o.get("bytes_shown")) for p, o in sample][:3]),
             probe="a")


def evaluate_set(streams, ctype, pricing_path=None):
    """유형 단위 집합 판정.

    §9.2.1-2 의 "골든 궤적으로 술어를 검증한다" 는 한 스트림이 아니라 그 유형의 골든
    **집합**(정상 + 음성)에 대한 요구다. 프로브 술어는 집합 안의 어느 스트림 하나가
    만족시키면 만족된 것으로 센다. 상시 술어는 모든 스트림이 만족시켜야 한다.
    """
    rank = {FALSE: 0, NO_EVIDENCE: 1, OUT_OF_STREAM: 2, VACUOUS: 3, TRUE: 4}
    # 음성 스트림(attempt 가 실패한 스트림)은 **프로브 증거**이지 seam 증거가 아니다.
    # 그 스트림들은 seam 을 일부러 깨서 fixture 가 그 seam 을 강제함을 보이는 것이므로,
    # 상시 술어를 그것들로 판정하면 "실패해야 할 때 실패했다"가 FAIL 로 둔갑한다.
    solved = [x for x in streams if x[0].outcome == "solved"] or streams
    merged = {}
    for seam in SEAM_FUNCS:
        best = {}
        for s, res, _ in streams:
            positive = any(s is x[0] for x in solved)
            for p in res[seam]:
                if p.probe is None and not positive:
                    continue
                cur = best.get(p.pid)
                if cur is None:
                    best[p.pid] = (p, s.path)
                    continue
                if p.probe is not None:
                    # 프로브: 집합 안에서 가장 강한 증거를 채택
                    if rank[p.verdict] > rank[cur[0].verdict]:
                        best[p.pid] = (p, s.path)
                else:
                    # 상시 술어: 정상 스트림 중 가장 약한 것을 채택
                    if rank[p.verdict] < rank[cur[0].verdict]:
                        best[p.pid] = (p, s.path)
        merged[seam] = [(v[0], v[1]) for v in best.values()]
    return merged


def main(argv=None):
    ap = argparse.ArgumentParser(description="KISIA spike seam checker (§2 술어)")
    ap.add_argument("streams", nargs="+")
    ap.add_argument("--type", choices=["A", "B", "C"], default=None,
                    help="유형을 강제한다. 기본값은 challenge_id 에서 유도")
    ap.add_argument("--pricing", default=None, help="config/pricing.openai.yaml")
    ap.add_argument("--set", dest="asset", action="store_true",
                    help="주어진 스트림들을 한 유형의 골든 집합으로 보고 합쳐 판정한다")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="술어 상세를 생략한다")
    ap.add_argument("--sufficiency", action="store_true",
                    help="S9-SUFFICIENCY: 봉투가 S9 소비자(라이트업)를 먹일 수 있는가. "
                         "seam 판정을 바꾸지 않는다")
    a = ap.parse_args(argv)

    loaded = []
    for path in a.streams:
        s = Stream(path)
        ctype = a.type or s.ctype
        if ctype is None:
            sys.stderr.write("유형을 판정할 수 없다: %s\n" % path)
            return 2
        res, jd = evaluate(s, a.pricing)
        loaded.append((s, res, jd, ctype))

    if a.json:
        payload = []
        for s, res, jd, ctype in loaded:
            item = {"stream": s.path, "type": ctype, "outcome": s.outcome,
                    "events": len(s.events), "judgment_digest": jd,
                    "envelope": [p.as_dict() for p in check_envelope(s)],
                    "seams": {}, "predicates": {}}
            for seam in SEAM_FUNCS:
                v, why, seqs = seam_verdict(seam, res[seam], ctype, s.structural_patches)
                item["seams"][seam] = {"verdict": v, "why": why, "seqs": seqs}
                item["predicates"][seam] = [p.as_dict() for p in res[seam]]
            item["negative_probes"] = [{"probe": n, "ok": ok, "why": why}
                                       for n, ok, why, _sm in negative_probes(s)]
            payload.append(item)
        sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return 0

    if a.sufficiency:
        sys.stdout.write("=== S9-SUFFICIENCY (seam 이 아니다. 어떤 seam 판정도 "
                         "바꾸지 않는다) ===\n")
        for s, _res, jd, ctype in loaded:
            sys.stdout.write("%s  [%s]\n" % (s.path, ctype))
            for p in s9_sufficiency(s, jd):
                sys.stdout.write("   [%s] %-6s %s%s\n"
                                 % (_MARK[p.verdict], p.pid, p.text,
                                    ("  // %s" % p.note) if p.note else ""))
        sys.stdout.write("\n")

    fail = 0
    for s, res, jd, ctype in loaded:
        text, verdicts, npass, ntot = report(s, res, jd, ctype, verbose=not a.quiet)
        sys.stdout.write(text + "\n" + "-" * 78 + "\n")
        if npass != ntot:
            fail = 1

    if a.asset:
        ctype = a.type or loaded[0][3]
        pack = [(s, res, jd) for s, res, jd, _ in loaded]
        merged = evaluate_set(pack, ctype, a.pricing)
        det = set_determinism(pack)
        merged["S5"] = [(det, "<집합>") if p.pid == "S5.4" else (p, src)
                        for p, src in merged["S5"]]
        sys.stdout.write("\n=== 유형 %s 골든 집합 판정 (%d 스트림) ===\n"
                         % (ctype, len(loaded)))
        npass = ntot = 0
        for seam in SEAM_FUNCS:
            load = LOAD_TABLE.get(ctype, {}).get(seam, [])
            if load is None:
                sys.stdout.write("%-3s N/A\n" % seam)
                continue
            preds = [p for p, _ in merged[seam] if p.probe is None or p.probe in load]
            f = [p for p in preds if p.verdict == FALSE]
            n = [p for p in preds if p.verdict == NO_EVIDENCE]
            ntot += 1
            if f:
                v = "FAIL(%s)  <- %s" % (seam, ", ".join(p.pid for p in f))
            elif n:
                v = "FAIL(%s)[no-evidence]  <- %s" % (seam, ", ".join(p.pid for p in n))
            else:
                v = "PASS"
                npass += 1
            sys.stdout.write("%-3s %s\n" % (seam, v))
            if not a.quiet:
                for p, src in sorted(merged[seam], key=lambda x: x[0].pid):
                    if p.probe is not None and p.probe not in load:
                        continue
                    label = src if src.startswith("<") else (
                        os.path.basename(os.path.dirname(src)) + "/" +
                        os.path.basename(src))
                    sys.stdout.write("     [%s] %-6s %s  <%s>\n"
                                     % (_MARK[p.verdict], p.pid, p.text, label))
        sys.stdout.write("load-table cells: %d/%d PASS\n" % (npass, ntot))
    return fail


if __name__ == "__main__":
    sys.exit(main())
