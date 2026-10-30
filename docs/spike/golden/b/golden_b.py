#!/usr/bin/env python3
"""유형 B 골든 트라젝토리 + 음성 프로브 B-9.

**턴이 5개인 이유는 자의적이지 않다.** S4의 지속 세션 술어는 "같은 `session_id`의
`session.io`가 **`model.completed` 3개 이상을 사이에 두고** 나타난다"이다. 관찰마다
턴 하나인 자연스러운 루프에서 세션을 만지는 턴이 k개면 첫 io 와 마지막 io 사이의
model.completed 는 k-1 개다. 따라서 3개를 만들려면 세션을 만지는 턴이 4개여야 하고,
프로토콜이 배너·HELO·ARM·READ 로 정확히 4단계인 것은 그래서다. §9.2의 "모델 턴을
최소 3회 가로질러"는 만족하고도 남는다.

세션은 `docker exec -i <worker> bash` 하나이고, TCP 연결은 그 bash 가 든 fd 3 위에
있다. bash 가 죽으면 fd 도 죽고 nonce 도 사라진다 — 세션 수명과 문제 해결 가능성이
같은 것에 매달려 있다는 뜻이고, 그것이 이 fixture 의 전부다.

`/dev/tcp` 를 쓰는 이유: worker 이미지에 netcat 을 넣지 않아도 되고, 연결이 셸
프로세스의 fd 로 **명시적으로** 표현되어 "세션이 살아 있다"가 관측 가능해진다.
"""
import re
import sys

BANNER_RE = re.compile(r"zone=([a-z0-9]{4})")
NONCE_RE = re.compile(r"nonce=([0-9a-f]{8})")
PART_RE = re.compile(r"part=([0-9a-f]{8})")


def _open_conn(s, target) -> tuple[str, str]:
    return s.run(
        f"exec 3<>/dev/tcp/{target['host']}/{target['port']}; "
        "IFS= read -r -u 3 L1; IFS= read -r -u 3 L2; printf '%s\\n%s\\n' \"$L1\" \"$L2\"",
        source_ref=f"session:{s.session_id}:connect+banner",
    )


def _say(s, line: str, ref: str) -> tuple[str, str]:
    return s.run(
        f"printf '{line}\\r\\n' >&3; IFS= read -r -u 3 R; printf '%s\\n' \"$R\"",
        source_ref=f"session:{s.session_id}:{ref}",
    )


def trajectory(g, *, probe_b9: bool = False) -> tuple[bool, str]:
    target = g.manifest["target"]
    g.attempt_started("유형 B 골든 트라젝토리" + (" (음성 프로브 B-9)" if probe_b9 else ""))
    g.bind_input()
    g.create_workspace()

    # --- T1 : 세션을 열고 붙는다 ------------------------------------------------ #
    g.turn("세션을 열고 대상에 붙어 배너를 읽는다")
    s = g.open_session(["/bin/bash"], kind="pty=false,shell=bash")
    obs_zone, banner = _open_conn(s, target)
    mz = BANNER_RE.search(banner)
    if not mz:
        return False, "배너에서 zone 을 찾지 못했다"
    zone = mz.group(1)

    # --- T2 : HELO ---------------------------------------------------------- #
    g.turn("HELO 로 이 연결 전용 nonce 를 받는다")
    _, r = _say(s, "HELO golden", "HELO")
    mn = NONCE_RE.search(r)
    if not mn:
        return False, f"HELO 응답에 nonce 가 없다: {r!r}"
    nonce = mn.group(1)

    if probe_b9:
        # B-9 (음성) — 세션을 끊고 다시 붙어 **이어서** 시도한다.
        # 성공하면 fixture 가 세션 유지를 강제하지 않는다는 뜻이고, fixture 결함이다.
        g.turn("B-9: 세션을 끊는다")
        s.close()
        g.turn("B-9: 새 세션으로 다시 붙어 이전 nonce 로 이어서 시도한다")
        s2 = g.open_session(["/bin/bash"], kind="pty=false,shell=bash")
        _open_conn(s2, target)
        _, r_arm = _say(s2, f"ARM {nonce[::-1]}", "ARM(stale nonce)")
        _, r_read = _say(s2, "READ", "READ(after stale ARM)")
        s2.close()
        got = PART_RE.search(r_read)
        if got:
            g.attempt_finished("invalid", "B-9 실패: 재접속 후에도 part 를 얻었다")
            return False, "B-9 실패: 세션을 끊고 다시 붙어도 답에 도달했다 — fixture 결함"
        g.attempt_finished(
            "failed",
            f"B-9 통과: 재접속 후 ARM={r_arm.strip()!r} READ={r_read.strip()!r} — part 를 얻지 못했다",
        )
        return True, "B-9 통과 (실패해야 할 때 실패했다)"

    # --- T3 : ARM ----------------------------------------------------------- #
    g.turn("nonce 를 뒤집어 ARM 한다")
    _, r = _say(s, f"ARM {nonce[::-1]}", "ARM")
    if "OK armed" not in r:
        return False, f"ARM 이 통과하지 않았다: {r!r}"

    # --- T4 : READ ---------------------------------------------------------- #
    g.turn("READ 로 part 를 받는다")
    obs_part, r_read = _say(s, "READ", "READ")
    mp = PART_RE.search(r_read)
    if not mp:
        return False, f"READ 응답에 part 가 없다: {r_read!r}"
    part = mp.group(1)

    # --- T5 : 조립과 제출 ------------------------------------------------------ #
    # 이 턴의 state.snapshot 이 T1에 연 세션을 아직 live 로 보고해야 한다 (S6).
    g.turn("세션을 유지한 채 두 관찰을 합쳐 flag 를 만든다")
    flag = f"kisia{{{zone}_{part}}}"
    obs_asm, _, _ = g.exec(["sh", "-c", f"printf '%s\\n' '{flag}'"], "tool:assemble flag")
    g.candidate(
        flag,
        derived_from=obs_asm,
        method="kisia{<zone>_<part>}. zone 은 배너 관찰, part 는 READ 관찰에서 왔다.",
    )
    g.em.emit(
        "candidate.provenance",
        assembled_in_observation=obs_asm,
        part_observations=[
            {"observation_id": obs_zone, "part": "zone", "source": "session banner (T1)"},
            {"observation_id": obs_part, "part": "part", "source": "session READ (T4)"},
        ],
        note="S7/S8 충돌에 대한 재료. FIXTURES.md §6 참조.",
    )
    ok = g.verify(flag)
    s.close()
    g.attempt_finished("solved" if ok else "failed", "verifier 판정")
    return ok, "골든 B 통과" if ok else "verifier 가 골든 후보를 거부했다 — fixture 결함"


def main(g, argv: list[str]) -> tuple[bool, str]:
    return trajectory(g, probe_b9="--b9" in argv)


if __name__ == "__main__":
    print("run.py 를 통해 실행한다", file=sys.stderr)
    raise SystemExit(2)
