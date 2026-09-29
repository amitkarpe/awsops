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
npm run prepare:runtime
```

`prepare:runtime` makes the generated static dashboard readable by the
non-root config2 service even when the deployment shell uses a restrictive
umask. Run it after every production build and before restarting config2.

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
- `/api/cockpit` — bounded public-safe projection for the Home demo cockpit
- `/api/resources?alias=lab-dev&control=restricted-ssh` — exact registered
  account/control drill-down. At most ten affected resources are returned per
  read as ordinal `resource-01` references, allowlisted family, status and
  evaluation time. `truncated=true` means the displayed list is incomplete;
  account IDs, resource IDs, ARNs and raw findings are never returned.

`control-registry.json` is the versioned allowlist shared by the Config
provider, dashboard, Compliance Agent backend and Home validator. The live
four-alias read for Issue #68 found only its two rules (S3 bucket public access
and restricted SSH); no EC2/EBS, S3 encryption or RDS rule was present in this
aggregator. These are eight account/control checks, **not** eight different
controls. M4 must separately decide whether to authorize more Config rules.
Missing, mismatched or over-30-day-old per-resource evidence fails the detail
read; it never becomes a compliant/green result. The detail list is not a
remediation or generic resource lookup interface.

## Home demo cockpit

The first dashboard panel uses the same four-alias/two-control provider as
`/api/diagnostics` and `/api/controls`. It shows READY only when the exact
eight-check matrix is complete, its oldest fetch is recent, the versioned
Compliance Agent contract still has one tool/zero actions, and a recent real
Harness invocation succeeded. Missing, failed, or older-than-15-minute Harness
telemetry shows DEGRADED. A route that has not been independently reported is
shown as `NOT_REPORTED`; this page does not create a public route.

For Home, set `AWSOPS_HARNESS_TELEMETRY_FILE` to the **same existing owner-private
absolute file path** in both the sec2 MCP process and config2 service. The
Compliance Agent writes only last-call status, latency, and time through its
existing `harness_client.py` invocation path. Configure a private directory
readable by those two processes; no prompt, answer, ARN, session, account ID,
or raw finding is stored. Do not commit the file or its path. Without this
optional integration the cockpit remains visibly DEGRADED while existing
Status/Explain/Plan behavior continues to work.

No demo re-arm, preview, confirmation, history, mutation or generic AWS action
is part of this package.

Source/provenance decisions:
https://github.com/amitkarpe/awsops/blob/g/issue-39-g-implementation/integration/config_dashboard/SOURCE_PROVENANCE.md
