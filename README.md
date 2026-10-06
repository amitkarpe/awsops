# AWS Ops

Clean, selectively migrated AWS security-operations contracts.

## Current acceptance

Roadmap #77 M1–M4 source preparation is merged in PRs #78–#81. Normal
repository engineering uses the saved cloud environment and GitHub CI. M3/M4
synthetic success is not live AWS approval; identity/acquisition and Config Pack
writes remain gated. Start with the canonical
[operating and recovery runbook](docs/architecture/DEV_COMPUTE_MODEL.md).

The earlier product/native roadmap remains separate:

- M2 live read/prepare/readback passed across four registered personal-LAB
  aliases. The temporary probe changed no existing services or AWS resources.
- M3 repository code supplies a durable ledger, private native bridge and
  trusted pause registration. Readiness follows fresh provider verification
  and durable registration, not model-supplied evidence.
- The isolated native-browser Reject canary remains deferred in Issue #11 / PR #13.
- Remediation remains disabled. The old repo is reference material, not a
  runtime dependency or an automatic source of credentials/deployment authority.
- Issue #14 owns the KISS read-only AWS resource/cost ledger and EC2 right-sizing evidence.
- Issue #49 browser acceptance is captured in
  `docs/architecture/PLAYWRIGHT_E2E.md`: Playwright verifies the live sec2
  tool -> persisted answer -> rendered DOM -> Archive path without exporting
  browser auth or enabling remediation.

Read `CONTEXT.md`, `SPEC.md`, Issue #1 and the active milestone Issue before work.
Migration choices are in `docs/architecture/MIGRATION.md`.

## AWS resource ledger

Canonical public view: `docs/current/AWS_RESOURCES.md`.

Refresh it from an existing personal-LAB AWS profile:

```bash
AWS_PROFILE=amit AWSOPS_EXPECTED_ACCOUNT=<private-account-id> \\
  python scripts/aws_resources_report.py --alias amit
```

The collector STS-verifies the private expected controller account first, then uses fixed read/list/describe/tag/metric/pricing operations only.
It emits logical classes and canonical account aliases (`amit`, `vagent`), never raw account IDs or provider
resource identifiers. Cost values are explicitly labeled as actual, estimated,
usage-based, direct-$0 or unknown.

## Tests

For full repository-only verification from the root on Linux with Python 3.12,
Node 24, npm, Git, Docker Compose and Chromium system libraries:

```bash
python scripts/cloud_verify.py --bootstrap
```

This is the GitHub Actions command: pinned public-source bootstrap, locked
install/audit, contracts, M3/M4 synthetic evidence, lint/build and synthetic
browser. It starts no Home services and makes no AWS calls. Without `--bootstrap`,
audit/download/source-reconstruction skips mean the result is not full CI parity.
The [runbook](docs/architecture/DEV_COMPUTE_MODEL.md) covers writable cache setup,
exact-head hosted verification, artifact limits, safe recovery and operator gates.

The narrower native contract loop remains:

```bash
python scripts/fetch_native_fixture.py
AWSOPS_REQUIRE_NATIVE_FIXTURE=1 python -m unittest discover -s tests -p 'test_*.py'
```

The explicit fixture step fetches two immutable upstream source files and
verifies their whole Git blobs. Python 3.12 and Node 24 are used in CI.
Offline tests without fixtures do not establish native integration acceptance.
For the Compliance Agent browser path, see `docs/architecture/PLAYWRIGHT_E2E.md`.

## Development compute

Use the [canonical compute/runbook](docs/architecture/DEV_COMPUTE_MODEL.md).
Home remains the NEW demo/private-browser runtime, not a cloud-engineering
fallback. Retained hosts stay under their separate owner boundaries.
