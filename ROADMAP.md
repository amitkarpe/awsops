# Roadmap

Owning roadmap: Issue #1. G owns implementation and verification.

## M1 - clean migration bootstrap - COMPLETE

Layered source layout, current-only docs, selective migration and CI.

## M2 - trustworthy read/prepare/readback - ACCEPTED

The corrected reader passed four verified LAB aliases and one fresh exact
preparation/readback through the isolated SSM probe. Evidence is in
`docs/evidence/M2_LAB_READ.json`. Temporary files were removed; services unchanged.

## M3 - native Reject-only decision - IN PROGRESS

- M3A (#7 / #8): private durable ledger and runtime-neutral decision adapter.
- M3B (#9 / #10): private receipt pipe, pinned resume seam and offline rollback.
- M3C (#11 / #12): trusted pause producer, fresh provider registration before
  readiness, and bound post-Reject readback. Repository code is accepted.
- Draft PR #13 owns the isolated real normal-auth browser acceptance.

Require authenticated native Reject, durable receipt, zero dispatch, unchanged
provider readback, supported Archive cleanup and retained-service protection.

## Operational hygiene - AWS resource ledger - IN PROGRESS (#14)

- One canonical public Markdown ledger: `docs/current/AWS_RESOURCES.md`.
- Read-only collector groups live tagged resources without raw provider IDs.
- Cost basis is explicit: ACTUAL / EST / USAGE-BASED / DIRECT-$0 / UNKNOWN.
- Current EC2 evidence recommends keeping `t3.medium`; `t3.small` is memory-tight.
- Live multi-account inventory coverage is still evidence-scoped; no auto-cleanup.

## M4 - bounded remediation migration - NOT STARTED

Only S3 BPA and restricted SSH on retained demo scope may be considered.
Separate exact-canary authority is required before any live Approve or write.
Every new/retained M4 AWS resource must appear in the resource ledger.

## M5 - parity and cutover - NOT STARTED

Parity/deferred list, deployment/runbook and explicit cutover. Preserve source
history and evidence; no destructive old-repository cleanup.
