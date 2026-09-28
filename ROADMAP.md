# Roadmap

Owning roadmap: Issue #1. G owns implementation and verification.

## M1 - clean migration bootstrap - COMPLETE

Layered source layout, current-only docs, selective migration and CI.

## M2 - trustworthy read/prepare/readback - ACCEPTED

The corrected reader passed four verified LAB aliases and one fresh exact
preparation/readback through the isolated SSM probe. Evidence is in
`docs/evidence/M2_LAB_READ.json`. Temporary files were removed; services unchanged.

## M3 - native Reject-only decision - REPOSITORY COMPLETE / LIVE ACCEPTANCE DEFERRED

- M3A (#7 / #8): private durable ledger and runtime-neutral decision adapter.
- M3B (#9 / #10): private receipt pipe, pinned resume seam and offline rollback.
- M3C (#11 / #12): trusted pause producer, fresh provider registration before
  readiness, and bound post-Reject readback. Repository code is accepted.
- Draft PR #13 owns the isolated real normal-auth browser acceptance.

Repository contracts remain preserved. Real authenticated native Reject, durable
receipt, zero dispatch, unchanged provider readback and Archive cleanup are deferred.
Do not reactivate Issue #11 / PR #13 until Amit explicitly reprioritizes M3.

## Home cutover / EC2 cost reduction - COMPLETE (#56)

Mode: **one execution PR, many milestones; standing owner approval recorded
2026-09-27.**

- M1 runtime preservation — COMPLETE in PR #57 / `14e004d1`.
- M2 real Home bootstrap — COMPLETE.
- M3 Home browser acceptance — COMPLETE with canonical Status/Explain/no-change
  Plan, one read-only tool and zero actions.
- M4 public NEW tunnel — COMPLETE with one provider-assigned HTTPS tunnel and
  no custom Route53 migration or home-router inbound forwarding.
- M5 cost cutover — COMPLETE: the exact retained `amit` EC2 is stopped, never
  terminated; EBS/EIP remain retained and Home NEW stayed healthy.
- Keep Issue #11 Reject-canary deferred and outside the Home read-only baseline.
- Lightsail remains DO NOT TOUCH. `vagent` has a newer owner exception: **STOP only** is authorized and tracked separately in `aws-platform` #107; all destructive/configuration changes remain prohibited.
- The single execution tracker is `docs/current/HOME_CUTOVER_EXECUTION.md`.


## Home Demo v1 productization - COMPLETE (#60)

- One canonical `home_demo.py validate` command for the supported Home runtime.
- Exact config2 four-alias x two-control and sec2 one-tool/zero-action contract.
- Existing Status / Explain / no-change Plan browser harness remains canonical.
- One KISS start -> status -> validate -> stop lifecycle.
- Repository/current-state reconciliation complete; no AWS mutation or new infrastructure.
- Validation is exact-head and latest-attempt bound: stale or superseded browser evidence fails closed.

## Operational hygiene - AWS resource ledger - IN PROGRESS (#14)

- Canonical public Markdown ledger: `docs/current/AWS_RESOURCES.md`.
- Canonical account aliases are `amit` and `vagent`; raw account IDs stay private.
- Account-first cost watch uses Cost Explorer actual MTD plus explicit EST / USAGE-BASED / DIRECT-$0 / UNKNOWN labels.
- EC2 / always-on compute has a separate high-visibility table.
- `amit` retained host is stopped/recovery-only; its encrypted 30 GiB gp3 volume and Elastic IP remain retained.
- `vagent` live read confirms one running expired-TTL `t3.small` learning host plus 109 S3 buckets total. **Owner decision 2026-09-27: the host is PROTECTED / DO NOT TOUCH.**
- Home-first compute is active: ordinary development and the NEW read-only demo stay on Home/GitHub; the stopped `amit` host is recovery-only and `vagent` remains separately governed.
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

## M4 - bounded remediation migration - NOT STARTED / UNAUTHORIZED

Do not begin M4 merely to bypass deferred M3. Any future S3 BPA or restricted
SSH mutation requires a new exact authority and accepted prerequisite decision.
Every new/retained M4 AWS resource must appear in the resource ledger.

## Old repository freeze / harvest - ACTIVE

- `aws-secops` is frozen for **new product development**.
- Harvest matrix: `docs/architecture/AWS_SECOPS_HARVEST.md`.
- PR #192 is preserved in frozen `aws-secops/main` and remains a high-value browser/E2E reference; do not continue product development there.
- PR #177 is also preserved in frozen `aws-secops/main`; do not port its persistent read-adapter merely for parity.
- Old repository history/evidence remains readable until M5.

## M5 - parity and cutover - DEFERRED / DOWNSTREAM

Parity/deferred list, deployment/runbook and explicit cutover. Close/supersede remaining old active PRs after their useful patterns are harvested. Preserve source history/evidence. Archive `aws-secops` only after explicit M5 cutover acceptance.
