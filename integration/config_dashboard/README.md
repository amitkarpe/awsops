# awsops config2 dashboard

Owner: https://github.com/amitkarpe/awsops/issues/39

This is the versioned NEW read-only Config Dashboard recovered from the proven
host-local dashboard source.

## Build

Use the observed source toolchain first: Node.js 24.x and npm 11.x.

```bash
npm ci
npm run build
npm run lint
```

No new unit-test suite is required for the Issue #39 recovery slice.

## Runtime

The service listens on loopback only and defaults to port `4313`.

Private runtime variables:

- `AWSOPS_CONFIG_AGGREGATOR_NAME` — exact existing read-only Config aggregator;
- `AWSOPS_CONFIG_TARGETS_JSON` — exact four private `alias/account_id` bindings;
- `PORT` — optional loopback port override after collision recheck.

The committed source contains no target account IDs or aggregator name.

Start:

```bash
node server.mjs
```

Public routing is separate:

```text
ops2.astromedicomp.org -> 308 -> config2.astromedicomp.org
config2.astromedicomp.org -> Basic auth -> 127.0.0.1:4313
sec2.astromedicomp.org -> existing NEW LibreChat
```

The config2 API exposes only read-only GET/HEAD routes:

- `/api/health`
- `/api/diagnostics`
- `/api/controls?environment=ALL&refresh=1`

No demo re-arm, preview, confirmation, history, mutation, generic AWS action or
resource-detail route is part of this package.

Source/provenance decisions:
https://github.com/amitkarpe/awsops/blob/g/issue-39-g-implementation/integration/config_dashboard/SOURCE_PROVENANCE.md
