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
The canary tool is registered under MCP server `awsops` as
`approve_s3_canary_once_mcp_awsops`. Its input contains only
`control=s3_canary`; its stdio handler returns a closed response and has no
provider, identity, packet or resource authority. The native pause producer
obtains `req.user` and the winning job generation from the authenticated host,
then privately performs fresh profile/account/Region-checked reads against the
fixed owner binding. It persists the application authority before replacing
the tool arguments with the committed batch, scope and authority digests. A
Python test fixture or copied pending action does not stand in for that flow.

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
`version`, `enabled`, `agent_id`, `python`, `source_root`, `database`,
`source_revision`, `application_database`, `application_binding`, and
`source_version`. `database` remains the native decision store;
`application_database` is the existing canary application ledger. Both are
private files. A narrowly guarded migration accepts only the exact six-field
native-gate v1 config from source commit
`1ee21e15017a066413bf705c96749ab7bf9cffd2`; it preserves `agent_id`, Python,
source-root and native-database paths, then adds the current source pin and
fixed canary paths. It requires the existing private M2 `read.json` contract
(`amit`, `ap-southeast-1`, registered LAB aliases) and the owner-private target
binding to match that source account and the fixed disposable-bucket pattern.
Unknown schemas, aliases, or bindings fail before the config backup or write.
The original bytes are backed up and read back before atomic replacement;
rollback restores those exact bytes. The target account and bucket are resource
scope only, never a substitute for the authenticated `req.user` identity.

On an authenticated pause-preparation request, the existing native
`DecisionStore`, `CanaryAdapter`, and `CanaryApprovalApplication` constructors
may initialize missing private ledger schemas after binding/read-config checks
and before provider construction. Existing recognized records are preserved;
unknown schemas or unsafe ownership/modes refuse readiness. A missing target
binding prevents card preparation. These steps do not create owner identity,
human consent, Approve authority or provider writes.

The binding path is a separate owner-only JSON file containing only
`account_id` and `bucket`; the canary child checks its ownership, permissions
and canonical path before loading it. These values stay out of receipts and
logs.
Absent/disabled/invalid configuration denies the reserved tool. Database and
its parent must be private. Paths/interpreter are trusted operator input, never
tool args.

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

## Issue #11 native decision and Issue #90 canary Reject seams

At the authorized LibreChat pin `cdfe54c3498818b21b33fb609fee02f2742b37ea`,
the legacy path captures the authenticated `req.user`, tenant, exact action and
generation before the native claim, then rereads the running job after the
single-winner CAS clears `pendingAction` and `pendingActionId`. The private
`DecisionStore` / `NativeDecisionAdapter` records Reject as `REJECTED`; legacy
Approve remains `APPROVE_BLOCKED` and resolves only to a blocked Reject response.
The fixed private child has no provider or execution capability.

The separate `approve_s3_canary_once` Reject path uses the same authenticated
host request and winning-CAS seam. It persists that server-owned decision in
`native_owner_decisions`; `NativeServerOwnerVerifier` reads it back and binds
the authenticated principal/tenant to the frozen authority, source revision,
scope and expiry. The verifier then feeds `NativeCanaryApprovalAdapter` and the
existing `CanaryApprovalApplication.decide()` path, whose atomic packet claim,
`canaries` decision and canonical four-envelope receipt remain authoritative.
The adapter factory for this path constructs only an inert Reject-only provider;
Approve is denied before the claim, and neither rejection nor receipt invokes an
AWS provider. The private child receives only the fixed message, source version
and a permission-checked private binding file. OS ownership of the controller,
child and SQLite ledger is the trust boundary; the record digest is an
integrity/reference value, not authentication. No browser/model supplied
identity, callback proof, digest or CAS boolean alone establishes authority.

Fresh packet preparation is distinct from the test-only authority fixtures:
the production pause child constructs only the existing fixed S3 canary reader
and application adapter, and its `prepare` call cannot mutate AWS. The tool's
direct MCP call cannot authorize or dispatch anything. The offline
production-dispatch regression exercises the real Python dispatch,
server-record verifier and application ledger with synthetic identities and a
fake SDK fixture. It does not prove a live authenticated UI click or runtime
installation. The production preparation path constructs the fixed provider
only to perform fresh reads; this source work did not invoke it. Live Approve,
AWS mutation and installation remain outside this source milestone.

The stable producer command exercises the actual native gate, host claim
handoff, Python adapter and application path with a test-only simulated
verifier and the existing Fake SDK:

```sh
python3 scripts/approval_e2e_artifacts.py --native-callback --output ~/.AGENTS-temp/awsops/issue11-native-run-1
```

It emits the unchanged `awsops-canary-e2e/1` summary, canonical four-envelope
receipts and separate lifecycle audits expected by Core2. The output remains
`TEST_SIMULATION`, `FAKE_SDK`, `SYNTHETIC` / `SYNTHETIC_ONLY`, and zero actual
AWS calls. This proves the source seam and artifact contract only; it does not
prove authenticated native UI, a mounted callback, or live approval.

## Immutable source and offline rollback

Upstream repository ID 600596928 now resolves to `LibreChat-AI/LibreChat`.
The authorized commit pin is `cdfe54c3498818b21b33fb609fee02f2742b37ea`.
`upstream.json` pins full producer and resume Git blobs. CI explicitly fetches
both and refuses drift; no full upstream checkout/history is committed here.

`rehearse_patch.cjs` uses marked OFFLINE candidates only. The optional component
is `resume` (default) or `pause`. It preserves exact originals and verifies
source/helper bytes on check/reapply/rollback. Producer and resume use the same
edit lock but separate backups; multi-file atomic installation is NOT claimed.
Both components must verify before any future canary startup. A partial copy,
missing helper, lock residue or drift is reconciliation-required, not permission
for broad cleanup. Rollback does not delete the decision ledger.

The PR13 isolated-root migration uses the versioned policy template
`integration/librechat/migration_pr13_to_89_v1.json`. The private bundle builder
materializes file hashes, rendered controller Git blobs, source revision and
archive digest into a non-template manifest. `isolated_migration.py` accepts
only the exact `/opt/awsops-native-canary` root, pinned cdfe rendered controller
blobs, absent or explicitly allowlisted PR13 legacy files, and exact staged
hashes. It backs up legacy files privately before atomic replacement and
refuses drift. Run `runtime_config.cjs apply` only after the code migration; it
adds the fixed MCP tool and Reject-only native hook while preserving unrelated
YAML. Rollback runs config rollback first, then code migration rollback; each
refuses if a current file no longer matches its staged state. Neither command
starts, stops or restarts a service, and neither changes application state,
credentials or retained service files. The source bundle must pass its archive
digest check (`--archive` is required by both operations) before extraction.
These source contracts do not prove current host compatibility or authorize
installation.

For a reviewed recovery from known metadata drift, manifest version 2 uses a
versioned exact-prestate tuple allowlist per target (content SHA-256, Git blob,
numeric uid/gid and mode, or explicit absence). Host observations belong only
in the private generated manifest, never this repository. Apply validates all
targets before creating exclusive root-only backups, records and fsyncs each
original byte/metadata tuple before replacement, and leaves already-exact
files untouched. Rollback validates every backup and current target before its
first restore, then restores the recorded metadata; it does not infer prior
ownership or mode from the legacy template. Existing v1 bundles remain
readable. A present journal or any tuple mismatch remains reconciliation-only.

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
