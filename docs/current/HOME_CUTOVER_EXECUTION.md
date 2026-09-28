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

**Status: PASS.** One Cloudflare quick tunnel exposed only Home sec2 loopback.
The provider-assigned hostname and browser evidence remain owner-private.

- [x] One NEW-only temporary tunnel from Home.
- [x] Provider-assigned HTTPS hostname; no Route53/custom DNS change.
- [x] No home-router inbound forwarding.
- [x] Remote Status/Explain/Plan PASS.
- [x] Restart/stop commands documented.
- [x] No new material recurring paid infrastructure.

Start the temporary tunnel from Home after the local sec2 service is healthy:

```text
cloudflared tunnel --no-autoupdate --url http://127.0.0.1:4311
```

Keep the assigned hostname in the private owner manifest. Set LibreChat's
private client/server origins to that exact HTTPS origin, restart only the Home
LibreChat process, and run the canonical compliance-agent browser acceptance.
To stop, terminate only that `cloudflared` process and restore the private
client/server origins to the loopback Home value before restarting the local
LibreChat process. This procedure does not alter DNS, the retained EC2 host or
OLD services.

Remote acceptance produced the exact three mode results, one read-only tool,
zero actions, eight checks per result, and Archive readback for all three test
conversations. Browser auth and storage state were not exported.

## M5 — cost cutover

**Status: PASS.** The exact retained `amit` host reached `stopped`; it was not
terminated. Git and the Home rebuild path are the NEW demo source of truth.

- [x] Final read-only retained-host / EBS / EIP verification.
- [x] Home NEW demo independent of EC2.
- [x] Retained `amit` EC2 stopped, **not terminated**.
- [x] Stopped state verified.
- [x] Encrypted 30 GiB gp3 volume remains attached; Elastic IP remains associated.
- [x] Lightsail untouched.
- [x] `vagent` remained untouched in this execution; its separate boundary remains owned by `aws-platform` Issue #107.
- [x] Resource/cost ledger updated.
- [x] Cutover/recovery runbook updated.

After the stop, the Home public HTTPS sec2 path returned 200 with TLS
verification, config2 remained READY/non-partial with four aliases and eight
checks, and the remote three-prompt acceptance remained PASS. The stopped host
retains recovery data and address allocation; no resource was deleted.

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
