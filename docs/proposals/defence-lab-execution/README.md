# Issue #90 — one LAB execution-role proposal

**15 October 2026. REVIEW ONLY. No IAM installation, workflow activation, AWS
API call, canary provisioning or remediation is performed by this change.**
Owner requested a concrete proposal, not execution. Exact account/resource
bindings stay owner-private; public aliases and explicit placeholders are used.
Continuation: [private binding and exact installation-only review](BINDING_REVIEW.md)
records rendered-candidate versus provider-verified status and the single decision.
The accompanying [proposal.json](proposal.json) is the complete proposed trust,
permission and boundary packet. It is **not a deployable template**: no installation renderer,
deployment command or live workflow is supplied. The continuation adds an offline
renderer and review-only fixed runbook source; no SDK is invoked during rendering.

## Reconciled evidence and acceptance

| Project | Current main / merged source | Accepted proof | Remaining gate |
|---|---|---|---|
| awsops #90 | `987561b21bd10618e34729ce8cf01bebb847fe5c`, PR91/92 | M1 contract, M2 intake and offline freeze; CI38738502752 | M3 partial; M4 real canary NOT_RUN |
| agentcore2 #39 | `acf464ac46c9d416e45a5c284b6b22af698440db`, PR40/41/43 | v1.10.0-mock, CI38738596130 synthetic browser/download proof; prior private publication receipt | hosted owner-auth E2E ACCESS_BLOCKED; real viewer #37 NOT_RUN |

Both delivered roadmap revisions and all four roadmap merges were freshly read.
Later safe core2 PR43 adds the source-only derived header label at acf464a;
its exact-head CI38749145545 passed, full E2E step skipped. That header patch
has not been published to the private Site in this continuation. Open awsops PR13 and
core2 PR8/38 are unrelated and unchanged. No competing implementation PR was
found. GitHub had closed both roadmaps despite comments saying they remained
open; they were reopened to preserve outstanding acceptance gates. No assumption
is made about what caused the closure. Existing MOCK GUI, Site and fixtures are
unchanged by this proposal. Source/CI/publication are not REAL remediation or
human acceptance. Do not repeat the accepted synthetic journey.

Existing #86 read proof is [run38113762515](https://github.com/amitkarpe/awsops/actions/runs/38113762515).
The earlier connector-expiry blocker is resolved by the later
[#90 checkpoint](https://github.com/amitkarpe/awsops/issues/90#issuecomment-6192833060).
Private identity inspection is historical read-only evidence, not proof of a
new execution role. No AWS connection, including root, is used for this proposal.

## Recommendation: isolated OIDC controller + SSM service execution role

One proposal, **two narrowly separated identities**, neither installed:

1. `awsops-github-lab-canary-controller`: GitHub OIDC, start exactly version 1 of
   one private custom SSM Automation document, read execution receipts, pass only
   the exact service role to SSM. It has **no S3 or Config permissions**.
2. `awsops-lab-s3-canary-execution`: assumed only by SSM in the same approved LAB
   and Region. Five S3 actions on **one exact new disposable bucket**, no object
   contents or object writes. It cannot create targets or change its own rights.

This separation keeps the write credential out of GitHub while SSM retains the
execution when a controller disconnects. No EC2, Lambda, CodeBuild, Step
Functions, schedule, provider/model integration or cross-account role is needed.
It does introduce SSM Automation and narrowly scoped `iam:PassRole` in a **new**
controller role: these are explicit proposed additions, not inherited authority
from the earlier four Config reads. Do not apply them without the later exact
installation approval.

The existing `awsops-github-readonly` role and `awsops-lab-readonly` Environment
remain unchanged. Its four service actions are precisely:
`config:DescribeConfigurationRecorders`, `config:DescribeConfigurationRecorderStatus`,
`config:DescribeConfigRules`, `config:DescribeComplianceByConfigRule`.
They confer no S3, SSM, IAM or cross-account authority. No read-role policy or
trust is reused as a write policy, and no Config evaluation trigger is added.

## Exact proposed trust and GitHub boundary

Reuse the existing account's `token.actions.githubusercontent.com` provider;
do not create a provider or alter repository-wide claim customization. Audience:
`sts.amazonaws.com`. Proposed exact `StringEquals` subject:

```text
repo:amitkarpe@1894622/awsops@1383456061:environment:awsops-lab-canary
```

The immutable owner/repository IDs were re-read from GitHub repository metadata.
The immutable subject format is supported by the accepted #83/#86 source
contract. **The new Environment/token has not been created or minted, so its
actual claim is NOT_LIVE_VERIFIED**. Privately read current repository OIDC
configuration and compare the full generated claim before enabling service
permissions. A legacy/name-only subject, wildcard, alternate repository, tag,
fork or PR claim is not an acceptable fallback.

Proposed workflow: `.github/workflows/awsops-lab-canary.yml`, separate from and
not replacing `.github/workflows/awsops-readonly.yml`. It is a proposed path only.
Manual `workflow_dispatch`, `refs/heads/main` guard, protected new Environment
`awsops-lab-canary`, main-only deployment branch rule, required owner review,
no admin bypass and prevention of self-review where supported. If these controls
cannot be enforced, record the exact limitation and stop installation; do not
silently substitute the read Environment. Same Environment subjects do not
cryptographically bind a workflow filename or branch: protected main review,
restricted Environment usage and source inspection are mandatory controls.

Only `contents: read` and `id-token: write`, no PR/fork/schedule triggers, five
minute timeout, pinned full-SHA actions, no persisted checkout credentials,
concurrency `awsops-issue90-single-canary`, `cancel-in-progress: false`.
Activation defaults to false in reviewed source; no free-form target/role/action
input or browser-uploaded approval. GitHub OIDC requests 900 seconds. IAM role
MaxSessionDuration is proposed as 3600 (the minimum configurable role maximum),
**not an enforceable 900-second role ceiling**. SSM service sessions are managed
by AWS and are not asserted to share the GitHub session's lifetime.

SSM execution-role trust allows only `ssm.amazonaws.com` / `sts:AssumeRole`,
with exact private `aws:SourceAccount` and
`arn:aws:ssm:ap-southeast-1:${LAB_ACCOUNT_ID}:automation-execution/*` SourceArn.
The execution UUID wildcard is necessary before admission; it does not bind a
runbook. Exact runbook/version admission and PassRole restriction are enforced
in the controller permissions. An administrator able to change these policies
or pass this role elsewhere remains outside this workload threat boundary.

## Exact permissions, resources and limitations

The JSON includes each identity policy and its proposed matching customer-managed
permissions boundary, with explicit deny fences for other actions/resources.
Boundaries do not grant permissions and are not SCPs. No managed AWS broad policy.

| Role | Exact IAM action | Exact scope / purpose |
|---|---|---|
| controller | `ssm:StartAutomationExecution` | `arn:aws:ssm:ap-southeast-1:${LAB_ACCOUNT_ID}:automation-definition/AWSOPS-Issue90-S3BpaCanary:1`, also `ssm:DocumentVersion=1`; start reviewed immutable document only |
| controller | `ssm:GetAutomationExecution` | same account/Region `automation-execution/*`; read durable result after reconnect |
| controller | `iam:PassRole` | exact `awsops-lab-s3-canary-execution` ARN, `iam:PassedToService=ssm.amazonaws.com`; no other IAM action |
| executor | `s3:GetBucketLocation` | exact canary bucket ARN; require Singapore |
| executor | `s3:GetBucketTagging` | same bucket; verify owner-approved disposable tags |
| executor | `s3:ListBucket` | same bucket, `s3:max-keys=1`; one unfiltered ListObjectsV2 emptiness check, no pagination |
| executor | `s3:GetBucketPublicAccessBlock` | same bucket; baseline and independent readback |
| executor | `s3:PutBucketPublicAccessBlock` | same bucket; set four flags true in fixed runbook |

S3 Allows require `aws:RequestedRegion=ap-southeast-1`, exact
`s3:ResourceAccount`, TLS. SSM Allows require Singapore; IAM PassRole is a global
control-plane permission and is constrained by exact role and service instead
of a misleading regional IAM endpoint condition. A bucket ARN contains no
account or Region: private owner/Region checks and the policy conditions are
essential. No bucket-prefix wildcard, object ARN or wildcard Allow resource.
`Resource: "*"` occurs only in explicit Deny fences, never in an Allow.

GetAutomationExecution can read **any execution metadata in that one account and
Region**; IAM has no generated execution ID at installation time. This is an
explicit residual read scope, not a claim of runbook-scoped read access. The
controller must fetch only its privately recorded execution ID. No List/Describe
executions permission. Tag-based narrowing is not adopted by pretending a caller
that can retag arbitrary executions provides strong isolation.

No Tags are supplied to StartAutomationExecution; no `ssm:AddTagsToResource` is
needed for this untagged invocation. AWS's machine-readable operation mapping
also lists conditional tagging/PassRole dependencies; this proposal includes
PassRole because the fixed document uses a service role, excludes tagging because
it is not requested, and must be verified at the installation gate. Likewise the
machine-readable ListObjectsV2 union contains ACL/Object Lambda variants; the
[general-purpose bucket API](https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListObjectsV2.html)
requires `s3:ListBucket`. No FetchOwner, ACL, Object Lambda, directory-bucket or
access-point variant is used; no `s3:GetObjectAcl` is added.

**Important limitation:** S3 authorizes PutPublicAccessBlock **and**
DeletePublicAccessBlock with `s3:PutBucketPublicAccessBlock`. IAM cannot express
“only set all four booleans true” using this action's supported condition keys.
The executor could weaken/remove BPA on this one canary if its trusted document
were replaced or execution credential compromised. The fixed versioned document,
SSM-only trust and absent document-update/PassRole rights on the executor reduce
that risk; they do not make it an IAM-enforced tighten-only API. There is no
invented `s3:DeleteBucketPublicAccessBlock` action to deny independently.

## Proposed execution contract (not implemented/activated here)

One private document version 1, hard-coded exact canary bucket, expected owner,
service role and reviewed baseline; **no target, API, code, role or flag inputs**.
The deployment-time private packet binds its rendered SHA-256, source SHA,
controller/role unique IDs, exact new bucket, decision expiry and expected state.
Only a fixed batch-bound decision receipt is accepted; a MOCK approval is inert.

1. Before OIDC: verify merged reviewed source, main/Environment, activation,
   trusted human receipt, single target, expiry and frozen scope digest. Reject
   exits without StartAutomationExecution. Expiry/drift/replay also zero dispatch.
2. After OIDC: private STS checks exact approved LAB account, assumed controller
   role/session and Region, rejects root/user/other role; no credential fallback,
   endpoint override, debug output, token artifact or raw exception log.
3. Persist intent and stable ClientToken before starting. Start **one** exact
   document version with that same token; retain returned execution ID privately.
   Uncertain response is reconciled against the same request/token and provider
   receipt, never a fresh token. If recovery cannot prove the outcome, stop UNKNOWN.
4. SSM owns a bounded script, at most 120 seconds, SDK max attempts 1, no target
   loop: verify expected owner on supported S3 calls, Region, exact disposable
   tags, complete empty listing (`KeyCount=0`, not truncated) and fresh baseline
   digest immediately before the one possible Put. Hold on any mismatch/error.
   ListObjectsV2 alone cannot prove no old versions/multipart writes: the private
   provisioning receipt must attest a newly created never-used unversioned bucket
   with no other writers; these are preconditions, not inferred from an empty page.
5. At most one Put of all four true flags; no retry on uncertain result. Re-read
   exact owner-bound BPA independently and return only controlled aliases/enums.
   A lost write acknowledgement yields UNKNOWN until readback; no automatic replay
   or rollback. A fresh already-all-true bucket yields NO_CHANGE, not remediation.
   Do not weaken new S3 defaults to manufacture a successful fix.
6. Later controller reconciliation reads the recorded AWS execution. OIDC expiry
   or workflow cancellation does not cancel SSM. No new dispatch for reconnect.
   Public receipt: source/review/run references, alias, real write count, provider
   match and `CONFIG_FRESHNESS=NOT_VERIFIED`; no raw account/ARN/bucket/execution
   identifier or private receipt hash. Config convergence is separate and no
   evaluation is forced. No new read of completed #86 proof just for acceptance.

The existing offline `plan.cjs` remains APPROVE_BLOCKED. Implementing and reviewing
this real admission/runbook path is still required; a role proposal is not a
working executor or a durable exactly-once transaction. IAM itself does not
prevent a permitted principal from starting again with a new ClientToken.

## Private verification and installation prerequisites

Status now: approved target binding is supplied by the owner; previous private
read-only inspection is recorded. **Fresh proposed-role STS, new trust token,
permissions boundary, simulation, SCP/effective restrictions, canary identity,
runbook digest and enforcement tests are NOT_VERIFIED / NOT_CREATED.** No root
call or AWS API is made in this preparation. No external read scope is assumed.

A separately authorized non-root IAM/security operator must privately:
- Reconcile exact owner-approved account and Singapore against independent
  configuration; read existing provider and repository OIDC subject settings.
- Bind a newly provisioned empty canary with exclusive ownership, disposable
  tags, creation receipt, no clients/data/writers/version history; prove it differs
  from all #89 fixtures. Exact name remains UNBOUND until that evidence exists.
- Render both policies/boundaries to exact values, reject every placeholder,
  wildcard bucket, unexpected action or broader attached/inline permission;
  compare saved JSON readback, role unique IDs and document version/hash.
- Inspect applicable boundary/SCP/resource policies with authorized access;
  unknown effective restrictions remain UNKNOWN, not PASS. Policy simulation
  must deny other buckets/accounts/Regions, object reads/writes, trust/IAM edits,
  cross-account assumption, other documents/versions and other PassRole targets.
- Verify required GitHub protection controls actually work. If a protection is
  unavailable, report the exact security gap rather than using blanket prior GO.

Public verification can report only statuses and source/run links. The owner's
explicit account number is deliberately absent from this public packet.
Neither target existence nor access to install the new roles is fabricated.

## Negative permissions, rollback, cleanup and cost

No Config writes/evaluation/aggregator, EC2/SG, Organizations, cross-account
AssumeRole, SSM SendCommand/StartSession, document creation/update, IAM policy/trust
mutation, broad ReadOnlyAccess, S3 object read/write/delete, bucket creation/
deletion, bucket policy/ACL mutation, account-level BPA, network/public endpoint,
secrets/KMS access or new key. The canary executor has no iam:PassRole. The only
controller IAM Allow is exact service PassRole. Provisioning/cleanup is deliberately
excluded from runtime identities, not hidden behind wildcards.

If installed later: disable new dispatch and revoke new controller trust under
explicit security authorization; this does not revoke already issued sessions
or terminate SSM. Quiesce/reconcile the exact execution before detaching the
new policies/boundaries. Authorized operator may emergency-stop the exact SSM
execution without adding StopAutomationExecution to this workload. Keep receipts.
Do not remove the existing provider or change the four-action Config role.

Preferred canary recovery is **leave all four protections true** and reconcile.
Restoring an original absent/false BPA state weakens security and requires a
separate exact authorization after drift check; it is never automatic. Runtime
roles cannot delete the bucket. Cleanup by the authorized provisioning owner
requires fresh empty/no-dependency proof and the normal deletion authorization;
never purge object versions or delete a bucket on a name match alone. Until
cleanup is verified, record CANARY_CLEANUP=PENDING, not zero resources.

Now: zero new AWS resources/cost from repository preparation. If approved later:
2 roles + 2 managed boundary policies + 1 custom SSM document + 1 separate canary
bucket + 1 GitHub Environment; no compute/schedule. No recurring compute charge
expected, but API, ordinary Config recording and retention/Actions costs are not
assumed free. Current Automation list price is $0.002/step plus $0.00003/second
for executeScript: one step capped at 120s is about $0.0056 before S3/Config/
Actions/other existing-account charges. Keep the total experiment below USD10;
this estimate is not an enforced spending cap or permission to incur charges.
No new billing-monitor permissions are granted merely to verify a small cost.

## One remaining decision

Review the [installation-only packet](BINDING_REVIEW.md) and its owner-private
rendered artifacts. Exact candidate name/account/role policies and runbook digests
are now bound privately; provider existence/ownership, effective permissions and
non-root setup access remain NOT_VERIFIED. Do not conflate these states. One
specific installation authorization is requested there; live execution is excluded.
PR93 remains draft/unmerged, and no installation may occur before that approval.

## Sources checked 15 October 2026

- [S3 service reference v1.4](https://servicereference.us-east-1.amazonaws.com/v1/s3/s3.json): actions, resource forms and condition keys
- [SSM service reference v1.4](https://servicereference.us-east-1.amazonaws.com/v1/ssm/ssm.json): exact definition/version and execution resources
- [SSM Automation trust](https://docs.aws.amazon.com/systems-manager/latest/userguide/automation-setup-iam.html): service principal and SourceAccount/SourceArn
- [StartAutomationExecution](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_StartAutomationExecution.html): version, ClientToken, optional Tags
- [GetAutomationExecution](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_GetAutomationExecution.html): durable result lookup
- [PutPublicAccessBlock](https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutPublicAccessBlock.html) and [DeletePublicAccessBlock](https://docs.aws.amazon.com/AmazonS3/latest/API/API_DeletePublicAccessBlock.html): shared IAM action, owner guard
- [GitHub OIDC](https://docs.github.com/en/actions/reference/security/oidc) and repository [accepted subject contract](../../current/CLOUD_READONLY_M3.md#subject-verification-evidence)
- [Permission boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html): permission ceiling, not a grant
- [Systems Manager pricing](https://aws.amazon.com/systems-manager/pricing/): per-step and script duration charges
- [Role session settings](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_update-role-settings.html): one-hour minimum configurable maximum; AWS service sessions differ
- [STS identity permission](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html): no added GetCallerIdentity Allow is needed

## Repository validation receipt

JSON parsing, exact controller (3) / executor (5) action-set assertions, matching
boundary Allows and explicit deny fences, literal proposed OIDC subject, disabled/
not-installed markers, whitespace and public private-ID/credential-shape scan:
PASS. No IAM validator, AWS simulation, OIDC token, service invocation or provider
readback was run; those results are NOT_VERIFIED, not PASS. The assertions inspect
proposal structure, not an IAM policy evaluator. No new testing framework or
repeat of the completed MOCK/browser suite. This documentation-only draft uses
`[skip ci]`; CI is NOT_RUN_DOCS_ONLY and is not a merge/installation acceptance.
