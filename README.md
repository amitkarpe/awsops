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

For the full repository-only cloud/CI verification loop on Linux with Python
3.12, Node 24, npm, Git and Docker Compose:

```bash
python scripts/cloud_verify.py --bootstrap
```

This is also the GitHub Actions CI command. Bootstrap downloads public pinned
fixtures/source, installs the dashboard's locked npm dependencies, and runs an
online npm audit that fails on high/critical advisories or audit errors. Lower
severity findings remain visible; nothing is upgraded automatically. Both modes
run dashboard lint, contracts, pack validation and the build. Later runs can omit
`--bootstrap` to use installed dependencies and fixtures; the online audit and
source reconstruction are then explicitly skipped, so this is not full CI parity.
Use a writable npm cache in restricted cloud sandboxes, for example
`npm_config_cache=/tmp/awsops-npm python scripts/cloud_verify.py --bootstrap`.
The command reports failures and environment-bound skips, never launches Home
services or invokes AWS, and does not establish owner-authenticated/live acceptance.
CI publishes a compact check/skip table in its job summary. See the
[Phase 1 evidence](docs/current/DOT_CLOUD_PILOT.md) and
[Phase 2 parity evidence](docs/current/DOT_CLOUD_CI_PARITY.md).

The same command now installs pinned Playwright Chromium headless shell and runs
the built config2 UI against a synthetic provider on an ephemeral loopback port.
Chromium and its Linux shared-library dependencies must be available; missing
browser/download access fails the check rather than silently skipping it.
The default browser cache is ignored `artifacts/playwright-browsers`; override
with `PLAYWRIGHT_BROWSERS_PATH` if needed. CI retains only labeled synthetic PNGs
and a commit-bound manifest for seven days. See
[cloud browser classification and operation](docs/current/CLOUD_BROWSER_PARITY.md).
This does not replace owner-authenticated LibreChat or live AWS acceptance.

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

See `docs/architecture/DEV_COMPUTE_MODEL.md` for the compute decision and `docs/architecture/HOME_DEV_WORKFLOW.md` for the sanitized local/Codex bootstrap. GitHub is the source of truth; the old `vagent` filesystem is disposable unless proven otherwise.
