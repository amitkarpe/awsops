# Specification

Status: ACTIVE - Home read-only v1 supported; M3 live acceptance deferred; M4 unauthorized.

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


## Supported Home read-only v1

Home is the supported NEW runtime. The retained `amit` EC2 is stopped and is
recovery state only. `python scripts/home_demo.py validate` is the canonical
fail-closed local validation command. It performs loopback GETs only and requires:

- config2 `READY`, `partial=false`, exactly four aliases, eight checks and two controls;
- sec2 application health;
- exactly one `ask_compliance_agent` MCP tool and zero actions;
- the existing Status / Explain / no-change Plan browser evidence, rendered-output
  binding and Archive cleanup.

Owner-private configuration remains outside Git under the existing schemas.
Cloudflare quick tunnel is optional demo transport, not permanent infrastructure.
The validator creates no AWS capability and performs no cloud mutation.

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

## Personal LAB credential standing authority

For this repository's **personal LAB/DEV demo surfaces only**, Amit grants G
standing authority to manage ordinary application/demo user credentials without
a new approval for each account operation. G may perform the change directly
when tooling allows or delegate it to the matching X/Codex worker.

Within this boundary, G/X may:

- reuse existing project credentials from the retained private `.env`, GitHub
  repository/environment secret or variable stores, and AWS Secrets Manager;
- create an application/demo user when the required LAB identity is absent;
- assign or reset a LAB application password/credential when needed to restore
  an approved demo or development journey;
- keep the same credential synchronized across the approved private stores when
  that is already the project pattern;
- share the LAB username/password back to Amit through the private chat/session
  or another private owner channel when needed for manual testing.

Do not place secret values in this public repository, Issues, PRs, Actions logs,
or public evidence. Prefer reusing an existing credential over generating a new
one when the existing private source is valid. This standing authority covers
application/demo credentials for config/sec/sync and related personal-LAB
surfaces; it does **not** authorize PROD/company credentials, AWS IAM/SSO/access
keys, broad secret rotation, OLD-environment credential copying, or unrelated
identity-system changes.

## Deployment and rollback

Issue #11 / PR #13 remain deferred. Their isolated canary contract is preserved,
but no canary may launch unless Amit explicitly reprioritizes M3 live acceptance. Source pins,
capacity, normal native authentication and isolated writable state must all
pass before a live run. New native auth account/session-secret provisioning
requires its explicit gate; do not reuse the old database or extract its keys.

The source patch utility still edits only marked offline candidates. Verify
both producer and resume components before startup. Partial apply/drift must
refuse startup; rollback only restores its exact files and never deletes audit.
No existing service restart, auth bypass, public DNS/ingress/network, IAM/OIDC,
new AWS resource, company/PROD or old-repository mutation is authorized.

M3 repository work is complete, but REAL authenticated native Reject, durable
receipt, fresh provider readback and cleanup remain DEFERRED. M4 is NOT STARTED
and has no mutation authority while that priority remains deferred.
Public proof uses aliases/digests, never private account/resource/native IDs,
policies, login material or browser state.
