"""검사기 — `docs/spec/spec.md` §2의 술어를 이벤트 스트림에 대해 평가한다.

**표준 라이브러리만 쓴다.** `kisia.runtime` 을 포함해 이 저장소의 어떤 모듈도
import 하지 않는다.

스트림 밖 입력은 둘이고, 둘 다 스트림이 스스로 지목한다:

1. `--pricing config/pricing.openai.yaml` — S3.2가 이름으로 지목하는 판정 입력.
2. `--fixture <dir>` — `attempt.started.challenge_manifest_sha256` 이 지목하는
   챌린지. 검사기가 해시를 대조하고, 어긋나면 판정하지 않는다.

두 번째가 필요한 이유는 스트림이 나르지 않는 사실 셋이 판정에 들어가기 때문이다.

- **유형 A/B/C** — `spec.md` §5 하중표의 행을 고른다. 봉투의 어떤 필드도 유형을
  나르지 않는다(통제 블록에 `challenge_id` 는 있고 `type` 은 없다).
- **`parts`** — S8.2가 `answer.sweep.part_hits` 를 소스로 쓰는데, `part` 는
  키이고 값은 봉투에 싣지 않는다(`TELEMETRY_SCHEMA.md` §3.2.1 — 스트림에 정답
  조각을 쓰면 S8.3의 스윕 대상이 스트림 자신이 된다). 값은 매니페스트 옆
  정답 파일에서 온다(`MANIFEST.md` §2.3, R3-4).
- **정답 문자열** — S8.2의 "정답을 담은 모든 관찰"이 무엇인지 정하려면 필요하다.
  검증된 후보에서 역산하면 후보를 한 번도 내지 않은 스트림이 S8.2를 공허참으로
  통과한다.

**이 입력이 S9.5를 깨지 않는 이유:** 셋 다 내용 주소로 고정되어 있고 스트림이
그 주소를 나른다. 검사기는 (스트림, 그 스트림이 지목한 픽스처, 단가표)의 순수
함수이고, 그 셋이 같으면 어느 기계에서도 같은 판정 digest 를 낸다.
"""

from kisia.checker.model import SeamVerdict, Verdict

__all__ = ["SeamVerdict", "Verdict"]
