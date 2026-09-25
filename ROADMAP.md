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

- Canonical public Markdown ledger: `docs/current/AWS_RESOURCES.md`.
- Canonical account aliases are `amit` and `vagent`; raw account IDs stay private.
- Account-first cost watch uses Cost Explorer actual MTD plus explicit EST / USAGE-BASED / DIRECT-$0 / UNKNOWN labels.
- EC2 / always-on compute has a separate high-visibility table.
- `amit` retained host remains `t3.medium`; root gp3 expanded online 20 -> 30 GiB and ext4 usage dropped 92% -> 60% with retained services active.
- `vagent` live read confirms one running expired-TTL `t3.small` learning host plus 109 S3 buckets total; cleanup remains unapproved.
- Home-first compute model is documented in `docs/architecture/DEV_COMPUTE_MODEL.md`: ordinary development stays local/GitHub, `amit` keeps the full M3 integration runtime, and `vagent` is reserved for a future lightweight AWS canary after an explicit repurpose gate.
- EC2 Name tags are part of the canonical high-cost/resource ledger view.
- No auto-cleanup. Any deletion/termination/repurpose is a separate exact mutation boundary.

## M4 - bounded remediation migration - NOT STARTED

Only S3 BPA and restricted SSH on retained demo scope may be considered.
Separate exact-canary authority is required before any live Approve or write.
Every new/retained M4 AWS resource must appear in the resource ledger.

## M5 - parity and cutover - NOT STARTED

Parity/deferred list, deployment/runbook and explicit cutover. Preserve source
history and evidence; no destructive old-repository cleanup.
