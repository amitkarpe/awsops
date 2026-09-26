# NEW demo edge

Owner: https://github.com/amitkarpe/awsops/issues/39

The edge tool renders configuration; it does not deploy services, issue
certificates, change DNS, or establish application readiness.

## Dashboard map

The example now selects the three-host format by including `config`:

- `ops2` is an entry redirect to `https://config2.astromedicomp.org$request_uri`.
  Its `/health` response proves only that the redirect vhost is configured.
- `config2` proxies to the explicit NEW loopback dashboard. Basic authentication
  covers its UI and API. The proxy permits GET/HEAD only and does not forward
  the Basic authentication header to the upstream. The backend must independently
  omit mutation routes; method filtering does not make an arbitrary backend safe.
- `sec2` retains its separate loopback upstream and WebSocket headers.

`ops` must be null in this format. `config` requires a NEW `basic_auth_file`
path in addition to the service/unit/root/port fields. Authentication material
stays private; this tool neither creates credentials nor copies OLD accounts.
`tls` has separate `ops`, `config` and `sec` entries. Null example values must be
filled from verified private operator inputs, never treated as live defaults.

The earlier two-host format remains accepted when `config` is absent. Its
shared TLS identity and optional ops backend remain unchanged for compatibility.

## Readiness boundary

DNS planning is CREATE-only, refuses conflicts, and preserves matching records.
Supply a complete current record inventory including config2 and the retained
A-record target. The preflight collector accepts the legacy two-host schema and the current
`config2` dashboard schema. In dashboard mode it inventories OLD `ops/config/sec`,
NEW `ops2/config2/sec2`, the NEW config2 service/port, and separate NEW certificate
identities. Its output is still inventory evidence only: authentication, browser
journey, provider completeness and owner acceptance remain separate proof.

A rendered file contains all configured NEW vhosts. Review and replace only
matching NEW blocks; do not install duplicate server names beside existing
NEW blocks. Never replace OLD configuration. Validate the exact candidate with
`nginx -t` on the intended host before any separately reviewed reload.

Issue #39 remains incomplete until the real dashboard source/provider and
owner access are available, the collector is aligned, and the authenticated
browser/data/agent journey is verified. A valid generated config is not demo
acceptance. Do not activate the ops2 redirect before config2 is actually ready.
