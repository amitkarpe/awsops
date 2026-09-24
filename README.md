# AWS Ops

Clean, selectively migrated AWS security-operations contracts.

## Current acceptance

- M2 live read/prepare/readback passed across four registered personal-LAB
  aliases. The temporary probe changed no existing services or AWS resources.
- M3 repository code supplies a durable ledger, private native bridge and
  trusted pause registration. Readiness follows fresh provider verification
  and durable registration, not model-supplied evidence.
- The isolated native-browser Reject canary is still pending. CI/rehearsal is
  not a claim of live authentication or end-to-end acceptance.
- Remediation remains disabled. The old repo is reference material, not a
  runtime dependency or an automatic source of credentials/deployment authority.

Read `CONTEXT.md`, `SPEC.md`, Issue #1 and active Issue #11 for current truth.
Migration choices are in `docs/architecture/MIGRATION.md`.

## Tests

```bash
python scripts/fetch_native_fixture.py
AWSOPS_REQUIRE_NATIVE_FIXTURE=1 python -m unittest discover -s tests -p 'test_*.py'
```

The explicit fixture step fetches two immutable upstream source files and
verifies their whole Git blobs. Python 3.12 and Node 22 are used in CI.
Offline tests without fixtures do not establish native integration acceptance.
