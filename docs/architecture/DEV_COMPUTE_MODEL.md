# Development Compute Model

Status: PLAN ACCEPTED FOR REPOSITORY DESIGN  
Updated: 2026-09-25  
Owner: Issue #14 / roadmap #1

## Decision

Use a **home-first development model**.

```text
Home workstation
  -> local coding / unit tests / docs / browser work
  -> GitHub
  -> GitHub Actions for repeatable CI
  -> AWS only when a test really requires AWS-hosted state, SSM, provider identity,
     native LibreChat integration, or account-local evidence
```

Do not treat EC2 as the default developer workstation.

## Current compute roles

| Account | EC2 name | Size | Role now | Decision |
| --- | --- | --- | --- | --- |
| `amit` | `agentcore-issue19-librechat-poc-r01` | `t3.medium` | full retained LibreChat + Ops + MongoDB integration runtime | **KEEP unchanged for current M3 acceptance** |
| `vagent` | `seccop-project1-old-ami-host-r01` | `t3.small` | old SecCop / Inspector-to-SSM learning host | **candidate lightweight AWS canary after a separate repurpose gate** |

## Why home-first

The home workstation should own:

- source editing;
- Python/Node development;
- Markdown/Astro/documentation work;
- unit tests;
- deterministic local integration tests;
- Terraform/CDK synthesis and plan generation;
- browser automation that does not require an AWS-hosted application;
- Git/GitHub workflow.

GitHub Actions should own:

- repeatable CI;
- lint/test/build;
- immutable fixture verification;
- repository-only acceptance.

AWS should be used only for behavior that cannot be proven locally.

This avoids paying for an EC2 instance merely to obtain a Linux shell or AWS-control access.

## `amit` runtime

Keep `agentcore-issue19-librechat-poc-r01` on `t3.medium` for now.

Reasons:

- it already hosts the retained LibreChat/Ops/MongoDB integration stack;
- M3 native browser acceptance still depends on a complete AWS-hosted runtime;
- current memory evidence does not justify `t3.small`;
- the root volume has already been corrected from 20 to 30 GiB.

Do not add ordinary development work to this host.

Longer-term cost lever:

1. finish M3;
2. prove which components truly need 24x7 AWS hosting;
3. move ordinary development to home/GitHub;
4. then evaluate a **stop-when-idle** or retirement model for the `amit` EC2 runtime.

Stopping or retiring the host is not authorized by this plan.

## `vagent` canary evidence

Live read-only discovery on 2026-09-25:

- EC2 name: `seccop-project1-old-ami-host-r01`;
- size: `t3.small`;
- SSM: Online;
- 14-day CPU average: about **0.13%**;
- observed CPU maximum: about **12.4%**;
- memory: about **1.89 GiB total**, **1.59 GiB available** at sample time;
- swap: **0**;
- root filesystem: about **20 GiB**, **10% used**;
- public IPv4: present;
- OS: **Amazon Linux 2**;
- Python: **3.7.16**;
- Git: not installed;
- Node: not installed;
- Docker: not installed;
- no application service is currently listening besides ordinary base-system services;
- old demo TTL has expired.

Cost Explorer currently shows its account usage is being offset by credits.
Treat that as **credit-funded**, not permanently free.

## Recommended `vagent` role

Do **not** install the full LibreChat/MongoDB/Ops stack on this `t3.small`.

Use it, after explicit repurpose approval, for lightweight AWS-hosted jobs such as:

- SSM-based smoke tests;
- provider-read/readback probes;
- small Python canaries;
- bounded AgentCore API/runtime experiments that fit within memory;
- network/account-local tests that cannot run from home or GitHub-hosted CI.

Do not use it for:

- MongoDB + LibreChat + multiple background services;
- long-running developer shells as the normal workflow;
- broad shared tooling accumulated over time;
- generic multi-account mutation;
- production workloads.

## Repurpose strategy

The current `vagent` host is an old Amazon Linux 2 experiment. Reuse must be deliberate, but **do not spend time doing forensic host preservation**.

GitHub is the source of truth:

- `mytestlab123/AgentCore` contains the AgentCore architecture, OIDC/Gateway-policy and related platform work;
- `mytestlab123/agentic-ai-cybersecurity-lab` contains the SecCop learning/demo code, browser helpers and runbooks;
- if useful host-only state cannot be identified quickly, recreate it from repository code instead of preserving the machine.

The live host inventory already shows no active application service, no Git/Node/Docker install and only base-system listeners. Therefore the preservation rule is:

1. keep repository history;
2. keep the existing public-safe AWS evidence already recorded;
3. no default EBS/AMI snapshot;
4. no filesystem-by-filesystem sync;
5. rebuild rather than reverse-engineer old local state.

A snapshot remains an AWS mutation/cost event and is justified only if a concrete irreplaceable artifact is later identified.

### Choose one clean path

Preferred order:

**Option 1 — lightweight in-place canary**

Use only if the required canary needs very little tooling.

- isolated directory;
- isolated Python environment;
- fixed service/user boundary;
- SSM only;
- no public app listener;
- no MongoDB/LibreChat;
- explicit TTL;
- remove only the new canary material when done.

**Option 2 — clean replacement**

Use if modern Node/Python/container tooling becomes a real requirement.

- preserve old SecCop evidence first;
- create a current supported image/runtime;
- keep `t3.small` only if measured memory fits;
- terminate the old AL2 host only after explicit approval.

Do not slowly transform the old AL2 learning host into an undocumented permanent platform.

## Cost policy

| Compute | Cost posture |
| --- | --- |
| Home workstation | preferred for normal development |
| GitHub Actions | preferred for repeatable repository CI |
| `amit` t3.medium | paid retained integration runtime; minimize 24x7 dependency after M3 |
| `vagent` t3.small | currently credit-funded; use only for bounded AWS-hosted canaries |
| New EC2 | avoid unless a concrete host/VPC-local requirement exists |

Every persistent AWS compute resource must remain visible in
`docs/current/AWS_RESOURCES.md` with:

- account alias;
- EC2 Name tag;
- size;
- state;
- age;
- purpose;
- cost basis;
- RETAIN / REVIEW / CLEANUP-CANDIDATE decision.

## Migration trigger

Do not move AgentCore workload merely because `vagent` appears free.

Move a workload only when all are true:

1. local/home execution cannot prove the requirement;
2. the workload fits comfortably inside `t3.small` memory/CPU;
3. required AWS identity/network locality is documented;
4. the authoritative SecCop/AgentCore state is present in GitHub or explicitly declared disposable;
5. the canary has an explicit lifecycle/TTL;
6. no public ingress, IAM expansion, secret migration, or target-resource mutation is implicitly introduced;
7. the active Issue records the exact mutation boundary.

## Near-term sequence

1. **Home first:** keep new source development and tests off EC2.
2. **Finish M3 on `amit`:** do not destabilize the accepted full runtime mid-milestone.
3. **Home workstation first:** use the Ubuntu 24.04 home system for normal Codex/development work; keep private hostnames/SSH aliases out of this public repo.
4. **Prepare `vagent` only when needed:** define one exact lightweight canary workload; do not perform forensic sync of the old host.
5. **Reassess `amit` after M3:** the largest savings comes from reducing its always-on duty cycle, not from moving ordinary coding between two EC2 hosts.

## Stop gates

Explicit approval remains required for:

- stopping/starting/terminating either EC2;
- retagging/rebuilding the `vagent` host;
- snapshot/AMI creation;
- installing a new persistent runtime/service on `vagent`;
- public ingress;
- IAM/OIDC/credential changes;
- cross-account trust;
- material new recurring cost;
- moving the M3 live canary away from its currently approved `amit` boundary.
