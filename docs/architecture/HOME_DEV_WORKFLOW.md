# Home DEV and AWS Demo Runbook

Status: OPERATING MODEL
Owner: Issue #29 / roadmap #1; home workstation baseline from Issue #14

## Purpose

Use the home workstation for normal development and keep AWS for short,
approved demo/UAT runs. AWS is not the normal development box.

Do not commit its hostname, SSH alias, IP address, local username, private paths, SSH config, keys, or other workstation identifiers to this public repository.

## Operating cycle

```text
Home DEV -> GitHub branch/PR/CI -> approved AWS demo start
          -> short final acceptance -> stop the AWS demo
```

| Stage | Responsibility |
| --- | --- |
| Home DEV | Edit, build, run local tests and browser checks, and prepare a reviewable branch. Do not keep a cloud stack running for ordinary coding. |
| GitHub PR/CI | Review the exact commit, required checks, and public-safe evidence. Start a demo only from the reviewed commit with required checks green and an active Issue that names the target and allowed actions. CI success alone is not live acceptance. |
| AWS demo/UAT | Host only the integration or user acceptance that needs the AWS-hosted app or provider identity. Use the approved host/transport and a short timebox; capture sanitized results, then stop the demo services started for that run. |

## Demo names

| Role | URLs | Status |
| --- | --- | --- |
| Old/reference demo | `ops.astromedicomp.org` and `sec.astromedicomp.org` | Preserve as a recoverable reference environment. |
| New awsops demo | `ops2.astromedicomp.org` and `sec2.astromedicomp.org` | Proposed/reserved names. This runbook does not imply DNS exists or authorize DNS changes. |

Keep both environments recoverable. This Issue authorizes no DNS, cloud, IAM,
network, or live-service changes; those require their own active authority.
If the proposed aliases are not configured, validate through the currently
approved endpoint and leave DNS unchanged.

## Startup checklist

1. Read the active Issue and confirm its target environment, account/Region,
   allowed actions, timebox, operator, and stop/rollback procedure. If any are
   missing or conflict with observed state, do not start.
2. Verify the exact Git commit to be exercised. The PR is reviewed and all
   required CI checks are green for that commit. Do not deploy dirty or
   unreviewed local changes.
3. Through the approved operator transport, read the current service/host
   state and record a sanitized baseline. Confirm both demo environments and
   their data/evidence are preserved; check capacity and the selected
   environment's source/config revision.
4. Start only the selected environment's required demo services using its
   approved procedure. Keep its intended exposure and authentication boundary;
   do not change DNS or widen network access as an ad hoc fix.
5. Check application readiness, dependency health, normal authentication, and
   the expected demo URL before UAT. A running host alone is not a healthy app.
6. Run only the Issue's short acceptance steps. Record the exact commit,
   outcome, sanitized evidence, and any failed stage. Do not claim acceptance
   from CI or a smoke check alone.

## Shutdown checklist

1. Preserve the acceptance result, logs needed to explain failures, and any
   audit/receipt state. Redact credentials, cookies, tokens, private resource
   identifiers, and raw findings before sharing evidence.
2. Stop only the demo services started for this run, using the approved
   environment-specific procedure. Do not stop unrelated retained services.
3. Verify those services are stopped and any services that were not part of
   the run remain in their recorded baseline state. Record the final sanitized
   status.
4. If the run changed app configuration, restore only its exact known-good
   configuration/revision using the documented rollback. Verify the restored
   health state; if rollback is partial or ambiguous, stop and report it.
5. Leave both environments, DNS, hosts, disks, addresses, databases, and audit
   evidence in place. Delete nothing; do not add cleanup or snapshot actions.

## Health and rollback

- Check the intended name resolves as expected, HTTPS/TLS is valid, the app
  responds on its documented readiness path, normal login works, and required
  dependencies are healthy. Use only endpoints and checks defined by the
  active Issue; do not infer readiness from an open port or running instance.
  Do not treat an unconfigured proposed alias as permission to add DNS.
- Keep the old/reference and new awsops demo paths separate. A failure in one
  is not authority to alter the other.
- On failure, capture the failing stage and sanitized state, stop only the
  services started for that demo, and restore its exact previous app/config
  revision if needed. Preserve databases, ledgers, audit evidence, and both
  demo environments for recovery and demonstration. Delete no resources.
- If the affected service, baseline, or rollback target is unclear, leave
  unrelated state untouched and escalate through the owning Issue.

## Source-of-truth repositories

Work from GitHub rather than preserving old EC2 filesystem state:

- `amitkarpe/awsops`
- `mytestlab123/AgentCore`
- `mytestlab123/agentic-ai-cybersecurity-lab`

Do not confuse the old `vagent` host with the old/reference demo URL
environment. The host's historical rebuild/disposal assessment does not
authorize deleting or repurposing either demo environment.

## Local workflow

```text
home Ubuntu workstation
  -> clone/pull repo
  -> read AGENTS.md / CONTEXT.md / active Issue
  -> develop + test locally
  -> push branch
  -> GitHub Actions
  -> use AWS only for tests that truly need AWS-hosted state
```

## Codex bootstrap

On the home workstation, Codex should start with read-only environment discovery:

```bash
uname -a
cat /etc/os-release
git --version || true
python3 --version || true
node --version || true
npm --version || true
docker --version || true
uv --version || true
aws --version || true
```

Then create one ordinary workspace, for example:

```bash
mkdir -p ~/git
cd ~/git
```

Clone only the repository needed for the current task. Do not clone or synchronize EC2 files merely because they exist.

For an existing clone:

```bash
git status
git remote -v
git fetch --all --prune
git switch main
git pull --ff-only
```

Before implementation, Codex must read the repository's own bootstrap files and current Issue/PR. Repository rules override this generic handoff.

## Installation rule

Do not install a large platform stack pre-emptively.

Install tools only when the active repository requires them.

Preferred pattern:

- Python project -> repository-declared Python/uv environment;
- Node project -> repository-declared Node/npm/yarn version;
- Terraform/CDK -> install only if the current task uses it;
- Docker -> only when the current task specifically benefits from containers;
- browser/Playwright -> use repository-owned setup/scripts.

Avoid persistent local databases/services unless the current milestone requires them.

## AWS rule

Local development does not create AWS authority.

Use existing authenticated AWS mechanisms only when the active Issue/SPEC explicitly authorizes the account, Region and action.

Prefer:

```text
local tests
  -> GitHub CI
  -> AWS read-only proof
  -> bounded AWS canary only when necessary
```

Do not use the home workstation as a new generic multi-account mutation controller.

## vagent rule

Do not spend time synchronizing the old `vagent` host.

If a future canary needs AWS-local execution:

1. define the exact canary in the owning Issue;
2. check whether it can run on the existing `t3.small`;
3. if yes, use an isolated directory/process with explicit TTL;
4. if modern tooling makes the old Amazon Linux 2 host awkward, prefer a clean rebuild later rather than accumulating one-off upgrades.

Any stop/start/retag/rebuild/snapshot/termination remains a separate AWS mutation decision.

## amit rule

Keep the current `amit` `t3.medium` full integration runtime unchanged until M3 acceptance.

Ordinary coding should move to the home workstation now; the paid `amit` runtime should eventually become an integration-only resource rather than a developer workstation.

## First local tasks

Good first Codex work on the home workstation:

1. run repository tests/builds;
2. fix repository-only failures;
3. develop Astro/Markdown/documentation work;
4. develop Python/Node logic;
5. run local browser automation;
6. prepare AWS plans/fixtures without mutating AWS.

Do not wait for EC2 merely to perform these tasks.
