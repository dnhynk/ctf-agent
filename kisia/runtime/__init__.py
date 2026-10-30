"""runtime — 오케스트레이터 (`PATH_SCOPE.md` §1).

컨테이너를 만들고 도구를 실행시키고 telemetry 를 낸다. **vendored 코드는 이 안에
있다.** `checker` 와 `verifier` 는 이 트리 밖이고, 그것은 편의가 아니라
`spec.md` S2.5·S8.1이 요구하는 배치다.

재빌드-1 에서 존재하는 것은 `kisia.runtime.telemetry` 뿐이다. 나머지(S1 입력 바인딩,
S2 격리, 세션 런타임)는 호스트가 필요하므로 재빌드-2 이후다 — `PATH_SCOPE.md` §4.3.
"""
