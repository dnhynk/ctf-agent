# B-4 재료 — 즉시 종료하는 자식을 만들고 거두지 않는다.
#
# 정답 경로가 아니다(spawn_bg.sh 와 같은 이유). arm 프로브 B-4가 이 파일을 쓴다.
#
#   실행:  sh /input/spawn_zombie.sh
#
# 부모가 waitpid 하지 않으므로 자식은 상태 Z로 남는다.
# SEAM_CONTRACT §4.1-3: 좀비는 생존자가 아니다. 좀비를 생존자로 세는 구현은 정리
# 성공을 실패로 보고하고 매 close마다 grace를 전부 소모한다. B-4는 그 시간을 관측한다.
exec python3 -c '
import os, sys, time
pid = os.fork()
if pid == 0:
    os._exit(0)
print("spawned short-lived child pid=%d (parent never reaps)" % pid, flush=True)
time.sleep(600)
'
