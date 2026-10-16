# AGENTS.md

## MVP-FIRST DEVELOPMENT POLICY

Owner override, 16 October 2026. Defence Factory is an MVP / advanced prototype,
not an enterprise production platform. **BUILD → DEMONSTRATE → IMPROVE.**

1. Working functionality before enterprise hardening.
2. Deliver the smallest complete end-to-end vertical slice.
3. Fix real defects; defer hypothetical future problems.
4. Reuse existing code, tools, roles and workflows.
5. No unnecessary frameworks, layers or infrastructure.
6. Minimal meaningful tests and evidence only; reuse completed proof.
7. Do not repeatedly request GO for routine development.
8. DOT is the sole implementer and owns implementation, testing and safe source
   merges when repository gates permit. No Direct, Factory, Codex X or other writer.
9. Optional hardening must NOT block MVP milestones.
10. Enterprise security, scalability, multi-tenant complexity and comprehensive
    edge-case coverage are future phases.

### Mandatory safety boundaries

- Personal AWS LAB only; never company, office, GovTech or PROD accounts.
- Human **Approve Once** for each fixed real-remediation batch.
- Preserve protected awsops Issue #89 fixtures.
- No root credentials, secret exposure or accidental destructive actions.
- Live IAM installation and remediation require exact, separate owner authorization.
- Keep MOCK and REAL evidence distinct. Private bindings stay out of public GitHub.

These are real boundaries, not a reason to invent additional approval ceremonies.
This policy supersedes conflicting older workflow preferences, not these boundaries.
Repository-only work and safe source merges need no repeated GO; source acceptance
never authorizes AWS installation, remediation or publication to a new audience.


Repository: `amitkarpe/awsops`

## Bootstrap

Read in this order:

1. `AGENTS.md`
2. `CONTEXT.md`
3. `SPEC.md`
4. owning Issue/PR
5. `ROADMAP.md` when selecting the next milestone
6. `docs/architecture/MIGRATION.md` when porting from `aws-secops`

GitHub is durable engineering state. Chat history is not authoritative.

## Canonical Agent OS routing

Use this repository file as the local router; do **not** load all of Agent OS for every task.

Relevant canonical guidance:
- [Agent Operating Principles](https://github.com/amitkarpe/agent-os/blob/main/kb/principles/amit-agent-operating-principles.md) — intent-led, evidence-gated delivery and Critical Path First.
- [ChatGPT and Codex Collaboration Protocol](https://github.com/amitkarpe/agent-os/blob/main/kb/playbooks/integrations/chatgpt-codex-collaboration-protocol.md) — G research/planning, X execution truth, handoffs and acceptance.
- [Context Loading Economy](https://github.com/amitkarpe/agent-os/blob/main/kb/playbooks/integrations/context-loading-economy.md) — warm continuation versus authority/recovery reloads.
- [GitHub OIDC and AWS-Owned Control](https://github.com/amitkarpe/agent-os/blob/main/kb/playbooks/integrations/github-oidc-aws-control.md) — durable bounded AWS control and provider readback.

Working default:
- G/ChatGPT owns intent clarification, research sufficiency, ordered plan, scope, safety and final acceptance.
- X/Codex owns live environment facts, implementation, low-level CLI/SSM/AWS execution and validation, and must challenge stale/infeasible plans.
- “80/20” is a heuristic, not a fixed ratio. Simple work may be mostly X; unfamiliar/high-risk/stateful work should be G-researched before mutation.
- Local `SPEC.md` plus the owning Issue/user instruction define actual AWS authority. Agent OS guidance never widens permission.

## Migration rule

`amitkarpe/aws-secops` is a **reference/archive**, not a template to copy.

Every imported idea or component must be classified as:
- **KEEP** — proven contract or implementation worth reusing;
- **REWRITE** — useful behavior with old-repo coupling;
- **LEAVE BEHIND** — historical, duplicated, experimental, or obsolete.

Do not introduce `pilot_v1`-style catch-all modules.

## Operating model

- Follow KISS: one useful vertical slice at a time.
- Prefer one owning roadmap Issue and 2-4 cohesive PRs, not micro-PRs.
- Fix routine implementation/refactor/integration failures autonomously; do not create or expand tests unless Testing Economy justifies it.
- Keep `CONTEXT.md` current-only.
- Treat this public repository, Issues, PRs, Actions logs, and evidence as public.
- Never commit credentials, account IDs, private ARNs/endpoints, auth material, raw private findings, browser state, or session data.

## AWS boundary

Repository work is autonomous.

AWS work requires the active Issue/SPEC to name the LAB/DEV boundary and allowed actions. A successful read proves connectivity, not mutation authority.

Never expose a generic model-accessible AWS mutation/API tool.

Company/office/PROD, IAM/OIDC/network expansion, public exposure, destructive operations, new secrets, or material recurring cost are stop gates unless explicitly authorized.

## Git workflow

```text
Issue -> branch -> cohesive implementation/docs/required validation -> PR -> CI/review
      -> squash merge when accepted -> update CONTEXT/ROADMAP -> continue
```

Use the existing milestone PR for fixes. Do not create replacement PRs unless the trust boundary or scope materially changes.

## Portfolio Economy Defaults

- Testing: default to **zero new tests**. Use the smallest existing validation that can prove the change. Add or modify tests only for a real uncovered regression, contract, security boundary, failure mode, or high-signal isolated logic. Once required checks pass and the changed behavior is proven, **stop**.
- Runners: public repositories may use standard GitHub-hosted runners such as `ubuntu-latest`. Private repositories should avoid GitHub-hosted runners by default and reuse an existing approved CodeBuild/CodePipeline or CodeBuild-hosted Actions runner; do not create new CI infrastructure merely to replace a free public runner.
