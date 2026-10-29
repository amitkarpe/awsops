# Roadmap #77 — development compute and operating runbook

Owner: [roadmap #77, M5](https://github.com/amitkarpe/awsops/issues/77).
Updated: 2026-10-06. M1–M5 source/runbook work is merged. #83 OIDC identity
is PROVEN at run 37450622218; [#86's latest receipt](https://github.com/amitkarpe/awsops/issues/86) owns live Config acquisition status. This is the canonical #77 technical engineering/resume runbook.
Resource decisions remain owned by #14 and live mutation gates by #62/#70.

## 29 October 2026 cloud handoff

[Manager Issue19](https://github.com/amitkarpe/manager/issues/19) is the current
migration index and transfer/closure authority. This section is the cloud entry
point; older #77 milestone receipts below remain historical. Source baseline is
[PR127](https://github.com/amitkarpe/awsops/pull/127), merged
`0f18adaaff27f14159ad4ef6d9827105691fb743`. Read the latest accepted Manager19
checkpoint and this document's eventual merge before selecting an execution pin.
One repository writer only: release/reconcile Home before admitting a cloud VM.
A queued task, environment creation or source merge does not prove live readiness.

### Copyable source-only first task

> Work in `amitkarpe/awsops` at Manager19's accepted merged revision. Read the
> repository instructions and current context, Manager19 and Issue90; verify
> origin/branch/HEAD and preserve existing work. Reconcile writer release first.
> Inspect the merged explicit application-ledger initializer and prepare its
> smallest exact deployment/recovery proposal with first-install versus lost-data
> proof. Do not start EC2/SSM, create a ledger, launch an app, invoke credentials,
> dispatch a workflow or change Cloudflare/IAM/resources. Reuse recorded source
> checks; validate only a demonstrated change. Return one cohesive PR if needed,
> exact checks, unknowns and the next gate to Manager19. Do not create another writer.

If a repository-scoped proxy cannot read Manager19, obtain its accepted public
handoff text from the owner; do not copy a PAT or silently attach another repository.

### VM setup and source verification

Use a repository-bound Linux workspace. CI uses Python3.12 and Node24; verify
actual VM tools rather than assuming its defaults match. Docker with the Compose
plugin is needed for configuration validation only; Chromium and system libraries
are needed for the synthetic browser check. Dashboard versions come from its
lockfile (currently Playwright1.63.0 and Vite8.2.4), not global installs. Git and
GitHub publication/readback capability are needed. Optional provider code uses
`integration/compliance_agent/requirements.txt` (boto3 1.43.98, MCP1.30.0,
Pydantic2.13.5); do not install or authenticate provider dependencies merely for
a docs change. Existing local CLI versions are not cloud requirements/proof.

For a changed source path that needs CI parity, use the existing entrypoint:

```sh
python3 scripts/cloud_verify.py --bootstrap
```

It performs locked installs/audit, pinned public-fixture fetches, source contracts,
Compose configuration, builds and synthetic browser checks. It does not start the
retained app or call AWS. Allow its reviewed package/CDN/GitHub fixture destinations
in the environment setup; report blocked downloads instead of weakening checks.
Without `--bootstrap`, missing dependencies/fixtures and skipped downloads/audit
remain incomplete parity. Prefer the smallest relevant existing check for edits;
docs-only handoff uses diff check and its automatic CI, no repeated local suite.
Native fixtures, browser binaries and dependency caches are generated inputs,
not durable owner evidence; private ledgers/config must never enter the image.

### Platform capabilities and actual gates

Vendor capabilities checked 29 October; this task did not create/test a cloud
account/environment or entitlement. Limits, VM tools, available connectors and
subscription usage must be verified in the selected session; no unlimited runtime
or credits claim. Source/Issue/PR history is durable; commit changes and retain
public-safe run/check references before a VM is paused/reclaimed.

| Surface | Supported route and limitation |
| --- | --- |
| Codex Cloud | Published repository environment with install/start configuration and network controls. Native AWS OIDC supports CLI/boto3 only after an attached trusted connection with exact issuer/audience/subject and resource permissions. Personal Home skills/auth are not inherited; browser/computer-use support is not promised. |
| Claude Code cloud | Repository VM with configurable setup/network. Inspect actual versions, including Node24 availability. Built-in GitHub tools or REST `gh api` can use its attached-repository proxy; GraphQL `gh issue`/`gh pr` can be refused. Local MCP/auth and repository `enabledPlugins` do not auto-install. Interactive AWS SSO is unsupported. Setup scripts precede environment variables. |
| GitHub Actions | Existing CI is source/synthetic. `awsops-readonly.yml` separately uses the approved main-only Environment and Actions OIDC role for fixed Config reads; do not dispatch it for handoff. Actions trust and its private secrets do not authenticate a coding VM. |
| CLI / supported plugin | Use an explicitly available approved connector or exact CLI identity where authorized; tool presence is not callability/authority. Do not copy Home credentials, restart local MCP, or turn an HTTP bearer network-secret feature into assumed AWS SigV4/OIDC access. |

Official references: [Codex cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments),
[Claude cloud environments](https://code.claude.com/docs/en/cloud-environments),
[GitHub Actions OIDC](https://docs.github.com/en/actions/concepts/security/openid-connect).
No IAM/federation connection is configured by this guide. Long-term provider work
should use the accepted cloud VM and a supported federated identity; if missing,
return the exact trust/connection requirement without changing it. Local SSO cache,
a product subscription and Actions OIDC are distinct identities. Do not copy or
reuse quarantined/exposed credentials. A valid supported scoped replacement is an
operator prerequisite, not something to invent in a cloud bootstrap script.

### Source, guest state and initialization boundary

The [accepted diagnostic](https://github.com/amitkarpe/awsops/issues/90#issuecomment-6344956805)
observed the application file missing, with a traversable owner0700 parent, then
independently verified STOPPED22Oct23:45SGT. It did not prove no historical ledger
was lost. The native DecisionStore, application ledger and authenticated owner
identity are separate. Installed runtime948e is historical guest evidence; PR127's
merged explicit initializer is source-only and was never deployed/executed there.
Full upstream app revision remains unverified. Fresh endpoint verification in the
handoff is UNKNOWN; an unavailable backend or anonymous Access challenge is not login.

See [runtime initialization](../../integration/runtime/README.md#explicit-application-ledger-initialization).
Any future exact setup Goal must pin deployed code/config/binding, establish
first-install provenance or recover lost history, preserve native bytes/rows and
all original claims/backups, keep existing/partial files fail-closed, and verify
schema-only zero rows without inventing a packet, principal or approval. The
approved constructor path is `prepare_native_canary`; normal packet preparation
still comes from authenticated `pause_gate` server context and fresh provider reads.
Only the real owner can log in and Reject a fresh bound packet. Approve/remediation
needs its genuine batch-specific approval; target binding and synthetic fixtures
never grant it. Preserve #89 fixtures, personal-LAB/Region boundaries and USD100
TOTAL incremental authority (no monthly reset or billing-cap claim).

### Recovery, rollback and local-only inputs

Public clone includes code, schemas, pins and sanitized evidence links. It lacks
private account/target mappings, source/config/backup hashes, original claims,
SQLite ledgers, login state and installed journal/backup bytes. Request only the
exact approved private input through a supported secure route; do not export Home
auth/browser state or the private evidence tree. Missing inputs stay BLOCKED.
Neither cloud service can infer guest state from a cloned README or synthetic receipt.

Source rollback is a reviewed revert PR. Guest rollback is a separate exact
operation: use recorded config-before-source ordering and versioned journals with
complete backup readback and original metadata, stop on unknown/partial state and
never replay original migrations. Do not delete ledgers/backups to obtain a clean
start. Host windows still require the reviewed independent Stop/STOPPED finally;
process RuntimeMaxSec does not stop EC2 billing. Terminate only an actual owned
forwarding session/process; RunCommand alone has no interactive session to invent.
Preserve the permanent owner-only protected hostname across windows. No Home
service/tunnel/evidence cleanup is part of source handoff; replacement consumers
and rollback must be proven first.

## Scope: #77 technical runbook, not current #90 worker routing

The cloud workflow and recovery procedures below retain #77's accepted technical
contract. They do not select the implementer for later work. Current #90 routing
is **Manager -> the same existing repository Codex X**, under the
[owner override](https://github.com/amitkarpe/awsops/issues/90#issuecomment-6207039365)
and [current context](../../CONTEXT.md). Preserve that worker and its worktrees;
routine FAST conversation/queue delivery is not a Direct mission or proof of
execution. Active Issue/task scope controls operations, not this historical diagram.

## #77 implemented path and gated design

```text
Amit / ChatGPT / Dot -> saved Codex Cloud environment -> GitHub branch / PR
                    -> GitHub Actions -> source and synthetic evidence

IDENTITY PROVEN (#83); CONFIG ACQUISITION SOURCE ACTIVE / LIVE RECEIPT IN #86:
reviewed GitHub request -> verified OIDC -> narrow AWS role
                        -> bounded AWS execution -> independent provider readback
```

#77 repository engineering is cloud-first and laptop-optional. Home remains
the supported NEW demo/private-browser runtime; it is not a fallback for blocked
cloud work. For #77 cloud acceptance, do not use office/Direct local execution or
retained AWS hosts to make a cloud check pass. This is not a ban on #90's approved
Manager -> existing X source work. No generic AWS tool or deploy command is provided here.

| Path | Execution class | Source of truth and acceptance boundary |
| --- | --- | --- |
| Source edits, offline contracts, lint/build | Cloud-native | [cloud_verify.py](../../scripts/cloud_verify.py); no AWS identity |
| Built config2 browser fixture | Cloud-native / GitHub-native | [browser_smoke.mjs](../../integration/config_dashboard/browser_smoke.mjs); real Chromium with synthetic provider, no owner login |
| PR review, checks and publication | GitHub-native | [CI workflow](../../.github/workflows/ci.yml), exact PR head, run/job and tested merge checkout |
| M3 read-only evidence contract | Cloud-native, synthetic only | [M3 contract/gates](../current/CLOUD_READONLY_M3.md); live acquisition is AWS-auth-required and unverified |
| M4 Config Pack planning/preflight | Cloud-native, synthetic only | [M4 schema](../current/CLOUD_CONFIG_PACK_M4.md); no executor or authenticated approval verifier |
| Config/provider identity, inventory, evaluation freshness | AWS-auth-required | Existing operator-approved identity and exact scope required; historical readback does not prove current state |
| sec2 login, persisted answer/DOM binding and Archive | Home/private-browser-required | [canonical browser harness](PLAYWRIGHT_E2E.md) and [Home runtime](HOME_DEMO_RUNTIME.md); cloud fixture cannot replace it |
| Home lifecycle and Tailscale/Funnel route | Home/operator-required | [Home lifecycle contract](../../scripts/home_demo.py); private state and separate route authority remain necessary |
| Config Pack write and readback | AWS-auth-required, gated | [#70 gate packet](../current/CONFIG_PACK_M4.md); no source PASS enables a write |

Home dependencies that remain: running sec2/config2 and MongoDB state, normal
owner login, private bindings and provider sessions, actual Harness telemetry,
and the approved public route. Keep them operator-owned until a separately
reviewed secure cloud replacement proves equivalent acceptance. Public-source
preparation and synthetic browser checks have already moved to cloud; do not
copy private Home files or sessions to reproduce those checks.

## Verify a clean source revision

Start at the repository root in the saved cloud environment. Read
[AGENTS](../../AGENTS.md), [CONTEXT](../../CONTEXT.md), [SPEC](../../SPEC.md),
the active owner issue and existing PR. Confirm origin is `amitkarpe/awsops`,
preserve local changes and check for another writer before switching branches.
Linux, Python 3.12, Node 24, npm, Git, Docker Compose and Chromium system libraries
are the CI baseline; cloud verification does not start containers/Home services.

```bash
git status --short --branch
git remote -v
git fetch origin
git log -1 --format=%H
npm_config_cache=/tmp/awsops-npm python scripts/cloud_verify.py --bootstrap
```

The wrapper is authoritative for the command sequence: pinned public fixtures,
locked npm install, explicit high/critical audit, Python/native/M3/cockpit tests,
source reconstruction, pack/preflight tests, lint/build and synthetic browser.
The Home-named `check`, `prepare`, `verify` subcommands used inside it validate
prerequisites and reconstruct pinned public source only. They are distinct from
`validate`, service lifecycle and `public-*` operations, which the wrapper skips.

Without `--bootstrap`, installed dependencies/fixtures are required and downloads,
audit and source reconstruction are SKIP: this is a narrower iteration result,
not full CI parity. A dependency/audit/CDN failure stays FAIL; fix a bounded
repository problem in the existing PR or record an environment blocker. Never
suppress the audit, weaken tests, or turn SKIP into PASS.

## Read evidence before accepting

From the current PR branch, inspect its head and checks separately from local
results. `gh pr view --json headRefOid,state,isDraft,statusCheckRollup` is a
read-only lookup. `gh run list --branch BRANCH` locates runs; replace `BRANCH`
with that PR's actual branch. `gh run view RUN_ID --json headSha,status,conclusion,jobs`
reads the selected run; replace `RUN_ID` with the observed numeric ID.

Require the reviewed head to match the current PR and run `headSha`, all required
checks to succeed, and CI checkout logs to identify the tested base/head merge
commit. PR CI artifacts record that merge checkout, which can differ from the PR
head. Local artifacts record local HEAD; a clean tree must also be established
because a recorded SHA alone cannot detect uncommitted edits. A later push needs
new exact-head evidence and review. A merged PR is verified by its merge SHA,
main readback and post-merge CI, not merely a successful merge command response.

| Evidence | Meaning and where to inspect |
| --- | --- |
| Local wrapper log/exit and check summary | Executed source checks; wrapper explicitly skips live/owner paths and external CI acceptance |
| Hosted CI result | Same command on the reported checkout; source/synthetic acceptance only |
| `artifacts/cloud-browser/manifest.json` and PNGs | `git_head`, SYNTHETIC_CONFIG2_ONLY, CLOUD_BROWSER_MOCK_PASS; labeled fixture, no browser auth export |
| `artifacts/cloud-readonly/mock-contract.json` | `checkoutHead`, SYNTHETIC_ONLY, eight cells, zero AWS calls; live/evaluation freshness NOT_VERIFIED |
| `artifacts/config-pack-preflight/mock-preflight.json` | `checkoutHead`, public template digest, synthetic candidate; executionAllowed=false, liveApproval/liveReadiness NOT_VERIFIED |
| Live acceptance | Separately authorized identity, acquisition, freshness and provider readback; none of the artifacts above supplies it |

The [workflow](../../.github/workflows/ci.yml) uploads three artifact groups with
seven-day retention. Upload success proves storage, not that contents were
inspected. M3/M4 hosted downloads were HTTP 403-blocked in Codex Cloud; local
artifacts were inspected separately. Preserve that distinction. Missing, expired,
wrong-SHA, RUNNING/failed or unavailable evidence is not acceptance.

Merged source anchors: [M3 acceptance](https://github.com/amitkarpe/awsops/issues/77#issuecomment-6008712131)
and [M4 acceptance](https://github.com/amitkarpe/awsops/issues/77#issuecomment-6008826658).
M4 merged at `221b984ec726600346dd221895c864c531ac0451` with
[post-merge CI PASS](https://github.com/amitkarpe/awsops/actions/runs/37409778264).
Earlier dated milestone documents preserve what ran then; their historical
browser-download failures do not override later successful runs, and later
success does not retroactively change those failures.

## Resume or recover without duplicate action

Durable engineering state is the owner issue, existing PR, commit and CI run;
local uncommitted work must be preserved separately in the same approved workspace.
No live AWS execution journal or resumable deployment exists in M3/M4. A lost
session cannot be reconstructed from a mock artifact as if it were a live run.

| Situation | Safe next step |
| --- | --- |
| Lost Codex/chat session | Reopen saved cloud environment, inspect status/worktrees and fetch refs; read #77 and the existing PR before resuming. Compare local and remote heads. Preserve others' changes; no reset, force-push, replacement PR or duplicate milestone. |
| Uncertain push/PR/merge response | Read remote branch, PR state/merge SHA and main first. Do not repeat the write based on a timeout alone. Resume the existing PR if still open. |
| Running or missing CI | Find the run for the exact head and await terminal status. Missing evidence stays unknown. Rerun only the inspected repository-only CI; never assume a workflow with AWS actions is safe to retry. |
| Bootstrap/Chromium blocked | Retain failure and inspect exact-head hosted CI separately; use the same approved cloud environment once access returns. No Home/office fallback or access-control bypass. |
| GitHub connector/session expired | Stop publication/readback claims; retain local work, SHA and known run IDs. Owner restores the existing connection. Read back remote state before retrying; do not create/extract replacement credentials. |
| Artifact download 403/expiry | Record upload versus inspection status separately; use accessible logs for only what they prove. If fresh contents are required, run the same safe source job and label its new run/SHA. Never manufacture or relabel an old artifact. |
| Missing/mismatched/stale preflight input | Reject. Reconcile independent expected context, exact source and fresh facts; do not edit an approval or reported fact to force a match. A rebuilt plan needs a matching separately reviewed packet. |
| Any future live request times out | Stop. Preserve existing operation/run identifiers and approved private evidence. Under an authorized read path, reconcile provider state before deciding whether a write occurred. Do not retry, advance aliases, overwrite a divergent pack or delete resources on uncertainty. This repo currently has no live runner to resume. |

Handoffs record owner/PR, base/head/merge SHA as applicable, dirty state, commands,
exit results, run/job/checkout, inspected versus merely uploaded artifacts, remaining
gates and one next goal. Public evidence contains aliases and safe summaries only;
never publish private bindings, raw plan digests, sessions or provider identifiers.

## Operator-owned activation gates

Normal repository work can continue without asking for another `go`. Activation
requires evidence and explicit authority beyond this runbook:

1. **Identity and access restriction verified:** #83 proved the existing exact
   immutable Environment subject and dedicated role. Main-only restriction and
   executor quiescence are verified under #86; preserve them without redesign.
   Independent Environment reviewer protection is absent and is not claimed.
2. **Account-local Config acquisition:** the exact four-action policy is attached
   and independently read back, with bounded IAM simulation evidence. PR #87
   merged activation; run 38098174190 returned PARTIAL on uppercase SUCCESS.
   Owner's continuation authorizes the exact status correction and one fresh
   reviewed merged-main proof. The latest #86 receipt owns the resulting SHA/run
   and acceptance; reconcile failed or uncertain acquisition before further action.
   No aggregator or Config writes are in scope. See the
   [bounded operating contract](../current/CLOUD_READONLY_M3.md#issue-86-account-local-config-operating-contract).
3. **M4 first write:** approve the [#62/#70 seven-item packet](../current/CONFIG_PACK_M4.md)
   for exact target alias/account/Region, pack/version/CREATE operation, six
   controls (no remediation canary), permitted actions, rollback/retention, cost
   and exclusions, updated for the actual OIDC role/workflow and lifecycle tags.
   Review clean source/template bindings, real approval verification, identity,
   recorder and existing service-linked role before execution. Missing role needs
   separate IAM authority; unknown/divergent pack state stops. Stage one alias;
   independent rule/provider readback must precede expansion or product acceptance.

Synthetic approval booleans do not satisfy these gates. No static-key fallback,
IAM broadening, automatic remediation, generic AWS mutation, new public exposure
or protected-host action is implied. Native Reject #11/#13 remains deferred.
The retained `amit` host stays recovery-only; `vagent`/Lightsail remain separately
governed. Historical inventory/cost evidence belongs in the
[resource ledger](../current/AWS_RESOURCES.md), not a claim of fresh readback here.

At this #77 checkpoint, remaining work was #86 gate resolution and
separately scoped trusted acquisition/execution with provider evidence. Current
#90 next work/routing comes from its owner decisions and Manager, not this list. Do not
invent another synthetic milestone, runtime migration or cleanup to claim the
live roadmap complete.
