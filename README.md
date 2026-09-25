# AWS Ops

Clean, selectively migrated AWS security-operations contracts.

## Current acceptance

- M2 live read/prepare/readback passed across four registered personal-LAB
  aliases. The temporary probe changed no existing services or AWS resources.
- M3 repository code supplies a durable ledger, private native bridge and
  trusted pause registration. Readiness follows fresh provider verification
  and durable registration, not model-supplied evidence.
- The isolated native-browser Reject canary is still pending in Issue #11 / PR #13.
- Remediation remains disabled. The old repo is reference material, not a
  runtime dependency or an automatic source of credentials/deployment authority.
- Issue #14 owns the KISS read-only AWS resource/cost ledger and EC2 right-sizing evidence.

Read `CONTEXT.md`, `SPEC.md`, Issue #1 and the active milestone Issue before work.
Migration choices are in `docs/architecture/MIGRATION.md`.

## AWS resource ledger

Canonical public view: `docs/current/AWS_RESOURCES.md`.

Refresh it from an existing personal-LAB AWS profile:

```bash
AWS_PROFILE=amit python scripts/aws_resources_report.py --alias personal-lab
```

The collector uses fixed read/list/describe/tag/metric/pricing operations only.
It emits logical classes and account aliases, never raw account IDs or provider
resource identifiers. Cost values are explicitly labeled as actual, estimated,
usage-based, direct-$0 or unknown.

## Tests

```bash
python scripts/fetch_native_fixture.py
AWSOPS_REQUIRE_NATIVE_FIXTURE=1 python -m unittest discover -s tests -p 'test_*.py'
```

The explicit fixture step fetches two immutable upstream source files and
verifies their whole Git blobs. Python 3.12 and Node 22 are used in CI.
Offline tests without fixtures do not establish native integration acceptance.
