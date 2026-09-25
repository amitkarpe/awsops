# Home Development Workflow

Status: READY FOR LOCAL USE  
Owner: Issue #14 / roadmap #1

## Purpose

Use the user's **Ubuntu 24.04 x86-64 home workstation** as the default zero-cloud-cost development machine.

Do not commit its hostname, SSH alias, IP address, local username, private paths, SSH config, keys, or other workstation identifiers to this public repository.

## Source-of-truth repositories

Work from GitHub rather than preserving old EC2 filesystem state:

- `amitkarpe/awsops`
- `mytestlab123/AgentCore`
- `mytestlab123/agentic-ai-cybersecurity-lab`

The old `vagent` host is considered reproducible/disposable unless a specific irreplaceable artifact is proven.

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
