# SAFETY_SCOPE

Canonical. This file defines where the agent may act. Anything not permitted here is out of scope,
whether or not code exists that could do it.

## Allowed targets

Only an endpoint declared in the challenge manifest for the attempt in progress. There is no
default target, no target named by the model at call time, and no resolution of a host from a
challenge description.

**Currently declared: none.** Neither committed manifest declares a target. Every target-tool
execution to date has been against a loopback socket started inside a test process.

## Allowed network

| Actor | Egress |
|---|---|
| Worker container | none by default. `network=challenge` requires a manifest-declared target; no challenge network has ever been created. |
| Host | `api.openai.com` only. `httpx` appears in the OpenAI adapter and nowhere else in `src/`. |

Package installation at run time is out of scope. Tool images are built and pinned by digest
beforehand.

Host egress is widened for the OSS foundation spike until 2026-08-21; see the exception below.

A second, permanent exception exists for the escalation layer and is currently inert; see
"Escalation egress" below. It does not widen the worker's egress, which stays `none by default`.

## Allowed file access

Inside the worker:

- `/input` — read-only, the challenge revision's inputs
- `/work` — writable, attempt-scoped
- `/artifacts` — writable, attempt-scoped

Out of scope: any host path, the Docker socket, the host home directory, host SSH keys, cloud
credentials. None is mounted.

The Docker socket is reachable by one dedicated account for the OSS foundation spike until
2026-08-21; see the exception below. It is still mounted into nothing.

Challenge-derived code, binaries, archives and captures are opened and executed only inside the
worker, never on the host.

## Credentials

- The OpenAI key exists only on the host, read from `~/.config/kisia-agent/secrets.env`. It is not
  passed to a worker, a prompt, a log or an artifact.
- A target credential is resolved on the host and written to the target socket. It does not enter
  the worker and is not returned to the model.
- Secret values are redaction sentinels; an export aborts rather than shipping one.
- The OSS foundation spike reuses this key on the host and passes it to candidate harness
  processes. See the exception below for what that costs and what compensates for it.

## Flag submission

**No submission endpoint exists.** `submission_mode` defaults to `manual`, `allow_auto_submit` is
false, and no platform adapter is implemented. A candidate flag is not a solved flag; acceptance is
a human action.

Automated submission is out of scope until a contest's rules are confirmed to permit it, an adapter
exists, a dry run has passed, and the permission is explicitly enabled.

## Escalation egress

Approved 2026-08-08 by dnhynk. Proposal and rationale: `docs/proposals/CANON_EDITS_2026-08-08.md`.

The product has one escalation layer: when the autonomous core stalls, a packet compiled from
its own telemetry is analysed by a model other than the one driving the attempt. That crossing
is an exception to "Host egress: `api.openai.com` only" and is defined here rather than left
to the layer that will implement it.

**Currently inert.** The escalation layer does not exist. Until it does, and until the
operator enables it for a named contest, no traffic is permitted under this section and the
`Allowed network` table applies unchanged.

When it is enabled, all six conditions hold simultaneously. Failing any one of them, the
export is refused and the refusal is recorded.

1. **One path.** Challenge-derived content leaves the host through a single export function.
   No other code path may reach an external model with challenge-derived bytes. An attempt to
   do so is a scope violation, not a bug.
2. **Compiled, not raw.** What crosses is a packet projected from the attempt's telemetry —
   observations, hypotheses, and their status. Raw challenge artifacts, binaries, captures and
   input files do not cross.
3. **Secret-scrubbed.** The export aborts rather than shipping a redaction sentinel. This is
   the existing rule under `Credentials`, applied to the export.
4. **Scope-checked.** The destination is an endpoint named in the enabled escalation
   configuration. There is no destination named by a model at call time and none resolved from
   a challenge description — the same rule the `Allowed targets` section applies to targets.
5. **Recorded.** Every export is recorded with its destination, the packet's content hash, the
   redaction result and the attempt it belongs to. An export that cannot be reconstructed from
   the record is treated as a run that left scope.
6. **Downstream of the core.** Escalation never runs inside the worker. It is a host-side
   projection of telemetry; the worker's egress is unchanged and stays `none by default`.

A run that used escalation is not a `clean solve@1`. See `EVAL_CONTRACT.md`.

## Permissions

Four independent permissions. None implies another.

| Permission | State |
|---|---|
| `allow_external_ai` | true |
| `allow_vps` | false |
| `allow_network_automation` | false |
| `allow_auto_submit` | false |

The integration host is `deployment_class=vps` without `allow_vps`, so it may process synthetic
fixtures only. Contest-derived intake, storage and execution are refused there.

## Container isolation (standing)

This is the product's permanent posture, not a time-limited exception. Signed 2026-08-09 by
dnhynk as `P-2` in `docs/proposals/CANON_EDIT_PRODUCT_POSTURE.md`.

It was measured before being written: the two-way test of `docs/rebuild/HOST_EXCEPTIONS.md`
§2.1.c was exercised on 2026-08-09 with every allow path succeeding, every refusal observed
with its reason, and a raw-socket `connect()` failing with `EACCES`.

- **The product creates containers only through the socket proxy.** The raw Docker socket is
  out of scope for the product as it is for everything else. An account that must launch
  workers is put in the proxy's group, never in `docker`.
- **Worker egress is enforced at the container.** `network=challenge` requires a
  manifest-declared target; a worker on an internal network reaches nothing else. **This is
  no longer unexercised** — it was observed on 2026-08-09, which supersedes the sentence under
  the product-rebuild exception below saying the container-side restriction "has never been
  exercised". That sentence is left in place as a record of when it was true.
- **A missing capability is reported and the work is blocked.** Isolation is not weakened to
  supply it. This restates the `Out of scope` rule and is repeated here because this is the
  section a product engineer reads.

This section grants nothing. It states a posture; the permissions table above is unchanged and
`allow_vps` stays false.

## Out of scope

- Any host, port or URL not declared in the attempt's manifest.
- Port scanning, path or parameter brute force, credential guessing, and high-rate requests. These
  require a manifest capability plus an explicit operator-approved budget; the capability does not
  currently exist, so they are unavailable.
- Requests that would degrade a service's availability.
- Running challenge-derived code on the host.
- Weakening worker isolation to compensate for a missing capability. A missing capability is
  reported and the work is blocked.
- Reaching a contest platform for scraping or submission. Bulk enumeration of a platform's
  catalogue, and any automated flag submission, stay out of scope regardless of permissions.
- Downloading contest-derived material is out of scope except under an active named exception
  that scopes it — see "Time-limited exception: calibration intake". Outside such an exception
  this line reads as it always did.

## Host access

The integration host is reached over SSH from the operator's address only, enforced by `ufw`.
Password and root SSH login stay disabled; a lockout is recovered through the provider console.
Procedure: `docs/runbook/ssh-and-firewall.md`.

## Time-limited exception: OSS foundation spike

Approved 2026-08-07 by dnhynk. **Expires 2026-08-21**, or 14 days after the start date recorded in
`docs/spike/HOST_EXCEPTIONS.md` §10, whichever is earlier. On expiry it lapses without notice and
the rules above apply unchanged. Extension requires a new approval recorded in that table.

Scope: the spike specified in `docs/spike/FOUNDATION_DECISION.md` §9, run on the integration host
under a dedicated unprivileged account outside `<PROTO_HOME>`.

Permitted for the duration, to that account only:

- **Docker socket access.** The socket is mounted into nothing. A candidate harness that requires
  it inside a container is refused, and the requirement is recorded as a spike observation. Access
  is withdrawn between work sessions, not held open for the whole window; the expiry above is a
  ceiling on exposure, not a schedule. Procedure and log: `HOST_EXCEPTIONS.md` §8.3, §9.1, §10.1.
- **Egress beyond `api.openai.com`**, to the destinations enumerated in `HOST_EXCEPTIONS.md` §3 and
  to no others. Each is added when first needed, with reason and date.
- **Reuse of the existing OpenAI key** in `~/.config/kisia-agent/secrets.env`, passed to candidate
  harness processes running on the host. Operator decision 2026-08-07, replacing the separate-key
  requirement approved earlier the same day. Two consequences are accepted rather than mitigated
  away: the $150 ceiling is **observed, not enforced by the provider**, and any leak means rotating
  the product key. The following are therefore mandatory, not advisory:
  - The key reaches a candidate as a process environment variable only. It is not written to a file
    under the spike's directory, not placed inside a container, not put in a prompt.
  - After every arm run, that arm's logs, traces and artifacts are scanned for the key. A hit stops
    the spike: the key is rotated and the finding recorded.
  - Recorded spend is checked against the $150 ceiling after every arm run and at each session
    boundary.
- **Package installation for spike setup** — host-side environments and candidate image builds.
  This does not extend to a candidate installing packages inside a container mid-attempt: that is
  permitted to happen, but is recorded as a spike observation rather than treated as normal.

Unchanged by this exception, and still out of scope:

- Contest-derived input on this host. `allow_vps` stays false; the spike uses self-authored
  synthetic challenges only. NYU CTF Bench, XBOW, CyBench and InterCode are not brought here.
- The four permissions in the table above.
- Publishing a challenge service on any interface other than loopback or an internal Docker
  network, and any `ufw` change.
- Writing to `<PROTO_HOME>/kisia-agent` or `<PROTO_HOME>/kisia-data`, and removing any of the six pinned
  prototype images.

Withdrawal is the checklist in `HOST_EXCEPTIONS.md` §9, executed at expiry with its result
recorded there.

## Time-limited exception: product rebuild

Approved 2026-08-08 by dnhynk; the five terms are signed in
`docs/rebuild/HOST_EXCEPTIONS.md` §5. Wording agreed in
`docs/proposals/CANON_EDIT_REBUILD_EXCEPTION.md`. **Start date: 2026-08-08. Expires
2026-09-30**, or on completion of the rebuild, whichever is earlier. On expiry it lapses
without notice. Extension requires a new approval recorded in that table.

Scope: building the product described in `docs/spec/spec.md`, on the integration host,
under a dedicated unprivileged account named `ctf-host-user`, separate from `ctf-spike-user`.

This exception differs from the spike's in kind, not only in dates. The spike measured
unverified code and threw it away; the rebuild vendors a verified MIT subset and builds a
product that keeps running. Container creation therefore stops being temporary access and
becomes **the product's permanent posture**, which is what the first item below settles.

Permitted for the duration, to the `ctf-host-user` account only:

- **Container creation through a socket proxy.** The proxy exposes container
  create/start/stop/remove. It **refuses, by enumeration**, any create whose body sets
  `HostConfig.Binds`, `HostConfig.Mounts[].Type=bind`, `HostConfig.Privileged`,
  `HostConfig.NetworkMode=host`, `HostConfig.PidMode=host`, `HostConfig.CapAdd`,
  `HostConfig.Devices`, `HostConfig.UsernsMode=host`, or `HostConfig.SecurityOpt`.
  It refuses `exec`, `PUT /archive`, and `GET /changes` against any container it did not
  create, identified by the `kisia-rebuild=1` label. **Every other endpoint is refused by
  default**; the allowed set is enumerated in `docs/rebuild/HOST_EXCEPTIONS.md` §2.1.a-3.
  The product speaks only to the proxy and
  never to `/var/run/docker.sock`. The raw socket stays out of scope; the proxy is the
  answer to the tension between that rule and a product that must launch workers.
  If proxy setup would block the rebuild's first day, raw docker-group membership is a
  fallback **and introducing the proxy becomes a named rebuild deliverable**. The product
  is not shipped on raw group membership.

  **This enumeration will go stale, and that is accepted rather than mitigated away.**
  A new escape spelling is a new refusal here, not a category. The standing guard is the
  two-way test of `docs/rebuild/HOST_EXCEPTIONS.md` §2.1.c, which is **run as a regression,
  not once**: an allow path, every refusal above, and a raw-socket `connect()` that must
  fail. Signed 2026-08-09 by dnhynk as `P-1` in
  `docs/proposals/CANON_EDIT_PRODUCT_POSTURE.md`; the earlier wording named four refusals
  while the proxy enforced nine plus ownership, which is the gap that proposal's §0 records.
- **Self-withdrawal.** `sudo /usr/local/sbin/rebuild-close` — one sudoers line, one command
  — revokes container-creation rights and stops rebuild containers. It is run between work
  sessions whenever more than a day will pass. The spike could not do this: withdrawal
  required the operator, which bound closing to their presence.
- **The existing product key, under a provider-enforced budget of $300.** Operator decision
  2026-08-08, amending the signed term: there is one key, so the rebuild shares the product's
  rather than holding its own. The ceiling is a **prepaid credit balance of $300**, not a
  monthly budget, so unlike the spike's observed-only ceiling **it is enforced** — exhausting
  it stops the API instead of letting spend continue silently, and **it does not reset with
  the calendar**. It is an accident stop, not an operating budget.

  Two properties follow from the mechanism and are load-bearing. **Automatic recharge stays
  off**; with it on there is no ceiling at all, only a delay. And because a balance is
  account-wide rather than project-scoped, **everything drawing on this account stops when it
  is exhausted** — nothing else currently does, and restarting requires a human to add
  credit, which is the intended friction.

  One consequence is accepted rather than mitigated away: **a leak means rotating the
  product's key**, since it is the same key. The following are therefore mandatory, not
  advisory. The key reaches processes as an environment variable only — never a file under
  `<HOME>`, never inside a container, never in a prompt, artifact, log or telemetry
  record. After every build/verify cycle the workspace, build images and volumes are searched
  for the key string; a hit stops the work, rotates the key, and is recorded.
- **Package installation for build purposes** — host-side environments and image builds.
  A container installing packages mid-attempt is recorded as an observation, not treated as
  normal.

**Host egress is not widened, because it is not currently constrained.** The spike measured
the host's outbound policy directly and found it unrestricted at the network layer
(`docs/spike/HOST_EXCEPTIONS.md` §10.2). The `Allowed network` table above states the rule;
the `Enforcement status` section below states what is actually enforced, and this is one of
the gaps it refers to. The rebuild starts from that fact rather than from a permission.

**Worker egress is unchanged and is the rebuild's own task.** `network=challenge` still
requires a manifest-declared target, and the container-side restriction has never been
exercised (`docs/evidence/2026-08-07-phase-b-evidence.md` §7). Implementing it is part of
the S2 seam, not something this exception grants.

Unchanged by this exception, and still out of scope:

- Contest-derived input on this host. `allow_vps` stays false; the rebuild verifies against
  self-authored synthetic fixtures only. NYU CTF Bench, XBOW, CyBench and InterCode are not
  brought here.
- The four permissions in the table above.
- Publishing a challenge service on any interface other than loopback or an internal Docker
  network, and any `ufw` change.
- The frozen prototype: `<PROTO_HOME>/kisia-agent`, the event log under `<PROTO_HOME>/kisia-runs`,
  and the six pinned prototype images.
- Weakening worker isolation to compensate for a missing capability.

Withdrawal is the checklist in `docs/rebuild/HOST_EXCEPTIONS.md` §4, executed between
sessions (§4.1) and at completion (§4.2), with results recorded there.

## Time-limited exception: calibration intake

Approved 2026-08-08 by dnhynk. Proposal and rationale:
`docs/proposals/CANON_EDIT_CALIBRATION_INTAKE.md`. **Start date: 2026-08-08. Expires
2026-09-30**, or on completion of the calibration set, whichever is earlier. On expiry it
lapses without notice and the rules above apply unchanged. Extension requires a new approval
recorded in that proposal.

Scope: assembling and running a fixed calibration set of 48 externally-authored challenges,
under the `ctf-host-user` account, for the purpose stated in the proposal's §0.2. This exception
does not enable `allow_vps`, which stays false, and does not permit contest-derived input
for any other purpose.

**The calibration set does not measure.** Its results are never counted in `clean_solve@1`
or `contest_solve`, in either the numerator or the denominator. See `EVAL_CONTRACT.md`,
"Calibration figures". A challenge admitted under this exception is not a member of `dev`,
`regression-private` or `final-holdout`, and does not move into or out of them.

Permitted for the duration, to the `ctf-host-user` account only:

- **Download of challenge material the operator's own platform account is entitled to**,
  bounded by a recorded request budget: no more than the 48 challenges named in the set, one
  download per challenge, and no enumeration of the platform's catalogue beyond what
  selecting those 48 requires. The budget is recorded before the first request and the
  actual count is recorded after the last. Exceeding it stops the work.
- **Storage of that material on the host**, under `<HOME>/calibration/`, and nowhere
  else. It is not committed to the repository. What the repository records is the manifest
  and its hash, as with any other challenge.
- **Execution of that material inside a worker container**, under the same isolation the
  product applies to every attempt. The rule that challenge-derived code is never run on the
  host is unchanged.
- **A fixed-address target proxy** for challenges whose service endpoint is assigned per
  session. The manifest declares the proxy's stable internal address; the proxy holds the
  ephemeral endpoint and is the only path to it. The worker reaches the proxy and nothing
  else. This exists so that the manifest, and therefore
  `challenge_manifest_sha256`, stays stable across attempts of the same challenge.

**Worker egress is unchanged.** The worker reaches one manifest-declared address, which is
the proxy's, on an internal Docker network. `none by default` still holds and
`network=challenge` still requires a manifest-declared target. This exception grants the
worker no new destination.

**Flag submission is unchanged and stays out of scope.** `allow_auto_submit` stays false.
A candidate flag produced against a calibration challenge is verified by the operator as a
human action, exactly as `Flag submission` above requires.

Unchanged by this exception, and still out of scope:

- `allow_vps` and the other three permissions in the table above.
- Contest-derived input for any purpose other than the calibration set defined here.
- Bulk enumeration of a platform's catalogue, and automated submission.
- Contest-derived material in `dev`, `regression-private` or `final-holdout`.
- Running challenge-derived code on the host.
- Publishing a challenge service on any interface other than loopback or an internal Docker
  network, and any `ufw` change.
- Weakening worker isolation to compensate for a missing capability.

Withdrawal: at expiry, `<HOME>/calibration/` is removed and the removal is recorded
in `docs/rebuild/HOST_EXCEPTIONS.md`, with the request-budget reconciliation from the first
item above.

## Enforcement status

These are the rules. What is actually enforced in code, and what has been demonstrated against a
real container rather than a fake, is recorded in
`docs/evidence/2026-08-07-phase-b-evidence.md` §4 and §7. Notably, the container-side network
restriction has never been exercised.
