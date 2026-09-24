# Roadmap

Owning roadmap: Issue #1. G owns direct implementation and verification.

## M1 - clean migration bootstrap - COMPLETE

Layered source layout, current-only control docs, selective migration matrix
and dependency-free CI. No wholesale source-repo copy.

## M2 - trustworthy read/prepare/readback - ACCEPTED

PR #5 hardened evidence/identity/completeness/freshness. Issue #6 executed its
exact merged reader on the retained LAB host: four aliases identity/Region
verified, complete inventory, one fresh lab-dev preparation, unchanged actual
provider-policy readback. 52 tests passed on that runner. Temporary files were
removed and deployed services were unchanged. See `docs/evidence/M2_LAB_READ.json`.

## M3 - native Reject-only decision - IN PROGRESS

M3A / Issue #7: repository-only durable ledger and runtime-neutral native
adapter. Native scope is exact; receipt commit precedes return. Reject records
REJECTED, synthetic Approve records APPROVE_BLOCKED, neither permits dispatch.

M3 live acceptance is NOT complete. Next: reviewed platform-specific wiring,
normal authenticated session, one native Reject, durable receipt, fresh
provider readback, cleanup and failure/terminalization proof. Do not infer
runtime deployment authority from repository merge or M2's temporary SSM probe.

## M4 - bounded remediation migration - NOT STARTED

Only S3 BPA and restricted SSH on retained demo scope may be considered.
Code migration and synthetic tests do not authorize live AWS mutation.
Require a separate explicit exact-canary authority before any live Approve.

## M5 - parity and cutover - NOT STARTED

Parity/deferred list, deployment/runbook, explicit cutover. Preserve source
history and evidence; no destructive old-repository cleanup.
