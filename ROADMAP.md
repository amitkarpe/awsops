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

## Home cutover / EC2 cost reduction - IN PROGRESS (#56)

Mode: **one execution PR, many milestones; standing owner approval recorded
2026-09-27.**

- M1 runtime preservation — COMPLETE in PR #57 / `14e004d1`.
- M2 real Home bootstrap — prove fresh pinned LibreChat, local MongoDB, config2
  and read-only provider wiring from Amit's Home Ubuntu system.
- M3 Home browser acceptance — normal owner login and canonical
  Status/Explain/no-change Plan with one read-only tool / zero actions.
- M4 public NEW tunnel — one temporary provider-assigned HTTPS tunnel from Home;
  no custom Route53 migration or home-router inbound forwarding.
- M5 cost cutover — after M1-M4 PASS, stop exactly the retained `amit` EC2,
  never terminate/delete it; retain EBS/EIP and verify Home NEW stays independent.
- Keep Issue #11 Reject-canary deferred and outside the Home read-only baseline.
- Protected Lightsail and `vagent` remain DO NOT TOUCH.
- The single execution tracker is `docs/current/HOME_CUTOVER_EXECUTION.md`.

## Operational hygiene - AWS resource ledger - IN PROGRESS (#14)

- Canonical public Markdown ledger: `docs/current/AWS_RESOURCES.md`.
- Canonical account aliases are `amit` and `vagent`; raw account IDs stay private.
- Account-first cost watch uses Cost Explorer actual MTD plus explicit EST / USAGE-BASED / DIRECT-$0 / UNKNOWN labels.
- EC2 / always-on compute has a separate high-visibility table.
- `amit` retained host remains `t3.medium`; root gp3 expanded online 20 -> 30 GiB and ext4 usage dropped 92% -> 60% with retained services active.
- `vagent` live read confirms one running expired-TTL `t3.small` learning host plus 109 S3 buckets total. **Owner decision 2026-09-27: the host is PROTECTED / DO NOT TOUCH.**
- Home-first compute model is documented in `docs/architecture/DEV_COMPUTE_MODEL.md`: ordinary development stays local/GitHub, `amit` keeps the full M3 integration runtime, and `vagent` is reserved for a future lightweight AWS canary after an explicit repurpose gate.
- EC2 Name tags are part of the canonical high-cost/resource ledger view.
- **Legacy Lightsail and the retained `vagent` t3.small are PROTECTED / DO NOT TOUCH.** Read-only inspection is allowed; any stop/start/delete/resize/repurpose/tag/IAM/network change needs new exact authorization.
- No auto-cleanup. Any other deletion/termination/repurpose is a separate exact mutation boundary.

## Demo UX polish - ACCEPTED (#49)

- Compliance Agent Status / Explain / no-change Plan share one KISS Markdown
  matrix across the exact four aliases and two controls.
- PR #54 adds one canonical Playwright acceptance harness by reusing proven
  browser mechanics from deferred PR #13 and frozen aws-secops PR #192.
- Persisted MCP output must equal final/rendered assistant output; format drift
  fails closed to canonical evidence rendering, so extra prose, invented
  identifiers/risk claims, quoted guardrails, and mode mixing are rejected.
- Live NEW sec2 browser acceptance passed 3/3; all three exact test conversations
  were archived, browser auth/storage state were not exported, and the agent
  remained exactly one read-only tool / zero actions.
- Config2 remained READY/non-partial with four aliases, eight checks and two
  controls; NEW/OLD sec/ops/config regressions remained healthy and unchanged.

## M4 - bounded remediation migration - NOT STARTED

Only S3 BPA and restricted SSH on retained demo scope may be considered.
Separate exact-canary authority is required before any live Approve or write.
Every new/retained M4 AWS resource must appear in the resource ledger.

## Old repository freeze / harvest - ACTIVE

- `aws-secops` is frozen for **new product development**.
- Harvest matrix: `docs/architecture/AWS_SECOPS_HARVEST.md`.
- PR #192 is preserved in frozen `aws-secops/main` and remains a high-value browser/E2E reference; do not continue product development there.
- PR #177 is also preserved in frozen `aws-secops/main`; do not port its persistent read-adapter merely for parity.
- Old repository history/evidence remains readable until M5.

## M5 - parity and cutover - NOT STARTED

Parity/deferred list, deployment/runbook and explicit cutover. Close/supersede remaining old active PRs after their useful patterns are harvested. Preserve source history/evidence. Archive `aws-secops` only after explicit M5 cutover acceptance.
