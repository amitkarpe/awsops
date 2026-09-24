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
  readiness, and bound post-Reject readback. Review/CI establish code acceptance.

The real isolated native canary is NOT accepted. Preflight only has run;
normal isolated login/session provisioning remains an explicit gate. No old
runtime/database/credential copying to bypass it. Continue in #11, not a new
sequence of troubleshooting issues. Require authenticated native Reject,
receipt, unchanged provider readback, cleanup and retained-service protection.

## M4 - bounded remediation migration - NOT STARTED

Only S3 BPA and restricted SSH on retained demo scope may be considered.
Separate exact-canary authority is required before any live Approve or write.

## M5 - parity and cutover - NOT STARTED

Parity/deferred list, deployment/runbook and explicit cutover. Preserve source
history and evidence; no destructive old-repository cleanup.
