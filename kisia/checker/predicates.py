"""`spec.md` §2의 seam별 술어 — 검사기가 그대로 평가하는 형태.

각 함수는 `Sk` 하나를 맡고 `Result` 목록을 돌려준다. 술어 id 는 `spec.md` 가 붙인
것을 그대로 쓴다 — 검사기가 근거 seq 와 함께 보고하는 식별자다(§2 머리말).

**판정은 사람이 로그를 읽어서 하지 않는다**(§0.3-4). 술어가 애매해 사람 판단이
필요하면 그 술어는 아직 계약이 아니고, 그때는 판정하지 말고 멈춘다(§8-1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import pairwise
from typing import Any

from kisia.checker.fixture import Fixture
from kisia.checker.grounding import (
    DEFAULT_MAX_VARIABLE_LEN,
    Source,
    find_decomposition,
    quoted_by,
    variable_part,
)
from kisia.checker.model import Result, Stream, Verdict
from kisia.checker.pricing import Price, price_call

#: `TELEMETRY_SCHEMA.md` §2 통제 블록의 항목 전부. S9.1이 이 목록을 검사한다.
CONTROL_FIELDS: tuple[str, ...] = (
    "runtime_id",
    "vendored_components",
    "structural_patches",
    "profile",
    "provider",
    "model_id",
    "model_snapshot",
    "endpoint",
    "requested_reasoning_effort",
    "effective_reasoning_effort",
    "tool_protocol",
    "state_mode",
    "store",
    "streaming",
    "capability_probe_id",
    "attempt_timeout_s",
    "tool_timeout_s",
    "session_timeout_s",
    "token_budget",
    "usd_budget",
    "bytes_shown_limit",
    "session_concurrency_limit",
    "session_kinds",
    "max_variable_len",
    "host_id",
    "image_digest",
    "network_policy",
    "challenge_id",
    "challenge_set",
    "challenge_manifest_sha256",
    #: 개정 S-4. **소급한다** — 이 필드가 생기기 전에 발행된 스트림은 통제 블록
    #: 결손이고 S9.1 이 거짓이 된다. 재빌드-6이 그 값을 재고(저장된 A·B 10개가 전부
    #: `FAIL(S9.1)`) 운영자 결정으로 **골든 셋을 다시 돌려** 해소했다 — 옛 스트림은
    #: 이력으로 남고 판정 근거는 새 집합이다(`OBSERVATION_LEDGER.md` `O-23`).
    "provenance",
    "flag_format",
    "connectors",
    "min_grounded_segment_len",
    "max_segments",
    "probe_set_id",
    #: 개정 R5-2 / S9.4a. 이 필드가 없으면 스트림이 단가표를 지목하지 않은 것이고,
    #: 그러면 S9.4a 가 요구하는 "고정 입력을 스트림이 해시로 지목한다"가 깨진다.
    "pricing_sha256",
    #: `ADR-0003` §Consequences 의 지표 회계 라벨. **소급한다** — `provenance`(개정
    #: S-4) 와 같은 성격이고 `O-23` 이 그 선례다. 검사기는 **존재만** 본다. 값의
    #: 정합(G-1 등)은 술어가 아니라 조립기가 발행 시점에 강제한다
    #: (`kisia/runtime/telemetry/control.py` 의 `_check_accounting`).
    "accounting_label",
    "solve_k",
    "run_participants",
)

#: `EVAL_CONTRACT.md` 의 6개 통제 항목 -> 이 블록의 필드 (`TELEMETRY_SCHEMA.md` §2의 표).
EVAL_CONTRACT_ITEMS: dict[str, tuple[str, ...]] = {
    "model (id and reasoning effort)": (
        "model_id",
        "model_snapshot",
        "requested_reasoning_effort",
        "effective_reasoning_effort",
    ),
    "per-attempt timeout": ("attempt_timeout_s",),
    "token budget": ("token_budget",),
    "hardware and container image (by digest)": ("host_id", "image_digest"),
    "network policy": ("network_policy",),
    "challenge snapshot (by content hash)": ("challenge_manifest_sha256",),
}

#: S2.2(P-S2-a)가 **제외**하는 경로 — 개정 R4-1.
#:
#: 원안은 "`/work` 밖"이었고 `/input` 이 그 안에 들어가, `/input` 쓰기 하나가 S2.2 와
#: S2.3 을 동시에 만족시켰다. 그러면 `/input:ro` 만 걸고 **루트fs 는 쓰기 가능한** 구현이
#: S2 를 통과한다 — S2 의 요구문("그 밖 경로 거부")이 한 번도 시험되지 않은 채로.
S2_2_EXCLUDED: tuple[str, ...] = ("/work", "/artifacts", "/input")

#: `checked_by` / `verifier_id` 의 꼴 — `<구성요소>@<위치>(<방법>)`.
_CHECKED_BY = re.compile(r"^(?P<comp>[^@]+)@(?P<loc>[^(]+)\((?P<method>.*)\)$")
#: 토큰 경계 — `TELEMETRY_SCHEMA.md` §3.2.1 이 열거한 여덟 `@ ( ) . / - _ 공백` 그대로.
#: 비교는 대소문자를 구분하지 않는다.
_TOKEN_SPLIT = re.compile(r"[@()./\-_\s]+")


@dataclass
class Ctx:
    """술어 하나를 평가하는 데 필요한 전부."""

    stream: Stream
    fixture: Fixture | None = None
    pricing: dict[str, Price] | None = None
    #: 실제로 읽은 단가표 **바이트**의 sha256. `--pricing` 이 없으면 빈 문자열이다.
    #: S9.4a 가 이 값을 통제 블록의 `pricing_sha256` 과 대조해 보고한다.
    pricing_digest: str = ""
    #: S7의 후보 중 `|V| > max_variable_len` 이라 판정에 넣지 않은 것 (R3-3).
    undecidable_candidates: list[str] = field(default_factory=list)

    # -- 편의 --------------------------------------------------------------
    @property
    def control(self) -> dict[str, Any]:
        return self.stream.control

    def ev(self, *types: str) -> list[dict[str, Any]]:
        return self.stream.by_type(*types)

    def seq(self, e: dict[str, Any]) -> int:
        raw = e.get("seq")
        return raw if isinstance(raw, int) else -1

    @property
    def observations(self) -> list[dict[str, Any]]:
        return self.ev("observation.recorded")

    def sources_before(self, seq: int) -> list[Source]:
        """`seq` 보다 앞선 모든 `observation.recorded` 의 `shown` 바이트."""
        out = []
        for o in self.observations:
            if self.seq(o) < seq and isinstance(o.get("shown"), str):
                out.append(
                    Source(
                        ident=str(o.get("observation_id")),
                        text=str(o.get("shown")),
                        origin=f"observation @seq{self.seq(o)}",
                    )
                )
        return out

    @property
    def actor_ids(self) -> set[str]:
        """정리·검증을 **수행한** 주체의 id 들. `checked_by` 가 이들과 달라야 한다."""
        ids: set[str] = set()
        for key in ("runtime_id", "arm_id"):
            raw = self.control.get(key)
            if isinstance(raw, str) and raw:
                ids.add(raw)
        vendored = self.control.get("vendored_components")
        if isinstance(vendored, list):
            for comp in vendored:
                if isinstance(comp, dict) and isinstance(comp.get("name"), str):
                    ids.add(str(comp["name"]))
        return ids

    @property
    def flag_format(self) -> str:
        raw = self.control.get("flag_format")
        if isinstance(raw, str) and raw:
            return raw
        return self.fixture.flag_format if self.fixture else ""

    @property
    def connectors(self) -> tuple[str, ...]:
        raw = self.control.get("connectors")
        if isinstance(raw, list) and raw:
            return tuple(str(c) for c in raw)
        return self.fixture.connectors if self.fixture else ("_", "-", ":", ".")

    @property
    def min_grounded_segment_len(self) -> int:
        raw = self.control.get("min_grounded_segment_len")
        if isinstance(raw, int):
            return raw
        return self.fixture.min_grounded_segment_len if self.fixture else 4

    @property
    def max_segments(self) -> int:
        raw = self.control.get("max_segments")
        if isinstance(raw, int):
            return raw
        return self.fixture.max_segments if self.fixture else 8

    @property
    def max_variable_len(self) -> int:
        raw = self.control.get("max_variable_len")
        return raw if isinstance(raw, int) else DEFAULT_MAX_VARIABLE_LEN

    @property
    def bytes_shown_limit(self) -> int | None:
        """표시 한도. 통제 블록이 없으면 매니페스트의 `display_limit_bytes`.

        `MANIFEST.md` §2.6이 둘을 같은 값으로 규정하므로 대체가 아니라 같은 값의
        다른 출처다. 어느 쪽에서 왔는지는 근거에 적는다.
        """
        raw = self.control.get("bytes_shown_limit")
        if isinstance(raw, int):
            return raw
        return self.fixture.display_limit_bytes if self.fixture else None


# ---------------------------------------------------------------------------
# 공통 판정 도구
# ---------------------------------------------------------------------------


def external_checker_ok(value: object, actor_ids: set[str]) -> tuple[bool, str]:
    """`checked_by` / `verifier_id` 가 **외부**인가 — S2.5의 형태 규칙, R3-2.1.

    문자 단위 포함 검사를 쓰지 않는다. 토큰 경계로 자른 뒤 비교하고, 비교는
    대소문자를 구분하지 않는다. r1 A-7이 문자 포함 검사를 버린 이유는 그것이
    `g-reference@host(...)` 같은 정당한 이름을 전부 걸었기 때문이다.
    """
    if not isinstance(value, str) or not value.strip():
        return False, "값이 없다"
    m = _CHECKED_BY.match(value.strip())
    if not m:
        return False, f"꼴이 <구성요소>@<위치>(<방법>) 이 아니다: {value!r}"
    comp = m.group("comp").strip().lower()
    tokens = {t.lower() for t in _TOKEN_SPLIT.split(value) if t}
    for actor in actor_ids:
        a = actor.strip().lower()
        if not a:
            continue
        if comp == a:
            return False, f"구성요소 이름이 정리/검증 주체 {actor!r} 와 같다"
        if a in tokens:
            return False, f"주체 {actor!r} 가 독립된 토큰으로 나타난다"
    return True, ""


def _res(pid: str, v: Verdict, seqs: tuple[int, ...] = (), note: str = "") -> Result:
    return Result(pid, v, seqs, note)


# ---------------------------------------------------------------------------
# S1 — challenge 입력
# ---------------------------------------------------------------------------


def s1(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    bound = ctx.ev("input.bound")
    firsts = [
        ctx.seq(e)
        for t in ("model.requested", "tool.requested")
        for e in (ctx.stream.first(t),)
        if e is not None
    ]
    if not bound:
        out.append(_res("S1.1", Verdict.NO_EVIDENCE, (), "input.bound 가 없다"))
    elif len(bound) != 1:
        out.append(
            _res(
                "S1.1",
                Verdict.FALSE,
                tuple(ctx.seq(b) for b in bound),
                "input.bound 가 1회가 아니다",
            )
        )
    else:
        bseq = ctx.seq(bound[0])
        late = [s for s in firsts if s < bseq]
        if late:
            why = "input.bound 가 첫 요청보다 뒤에 있다"
            out.append(_res("S1.1", Verdict.FALSE, (bseq, *late), why))
        else:
            out.append(_res("S1.1", Verdict.TRUE, (bseq,)))

    out.append(_s1_2(ctx, bound))

    if "structural_patches" in ctx.control:
        out.append(
            _res(
                "S1.3",
                Verdict.TRUE,
                (ctx.seq(ctx.control),),
                f"structural_patches={ctx.control.get('structural_patches')!r}",
            )
        )
    else:
        out.append(_res("S1.3", Verdict.FALSE, (), "통제 블록에 structural_patches 가 없다"))
    return out


def _s1_2(ctx: Ctx, bound: list[dict[str, Any]]) -> Result:
    if ctx.fixture is None:
        return _res("S1.2", Verdict.NO_EVIDENCE, (), "픽스처가 없어 /input 목록을 대조할 수 없다")
    declared = ctx.fixture.inputs
    if not declared:
        # R2-16 — 매니페스트가 `inputs: []` 를 선언한 챌린지에서 files[] 가 비는 것은 위반이 아니다.
        return _res("S1.2", Verdict.VACUOUS, (), "매니페스트가 inputs: [] 를 선언한다 (R2-16)")
    if not bound:
        return _res("S1.2", Verdict.NO_EVIDENCE, (), "input.bound 가 없다")

    listed = bound[0].get("files")
    rows = listed if isinstance(listed, list) else []
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            by_name[str(row.get("path", "")).rsplit("/", 1)[-1]] = row

    bad: list[str] = []
    for want in declared:
        name = str(want.get("path", "")).rsplit("/", 1)[-1]
        got = by_name.get(name)
        if got is None:
            bad.append(f"{name}: files[] 에 없다")
            continue
        want_sha = str(want.get("sha256", "")).removeprefix("sha256:")
        got_sha = str(got.get("sha256", "")).removeprefix("sha256:")
        if want_sha != got_sha:
            bad.append(f"{name}: sha256 불일치")
        if int(want.get("bytes", -1) or -1) != int(got.get("bytes", -2) or -2):
            bad.append(f"{name}: 바이트 수 불일치")
    seqs = (ctx.seq(bound[0]),)
    if bad:
        return _res("S1.2", Verdict.FALSE, seqs, "; ".join(bad))
    return _res("S1.2", Verdict.TRUE, seqs, f"{len(declared)}개 파일 대조")


# ---------------------------------------------------------------------------
# S2 — workspace 격리
# ---------------------------------------------------------------------------


def s2(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    created = ctx.ev("workspace.created")
    if not created:
        out.append(_res("S2.1", Verdict.NO_EVIDENCE, (), "workspace.created 가 없다"))
    else:
        e = created[0]
        mounts = e.get("mounts")
        ok_mounts = isinstance(mounts, list) and bool(mounts) and all(
            isinstance(m, dict) and "path" in m and "mode" in m for m in mounts
        )
        network = e.get("network")
        ok_net = bool(network) and (isinstance(network, str | dict))
        seqs = (ctx.seq(e),)
        if ok_mounts and ok_net:
            out.append(_res("S2.1", Verdict.TRUE, seqs))
        else:
            why = [] if ok_mounts else ["mounts 가 모드와 함께 있지 않다"]
            if not ok_net:
                why.append("network 가 이름과 함께 있지 않다")
            out.append(_res("S2.1", Verdict.FALSE, seqs, "; ".join(why)))

    # **개정 R4-1** — 두 전건이 겹치지 않는다. S2.2 는 `/work`·`/artifacts`·`/input`
    # **어디에도 속하지 않는** 경로이고 S2.3 은 `/input` 이므로 배타적이다. 따라서
    # "S2.2 와 S2.3 은 서로 다른 두 쓰기를 요구한다"는 요구가 경로 규칙에서 따라 나오고,
    # 별도의 사후 검사가 필요 없다.
    out.append(_refusal_probe(ctx, "S2.2", S2_2_EXCLUDED, ()))
    out.append(_refusal_probe(ctx, "S2.3", (), ("/input",)))
    out.append(_connect_probe(ctx))
    out.append(_s2_5(ctx))
    return out


def _under(path: str, root: str) -> bool:
    """`path` 가 `root` 아래인가. **문자열 접두사가 아니라 경로 성분으로** 본다.

    `/inputx/probe` 는 `/input` 으로 시작하지만 `/input` 아래가 아니다. 접두사로
    보면 그런 경로가 S2.3 을 만족시키고 S2.2 에서는 빠진다 — 어느 술어도 재지
    못하는 구멍이 생긴다.
    """
    return path == root or path.startswith(root + "/")


def _refusal_probe(
    ctx: Ctx, pid: str, excluded: tuple[str, ...], required: tuple[str, ...]
) -> Result:
    """쓰기 거부 프로브 하나.

    `excluded` 아래 경로는 제외하고, `required` 가 비어 있지 않으면 그 아래여야 한다.
    """
    hits: list[dict[str, Any]] = []
    for e in ctx.ev("scope.refused"):
        action = str(e.get("action", ""))
        if not action.startswith("write:"):
            continue
        path = action.split(":", 1)[1]
        if any(_under(path, root) for root in excluded):
            continue
        if required and not any(_under(path, root) for root in required):
            continue
        hits.append(e)
    if not hits:
        where = " / ".join(required) if required else "그 밖 경로"
        return _res(pid, Verdict.NO_EVIDENCE, (), f"{where} 쓰기에 대한 scope.refused 가 없다")

    if pid in ("S2.2", "S2.3"):
        # "그리고 **호스트에서 확인**해 파일이 생기지 않았다" — 자기 보고로는 부족하다.
        #
        # **개정 R5-4가 S2.3 을 여기 더했다.** 원안은 S2.2 만 이 절반을 요구했고, 그래서
        # `/input` 이 실제로는 쓰기 가능한 구현이 `scope.refused` 를 내기만 하면 S2.3 을
        # 통과했다. 재빌드-4의 음성 대조가 그것을 실물로 보였다(`spec.md` §8.6).
        confirmed = [e for e in hits if e.get("host_check_file_exists") is False]
        if not confirmed:
            return _res(
                pid,
                Verdict.NO_EVIDENCE,
                tuple(ctx.seq(e) for e in hits),
                "거부는 있으나 호스트 확인(host_check_file_exists=false)이 스트림에 없다 — "
                "요구된 사실의 절반이 기록되지 않았다",
            )
        return _res(pid, Verdict.TRUE, tuple(ctx.seq(e) for e in confirmed))
    return _res(pid, Verdict.TRUE, tuple(ctx.seq(e) for e in hits))


def _connect_probe(ctx: Ctx) -> Result:
    """S2.4 — 미선언 host:port 접속을 **컨테이너 안에서** 시도해 실패했다."""
    hits = [
        e
        for e in ctx.ev("scope.refused")
        if str(e.get("action", "")).startswith("connect:")
        and str(e.get("attempted_from", "")) == "container"
    ]
    if hits:
        return _res("S2.4", Verdict.TRUE, tuple(ctx.seq(e) for e in hits))
    weaker = [e for e in ctx.ev("scope.refused") if str(e.get("action", "")).startswith("connect:")]
    if weaker:
        return _res(
            "S2.4",
            Verdict.FALSE,
            tuple(ctx.seq(e) for e in weaker),
            "connect 거부는 있으나 attempted_from=container 가 아니다 — "
            "호스트에서 대신 시도한 것은 이 술어를 만족시키지 못한다",
        )
    return _res("S2.4", Verdict.NO_EVIDENCE, (), "connect: 에 대한 scope.refused 가 없다")


def _s2_5(ctx: Ctx) -> Result:
    destroyed = ctx.ev("workspace.destroyed")
    if not destroyed:
        return _res("S2.5", Verdict.NO_EVIDENCE, (), "workspace.destroyed 가 없다")
    e = destroyed[-1]
    seqs = (ctx.seq(e),)
    survivors = e.get("surviving_processes")
    if survivors != 0:
        return _res("S2.5", Verdict.FALSE, seqs, f"surviving_processes={survivors!r}")
    ok, why = external_checker_ok(e.get("checked_by"), ctx.actor_ids)
    if not ok:
        return _res("S2.5", Verdict.FALSE, seqs, f"checked_by 가 외부가 아니다 — {why}")
    return _res("S2.5", Verdict.TRUE, seqs)


# ---------------------------------------------------------------------------
# S3 — 모델 추론
# ---------------------------------------------------------------------------


def s3(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    reqs = ctx.ev("model.requested")
    comps = ctx.ev("model.completed")
    fails = ctx.ev("model.failed")

    if not reqs:
        out.append(_res("S3.1", Verdict.VACUOUS, (), "model.requested 가 0건이다"))
    elif len(reqs) == len(comps) + len(fails):
        out.append(_res("S3.1", Verdict.TRUE, (), f"{len(reqs)}쌍"))
    else:
        out.append(
            _res(
                "S3.1",
                Verdict.FALSE,
                tuple(ctx.seq(e) for e in reqs),
                f"requested {len(reqs)} != completed {len(comps)} + failed {len(fails)}",
            )
        )

    out.append(_s3_2(ctx, reqs, comps))
    out.append(
        _res("S3.3", Verdict.OUT_OF_STREAM, (), "P-S3-a 는 두 스트림을 비교하는 교차 스트림 술어다")
    )
    out.append(_s3_4(ctx, reqs))
    out.append(_s3_5(ctx))
    return out


def _paid(
    reqs: list[dict[str, Any]], comps: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs = list(zip(reqs, comps, strict=False))
    return [
        (r, c)
        for r, c in pairs
        if int(r.get("input_tokens", 0) or 0) + int(c.get("output_tokens", 0) or 0) > 0
    ]


def _s3_2(ctx: Ctx, reqs: list[dict[str, Any]], comps: list[dict[str, Any]]) -> Result:
    paid = _paid(reqs, comps)
    if not paid:
        return _res("S3.2", Verdict.VACUOUS, (), "과금 대상 호출이 0회다")
    if ctx.pricing is None:
        return _res("S3.2", Verdict.NO_EVIDENCE, (), "--pricing 이 주어지지 않아 재계산할 수 없다")

    bad: list[str] = []
    seqs: list[int] = []
    for r, c in paid:
        model = str(r.get("model_id", ""))
        price = ctx.pricing.get(model)
        seqs.append(ctx.seq(c))
        if price is None:
            bad.append(f"seq{ctx.seq(c)}: 단가표에 {model!r} 행이 없다")
            continue
        if "cache_write_tokens" not in r:
            bad.append(f"seq{ctx.seq(r)}: cache_write_tokens 가 없어 재계산 불가 (r1 A-1)")
            continue
        want = price_call(
            price,
            input_tokens=int(r.get("input_tokens", 0) or 0),
            cached_tokens=int(r.get("cached_tokens", 0) or 0),
            cache_write_tokens=int(r.get("cache_write_tokens", 0) or 0),
            output_tokens=int(c.get("output_tokens", 0) or 0),
        )
        got = Decimal(str(c.get("usd", "0")))
        if want.quantize(Decimal("0.000000000001")) != got.quantize(Decimal("0.000000000001")):
            bad.append(f"seq{ctx.seq(c)}: 재계산 {want} != 기록 {got}")
    if bad:
        return _res("S3.2", Verdict.FALSE, tuple(seqs), "; ".join(bad[:5]))
    return _res("S3.2", Verdict.TRUE, tuple(seqs), f"{len(paid)}건 재계산 일치")


def _s3_4(ctx: Ctx, reqs: list[dict[str, Any]]) -> Result:
    thresholds = (
        {p.model: p.long_context_threshold_tokens for p in ctx.pricing.values()}
        if ctx.pricing
        else {}
    )
    over: list[dict[str, Any]] = []
    for r in reqs:
        limit = thresholds.get(str(r.get("model_id", "")))
        if limit and int(r.get("input_tokens", 0) or 0) > limit:
            over.append(r)
    if not over:
        return _res("S3.4", Verdict.VACUOUS, (), "재과금 경계를 넘긴 요청이 없다")
    unmarked = [r for r in over if not r.get("long_context_repriced")]
    if unmarked:
        return _res(
            "S3.4",
            Verdict.FALSE,
            tuple(ctx.seq(r) for r in unmarked),
            "경계를 넘겼는데 그 사실이 이벤트로 표시되지 않았다",
        )
    return _res("S3.4", Verdict.TRUE, tuple(ctx.seq(r) for r in over))


def _s3_5(ctx: Ctx) -> Result:
    """조용한 강등 금지 (R2-18). effective effort 는 선언이 아니라 관측이다.

    **r1~r6 의 이 술어는 선언끼리만 비교했다.** `requested_`·`effective_reasoning_effort`
    를 둘 다 통제 블록에서 꺼내 견주므로 **출처가 같아 어긋날 수가 없었다.** 계약
    문면은 그 반대를 요구한다 — "effective effort 는 선언이 아니라 관측이다
    (`usage...reasoning_tokens`)". `O-25`(S6.4 의 죽은 절)와 같은 미구현이고,
    개정이 아니라 그 미구현의 해소다.

    **관측 쪽은 건전한 방향만 잰다.** `reasoning_tokens > 0` 이면 추론이 일어난
    것이므로 `effective=none` 이라는 선언과 정면으로 어긋난다. 그 **반대**
    (`medium` 을 선언했는데 `reasoning_tokens=0`)는 술어로 쓰지 않는다 —
    `spec.md` S3.5 가 인용하는 `ARM_E_REPORT.md` §3.3 이 "11토큰 프로브의
    `reasoning_tokens=0` 은 effort 가 none 이라는 증거가 아니었다"를 실측으로 적었다.
    (ADR-0001 에는 그런 절이 없다 — 재빌드-7이 처음에 그렇게 잘못 인용했다.)
    접으면 정당한 run 을 실패로 만든다.
    """
    req = ctx.control.get("requested_reasoning_effort")
    eff = ctx.control.get("effective_reasoning_effort")
    if req is None and eff is None:
        return _res(
            "S3.5",
            Verdict.NO_EVIDENCE,
            (),
            "통제 블록에 requested/effective_reasoning_effort 가 없다",
        )
    if req != eff:
        return _res(
            "S3.5",
            Verdict.FALSE,
            (),
            f"requested={req!r} != effective={eff!r} — run 실패 처리",
        )

    # (a) 행동 증거 — 추론이 일어났는데 선언이 `none` 이다.
    if eff == "none":
        reasoned = [
            r for r in ctx.ev("model.requested") if int(r.get("reasoning_tokens", 0) or 0) > 0
        ]
        if reasoned:
            return _res(
                "S3.5",
                Verdict.FALSE,
                tuple(ctx.seq(r) for r in reasoned),
                f"effective=none 인데 reasoning_tokens>0 인 호출이 {len(reasoned)}건 —"
                " 선언이 관측에 반증됐다",
            )

    # (b) provider 가 되돌려 준 effort — 실으면 검사하고, 없으면 이 절은 지나간다.
    #     r1~r6 의 스트림에는 이 필드가 없다. 요구하면 그것이 `O-23` 의 소급이다.
    mismatched = [
        c
        for c in ctx.ev("model.completed")
        if c.get("effective_reasoning_effort_observed") not in (None, eff)
    ]
    if mismatched:
        got = {str(c.get("effective_reasoning_effort_observed")) for c in mismatched}
        return _res(
            "S3.5",
            Verdict.FALSE,
            tuple(ctx.seq(c) for c in mismatched),
            f"통제 블록은 effective={eff!r} 인데 provider 가 되돌려 준 값이 "
            f"{sorted(got)} 인 호출이 {len(mismatched)}건",
        )
    return _res("S3.5", Verdict.TRUE, (), f"effort={req!r}")


# ---------------------------------------------------------------------------
# S4 — 도구 실행
# ---------------------------------------------------------------------------


def s4(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    comps = ctx.ev("tool.completed")
    if not comps:
        out.append(_res("S4.1", Verdict.NO_EVIDENCE, (), "tool.completed 가 없다"))
    else:
        missing = [
            e
            for e in comps
            if "exit_code" not in e
            or not (e.get("observation_id") or e.get("artifact_ids"))
        ]
        if missing:
            out.append(
                _res(
                    "S4.1",
                    Verdict.FALSE,
                    tuple(ctx.seq(e) for e in missing),
                    "tool.completed 에 exit_code 또는 출력 연결이 없다 (r2가 exit_code 를 더했다)",
                )
            )
        else:
            out.append(_res("S4.1", Verdict.TRUE, tuple(ctx.seq(e) for e in comps)))

    out.append(_s4_2(ctx))
    out.append(_s4_3(ctx))
    out.append(_s4_4(ctx))
    return out


def _s4_2(ctx: Ctx) -> Result:
    """같은 session_id 의 session.io 가 model.completed **3개 이상**을 사이에 두고 나타난다."""
    ios = ctx.ev("session.io")
    if not ios:
        return _res("S4.2", Verdict.VACUOUS, (), "session.io 가 없다 — 세션을 여는 스트림이 아니다")
    model_seqs = [ctx.seq(e) for e in ctx.ev("model.completed")]
    by_session: dict[str, list[int]] = {}
    for e in ios:
        by_session.setdefault(str(e.get("session_id")), []).append(ctx.seq(e))
    for sid, seqs in by_session.items():
        lo, hi = min(seqs), max(seqs)
        between = [s for s in model_seqs if lo < s < hi]
        if len(between) >= 3:
            return _res(
                "S4.2",
                Verdict.TRUE,
                (lo, hi),
                f"{sid}: 사이 model.completed {len(between)}개",
            )
    worst = max(
        (
            len([s for s in model_seqs if min(v) < s < max(v)])
            for v in by_session.values()
        ),
        default=0,
    )
    return _res(
        "S4.2",
        Verdict.FALSE,
        (),
        f"어느 세션도 model.completed 3개를 가로지르지 않는다 (최대 {worst})",
    )


def _s4_3(ctx: Ctx) -> Result:
    ex = ctx.ev("http.exchanged")
    if len(ex) < 2:
        return _res("S4.3", Verdict.VACUOUS, (), f"http.exchanged 가 {len(ex)}건이다")
    initial = str(ex[0].get("jar_digest_before", ""))
    broken: list[int] = []
    for a, b in pairwise(ex):
        if str(a.get("jar_digest_after", "")) != str(b.get("jar_digest_before", "")):
            broken.append(ctx.seq(b))
    if broken:
        return _res(
            "S4.3",
            Verdict.FALSE,
            tuple(broken),
            "jar_digest_after(n) != jar_digest_before(n+1)",
        )
    if all(str(e.get("jar_digest_after", "")) == initial for e in ex):
        return _res(
            "S4.3",
            Verdict.FALSE,
            (ctx.seq(ex[-1]),),
            "항아리가 초기값에서 움직이지 않았다",
        )
    return _res("S4.3", Verdict.TRUE, (ctx.seq(ex[0]), ctx.seq(ex[-1])))


def _s4_4(ctx: Ctx) -> Result:
    """P-S4-a — 자식을 만드는 명령을 죽이고 **외부 검사기가** 생존 0을 확인했다.

    `descendants_killed == 0` 은 정리 능력의 증거가 아니라 **정리할 것이 없었다**는
    사실이다(`CHECKER.md` §2.1의 B 행). 그래서 1 이상을 요구한다.
    """
    seen = False
    for e in ctx.ev("session.closed", "tool.completed"):
        killed = e.get("descendants_killed")
        if not isinstance(killed, int) or killed < 1:
            continue
        seen = True
        if e.get("survivors") != []:
            return _res("S4.4", Verdict.FALSE, (ctx.seq(e),), f"survivors={e.get('survivors')!r}")
        ok, why = external_checker_ok(e.get("checked_by"), ctx.actor_ids)
        if not ok:
            return _res(
                "S4.4",
                Verdict.FALSE,
                (ctx.seq(e),),
                f"checked_by 가 외부가 아니다 — {why}",
            )
        return _res("S4.4", Verdict.TRUE, (ctx.seq(e),))
    return _res(
        "S4.4",
        Verdict.NO_EVIDENCE,
        (),
        "" if seen else "자식을 만든 뒤 죽인 기록이 없다 (descendants_killed >= 1 인 이벤트 부재)",
    )


# ---------------------------------------------------------------------------
# S5 — 실행 결과 관찰
# ---------------------------------------------------------------------------


def s5(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    limit = ctx.bytes_shown_limit
    obs = ctx.observations
    if limit is None:
        out.append(_res("S5.1", Verdict.NO_EVIDENCE, (), "bytes_shown_limit 을 알 수 없다"))
        out.append(_res("S5.2", Verdict.NO_EVIDENCE, (), "같은 이유"))
    else:
        over = [o for o in obs if int(o.get("bytes_total", 0) or 0) > limit]
        if not over:
            out.append(_res("S5.1", Verdict.VACUOUS, (), f"표시 한도({limit})를 넘는 관찰이 없다"))
            out.append(_res("S5.2", Verdict.VACUOUS, ()))
        else:
            bad = [o for o in over if o.get("truncated") is not True or not o.get("artifact_id")]
            if bad:
                out.append(
                    _res(
                        "S5.1",
                        Verdict.FALSE,
                        tuple(ctx.seq(o) for o in bad),
                        "한도를 넘었는데 truncated=true 또는 artifact_id 가 없다",
                    )
                )
            else:
                out.append(_res("S5.1", Verdict.TRUE, tuple(ctx.seq(o) for o in over)))
            produced = {
                str(a.get("artifact_id")): a for a in ctx.ev("artifact.produced") if a.get("sha256")
            }
            missing = [o for o in over if str(o.get("artifact_id")) not in produced]
            if missing:
                out.append(
                    _res(
                        "S5.2",
                        Verdict.FALSE,
                        tuple(ctx.seq(o) for o in missing),
                        "artifact_id 에 대응하는 artifact.produced(sha256 포함)가 없다",
                    )
                )
            else:
                out.append(_res("S5.2", Verdict.TRUE, tuple(ctx.seq(o) for o in over)))

    out.append(_s5_3(ctx))
    out.append(_s5_4(ctx))
    out.append(_s5_5(ctx))
    return out


def _s5_3(ctx: Ctx) -> Result:
    known: set[str] = set()
    dangling: list[int] = []
    for e in ctx.stream:
        t = e.get("type")
        if t == "observation.recorded":
            known.add(str(e.get("observation_id")))
        elif t == "model.requested":
            ids = e.get("observation_ids")
            if isinstance(ids, list):
                for oid in ids:
                    if str(oid) not in known:
                        dangling.append(ctx.seq(e))
                        break
    if dangling:
        return _res(
            "S5.3",
            Verdict.FALSE,
            tuple(dangling),
            "model.requested 가 기록되지 않은 관찰을 가리킨다",
        )
    used = any(e.get("observation_ids") for e in ctx.ev("model.requested"))
    if not used:
        return _res("S5.3", Verdict.VACUOUS, (), "observation_ids 를 실은 model.requested 가 없다")
    return _res("S5.3", Verdict.TRUE, ())


def _s5_4(ctx: Ctx) -> Result:
    """P-S5-a 결정론. 한 스트림 안의 두 관찰일 필요는 없다 — 집합 판정이 해소한다."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for o in ctx.observations:
        digest = str(o.get("full_digest", ""))
        if digest:
            groups.setdefault(digest, []).append(o)
    pairs = {k: v for k, v in groups.items() if len(v) >= 2}
    if not pairs:
        return _res(
            "S5.4",
            Verdict.NO_EVIDENCE,
            (),
            "같은 full_digest 를 갖는 관찰 쌍이 이 스트림에 없다",
        )
    for digest, members in pairs.items():
        shown = {int(m.get("bytes_shown", -1) or -1) for m in members}
        sd = {str(m.get("shown_digest", "")) for m in members}
        if len(shown) != 1 or len(sd) != 1:
            return _res(
                "S5.4",
                Verdict.FALSE,
                tuple(ctx.seq(m) for m in members),
                f"full_digest {digest[:16]}… 인데 bytes_shown/shown_digest 가 다르다",
            )
    return _res("S5.4", Verdict.TRUE, tuple(ctx.seq(m) for v in pairs.values() for m in v))


def _s5_5(ctx: Ctx) -> Result:
    """P-S5-b (R2-5) — **하니스가** 표시 한도를 넘는 관찰을 강제로 생산했다.

    행사 표시는 `source_ref` 가 `probe:P-S5-b` 로 시작하는 것이다. 에이전트가
    고른 도구가 우연히 절단을 낸 것과 하니스가 강제한 것은 다른 사실이고, 접으면
    R2-5가 만들어진 이유가 사라진다.
    """
    forced = [
        o
        for o in ctx.observations
        if str(o.get("source_ref", "")).startswith("probe:P-S5-b") and o.get("truncated") is True
    ]
    if forced:
        return _res("S5.5", Verdict.TRUE, tuple(ctx.seq(o) for o in forced))
    return _res(
        "S5.5",
        Verdict.NO_EVIDENCE,
        (),
        "P-S5-b 가 이 스트림에 없다 — S5는 증거 없음(FAIL)",
    )


# ---------------------------------------------------------------------------
# S6 — 상태 유지
# ---------------------------------------------------------------------------


def s6(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    snaps = ctx.ev("state.snapshot")
    turns = len(ctx.ev("model.requested"))
    if turns == 0:
        out.append(_res("S6.1", Verdict.VACUOUS, (), "모델 턴이 없다"))
    elif len(snaps) >= turns:
        out.append(_res("S6.1", Verdict.TRUE, (), f"turn {turns} / state.snapshot {len(snaps)}"))
    else:
        out.append(
            _res("S6.1", Verdict.FALSE, (), f"turn {turns} 인데 state.snapshot 이 {len(snaps)}개다")
        )

    opened = ctx.ev("session.opened")
    exchanges = ctx.ev("http.exchanged")
    # R2-6 공허참 봉쇄 — 하중표가 S6을 싣는 유형에서 상태가 없다는 것 자체가 FAIL 이다.
    blockade = not opened and len(exchanges) < 2
    out.append(_s6_2(ctx, snaps, opened, blockade))
    out.append(_s6_3(ctx))
    out.append(_s6_4(ctx, exchanges, blockade))
    out.append(_s6_5(ctx))
    out.append(
        _res(
            "S6.6",
            Verdict.FALSE if blockade else Verdict.TRUE,
            (),
            "세션 0개 · 항아리 연쇄 0건 — S6.2/S6.4 는 공허참이 아니라 증거 없음이다 (R2-6)"
            if blockade
            else "",
        )
    )
    out.append(_s6_7(ctx, snaps))
    return out


def _s6_2(
    ctx: Ctx, snaps: list[dict[str, Any]], opened: list[dict[str, Any]], blockade: bool
) -> Result:
    if not opened:
        if blockade:
            return _res("S6.2", Verdict.NO_EVIDENCE, (), "세션이 0개다 (R2-6 봉쇄)")
        # r1 A-5 — 세션을 여는 스트림에만 적용한다.
        return _res("S6.2", Verdict.VACUOUS, (), "세션을 여는 스트림이 아니다 (r1 A-5)")

    closed_at = {
        str(e.get("session_id")): ctx.seq(e) for e in ctx.ev("session.closed")
    }
    live_by_turn = {
        int(s.get("turn", 0) or 0): {str(x) for x in (s.get("live_session_ids") or [])}
        for s in snaps
    }
    problems: list[str] = []
    seqs: list[int] = []
    for op in opened:
        sid = str(op.get("session_id"))
        op_seq = ctx.seq(op)
        turn_of_open = min(
            (t for t, s in ((int(x.get("turn", 0) or 0), ctx.seq(x)) for x in snaps) if s > op_seq),
            default=None,
        )
        if turn_of_open is None:
            continue
        target = turn_of_open + 3
        if target not in live_by_turn:
            continue  # turn n+3 이 없다 — 이 스트림에서 평가할 대상이 아니다
        close_seq = closed_at.get(sid)
        snap_seq = next(
            (ctx.seq(s) for s in snaps if int(s.get("turn", 0) or 0) == target), None
        )
        if close_seq is not None and snap_seq is not None and close_seq < snap_seq:
            continue  # 그 사이에 닫았다
        if sid not in live_by_turn[target]:
            problems.append(f"{sid}: turn {target} 의 live 집합에 없다")
            seqs.append(snap_seq or op_seq)
    if problems:
        return _res("S6.2", Verdict.FALSE, tuple(seqs), "; ".join(problems))
    return _res("S6.2", Verdict.TRUE, tuple(ctx.seq(o) for o in opened))


def _s6_3(ctx: Ctx) -> Result:
    """모델이 참조한 세션이 live 에 없으면 `scope.refused(unknown_session)` 을 낸다."""
    live: set[str] = set()
    refusals = {
        ctx.seq(e)
        for e in ctx.ev("scope.refused")
        if "unknown_session" in str(e.get("reason_code", ""))
        or "unknown_session" in str(e.get("action", ""))
    }
    silent: list[int] = []
    referenced_dead = False
    for e in ctx.stream:
        t = e.get("type")
        if t == "session.opened":
            live.add(str(e.get("session_id")))
        elif t == "session.closed":
            live.discard(str(e.get("session_id")))
        elif t == "session.io":
            sid = str(e.get("session_id"))
            if sid not in live:
                referenced_dead = True
                near = {ctx.seq(e) - 1, ctx.seq(e), ctx.seq(e) + 1}
                if not (near & refusals):
                    silent.append(ctx.seq(e))
    if silent:
        return _res(
            "S6.3",
            Verdict.FALSE,
            tuple(silent),
            "live 에 없는 session_id 를 참조했는데 scope.refused(unknown_session) 이 없다",
        )
    if not referenced_dead and not refusals:
        return _res("S6.3", Verdict.VACUOUS, (), "죽은 세션을 참조한 사례가 없다")
    return _res("S6.3", Verdict.TRUE, tuple(sorted(refusals)))


def _s6_4(ctx: Ctx, exchanges: list[dict[str, Any]], blockade: bool) -> Result:
    if len(exchanges) < 3:
        if blockade:
            return _res("S6.4", Verdict.NO_EVIDENCE, (), "항아리 연쇄가 0건이다 (R2-6 봉쇄)")
        return _res("S6.4", Verdict.VACUOUS, (), f"http.exchanged 가 {len(exchanges)}건이다")
    seqs = (ctx.seq(exchanges[0]), ctx.seq(exchanges[2]))
    #: 계약 문면은 "**세 번째 요청**의 `jar_digest_before` 가 **첫 요청 이후**의 값과
    #: 이어진다"이므로 고리가 **둘**이다. 첫 고리를 S4.3 에 맡기면 S6.4 는 자기 문장을
    #: 스스로 재지 못하고, 두 술어가 같은 집합에 있는 동안에만 우연히 성립한다.
    #: 재빌드-6 이 둘째 고리만 보는 구현을 고쳤다 (`O-25`).
    def _link(a: int, b: int) -> bool:
        return str(exchanges[a].get("jar_digest_after", "")) == str(
            exchanges[b].get("jar_digest_before", "")
        )

    links = (_link(0, 1), _link(1, 2))
    if not all(links):
        return _res(
            "S6.4",
            Verdict.FALSE,
            seqs,
            "세 번째 요청의 항아리가 첫 요청 이후와 이어지지 않는다",
        )
    return _res("S6.4", Verdict.TRUE, seqs)


def _s6_5(ctx: Ctx) -> Result:
    """P-S6-a (R2-7) — 상태 소재를 버렸을 때 **유실이 관측된다**. 실패를 요구하지 않는다."""
    ex = ctx.ev("http.exchanged")
    for a, b in pairwise(ex):
        if str(a.get("jar_digest_after", "")) != str(b.get("jar_digest_before", "")):
            return _res("S6.5", Verdict.TRUE, (ctx.seq(b),), "(a) 항아리 연쇄가 끊겼다")
    lost = [e for e in ctx.ev("scope.refused") if "state_lost" in str(e.get("reason_code", ""))]
    if lost:
        return _res(
            "S6.5",
            Verdict.TRUE,
            tuple(ctx.seq(e) for e in lost),
            "(b) scope.refused(state_lost)",
        )
    snaps = ctx.ev("state.snapshot")
    for a, b in pairwise(snaps):
        prev = {str(x) for x in (a.get("live_session_ids") or [])}
        now = {str(x) for x in (b.get("live_session_ids") or [])}
        gone = prev - now
        if gone and not any(
            str(e.get("session_id")) in gone
            for e in ctx.ev("session.closed")
            if ctx.seq(a) < ctx.seq(e) < ctx.seq(b)
        ):
            return _res(
                "S6.5",
                Verdict.TRUE,
                (ctx.seq(b),),
                "(c) state.snapshot 의 항목이 사라졌다",
            )
    return _res("S6.5", Verdict.NO_EVIDENCE, (), "P-S6-a 의 세 신호 중 어느 것도 스트림에 없다")


def _s6_7(ctx: Ctx, snaps: list[dict[str, Any]]) -> Result:
    """조용한 축출 금지 (R2-8)."""
    silent: list[int] = []
    for a, b in pairwise(snaps):
        prev = {str(x) for x in (a.get("live_session_ids") or [])}
        now = {str(x) for x in (b.get("live_session_ids") or [])}
        for sid in prev - now:
            accounted = any(
                str(e.get("session_id")) == sid and ctx.seq(a) < ctx.seq(e) < ctx.seq(b)
                for e in ctx.ev("session.closed", "scope.refused")
            )
            if not accounted:
                silent.append(ctx.seq(b))
    if silent:
        return _res(
            "S6.7",
            Verdict.FALSE,
            tuple(silent),
            "session.closed / scope.refused 없이 live 집합을 떠났다",
        )
    if len(snaps) < 2 or not ctx.ev("session.opened"):
        return _res("S6.7", Verdict.VACUOUS, (), "세션이 live 집합을 떠난 사례가 없다")
    return _res("S6.7", Verdict.TRUE, ())


# ---------------------------------------------------------------------------
# S7 — flag 후보 추출
# ---------------------------------------------------------------------------


def s7(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    cands = ctx.ev("candidate.produced")
    fmt = ctx.flag_format
    if not cands:
        out.append(_res("S7.1", Verdict.VACUOUS, (), "candidate.produced 가 없다"))
        out.append(_res("S7.2", Verdict.VACUOUS, ()))
        out.append(_res("S7.3", Verdict.VACUOUS, ()))
        return out
    if not fmt:
        out.append(_res("S7.1", Verdict.NO_EVIDENCE, (), "flag_format 을 알 수 없다"))
        out.append(_res("S7.2", Verdict.NO_EVIDENCE, ()))
        out.append(_res("S7.3", Verdict.NO_EVIDENCE, ()))
        return out

    bad: list[str] = []
    good: list[int] = []
    judged = 0
    for c in cands:
        value = str(c.get("value", ""))
        cseq = ctx.seq(c)
        var = variable_part(value, fmt)
        if var is None:
            # R3-1 — 형식에 맞지 않으면 `V(c)` 가 정의되지 않고 그 후보의 술어는 거짓이다.
            judged += 1
            bad.append(f"seq{cseq}: {value!r} 가 flag_format {fmt!r} 에 맞지 않는다")
            continue
        if len(var) > ctx.max_variable_len:
            # R3-3 — 판정 불가. seam 판정에 넣지 않는다.
            ctx.undecidable_candidates.append(f"seq{cseq}: |V|={len(var)} > {ctx.max_variable_len}")
            continue
        judged += 1
        sources = ctx.sources_before(cseq)

        # (a) 인용 — 선언된 derived_from 에 대해 바이트로 검증한다.
        declared = c.get("derived_from")
        declared_ids = {str(x) for x in declared} if isinstance(declared, list) else set()
        quoted = [s for s in quoted_by(value, sources) if s in declared_ids]
        if quoted:
            good.append(cseq)
            continue

        # (b) 파생 — 선언과 무관하게 스스로 분할을 탐색한다 (S7.2).
        found = find_decomposition(
            var,
            sources,
            connectors=ctx.connectors,
            min_grounded_segment_len=ctx.min_grounded_segment_len,
            max_segments=ctx.max_segments,
        )
        if found is not None:
            good.append(cseq)
            continue
        bad.append(f"seq{cseq}: 인용도 파생도 없다 — {value!r} 는 환경에서 오지 않았다")

    if judged == 0:
        why = "판정 가능한 후보가 없다 (전부 판정 불가)"
        out.append(_res("S7.1", Verdict.NO_EVIDENCE, (), why))
    elif bad:
        out.append(_res("S7.1", Verdict.FALSE, tuple(good), "; ".join(bad[:5])))
    else:
        out.append(_res("S7.1", Verdict.TRUE, tuple(good), f"{judged}개 후보 전부 인용 또는 파생"))

    out.append(
        _res(
            "S7.2",
            Verdict.TRUE,
            (),
            "검사기의 성질이다 — method·derived_from 의 선언을 판정 입력으로 쓰지 않고 "
            "(b)를 독립적으로 탐색했다. 스트림이 이것을 깰 수 없다.",
        )
    )
    out.append(
        _res(
            "S7.3",
            Verdict.TRUE,
            (),
            "검사기의 성질이다 — 소스 집합에 관찰만 넣었다. 챌린지 입력 표면은 S8(i) 전용이다.",
        )
    )
    return out


# ---------------------------------------------------------------------------
# S8 — flag 검증
# ---------------------------------------------------------------------------


def s8(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    out.append(_s8_1(ctx))
    out.extend(_s8_2(ctx))
    out.append(_s8_3(ctx))
    out.append(_s8_4(ctx))
    out.append(_s8_5(ctx))
    return out


def _s8_1(ctx: Ctx) -> Result:
    vers = ctx.ev("verification.completed")
    if not vers:
        return _res("S8.1", Verdict.NO_EVIDENCE, (), "verification.completed 가 없다")
    for v in vers:
        ok, why = external_checker_ok(v.get("verifier_id"), ctx.actor_ids)
        if not ok:
            return _res(
                "S8.1",
                Verdict.FALSE,
                (ctx.seq(v),),
                f"verifier_id 가 외부가 아니다 — {why}",
            )
    return _res("S8.1", Verdict.TRUE, tuple(ctx.seq(v) for v in vers))


def _answer_of(ctx: Ctx) -> str | None:
    """이 attempt 의 정답 문자열. 픽스처가 있으면 거기서, 없으면 검증된 후보에서."""
    if ctx.fixture and ctx.fixture.flag:
        return ctx.fixture.flag
    verified = {
        str(v.get("candidate_digest", ""))
        for v in ctx.ev("verification.completed")
        if v.get("verdict") is True
    }
    if not verified:
        return None
    import hashlib

    for c in ctx.ev("candidate.produced"):
        value = str(c.get("value", ""))
        digest = "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
        if digest in verified or digest.removeprefix("sha256:") in {
            d.removeprefix("sha256:") for d in verified
        }:
            return value
    return None


def _s8_2(ctx: Ctx) -> list[Result]:
    """(i) 조립 검증 — R2-2, R3-4."""
    answer = _answer_of(ctx)
    if answer is None:
        return [_res(
            "S8.2",
            Verdict.NO_EVIDENCE,
            (),
            "정답 문자열을 알 수 없다 (픽스처·검증 후보 둘 다 없다)",
        )]
    fmt = ctx.flag_format
    var = variable_part(answer, fmt) if fmt else None
    if var is None:
        return [_res("S8.2", Verdict.NO_EVIDENCE, (), f"정답 {answer!r} 의 가변부를 얻을 수 없다")]

    leaks = [
        o
        for o in ctx.observations
        if isinstance(o.get("shown"), str) and (answer in str(o["shown"]) or var in str(o["shown"]))
    ]
    if not leaks:
        return [_res("S8.2", Verdict.VACUOUS, (), "정답이나 그 가변부를 담은 관찰이 없다")]

    # 스윕 표면 중 part_hits 가 기록된 것을 소스로 더한다 (R2-2).
    parts = ctx.fixture.parts if ctx.fixture else {}
    sweep_sources: list[Source] = []
    for sw in ctx.ev("answer.sweep"):
        surfaces = sw.get("surfaces")
        for s in surfaces if isinstance(surfaces, list) else []:
            if not isinstance(s, dict):
                continue
            name = str(s.get("surface", "?"))
            for hit in s.get("part_hits") or []:
                if not isinstance(hit, dict) or int(hit.get("count", 0) or 0) < 1:
                    continue
                pid = str(hit.get("part"))
                text = parts.get(pid)
                if text is None:
                    continue
                sweep_sources.append(
                    Source(ident=f"surface:{name}#{pid}", text=text, origin=f"answer.sweep {name}")
                )

    failures: list[str] = []
    ok_seqs: list[int] = []
    for o in leaks:
        oseq = ctx.seq(o)
        sources = ctx.sources_before(oseq) + sweep_sources
        whole = [s.ident for s in sources if var in s.text]
        if whole:
            failures.append(f"seq{oseq}: 단일 소스 {whole[0]} 가 V 를 통째로 담고 있다")
            continue
        found = find_decomposition(
            var,
            sources,
            connectors=ctx.connectors,
            min_grounded_segment_len=ctx.min_grounded_segment_len,
            max_segments=ctx.max_segments,
            require_distinct_sources=2,
        )
        if found is None:
            failures.append(f"seq{oseq}: 조립 파생이 없다 — 정답의 최초 유출")
        else:
            ok_seqs.append(oseq)
    if failures:
        return [_res(
            "S8.2",
            Verdict.FALSE,
            tuple(ctx.seq(o) for o in leaks),
            "; ".join(failures[:5]),
        )]
    return [_res("S8.2", Verdict.TRUE, tuple(ok_seqs), f"{len(ok_seqs)}개 관찰에서 조립 확인")]


def _s8_3(ctx: Ctx) -> Result:
    sweeps = ctx.ev("answer.sweep")
    if not sweeps:
        return _res(
            "S8.3",
            Verdict.NO_EVIDENCE,
            (),
            "answer.sweep 이 없다 — 스윕 없이 만족되지 않는다 (§0.3-2)",
        )
    hits: list[str] = []
    for sw in sweeps:
        surfaces = sw.get("surfaces")
        for s in surfaces if isinstance(surfaces, list) else []:
            if isinstance(s, dict) and int(s.get("whole_hits", 0) or 0) > 0:
                hits.append(f"{s.get('surface')}: whole_hits={s.get('whole_hits')}")
        ok, why = external_checker_ok(sw.get("checked_by"), ctx.actor_ids)
        if not ok:
            return _res(
                "S8.3",
                Verdict.FALSE,
                (ctx.seq(sw),),
                f"checked_by 가 외부가 아니다 — {why}",
            )
    if hits:
        return _res("S8.3", Verdict.FALSE, tuple(ctx.seq(s) for s in sweeps), "; ".join(hits))
    return _res("S8.3", Verdict.TRUE, tuple(ctx.seq(s) for s in sweeps))


def _s8_4(ctx: Ctx) -> Result:
    """solver 가 받는 것은 판정뿐이다 — 정답도, 정답의 해시도 받지 않는다.

    **경계를 직접 잰다.** verifier 에서 solver 로 넘어간 것의 기록이
    `verification.completed` 자신이므로, 그 이벤트의 **값**들이 정답이나 정답의
    해시를 나르는지 본다. 이름으로 의심 필드를 찾지 않는다 — 라벨이 아니라
    바이트가 판정한다(§0.3-3).

    `candidate_digest` 는 예외다. 후보가 맞는 순간 후보의 해시와 정답의 해시는
    같은 값이므로, 그것을 위반으로 세면 성공한 모든 attempt 가 FAIL 이 된다.

    틀린 판정이 있으면 그 뒤 solver 가 보는 표면에 정답의 해시가 나타나지
    않았는지도 함께 본다 — 판정 이후에 새로 들어온 것만이 verifier 에서 온 것일
    수 있기 때문이다.
    """
    import hashlib

    vers = ctx.ev("verification.completed")
    if not vers:
        return _res("S8.4", Verdict.NO_EVIDENCE, (), "verification.completed 가 없다")
    answer = _answer_of(ctx)
    if answer is None:
        return _res("S8.4", Verdict.NO_EVIDENCE, (), "정답 문자열을 알 수 없다")
    ahash = hashlib.sha256(answer.encode("utf-8")).hexdigest()

    leaked: list[str] = []
    seqs: list[int] = []
    for v in vers:
        seqs.append(ctx.seq(v))
        for key, value in v.items():
            if key == "candidate_digest":
                continue
            blob = repr(value)
            if answer in blob or ahash in blob:
                leaked.append(f"seq{ctx.seq(v)}.{key}")

    negatives = [v for v in vers if v.get("verdict") is False]
    if negatives:
        after = ctx.seq(negatives[0])
        for e in ctx.stream:
            if ctx.seq(e) <= after:
                continue
            if e.get("type") not in (
                "observation.recorded",
                "session.io",
                "tool.requested",
                "model.requested",
            ):
                continue
            if ahash in repr(e):
                leaked.append(f"seq{ctx.seq(e)}: 틀린 판정 뒤 solver 표면에 정답 해시")

    if leaked:
        return _res("S8.4", Verdict.FALSE, tuple(seqs), "; ".join(leaked[:5]))
    return _res("S8.4", Verdict.TRUE, tuple(seqs), f"{len(vers)}건의 판정이 verdict 만 넘긴다")


def _s8_5(ctx: Ctx) -> Result:
    negatives = [v for v in ctx.ev("verification.completed") if v.get("verdict") is False]
    if not negatives:
        return _res("S8.5", Verdict.NO_EVIDENCE, (), "P-S8-a (음성 프로브)를 돌리지 않았다")
    return _res("S8.5", Verdict.TRUE, tuple(ctx.seq(v) for v in negatives))


# ---------------------------------------------------------------------------
# S9 — telemetry 저장
# ---------------------------------------------------------------------------


def s9(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    control = ctx.control
    missing = [f for f in CONTROL_FIELDS if f not in control]
    unmet = [
        name
        for name, fields in EVAL_CONTRACT_ITEMS.items()
        if any(f not in control for f in fields)
    ]
    if missing:
        out.append(
            _res(
                "S9.1",
                Verdict.FALSE,
                (ctx.seq(control),),
                f"통제 블록 {len(CONTROL_FIELDS) - len(missing)}/{len(CONTROL_FIELDS)}. "
                f"빠진 것: {' '.join(missing)}"
                + (f" | EVAL_CONTRACT 미충족: {unmet}" if unmet else ""),
            )
        )
    else:
        note = f"통제 블록 {len(CONTROL_FIELDS)}/{len(CONTROL_FIELDS)}, EVAL_CONTRACT 6/6"
        out.append(_res("S9.1", Verdict.TRUE, (ctx.seq(control),), note))

    # 여기까지 왔다는 것은 load_stream 의 첫 관문을 통과했다는 뜻이다.
    out.append(_res("S9.2", Verdict.TRUE, (1, len(ctx.stream.events)), "seq 1..N 빈틈 없음"))
    out.append(_s9_3(ctx))
    out.append(
        _res(
            "S9.4",
            Verdict.OUT_OF_STREAM,
            (),
            "수집기의 구조적 성질이므로 한 스트림에서 평가하지 않는다",
        )
    )
    out.append(_s9_4a(ctx))
    out.append(
        _res("S9.5", Verdict.OUT_OF_STREAM, (), "P-S9-a 는 두 기계의 판정 digest 를 대조한다")
    )
    return out


def _s9_4a(ctx: Ctx) -> Result:
    """스트림 밖 고정 입력 둘이 스트림의 지목과 같은가 — 개정 R5-2 / `spec.md` S9.4a.

    **`스트림 밖`으로 보고한다.** S9.4 와 같은 성격이다 — 재는 대상이 스트림의
    성질이 아니라 **검사기가 무엇을 입력으로 썼는가**이기 때문이다. 따라서 이
    술어는 어떤 seam 판정도 움직이지 않는다(`spec.md` §6.2 — 스트림 밖은 세지
    않는다). 움직이는 것은 다른 자리다:

    - **어긋나면** 검사기가 애초에 판정을 내지 않는다(`TELEMETRY_SCHEMA.md` §2).
      그 관문은 `kisia/checker/__main__.py` 에 있고, 여기 도달한 스트림은 이미
      그 관문을 통과했다.
    - **지목이 아예 없으면** S9.1 이 통제 블록 결손으로 거짓이 되고 그 attempt 는
      폐기 대상이 된다.
    """
    control = ctx.control
    notes: list[str] = []

    pin = str(control.get("pricing_sha256", ""))
    if not pin:
        notes.append("단가표: 스트림이 지목하지 않았다 (S9.1이 잡는다)")
    elif not ctx.pricing_digest:
        notes.append(f"단가표: 지목 {pin[:12]}… — 검사기에 --pricing 이 없어 대조하지 않았다")
    else:
        notes.append(f"단가표: 지목과 일치 {ctx.pricing_digest[:12]}…")

    want = str(control.get("challenge_manifest_sha256", ""))
    if not want:
        notes.append("픽스처: 스트림이 지목하지 않았다 (S9.1이 잡는다)")
    elif ctx.fixture is None:
        notes.append(f"픽스처: 지목 {want[:12]}… — 해소하지 못했다")
    else:
        notes.append(f"픽스처: 지목과 일치 {ctx.fixture.manifest_sha256[:12]}…")

    return _res("S9.4a", Verdict.OUT_OF_STREAM, (ctx.seq(control),), " | ".join(notes))


def _s9_3(ctx: Ctx) -> Result:
    """모든 `*.requested` 에 짝이 있다. `op_id` 는 선택이 아니라 필수다 (R2-17)."""
    treqs = ctx.ev("tool.requested")
    tcomps = ctx.ev("tool.completed")
    no_op = [e for e in treqs + tcomps if not e.get("op_id")]
    if no_op:
        return _res(
            "S9.3",
            Verdict.FALSE,
            tuple(ctx.seq(e) for e in no_op[:10]),
            f"op_id 가 없는 tool.* 이벤트 {len(no_op)}건 — R2-17 이후 필수다",
        )
    req_ops = [str(e.get("op_id")) for e in treqs]
    comp_ops = [str(e.get("op_id")) for e in tcomps]
    dangling = [o for o in req_ops if o not in comp_ops]
    orphan = [o for o in comp_ops if o not in req_ops]
    if dangling or orphan:
        return _res(
            "S9.3",
            Verdict.FALSE,
            (),
            f"짝 없는 op_id — 미완료 {dangling[:5]} / 요청 없는 완료 {orphan[:5]}",
        )
    mreqs, mcomps = ctx.ev("model.requested"), ctx.ev("model.completed")
    if len(mreqs) != len(mcomps) + len(ctx.ev("model.failed")):
        return _res("S9.3", Verdict.FALSE, (), "model.requested 에 짝이 없다")
    if not treqs and not mreqs:
        return _res("S9.3", Verdict.VACUOUS, (), "*.requested 가 없다")
    return _res(
        "S9.3",
        Verdict.TRUE,
        (),
        f"tool {len(req_ops)}쌍 (op_id), model {len(mreqs)}쌍 (직렬)",
    )


SEAM_FUNCS = {
    "S1": s1,
    "S2": s2,
    "S3": s3,
    "S4": s4,
    "S5": s5,
    "S6": s6,
    "S7": s7,
    "S8": s8,
    "S9": s9,
}
