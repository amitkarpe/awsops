# Specification

Status: ACTIVE - M2 evidence hardening; live acceptance pending.

## Goal and layering

Read evidence -> normalized finding -> exact fresh prepare/freeze -> native
human decision -> durable receipt -> bounded action -> independent readback.

Domain contracts do not depend on LibreChat. AWS reads, controls, approval,
execution and runtime integration remain separate. M2 implements only the
read/prepare/readback portion. No executor or native decision is exposed yet.

## Current security contract

- Model/user input nominates an alias, resource reference and expected digest;
  it never supplies authoritative evidence, an account ID, role or AWS API.
- Prepare rereads provider truth. Incomplete, unverified, stale, UNKNOWN or
  changed candidate evidence cannot be prepared.
- Four distinct operator-registered LAB aliases only: lab-dev, lab-poc,
  lab-qa, lab-sec. Controller and assumed target identity must match private
  bindings. Client and returned bucket Region must be ap-southeast-1.
- Provider reads use bounded pagination and an expected-owner guard. Limits
  and provider failures are explicit, never silently complete.
- The TLS evaluator proves only its documented conventional policy pattern.
  UNKNOWN is not COMPLIANT and is not an AWS Config evaluation result.
- Digests bind provider policy, identity binding, resource, Region and evaluator
  version. They are not authorization tokens. Observation time is separate.
- Preparations have unique IDs, exact scope hashes and a maximum five-minute
  TTL. They are server-owned in-process planning records, not durable approval
  receipts. Restart invalidates them; M3 will own durable human decisions.
- Readback compares actual policy evidence, not just a compliance label.
  Missing, partial, expired or unavailable evidence is never unchanged success.
- No live remediation, Approve, generic AWS API tool, deployment, IAM/OIDC,
  network/public exposure, new credential or company/PROD work is authorized.
- Public evidence contains aliases and digests, not raw policies, account IDs,
  bucket names, runtime credentials or browser state.

## Milestone boundaries

M1 is merged. M2 needs corrected-code tests AND fresh target-scoped LAB evidence.
M3 native Reject-only integration starts after M2 acceptance; its durable
receipt and runtime adapter must remain separate from domain logic.
M4 mutation controls need their own exact canary authority. Existing v1 write
permissions are not inherited by this repository. M5 cutover remains future.
