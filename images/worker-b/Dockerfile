# 재빌드의 worker 이미지 — **유형 B(세션)**. 유형 A 이미지(`images/worker/`)는 그대로 둔다.
#
# 둘을 따로 두는 이유: 재빌드-4의 골든 A 는 `kisia/worker-a:1`(sha256:49a321f3…) 위에서
# 8칸 PASS 를 받았고 그 스트림이 재현 가능해야 한다. 유형 B 가 요구하는 pwntools 를
# 그 이미지에 얹으면 A 의 `image_digest` 가 바뀌고 판정의 근거가 흔들린다.
#
# **빌드는 `ctf` 가 한다.** 프록시가 `POST /build` 를 거부하고(`HOST_EXCEPTIONS.md`
# §2.1.b), 제품은 digest 로 실행만 한다. 고정은 `images/images.lock.yaml`.
#
#     ctf$ docker build -t kisia/worker-b:1 <이 디렉터리>
#     ctf$ docker image inspect kisia/worker-b:1 --format '{{.Id}}'
#
# 베이스를 `ubuntu:24.04` 로 두는 이유는 A 와 같다 — 호스트에 이미 있어 새로 pull 하지
# 않는다. 프록시가 `POST /images/create` 를 거부하므로 pull 은 애초에 서지 않는다.
FROM ubuntu:24.04

#  binutils        -> strings. 유형 A 와 같은 도구 계층을 유지한다
#  python3         -> 세션 리더(pty)와 P-S2-c
#  python3-pwntools-> `_connect.py` 의 `from pwn import *`. PATH_SCOPE §2.3-3 이
#                     "런타임 패키지 설치 금지"이므로 **빌드 시점에** 넣는다
#  python3-setproctitle -> `_connect.py` 의 `setproctitle` import
#  procps          -> 진단용 `ps`. 판정에 쓰지 않는다 — 생존자 계수는 호스트 `/proc` 에서
#                     오고(§4.1-2), 이것은 컨테이너 자기 보고 쪽을 나란히 재는 데만 쓴다
#
# apt 로 넣고 pip 를 쓰지 않는다: 배포판이 고정한 버전이 재현 가능하고, pip 를 넣으면
# 이미지 안에 런타임 설치 경로가 생긴다 — §2.3-3 이 막으려는 것이 그것이다.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      binutils python3 python3-pwntools python3-setproctitle procps \
 && rm -rf /var/lib/apt/lists/*

# **vendored 컨테이너 자산 둘 — `PATH_SCOPE.md` §2.3.**
#
# 1. 마운트하지 않고 **굽는다.** 마운트하면 그 경로가 쓰기 표면이 되거나 호스트 경로가
#    컨테이너에 노출된다. 굽으면 `image_digest` 로 통제 블록에 남는다.
# 2. `/opt` 아래다. `/root`(쓰기 표면 증가)도 `/work`(worker 가 자기 도구를 고칠 수
#    있게 된다)도 아니다.
#
# `server_connection.sh` 는 §2.3 이 목록에 넣었으므로 굽지만, **우리 도구 계층은 이것을
# source 하지 않는다** — 그 마커 프로토콜(`<<INTERACTIVE||…||INTERACTIVE>>`)은 우리가
# vendor 하지 않는 `swe_env.py` 가 읽는 것이다(§3.2). 굽는 것과 쓰는 것을 접지 않는다.
COPY _connect.py server_connection.sh /opt/kisia/session/
RUN chmod 0444 /opt/kisia/session/_connect.py /opt/kisia/session/server_connection.sh

# 루트fs 는 `--read-only` 로 돈다. 쓰기는 세 마운트뿐이고 규칙은 `PATH_SCOPE.md` §2.1.
# `HOME=/work` 이라 pwntools 의 캐시(`~/.pwntools-cache-*`)가 쓰기 가능한 볼륨에 떨어진다 —
# 루트fs 가 읽기 전용인 채로 `from pwn import *` 가 서는 이유다.
WORKDIR /work
ENV HOME=/work
