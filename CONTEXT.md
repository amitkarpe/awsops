# Agent Context

Repository: `amitkarpe/awsops`
Status: ACTIVE
Updated: 2026-09-24

## Authority

Roadmap #1 owns migration. G implements, validates and reviews directly.
M2 live reads and M3A/M3B repository integration are accepted. Issue #11 owns
M3C trusted pause registration and the isolated native canary; PR #12 records
its current code/review/merge state. No Codex handoff is required.

Amit approved an isolated canary on the same verified personal-LAB host, with
separate state and no changes to existing services. New native login/secret
provisioning is an explicit remaining gate; never copy old browser/auth data.
No target-resource mutation, live Approve, IAM/OIDC/network or PROD work.

## Current truth

- M2 live evidence remains `docs/evidence/M2_LAB_READ.json`.
- M3A/M3B supply the private ledger, receipt pipe and pinned resume adapter.
- M3C connects the pinned pause producer to a fresh provider-backed preparation
  before native readiness. Failed registration/replaced generations cannot
  publish a card. Only Reject is offered; no executor exists.
- Bound post-Reject readback can reopen durable evidence without reconstructing
  a job or replaying its decision. Readback output is not a new ledger event.
- Producer/controller rehearsal uses pinned upstream code, genuine local
  service/ledger logic and explicit provider/native dependency doubles. It is
  not proof of live native authentication, Redis/Mongo or browser behavior.
- Preflight found the retained services active and no isolated canary. No
  canary process/listener/login was created. The retained patched source is
  not the clean upstream pin; it must not be altered or silently reused.
- M3 live acceptance is PENDING; Issue #11 remains open after repository merge.
- `aws-secops` stays reference/archive material; neither repo nor runtime changed.

## Next

Complete the isolated canary's normal authentication/bootstrap boundary under
#11, then real Reject -> durable receipt -> provider readback -> cleanup.
Do not create another roadmap or mistake code/CI acceptance for live completion.
