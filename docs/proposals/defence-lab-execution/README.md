# Defence Factory personal-LAB Power User review

15 October 2026. Owning Issue90, existing PR93. Dot is sole native implementer.
Owner direction: https://github.com/amitkarpe/awsops/pull/93#issuecomment-6194680568

## Superseding design

The former S3-only/five-action proposal and its installation request are superseded.
Do not install the old private packet. Source-only acceptance or merge of PR93 does
not authorize IAM installation or live dispatch. The existing
four-action Config read role, OIDC provider, protected Issue89 fixtures and public
access settings remain unchanged. No AWS call, IAM installation or live dispatch
occurred during this revision.

One reusable account-specific role template is proposed for explicitly registered
personal LAB accounts. First rollout is owner-designated personal LAB alias amit,
Singapore only. No office/dev/PROD or automatic additional-account registration.

Identity separation:
1. A distinct GitHub OIDC controller can assume only explicitly registered target
   dispatcher roles. It has no broad service-write permissions.
2. A target-account dispatcher can start one fixed reviewed SSM document version,
   read bounded execution receipts, and pass only its exact same-account service
   execution role to SSM.
3. An AWS-owned service execution role uses AWS-managed PowerUserAccess with one
   deny-category boundary. It is not directly assumable by GitHub. The same template
   supports reviewed S3, security-group and EC2 compliance operations without
   adding service-specific permission grants for every capability.

Exact role names, rendered trusts, target registration, protected resources and
policy/document hashes remain in the private review material. Public templates from
the previous narrow design are retired here to prevent accidental use.

## Guardrails and acknowledged residual risk

The proposed boundary denies identity/account administration, protected targets,
other Regions, known foreign resource ownership, common destructive/public-exposure
operations, audit disablement, delegated arbitrary execution and major spend paths.
Per-batch controls require an immutable scope, exact resource revisions, expiry,
authenticated human Approve Once or Reject, atomic decision consumption, stable
idempotency token, durable receipts, drift checks and independent provider readback.
The current source runbook is unconditionally blocked and contains no provider calls.

A broad AWS policy plus a short deny overlay is NOT a complete security perimeter
or hard cost cap. Ordinary data reads and some resource-creation/spend actions remain
possible. Resource-account condition keys are absent for some APIs; endpoint Region
is not a guarantee about all effects. Protected resources also need indirect dependency
review. Managed-policy versions may change. Fixed trusted code, private effective
permission verification, and review of these residuals are installation prerequisites.
There is no generic model-accessible AWS mutation tool.

AWS documentation currently identifies PowerUserAccess v12, including service-linked
role administration exceptions; the proposed overlay denies those exceptions.
The actual policy version and effective access in the LAB are NOT_VERIFIED.
Reference: https://docs.aws.amazon.com/aws-managed-policy/latest/reference/PowerUserAccess.html
PassRole reference: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html

## Evidence and acceptance limits

- LOCAL_SOURCE_REVIEW=PASS: revised policy/trust model, private-only renderer and
  inert multi-service scope review prepared outside the public publication packet.
- OFFLINE_CHECKS=75_PASS: local policy-subset checks, private-output restrictions,
  fixed trust/dispatcher boundaries, negative cases and intentional residual ALLOW
  examples. Existing synthetic intake/freeze/Reject checks also PASS.
- These checks are NOT AWS IAM simulation, SCP validation, actual role assumption,
  provider ownership, hosted viewer acceptance or a REAL remediation proof.
- Revised detailed source/tests are retained privately; they are not claimed to be
  committed in this sanitized-summary revision. Earlier detailed publication was
  withheld to preserve the public/private boundary; no private material is published.
- CI=NOT_RUN_SUMMARY_ONLY. Prior CI/source evidence is not reused as live authority.
- INSTALLATION=HELD; LIVE_DISPATCH=HELD; NEW_AWS_RESOURCES=0.

## One remaining external gate

First complete exact-account private verification using an approved non-root access
path: fresh identity/role binding, protected target/dependency inventory, actual
managed-policy version, trust, boundary, SCP/resource-policy effects and cost safeguards.
No root fallback, unknown account or assumed authority from the old read-only proof.

Only when that packet is complete, request ONE revised installation-only decision
for the exact new identities, boundaries, protected Environment and blocked document
in the designated personal LAB, within USD10 total experiment spend. No broad policy
activation or REAL canary is approved now. The earlier narrow installation question
cannot authorize this materially different design. No repeated GO is required for
safe source preparation.

Future canary execution requires its own frozen exact-target authority. First target
must be newly disposable and free of genuine data/clients. No public-access changes,
protected fixtures, bulk live remediation, permanent compute, schedule or paid model
calls. Secure defaults may produce NO_CHANGE; never weaken a resource to force a demo.

Rollback: stop new admissions, reconcile in-flight execution, preserve receipts and
verify session expiry; remove only newly installed components under exact authority.
No automatic deletion, unsafe configuration restoration or existing-role/provider
changes. Cost accounting must include in-flight estimates and a safety margin;
budget alerts are not hard caps and API calls are not guaranteed free.

NEXT=Complete private non-root/effective-access verification before requesting the
single revised exact-account installation decision. MOCK, source and REAL evidence
remain separate. The existing companion MOCK GUI is preserved.
