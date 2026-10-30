# Evidence pack — KISIA CTF harness, 2026-08-07

Revision `a54deb0`, working tree clean. 14 commits after the Phase A handoff (`72f287d`).

This document exists so someone can decide whether any of this code is worth reusing. It is not a
handoff and it argues for nothing. Every number below was produced by running a command; where a
fact comes from a record rather than from a run performed on 2026-08-07, it says so.

The repository is an early prototype. The presence of a module, a tool name or a passing test is
not treated here as evidence that a capability exists.

## 1. Reproducing every number in this document

On the Windows workspace:

```bash
uv sync --frozen
uv run pytest                                   # everything Docker-free
uv run pytest -m unit --collect-only -q         # per-marker counts
uv run ruff format --check . && uv run ruff check . && uv run mypy src/kisia_agent
uv run kisia doctor --offline
uv run kisia smoke offline
```

On the Linux host (`ssh CTF-agent`, checkout at `<PROTO_HOME>/kisia-agent`):

```bash
/usr/local/bin/uv run pytest -m "unit or contract or docker"
/usr/local/bin/uv run kisia doctor --live-openai --docker
/usr/local/bin/uv run kisia runtime smoke --profile <base|pwn|rev|web|crypto|forensics>
/usr/local/bin/uv run kisia run export --latest --output /tmp/run.tar.gz
```

The event-log figures in §5 come from `<PROTO_HOME>/kisia-runs/events/events-000001.jsonl`, read with
a throwaway Python script over the JSONL.

## 2. Environment the numbers came from

| | |
|---|---|
| Linux host | Vultr Ubuntu 24.04, 8 vCPU / 16 GiB, Docker 29.7.1, no `/dev/kvm` |
| Python | 3.12.13 on both hosts |
| Package | `kisia-agent 0.1.0` |
| Worker images | six, pinned by digest in `config/images.lock.yaml`, helper protocol 4 |
| Recorded permissions | `allow_external_ai` true; `allow_vps`, `allow_network_automation`, `allow_auto_submit` false |

`kisia doctor --offline` on the host reports `policy OK (acknowledged by dnhynk)` and
`deployment WARN (POLICY_NOT_ACKNOWLEDGED)` — the host is `deployment_class=vps` without
`allow_vps`, so it may process synthetic fixtures only.

## 3. Test inventory

Collected counts, `uv run pytest -m <marker> --collect-only -q`, 2026-08-07:

| Marker | Tests | What it touches |
|---|---:|---|
| `unit` | 456 | pure functions; no Docker, no network, no model |
| `contract` | 207 | fakes and fixtures; a loopback socket for the target tools |
| `docker` | 30 | a real container on the Linux host |
| `live_openai` | **0** | **no automated test exists for the paid path** |
| total | 693 | |

Last observed runs:

- Windows, `uv run pytest`: `663 passed, 30 skipped` (the 30 skipped are the `docker` marker).
- Host, `pytest -m "unit or contract or docker"`: `693 passed in 63.83s`.
- Static: `ruff format --check` clean, `ruff check` clean, `mypy src/kisia_agent` clean (81 files).
  `tests/` is outside the mypy gate and has pre-existing type errors.

The 30 Docker tests are `test_analysis.py: 13`, `test_sessions.py: 9`, `test_worker.py: 8`.

**What the totals do not mean.** 663 of the 693 tests never start a container. A tool that passes
its contract test has been exercised against `FakeRuntime`, which reads and writes real files but
is not the code that decides containment. Where the two disagree, only the Docker tests would
notice, and §4 states per tool whether such a test exists.

## 4. Per-tool evidence

Nineteen tools are advertised to the model. "Container evidence" means a `docker`-marked test
drove the tool against a real worker.

| Tool | Container evidence | Success case observed | Failure case observed |
|---|---|---|---|
| `run_command` | yes | exit code, stdout preview, artifact on truncation | timeout kills descendants; output limit; `network=challenge` refused with no network |
| `write_file` | yes | bytes + sha256 written under `/work` | write outside `/work` refused |
| `read_file` | **no pytest** | `kisia runtime smoke` asserts "input is readable" | — |
| `list_files` | **no pytest** | contract test only | — |
| `start_session` | yes | shell opens, banner returned, sequence 1 | third concurrent session refused |
| `session_send` | yes | `echo` round-trips; sequence gapless 2,3,4,5 | send after close refused |
| `close_session` | yes | transcript artifact hash equals the file's bytes | — |
| `extract_archive` | yes | well-formed zip lands under `/work` | `../` (zip+tar), absolute entry, symlink and hardlink escape, zip bomb, tar bomb, over-count, encrypted-without-password, encrypted-wrong-password — all refused |
| `inspect_binary` | yes | ELF64/x86-64/PIE/interpreter, cross-checked against `readelf` | non-ELF reported `format: unknown` |
| `inspect_mitigations` | yes | NX/RELRO/BIND_NOW read from headers | non-ELF refused |
| `search_strings` | yes | offset and context returned | — |
| `save_artifact` | yes | hash and size recorded | `../host-secret.txt` refused |
| `read_artifact_preview` | yes | text and base64 forms | unknown artifact id refused |
| `open_target_session` | **no** — loopback fixture only | banner returned, credential written to socket | missing capability, missing credential refused |
| `probe_target` | **no** — loopback fixture only | connectivity + banner | undeclared target refused; request budget exhausted |
| `reset_target` | **no** | — | always returns not-accepted; no platform adapter exists |
| `update_evidence`, `candidate_flag`, `finish_attempt` | n/a (host control) | offline smoke | — |

The three target tools have never contacted anything but a Python loopback server started inside
the test process.

## 5. The paid path: one observation

`<PROTO_HOME>/kisia-runs/events/events-000001.jsonl`, read 2026-08-07:

```
events            1252
attempts          48
model.completed   {'fake-model': 24, 'gpt-5.6-terra': 6}
usd               0.017598000000
candidates        ['  KISIA{offline_smoke_not_a_real_flag}' ×6,
                   'KISIA{live_smoke_not_a_real_flag}' ×1]
```

Six real API calls have ever been made, on 2026-08-05/06, costing $0.0133 of the $0.0176 total.
They were not re-run on 2026-08-07; the figures above are read from the log.

**Every candidate this system has ever produced is a string planted in a fixture by this
repository.** `examples/smoke/manifest.yaml` declares `provenance: synthetic` and states its own
objective as *"read the staged handout and report the flag-shaped string it contains"*. Both
manifests in the repository are synthetic. No contest-derived challenge has been registered, and
`allow_vps` is false, so the host would refuse one.

What the paid run demonstrates: a Responses API call, a tool call reaching a container, a
candidate event, usage and cost recorded, and an exit without exposing the key. What it does not
demonstrate: solving anything.

## 6. Never executed

- **Any real CTF challenge.** No attempt has ever run against contest-derived input.
- `live_openai` marker: zero tests. The paid path is a CLI command, verified once by hand.
- `kisia smoke openai` from a fresh clone (the Phase A reproduction stopped at `doctor`).
- Long-context tier (input >272K), and the 65%/80% context thresholds — the live run measured a
  ratio around 0.003. Unit tests only.
- `MODEL_POLICY_BLOCKED` against the real API.
- `contains_secret` against a genuinely leaked key. Synthetic values only.
- `gpt-5.6-luna`, `gpt-5.6-sol`, `gpt-5.3-codex`: never called. `gpt-5.3-codex` has no price entry
  and fails by design when selected.
- Docker on Windows (absent).
- The operational performance criteria (since-retired `deployment.md` §8) in full: warm-worker p95, ten consecutive smokes, 30-minute soak, event-store
  throughput, dashboard latency. **No measurement of any kind exists.**

## 7. Named criteria not met

These criteria were written by this repository for itself, in a specification document deleted
on 2026-08-07 (git history has it). They are quoted rather than referenced so this section stands
alone:

**B0** — "the model is never offered a tool whose required capability the probe reported
unavailable". The host capability probe (`kvm`, `nested-virt`, `seccomp`, `cgroup-v2`) gates no
tool. The target-capability gate added in B3 is a different mechanism keyed on manifest targets.

**B3** — three of six criteria unmet:

1. "a worker with `network=challenge` reaches only manifest-declared host/port pairs, proven from
   inside the container". Nothing creates a challenge Docker network. The target tools connect
   from the host, so the container-side path was never exercised. Only the refusal — asking for
   `challenge` on a worker that joined no network — is tested.
2. "a forced call returns `unavailable`". It returns `TOOL_INVALID_ARGUMENT` (undeclared target)
   or `TOOL_NOT_IMPLEMENTED` (undeclared capability). `ToolStatus.UNAVAILABLE` is not used.
3. "credential, path and parameter brute force require a manifest capability plus an explicit
   operator-approved budget". No brute-force capability exists. Only raising the request rate above
   5/s or 1 connection is gated.

**B4** — not started. `DockerRuntime.find_orphans` exists and has **exactly one reference in the
repository: its own definition.** No caller, no test. `AttemptStatus.INTERRUPTED` exists as an enum
value with no reconciliation path behind it. There is no restart entry point.

**B5** — not started. No soak harness, no percentile measurement; `rg 'soak|p95|percentile'` over
`src/` returns nothing.

**Phases C, D, E** — no code. No cockpit, scheduler, multi-worker concurrency, NYU evaluation
harness, router, or contest adapter.

## 8. Defects that passing tests did not catch

Recorded because they bear on how much the green suite is worth. Each was found by running the
code against a container and reading the result, not by a test failing.

1. **`killpg` does not clear a PTY.** A shell on a tty enables job control and puts each background
   job in its own process group. `sleep 300 &` survived a group stop — two of them, confirmed by
   `ps`. The A2 criterion "timeout kills descendants, 0 surviving" had been passing for
   `run_command` only because a non-interactive shell leaves its jobs in one group. The kernel
   session is the shared boundary; the code now clears that instead.
2. **A killed descendant lingers as a zombie** and was counted as a survivor, reporting a
   successful cleanup as a failure and spending the whole grace period every close (2.00s → 0.05s
   once zombies stopped counting).
3. **`waitpid(WNOHANG)` returns status 0 for a live child**, and status 0 also means "exited
   cleanly". A running session was reported as exited 0 until the returned pid was checked instead.
4. **A tool's artifact had no producer event.** `tool.completed` carries artifact ids only, so the
   hash was in no event and the artifact could not be cited as evidence. This affected
   `run_command`'s truncated-output artifacts from A2 onward, not only B2 transcripts.
5. **`newline` was honoured for a pty session and silently dropped for a target session**, where it
   matters more.

## 9. Statements this repository cannot support

- That the harness can solve a CTF challenge, of any category or difficulty.
- That any measured figure in `deployment.md` §8 is met, or has been attempted.
- That the six worker profiles carry the tools a real challenge needs. Package lists were chosen
  without reference to any challenge corpus; only that the images build and pass the eight A2
  isolation assertions.
- That target access works against anything other than a loopback socket in a test process.
- That a restart is recoverable.
- That model routing, escalation or specialist selection has any validation behind it. One model
  has ever been called.
