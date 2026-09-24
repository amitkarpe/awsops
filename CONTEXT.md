# Agent Context

Repository: `amitkarpe/awsops`  
Status: ACTIVE  
Updated: 2026-09-23

## Current authority

Roadmap Autopilot Issue #1 owns the clean migration from `amitkarpe/aws-secops`.

M1 is complete and merged.

Current milestone: **M2 — read-only s3_ssl vertical slice**.

M2 permits:
- repository implementation and tests;
- personal-LAB read-only verification for the exact registered aliases;
- exact identity/Region validation;
- no AWS mutation.

## Current truth

- `awsops` is the new clean product repository.
- `aws-secops` remains reference/archive until explicit cutover.
- Migration is selective: KEEP / REWRITE / LEAVE BEHIND.
- M2 implements a runtime-neutral fixed S3 TLS evidence path; account IDs remain private runtime input and are never emitted.
- No legacy S3 BPA/SSH executor is part of M2.

## Next

Finish M2 tests and personal-LAB read-only evidence. Then continue to M3 native Reject-only decision.

## Restart

`Read AGENTS.md, CONTEXT.md, SPEC.md and Issue #1. Continue M2 read-only s3_ssl; no AWS mutation.`
