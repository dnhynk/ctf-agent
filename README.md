# ctf-agent

An evaluation contract, harness and container sandbox for building an LLM agent that solves CTF (capture-the-flag) security challenges in authorized environments.

Every attempt is recorded as an event stream, and a checker judges that record against a written contract. `clean_solve@1` means one attempt, no retry, no human help and one model, and the contract requires it to be reported apart from `contest_solve`. A flag obtained from a writeup counts as a failure, and a challenge inspected while fixing the agent leaves the holdout set for good.

```console
$ uv run python -m kisia.checker --json --pricing config/pricing.openai.yaml --set \
    kisia_tests/data/streams/2026-08-09-p3-regen/out-a7/*.jsonl | jq -c '.sets[0].seams'
{"S1":"PASS","S2":"PASS","S3":"PASS","S4":"PASS","S5":"PASS","S6":"N/A","S7":"PASS","S8":"PASS","S9":"PASS"}
```

The checker replays five recorded attempts in which gpt-5.6-terra drove tools in a worker container against this repository's synthetic static-file fixture, and returns one verdict per contract seam. No API key is needed.

- Context: personal project, solo, August 2026, built for the 2026 KISIA CTF.
- Verified (local, Linux host, 2026-08-09): the replayed set above, four model-driven attempts and one negative control, passes all eight applicable seams.
- Status: public snapshot. No challenge solved yet. The contest pipeline has run end to end with a real model and real containers and produced no candidate flags.

Public snapshot of a private development repository; history starts here because the private history contains host addresses, accounts, permission settings and records of externally collected challenges.

## What it does

- Runs one attempt of a model-driven agent against a challenge. The model is called from the host through the OpenAI Responses API, and its tools run in a disposable Docker worker. Challenges come in three types: static files (A), an interactive network service (B) and a web service (C).
- Records every model call, tool call, observation, candidate flag and verification as a JSONL event stream. A stream opens only when its control block records the model, reasoning effort, timeouts, budgets, image digests, network policy and challenge hash that the contract requires to match across compared runs.
- Judges a stream, or a set of streams of one type, against a contract that defines nine seams, the interfaces between parts of the harness: challenge input (S1), workspace isolation (S2), model inference (S3), tool execution (S4), result observation (S5), state across turns (S6), flag candidate extraction (S7), flag verification (S8) and telemetry (S9).
- Runs a contest queue. It builds a manifest from a challenge directory, moves each challenge through a six-step model schedule within wall-clock, attempt and dollar budgets, parks it when a budget runs out and resumes it later.
- Writes a Markdown writeup and a `repro.sh` from a stream, and compiles a stalled attempt's record into a packet for review by a second model.

## How it works

- Each attempt gets an accounting label when it is created: `clean`, `solve@k` (several attempts) or `contest`. A `clean` run must have one attempt and a single participant, the harness's own model loop. A run that consulted an outside model must be `contest`, and a `final-holdout` attempt must be `clean`. The stream writer refuses to open a stream that breaks these rules: `kisia/runtime/telemetry/control.py`, tested in `kisia_tests/test_accounting_label.py`.
- A candidate flag passes extraction (S7) only if it appears in one tool observation or is covered by fragments of earlier observations. The checker searches every way to split the flag and does not rely on the agent's own claim about where it came from, so a made-up flag with no fragment in any observation fails: `kisia/checker/grounding.py`. The answer stays in a separate verifier process that receives candidates and returns only a verdict: `kisia/runtime/verifier.py`.
- Each worker gets its own internal Docker network with no route out, a read-only root filesystem, no Linux capabilities and three volumes: `/input` (read-only), `/work` and `/artifacts`. See `kisia/runtime/workspace.py`.
- The account that launches workers cannot reach the Docker socket. It talks to a proxy that parses each request body; refuses host binds, privileged mode, host namespaces, added capabilities, devices and unconfined security profiles; labels everything it creates; and allows later calls only on labelled objects: `kisia/proxy/docker_proxy.py`, tested in `kisia_tests/test_proxy_policy.py`.
- Interactive sessions come from SWE-agent v0.7.0 (MIT), kept byte-identical under `vendor/` apart from listed patches. One adapter file imports it, and `kisia_tests/test_vendor_boundary.py` checks the upstream hashes and that boundary.

Start reading here: `docs/canon/EVAL_CONTRACT.md` (109 lines), `kisia/runtime/telemetry/control.py` (264 lines) and `kisia/proxy/docker_proxy.py` (712 lines). The largest module is `kisia/checker/predicates.py` (62 KB). Code comments and most design documents are in Korean.

## Results

All results are local measurements on fixtures this repository wrote. None is a contest result.

- Foundation choice, 2026-08-07 ([FOUNDATION_DECISION.md](docs/spike/FOUNDATION_DECISION.md) §12, in Korean). Three open-source harnesses ran behind the same contract on the contract fixtures: TATAR-LAB `ctf-agents`, EnIGMA on SWE-agent v0.7.0, and Codex CLI 0.147.0 as a control. All three failed flag extraction (S7) for the same reason: the model assembled the flag inside its own message, so no tool output contained it. The contract was then changed to accept fragments of earlier tool output, as described above (`docs/spec/spec.md` §3). EnIGMA passed the interactive-session seams with two structural patches and was the only harness whose model opened a session in every run, so its session runtime is the one reused component.
- Rebuilt harness, 2026-08-09, Linux host. Scripted runs on all three fixtures and model-driven runs with gpt-5.6-terra on the static-file and interactive-service fixtures pass every applicable seam. The streams are in `kisia_tests/data/streams/` and replay offline.
- Isolation, 2026-08-09, Linux host ([SAFETY_SCOPE.md](docs/canon/SAFETY_SCOPE.md), "Container isolation"). In a two-way test of the socket proxy, every allowed call succeeded, every refused call was logged with its reason, and a direct `connect()` to the Docker socket failed with `EACCES`. The worker's network restriction was observed the same day.
- Contest pipeline, 2026-08-09, Linux host. Four queue runs with a real model and real worker containers on copies of the static-file fixture's inputs, with the answer removed, produced no candidate flags. One run failed on names left behind by an earlier run's budget kill: worker containers, networks and volumes. The whole test suite passed at the time. The queue now removes such leftovers before it starts (`kisia/contest/queue.py`).
- Earlier prototype, 2026-08-07 ([evidence pack](docs/evidence/2026-08-07-phase-b-evidence.md)). It passed its whole test suite and still had five defects that appeared only against real containers. One example: `killpg` did not stop background jobs started from a PTY shell. The project therefore treats a checker verdict on a stream from a real container run as the evidence that a seam works.

## Status and limitations

- No CTF challenge solved yet. Every candidate flag so far came from fixtures this repository wrote.
- The contest pipeline has run end to end on the Linux host (2026-08-09) and produced no candidate flags. The path from a candidate to the queue's result file is covered only by tests.
- The contest path handles static-file (A) and interactive-service (B) challenges. Type B has not run through it on the host, and the web type (C) is not wired into it.
- Sending escalation packets to a second model is turned off in the safety scope. Flags are submitted by a person; no submission code exists.
- The priorities in `docs/canon/OBJECTIVE.md` are unmeasured: holdout `clean_solve@1`, p95 time to flag, cost per clean solve and run-to-run consistency. The `regression-private` and `final-holdout` sets are empty. Their rules were fixed on 2026-08-08, before any challenge was written for them.
- Docs and code comments cite development records (session logs, observation ledgers, the former session contract) that are not in this snapshot.

## Run it

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). These commands need no API key and no Docker. They assume a POSIX shell.

```bash
uv sync
uv run pytest
uv run ruff check kisia kisia_tests && uv run mypy kisia
uv run python -m kisia.checker --quiet --set --pricing config/pricing.openai.yaml \
  kisia_tests/data/streams/2026-08-09-p3-regen/out-a7/*.jsonl
uv run python -m kisia.writeup kisia_tests/data/streams/2026-08-09-p3-regen/out-a7/r7a-ok-01.jsonl
```

Expected: pytest passes, with three tests that need POSIX `select()` skipped on Windows. Ruff and mypy report no issues. The checker prints a verdict per stream and ends with the set verdict: S1 to S5 and S7 to S9 PASS, S6 N/A. The last command prints a Markdown writeup. The checker labels and the writeup are in Korean (집합 판정 means set verdict, 유형 type, 정상 normal, 전체 total); add `--json` to the checker for English keys.

Live attempts need a Linux host with Docker, the socket proxy in front of the Docker socket, a separate account that can use only the proxy, worker images built from `images/` and pinned by digest in `images/images.lock.yaml`, and an OpenAI key in `~/.config/kisia-agent/secrets.env`. The host procedure is in `docs/runbook/` (partly in Korean), with placeholders for addresses and account names.

## Docs

- [docs/canon/](docs/canon/): objective, evaluation contract and safety scope.
- [docs/spec/spec.md](docs/spec/spec.md): the nine-seam contract that the checker enforces (in Korean, 100 KB).
- [docs/spec/HOLDOUT.md](docs/spec/HOLDOUT.md): challenge sets, one-way moves between them and sealing (in Korean).
- [docs/spike/FOUNDATION_DECISION.md](docs/spike/FOUNDATION_DECISION.md): the comparison of open-source harnesses (in Korean, 91 KB).
- [docs/evidence/2026-08-07-phase-b-evidence.md](docs/evidence/2026-08-07-phase-b-evidence.md): what the earlier prototype could and could not support.

## Project context

Personal project, solo, August 2026. It was built for the 2026 KISIA CTF, run by the Korea Information Security Industry Association, which is where the package name `kisia` comes from.

I set the objective, approved the evaluation contract, the safety scope, every change to them and the foundation decision, and required every claim that something works to come with the command and its output. AI coding agents, mainly Claude Code, wrote most of the code and documents under those rules. [AGENTS.md](AGENTS.md) keeps the short version.

## License

MIT ([LICENSE](LICENSE)). `vendor/swe_agent_dc18a740/` is a partial copy of SWE-agent v0.7.0 under its own MIT license.
