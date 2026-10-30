"""evidence store — attempt 산출물의 보관 계약.

`ADR-0003` §Decision-1 이 채택한 컴포넌트 경계 일곱 중 하나다
(`CONTEST_ARCHITECTURE.md` §16-B: "solver, verifier, scheduler, evidence store 의 경계").

**여기는 판정하지 않는다.** 무엇이 참인지는 검사기(`kisia.checker`)와 verifier
(`kisia.runtime.verifier`)의 것이고, 이 계층은 **무엇이 어떤 바이트로 언제 들어왔는지**만
적는다. 그 둘이 runtime 밖에서 도는 것이 `PATH_SCOPE.md` §1 의 배치이고, 보관이 판정을
겸하면 그 배치가 무의미해진다.

**`kisia.runtime` 을 import 하지 않는다.** 검사기에 걸린 것과 같은 성질이다
(`PATH_SCOPE.md` §4.3, S9.5): 보관된 증거는 다른 기계에서 열려야 하고, 그러려면 컨테이너·
모델·docker 를 아는 트리에 묶이면 안 된다. `kisia_tests/test_evidence_store.py` 가
그 경계를 강제한다.

**`O-47` 이 여기 앉는다.** ClaudeCode 의 전사본은 `~/.claude/projects/<ns>/<session>.jsonl`
에 **평문으로** 남고, 그 워커가 실제 챌린지를 풀면 챌린지 콘텐츠와 (챌린지에 따라)
정답이 그 파일에 앉는다(`CLAUDECODE_WORKER_DESIGN.md` §1.4). 그래서 이 계층의
`ingest_transcript` 는 **복사가 아니라 이동**이고, 옮긴 바이트의 해시를 확인한 **뒤에만**
원본을 지운다. `CLAUDECODE_WORKER_DESIGN.md` §4-④ 가 권고한 회수 자세를 코드로 세운 것이다.

**escalation 패킷의 자리는 이 계층이 정하지 않는다.** `PATH_SCOPE.md` §3.7 이
`<데이터 루트>/escalation/<attempt_id>/packet.json` 으로 이미 정했고, 여기서는 그 경로를
그대로 쓴다. `export.log` 는 **export 게이트의 것이고 이 계층이 쓰지 않는다** — egress 는
현재 비활성이다(`SAFETY_SCOPE.md` "Escalation egress": *"Currently inert"*).

**비밀 제거를 여기서 하지 않는다.** canon 은 그 의무를 **export 경로**에 건다
(`SAFETY_SCOPE.md` "Escalation egress" 조건 3: *"The export aborts rather than shipping a
redaction sentinel"*). 보관은 export 가 아니다. 여기에 두 번째 제거 계층을 세우면
어느 쪽이 실제로 막았는지 알 수 없게 되고, 그것은 canon 이 조건 1(단일 경로)로 막으려는
형태 그 자체다.
"""

from kisia.evidence.store import ROLES, EvidenceError, EvidenceStore, Record

__all__ = ["ROLES", "EvidenceError", "EvidenceStore", "Record"]
