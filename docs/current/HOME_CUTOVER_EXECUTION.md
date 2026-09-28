# Home cutover execution

Owner: Issue #56  
Mode: **Roadmap Autopilot — one execution PR, many milestones**

Standing approval: Amit approved continuous execution on 2026-09-27. Do not ask
for `go` between routine steps. Stop only at Issue #56 hard gates.

## M2 — real Home bootstrap

**Status: PASS on the verified Home Ubuntu workstation.** Execution used a separate clean PR #58 checkout; the unrelated Home checkout and office WSL worktree remained untouched.

- [x] Fresh PR #58 checkout on Home Ubuntu.
- [x] `python scripts/home_demo.py check` PASS.
- [x] Pinned LibreChat prepare/verify PASS.
- [x] Isolated local MongoDB PASS on loopback.
- [x] Local config2 health PASS on loopback.
- [x] Existing owner-approved read-only AWS profile produced READY, non-partial exact 4 x 2 evidence.
- [x] No retained-EC2 filesystem, database, environment, TLS, cookies, browser state, or secrets copied.

## M3 — Home browser acceptance

- [x] Normal owner login.
- [x] Canonical AWS Ops Compliance Agent registered/selected.
- [x] Exactly one read-only MCP tool / zero actions.
- [x] Status PASS.
- [x] Explain PASS.
- [x] No-change Plan PASS.
- [x] Persisted MCP output == persisted assistant text == rendered DOM contract.
- [x] Test conversations archived; no browser auth/storage export.

Home browser acceptance passed all three exact prompts on 2026-09-28. The run exposed and fixed the Node 24 requirement, literal MCP command template, local browser origin, AWS profile propagation, and MCP timeout needed by the pinned runtime. Evidence remains owner-private; public proof records only structural counts and PASS/GAPS.

## M4 — public NEW tunnel

- [ ] One NEW-only temporary tunnel from Home.
- [ ] Provider-assigned HTTPS hostname first; no Route53/custom DNS change.
- [ ] No home-router inbound forwarding.
- [ ] Remote Status/Explain/Plan PASS.
- [ ] Restart/stop commands documented.
- [ ] No new material recurring paid infrastructure.

## M5 — cost cutover

- [ ] Final read-only retained-host / EBS / EIP verification.
- [ ] Home NEW demo independent of EC2.
- [ ] Retained `amit` EC2 stopped, **not terminated**.
- [ ] Stopped state verified.
- [ ] EBS/EIP retained.
- [ ] Lightsail untouched.
- [ ] `vagent` stop-only action reconciled separately via `aws-platform` Issue #107; never terminate/delete/resize/retag or change its EBS/EIP/IAM/network/DNS.
- [ ] Resource/cost ledger updated.
- [ ] Cutover/recovery runbook updated.

## Evidence rule

Keep public evidence sanitized. Never commit account IDs, ARNs, credentials,
cookies, browser storage, owner passwords, raw private findings or tunnel secrets.

## Final acceptance

This PR remains open until M2-M5 pass. Routine fixes, scripts, tests and docs are
added to this same PR. Merge only after Issue #56 acceptance is complete.


## Execution environment boundary — 2026-09-28

- Office laptop / office WSL: **NO runtime installs**. Read/review/Git/docs only.
- Home system: all Docker/Compose, MongoDB, LibreChat, Playwright/browser and tunnel work.
- Home runtime target: **dev@home**, owned by `aws-platform` Issue #99.
- Hermes/Issue #106 remains separate and is not a prerequisite for Home runtime work.
- Bridge2 routing mismatch #109 is fixed in aws-platform main. A second mission-lifecycle blocker remains: fresh bounded read-only project and Factory missions can stay `running` without publishing a terminal result. Issue #94 is reopened with fresh reproduction evidence; its proven readback fix is now merged directly to aws-platform main via PR #114. Live runtime reload/cancellation must still wait for a safe idle checkpoint (#96/#109).
- Existing relay/direct bridge evidence is not permission to install runtime dependencies on office WSL.
- Resume M2 only on the actual Home system. Do not improvise an office fallback.


## Bridge continuation checkpoint — 2026-09-28

- aws-platform #108 capability split: merged/complete.
- aws-platform #109 route/status mismatch: repository fix merged.
- aws-platform #94 readback fix: ported directly to current main in PR #114.
- Live Bridge remains occupied by two bounded read-only missions that have not published terminal results:
  - one project-profile #109 acceptance mission;
  - one Factory #99 Home-preflight mission.
- Do not redispatch, force-clear, restart Bridge/app-server, or install office runtime while those executions are ambiguous.
- #96 owns safe mission-cancel/reconciliation semantics.
