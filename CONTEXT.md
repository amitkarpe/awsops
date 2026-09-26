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
- Issue #33 standing personal-LAB authority covers exact NEW TLS/DNS-01, additive Nginx/service work, and narrow challenge-TXT IAM where needed. Bridge2 capability flags do not constrain Codex native execution. No OLD mutation, deletion, broad IAM, new compute/network resources or PROD.
- Issue #33 Option A public reachability is live on the retained host. NEW `sec2`
  has isolated transient db/model/app units on loopback 27111/4312/4311,
  respectively; `/login` returns HTTP 200 with TLS verification 0. NEW `ops2`
  is an additive static read-only Nginx landing, with `/` and `/health` returning
  HTTP 200/TLS 0. There is no NEW operator backend or mutation UI. Both NEW
  CNAMEs use the verified retained target; OLD `sec/ops` DNS, vhosts and units
  were untouched. Immediate OLD public checks returned sec HTTP 200/TLS 0 and
  ops HTTP 308/TLS 0, then HTTP 401/TLS 0 after its redirect. Private normal
  sec2 login returned HTTP 200 with a user object; its in-memory bearer accessed
  protected `/api/user` and `/api/models` at HTTP 200. M4 public and private
  HTTP acceptance was complete at Issue #33 closeout; browser GUI navigation
  was exercised later under Issue #29 as recorded below.
- Issue #29 M4 browser walkthrough (2026-09-26): all four public names resolved
  and had valid TLS. On the retained host, headless Chromium reached each
  hostname through the local Nginx listener with HTTPS hostname/certificate
  verification intact. NEW `sec2` used its existing private NEW-only account
  to complete normal browser login at `/c/new`; Chat History, Agent Builder,
  Prompts, and New chat controls were clicked. NEW `ops2` showed its read-only
  status page and its link opened `sec2` login. OLD `sec` showed LibreChat's
  Welcome back login and its theme/registration navigation worked. OLD `ops`
  redirected to a protected config endpoint with unauthenticated HTTP 401;
  it is not a public click-through GUI. No OLD credential was available in this
  session, so authenticated OLD sec navigation remains an operator Demo Day
  check. No OLD service or state was changed. The concise sequence is
  `docs/current/DEMO_DAY.md`; Issue #11 Reject remains deferred.
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

1. Execute Issue #29 M4 Demo Day readiness now: exercise the supported OLD and NEW browser GUI paths, fix only demo blockers, and produce one concise click-through checklist for Amit. Preserve the accepted HTTP/API baseline from Issue #33.
2. Issue #11 / PR #13 native Reject acceptance is explicitly DEFERRED by Amit and is non-blocking. Do not resume unless Amit re-prioritizes it.
3. Keep old aws-secops PR #177 deferred unless a concrete future awsops read-adapter milestone needs it; Issue #14 remains independent and implies no cleanup mutation.

Do not create another roadmap or mistake code/CI acceptance for live completion.
