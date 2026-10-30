# 골든 트라젝토리가 도는 worker 이미지.
#
# 이것은 arm의 이미지가 아니다. arm(T·E)은 자기 이미지를 쓴다. 이 이미지는 "에이전트에게
# 노출된 도구 계층"을 골든 드라이버가 밟을 때 쓰는 최소 환경이고, 후보와 무관하게 유지된다.
#
# 베이스를 ubuntu:24.04로 두는 이유: 호스트에 이미 있어서 새로 pull하지 않는다.
# 프로토타입 이미지(kisia/worker-*:phase-a)를 쓰지 않는 이유: 스파이크가 만든 것과
# 제품 자산의 경계를 §9.2 회수 시점에 흐리지 않기 위해서다.
FROM ubuntu:24.04

# binutils  -> strings (유형 A의 관찰 1)
# python3   -> 집계 한 조각 (유형 A의 관찰 2), HTTP 클라이언트 (유형 C)
# bash      -> /dev/tcp 로 여는 지속 세션 (유형 B). ubuntu:24.04에 이미 있다
RUN apt-get update \
 && apt-get install -y --no-install-recommends binutils python3 \
 && rm -rf /var/lib/apt/lists/*

# 도구 계층의 HTTP 도구. 쿠키를 스스로 관리하지 않는다 — 항아리는 드라이버가 들고 있고
# 매 요청의 Cookie 헤더를 명시적으로 넘긴다. C-4(항아리를 버린다)가 관측 가능하려면
# 항아리가 도구 안이 아니라 도구 밖에 있어야 한다.
COPY httpreq.py /opt/httpreq.py

WORKDIR /work
ENV HOME=/work
