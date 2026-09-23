# AGENTS.md

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
- Fix routine test/refactor/integration failures autonomously.
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
Issue -> branch -> cohesive implementation/tests/docs -> PR -> CI/review
      -> squash merge when accepted -> update CONTEXT/ROADMAP -> continue
```

Use the existing milestone PR for fixes. Do not create replacement PRs unless the trust boundary or scope materially changes.
