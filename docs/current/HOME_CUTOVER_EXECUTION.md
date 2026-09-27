# Home cutover execution

Owner: Issue #56  
Mode: **Roadmap Autopilot — one execution PR, many milestones**

Standing approval: Amit approved continuous execution on 2026-09-27. Do not ask
for `go` between routine steps. Stop only at Issue #56 hard gates.

## M2 — real Home bootstrap

- [ ] Fresh `awsops/main` on Home Ubuntu.
- [ ] `python scripts/home_demo.py check` PASS.
- [ ] Pinned LibreChat prepare/verify PASS.
- [ ] Isolated local MongoDB PASS.
- [ ] Local config2 health PASS.
- [ ] Live Config diagnostics READY/non-partial exact 4 x 2 when owner SSO is available.
- [ ] No EC2 filesystem copied.

## M3 — Home browser acceptance

- [ ] Normal owner login.
- [ ] Canonical AWS Ops Compliance Agent registered/selected.
- [ ] Exactly one read-only MCP tool / zero actions.
- [ ] Status PASS.
- [ ] Explain PASS.
- [ ] No-change Plan PASS.
- [ ] Persisted MCP output == persisted assistant text == rendered DOM contract.
- [ ] Test conversations archived; no browser auth/storage export.

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
- [ ] `vagent` untouched.
- [ ] Resource/cost ledger updated.
- [ ] Cutover/recovery runbook updated.

## Evidence rule

Keep public evidence sanitized. Never commit account IDs, ARNs, credentials,
cookies, browser storage, owner passwords, raw private findings or tunnel secrets.

## Final acceptance

This PR remains open until M2-M5 pass. Routine fixes, scripts, tests and docs are
added to this same PR. Merge only after Issue #56 acceptance is complete.
