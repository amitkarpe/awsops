# Agent Context

Repository: `amitkarpe/awsops`
Status: ACTIVE
Updated: 2026-09-27

## Authority

Roadmap #1 owns migration. G owns roadmap/review/merge and may delegate bounded
repository implementation to X through Bridge2. M2 live reads and M3A/M3B/M3C
repository integration are accepted. Issue #11 and draft PR #13 own the remaining
isolated normal-auth native Reject canary. Issue #29 owns the Home DEV -> AWS
Demo operating model; Issue #39 owns the recovered read-only NEW Config
Dashboard and Compliance Agent demo.

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
- Cost Explorer readback for 2026-09-01..27 reports `amit` at USD 58.51 MTD;
  its largest service cost is EC2 Compute at USD 31.52 MTD, followed by
  Lightsail at USD 8.28 MTD. `vagent` reports effectively USD 0.00 MTD in its account view.
- Retained host right-sizing stays **`t3.medium`**. The root gp3 volume was grown
  online from 20 to 30 GiB; ext4 root filesystem grew from ~18.3 to 28 GiB and
  usage dropped from 92% to 60%. SSM stayed Online and both retained services
  remained active. No instance stop/restart or type change occurred.
- Live `vagent` inventory confirms `seccop-project1-old-ami-host-r01` (`t3.small`) is SSM Online and almost idle (~0.13% 14-day CPU average), with ~1.59 GiB RAM available and ~10% root-disk use at the sampled point. It is Amazon Linux 2 with Python 3.7 and no Git/Node/Docker, so it is not a clean modern developer workstation. **Owner decision 2026-09-27: this `vagent` host is PROTECTED / DO NOT TOUCH.** No stop, terminate, delete, resize, repurpose, retag, IAM or network change is authorized; read-only inspection only unless Amit gives a new exact authorization.
- Legacy Lightsail resources (one running, one stopped; created 2017/2018) are also **PROTECTED / DO NOT TOUCH** by Amit's 2026-09-27 decision. Read-only inspection is allowed; no stop/start/delete/resize/rebuild/tag/IAM/network mutation without new explicit authorization.
- `docs/architecture/DEV_COMPUTE_MODEL.md` defines the accepted design: home workstation for normal development, GitHub Actions for repeatable CI, `amit` `t3.medium` only for the current full LibreChat/Ops/MongoDB integration path, and `vagent` only as a future lightweight AWS canary after an explicit repurpose gate.
- `docs/architecture/HOME_DEV_WORKFLOW.md` is the sanitized Codex/home-workstation bootstrap. GitHub is the source of truth for `AgentCore` and `agentic-ai-cybersecurity-lab`; do not spend time forensically synchronizing the old vagent filesystem unless a concrete irreplaceable artifact is proven.
- `aws-secops` is **FROZEN / REFERENCE** and remains a reference/archive.
  `docs/architecture/AWS_SECOPS_HARVEST.md` is the canonical harvest matrix;
  new implementation belongs only in `awsops`.
- Issue #29 M1-M3 are accepted: Home DEV is the normal development path, OLD demo names remain `ops.astromedicomp.org` / `sec.astromedicomp.org`, and NEW names are `ops2.astromedicomp.org` / `sec2.astromedicomp.org`.
- Issue #33 M1 is merged in PR #34. `integration/edge/awsops_edge.py` now provides an offline NEW-only Route53 planner and additive Nginx renderer. It has no apply/reload/service path; OLD routes remain untouched.
- Issue #33 standing personal-LAB authority covers exact NEW TLS/DNS-01, additive Nginx/service work, and narrow challenge-TXT IAM where needed. Bridge2 capability flags do not constrain Codex native execution. No OLD mutation, deletion, broad IAM, new compute/network resources or PROD.
- Issue #39 M1-M4 is merged in PR #40 at
  `078e4992576cbd8f668c9ddb614df0fc6975c6bc`. The retained LAB host now runs
  that exact merged-main release for both the isolated config2 dashboard and
  the sec2 read-only Compliance Agent import path. Config2 is a persistent NEW
  service on loopback `127.0.0.1:4313`; diagnostics are `READY`, non-partial,
  and contain exactly four aliases by two controls. Its public API projection
  contains no account IDs, resource IDs, ARNs, or raw Config findings.
- NEW `config2.astromedicomp.org` is the canonical dashboard entry point.
  Existing `ops2` DNS and redirect remain compatibility-only and must not gain
  more product behavior. NEW `sec2` exposes exactly one read-only AWS Ops
  Compliance Agent tool for Status, Explain, and no-change Plan. A merged-main
  restart and protocol smoke passed on 2026-09-27. The dashboard and agent have
  no remediation, re-arm, Approve, Reject, or generic AWS action.
- The failed owner rehearsal exposed restrictive generated-asset permissions:
  config2 APIs were healthy, but the non-root service could not read `dist` and
  returned a JSON error for `/`. The live NEW assets were corrected to readable
  file/traversal modes; authenticated public `/` now returns dashboard HTML,
  its JavaScript asset returns 200, and the exact 4 x 2 API remains READY and
  public-safe. Production builds must run `npm run prepare:runtime` before the
  config2 service starts or restarts.
- Issue #39 owner access is now accepted. The NEW sec2 owner identity was
  provisioned in the preserved NEW database using the standing LAB credential
  authority; the pre-existing NEW user and database state were preserved.
  Owner login passed through the public sec2 path. The AWS Ops Compliance Agent
  remained exactly one read-only MCP tool with zero actions, and the required
  owner-session prompts (Status, Explain, and no-change Plan) passed 3/3 with
  evidence-grounded output and no mutation claim. The live repair also corrected
  the NEW sec2 model allowlist, restored service-user execute access to the NEW
  MCP virtual environment, and recovered only the transient NEW sec2 app unit.
  No OLD auth/state or agent model/tool record was changed.
- Issue #49 presentation polish is accepted through the live NEW sec2 browser
  path. PR #54 harvested the proven browser mechanics from deferred PR #13 and
  frozen aws-secops PR #192 into one canonical Playwright acceptance harness.
  Status / Explain / no-change Plan passed 3/3 against the exact reviewed head:
  each answer is bound to the persisted MCP output, rendered with the exact
  four-alias x two-control matrix and final read-only guardrail, and its exact
  test conversation is archived. The harness exports no browser auth or storage
  state. Model-format drift now fails closed to canonical evidence rendering,
  preventing the quote/rewrite/invented-detail regression exposed by the owner
  screenshot. Config2 remained READY/non-partial with four aliases, eight checks
  and two controls; the agent remained exactly one read-only tool / zero actions.
  NEW/OLD TLS and routing regressions passed; no AWS resource, IAM, network, DNS,
  TLS, auth, model/provider, remediation, or OLD runtime state was changed.
- OLD `ops/config/sec` remained active and unchanged through the merged-main
  recovery. Independent public checks returned TLS verification 0 and expected
  statuses: OLD sec 200, OLD ops 308 to config, OLD config 401; NEW sec2 200,
  NEW ops2 308 to config2, and NEW config2 401 without credentials.
- Issue #29 M4 browser walkthrough (2026-09-26): all four public names resolved
  and had valid TLS. On the retained host, headless Chromium reached each
  hostname through the local Nginx listener with HTTPS hostname/certificate
  verification intact. NEW `sec2` used its existing private NEW-only account
  to complete normal browser login at `/c/new`; Chat History, Agent Builder,
  Prompts, and New chat controls were clicked. The earlier NEW `ops2` static
  landing was later replaced by the Issue #39 redirect to config2. OLD `sec`
  showed LibreChat's
  Welcome back login and its theme/registration navigation worked. A final
  Issue #29 browser check used the pre-existing private OLD account to reach
  `/c/new` with a chat composer and click Chat History, Agent Builder, and
  Prompts. OLD `ops` redirected to a protected config endpoint with
  unauthenticated HTTP 401; it is not a public click-through GUI. Post-login
  checks returned expected HTTP status and TLS verification 0 for all four
  public names. No OLD account, credential, service, DNS, vhost, or config was
  changed. M4 browser navigation is accepted; `docs/current/DEMO_DAY.md` is
  the concise sequence. Issue #11 Reject remains deferred.
- Separate NEW Certbot Route53 certificates have exact `sec2`, `ops2`, and
  `config2` SANs and expire 2026-12-25 UTC. The existing Certbot timer is
  enabled; actual unattended renewal has not yet been observed. Check it with
  `systemctl list-timers certbot.timer` and `sudo certbot certificates`; renewal
  uses the same scoped Route53 DNS-01 method. Two retained-role inline
  policies allow only UPSERT of each exact ACME TXT name in the verified zone,
  with required read/list/GetChange actions; no DELETE is granted. Both TXT
  records remain. No resource or evidence was deleted.

## Dual-demo operation

- Start/recover config2 with `sudo systemctl start awsops-config2-app.service`.
  After every dashboard build, run `npm run prepare:runtime` from its release
  directory before starting or restarting the non-root service.
  Confirm `systemctl is-active` and that only loopback owns port 4313, then read
  `/api/health`, `/api/diagnostics`, and
  `/api/controls?environment=ALL&refresh=1`. Require `READY`, `partial=false`,
  four aliases, eight checks, and only the two approved controls.
- Restart config2 with
  `sudo systemctl restart awsops-config2-app.service`; restart only
  `awsops-sec2-app.service` if its agent configuration or release binding
  changed. The isolated sec2 db/model/app recovery procedure remains in the
  [Issue #33 PR #35 handoff](https://github.com/amitkarpe/awsops/pull/35#issuecomment-5845669640).
- Health: run `sudo nginx -t`, check config2 loopback health and sec2 loopback
  `/login`, then verify config2 public TLS, its expected 401 without credentials,
  authenticated dashboard HTML/assets, and sec2 `/login`. Immediately recheck
  OLD ops/config/sec. Ops2 may be read back as compatibility routing but is not
  the canonical NEW journey.
- Stop only NEW sec2, when separately safe to do so:
  `sudo systemctl stop awsops-sec2-app awsops-sec2-model awsops-sec2-db`.
  Stop config2 separately with
  `sudo systemctl stop awsops-config2-app.service` only when its demo is also
  intentionally ending.
  Preserve NEW state, certificates, TXT evidence and both demo generations;
  do not stop OLD services or delete resources. Home DEV remains the normal
  development path; AWS remains short Demo/UAT.

## Next

1. Issue #39 and Issue #49 are accepted: config2, sec2 owner access, the
   read-only AWS Ops Compliance Agent, and its KISS table-first Status /
   Explain / no-change Plan output are the current NEW demo path. Use
   `docs/current/DEMO_DAY.md` for rehearsal.
2. Issue #11 / PR #13 native Reject acceptance is explicitly DEFERRED by Amit and is non-blocking. Do not resume unless Amit re-prioritizes it.
3. Keep old aws-secops PR #177 deferred unless a concrete future awsops read-adapter milestone needs it; Issue #14 remains independent and implies no cleanup mutation.

Do not create another roadmap or mistake code/CI acceptance for live completion.
