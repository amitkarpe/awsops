# Agent Context

Repository: `amitkarpe/awsops`
Status: ACTIVE
Updated: 2026-09-24

## Authority

Roadmap #1 owns migration. G owns implementation, validation and review.
Issue #6 owns M2 live evidence; Issue #7 owns repository-only M3A decisions.
No Codex handoff is required. No live approval, remediation, deployment,
IAM/OIDC/network/credential changes or source-repo modifications are authorized.

## Current truth

- M1 bootstrap is merged.
- M2 is accepted: the corrected exact reader ran on the verified retained LAB
  host using existing SDK sessions. All four aliases passed identity/Region and
  complete inventory checks. One fresh lab-dev freeze had unchanged readback.
- The same runner passed all 52 M2 tests. Probe files were removed and both
  deployed services retained their original process/start identities.
- Evidence: `docs/evidence/M2_LAB_READ.json`; source revision is recorded there.
- M3A adds a private durable decision ledger and an in-process native adapter.
  Reject and synthetic blocked Approve have no execution path. This is tested
  repository code, NOT an authenticated native browser acceptance result.
- M3 overall remains incomplete. Real native integration must authenticate the
  user and bind the exact paused action before calling the adapter. No HTTP,
  model tool, browser session or deployed adapter exists in this package.
- `aws-secops` remains reference/archive material, not archived or modified.

## Next

PR #8 records M3A code/review/merge status. Define and validate the exact
LAB native-runtime integration and deployment boundary before live changes.
Reuse normal platform authentication; do not extract browser credentials,
replace the old runtime, or treat a SQLite receipt as authentication.

## Restart

Read AGENTS.md, CONTEXT.md, SPEC.md and roadmap #1; inspect #6/#7 and current
PR/main truth. Preserve M2 acceptance and keep M3 live proof explicitly pending.
