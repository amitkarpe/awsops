# Agent Context

Repository: `amitkarpe/awsops`  
Status: ACTIVE  
Updated: 2026-09-23

## Current authority

Roadmap Autopilot Issue #1 owns the clean migration from `amitkarpe/aws-secops`.

Current milestone: **M1 — migration inventory + clean contract**.

M1 is repository-only:
- no AWS deployment or mutation;
- no IAM/OIDC/network change;
- no cleanup/archive of the source repository.

## Current truth

- `awsops` is the new clean product repository.
- `aws-secops` remains the reference/archive until explicit cutover.
- Migration is selective: KEEP / REWRITE / LEAVE BEHIND.
- The accepted source baseline includes the released bounded Compliance Agent, durable approval/audit contracts, and later read-only `s3_ssl` research.
- Draft/partial source work is evidence for design, not accepted product truth.

## Next

Finish M1 acceptance and then continue to M2: one clean read-only `s3_ssl` vertical slice.

## Restart

`Read AGENTS.md, CONTEXT.md, SPEC.md and Issue #1. Continue the active migration milestone; treat aws-secops only as migration source material.`
