# Private binding and installation review — PR93 continuation

15 October 2026. This supplements the single proposal; no new proposal/Issue.
PR93 stays DRAFT and UNMERGED. No IAM, SSM, S3, GitHub Environment or Site changes
were applied by this continuation. The only external mutations were authorized
repository/PR/Issue updates. agentcore2 source Issue42 is separate and MOCK-only.

## What is complete versus unavailable

- **PRIVATE_CANDIDATE_BINDING=RENDERED**: one exact reserved new bucket name,
  owner-specified account, Singapore, exact proposed role ARNs, immutable repository
  OIDC subject, boundaries and fixed SSM document. Actual values and SHA-256
  manifest are in the owner-private review attachment, never public GitHub.
- **PROVIDER_TARGET_BINDING=NOT_VERIFIED / TARGET=NOT_CREATED**: selecting a name
  does not prove global availability, ownership, emptiness or a provider baseline.
  No existing resource may be adopted if creation reports a collision.
- **INSTALLED_EFFECTIVE_POLICY=NOT_VERIFIED**: proposed roles/boundaries do not
  exist as verified installations. Fresh SCP, resource-policy, principal policy,
  IAM simulation and immutable role-ID checks have not run. The previously
  connected identity is not the approved non-root setup/verification path; do not
  use it or silently assume a role to fill the evidence gap.
- **OFFLINE_NEGATIVE_REVIEW=PASS**: 60 structural/local subset checks and injected
  fake-provider cases. They cover exact actions/resources, other Regions/accounts,
  absent direct controller S3 authority, exact PassRole target/service/document
  version, root refusal, expiry, non-empty target, drift/replay, no-change and
  uncertain-write no-retry. This is NOT AWS IAM Policy Simulator, SCP simulation,
  a real service session, end-to-end trust proof or effective-access certification.

The public runbook script plus local-only renderer produce a fixed embedded
Python3.12 SSM document, no attachments, parameters or target inputs. The current
private binding is RESERVED_NOT_CREATED / NOT_AUTHORIZED, so the rendered
runbook returns BLOCKED before importing an SDK or calling STS/S3. It is safe
review material, not a claim of runnable remediation. No false success/receipt
has been invented. Preparing a later provider-verified, batch-approved binding
changes the rendered runbook digest/version and requires its separate live review.

## Exact installation-only request, still HELD

The requested decision is one **installation-only** package, in the owner-private
exact LAB/Singapore binding and with the attached exact names/digests:

1. Create the two named roles, two customer-managed boundaries, and their exact
   inline policies from the rendered packet. Names: controller
   `awsops-github-lab-canary-controller`, executor `awsops-lab-s3-canary-execution`,
   boundaries `awsops-issue90-controller-boundary` and
   `awsops-issue90-canary-boundary`; inline policies `issue90-controller-v1` and
   `issue90-canary-v1`. Reuse the existing OIDC provider without modification.
   New-role setup needs CreateRole, CreatePolicy, PutRolePermissionsBoundary and
   PutRolePolicy on these new objects only; no modification/adoption of existing
   objects on collision and no new permission assigned to the existing read role.
2. Create one new general-purpose S3 canary with the exact private name,
   Singapore location and the four specified disposable/ownership tags.
   CreateBucket and PutBucketTagging only; require default BucketOwnerEnforced
   and all four BPA flags TRUE on readback. No objects, clients, bucket policy,
   website, versioning, weakening of defaults or replacement target on collision.
   Runtime roles intentionally cannot provision or delete this target.
3. Install only version1 of `AWSOPS-Issue90-S3BpaCanary` with the fixed current
   blocked runbook digest. No StartAutomationExecution, invocation, test dispatch,
   service execution or claim of a successful canary. CreateDocument only; do not
   overwrite an existing same-name document or widen the version allowlist.
4. Create the new `awsops-lab-canary` Environment with main-only branch protection
   and actual required review/no-bypass controls after confirming support.
   Do not create or activate the proposed workflow yet, dispatch OIDC, or add
   static credentials. Existing read-only Environment/provider/role stay unchanged.
5. Authorized **non-root** security operator reads back new policies/boundaries,
   role IDs and private target; verifies SCP/resource-policy/protection limitations
   and runs exact policy simulation if permitted. Unknown/denied evidence stays
   UNKNOWN and blocks further activation. No automatic permission widening.

No existing IAM access for the setup operator is asserted. This package is a
requested authorization, not a new broad IAM policy for dot. Actual non-root
setup/verification access remains an execution prerequisite; approval alone does
not provide credentials or authorize root fallback.

**Excluded:** merge/activation of PR93, live dispatch/remediation, weakening BPA,
#89 fixtures, changes to Config read role/trust, cross-account/Organizations,
new provider/keys, other resources, public exposure, recurring jobs or compute.
Installation approval must not be interpreted as the separate live approval.

## Rollback and spending limits

Proposed maximum experiment allowance **USD10 total**, not a recurring budget or
promise that AWS calls are free. Current work costs no new AWS infrastructure.
No compute/schedule; retain only the two roles/two boundaries/one document/one
empty bucket if installation is approved. Check existing Config recording impact
and request/retention cost privately before provisioning; unknown material cost
blocks it. No automatic re-provisioning or repeated executions.

If setup fails, stop on the first unexpected identity/policy/target/protection.
Keep a receipt of partial objects; do not overwrite other objects or delete data.
Keep the new Environment/workflow disabled and withhold execution. A reviewed
operator can remove only the newly created scoped role permissions/trust and
record that sessions may survive; no executor was started by this package.
Preserve audit evidence. Deletion of roles/document/boundaries or the fresh empty
bucket is not automatically performed under this installation request: record
cleanup candidates, verify no consumers or contents, and obtain the applicable
cleanup authorization. Never purge objects/versions, restore insecure settings,
remove the existing provider or alter #89 to call cleanup complete.

## Reproducibility

`python docs/proposals/defence-lab-execution/check-review.py` runs only local
assertions/fake clients, zero provider calls. The policy evaluator intentionally
implements only the operators in this packet and fails on unknown operators;
it is not a substitute for AWS semantics or installed-effective-policy evidence.
`render-review.py <private-binding.json> <outside-repository-output-directory>`
uses stdlib only, refuses repository output, writes mode0600 files and a private
manifest. It has no AWS client or upload/install command. Do not commit render
outputs or paste private account/resource bindings into public logs.

Runbook compilation/JSON structure, fixed target/no-input contract, blocked
current binding zero-call behavior, 60 offline checks and whitespace: PASS.
A new security-boundary check is justified; no framework or repeated GUI E2E added.

ONE_NEXT_STEP=Owner reviews the private rendered packet and decides whether to
authorize exactly the installation-only package above, retaining the non-root
verification prerequisite and a separate live-execution gate.
