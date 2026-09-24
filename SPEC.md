# Specification

Status: ACTIVE - M2 live accepted; M3 repository integration, not deployed.

## Goal and layering

Read evidence -> normalized finding -> fresh freeze -> native human choice
-> durable receipt -> bounded action -> independent provider readback.
Domain and decision records do not depend on LibreChat or AWS clients.
Remediation is disabled; no model-facing executor or decision API is enabled.

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
- Unique in-process planning scopes expire within five minutes. Registration
  requires the actual server/provider-backed scope, not caller JSON or a hash.

## M3A durable decision contract

- One private SQLite ledger records PREPARE_FROZEN and NATIVE_DECISION events.
- Exact tool/principal/tenant/conversation/action/generation/tool-call binding
  is stored as a digest with the frozen scope. Neither digest is a credential.
- Native authentication/ownership and the winning resume claim belong to the
  hosting platform, before final decision handling. JSON/Python value types
  do not form an authentication boundary against untrusted server code.
- A final decision returns only after its database transaction commits.
  Replay, mismatch, expiry and persistence failure produce no continuation.
- Reject records REJECTED. A synthetic Approve records APPROVE_BLOCKED and
  maps to reject. Both have dispatch_allowed=false; no executor exists.
- A lost response after commit requires bound audit read, never re-resume.
- Filesystem/server administrators are trusted. Hash links/triggers detect
  ordinary corruption; this is not an externally anchored audit service.

## M3B native-runtime integration contract

- Default-off private OS-pipe bridge reuses the existing ledger. No new HTTP
  listener, shared secret, browser credential extraction or cloud dependency.
- Only a trusted pause producer may register the provider-backed scope with
  the actual native action identity. Missing registration cannot be bypassed
  by auto-registering request input during resume.
- Exact pinned upstream controller: native guards, strict canary envelope,
  existing single-winner CAS, committed receipt, then only a reject resolution.
- Mixed/unknown tool requests and edited scope/decisions fail closed. Existing
  unrelated native tool paths bypass the new integration unchanged.
- Receipt failure before continuation attempts exact-generation terminalization,
  checkpoint cleanup only on a confirmed win, and separate slot release.
  Timeout/failure reports RECONCILE_REQUIRED. No blind retry or fake success.
- The offline candidate patch tool verifies source/helper bytes and refuses
  drift or unsafe paths. It never operates a service or deletes ledger state.
- Controller tests stub external native/auth/persistence/model dependencies.
  They do not certify production authentication, Redis/Mongo or browser E2E.

## Live and publication boundaries

Issue #6's authorized temporary read-only SSM probe is complete and cleaned.
Issue #9 permits repository/local/CI integration and rollback rehearsal only.
The canary plan in docs/architecture/M3_NATIVE_RUNTIME.md needs explicit exact
deployment scope before new processes, listeners, runtime/auth/state changes.
No change to the retained LibreChat service is inherited from repository merge.

No live Approve, remediation, generic AWS operation, credential/IAM/OIDC/network
or public exposure change, company/PROD or old-runtime modification. Synthetic
blocked-Approve tests have no AWS/native production access. Public proof uses
aliases/digests, not raw policies, account IDs, bucket names, native identities
or browser state. M3 full acceptance still needs trusted pause wiring, normal
login, native Reject, durable receipt, fresh provider readback and cleanup.

M4 mutation controls require separate exact canary authority. M5 remains future.
