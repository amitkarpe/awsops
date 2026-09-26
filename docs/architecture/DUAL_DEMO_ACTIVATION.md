# Dual-demo activation and recovery contract

Owner: Issue #29 M3 under roadmap #1
Status: DESIGN ONLY — no live environment, service, proxy, or DNS changes

## Purpose and names

Keep the reference demo and the `awsops` demo independently recoverable. Home
DEV remains the normal development environment; AWS is used only for an approved
short demo/UAT window. This document proposes an activation contract. It does
not prove either demo can currently start, imply that the proposed names resolve,
or authorize an activation.

| Environment | Intended URLs | Status |
| --- | --- | --- |
| OLD / reference | `ops.astromedicomp.org`, `sec.astromedicomp.org` | Preserve as a recoverable reference. |
| NEW / `awsops` | `ops2.astromedicomp.org`, `sec2.astromedicomp.org` | Proposed names; DNS and routing are unverified. |

The old `vagent` learning host is not synonymous with the OLD/reference demo.
The retained `amit` host is documented as hosting the full LibreChat/Ops/
MongoDB integration runtime; that fact does not identify which demo owns each
service or establish the proposed NEW mapping.

## Mapping and isolation contract

The repository has no verified, current inventory assigning demo directories,
service units, listener ports, health paths, database names/volumes, proxy
targets, or DNS records to OLD and NEW. Resolve each item from an approved,
read-only host/config inventory and record it in the activation change before
acting. Do not guess from historical evidence or reuse a value from the
disposable Issue #11 browser canary.

| Boundary | OLD / reference | NEW / `awsops` | Required proof |
| --- | --- | --- | --- |
| Checkout and writable app/config roots | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Distinct roots and explicit release revision; no shared writable checkout/config. |
| Service units, users, process targets | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Exact unit/user names and stop targets from the host; no wildcard stop/kill. |
| App and dependency loopback ports | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Actual listeners plus a reserved, non-overlapping NEW assignment; bind privately as designed. |
| MongoDB URI, database, user, data volume | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Separate database identity and writable storage; no cross-environment writes. |
| Auth/session keys and account boundary | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Independent private configuration and session-signing material; no copied credentials. |
| Browser profile, cookies, local storage | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Separate profile directories and login/session state. Never copy browser state. |
| Logs, receipts, ledgers, checkpoints, uploads | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Separate writable paths and retention; preserve both evidence sets. |
| Proxy virtual hosts, TLS, upstreams, DNS | Existing targets and records: `VERIFY-BEFORE-ACTIVATION` | Proposed names and targets: `VERIFY-BEFORE-ACTIVATION` | Read-only before/after inventory; exact host, certificate, listener, upstream, and record mapping. |

The intended proxy design is one explicit virtual-host mapping per hostname:
the two OLD names route only to the OLD app upstreams, and the two proposed NEW
names route only to separately assigned NEW app upstreams. Keep app and database
listeners private; publish only the approved TLS proxy entrypoint. Exact
addresses, listener ports, service names, upstreams, certificate coverage, DNS
record values/TTLs, and health paths remain `VERIFY-BEFORE-ACTIVATION`. Do not
point a public name at a development or disposable canary listener. In
particular, loopback ports used by the Issue #11 isolated browser canary are not
the demo port map.

No shared writable database, volume, session store, auth key, browser profile,
or evidence directory is allowed by this design. If a future verified topology
requires sharing, stop and obtain a reviewed, explicit exception that explains
consistency, access, rollback, and blast-radius behavior before activation.

## Collision preflight — all checks must pass

Record a sanitized baseline for both environments and check all of the
following before any future service, proxy, or DNS action:

- [ ] Confirm the owning Issue names the environment, reviewed commit, operator,
  account/Region, allowed actions, timebox, health checks, rollback target, and
  stop procedure.
- [ ] Inventory exact checkout/config/data roots, owners, permissions, current
  revisions, service units/users, process IDs, and current health for OLD and
  NEW. Confirm no path or stop target overlaps.
- [ ] Read current listeners and proxy configuration. Confirm all OLD and NEW
  app/dependency ports are distinct, available for their intended role, and
  loopback/private where required. Check that no unrelated listener is targeted.
- [ ] Confirm each hostname has exactly the intended virtual host, TLS
  certificate coverage, upstream, and DNS target/TTL. Detect duplicate
  `server_name` entries, wildcard/default-host collisions, stale records, and
  unintended public listeners. Proposed NEW DNS remains untouched until a
  separate explicit change gate passes.
- [ ] Confirm MongoDB connection identities, database names, users, volumes,
  backup/recovery points, and write targets are distinct. Check any cache,
  queue, object storage, upload directory, or shared filesystem used by either
  app for the same isolation.
- [ ] Confirm independent auth configuration, session/signing keys, cookie
  domains, browser profile paths, and test accounts. Do not copy or print
  credentials, cookies, tokens, or profile contents.
- [ ] Confirm log, audit, receipt, ledger, checkpoint, and evidence paths are
  separate and retained. Verify the rollback revision/config is available
  without deleting or rewriting evidence.
- [ ] Confirm start/stop commands name only the selected environment's exact
  services. No broad process kill, shared dependency restart, cleanup, or
  deletion is part of this contract.
- [ ] Capture read-only OLD/reference health and revision evidence before the
  NEW change so the post-check can demonstrate it was untouched.

Any unknown, overlap, unexpected listener, ambiguous ownership, failed health
check, or missing rollback target is a stop condition. Resolve it in the
activation review; do not improvise during the window.

## Activation order

This is a future operator sequence only; it does not authorize execution.

1. Review this contract and the separate live activation approval. Reconfirm
   the target, reviewed revision, preflight results, timebox, operator,
   communications, stop/rollback commands, and evidence plan.
2. Capture sanitized OLD and NEW baselines: exact revisions, service state,
   listeners, health, and state/config identities. Keep secrets and private
   identifiers out of shared evidence.
3. Start only the selected environment's isolated dependencies that are
   confirmed stopped and required. Verify their own health and storage identity.
4. Start that environment's exact app service(s). Verify expected revision,
   readiness, normal authentication, and dependency connectivity on the private
   loopback endpoints.
5. Only after a separate approved proxy/DNS change gate, apply the reviewed
   host-to-upstream mapping. Validate TLS, hostname routing, health, and login
   for each changed name. Never expose database or app development ports.
6. Run only the short acceptance steps in the owning Issue. Capture sanitized
   results, exact revision, timestamps, health results, and any failed stage.
7. Recheck OLD/reference health and revision against its baseline after NEW
   activation. A changed or unavailable OLD environment fails the independence
   proof; stop the selected NEW work and follow the approved rollback.

No hostname should be activated until its folder/service/port/state/proxy map
is populated with verified values and all collision checks pass.

## Health, stop, and recovery

Health checks must be specified in the activation Issue using verified paths.
At minimum, independently check for each environment: expected hostname and
TLS certificate, exact app revision, documented readiness response, normal
login/session behavior, app-to-database health, and no listener on an
unintended public interface. An open port, running process, or green CI alone
does not establish application readiness or live acceptance.

At the end of a demo window:

1. Save sanitized acceptance output and required logs/evidence; preserve
   receipts, ledgers, checkpoints, and database state.
2. If routing was separately changed, follow that change's approved reversal
   order and verify the intended hostname state. Do not alter OLD routing as an
   ad hoc fix for NEW.
3. Stop only the exact app/dependency services started for the selected demo,
   in reverse dependency order: app first, then only its newly started
   dependencies. Do not stop pre-existing or shared/uncertain services.
4. Verify selected services returned to their recorded baseline and the other
   environment still matches its baseline. Record sanitized final health.
5. If rollback is partial, ambiguous, or makes either environment unhealthy,
   stop further changes and report it through the owning Issue.

Recovery means restarting the preserved, accepted revision with its matching
configuration and state under its environment-specific procedure. Preserve
both demos, data, volumes, addresses, DNS records, proxy configurations,
ledgers, and evidence. **Delete nothing.** No cleanup, repurpose, or retirement
is implied.

## Old/reference untouched proof

Before and after any separately approved NEW activation, compare the sanitized
OLD baseline and final read-only inventory: revision, exact service/process
state, listener ownership, health, and relevant configuration/data identity.
The NEW change must use only its verified isolated roots and targets. Record
the comparison with timestamps and the NEW change identifier. If the OLD
baseline cannot be established or is not preserved, independence is unproven;
do not claim acceptance. This design document itself contains no live proof.

## Separate live activation gate

M3 repository design does not authorize a cloud, DNS, proxy, network, or service
mutation. Before any such work, open/update an owning Issue with explicit
approval for the exact environment and actions; the fully verified mapping and
collision checklist; account/Region and target identities; operator and
timebox; expected health checks; evidence plan; and exact stop/rollback steps.
Review the change plan and obtain the required approval at that time. If any
mapping field remains `VERIFY-BEFORE-ACTIVATION`, do not activate. Keep both
environments recoverable and delete nothing.
