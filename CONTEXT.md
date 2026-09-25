# Agent Context

Repository: `amitkarpe/awsops`
Status: ACTIVE
Updated: 2026-09-25

## Authority

Roadmap #1 owns migration. G implements, validates and reviews directly.
M2 live reads and M3A/M3B/M3C repository integration are accepted. Issue #11
and draft PR #13 own the remaining isolated normal-auth native Reject canary.
No Codex handoff is required.

Issue #14 owns a parallel read-only operational-hygiene track: the public-safe
AWS resource/cost ledger plus retained-host right-sizing evidence. It authorizes
read-only discovery only; it does not authorize EC2 stop/start/resize or cleanup.

No target-resource mutation, live Approve, IAM/OIDC/network or PROD work.

## Current truth

- M2 live evidence remains `docs/evidence/M2_LAB_READ.json`.
- M3A/M3B supply the private ledger, receipt pipe and pinned resume adapter.
- M3C connects the pinned pause producer to fresh provider-backed preparation
  before native readiness. Only Reject is offered; no executor exists.
- Draft PR #13 owns the isolated browser/runtime acceptance and must protect the
  retained services and normal authentication boundary.
- `docs/current/AWS_RESOURCES.md` is the canonical KISS resource/cost view.
  The current personal-LAB snapshot found 21 live `project=aws-secops` tagged
  resources, no `project=awsops` resources, plus the shared retained runtime.
- Retained host right-sizing evidence says **keep `t3.medium` for now**: CPU is
  light, but the sampled workload would leave only ~0.31 GiB theoretical RAM
  headroom on `t3.small`, with no swap. Root filesystem usage at 92% is the
  more immediate capacity concern. No resize or disk mutation is authorized.
- The vagent 100-bucket demo fleet is represented from accepted repo evidence;
  a fresh live account sweep is still required before cleanup/cost decisions.
- `aws-secops` remains reference/archive evidence material, not the primary product repo.

## Next

1. Finish Issue #14 repository ledger/collector acceptance and live coverage
   gaps without AWS mutation.
2. Continue Issue #11 / PR #13 to the real isolated Reject -> receipt ->
   provider readback -> Archive acceptance.

Do not create another roadmap or mistake code/CI acceptance for live completion.
