# Defence Factory MVP: one personal-LAB execution role

Owner MVP-first override, 16 October 2026. Owning Issue #90, existing PR #93.
This replaces the S3-only proposal AND the later three-role controller/dispatcher
proposal. Those private installation packets are superseded, not apply authority.

## Smallest working architecture

Use the existing GitHub OIDC provider and manual workflow conventions with **ONE
reusable PowerUserAccess-based LAB execution role**, directly assumed through the
reviewed repository/Environment-bound OIDC trust. No new central controller,
dispatcher, cross-account broker, Organizations discovery or per-service grant cycle.
Keep the existing four-action Config read role unchanged; reuse its proven identity
pattern, not its permissions. The new write-capable role is a separately approved
installation, not an expansion silently attached to the read role.

First target is owner-designated personal LAB alias amit, ap-southeast-1 only.
Exact account/role/resource values, trust bindings and rendered hashes stay private.
The existing protected Environment/main-only/manual-dispatch practices are reused.
A fixed short job verifies STS account/role/Region, checks a fresh batch-bound human
Approve Once receipt, runs only the reviewed operation, verifies provider state and
exports a sanitized receipt. Request a 900-second session and use a five-minute job
limit; do not claim these revoke all credentials or bound AWS service sessions.
No static keys, arbitrary model-supplied code/commands or automatic mutation replay.

PowerUserAccess is broad across S3, SG, EC2 and SSM service APIs. The operation
catalog and owner approval control what the product executes. Adding an ordinary
supported service operation should not require another per-service IAM allowlist.
No AdministratorAccess. Retain a compact safety overlay for identity administration,
protected fixtures and disallowed accounts/Region/destruction/public changes; it is
not an enterprise perimeter or a promise of exhaustive API coverage.

## Is a second role necessary?

**Not for the first short S3 canary.** Run its fixed calls directly under the single
OIDC execution role. No SSM service role or iam:PassRole is needed for that path.

AWS does require an assume/service role when a custom SSM aws:executeScript step
calls AWS APIs. If that specific AWS-owned execution path is later needed, reuse an
appropriate approved service role, or propose ONE minimal second role plus PassRole
limited to that exact same-account role and SSM. Do not add a third dispatcher or
pre-build this extension now. PowerUserAccess does not itself grant iam:PassRole.
Reference: https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-document-script-considerations.html

## MVP journey and delivered work

1. Reuse existing Config read evidence and bounded synthetic CSV/JSON import.
2. Reuse existing grouped findings/selection in agentcore2; keep its MOCK badge.
3. Reuse immutable batch and Approve Once/Reject semantics. A browser/imported
   assertion is not a trusted real-operation approval.
4. First REAL operation: one new disposable, empty S3 canary only after exact
   installation and live-operation approvals. A fixed default-encryption check/
   reconciliation is the initial candidate; secure default may yield NO_CHANGE.
   Do not weaken it to manufacture a demo. No protected Issue #89 targets or
   public-access changes. SG and EC2 follow after this slice is demonstrated.
5. Read back provider results, export sanitized evidence and keep Config freshness
   separate. UNKNOWN or ambiguous write acknowledgement requires readback before
   retry; no blind replay or fabricated VERIFIED result. Keep basic rollback and
   cleanup notes for the exact canary, with destructive cleanup separately approved.

Delivered M1–M4 source and MOCK evidence are reused, not rebuilt or repeatedly tested.
The live operation remains unperformed. This design is not a runnable AWS deployment.
The next small source milestone is connecting the existing frozen decision/receipt
seam to a fixed S3-canary adapter with one focused fake-provider check, before its
separately approved live proof. No multi-account orchestration or new framework.

## Essential safety and honest limits

- Personal LAB only; no company, GovTech, office or PROD access, root credentials,
  secret exposure, accidental destructive action or unknown-account onboarding.
- Human Approve Once for the exact fixed batch, target identity verification,
  protected-resource exclusions, basic cost awareness and audit/readback evidence.
- PowerUserAccess includes broad reads, writes and spending paths. Its documented
  service-linked-role exceptions are not blanket authority for this application.
  Keep identity-administration restrictions in the reviewed installation scope.
- Policy versions and actual permissions must be checked for the live installation,
  but enterprise-grade policy simulation is NOT a repository-development gate.
- USD10 total experiment target; price/bound the first operation and stop on unknown
  cost. AWS Budgets alerts are NOT a hard spending cap. APIs are not guaranteed free.
- Optional security hardening, scaling, multi-tenancy and exhaustive edge-case tests
  are deferred. Do not turn these real boundaries into speculative milestone gates.

PowerUserAccess reference:
https://docs.aws.amazon.com/aws-managed-policy/latest/reference/PowerUserAccess.html

## Acceptance and next authority

Source-only policy/design updates can merge under the owner MVP directive when
ordinary repository gates pass. No IAM installation or remediation follows from
merge. Public files are sanitized; detailed private bindings remain outside GitHub.
Earlier 75 offline checks describe the superseded three-role design and are retained
as historical evidence, NOT relabeled as validation of this one-role architecture.
Only focused documentation/boundary consistency checks are required for this change.

IAM_INSTALLATION=HELD
LIVE_DISPATCH=HELD
AWS_POLICY_SIMULATION=NOT_VERIFIED (not required for source-only acceptance)
NEXT=Fixed S3 canary adapter through the existing approval/evidence seam. Present
one exact installation decision and a separate exact canary decision when ready;
no repeated GO for source development.
