# 재빌드 호스트 프로비저닝 — 붙여넣기 절차

`docs/canon/SAFETY_SCOPE.md`의 "Time-limited exception: product rebuild"(착수 2026-08-08,
만료 2026-09-30)가 허용한 것을 **실제로 만드는** 절차다. 예외는 허가이고 이 문서는 준비다 —
`docs/rebuild/HOST_EXCEPTIONS.md` §5.1의 체크리스트를 명령으로 편 것.

**소켓 프록시는 이 절차에 없다.** §2.1의 fallback을 택했다 — raw docker 그룹으로 시작하고
**프록시 도입을 재빌드의 명시적 산출물로 등재한다.** 그 등재가 §6이고, 건너뛰면 fallback이
영구가 된다. **raw 그룹으로 제품을 출하하지 않는다.**

**블록마다 어디서 도는지가 첫 줄에 있다.** 이 절차는 호스트와 워크스테이션을 오간다.

| 표시 | 어디 |
|---|---|
| `# @host` | `ssh CTF-agent` 안. 계정 `ctf`, passwordless sudo |
| `# @ws` | **워크스테이션 셸, 그리고 저장소 안**(`cd <HOME>/KISIA_CTF`) |

`ufw`와 sshd는 만지지 않는다.

> **`# @ws` 블록을 호스트에서 돌리지 마라.** `git remote add`를 `ssh` 세션 안에서 돌리면
> `<PROTO_HOME>`에서는 "not a git repository"로 실패하지만, **`<PROTO_HOME>/kisia-agent`에서는
> 성공한다** — 동결된 프로토타입의 git config를 고치게 되고 그것은
> `PATH_SCOPE.md` §4.1 위반이다. 실패가 아니라 성공이 사고인 경우다.

---

## 0. 먼저 알아 둘 것 셋

1. **`ctf-host-user`를 docker 그룹에 넣는 것은 호스트 root 동등이다.** 스파이크가 Path A에서
   회수한 바로 그 권한이고, 지금 다시 여는 것이다. 감당 가능하게 만드는 유일한 장치가
   §3의 `rebuild-close`이므로 **§3을 건너뛰면 §2를 하지 마라.**
2. **계정 경계는 운영자에 대한 보안 경계가 아니다.** `ctf`는 passwordless sudo를 갖고 있어
   언제든 `ctf-host-user`가 된다. 계정을 가르는 이유는 §2.3이 적은 대로 **두 예외가 한 계정에
   걸려 만료일이 둘이 되는 것을 막기 위해서**다.
3. **그룹 변경은 기존 세션에 반영되지 않는다.** `usermod` 뒤에는 로그인 셸을 새로 열어야
   한다. 이걸 모르면 "권한을 줬는데 안 된다"로 30분을 쓴다.

---

## 1. 계정과 작업 공간

```bash
# @host
ssh CTF-agent

sudo adduser --disabled-password --gecos "" ctf-host-user
sudo install -d -m 700 -o ctf-host-user -g ctf-host-user <HOME>/.ssh
sudo install -d -m 755 -o ctf-host-user -g ctf-host-user <HOME>/git
```

**운영자 키를 `ctf-host-user`에도 인가한다.** 같은 키, 같은 출발지(ufw는 여전히 한 주소만
허용한다). sshd 설정은 바뀌지 않는다.

```bash
# @host
sudo cp <PROTO_HOME>/.ssh/authorized_keys <HOME>/.ssh/authorized_keys
sudo chown ctf-host-user:ctf-host-user <HOME>/.ssh/authorized_keys
sudo chmod 600 <HOME>/.ssh/authorized_keys
```

### 1.1 코드를 어떻게 넣는가 — `<PROTO_HOME>`는 750이다

`ctf-host-user`는 기존 bare repo(`<PROTO_HOME>/git/kisia-agent.git`)를 **읽을 수 없다.** 스파이크가
§10.3에서 이벤트 로그를 건드릴 수 없었던 것과 같은 이유다. `<PROTO_HOME>`의 모드를 바꾸지
않는다 — 그 안에 동결된 프로토타입과 `secrets.env`가 있다.

대신 `ctf-host-user` 소유의 bare repo를 새로 두고, 워크스테이션이 거기로 push한다.
프로토타입의 `vultr` 리모트와 같은 모양이다.

```bash
# @host
sudo -u ctf-host-user git init --bare <HOME>/git/kisia.git
sudo -u ctf-host-user git --git-dir=<HOME>/git/kisia.git symbolic-ref HEAD refs/heads/main
```

**둘째 줄을 빠뜨리면 clone이 빈 `master`를 낸다.** `git init --bare`의 HEAD 기본값이
`master`인데 우리가 push하는 브랜치는 `main`이라, HEAD가 없는 ref를 가리킨 채로 남는다.
증상은 `warning: remote HEAD refers to nonexistent ref` + `your current branch 'master'
does not have any commits yet`이고, **clone은 성공한 것처럼 보인다.** 실측 2026-08-08.

**순서가 있다. 앞의 셋이 없으면 push가 붙지 않는다** — ssh config 항목 → bare repo(위) →
`ctf-host-user`의 `authorized_keys`(§1) → 그 다음에 remote·push.

`~/.ssh/config`에 한 항목. **`IdentityFile`은 기존 `CTF-agent` 항목과 같은 키를 쓴다**
(추측하지 말고 그 항목을 열어 복사한다):

```
Host CTF-rebuild
    HostName 203.0.113.10
    User ctf-host-user
    IdentityFile <HOME>\.ssh\id_rsa
```

붙는지 먼저 본다. 여기서 실패하면 remote를 더해 봐야 소용없다:

```bash
# @ws
ssh CTF-rebuild 'echo ok; ls -ld <HOME>/git/kisia.git'
```

그 다음 리모트와 첫 push:

```bash
# @ws  — 반드시 저장소 안에서
cd <HOME>/KISIA_CTF
git remote add rebuild-host CTF-rebuild:<HOME>/git/kisia.git
git push rebuild-host main
```

호스트에서 checkout:

```bash
# @host
sudo -iu ctf-host-user git clone <HOME>/git/kisia.git <HOME>/kisia
```

이후 갱신은 `# @ws`에서 `git push rebuild-host <branch>` → `# @host`에서
`git -C <HOME>/kisia pull --ff-only origin <branch>`.

---

## 2. 컨테이너 생성 — fallback (raw docker 그룹)

```bash
# @host
sudo usermod -aG docker ctf-host-user
```

**§0-3을 기억할 것** — 이 뒤에 여는 `ctf-host-user` 세션부터 적용된다.

> **컨테이너에 라벨을 붙이는 것이 코드 쪽 요구다.** §3의 `rebuild-close`가 정지시킬 대상을
> 찾는 유일한 수단이 라벨이다. 재빌드가 만드는 모든 컨테이너·네트워크·이미지에
> **`--label kisia-rebuild=1`**을 단다. 스파이크가 `kisia-spike=1`로 같은 일을 했고,
> 그 덕에 Path A 회수에서 잔존 0을 셀 수 있었다.

---

## 3. 자기 종료 — `rebuild-close`

**§2를 했으면 반드시 이것도 한다.** 이것이 스파이크에 없던 유일한 개선이고,
raw 그룹 fallback을 감당 가능하게 만드는 장치다.

```bash
# @host
sudo tee /usr/local/sbin/rebuild-close > /dev/null << 'EOF'
#!/bin/sh
# 재빌드 세션의 자기 종료. 닫기만 한다 — 여는 경로는 여기 없다.
set -u
ts=$(date -u +%FT%TZ)
docker ps -q --filter label=kisia-rebuild=1 | xargs -r docker stop >/dev/null 2>&1 || true
gpasswd -d ctf-host-user docker >/dev/null 2>&1 || true
echo "rebuild-close ${ts}: containers stopped, docker access revoked"
EOF
sudo chmod 755 /usr/local/sbin/rebuild-close
```

sudoers는 **그 한 줄만** 허용한다:

호스트 권한 설정은 비공개.

**비대칭이 핵심이다.** 닫기는 세션이 스스로 하고(`sudo rebuild-close`), **여는 것은
운영자만** 한다(§2의 `usermod`에는 sudo를 주지 않는다). 세션이 자기 접근을 다시 열 수
있으면 이 장치 전체가 무의미해진다.

---

## 4. 예산 $300 — 키는 제품 것을 공유한다

**정정 2026-08-08 (운영자 결정).** 초안은 전용 재빌드 키를 권했으나 **키가 하나뿐이므로
제품 키를 공유한다.** 그 결정과 감수하는 것은 `docs/rebuild/HOST_EXCEPTIONS.md` §2.5의
정정 블록과 canon("Time-limited exception: product rebuild")에 있다.

**키 개수와 상한 강제는 분리 가능하다.** 스파이크가 못 고친 것은 키를 공유했다는 것이
아니라 **예산이 어디에도 걸려 있지 않았다는 것**이다.

**OpenAI 콘솔에서** (호스트 밖):

1. **선불 잔고를 $300으로 맞춘다.** (실행됨 2026-08-08.) 이것이 §2.5가 요구하는
   **실제 강제**다 — 소진되면 API가 멈추지 조용히 계속되지 않는다.
2. **자동 충전(auto-recharge)을 끈다.** 켜져 있으면 상한이 아니라 **지연**일 뿐이다.
   **이 장치의 유일한 단일 실패점이므로 반드시 확인한다.**
3. **새 키를 만들지 않는다.** `<PROTO_HOME>/.config/kisia-agent/secrets.env`를 그대로 쓴다.

**월 예산 한도가 아니라 잔고를 고른 이유.** 월 한도는 달마다 리셋되므로 재빌드가 달을
넘기면 $300이 다시 생긴다. 계약이 요구하는 것은 운영 예산이 아니라 **재빌드 전체에 걸린
사고 방지턱**이고, 잔고는 달력과 무관한 절대 상한이다. 대가는 **소진되면 사람이 충전할
때까지 계속 멈춘다**는 것이고, 그 마찰이 의도된 것이다.

> **`secrets.rebuild.env`를 만들지 마라.** 같은 키를 두 파일에 두면 한쪽만 교체되는
> 드리프트가 생긴다. 2026-08-08에 실제로 그렇게 만들었다가 지웠다 — 두 파일의 키
> sha256이 같았고, **파일이 있고 `sk-proj-` 형식이라 육안으로는 맞아 보였다.**

**부수 효과:** 예산이 프로젝트에 걸리므로 그 키를 쓰는 다른 것도 함께 잘린다. 현재 다른
소비자는 없다(프로토타입 동결).

**실행은 이 모양으로만 한다** — 키가 파일로 `<HOME>`에 내려가지 않는다:

```bash
# @host
sudo -u ctf sh -c '. <PROTO_HOME>/.config/kisia-agent/secrets.env;   sudo -u ctf-host-user --preserve-env=OPENAI_API_KEY <명령>'
```

**매 빌드/검증 사이클 후 키 검색은 권고가 아니라 의무다** — 제품 키를 공유하므로 유출은
곧 제품 키 교체다. 적중하면 중단·보고·교체.

```bash
# @host
sudo sh -c '. <PROTO_HOME>/.config/kisia-agent/secrets.env;   grep -rIl "$OPENAI_API_KEY" <HOME> 2>/dev/null | head'
# 출력이 없어야 한다
```

> **인용에 주의.** `sudo sh -c "... $OPENAI_API_KEY ..."`를 **이중따옴표**로 쓰면 바깥
> 셸이 `sudo` 전에 확장해 버려 **언제나 빈 값**이 나오고, 그것을 "키가 없다"로 오독하게
> 된다. 2026-08-08에 실제로 그렇게 한 번 잘못 읽었다. 위처럼 **작은따옴표**를 쓴다.

---

## 5. 확인 — 넷 다 됐는가

```bash
# @host
id ctf-host-user                                   # groups 에 docker 가 있다
sudo -u ctf-host-user docker ps                    # 권한 오류 없이 돈다
# sudoers: rebuild-close 한 줄만 (호스트 권한 설정은 비공개)
ls -ld <HOME>/kisia <HOME>/git/kisia.git
df -h / | tail -1                            # 80% 미만 (스파이크 규칙)
sudo ufw status numbered                     # 기준선 그대로여야 한다 — 만졌으면 실패다
```

되돌리는 것도 한 줄이다:

```bash
# @host
sudo /usr/local/sbin/rebuild-close
```

### 5.1 실측 — 2026-08-08 프로비저닝

§1~§3·§5를 실제로 돌렸다. **§4의 예산 $300은 OpenAI 콘솔이 필요해 남아 있다** — 키는
제품 것을 공유하기로 정해졌으므로(2026-08-08) 새로 만들 키가 없고, `secrets.rebuild.env`는
만들었다가 지웠다.

`rebuild-close`를 **설치만 하지 않고 시험했다.** 시험하지 않은 안전장치는 안전장치가 아니고,
이 저장소는 자기 보고를 증거로 쓰지 않는다.

```
grant   → id -nG: ctf-host-user users docker        docker ps rc=0
close   → rebuild-close 2026-08-08T00:36:16Z: containers stopped, docker access revoked
확인    → id -nG: ctf-host-user users               permission denied ... /var/run/docker.sock
비대칭  → ctf-host-user 가 sudo usermod 시도: "a password is required"  (스스로 열지 못한다)
reopen  → 운영자 usermod → docker ps rc=0
```

§5 확인 결과: `ctf-host-user`가 docker 그룹에 있고, sudoers는 `rebuild-close` **한 줄뿐**,
`<HOME>/{kisia,git/kisia.git}` 존재, 디스크 20%, `ufw` 기준선 그대로.

---

## 6. 프록시를 산출물로 등재한다 — 건너뛰지 마라

fallback을 택한 대가다. `docs/rebuild/REBUILD_LOG.md`에 다음을 적는다.

```
D-1  docker socket proxy — raw 그룹 fallback 을 대체한다.
     생성/시작/정지/삭제만 노출하고 host bind mount · --privileged ·
     --network=host · 무관 컨테이너 exec 을 거부한다.
     근거: docs/rebuild/HOST_EXCEPTIONS.md §2.1, SAFETY_SCOPE "product rebuild".
     완료 조건: §4.2 체크리스트 1번 — 프록시가 제품의 영구 컨테이너 경로가 되고
                raw 그룹 접근이 회수됐음을 확인.
```

**이것이 §4.2(재빌드 완료 체크리스트)의 1번과 같은 항목이다.** 등재하지 않으면 완료
판정에서 이 부채가 보이지 않고, fallback이 조용히 제품의 자세가 된다.

---

## 7. 세션 개폐 기록

`docs/rebuild/HOST_EXCEPTIONS.md` §3이 요구한다. 한 줄이면 된다.

```bash
# @host
# 세션 시작 (운영자가 §2 의 usermod 를 다시 실행할 때)
echo "$(date -u +%FT%TZ) open" | sudo -u ctf-host-user tee -a <HOME>/access.log

# 세션 종료
sudo /usr/local/sbin/rebuild-close | sudo -u ctf-host-user tee -a <HOME>/access.log
```

연속으로 작업하면 이 로그는 두 줄로 끝난다. 그것도 규정대로다 — §3의 휴면은 **하루 이상
간격일 때만** 요구된다.

---

## 부록. 참조

- `docs/canon/SAFETY_SCOPE.md` — "Time-limited exception: product rebuild" (권한의 출처)
- `docs/rebuild/HOST_EXCEPTIONS.md` — §2.1(프록시와 fallback) · §2.2(자기 종료) ·
  §2.3(계정) · §2.5(키) · §3(기간) · §4(회수) · §5.1(이 절차의 체크리스트)
- `docs/spike/HOST_EXCEPTIONS.md` §10.3 — Path A 회수. `<PROTO_HOME>` 750, 라벨 기반 잔존 확인
- `docs/runbook/ssh-and-firewall.md` — `ufw`를 만질 일이 생기면 그 절차. 재빌드도 예외 없음
- `docs/spec/PATH_SCOPE.md` §4 — 호스트 경로 규칙. 프로토타입 자산 불가침
