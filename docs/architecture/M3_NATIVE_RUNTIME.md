# Native runtime integration and isolated canary

Owner: G, Issue #11 under roadmap #1. M3B is merged; M3C adds trusted pause
registration and readback. Repository acceptance is separate from live canary.

## One native UI, separate private responsibilities

```text
normal authenticated native run
  -> exact reject-only candidate nomination
  -> trusted native pause producer
  -> private provider process: fresh read/freeze + ledger registration
  -> registration committed, generation rechecked
  -> native pause claim/card
  -> human Reject
  -> native resume guards + single winning claim
  -> credential-free receipt process: committed REJECTED
  -> only reject resolution
  -> private provider readback bound to the consumed receipt
```

No new HTTP decision endpoint, second approval UI, generic AWS API or executor
exists. Domain/ledger code does not depend on LibreChat. Private OS pipes still
trust the local server and filesystem; they do not authenticate users.

## Exact tool and producer contract

Logical tool: `decide_s3_ssl_reject_only`.
Native wire name: `decide_s3_ssl_reject_only_mcp_awsops`.
The candidate tool schema must permit exactly `control`, `account_alias`,
`resource_ref`, `expected_evidence_digest`. A model may nominate only these.
The real application tool registration and browser wiring remain canary work;
a Python test fixture or a copied pending action must not stand in for them.

The supported pre-tool hook factory `pause_gate.cjs.approvalHook` offers only
Reject. Register it only for the exact canary tool/agent through native policy;
it requests review and is not the durable registration point.

The pinned producer's `handleRunInterrupt` builds the actual action ID, then
`beforePause` verifies authenticated server ownership, tenant, running
createdAt generation, agent and single exact tool. The private provider process
uses the M2 reader, complete verified fleet evidence and fresh preparation. It
binds the resulting scope to that exact native action before committing.

Only a successful reply and a second identical native-context check allow the
producer to replace candidate arguments with `control/batch_id/scope_hash` and
reduce native expiry. Then the existing native pause CAS and publication run.
A stale/changed/mixed action, unsupported choices, failed provider read or
registration failure cannot publish a card. Reject skips the underlying tool;
rewriting the pending review payload does not authorize checkpoint execution.

A lost acknowledgement or lost pause claim may leave an immutable orphan
PREPARE_FROZEN event. It has no native readiness/decision and grants no dispatch.
Do not erase it, replay it or silently rebind it. Reconcile and prepare anew.

## Private process configuration

`AWSOPS_NATIVE_CONFIG` remains an owned private file with exact fields:
`version`, `enabled`, `agent_id`, `python`, `source_root`, `database`.
Absent/disabled/invalid configuration denies the reserved tool. Database and
its parent must be private and already provisioned; requests never replace a
missing ledger. Paths/interpreter are trusted operator input, never tool args.

`AWSOPS_READ_CONFIG` points to a separate private operator-owned read config
using the existing M2 profile/account bindings. The provider process retains
HOME to use that named local profile; no parent AWS or browser credential
variables are forwarded. IMDS fallback is disabled. The receipt process still
receives only LANG, with no AWS credential access. Neither path prints secrets.

The provider pipe caps input/output at 16 KiB and kills only its child after
30 seconds. The receipt pipe retains its four-second bound. Neither silently
retries. A source/profile/SDK failure is not permission to broaden IAM or copy
credentials. The tests' `pause_seed.py` is synthetic and NEVER a live launcher.

## Bound readback, not continuation

The trusted server may invoke `readbackRejected` using its immutable decision
envelope. Python verifies the exact native binding, scope and a durable
REJECTED receipt before target reads. It can reopen the ledger and a fresh
read service without restoring the old in-process preparation cache or job.

Fresh policy evidence must still match, with complete fleet identity/Region
coverage and an unexpired preparation. Otherwise unchanged is false. UNKNOWN,
UNAVAILABLE, partial reads and same-status policy drift are not success.
This operation does not append a decision, offer a continuation or mutate AWS.
Its receipt-linked result must be included in the final durable evidence
packet; a third ledger event or automatic native UI publication is not claimed.

## Immutable source and offline rollback

Upstream repository ID 600596928 now resolves to `LibreChat-AI/LibreChat`.
The commit pin is unchanged: `eaef87fa2684025627e25d649a56f4f2a63417a7`.
`upstream.json` pins full producer and resume Git blobs. CI explicitly fetches
both and refuses drift; no full upstream checkout/history is committed here.

`rehearse_patch.cjs` uses marked OFFLINE candidates only. The optional component
is `resume` (default) or `pause`. It preserves exact originals and verifies
source/helper bytes on check/reapply/rollback. Producer and resume use the same
edit lock but separate backups; multi-file atomic installation is NOT claimed.
Both components must verify before any future canary startup. A partial copy,
missing helper, lock residue or drift is reconciliation-required, not permission
for broad cleanup. Rollback does not delete the decision ledger.

The resume failure path still uses generation-fenced terminalization, conditional
checkpoint cleanup and independent slot release; timeout reports reconciliation.
The producer failure path raises before pause publication and relies on the
normal native run error lifecycle. Rehearsal does not prove all outer lifecycle,
Redis/Mongo, native authentication or model execution behavior.

## Live preflight and remaining acceptance

SSM preflight is recorded in `../evidence/M3_CANARY_PREFLIGHT.json`. The existing
services were active, no canary directory existed, and the retained resume
was already a different patched variant. Do NOT apply clean-source patches to
that retained service or reuse its writable database, cookies or secret files.
Capacity was measured; full-runtime resource use remains unproven, not declared
safe or unsafe solely from one free-memory snapshot.

Issue #11 permits a separate loopback canary on the same verified LAB host;
no new EC2, ingress/DNS/IAM or existing-service changes. No canary process,
listener, login, credential or native decision was created by this preflight.
Creating its disposable normal login and local session-signing keys requires
the explicit auth-provisioning gate. No secrets should be pasted into chat.

After that gate, continue in #11: capacity-limited clean pinned candidate,
separate state, real tool/native policy registration, normal login, fresh
read/prepare, native Reject, receipt/readback, supported chat cleanup, canary
rollback and confirmation that existing services remain unaffected. No live
Approve. Stop only canary processes; preserve sanitized acceptance/audit proof.

## Test interpretation

Python tests use the genuine evidence service and SQLite ledger with synthetic
providers. Node tests extract and execute the exact pinned producer method;
M3B tests execute the exact pinned resume controller. External native managers,
authentication, model services and publication helpers are explicitly doubled.
The genuine Python private processes/ledger run in cross-language tests.

CI must run all fixture-dependent groups without skips. These results establish
producer/receipt/readback contracts and offline rollback, NOT a browser pass.
M3 and #11 remain incomplete until the real authenticated canary succeeds.
