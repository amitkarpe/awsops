# M4 Config Pack offline plan and preflight

Scope: [roadmap #77](https://github.com/amitkarpe/awsops/issues/77), subject to
[product #62](https://github.com/amitkarpe/awsops/issues/62) and
[pack #70](https://github.com/amitkarpe/awsops/issues/70). Based on M3 source-only
acceptance in merged PR #80 (`2beca9cb08083bd6458bce89c72a71c48462552e`).
**Repository preparation only. No executor, live approval, or deployment.**

## One immutable proposed plan

`integration/config_dashboard/conformance-pack/preflight.mjs` extends the existing
pack validator, manifest and two-control registry. It does not duplicate the six
rule definitions, change the live registry, or introduce dependencies. Its strict,
versioned executable schema rejects missing, extra and incorrectly typed fields.

`preparePlan(expected)` accepts independently supplied `{sourceCommit, target}`.
The target has exactly `alias`, `accountId`, `roleName`, `roleId`: one of the four
registered LAB aliases, a 12-digit account, a bounded role name and immutable role
ID. These values are private inputs in any future real integration; all runnable
examples here invent them. Syntax alone does not establish ownership or identity.

The recursively frozen plan binds schema version 1, OFFLINE_ONLY, CREATE,
`config:PutConformancePack`, one target, ap-southeast-1, the fixed pack/version,
exact six controls, source commit and SHA-256 of the actual template, manifest,
live registry and existing seven-item gate packet (`CONFIG_PACK_M4.md`). It also
binds one stage, no update/delete/remediation/execution and owner issue references.
A canonical SHA-256 covers all plan fields. This digest is a consistency binding,
not a signature or owner authorization. Do not publish it: it covers private
bindings. Preparing a plan requires no approval and cannot perform an operation.

## Offline preflight input schema

`preflight(expected, plan, approval, facts, now)` rebuilds the expected plan from
the independently supplied context and current files, then compares every field.
Callers must never derive that context from the submitted plan or evidence.
The caller's source commit is not independently verified by this library; the
synthetic runner obtains its actual checkout SHA from Git. A future trusted
integration must bind clean source, approved revision and acquisition provenance.

Approval fields (all required, no extras):

- `schemaVersion: 1`, `evidenceKind: SYNTHETIC_ONLY`,
  `decision: APPROVE_OFFLINE_REHEARSAL`, exact `planDigest`.
- Integer `issuedAt` and `expiresAt` in epoch milliseconds, at most five minutes
  apart, already issued and not expired relative to the supplied clock.
- `gates`: exactly `target`, `pack`, `controls`, `actions`, `rollbackRetention`,
  `cost`, `exclusions`, each boolean true. These simulate the seven #70 review
  dimensions bound through the gate packet; they do not attest real decisions.

Fact fields (all required, no extras):

- `schemaVersion: 1`, `evidenceKind: SYNTHETIC_ONLY`, exact `planDigest`.
- Integer `observedAt`, after issuance and no more than five minutes old, not future.
- Exact `target` and `region`, `recorderActive: true`, `conformsRoleExists: true`.
- `pack`: exact `name`, normalized `state`, `templateSha256`. ABSENT requires
  null digest and yields CREATE_CANDIDATE; STABLE requires the exact template
  digest and yields NOOP_CANDIDATE. Divergence, unknown or in-progress state
  rejects; there is no update, overwrite or automatic retry path.

These are normalized invented facts, not an AWS response schema. No provider
adapter claims it can obtain deployed template bytes or establish stability.
A future adapter must prove those facts and actual rule readback independently;
uncertain deployed content must stop, never become a no-op acceptance.

Errors expose only `CONFIG_PACK_PREFLIGHT_REJECTED`, never input values. Success
exposes a fixed public projection with OFFLINE_PREFLIGHT_VALID, SYNTHETIC_ONLY,
`executionAllowed: false`, `awsCalls: 0`, and both live approval and readiness
NOT_VERIFIED. Even perfectly consistent fake approvals/facts cannot authorize
execution. Purported LIVE inputs are rejected rather than promoted.

## Operator verification and evidence

Run `python scripts/cloud_verify.py --bootstrap` for the existing complete
cloud/CI contract. `npm run validate:pack` in `integration/config_dashboard`
includes the existing three pack tests and four focused preflight tests for
source/target/operation drift, missing or inconsistent approval, expiry,
prerequisites, partial facts, divergence, create and no-op cases.

`node scripts/config_pack_preflight_mock.mjs` emits only synthetic inputs and
writes `artifacts/config-pack-preflight/mock-preflight.json`: fixed summary,
actual checkout SHA and public template digest. It publishes no target identity,
raw plan, approval, facts or digest of private bindings. The existing contents-read
CI uploads it with seven-day retention. Exact PR SHA/run results belong in the
PR handoff. M3 hosted artifact downloads were HTTP 403-blocked; an upload alone
must not be reported as independent content inspection.

## Unresolved live gates

This slice completes neither live M3 nor the full M4 before-write gate. The actual
OIDC subject/customization, protected environment, narrow existing provider/role,
private target bindings and source/provider provenance remain unverified. The M3
trust placeholder stays non-deployable. Actual lifecycle tags, costs, retention,
per-target effective permissions and the reviewed workflow must be resolved in the
explicit #62/#70 seven-item owner packet before first write. No simulated gate
boolean substitutes for that packet. Missing service-linked role requires a
separate IAM decision; this module never creates one.

No AWS calls, network provider operations, credentials, IAM/OIDC/security settings,
activation, remediation, deletion, infrastructure or cost are introduced. No
workflow gains OIDC permissions or a deployment trigger. Home/office/Direct
fallback and deferred #11/#13 remain excluded. Independent review is required
before merging this source milestone; live execution requires separate authority.
