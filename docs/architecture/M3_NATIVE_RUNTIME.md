# M3B - native runtime bridge and isolated rollback rehearsal

Owner: G, Issue #9 under roadmap #1. Repository integration, not deployment.

## Small integration boundary

Node native platform -> private child-process stdin -> existing Python ledger
-> commit -> validated reject resolution -> native continuation.

No HTTP service, new shared secret, browser token extraction, generic tool,
AWS client or remediation executor is added. Credentials are not forwarded to
the Python child. This IPC is NOT authentication: trusted local server code
and the hosting OS own that boundary.

The logical tool is `decide_s3_ssl_reject_only`; the only supported wire name
is `decide_s3_ssl_reject_only_mcp_awsops`. Prefix lookalikes and mixed tool
approvals fail closed. Unrelated native tools bypass the new path unchanged.

The optional private runtime configuration is disabled by absence. It must
have version=1, enabled=true, an exact canary agent_id, and operator-owned
absolute python/source_root/database paths. It contains no secret. Source and
interpreter paths are trusted deployment input, never model or request fields.
The database must already exist in a private owned directory. Requests do not
initialize an absent/empty replacement ledger.

## Registration is a separate, mandatory integration step

The trusted preparation service owns the actual provider-backed FrozenScope.
The native pause producer owns the action/generation/tool-call identity. Once
that exact pause exists, `registerPrepared` binds these two server-owned facts
through the existing DecisionStore.register contract. A model supplies neither.

M3B supplies and tests this callback; it does NOT install a callback into a live
pause producer. Enabling the final-decision seam without trusted registration
cannot pass: the ledger denies missing records. Do not auto-register a scope
from a /resume POST or reconstruct one from a hash to bypass that guard.

The pause producer must withhold the canary's decision readiness if durable
registration fails. Failed/expired registrations require a new preparation;
there is no blind rebind or replay. The eventual canary runtime must prove this
wiring before native browser acceptance, alongside provider-backed preparation.

## Pinned native resume seam

`integration/librechat/upstream.json` pins upstream commit and full Git blob:

- LibreChat tag: v0.8.8-rc1
- commit: eaef87fa2684025627e25d649a56f4f2a63417a7
- controller blob: a5bae98f76d0dac120d72da9bcd5e1c81a144b8d
- controller: api/server/controllers/agents/resume.js

No tag drift, retained-runtime variant or approximate text match is accepted.
The package uses two small insertions in that exact source:

1. After native owner/tenant/action/agent/decision validation, but before the
   resume claim, capture a strict immutable envelope. Disabled/missing config,
   unsupported input or wrong canary identity is denied before claim.
2. After the single winning native CAS, but before ACK/initialization/resume,
   persist the receipt. Only its exact reject resolution may continue.

Only object-form exact control/batch_id/scope_hash arguments are supported.
Extra fields, string arguments and edit/respond choices are deliberately denied.
The canary requires the explicit generationCreatedAt identity even where the
upstream legacy route allows omission. Single-tenant bindings use a distinct
server sentinel, not an untrusted default tenant.

## Failure and reconciliation

A receipt subprocess has bounded input/output and a four-second deadline.
Failure kills only that child; it does not retry. The child may have committed
before an ACK was lost: audit inspect is the recovery action, never re-record
or re-resume. Inspect returns no continuation.

On post-claim receipt failure the controller does not ACK success or rebuild
the model client. It calls the platform's existing completeJob with the exact
createdAt fence, and prunes only that generation's checkpoint after a confirmed
terminal win. Concurrency release is attempted separately even if terminal or
checkpoint storage fails. Each cleanup call is bounded. A timeout/false/failure
returns RECONCILE_REQUIRED, not a false claim of cleanup or success. A late
terminal operation still carries its old generation fence.

These are controller-contract tests with the native manager/checkpointer and
model client stubbed, not a test of real Redis/Mongo persistence, authentication
middleware, UI rendering or provider readback. The genuine Python SQLite store
and private process bridge run in the cross-language tests.

## Rehearsal and rollback

`rehearse_patch.cjs` only operates on an explicitly marked offline candidate
copy. Check is read-only. Apply verifies the complete upstream blob and a unique
seam, backs up original bytes, writes the helper and atomically replaces the
controller. Reapply is idempotent. A lock prevents concurrent cooperating edits.
Rollback verifies source/helper/original bytes before restoring the controller
and removing only its own unchanged helper. It never removes a decision ledger.
Drift, symlinks, missing markers or an incomplete backup refuse changes. A
crash/staged-file/lock residue is an explicit recovery condition, not permission
for broad deletion. The marker is a safety interlock, not deployment authority.

CI downloads the one immutable upstream controller, verifies its Git blob, then
runs its patched controller with explicit external dependency stubs. No upstream
source history or dependency tree is copied into this repository. The fixture
lives under ignored artifacts. CI fails rather than silently skipping it.
Local tests can run without network, but report the two fixture groups skipped;
that is insufficient for integration acceptance.

## Proposed isolated canary boundary - NOT AUTHORIZED TO DEPLOY

Target: the same owner-verified personal-LAB host used in #6, ap-southeast-1.
Before use, reverify exact account/instance/Region, capacity and SSM identity.
No new EC2, target role, AWS resource, public DNS, ingress or cross-account trust.

Proposed runtime namespace: awsops-native-canary, separate candidate files,
separate decision/checkpoint/chat state and a dedicated agent. Never point it
at the old runtime's writable databases, ledger, service unit or configuration.
Do not restart/replace the retained LibreChat services. Any loopback listener,
new native session configuration or credential provisioning needs the explicit
canary authority; it is not covered by M2's completed temporary SSM probe.

One cohesive canary run must establish all of the following:
- the actual trusted provider prepare/pause registration path;
- normal native authentication and ownership, with auth data staying in-browser;
- exact pinned source and helper plus private ledger wiring;
- only fixed read/prepare and this reject-only tool on the canary agent;
- authenticated native Reject, durable receipt, zero remediation dispatch;
- fresh provider-policy readback and supported disposable-chat cleanup;
- failure/restart/reconciliation plus a rollback that stops only the canary,
  preserves audit evidence and proves the old service identities are unchanged.

No live Approve is authorized. Configure reject-only native allowed decisions;
synthetic blocked-Approve tests are defense-in-depth, not a live test plan.
Do not enable the canary merely because repository CI is green.

## Source references

- https://github.com/danny-avila/LibreChat/blob/eaef87fa2684025627e25d649a56f4f2a63417a7/api/server/controllers/agents/resume.js
- https://github.com/danny-avila/LibreChat/blob/eaef87fa2684025627e25d649a56f4f2a63417a7/packages/api/src/agents/hitl/hooks.ts
- https://github.com/danny-avila/LibreChat/blob/eaef87fa2684025627e25d649a56f4f2a63417a7/packages/api/src/agents/hitl/resume.ts

The supported pre-tool hook is not a final human-decision callback. The native
resume integration is an explicitly pinned patch, not an upstream supported
plugin API. Future upstream updates require a new source review and fixture.
