# 재빌드의 worker 이미지 — 유형 A 골든 궤적이 도는 최소 환경.
#
# **스파이크의 `kisia-fix/worker:1` 을 쓰지 않는다.** 그 이미지의 Dockerfile 이 프로토타입
# 이미지를 쓰지 않은 것과 같은 이유다 — 스파이크 산출물과 제품 자산의 경계를
# `HOST_EXCEPTIONS.md` §9.2 회수 시점에 흐리지 않기 위해서. 재빌드가 스파이크 이미지 위에
# 서면 그 회수가 제품을 깨뜨린다.
#
# **빌드는 `ctf` 가 한다.** 프록시가 `POST /build` 를 거부하고(§2.1.b), 제품은 digest 로
# 실행만 한다. `PATH_SCOPE.md` §2.3("런타임 패키지 설치 금지 — 이미지는 미리 빌드하고
# digest 로 고정한다")의 그 배치이고 `config/images.lock.yaml` 이 선례다.
#
#     ctf$ docker build -t kisia/worker-a:1 images/worker/
#
# 베이스를 `ubuntu:24.04` 로 두는 이유: 호스트에 이미 있어 새로 pull 하지 않는다.
# 프록시가 `POST /images/create` 도 거부하므로 pull 은 애초에 서지 않는다.
FROM ubuntu:24.04

#  binutils -> strings  : 유형 A 관찰 1. notes.bin 은 0x80..0xFF 뿐이라 cat 으로 읽히지
#                         않고, 도구를 하나 강제하는 것이 픽스처의 설계다
#  python3            -> 유형 A 관찰 2(집계)와 P-S2-c(미선언 목적지 접속 시도)
#  tar·gzip·bash 는 ubuntu:24.04 에 이미 있다 — 아카이브 해제와 /dev/tcp 프로브
RUN apt-get update \
 && apt-get install -y --no-install-recommends binutils python3 \
 && rm -rf /var/lib/apt/lists/*

# **vendored 컨테이너 자산(`_connect.py`·`server_connection.sh`)은 여기 없다.**
# 그것은 유형 B 세션 이미지의 것이고(`PATH_SCOPE.md` §2.3), 그 이미지를 굽는 세션이
# `LICENSE_MATRIX.md` §5.4.5(pwntools)를 함께 채운다. 유형 A 는 세션을 열지 않으므로
# 여기 넣으면 쓰지 않는 자산을 굽고 라이선스 고지 대상만 늘린다.

# 루트fs 는 `--read-only` 로 뜬다. 세 마운트만 쓰기 표면이고 그 규칙은 `PATH_SCOPE.md` §2.1.
WORKDIR /work
ENV HOME=/work
