# M3 read-only cloud contract — repository preparation

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

The only runnable producer, `node scripts/cloud_readonly_mock.mjs`, constructs
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

## Exact owner gate packet — NOT APPROVED / NOT APPLIED

The proposed JSON files are review material, not deployment inputs. Unknown
private bindings in `bindings.example.json` must remain placeholders in public
Git. No suitable provider, role, environment or aggregator was discovered or
assumed to exist. A later authorized owner must resolve all of the following:

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

All mutation, resource details, remediation, Config Pack deployment, retained
EC2/Lightsail/vagent actions, IAM/OIDC provisioning, secrets, Home/office,
Tailscale, DNS/TLS and public-route changes remain excluded. #11/PR #13 deferred.

## Subject verification gate — unresolved

The repository's actual OIDC subject format and customization have **not** been
verified. [GitHub's immutable subject documentation](https://docs.github.com/en/actions/reference/security/oidc#immutable-subject-claims)
describes name-only and immutable owner/repository-ID formats; subject
customization can also change the result. Repository names or creation dates
alone are not proof of the effective subject.

Before replacing the placeholder, an authorized owner must obtain read-only
settings evidence for this repository's effective immutable-subject mode and
subject customization, including any inherited settings and opt-in state, and
verify the exact subject for the intended `awsops-lab-readonly` environment/job
context. Record the evidence source and observation time in the private gate
packet; keep private identities and token material out of Git and public logs.
If settings evidence cannot establish the exact format, leave the placeholder
and stop. Do not mint a token or change settings to resolve this repository task.
Any later verification needing token issuance requires separate authorization.

Review the verified exact subject with the provider, audience and GitHub controls
above before any separately authorized IAM change. Retain `StringEquals`; do not
add wildcard subjects, alternate-format fallbacks or broader trust. Passing the
offline policy test proves only that this proposal preserves the placeholder and
fixed conditions, never that GitHub can assume a role or that live M3 is ready.

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
