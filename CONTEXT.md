# Agent Context

Repository: `amitkarpe/awsops`
Status: ACTIVE
Updated: 2026-09-25

## Authority

Roadmap #1 owns migration. G implements, validates and reviews directly.
M2 live reads and M3A/M3B/M3C repository integration are accepted. Issue #11
and draft PR #13 own the remaining isolated normal-auth native Reject canary.
No Codex handoff is required.

Issue #14 owns operational hygiene: the public-safe AWS resource/cost ledger,
account-level cost visibility and retained-host capacity evidence. Amit explicitly
authorized one bounded LAB mutation: grow the `amit` retained host root gp3 volume
from 20 to 30 GiB and extend its existing ext4 root filesystem online. That
change completed successfully. Instance type remains `t3.medium`; cleanup remains
unauthorized.

No target-resource mutation, live Approve, IAM/OIDC/network or PROD work.

## Current truth

- M2 live evidence remains `docs/evidence/M2_LAB_READ.json`.
- M3A/M3B supply the private ledger, receipt pipe and pinned resume adapter.
- M3C connects the pinned pause producer to fresh provider-backed preparation
  before native readiness. Only Reject is offered; no executor exists.
- Draft PR #13 owns the isolated browser/runtime acceptance and must protect the
  retained services and normal authentication boundary.
- `docs/current/AWS_RESOURCES.md` is the canonical KISS resource/cost view and
  uses canonical account aliases `amit` and `vagent`.
- Cost Explorer readback for 2026-09-01..25 reports `amit` at USD 54.24 MTD;
  its largest service cost is EC2 Compute at USD 28.94 MTD, followed by
  Lightsail at USD 7.62 MTD. `vagent` reports USD 0.00 MTD in its account view.
- Retained host right-sizing stays **`t3.medium`**. The root gp3 volume was grown
  online from 20 to 30 GiB; ext4 root filesystem grew from ~18.3 to 28 GiB and
  usage dropped from 92% to 60%. SSM stayed Online and both retained services
  remained active. No instance stop/restart or type change occurred.
- Live `vagent` inventory confirms `seccop-project1-old-ami-host-r01` (`t3.small`) is SSM Online and almost idle (~0.13% 14-day CPU average), with ~1.59 GiB RAM available and ~10% root-disk use at the sampled point. It is Amazon Linux 2 with Python 3.7 and no Git/Node/Docker, so it is not a clean modern developer workstation. No cleanup or repurpose has been authorized.
- `docs/architecture/DEV_COMPUTE_MODEL.md` defines the accepted design: home workstation for normal development, GitHub Actions for repeatable CI, `amit` `t3.medium` only for the current full LibreChat/Ops/MongoDB integration path, and `vagent` only as a future lightweight AWS canary after an explicit repurpose gate.
- `docs/architecture/HOME_DEV_WORKFLOW.md` is the sanitized Codex/home-workstation bootstrap. GitHub is the source of truth for `AgentCore` and `agentic-ai-cybersecurity-lab`; do not spend time forensically synchronizing the old vagent filesystem unless a concrete irreplaceable artifact is proven.
- `aws-secops` remains reference/archive evidence material, not the primary product repo.

## Next

1. Finish Issue #14 repository acceptance for the account-first cost view and
   keep cleanup as a separate explicit mutation decision.
2. Continue Issue #11 / PR #13 to the real isolated Reject -> receipt ->
   provider readback -> Archive acceptance.

Do not create another roadmap or mistake code/CI acceptance for live completion.
