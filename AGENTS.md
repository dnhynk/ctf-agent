# AGENTS.md

Rules for coding agents that change this repository. The linked documents give the reasons.

- `docs/canon/` and `docs/spec/` are read-only during implementation. If one looks wrong, stop and
  report it. A change starts as a proposal in `docs/proposals/` and applies only after the operator
  signs it.
- When the code and `docs/spec/spec.md` disagree, the code is wrong.
- Do not read, debug against or tune on `final-holdout` or `regression-private` challenges. A
  challenge inspected to fix the agent moves down to `dev` and never moves back
  (`docs/spec/HOLDOUT.md`).
- Do not weaken worker isolation to make up for a missing capability. Report the gap and stop
  (`docs/canon/SAFETY_SCOPE.md`).
- Create containers only through the socket proxy in `kisia/proxy/`. Do not give a worker the
  Docker socket, a host bind mount or network egress.
- Do not add automatic flag submission. `docs/canon/SAFETY_SCOPE.md` lists the conditions that
  must hold first.
- `vendor/` stays byte-identical to upstream SWE-agent v0.7.0. Change it only through a patch in
  `vendor/patches/` that is also listed in `docs/spec/SEAM_IMPLEMENTATION_MAP.md` §5. If a third
  structural patch seems necessary, stop and report. `kisia_tests/test_vendor_boundary.py`
  checks the upstream hashes, fails at the third structural patch and allows a single product
  file (`kisia/runtime/session.py`) to import vendored code.
- `docs/spike/` holds recorded evidence and fixture bytes. Do not edit it. Ruff excludes it so
  that `--fix` cannot rewrite those bytes.
- Report that something works only together with the command you ran and its output. A passing
  unit test does not show that a seam works; a checker verdict on a stream from a real container
  run does.

Before handing work back, run:

```bash
uv run pytest
uv run ruff check kisia kisia_tests
uv run mypy kisia
```
