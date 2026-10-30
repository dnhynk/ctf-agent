# SSH and firewall runbook

Status: Operational procedure for the Vultr target
Owns: how SSH reachability is changed without losing it

The host permits SSH from one source address. That is the intended posture: it is the single
control keeping the management port off the open internet, and widening it is not a workaround for
an inconvenience. The risk it creates is equally real - the operator's ISP address changes and the
host becomes unreachable - so the procedure below exists to change the allowed source safely, and
the recovery path exists for when it is already too late.

Two rules hold throughout:

- **Never open password or root SSH login to work around a lockout.** `PasswordAuthentication no`
  and `PermitRootLogin prohibit-password` stay as they are. A lockout is recovered through the
  provider console, which is already authenticated out of band; trading a permanent weakening for
  a temporary convenience is the wrong trade.
- **Never let a firewall change ride along with a deploy.** A bootstrap script that also edits
  `ufw` will eventually be run by someone who only wanted to deploy.

## 1. The allowed source is an input, not a constant

The current address lives in the operator's environment, not in any committed file:

```bash
export SSH_SOURCE_CIDR=<operator address>/32
```

This paragraph used to state that no committed file contains the value while printing it one line
above. Beyond the contradiction, the repository now has an off-box remote, and an operator's home
address is not something it needs to carry. To read the value that is actually in force, ask the
host: `sudo ufw status numbered`. That is the authority anyway - a copy in a document is a second
place to be wrong.

A script that needs the address reads `SSH_SOURCE_CIDR` and fails with a clear message when it is
unset, so running one without deciding on a source is impossible rather than silently defaulting
to something permissive.

## 2. Changing the allowed source

The failure this avoids is dropping the rule that is carrying the session doing the dropping.

1. Keep the current SSH session open. Do not close it for any reason until step 5 succeeds.
2. From that session, **add** the new source without removing anything:
   ```bash
   sudo ufw allow from "$NEW_CIDR" to any port 22 proto tcp comment 'operator, added <date>'
   sudo ufw status numbered
   ```
3. Confirm the new rule is present and the old one is still there.
4. From the new address, open a **second, independent** SSH session. This is the step that proves
   the new rule works; nothing before it is evidence.
5. Only with that second session established and confirmed working, remove the old rule from
   either session:
   ```bash
   sudo ufw status numbered          # find the old rule's number
   sudo ufw delete <number>
   sudo ufw status numbered          # confirm exactly the intended rules remain
   ```
6. Update `SSH_SOURCE_CIDR` in the operator's environment to match.

If step 4 fails, delete the rule added in step 2 and investigate from the session that is still
open. Nothing has been lost.

## 3. Recovering from a lockout

When SSH is already unreachable, the provider console is the only way in and it does not depend on
`ufw`.

1. Vultr customer portal → the server → **View Console** (noVNC).
2. Log in as **`root`**, not as `ctf`. The console is a local terminal, so
   `PasswordAuthentication no` does not apply to it and a password works there even though it
   never does over SSH. Two facts decide which account:
   - `ctf` is deliberately password-locked (`passwd -S ctf` reports `L`), so it cannot log in at
     the console at all. That is kept, not fixed: the service account then has no password path
     anywhere.
   - `deployment.md` section 3 already assigns firewall administration to root, so recovering the
     firewall as root is the documented division of duties rather than an exception to it.

   **The root password must be known before it is needed.** Check it while SSH still works:
   `sudo passwd -S root` must report `P`; if it reports `L` or `NP`, or nobody knows the value,
   set one now with `sudo passwd root`. Discovering this during a lockout is discovering it too
   late - there is no third way in.
3. Confirm the current rules and add the new source:
   ```bash
   sudo ufw status numbered
   sudo ufw allow from <new-cidr> to any port 22 proto tcp comment 'operator, console recovery'
   ```
4. Reconnect over SSH from the new address and confirm.
5. Remove the stale rule following section 2 step 5 - from SSH, not from the console, so the
   removal is again protected by a working session.

Do not enable password SSH, do not enable root SSH, and do not `ufw disable` as a shortcut. The
first two are permanent weakenings for a temporary problem; the third exposes every port on the
host to the internet for as long as it stays off.

## 4. Verification

This procedure is not documentation until it has been executed once. The A4 exit criteria below
require one rehearsed console recovery, so that the first time it is performed is not during a
contest.

Rehearse with a **documentation-only address**, never with the operator's real one. The real
address already has a rule, so `ufw allow` for it answers "Skipping adding existing rule" and
proves only that the console can log in - not that a rule can be added. `192.0.2.1/32` is
RFC 5737 TEST-NET-1: it is reserved for documentation and is not routable on the public internet,
so adding it opens nothing while exercising the exact commands.

```bash
sudo ufw status numbered
sudo ufw allow from 192.0.2.1/32 to any port 22 proto tcp comment 'console rehearsal, delete me'
sudo ufw status numbered      # the new rule is present and the real one is untouched
sudo ufw delete <number>      # the number of the rehearsal rule
sudo ufw status numbered      # back to exactly the rules you started with
```

Keep the existing SSH session open throughout, exactly as in section 2. The rehearsal is a drill
for a lockout, not a reason to cause one.

## 5. Console recovery rehearsal log

| Date | Operator | Outcome |
|---|---|---|
| 2026-08-06 | dnhynk | Success. Console login as `root`, rule for `192.0.2.1/32` added, observed in `ufw status numbered` alongside the untouched operator rule, then deleted. |

Verified on the host afterwards: exactly one rule remains, the original one; `sshd -T` still
reports `passwordauthentication no` and `permitrootlogin without-password`; `ctf` is still
password-locked and `root` still has a usable password. The rehearsal changed nothing it did not
change back.

Preparing this rehearsal is what found the defect it existed to find: the procedure said to log in
as `ctf`, and `ctf` cannot log in at the console at all. Had that been discovered during a real
lockout there would have been no way in.
