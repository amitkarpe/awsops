# Roadmap

Owner: Issue #1. Implementation owner: G.

## M1 - COMPLETE

Clean bootstrap, migration matrix, layered skeleton and credential-free CI.

## M2 - ACTIVE; not live-accepted

Issue #4 hardens the initial read-only implementation before acceptance:

1. Conservative TLS-deny coverage and real provider-policy evidence.
2. Verified account/Region, bounded inventory, explicit partial/error states.
3. Fresh exact prepare, unique expiring batch, changed-policy readback.
4. Adversarial tests, source-backed contract and opt-in LAB probe.

Repository proof and live proof are separate. The controller/registry read is
not a four-target read. Acceptance still needs the corrected reader running
with the existing registered target-role sessions, then fresh prepare/readback.

## M3 - NEXT; not started

Runtime-neutral durable Reject/blocked-Approve decision service, then one
thin native UI adapter and authenticated Reject-only E2E. No live Approve.

## M4 - FUTURE

Selective S3 BPA and restricted-SSH migration only after exact per-control
canary authority. No generic executor or inherited old-repo write authority.

## M5 - FUTURE

Capability parity, reversible cutover and explicit archival decision. Preserve
old evidence. Do not run two equal product development tracks.

## Boundaries

No company/PROD, third live remediation control, automatic uncertain retries,
old-repo cleanup or infrastructure/auth expansion under M2.
