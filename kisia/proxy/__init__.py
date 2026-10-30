"""docker 소켓 프록시 — 제품이 컨테이너에 닿는 **유일한** 경로.

`runtime` 도 `checker` 도 아니다(`PATH_SCOPE.md` §1의 네 주체 어디에도 없다).
프록시는 `runtime` 과 **권한 경계를 사이에 두고** 마주 본다 — 프록시만 `docker` 자격을
갖고 `runtime` 은 갖지 않는다. 그래서 `kisia.runtime` 아래가 아니라 형제로 둔다.

설계는 `docs/rebuild/HOST_EXCEPTIONS.md` §2.1.a 가 확정했고 이 패키지는 그 구현이다.
**새 의존성 0** — 표준 라이브러리만 쓴다(§2.1.a-2).
"""
