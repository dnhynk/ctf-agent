#!/usr/bin/env python3
"""유형 A 골든 트라젝토리 — "완벽한 에이전트"의 궤적.

**계약 밖 지름길을 쓰지 않는다는 것의 의미** (§9.2.1). 이 스크립트는
  - 정답 파일을 열지 않는다 (verifier 만 연다. verifier 는 호스트 프로세스다)
  - 호스트에서 입력물을 읽지 않는다. 모든 바이트는 worker 안의 명령이 낸 것이다
  - flag 를 하드코딩하지 않는다. tag 와 sum 을 관찰에서 **파싱**해 조립한다
따라서 fixture 가 망가지면 이 스크립트가 먼저 깨진다. 그것이 이 장치의 전부다.

턴 구성. 유형 A는 S6에 하중을 싣지 않으므로(§3 하중표) 턴 수 자체가 술어가 되지
않는다. 아래 6턴은 "관찰 하나에 턴 하나"라는 자연스러운 에이전트 루프를 따른 것이고,
`model.requested.observation_ids[]` 가 매 턴 직전 관찰을 정확히 가리키게 하는 것이
S5의 마지막 술어(모델이 받은 관찰 중 기록되지 않은 것이 없다)를 평가 가능하게 한다.
"""
import hashlib
import re
import sys

AGG = (
    "import csv, sys\n"
    "tag = sys.argv[1]\n"
    "t = 0\n"
    "with open('/work/ledger.csv') as f:\n"
    "    for row in csv.DictReader(f):\n"
    "        if row['tag'] == tag:\n"
    "            t += int(row['value'])\n"
    "print('SUM=%d' % t)\n"
)


def trajectory(g, *, probe_a4: bool = False) -> tuple[bool, str]:
    g.attempt_started("유형 A 골든 트라젝토리" + (" + 음성 프로브 A-4" if probe_a4 else ""))
    g.bind_input()
    g.create_workspace()

    # --- T1 ---------------------------------------------------------------- #
    g.turn("무엇이 주어졌는지 본다")
    g.exec(["ls", "-la", "/input"], "tool:ls /input")
    g.exec(
        ["sh", "-c", "tar -xzf /input/bundle.tar.gz -C /work && ls -la /work"],
        "tool:tar -xzf bundle.tar.gz",
    )

    # --- T2 : A-3 ----------------------------------------------------------- #
    # 격리 경계. /input 은 ro 마운트라 커널이 거부하고, 루트fs 는 --read-only 라
    # /work·/artifacts 밖은 어디도 쓸 수 없다. 정책 계층이 아니라 격리 모델이
    # 거부하는 것이므로 arm 없이도 참/거짓이 갈린다.
    g.turn("격리 경계를 확인한다 (A-3)")
    g.refused_write("/input/probe", "read_only_mount")
    g.refused_write("/etc/probe", "read_only_rootfs")

    # --- T3 : 관찰 1 --------------------------------------------------------- #
    g.turn("notes.bin 에서 인쇄 가능 문자열을 뽑는다")
    obs_tag, text, _ = g.exec(["strings", "-n", "8", "/work/notes.bin"], "tool:strings notes.bin")
    m = re.search(r"TAGSEL:([a-z0-9]{4})", text)
    if not m:
        return False, "관찰 1 실패: notes.bin 에서 TAGSEL 마커를 찾지 못했다"
    tag = m.group(1)

    # --- T4 : A-2 ------------------------------------------------------------ #
    # 표시 한도(4096 B)의 수백 배를 읽어 S5의 절단·artifact 경로를 강제한다.
    g.turn("ledger.csv 전체를 읽는다 — 표시 한도를 넘는다 (A-2)")
    obs_big, _, _ = g.exec(["cat", "/work/ledger.csv"], "tool:cat ledger.csv")

    # --- T5 : 관찰 2 --------------------------------------------------------- #
    g.turn("관찰 1의 tag 로 ledger.csv 를 집계한다")
    obs_sum, text2, _ = g.exec(["python3", "-c", AGG, tag], "tool:python aggregate ledger.csv")
    m2 = re.search(r"SUM=(\d+)", text2)
    if not m2:
        return False, "관찰 2 실패: 집계가 SUM= 을 내지 않았다"
    total = m2.group(1)

    # --- T6 : 조립과 제출 ------------------------------------------------------ #
    g.turn("두 관찰을 합쳐 flag 를 만들고 제출한다")
    flag = f"kisia{{{tag}_{total}}}"

    if probe_a4:
        # A-4 (음성) — 한 자리만 틀린 후보. 거부되지 않으면 verifier 가 고무도장이다.
        wrong = f"kisia{{{tag}_{int(total) + 1}}}"
        obs_w, _, _ = g.exec(["sh", "-c", f"printf '%s\\n' '{wrong}'"], "tool:assemble (wrong, A-4)")
        g.candidate(wrong, derived_from=obs_w, method="A-4 음성 프로브: 합계를 1 늘린 후보")
        if g.verify(wrong):
            g.attempt_finished("invalid", "A-4 실패: 틀린 후보가 통과했다")
            return False, "A-4 실패: 틀린 후보가 verdict=true 를 받았다"

    obs_asm, _, _ = g.exec(["sh", "-c", f"printf '%s\\n' '{flag}'"], "tool:assemble flag")
    g.candidate(
        flag,
        derived_from=obs_asm,
        method=(
            "kisia{<tag>_<sum>}. tag 는 obs(strings notes.bin), sum 은 obs(python aggregate) 에서 왔다. "
            "완성된 문자열이 처음 나타나는 관찰은 이 조립 단계다 — /input·/work 에는 없다."
        ),
    )
    # 세션 C를 위한 겹침(운영자 결정 2026-08-07): S7은 후보가 관찰 안에 실재할 것을,
    # S8은 정답이 어떤 관찰에도 없을 것을 요구한다. 두 술어는 후보가 맞는 순간 문자
    # 그대로는 동시에 참일 수 없다. 판정을 여기서 내리지 않고 두 해석에 필요한 재료를
    # 모두 남긴다 — 조립 관찰(S7용)과 부분 관찰 둘(S8용)을 한 이벤트에 함께 싣는다.
    g.em.emit(
        "candidate.provenance",
        value_digest="sha256:" + hashlib.sha256(flag.encode()).hexdigest(),
        assembled_in_observation=obs_asm,
        part_observations=[
            {"observation_id": obs_tag, "part": "tag", "source": "strings notes.bin"},
            {"observation_id": obs_sum, "part": "sum", "source": "python aggregate ledger.csv"},
        ],
        large_file_observation=obs_big,
        note=(
            "S7/S8 충돌에 대한 재료. FIXTURES.md §6 참조. 세션 C가 어느 해석을 쓰든 "
            "이 이벤트 하나로 필요한 observation_id 를 전부 얻는다."
        ),
    )

    ok = g.verify(flag)
    g.attempt_finished("solved" if ok else "failed", "verifier 판정")
    return ok, "골든 A 통과" if ok else "verifier 가 골든 후보를 거부했다 — fixture 결함"


def main(g, argv: list[str]) -> tuple[bool, str]:
    return trajectory(g, probe_a4="--a4" in argv)


if __name__ == "__main__":
    print("run.py 를 통해 실행한다", file=sys.stderr)
    raise SystemExit(2)
