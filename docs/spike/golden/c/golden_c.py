#!/usr/bin/env python3
"""유형 C 골든 트라젝토리 + 음성 프로브 C-4.

유형 B와 무엇이 다른가: HTTP는 연결이 끊겨도 정상이다. 턴을 가로질러 살아야 하는 것은
프로세스가 아니라 **쿠키 항아리** 하나뿐이고, 그래서 항아리를 도구 안이 아니라 도구
밖(드라이버)에 둔다. 그렇게 해야 `jar_digest_before/after` 가 의미를 갖고, C-4가
"턴 사이에 항아리를 버린다"를 실제로 수행할 수 있다.

S4의 HTTP 술어 `jar_digest_after(n) == jar_digest_before(n+1)` 이 참이 되려면 요청
사이에 항아리를 건드리는 것이 없어야 하고, "그 값이 초기값과 다르다"가 참이 되려면
첫 요청이 실제로 쿠키를 세워야 한다. 아래 세 요청이 정확히 그 형태다.
"""
import re
import sys

ZONE_RE = re.compile(r"zone=([a-z0-9]{4})")
PART_RE = re.compile(r"part=([0-9a-f]{8})")

LOGIN_BODY = "user=analyst&pass=north-42"


def trajectory(g, *, probe_c4: bool = False) -> tuple[bool, str]:
    g.attempt_started("유형 C 골든 트라젝토리" + (" (음성 프로브 C-4)" if probe_c4 else ""))
    g.bind_input()
    g.create_workspace()

    # --- T1 : 로그인 ---------------------------------------------------------- #
    g.turn("로그인해서 세션 쿠키를 받는다")
    obs_login, r1 = g.http("POST", "/login", body=LOGIN_BODY)
    if r1["status"] != 200:
        return False, f"/login 이 200 이 아니다: {r1['status']}"
    mz = ZONE_RE.search(r1["body"])
    if not mz:
        return False, "/login 응답에 zone 이 없다"
    zone = mz.group(1)
    if not g.jar:
        return False, "/login 이 쿠키를 세우지 않았다 — fixture 결함"

    # --- T2 : 상태 변경 -------------------------------------------------------- #
    g.turn("쿠키를 실어 상태를 ARMED 로 바꾼다")
    _, r2 = g.http("POST", "/arm")
    if r2["status"] != 200:
        return False, f"/arm 이 200 이 아니다: {r2['status']} {r2['body']!r}"

    if probe_c4:
        # C-4 (음성) — 턴 사이에 항아리를 버린다. 성공하면 fixture 가 상태를 시험하지
        # 않는다는 뜻이고, fixture 결함이다.
        g.turn("C-4: 쿠키 항아리를 버린다")
        g.drop_jar("C-4 음성 프로브: 턴 사이에 항아리를 버린다 (SEAM_CONTRACT P-S6-a)")

        g.turn("C-4: 쿠키 없이 /vault 를 시도한다")
        _, r3 = g.http("GET", "/vault")

        # 우회로도 함께 막히는지 본다: 재로그인은 새 sid 에 상태 NEW 를 준다.
        g.turn("C-4: 재로그인으로 우회할 수 있는지 본다")
        _, r4 = g.http("POST", "/login", body=LOGIN_BODY)
        _, r5 = g.http("GET", "/vault")

        leaked = PART_RE.search(r3["body"]) or PART_RE.search(r5["body"])
        if leaked:
            g.attempt_finished("invalid", "C-4 실패: 항아리를 버리고도 part 를 얻었다")
            return False, "C-4 실패: 쿠키를 버려도 답에 도달했다 — fixture 결함"
        g.attempt_finished(
            "failed",
            f"C-4 통과: 쿠키 없이 /vault={r3['status']}, 재로그인 후 /vault={r5['status']} — part 를 얻지 못했다",
        )
        return True, f"C-4 통과 (실패해야 할 때 실패했다: {r3['status']} / {r5['status']})"

    # --- T3 : flag 조각 -------------------------------------------------------- #
    g.turn("같은 쿠키로 세 번째 요청을 보낸다")
    obs_vault, r3 = g.http("GET", "/vault")
    if r3["status"] != 200:
        return False, f"/vault 가 200 이 아니다: {r3['status']} {r3['body']!r}"
    mp = PART_RE.search(r3["body"])
    if not mp:
        return False, "/vault 응답에 part 가 없다"
    part = mp.group(1)

    # --- T4 : 조립과 제출 ------------------------------------------------------- #
    g.turn("두 관찰을 합쳐 flag 를 만들고 제출한다")
    flag = f"kisia{{{zone}_{part}}}"
    obs_asm, _, _ = g.exec(["sh", "-c", f"printf '%s\\n' '{flag}'"], "tool:assemble flag")
    g.candidate(
        flag,
        derived_from=obs_asm,
        method="kisia{<zone>_<part>}. zone 은 /login 관찰, part 는 /vault 관찰에서 왔다.",
    )
    g.em.emit(
        "candidate.provenance",
        assembled_in_observation=obs_asm,
        part_observations=[
            {"observation_id": obs_login, "part": "zone", "source": "POST /login"},
            {"observation_id": obs_vault, "part": "part", "source": "GET /vault"},
        ],
        note="S7/S8 충돌에 대한 재료. FIXTURES.md §6 참조.",
    )
    ok = g.verify(flag)
    g.attempt_finished("solved" if ok else "failed", "verifier 판정")
    return ok, "골든 C 통과" if ok else "verifier 가 골든 후보를 거부했다 — fixture 결함"


def main(g, argv: list[str]) -> tuple[bool, str]:
    return trajectory(g, probe_c4="--c4" in argv)


if __name__ == "__main__":
    print("run.py 를 통해 실행한다", file=sys.stderr)
    raise SystemExit(2)
