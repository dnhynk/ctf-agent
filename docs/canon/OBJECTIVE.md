# OBJECTIVE

Canonical. This file defines what is being built and how success is ranked. Nothing else in the
repository overrides it.

## What is being built

An agent that, inside an authorized CTF environment, autonomously analyses a challenge, executes
tools against it, and produces a verified flag for submission.

## Priorities, in order

1. **Clean solve@1 on a private holdout.** One attempt, one challenge, no retry, on challenges the
   agent has never seen and whose write-ups are not reachable.
2. **p95 time-to-flag.**
3. **Cost per clean solve.**
4. **Run-to-run consistency.** The same challenge under the same controls should not swing between
   solved and unsolved.
5. **Scope compliance.** Staying inside `SAFETY_SCOPE.md`.

A change that improves a lower-numbered priority at the cost of a higher-numbered one is a
regression. Priority 5 is last in ordering but is not optional: a run that leaves scope is void
regardless of what it produced.

## What is not the objective

- Passing this repository's own fixtures. Every candidate produced to date is a string this
  repository planted; see `docs/evidence/2026-08-07-phase-b-evidence.md` §5.
- Test count, coverage, or a green suite.
- Preserving any existing module, interface or architecture. Those are proposals; see
  `docs/proposals/`.

## Current standing against these priorities

Unmeasured. There is no private holdout, no time-to-flag measurement, no cost-per-solve figure and
no repeat-run data. Priority 5 is the only one with any evidence behind it, and that evidence is
partial — the same evidence pack, §7.
