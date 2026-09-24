# Specification

Status: ACTIVE - M2 live accepted; M3A repository-only decision boundary.

## Goal and layering

Read evidence -> normalized finding -> exact fresh freeze -> native human
choice -> durable receipt -> bounded action -> independent provider readback.
Domain and decision records do not depend on LibreChat or AWS clients. No
executor, public decision API, model tool or native-runtime deployment is
included in the current M3A package.

## M2 evidence contract

- Candidate input never supplies authoritative policy/account/role/API data.
- Prepare rereads provider truth and requires complete verified coverage,
  current NON_COMPLIANT evidence and an unchanged candidate digest.
- Exactly four distinct private LAB bindings: lab-dev, lab-poc, lab-qa, lab-sec.
  Controller and target read-role identities must match; Region ap-southeast-1.
- Bounded pagination, expected owner and returned bucket Region are enforced.
  Partial/provider/UNKNOWN results cannot be invented into success.
- Digests bind actual policy, identity, resource, Region and evaluator version.
- Provider readback compares policy evidence, not only the compliance label.
- Unique in-process planning scopes expire within five minutes. A server must
  register the actual validated preparation, not a caller-manufactured object.

## M3A durable decision contract

- One private SQLite ledger records PREPARE_FROZEN and NATIVE_DECISION events.
- Exact tool/principal/tenant/conversation/action/generation/tool-call binding
  is stored as a digest with the frozen scope. Neither digest is a credential.
- Native authentication/ownership checks and the single winning resume claim
  belong to the hosting platform, BEFORE this in-process adapter is invoked.
  Python value types are not a security boundary against untrusted server code.
- A final decision is returned only after its database transaction commits.
  Replay, mismatch, expiry and persistence failure produce no continuation.
- Reject records REJECTED. An Approve request records APPROVE_BLOCKED and maps
  to a reject resolution. Both have dispatch_allowed=false; no executor exists.
- Reopen preserves consumed decisions. A persisted receipt does not recreate
  an expired native job or grant permission to resume it again.
- Append-only triggers/hash links detect ordinary corruption. Local filesystem
  administrators are trusted; this is not an externally anchored audit service.
- The future native adapter must prove post-claim storage-failure terminalization
  and authenticated browser Reject/readback/cleanup before M3 is accepted.

## Live and publication boundaries

The user authorized only a temporary read-only SSM probe on the existing
verified retained host for M2. That probe is complete and cleaned. It did not
restart/change deployed services or install dependencies. Future live runtime
changes require an explicit exact target/deployment boundary.

No live Approve, remediation, generic AWS operation, new credential, IAM/OIDC,
network/public exposure, company/PROD or old-runtime modification. Synthetic
unit tests may exercise blocked Approve without AWS/native-platform access.
Public evidence contains aliases/digests, not raw policies/account IDs, bucket
names, credentials, native identity values or browser state.

M4 mutation controls require separate exact canary authority. No source-repo
write permissions are inherited. M5 cutover remains future work.
