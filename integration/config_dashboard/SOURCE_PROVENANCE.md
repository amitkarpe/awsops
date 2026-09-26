# Source provenance

- Origin: host-local, non-Git OLD `refine-config-console` source.
- OLD core source SHA256: `4558b1d17758730b317a5dc40fe95012c6a378d15fc254905b2a28f8eb03c1dd`.
- Sanitized archive SHA256: `21fcdabcbeab5dfff495ca556c5d740c1f63527631104a5c9c07f12a2089aa06`.
- Observed source toolchain: Node.js `v24.20.0`; npm `11.19.0`.
- Attribution and third-party notices: `NOTICE.md`.

## Issue #39 adaptation

**KEEP**

- React/Refine visual structure, responsive layout, dashboard views and local theme.
- Four-account freshness/partial-result semantics.
- The fixed S3 Block Public Access and restricted-SSH product vocabulary.

**ADAPT**

- The AWS Config reader now requires explicit private NEW bindings through
  `AWSOPS_CONFIG_TARGETS_JSON` and `AWSOPS_CONFIG_AGGREGATOR_NAME`.
- The runtime is loopback-only and defaults to the NEW config2 candidate port
  `4313`.
- The public API projects only alias, approved control key/category,
  compliance state, affected count/capped flag, warning, and bounded freshness.
- The Compliance Agent link targets `https://sec2.astromedicomp.org/`.

**LEAVE BEHIND**

- demo-admin / re-arm / preview / confirmation / CodeBuild mutation routes;
- audit/job/history state and routes;
- fixture and synthetic account modes;
- OLD DEV/PROD profile bindings;
- raw Config rule identifiers, source/scope/input-parameter details and
  resource identifiers.

The NEW package is intentionally read-only. It contains no generic AWS action
or remediation route. Private account IDs, aggregator name, credentials and
authentication material remain runtime configuration and are never committed.
