# Development compute and operating runbook

Owner: [roadmap #77, M5](https://github.com/amitkarpe/awsops/issues/77).
Updated: 2026-10-06. M1–M4 source preparation is merged; live AWS readiness
remains **NOT_VERIFIED**. This is the canonical engineering/resume runbook.
Resource decisions remain owned by #14 and live mutation gates by #62/#70.

## Implemented path and gated design

```text
Amit / ChatGPT / Dot -> saved Codex Cloud environment -> GitHub branch / PR
                    -> GitHub Actions -> source and synthetic evidence

GATED, NOT IMPLEMENTED AS A LIVE EXECUTION PATH:
reviewed GitHub request -> verified OIDC -> narrow AWS role
                        -> bounded AWS execution -> independent provider readback
```

Normal repository engineering is cloud-first and laptop-optional. Home remains
the supported NEW demo/private-browser runtime; it is not a fallback for blocked
cloud work. Do not use office/Direct local execution or retained AWS hosts to
make a cloud check pass. No generic AWS tool or deploy command is provided here.

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

1. **M3 actual identity/trust:** verify effective OIDC subject format/customization,
   inherited settings and the intended environment/job context, plus protected
   environment reviewers and branch/workflow restrictions. Keep the
   [subject placeholder](../../integration/cloud_readonly/trust.proposed.json)
   non-deployable until resolved. Do not mint tokens or change settings to make
   documentation/synthetic checks pass. Missing provider/role or any trust change
   requires a separate exact IAM/OIDC authorization.
2. **M3 acquisition:** owner verifies existing provider/audience, exact collector
   role/immutable ID, effective permissions and aggregator isolation; privately
   maps four distinct LAB accounts and exact rules in ap-southeast-1. Review the
   bounded acquisition adapter/workflow and private handling before any live run;
   independently establish provenance and evaluation freshness. Full checklist:
   [M3 owner packet](../current/CLOUD_READONLY_M3.md).
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

After M5 documentation review, remaining meaningful work is gate resolution and
separately scoped trusted acquisition/execution with provider evidence. Do not
invent another synthetic milestone, runtime migration or cleanup to claim the
live roadmap complete.
