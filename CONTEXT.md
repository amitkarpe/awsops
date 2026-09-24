# Agent Context

Repository: `amitkarpe/awsops`
Status: ACTIVE
Updated: 2026-09-24

## Authority

Issue #1 owns migration. G owns implementation, validation and review; X is not
required for this work. Issue #4 owns M2 evidence/prepare acceptance hardening.
Repository work and verified personal-LAB reads are allowed. No deployment,
AWS mutation, IAM/OIDC/network/credential changes or source-repo changes.

## Current truth

- M1 bootstrap is merged.
- M2 implementation is present; acceptance hardening corrects policy coverage,
  partial inventory reporting, provider-policy digests and fresh preparation.
- M2 live four-alias read/prepare/readback acceptance is still PENDING.
- G verified the personal controller and registry with the AWS app. This does
  not verify target-role sessions or run the new reader in those accounts.
- The read-only probe requires an operator-owned private configuration and an
  existing runner with the registered read-role sessions. No credentials are
  exported between tools to manufacture that access.
- M3 is next, not started or accepted. No native UI/decision/executor is exposed.
- `aws-secops` remains reference/archive material; it has not been archived,
  changed or deployed by this work.

## Next

Review the exact-head proof on Issue #4, then run the corrected read-only probe
through an authorized target-scoped LAB runner. Keep M2 open until it passes.
Do not substitute mocked tests, a root-controller read or old-repo evidence.

## Restart

Read AGENTS.md, CONTEXT.md, SPEC.md, Issue #1 and Issue #4. Reconcile current
main/PRs; continue G-owned M2 acceptance before M3.
