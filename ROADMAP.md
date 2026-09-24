# Roadmap

Owning roadmap: Issue #1. G owns direct implementation and verification.

## M1 - clean migration bootstrap - COMPLETE

Layered layout, current-only control docs, selective migration and credential-
free CI. No wholesale source-repo copy.

## M2 - trustworthy read/prepare/readback - ACCEPTED

PR #5 hardened evidence/identity/completeness/freshness. Issue #6 executed the
exact corrected reader on the retained LAB host: four verified aliases,
complete inventory and one fresh lab-dev prepare with unchanged policy readback.
Temporary files were removed and deployed services unchanged. Evidence is in
`docs/evidence/M2_LAB_READ.json`.

## M3 - native Reject-only decision - IN PROGRESS

M3A / #7 / PR #8: accepted repository-only private durable ledger. Exact binding,
commit-before-return, replay/expiry checks, Reject and blocked-Approve handling.

M3B / #9: private process bridge, source-pinned native resume integration,
controller-contract rehearsal and isolated apply/rollback tool. Full exact-head
CI/review must pass. It does not install a live pause producer or authenticate
users. Proposed canary boundary: `docs/architecture/M3_NATIVE_RUNTIME.md`.

M3 live acceptance is NOT complete. The next canary must connect trusted native
pause registration, normal login, real Reject, durable receipt, fresh provider
readback, cleanup and recovery. Exact deployment authority is still required;
M2's previous temporary probe is not blanket runtime authority.

## M4 - bounded remediation migration - NOT STARTED

Only S3 BPA and restricted SSH on retained demo scope may be considered.
Separate exact-canary authority is required before live mutation/Approve.

## M5 - parity and cutover - NOT STARTED

Parity/deferred list, runbook and explicit cutover. Preserve old source/history.
