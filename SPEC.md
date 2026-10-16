# Specification — Defence Factory MVP

## MVP-FIRST DEVELOPMENT POLICY

Owner override, 16 October 2026. Defence Factory is an MVP / advanced prototype,
not an enterprise production platform. **BUILD → DEMONSTRATE → IMPROVE.**

1. Working functionality before enterprise hardening.
2. Deliver the smallest complete end-to-end vertical slice.
3. Fix real defects; defer hypothetical future problems.
4. Reuse existing code, tools, roles and workflows.
5. No unnecessary frameworks, layers or infrastructure.
6. Minimal meaningful tests and evidence only; reuse completed proof.
7. Do not repeatedly request GO for routine development.
8. DOT is the sole implementer and owns implementation, testing and safe source
   merges when repository gates permit. No Direct, Factory, Codex X or other writer.
9. Optional hardening must NOT block MVP milestones.
10. Enterprise security, scalability, multi-tenant complexity and comprehensive
    edge-case coverage are future phases.

### Mandatory safety boundaries

- Personal AWS LAB only; never company, office, GovTech or PROD accounts.
- Human **Approve Once** for each fixed real-remediation batch.
- Preserve protected awsops Issue #89 fixtures.
- No root credentials, secret exposure or accidental destructive actions.
- Live IAM installation and remediation require exact, separate owner authorization.
- Keep MOCK and REAL evidence distinct. Private bindings stay out of public GitHub.

These are real boundaries, not a reason to invent additional approval ceremonies.
This policy supersedes conflicting older workflow preferences, not these boundaries.
Repository-only work and safe source merges need no repeated GO; source acceptance
never authorizes AWS installation, remediation or publication to a new audience.

## Current vertical slice — Issue #90

Backend awsops and existing frontend agentcore2: read/import findings → group and
select resources → human Approve Once → approved LAB operation → provider readback
and exported evidence. Reuse delivered M1–M4 source; do not rebuild it.

- First personal LAB alias: amit; Region ap-southeast-1. Exact identity stays private.
- Existing account-local Config read role/proof is preserved; it does not grant write
  authority. Reuse the OIDC provider and workflow conventions.
- PR #93 proposes ONE reusable PowerUserAccess-based LAB execution role for the MVP.
  No cross-account controller/dispatcher architecture. A second service role is
  considered only when an actual AWS operation technically requires one.
- First live milestone is one new disposable S3 canary, after separate installation
  and exact-operation approval. SG and EC2 operations follow later.
- Fixed reviewed operations only; no arbitrary model-supplied AWS command. Verify
  identity/target, record the approved batch and outcome, read back provider state.
  Unknown write outcome is reconciled before any retry. Never count MOCK as REAL.
- Basic cost awareness: USD10 total experiment target; no claim that Budgets is a
  hard cap. No new infrastructure or paid service is authorized by this source work.
- Current source mode has no live apply authority. IAM installation and live
  remediation remain held until their exact separate owner decisions.

## Preserved completed/deferred work

Issue #86 read-only proof remains accepted. Issue #89 fixtures remain unchanged.
Issue #11 / PR #13 legacy native canary is deferred, not revived by this policy.
Existing domain decisions, receipts and runtime code are reused; no legacy approval,
credential-management or alias list expands Issue #90 authority. Source/history and
architecture documents remain references, not new live authorization.
