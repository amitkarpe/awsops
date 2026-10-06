# M3 read-only cloud contract — repository preparation

## Issue #83 live identity activation

The current Issue #83 owner decision authorizes the personal LAB identity path.
Private verification used the canonical `amit` account alias and fixed Region
`ap-southeast-1`; the account identifier remains private. One existing
`token.actions.githubusercontent.com` provider with the `sts.amazonaws.com`
audience was reused. GitHub reports immutable subject claims enabled with its
default claim set. The private role trust uses `StringEquals` for the exact
environment subject and audience; public docs intentionally omit immutable
owner/repository IDs and AWS identifiers.

The dedicated `awsops-github-readonly` role has no attached or inline AWS
permissions: `GetCallerIdentity` needs no identity-policy grant. It is tagged
for Issue #83 with TTL review date `31-12-26`; this is a review date, not
automatic deletion. No accepted Config aggregator exists in the target
account/Region, so Config read is `BLOCKED_NO_ACCEPTED_AGGREGATOR` and no Config
permission was added.

GitHub Environment `awsops-lab-readonly` is restricted to the Issue #83
implementation branch and `main`. GitHub rejected self-review prevention
without at least one reviewer; the repository currently has no independent
eligible administrator, so no unusable reviewer gate was configured. The
manual workflow uses a verified immutable release commit of
`aws-actions/configure-aws-credentials`, 900-second sessions, and private
environment secrets `AWS_ROLE_ARN` and `AWS_EXPECTED_ACCOUNT_ID`. It prints only
sanitized pass/fail markers. Identity-only run
[37450622218](https://github.com/amitkarpe/awsops/actions/runs/37450622218)
passed at merged PR #84 main `a12f7f3d004eeed9acb2a6a0e123a7f5e3894983`.
Issue #83 is complete; this proof does not include Config reads.

The identity proof above is historical accepted evidence. Issue #86 replaces the
workflow's source consumer with the disabled, main-only contract below; do not
repeat the identity-only run. The obsolete branch remains in the Environment
because its authorized removal returned GitHub 403; source guards do not prove
that the live Environment is main-only.

## Issue #86 account-local Config operating contract

Owner: [#86](https://github.com/amitkarpe/awsops/issues/86), parent #77;
[#85](https://github.com/amitkarpe/awsops/issues/85) is policy decision input.
Source/offline acceptance is separate from **Config NOT_RUN/PENDING**.
This capability reads only the existing `amit` account in `ap-southeast-1`.
It does not populate the four-alias dashboard, prove evaluation freshness,
remediate, create Config resources or use an aggregator.

### Activation gates and policy

The existing manual workflow has a job-level `main`/`workflow_dispatch` guard,
five-minute timeout and the preserved pinned OIDC action with a 900-second
session. `CONFIG_ACQUISITION_ENABLED: 'false'` is committed source, not a dispatch
input or configurable variable. While false it skips role assumption and the
reader emits BLOCKED / NOT_ACQUIRED with null counts, then exits nonzero.
No workflow is dispatched during repository implementation.

Before any future activation:

1. Authorized repository administrator removes only obsolete deployment branch
   rule `62118086` (`g/issue-83-github-oidc-readonly`), preserving main rule
   `62118088`, then reads back only main/branch. The current integration received
   HTTP 403 on deletion; GET still showed both rules. No bypass or reviewer change.
2. Independent source review accepts the existing workflow/reader. Operator
   privately verifies the approved LAB account, exact existing role identity,
   effective permissions, permissions boundary and SCP limitations. Source
   tests do not establish these live facts; they remain UNKNOWN here.
3. Explicit owner approval precedes attaching the individually removable
   [account-local proposal](../../integration/cloud_readonly/account-local.proposed.json)
   and private effective-access readback. Do not attach it now. The account
   placeholder makes the public proposal non-deployable as supplied.
4. Explicit authorization for one Config-read run precedes a reviewed activation
   change of the literal source gate and one manual main dispatch. Record exact
   reviewed SHA/run; no automatic reruns, schedule or repeat identity proof.

Static policy readiness: `IAM_POLICY_READY=YES`, `EXACT_ACTIONS=4`,
`OWNER_APPROVAL_REQUIRED=YES`. This describes review material, not live access.
Recorder actions `DescribeConfigurationRecorders` and
`DescribeConfigurationRecorderStatus` use the approved account's Singapore
`configuration-recorder/*/*` ARN family. `DescribeConfigRules` and
`DescribeComplianceByConfigRule` require Resource `*` because they do not support
resource-level IAM; both statements fix `aws:RequestedRegion=ap-southeast-1`.
No extra STS Allow, broad ReadOnlyAccess, Config wildcard or trust change.
The [AWS service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_config.html)
and its public machine-readable Config reference were checked for all four
same-named read actions and resource support. The older aggregate proposal below
remains separate and is not attached or silently combined with this policy.

### Bounded acquisition and public output

`scripts/config_posture.py` uses one STS identity read before Config, checking
independently supplied private account and exact role/session. It executes only
the four fixed operations through AWS CLI with captured stdout/stderr, fixed
Region, no profiles, endpoint override, CLI autopagination or retries. Only the
OIDC action's temporary session credentials reach the subprocess; credential
files and instance metadata are disabled. It makes two default recorder reads,
at most five pages per rule/compliance list, at most 500 rows per list and 12
Config calls total. A 120-second deadline includes STS and Config; each process
has at most 15 seconds. Failure stops the read; no raw response artifact is saved.

Default recorder APIs cover **customer-managed recorders only**. A complete
empty recorder response means absence in that scope, never absence of all
service-linked recorders. `RECORDER_SCOPE` describes the returned recording
strategy: ALL_SUPPORTED_RESOURCE_TYPES, INCLUSION_BY_RESOURCE_TYPES,
EXCLUSION_BY_RESOURCE_TYPES, NOT_APPLICABLE (confirmed scoped absence), or
UNKNOWN. It does not certify all resource types or global-resource coverage.
Private recorder names and exact rule-name sets must reconcile; rules must be
ACTIVE. Remaining/repeated tokens or row/page caps yield INCOMPLETE_PAGINATION.
Inventory changes between reads can yield INCONSISTENT; there is no atomic
snapshot or retry to hide that uncertainty.

The simple public summary contains only fixed fields/enums, nullable counts,
validated public `SOURCE_SHA` and `RUN_ID` (otherwise NOT_VERIFIED):

| Field | Meaning |
| --- | --- |
| OIDC_IDENTITY / REGION | PASS only after actual identity and fixed-Region checks; disabled is NOT_ACQUIRED, mismatch FAIL |
| CONFIG_ACQUISITION | PASS, PARTIAL or BLOCKED; PASS means complete bounded acquisition, never product READY or account compliance |
| REASON | COMPLETE, NOT_ACQUIRED, ACCESS_DENIED, INCOMPLETE_PAGINATION, INCONSISTENT, UNKNOWN, IDENTITY_MISMATCH or REGION_MISMATCH |
| RECORDER_PRESENT / RECORDING | YES, NO or UNKNOWN within the customer-managed recorder scope |
| RULE_INVENTORY_COMPLETE | YES only after complete private inventory/compliance reconciliation; otherwise NO |
| TOTAL_RULES / COMPLIANT_RULES / NONCOMPLIANT_RULES / INSUFFICIENT_DATA_RULES / NOT_APPLICABLE_RULES | Counts of rules, not resources; null until complete, zero only for a complete observed empty category |
| EVALUATION_FRESHNESS | Always NOT_VERIFIED; collection success is not evaluation freshness |
| STATIC_KEYS | NONE in this fixed OIDC workflow; no static-key fallback |

A returned recorder with unknown strategy or unsuccessful last recorder status
produces PARTIAL even if rule counts are complete. Errors never imply absence,
zero counts or READY. Previously verified recorder fields may survive a later
rule-list failure, with overall PARTIAL/BLOCKED and null rule counts. The script
exits nonzero unless acquisition PASS. Credential-action failures can stop the
job before the reader; missing summary means NOT_ACQUIRED, never successful
Config acquisition. Public logs must contain no raw responses, names, account
IDs, ARNs, tokens or exception bodies. Offline injected fixtures exercise these
boundaries but supply no AWS provenance or live readiness.

### Lifecycle, failure and resource accounting

For the future single authorized run, retain the sanitized source/run-bound
summary and inspect exact-head status. Cancel on unexpected behavior; do not
rerun on a timeout or change policy to make a denial pass. Once the run is
accepted, update #86/#77 from NOT_RUN/PENDING to PROVEN only for the bounded
Config acquisition; evaluation freshness remains NOT_VERIFIED. Disable the
source gate again through review before any further acquisition; future runs
require their own authorization.

No role/provider/aggregator/recorder/rule/schedule/static key or secret is created
by this source change. No AWS mutation or live read is performed here. New
recurring infrastructure cost expected: $0; this is not a promise of free
API/Actions/ancillary usage. Do not enable Config or trigger evaluations.
Stopping dispatch or cancelling a job does not revoke issued credentials;
900-second sessions expire naturally. Any later service policy is separately
removable by an authorized operator. No Config resource rollback/deletion is
needed for reads, and trust/provider removal is outside this contract.

## Historical M3 aggregate source preparation

Owning scope: [#77 owner instruction](https://github.com/amitkarpe/awsops/issues/77#issuecomment-5974933354).
Base: `b5b21e15b5d0202700fa66ebd9d01096c573c6c7` (merged PR #79).
Origin is `https://github.com/amitkarpe/awsops.git`; main matched that base.
Separate clean worktree/branch `dot/77-m3-readonly-contract` preserves prior work.
No AWS calls, credentials, IAM/OIDC changes, Home execution or deployments.

## Implemented boundary

`integration/cloud_readonly/contract.mjs` reuses the dashboard control registry:
exactly lab-dev, lab-poc, lab-qa, lab-sec in ap-southeast-1, with the existing
S3 public-access and restricted-SSH controls. It validates distinct private
account bindings, exact role name/session/immutable role ID, exact raw rule
names per alias and STS-shaped identity. Placeholders intentionally fail.

`requestPlan` produces eight data-only Config summary requests, each with exact
account, Region and rule filters, limit 2, and one exact aggregator name.
No client or executor exists. The validator requires eight distinct matching
responses with one row each, no pagination, capped count, unknown state, extra
field, error or missing cell. Collection time must be within five minutes with
no future tolerance. The future acquisition adapter must strip SDK transport
metadata only, preserve tokens/errors for rejection, and authenticate provenance.
Changing a private binding requires owner review; syntactic validation does not
establish that an arbitrary supplied account belongs to LAB.

The aggregate contract’s only runnable producer, `node scripts/cloud_readonly_mock.mjs`, constructs
invented in-memory evidence. It publishes `artifacts/cloud-readonly/mock-contract.json`
with fixed labels, registry scope, cell count, actual checkout SHA and
`SYNTHETIC_ONLY`. It publishes no raw accounts, ARNs, findings, rule names,
counts, request IDs, private timestamps or hashes of private identifiers.
Validation does not verify AWS provenance, aggregator source health, or evaluation
freshness: `liveReadiness` and `evaluationFreshness` remain `NOT_VERIFIED`.
A recent collection timestamp is not a recent Config evaluation.

Existing provider behavior stays unchanged. Reused: registry and aggregate
summary API shape. New strict offline contract: identity and complete matrix.
Excluded: dashboard resource detail API, live runner and generic AWS tool.
Five focused Node tests cover these previously untested safety boundaries;
the canonical cloud verification runs them and produces the fixed artifact.
CI retains contents-read permissions only, plus a seven-day synthetic artifact.

## Historical owner gate packet at PR #80 — superseded by Issue #83

The proposed JSON files remain review material, not deployment inputs. Unknown
private bindings in `bindings.example.json` remain placeholders in public Git.
The following packet records the state before Issue #83 owner authorization;
its provider/role/environment stop gates are superseded by the live activation
section above. The Config aggregator and Config-read limitations remain active:

| Gate | Required owner decision/evidence |
| --- | --- |
| Identity | Existing collector account, exact read-role ARN/name and immutable role ID; independent mapping of the four distinct LAB accounts and eight exact raw rule names. No alias inferred from account ordering. |
| Provider | Existing `https://token.actions.githubusercontent.com` OIDC provider in that collector account, audience `sts.amazonaws.com`; reuse only after owner verifies its configuration. Missing provider/role is a new explicit IAM gate. |
| Trust | `trust.proposed.json`: only `sts:AssumeRoleWithWebIdentity`, exact provider ARN and `StringEquals` audience/sub. Subject is deliberately `<UNVERIFIED_SUBJECT_DO_NOT_DEPLOY>`; it is not a GitHub subject and must not be deployed. Resolve the actual-format verification gate below before proposing an exact value. |
| GitHub controls | Proposed environment `awsops-lab-readonly` requires owner reviewers, prevention of self-review and deployment restricted to protected `main`. Environment subject does **not** bind a branch/workflow; owner must verify these controls and prevent any unreviewed workflow obtaining that environment token. No PR/fork or scheduled live execution. |
| Permission | `permissions.proposed.json`: only `config:DescribeAggregateComplianceByConfigRules`, exact existing aggregator ARN (ID, not name) in ap-southeast-1, `aws:RequestedRegion` fixed. No additional policies, broad permission sets or cross-role assume path. Owner reviews effective permissions, boundary and SCPs. |
| Aggregator scope | IAM scopes this action to the aggregator, **not** the four source accounts/rules. Request filters are application checks, not IAM constraints. Owner must prove the aggregator contains only authorized LAB source scope or stop for a different isolation design; do not approve broader organizational access silently. Creating/changing an aggregator is outside this packet. |
| Execution | Later separately reviewed adapter/workflow, one manually approved run, pinned reviewed commit/actions, job timeout 5 minutes, STS duration 900 seconds, no SDK retries/pagination; one GetCallerIdentity then eight planned Config calls maximum, abort on first mismatch. Validate identity before Config; fixed regional endpoints, no profile/static-key fallback or endpoint override. |
| Private handling | Owner-approved private delivery of bindings and in-memory responses only; no secret/account mapping in public artifacts, GitHub variables printed to logs, shell trace, AWS debug or raw exception output. No existing private binding inspected in this pass. |
| Acceptance | Trusted acquisition, exact identity/Region/matrix and sanitized public evidence tied to reviewed SHA/run; owner separately accepts source/evaluation freshness before any product READY claim. Offline mock output cannot satisfy this gate. |
| Cost/rollback | No new compute, Config rules, recorders or recurring schedule. Owner verifies existing Config pricing/billing and accepts one bounded read run plus Actions minutes. On failure stop, cancel run and let 15-minute session expire; owner can revoke trust if needed under separate authority. No live resource rollback/mutation is needed for reads. |

No `sts:GetCallerIdentity` Allow is added: [AWS documents it requires no permission](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html).
The [AWS Config authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_config.html)
maps the proposed operation to the single read action and required
ConfigurationAggregator resource. The [API request/response contract](https://docs.aws.amazon.com/config/latest/APIReference/API_DescribeAggregateComplianceByConfigRules.html)
supports account/Region/rule filters and pagination; no evaluation timestamp is
returned. [GitHub's AWS OIDC guidance](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
describes audience, exact subject and environment protection requirements.
The machine-readable service-reference endpoint was proxy-blocked (403);
policy scope was checked against the official HTML authorization table instead.
No AWS SDK source exists in this slice, so policy design is operation-based.

All Config mutation, resource details, remediation, Config Pack deployment,
retained EC2/Lightsail/vagent actions, IAM expansion, secrets publication,
Home/office, Tailscale, DNS/TLS and public-route changes remain excluded.
#11/PR #13 deferred.

## Subject verification evidence

Read-only GitHub repository settings show the default claim set with immutable
owner/repository identities enabled. The exact environment subject format is
therefore `repo:<owner>@<owner-id>/<repo>@<repo-id>:environment:awsops-lab-readonly`;
the concrete IDs and trust document remain private. The deployed role uses exact
`StringEquals` conditions for that subject and `sts.amazonaws.com`; no wildcard
or alternate subject is accepted. The accepted identity-only run above proved that the live claim matched the
private trust at its recorded SHA; later source tests do not refresh this proof.

## Executed evidence

Cloud execution on 2026-10-04 used Python 3.12.14, Node 24.19.0, npm 11.9.0
and Docker Compose 2.40.3. No additional dependency was introduced. Bootstrap
requires public GitHub source/npm access and Playwright CDN access; npm cache
was directed to writable `/tmp/awsops-m3-npm` (default home cache is unwritable).
Inspected fixture fetch and Home-named source prepare: both fetch pinned public
source only and require no Home execution. Docker daemon is not needed for config.

Executed `npm_config_cache=/tmp/awsops-m3-npm python scripts/cloud_verify.py --bootstrap`:
**FAIL, exit 1, exactly two browser-related failures**, about 34 seconds of
measured child-command time. Dependency installation took 3.7s, fixtures 0.6s,
source preparation 8.3s. No environment repair or access-control bypass attempted.

| Command (dashboard commands run in integration/config_dashboard) | Cloud result |
| --- | --- |
| `python scripts/fetch_native_fixture.py` | PASS |
| `npm ci --no-audit` | PASS |
| `npm audit --audit-level=high` | PASS, zero vulnerabilities |
| `node node_modules/playwright/cli.js install --only-shell chromium` | FAIL: pinned Chromium CDN HTTP 403, Domain forbidden |
| `python -m unittest discover -s tests -p 'test_*.py'` | PASS, 161 tests |
| `node --test tests/cloud_readonly.test.mjs` | PASS, 5 boundary tests |
| `node scripts/cloud_readonly_mock.mjs` | PASS, eight synthetic cells, no AWS |
| `node --test tests/demo_cockpit.test.cjs` | PASS, 2 tests |
| `python scripts/home_demo.py check` | PASS |
| `docker compose -f integration/runtime/home/docker-compose.yaml config -q` | PASS |
| `python scripts/home_demo.py prepare <temporary-directory>` then `verify <same-directory>` | PASS, pinned public source only |
| `npm run lint` | PASS |
| `npm run validate:pack` | PASS, 3 tests |
| `npm run build` then `npm run prepare:runtime` | PASS |
| `npm run test:browser` | FAIL: executable unavailable after blocked install |
| `git diff --check` | PASS |

Skipped by design: Home/authenticated browser acceptance, Tailscale/Funnel,
AWS readback/deployment/remediation. Cloud-safe: offline contracts, public-source
bootstrap, build and synthetic artifacts. GitHub-hosted browser result is checked
separately for this PR; Codex's failed browser check is never relabeled PASS.
Live AWS identity, private binding ownership and provider freshness remain owner
gates. Final PR head/run evidence is maintained in the PR body to avoid a
self-referential commit hash in this file.
