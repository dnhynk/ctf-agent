"""KISIA CTF 재빌드 트리.

경계는 `docs/spec/PATH_SCOPE.md` §1의 네 주체를 그대로 따른다.

    kisia.runtime   오케스트레이터. telemetry 봉투를 낸다.
    kisia.checker   스트림에 대한 순수 함수. runtime 을 import 하지 않는다.
    kisia.verifier  solver 밖에서 도는 판정자 (재빌드-2 이후).

`kisia.checker` 가 `kisia.runtime` 을 import 하지 않는 것은 편의가 아니라
`spec.md` S9.5(P-S9-a)가 요구하는 성질이다 — 검사기가 조립기 버전에 묶이면
스트림에 대한 순수 함수가 아니게 된다. `kisia_tests/test_import_boundary.py`
가 그것을 강제한다.
"""

__all__ = ["__version__"]

__version__ = "0.0.0+rebuild1"
