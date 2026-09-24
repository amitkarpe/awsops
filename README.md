# AWS Ops

Clean, selectively migrated AWS security-operations contracts.

## Current acceptance

- M2 live read/prepare/readback passed across the four registered personal-LAB
  aliases. The temporary probe changed no deployed services or AWS resources.
- M3A supplies a repository-only durable decision ledger and native adapter
  contract. No native runtime integration or live Reject E2E is claimed yet.
- Remediation remains disabled. The old repository is reference material,
  not a runtime dependency or an automatic source of deployment authority.

Read `CONTEXT.md` for the restart point, `SPEC.md` for boundaries, and Issue #1
for the roadmap. Migration choices are in `docs/architecture/MIGRATION.md`.

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
