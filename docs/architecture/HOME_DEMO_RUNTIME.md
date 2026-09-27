# Home demo runtime and EC2 stop gate

Owner: Issue #56 under roadmap #1.

## Why this exists

The 2026-09-27 retained-host audit proved that the NEW application source is
largely preserved, but several launch/configuration details lived only on the
EC2 filesystem or in transient systemd state. This page defines the clean
rebuild boundary before any EC2 stop.

## Source-of-truth split

| Category | Source of truth |
| --- | --- |
| config2 source/build | `integration/config_dashboard/` |
| Compliance Agent | `integration/compliance_agent/` |
| edge renderer/design | `integration/edge/` |
| runtime/service templates | `integration/runtime/` |
| LibreChat source | exact pin in `integration/runtime/librechat-runtime.json` |
| private values | owner-local files / approved private stores, never Git |
| MongoDB/user/chat state | runtime data, not source code |
| Issue #11 Reject canary | deferred PR #13 reference; not Home baseline |

## EC2-only artifacts classified

### Captured/reproducible

- persistent config2 service contract;
- sec2 MongoDB/app service contract;
- loopback ports and working directories;
- Config/Compliance-Agent private environment key schemas;
- pinned LibreChat source;
- NEW edge mapping via the existing renderer plus accepted runtime inventory.

### Intentionally private/runtime-only

- Config target IDs/aggregator value;
- Harness identifier and AWS SSO/session material;
- LibreChat application secrets;
- MongoDB data/user records;
- login/browser state;
- certificate private keys and Basic-auth secret material.

These should survive a stopped EC2 on EBS, but Home DEV must **not** depend on
copying them. Home uses fresh local runtime state and owner-supplied private
inputs.

### Deferred, not part of Home baseline

The running `awsops-sec2-model` process belongs to Issue #11's deterministic
Reject-only canary. Its exact implementation is preserved in PR #13. The
read-only Compliance Agent Home demo does not import or enable that Reject path.

## Stop-readiness checklist

Issue #56 may declare the retained `amit` EC2 **STOP-READY** only when all are
true:

- [ ] fresh Home checkout passes repository validation;
- [ ] config2 builds, starts and returns local `/api/health`;
- [ ] pinned LibreChat source can be prepared without the EC2 filesystem;
- [ ] isolated local MongoDB starts on loopback;
- [ ] Compliance Agent MCP wiring is reconstructible from Git + private inputs;
- [ ] normal local owner login/browser journey is proven;
- [ ] public-demo tunnel choice is documented and tested separately;
- [ ] owner understands stopped EC2 retains EBS cost/state and is not terminated;
- [ ] protected Lightsail and protected `vagent` remain untouched.

Until the local browser + tunnel gates are complete, the answer remains
**NOT STOP-READY** even though the runtime source/glue is now captured.
