# MVP live gate

16 October 2026. Earlier S3-only and three-role installation packets are superseded.
Current proposal: one reusable PowerUserAccess-based personal-LAB role, directly
using the existing OIDC provider. No SSM service role is needed for the first short
S3 canary. See [the single review summary](README.md).

Repository work does not need enterprise policy simulation or another GO.
Before actual IAM installation, obtain one separate exact-account/role/trust/policy
owner decision through the private channel using non-root access. Before real
remediation, obtain a separate Approve Once decision for the exact disposable
canary/operation/cost/rollback scope and verify the target identity. Preserve #89.
No root, office/PROD, secrets in public GitHub or accidental destructive changes.

Private bindings are not public evidence. No new role, resource or workflow has
been installed by this proposal. MOCK and REAL proof remain separate.
