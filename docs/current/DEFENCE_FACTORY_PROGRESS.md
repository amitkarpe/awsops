# Defence Factory MVP progress

16 October 2026. Issue90; DOT sole native implementer.

Completed source: PR91/92 shared contract, bounded synthetic intake, candidate
catalog, frozen approval scope and non-executing receipt seam. Companion agentcore2
PR40/41 grouped MOCK journey and PR43 version label are reused. No rebuild or
repeated E2E. Real viewer and hosted label proof remain separate from source.

Current PR93 installs the MVP-first DEVELOPMENT POLICY in AGENTS/SPEC and simplifies
the DESIGN to one reusable PowerUserAccess-based LAB role using existing OIDC.
This does not install AWS IAM. Optional enterprise hardening is deferred. Existing
Config read role and #89 protected fixtures are unchanged.

The prior 75 local tests apply to the superseded three-role design, retained as
historical evidence only. Current documentation consistency checks establish the
new policy and source scope; no live policy simulation or AWS result is claimed.

Next: fixed S3-canary adapter through the existing batch decision/evidence seam.
LIVE blockers: exact separate IAM-installation authorization/non-root target access,
then exact disposable-canary Approve Once. No extra GO for repository implementation.
Cost target USD10 total; budgets alert, not cap. No AWS calls or resources in this
source-policy update. MOCK stays MOCK.
