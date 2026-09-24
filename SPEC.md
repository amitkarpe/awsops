# Specification

Status: ACTIVE - M2 live accepted; M3C integration, native canary still pending.

## Goal and layering

Read evidence -> normalized finding -> fresh freeze -> native human choice
-> durable receipt -> independent provider readback. Remediation is disabled.
Domain/decision records remain independent of LibreChat and AWS clients.
There is no generic model-facing AWS or decision API.

## Evidence and preparation

- Exactly four private registered LAB bindings: lab-dev, lab-poc, lab-qa,
  lab-sec; expected controller/read-role identities and ap-southeast-1 Region.
- Fixed bounded SDK reads verify returned Region and expected bucket owner.
  Partial, unavailable, UNKNOWN or stale evidence cannot become preparation.
- Digests bind actual policy, identity, resource, Region and evaluator version.
  Provider readback compares policy evidence, not a compliance label alone.
- Candidate input nominates alias/resource reference/expected digest. It never
  supplies a frozen scope, provider policy, account ID, role or AWS operation.
- Prepare rereads provider truth and expires within five minutes. Model input,
  JSON value types and digests are not authorization.

## Durable native decisions

- One private SQLite ledger records PREPARE_FROZEN and NATIVE_DECISION.
- Exact server-owned tool/principal/tenant/conversation/action/generation/call
  binding is persisted as a digest. The platform owns authentication and claims.
- Final choices return only after commit. Replay, mismatch, expiry or storage
  failure cannot continue the native job. Audit reads never mint continuation.
- Reject records REJECTED. Synthetic Approve records APPROVE_BLOCKED and maps
  to reject; no executor exists. Live Approve remains prohibited.
- Hash links/triggers detect ordinary corruption under trusted local server/
  filesystem administration; they are not an externally anchored audit service.

## Trusted pause producer and private processes

- An exact source-pinned insertion runs BEFORE native approvals.pause/card
  publication. The actual running generation/user/tenant/agent is validated.
- One exact reject-only tool nominates a candidate. The provider process reads
  fresh evidence, freezes it and commits its native registration before reply.
- Native identity and candidate are rechecked after provider work. Only then
  may the pending action receive the committed batch/scope and reduced expiry.
- Failure/lost acknowledgement or losing the subsequent native pause claim
  can leave orphan PREPARE evidence, never readiness or execution authority.
  Preserve/reconcile it; do not silently rebind or manufacture a decision.
- Only ['reject'] is offered on the native card. Unrelated tools bypass the
  canary integration; mixed/reserved lookalikes and edited input fail closed.
- Receipt and provider processes are separate. The receipt child receives no
  credentials. The provider child uses only the configured existing local SDK
  profile, not copied parent/browser tokens. Bounded pipes expose no listener.
- A bound REJECTED receipt permits fresh read-only comparison after reopening
  state, without restoring the planning cache/job. Missing, expired, changed,
  partial or unknown evidence cannot report unchanged. Readback output must be
  retained in the final canary evidence packet; no new ledger event is claimed.
- Runtime controller tests explicitly stub external auth/store/model services.
  They cannot certify native login, complete application startup or browser E2E.

## Deployment and rollback

Issue #11 records the approved isolated canary on the existing verified LAB
host, separate files/chat/checkpoint/ledger state, loopback only and no changes
to existing services. Preflight has run; no canary was launched. Source pins,
capacity, normal native authentication and isolated writable state must all
pass before a live run. New native auth account/session-secret provisioning
requires its explicit gate; do not reuse the old database or extract its keys.

The source patch utility still edits only marked offline candidates. Verify
both producer and resume components before startup. Partial apply/drift must
refuse startup; rollback only restores its exact files and never deletes audit.
No existing service restart, auth bypass, public DNS/ingress/network, IAM/OIDC,
new AWS resource, company/PROD or old-repository mutation is authorized.

M3 overall requires REAL authenticated native Reject, durable receipt, fresh
provider readback and cleanup. M4 mutation needs separate exact-canary authority.
Public proof uses aliases/digests, never private account/resource/native IDs,
policies, login material or browser state.
