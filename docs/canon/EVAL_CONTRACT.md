# EVAL_CONTRACT

Canonical. This file defines how a result is judged. A number produced outside this contract is
not a result and may not be compared against one produced inside it.

## Controls held identical across compared runs

A comparison is only valid if every one of these is the same on both sides:

- model (id and reasoning effort)
- per-attempt timeout
- token budget
- hardware and container image (by digest)
- network policy
- challenge snapshot (by content hash)

Any of these differing makes the two runs incomparable. State them with the result; a result
without its controls recorded is discarded.

## What counts as success

**Clean solve.** The agent reached the flag by analysing the challenge and the artifacts it was
given, within the controls above, and the flag verified.

## What counts as failure

- Not producing a verified flag.
- Producing the flag from a write-up, a solution repository, a search result, or any source
  describing this challenge rather than the challenge itself.
- Producing the flag by searching for the flag string directly.
- Any run that left `SAFETY_SCOPE.md`.
- Any run whose controls cannot be reconstructed from its record.

Retrieval of a write-up or a flag is a **failure**, not a partial success and not an excluded
sample. It is recorded as an attempt and counted in the denominator.

## Reporting unit

`solve@1`: one attempt per challenge, no retry, no human intervention mid-attempt. Anything else
(`solve@k`, best-of-n, resumed attempts) is a different number and is labelled as such. It does not
substitute for `solve@1`.

Two figures are reported, always both, never merged. Approved 2026-08-08 by dnhynk; proposal and
rationale in `docs/proposals/CANON_EDITS_2026-08-08.md`.

**`clean_solve@1`** — the instrument. One attempt, no retry, no human intervention, one model, no
escalation, on a challenge the agent has never seen. This is the number that governs whether the
autonomous core is improving and the number `OBJECTIVE.md` ranks first. It is the only
uncontaminated measure of the agent itself, because a figure that mixes in a human or a second
model cannot be attributed to the agent. It is never dropped and never replaced.

**`contest_solve`** — the goal. The result including the escalation layer: operator-mediated
handoff, analysis by a second model, and reinjection of what came back. This is what a contest
actually scores.

The relationship is the one this contract already applies to `solve@k`: **the second figure does
not substitute for the first.** A run that used escalation is counted in `contest_solve` and is
**not** counted as a `clean_solve@1` success; it remains in the `clean_solve@1` denominator as an
attempt that the core did not solve alone.

Both figures are subject to everything above. In particular, a flag obtained from a write-up, a
solution repository, a search result or by searching for the flag string is a **failure under
both**. Escalation is analysis of the attempt's own record by another model; it is not retrieval,
and a packet that carries a retrieved solution is a retrieval regardless of which model produced
it.

An escalated run records which model was consulted and what crossed the boundary. See
`SAFETY_SCOPE.md`, "Escalation egress". A run whose escalation cannot be reconstructed from its
record is discarded, like any other run whose controls cannot be reconstructed.

## Holdout discipline

- The private holdout is not used for development, prompt tuning, threshold selection or debugging.
- A challenge inspected by a human for the purpose of fixing the agent leaves the holdout.
- Development happens on a separate set.

## Calibration figures

Approved 2026-08-08 by dnhynk. Proposal and rationale:
`docs/proposals/CANON_EDIT_CALIBRATION_INTAKE.md`.

A calibration set exists for the purpose of sizing the harness, not measuring it: which
categories it can physically handle, where difficulty first breaks it, whether the
per-attempt timeout is the right value. Its challenges are externally authored and admitted
under "Time-limited exception: calibration intake" in `SAFETY_SCOPE.md`.

**`calibration@1` and `calibration@k` are different numbers and are labelled as such.** They
do not substitute for `clean_solve@1` or `contest_solve`, and a calibration attempt is
counted in neither figure, in neither the numerator nor the denominator. A table that reports
a calibration figure alongside either of the other two states which is which on every row.

The reason is not convention. An externally-authored challenge has public write-ups, and
those write-ups may already be inside the model's weights. `clean_solve@1` requires a
challenge the agent has never seen; that property cannot be established for such a challenge
and cannot be restored by any control this contract can impose. **A calibration figure is
therefore an upper bound on nothing and a lower bound on nothing** — it says the harness got
there or did not, and the reason is not attributable.

Everything above still applies to a calibration run. In particular a flag obtained from a
write-up, a solution repository or a search result is a failure, and a run whose controls
cannot be reconstructed is discarded. Retrieval that occurred during pre-training is not
observable in the run's record and is not claimed to be excluded; this is the limit named in
the paragraph above, stated once rather than mitigated away.

## Current standing

No evaluation has been run under this contract. There is no holdout set, no comparison harness and
no recorded result. The figures that exist in this repository are fixture executions, not results;
see `docs/evidence/2026-08-07-phase-b-evidence.md` §3 and §5.
