# AWS Ops

Clean, selectively migrated AWS security-operations contracts.

## Current acceptance

- M2 live read/prepare/readback passed across four registered personal-LAB
  aliases without changing deployed services or AWS resources.
- M3A supplies the durable decision ledger. M3B adds a private process bridge,
  pinned native-controller integration and offline rollback rehearsal.
- Native-runtime deployment and authenticated browser Reject acceptance remain
  pending. No remediation or new authentication mechanism is enabled.

Read `CONTEXT.md` for current issue/PR status, `SPEC.md` for boundaries and
Issue #1 for the roadmap. Runtime plan: `docs/architecture/M3_NATIVE_RUNTIME.md`.

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Python 3.12+ and Node 22 are required. CI explicitly downloads and verifies one
immutable upstream controller fixture before the same command. Without that
fixture, local tests report native-controller/rollback groups as skipped, not
accepted. No credentials or AWS calls are needed by the test suite.
