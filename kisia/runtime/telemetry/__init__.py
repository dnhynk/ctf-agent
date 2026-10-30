"""S9 봉투 — `docs/spec/TELEMETRY_SCHEMA.md` 의 확정판을 내는 쪽.

이 패키지가 지는 최소 의무는 §7의 아홉이고, 가장 먼저 틀리는 자리에 대한 경고는
§7.1이다. 그 경고를 **구조로** 처리했다 — `EnvelopeWriter.emit` 이 `**kwargs` 를
받지 않는다. 스파이크에서 `session.opened` 가 통째로 사라진 원인이 조립기의 내부
키워드 인자 이름(`kind`)이 계약 필드 이름과 겹친 것이었고, 키워드 인자가 없으면
그 겹침이 애초에 성립하지 않는다.
"""

from kisia.runtime.telemetry.control import ControlBlock, ControlBlockError
from kisia.runtime.telemetry.envelope import EnvelopeError, EnvelopeWriter

__all__ = ["ControlBlock", "ControlBlockError", "EnvelopeError", "EnvelopeWriter"]
