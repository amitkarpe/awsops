# Agent Context

Repository: `amitkarpe/awsops`
Status: ACTIVE
Updated: 2026-09-24

## Authority

Roadmap #1 owns migration. G owns direct implementation, validation and review.
M2 live probe #6 and M3A ledger #7 are complete. Issue #9 owns the repository-only
M3B native-runtime bridge, source-pinned rehearsal and rollback plan.
No runtime deployment, live approval/remediation, IAM/OIDC/network/credential
change or modification of the source repository is authorized.

## Current truth

- M1 bootstrap and M2 corrected live read/prepare/readback are accepted.
- M2 evidence: `docs/evidence/M2_LAB_READ.json`. Its temporary files were removed;
  deployed services stayed unchanged. This is not native browser evidence.
- M3A provides the private durable ledger and runtime-neutral decision adapter.
- M3B provides a private Node/Python process bridge, an exact-source native
  resume seam, bounded failure terminalization, and offline apply/rollback.
  Current Issue #9/PR checks record its review/acceptance state.
- The bridge is default-off. It neither authenticates callers nor supplies an
  HTTP/model tool. Native server ownership/claim and trusted pause registration
  are mandatory. Missing registration fails closed.
- M3 live browser acceptance is still PENDING. No new agent, native session,
  service or deployed adapter was created. Real pause registration/auth/readback
  must be connected and tested in an explicitly isolated canary.
- `aws-secops` remains reference/archive material; its runtime is untouched.

## Next

Review the M3B exact-head proof under #9, then establish the explicit isolated
canary boundary in `docs/architecture/M3_NATIVE_RUNTIME.md` before deployment.
Do not treat controller tests, a ledger receipt or a previous SSM probe as
native browser proof, authentication or permission to change old services.

## Restart

Read AGENTS.md, CONTEXT.md, SPEC.md, roadmap #1 and Issue #9; reconcile current
main/PRs. Keep M2 acceptance and M3 repository/live evidence separate.
