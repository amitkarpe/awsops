# Agent Context

Repository: `amitkarpe/awsops`
Status: ACTIVE
Updated: 2026-09-26

## Authority

Roadmap #1 owns migration. G owns roadmap/review/merge and may delegate bounded
repository implementation to X through Bridge2. M2 live reads and M3A/M3B/M3C
repository integration are accepted. Issue #11 and draft PR #13 own the remaining
isolated normal-auth native Reject canary. Issue #29 owns the Home DEV -> AWS
Demo operating model; Issue #33 owns additive NEW `ops2/sec2` activation work.

Issue #14 owns operational hygiene: the public-safe AWS resource/cost ledger,
account-level cost visibility and retained-host capacity evidence. Amit explicitly
authorized one bounded LAB mutation: grow the `amit` retained host root gp3 volume
from 20 to 30 GiB and extend its existing ext4 root filesystem online. That
change completed successfully. Instance type remains `t3.medium`; cleanup remains
unauthorized.

Issue #33 separately authorizes exact personal-LAB NEW `sec2/ops2` DNS, TLS,
Nginx and service activation. It does not authorize OLD `sec/ops` mutation,
deletion, broad IAM, new compute/network resources, live Approve or PROD work.

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
- `aws-secops` is now formally treated as **FROZEN / REFERENCE** for new product work and remains **reference/archive** evidence until M5. `docs/architecture/AWS_SECOPS_HARVEST.md` is the canonical harvest matrix for old PR #192/#177. New implementation belongs only in `awsops`; old repo remains readable evidence until M5 cutover/archive.
- Issue #29 M1-M3 are accepted: Home DEV is the normal development path, OLD demo names remain `ops.astromedicomp.org` / `sec.astromedicomp.org`, and NEW names are `ops2.astromedicomp.org` / `sec2.astromedicomp.org`.
- Issue #33 M1 is merged in PR #34. `integration/edge/awsops_edge.py` now provides an offline NEW-only Route53 planner and additive Nginx renderer. It has no apply/reload/service path; OLD routes remain untouched.
- Issue #33 Option A public reachability is live on the retained host. NEW `sec2`
  has isolated transient db/model/app units on loopback 27111/4312/4311,
  respectively; `/login` returns HTTP 200 with TLS verification 0. NEW `ops2`
  is an additive static read-only Nginx landing, with `/` and `/health` returning
  HTTP 200/TLS 0. There is no NEW operator backend or mutation UI. Both NEW
  CNAMEs use the verified retained target; OLD `sec/ops` DNS, vhosts and units
  were untouched. Immediate OLD public checks returned sec HTTP 200/TLS 0 and
  ops HTTP 308/TLS 0. Authenticated sec2 login/application smoke is still
  **pending**, so M4 is not fully accepted.
- Separate NEW Certbot Route53 certificates have exact `sec2` and `ops2` SANs
  and expire 2026-12-25 UTC. The existing Certbot timer is enabled; actual
  unattended renewal has not yet been observed. Check it with
  `systemctl list-timers certbot.timer` and `sudo certbot certificates`; renewal
  uses the same scoped Route53 DNS-01 method. Two retained-role inline
  policies allow only UPSERT of each exact ACME TXT name in the verified zone,
  with required read/list/GetChange actions; no DELETE is granted. Both TXT
  records remain. No resource or evidence was deleted.

## Dual-demo operation

- Start/recover NEW sec2: verify the isolated NEW root, free ports, certificates
  and `nginx -t`, then replay the exact `systemd-run` db -> model -> app sequence
  in the [Issue #33 PR #35 handoff](https://github.com/amitkarpe/awsops/pull/35#issuecomment-5845669640).
  These are transient units, not boot-enabled services. NEW ops2 is served by
  Nginx alone and has no backend unit.
- Health: `systemctl is-active awsops-sec2-db awsops-sec2-model awsops-sec2-app`,
  `curl -fsS http://127.0.0.1:4311/login`, `sudo nginx -t`, and public HTTPS
  checks from an independent operator client for OLD sec/ops and NEW sec2
  `/login` plus ops2 `/health`. Require TLS verification 0 for each public name.
- Stop only NEW sec2, when separately safe to do so:
  `sudo systemctl stop awsops-sec2-app awsops-sec2-model awsops-sec2-db`.
  Preserve NEW state, certificates, TXT evidence and both demo generations;
  do not stop OLD services or delete resources. Home DEV remains the normal
  development path; AWS remains short Demo/UAT.

## Next

1. Complete the private authenticated sec2 login/application smoke and record
   its result on Issue #33. Review PR #35 separately; do not confuse its
   read-only collector CI with live acceptance. Preserve OLD and NEW demos.
2. Continue Issue #11 / PR #13 to the real isolated Reject -> receipt -> provider readback -> Archive acceptance.
3. Keep old aws-secops PR #177 deferred unless a concrete future awsops read-adapter milestone needs it; Issue #14 remains independent and implies no cleanup mutation.

Do not create another roadmap or mistake code/CI acceptance for live completion.
