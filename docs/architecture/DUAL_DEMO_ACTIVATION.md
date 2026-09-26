# Dual-demo activation and recovery contract

Owner: Issue #29 M3 under roadmap #1
Status: DESIGN ONLY — no live environment, service, proxy, or DNS changes

## Purpose and names

Keep the reference demo and the `awsops` demo independently recoverable. Home
DEV remains the normal development environment; AWS is used only for an approved
short demo/UAT window. This document proposes an activation contract. It does
not prove either demo can currently start, imply that the proposed names resolve,
or authorize an activation.

| Environment | Intended URLs | Status |
| --- | --- | --- |
| OLD / reference | `ops.astromedicomp.org`, `sec.astromedicomp.org` | Preserve as a recoverable reference. |
| NEW / `awsops` | `ops2.astromedicomp.org`, `sec2.astromedicomp.org` | Proposed names; DNS and routing are unverified. |

## Issue #33 diagnosis: DNS first

The Issue #33 report says Chrome returned `ERR_NAME_NOT_RESOLVED` for both NEW
names while OLD `ops` and `sec` still worked. This places the reported failure
at name resolution, before TLS, the proxy, an application upstream, or browser
behavior. It does **not** establish whether the NEW records are absent, in the
wrong zone, not delegated, or affected by a resolver cache. No authoritative
DNS query or provider read was performed for this repository change, so the
exact DNS defect remains unverified.

Current `awsops` files document the NEW names as proposed only. Issue #11 / PR
#13 documents an isolated normal-auth browser canary, not persistent `ops2` or
`sec2` services. The repository contains no durable NEW hostname-to-service,
service-unit, health-path, or loopback-upstream mapping. That is not proof that
no live process exists; resolve live existence with the read-only inventory
checks below before preparing any activation.

The frozen `aws-secops` reference documents an older edge pattern in
[`docs/implementation/NAMED_UI_DEPLOYMENT.md`](https://github.com/amitkarpe/aws-secops/blob/main/docs/implementation/NAMED_UI_DEPLOYMENT.md)
and [`scripts/subdomain-dns.sh`](https://github.com/amitkarpe/aws-secops/blob/main/scripts/subdomain-dns.sh):
Route 53 commands, an Nginx proxy on a retained personal-LAB host, and two
CNAMEs directed at the preserved legacy A record. Its architecture document
maps `sec.astromedicomp.org` to LibreChat and `ops.astromedicomp.org` to a
redirect/legacy entry. The historical deployment records loopback ports 3333
and 3340 and says both applications share the same stores. Those details are
reference evidence only, not a current live readback or the NEW mapping. In
particular, copying its aliases/upstreams would route back to OLD and its shared
stores violate this document's OLD/NEW isolation rule.

The reference DNS script uses AWS Route 53 CLI with a caller-supplied hosted
zone ID and the profile alias `amit`; it proposes CNAMEs with TTL 60 and stops
on conflicting records. That proves a historical tooling pattern, not current
zone ownership, delegation, account authority, target, or TTL. `awsops` has no
authoritative DNS provider/config path or zone ID recorded. Verify ownership
read-only using the operator's approved identity; do not copy an account ID or
zone ID into this public runbook.

## Dependency chain and proposed NEW activation map

Resolve and review the chain in this order. A later layer cannot compensate
for a failed earlier one.

| Layer | OLD / reference — currently reported working | NEW / `awsops` — required plan and unresolved values |
| --- | --- | --- |
| DNS | Existing `ops` and `sec` names resolve per the Issue #33 report. Exact record types, targets, and TTLs were not read. | Need one record for `ops2.astromedicomp.org` and one for `sec2.astromedicomp.org`. Record type (`CNAME` or provider-supported alias), exact target, TTL, zone, and ownership are `VERIFY-BEFORE-ACTIVATION`. Do not blindly reuse the reference script's legacy-A target. |
| Public proxy and TLS | Reference docs describe Nginx and an existing TLS path; current vhost/certificate state was not inspected. | Proposed separate `ops2` and `sec2` vhosts on a verified approved edge. The `ops2` operator/Ops and `sec2` LibreChat/Sec roles follow the OLD names but are not yet verified for NEW. TLS SANs, listeners, renewal method, source policy, vhost paths, and proxy targets are `VERIFY-BEFORE-ACTIVATION`. |
| Loopback upstream | Historical reference lists LibreChat on loopback 3333 and operator backend on 3340, with shared stores. | Each NEW vhost must route to its own verified NEW loopback service. NEW ports and upstream protocol/paths are `VERIFY-BEFORE-ACTIVATION`; do not reuse canary ports or assume the historical shared-store ports. |
| Service/runtime | The `awsops` resource ledger reports retained LibreChat/Ops/MongoDB services on the `amit` runtime, but does not assign them to the requested NEW public hostnames. | No persistent `ops2/sec2` service mapping is in repository evidence. Exact units, users, checkout/config/data roots, MongoDB identities, auth/session state, and dependencies are `VERIFY-BEFORE-ACTIVATION`. The Issue #11 canary is not proof of these services. |
| Health | OLD URLs are user-reported working; current health endpoints and responses were not queried. | Verify DNS, TLS/SNI and host routing, service revision, documented readiness path, normal auth, database connectivity, and OLD unchanged. NEW health paths and expected status/content are `VERIFY-BEFORE-ACTIVATION`. |

### Read-only resolution checks

Run these only later through the approved operator channel. Keep full output
private; record only sanitized record types/TTL/targets, service names/states,
port roles, and pass/fail in the public Issue. Do not run them as part of this
documentation-only mission.

1. Compare recursive answers and delegation for all four names:

   ```sh
   for host in ops.astromedicomp.org sec.astromedicomp.org ops2.astromedicomp.org sec2.astromedicomp.org; do
     for type in CNAME A AAAA; do dig +noall +answer "$host" "$type"; done
   done
   dig +noall +answer astromedicomp.org NS
   ```

   If OLD answers but NEW is empty, check the authoritative zone and delegation
   before concluding the records are absent. The Chrome symptom alone cannot
   distinguish an absent record from a wrong authority or resolver state.

2. After verifying the approved account/profile and exact public hosted zone,
   use Route 53 read-only calls to inspect only the four names:

   ```sh
   aws route53 list-hosted-zones-by-name --dns-name astromedicomp.org --profile "$VERIFIED_PROFILE" --output json
   aws route53 list-resource-record-sets --hosted-zone-id "$VERIFIED_ZONE_ID" --profile "$VERIFIED_PROFILE" \
     --output json > "$PRIVATE_ROUTE53_RECORDS_JSON"
   TARGET_FQDN="${VERIFIED_DNS_TARGET%.}."
   jq --arg target "$TARGET_FQDN" \
     '{ResourceRecordSets:[.ResourceRecordSets[] | select(.Name==$target or .Name=="ops.astromedicomp.org." or .Name=="sec.astromedicomp.org." or .Name=="ops2.astromedicomp.org." or .Name=="sec2.astromedicomp.org.")]}' \
     "$PRIVATE_ROUTE53_RECORDS_JSON" > "$PRIVATE_ROUTE53_PLANNER_JSON"
   ```

   The reference profile alias is only a hint. Reverify the caller identity and
   zone ownership; if another provider/zone owns delegation, use its read-only
   record inventory instead. Resolve `VERIFIED_DNS_TARGET` from the reviewed
   OLD/edge mapping before building `PRIVATE_ROUTE53_PLANNER_JSON`. That private
   planner input must contain the target's existing A record plus the four public
   names; otherwise `plan-dns` fails closed. Feed that file to the offline planner:

   ```sh
   python3 integration/edge/awsops_edge.py plan-dns \
     --config "$AWSOPS_EDGE_CONFIG" \
     --record-sets "$PRIVATE_ROUTE53_PLANNER_JSON"
   ```

   The verified record inventory determines the exact target and whether the
   planned CNAMEs are safe; do not infer those values from the historical repo.

3. On the verified host, inventory proxy and runtime without changing them:

   ```sh
   sudo nginx -T
   sudo systemctl list-units --type=service --all --no-legend
   sudo systemctl list-unit-files --type=service --no-legend
   sudo ss -ltnp
   ```

   Inspect the Nginx `server_name`, `listen`, TLS certificate references, and
   `proxy_pass`/upstream mapping for OLD and any NEW names. Match unit names,
   process owners, listener sockets, and checkout/config roots. Nginx dumps and
   service metadata can contain private values; keep raw output private and
   publish only sanitized mapping facts. Do not assume `nginx`, `aws-secops-*`,
   or any unit name is the current awsops NEW service name.

4. For every candidate NEW upstream discovered above, use its verified private
   loopback port and application-documented health path for a read-only local
   probe, for example:

   ```sh
   curl --fail --silent --show-error --max-time 5 \
     "http://127.0.0.1:${VERIFIED_NEW_PORT}/${VERIFIED_HEALTH_PATH}"
   ```

   Resolve the port and path from the actual service/config and application
   documentation first. Do not probe a guessed port or treat an open socket as
   health. Validate HTTPS hostname/TLS and normal auth only during a separately
   approved acceptance window.

   In that separately approved window, check SNI/certificate verification and
   the documented HTTPS health path for each NEW hostname:

   ```sh
   openssl s_client -connect "${VERIFIED_EDGE}:443" -servername ops2.astromedicomp.org -verify_return_error </dev/null
   openssl s_client -connect "${VERIFIED_EDGE}:443" -servername sec2.astromedicomp.org -verify_return_error </dev/null
   curl --fail --silent --show-error --max-time 10 \
     "https://ops2.astromedicomp.org/${VERIFIED_OPS_HEALTH_PATH}"
   curl --fail --silent --show-error --max-time 10 \
     "https://sec2.astromedicomp.org/${VERIFIED_SEC_HEALTH_PATH}"
   ```

   `VERIFIED_EDGE` and both verified health paths must come from the reviewed
   activation map. These checks are not part of the current repository-only
   mission.

### Proposed change set after values are verified

The smallest likely activation is two NEW-only DNS records, two NEW-only TLS
vhosts on the verified edge, and distinct NEW loopback app upstream(s) backed by
isolated service configuration/state. The record target should be the approved
edge that actually owns those vhosts, not automatically the OLD application
origin. Whether the existing Nginx edge can safely serve the new vhosts depends
on host identity, capacity, current config and isolation checks above. Do not
create a new edge or assign a port unless the separate approval names it.

The OLD/NEW separation checklist below remains mandatory. In particular,
verify distinct checkout/config roots, MongoDB database and writable storage,
auth/session keys, browser profiles, and evidence directories before assigning
any NEW upstream. A shared host or proxy may be acceptable only if each request
routes to isolated NEW app state and additive configuration leaves OLD behavior
unchanged.

## M1 offline edge planner

`integration/edge/awsops_edge.py` is a local plan/render utility only. Its
`plan-dns` command reads a private operator config plus a saved Route 53
`list-resource-record-sets` response and prints a proposed change batch. It
does not import an AWS SDK, call Route 53, or offer an apply operation. Its
fixed scope is `ops2.astromedicomp.org` and `sec2.astromedicomp.org`; it emits
only `CREATE` for absent names, treats an exact CNAME/target/TTL match as
`UNCHANGED`, and refuses any conflicting pre-existing record. The target must
already have one A record set. TTL 60 follows the reviewed bounded reference
plan. OLD records and the target record are never emitted as changes.

The config must supply the verified retained-host target, a NEW `sec` service
unit, non-overlapping NEW runtime/state roots, its loopback port, and
certificate/key paths in the dedicated `awsops-ops2-sec2` certificate
directory. A NEW `ops` service block is optional and may be `null` until M2
proves a real operator backend; when present it must have a distinct service,
roots, and loopback port. `edge-config.example.json` contains null placeholders
and is intentionally unusable until M2 resolves those values. The validator
refuses missing placeholders, old `aws-secops` service or path values,
overlapping roots, duplicate ports, and a shared/incorrect certificate
directory. The renderer hard-codes loopback as the only upstream address.

`render-nginx` writes only to stdout. It produces an additive include with
NEW-only `server_name` blocks, HTTP-to-HTTPS redirects, loopback-only upstreams,
and WebSocket upgrade headers. It cannot replace or stop the OLD Nginx site.
`ops2` is only a reverse proxy to a verified configured backend; the package
does not create an operator/admin UI. If M2 finds no real NEW Ops backend, keep
`ops` null so neither a DNS record nor an Nginx block is emitted for `ops2`;
record the product gap separately.

The dedicated TLS identity is `awsops-ops2-sec2`; exact file paths and
certificate issuance remain private config. Use DNS-01 for issuance/renewal as
the reference pattern did, but verify the existing challenge mechanism and
least-privilege Route 53 policy for the exact `_acme-challenge` names first.
This PR changes no IAM policy or certificate. Run `nginx -t` against the
reviewed candidate include before any separately approved install/reload; do
not replace the OLD site file.

Offline invocations (no host-side effects):

```sh
python3 integration/edge/awsops_edge.py plan-dns \
  --config "$AWSOPS_EDGE_CONFIG" --record-sets "$PRIVATE_ROUTE53_RECORDS_JSON"
python3 integration/edge/awsops_edge.py render-nginx \
  --config "$AWSOPS_EDGE_CONFIG"
```

Keep the config and readback private; commit neither runtime paths nor private
DNS/provider output. There is no Nginx write, AWS apply, service start/stop, or
live health request in these commands.

Focused offline contract tests:

```sh
python3 -m unittest discover -s tests -p 'test_awsops_edge.py'
```

### M2 read-only runtime preflight

Before filling the example config, G/operator should run these checks over the
approved read-only transport. Keep raw output private and publish only the
sanitized values needed by the activation map:

```sh
sudo systemctl show "$VERIFIED_OLD_UNIT" --property=Id --property=ActiveState \
  --property=SubState --property=FragmentPath --property=User --property=Group \
  --property=WorkingDirectory --property=EnvironmentFiles
sudo systemctl show "$VERIFIED_NEW_UNIT" --property=Id --property=ActiveState \
  --property=SubState --property=FragmentPath --property=User --property=Group \
  --property=WorkingDirectory --property=EnvironmentFiles
sudo certbot certificates
sudo certbot plugins
```

First resolve exact unit names from the service inventory earlier in this
document. Do not run a command for a guessed unit. Read referenced app
configuration privately to confirm runtime/state roots, MongoDB database and
volume identity, auth/session isolation, and browser/evidence paths; report
only distinct/same and verified/unverified, never URIs, keys, usernames,
cookies, or raw environment values. Confirm an actual `ops2` backend exists
before enabling the optional `ops` block.

For the existing DNS-01 principal, inspect current attached and inline policy
names and contents read-only after verifying the operator identity and role:

```sh
aws sts get-caller-identity --profile "$VERIFIED_PROFILE" --output json
aws iam list-attached-role-policies --role-name "$VERIFIED_DNS01_ROLE" --profile "$VERIFIED_PROFILE"
aws iam list-role-policies --role-name "$VERIFIED_DNS01_ROLE" --profile "$VERIFIED_PROFILE"
aws iam get-role-policy --role-name "$VERIFIED_DNS01_ROLE" \
  --policy-name "$VERIFIED_INLINE_POLICY" --profile "$VERIFIED_PROFILE"
aws iam get-policy --policy-arn "$VERIFIED_MANAGED_POLICY_ARN" --profile "$VERIFIED_PROFILE"
aws iam get-policy-version --policy-arn "$VERIFIED_MANAGED_POLICY_ARN" \
  --version-id "$VERIFIED_POLICY_VERSION" --profile "$VERIFIED_PROFILE"
```

Read the reported policy documents privately and confirm the existing policy
can complete DNS-01 only for the required NEW challenge names and verified
zone. Run `get-role-policy` only for a policy returned by `list-role-policies`;
for a managed policy, use its returned ARN and default version from `get-policy`.
Do not edit or widen IAM; if coverage is absent, stop for a separate approval.
Do not publish role ARNs, account IDs, raw policy documents, or challenge
values.

### NEW-only rollback

If an approved NEW activation fails, disable/revert only the exact NEW DNS
records and NEW vhost fragments introduced by that change, then stop only the
identified NEW app units that were started for the window. Keep OLD DNS, vhosts,
certificates, services, stores, and state at their recorded baseline. Preserve
NEW state, logs, and evidence for recovery; do not delete resources. If config
is shared with OLD or the rollback cannot be scoped precisely to NEW, do not
activate until that collision is resolved.

The old `vagent` learning host is not synonymous with the OLD/reference demo.
The retained `amit` host is documented as hosting the full LibreChat/Ops/
MongoDB integration runtime; that fact does not identify which demo owns each
service or establish the proposed NEW mapping.

## Mapping and isolation contract

The repository has no verified, current inventory assigning demo directories,
service units, listener ports, health paths, database names/volumes, proxy
targets, or DNS records to OLD and NEW. Resolve each item from an approved,
read-only host/config inventory and record it in the activation change before
acting. Do not guess from historical evidence or reuse a value from the
disposable Issue #11 browser canary.

| Boundary | OLD / reference | NEW / `awsops` | Required proof |
| --- | --- | --- | --- |
| Checkout and writable app/config roots | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Distinct roots and explicit release revision; no shared writable checkout/config. |
| Service units, users, process targets | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Exact unit/user names and stop targets from the host; no wildcard stop/kill. |
| App and dependency loopback ports | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Actual listeners plus a reserved, non-overlapping NEW assignment; bind privately as designed. |
| MongoDB URI, database, user, data volume | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Separate database identity and writable storage; no cross-environment writes. |
| Auth/session keys and account boundary | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Independent private configuration and session-signing material; no copied credentials. |
| Browser profile, cookies, local storage | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Separate profile directories and login/session state. Never copy browser state. |
| Logs, receipts, ledgers, checkpoints, uploads | `VERIFY-BEFORE-ACTIVATION` | `VERIFY-BEFORE-ACTIVATION` | Separate writable paths and retention; preserve both evidence sets. |
| Proxy virtual hosts, TLS, upstreams, DNS | Existing targets and records: `VERIFY-BEFORE-ACTIVATION` | Proposed names and targets: `VERIFY-BEFORE-ACTIVATION` | Read-only before/after inventory; exact host, certificate, listener, upstream, and record mapping. |

The intended proxy design is one explicit virtual-host mapping per hostname:
the two OLD names route only to the OLD app upstreams, and the two proposed NEW
names route only to separately assigned NEW app upstreams. Keep app and database
listeners private; publish only the approved TLS proxy entrypoint. Exact
addresses, listener ports, service names, upstreams, certificate coverage, DNS
record values/TTLs, and health paths remain `VERIFY-BEFORE-ACTIVATION`. Do not
point a public name at a development or disposable canary listener. In
particular, loopback ports used by the Issue #11 isolated browser canary are not
the demo port map.

No shared writable database, volume, session store, auth key, browser profile,
or evidence directory is allowed by this design. If a future verified topology
requires sharing, stop and obtain a reviewed, explicit exception that explains
consistency, access, rollback, and blast-radius behavior before activation.

## Collision preflight — all checks must pass

Record a sanitized baseline for both environments and check all of the
following before any future service, proxy, or DNS action:

- [ ] Confirm the owning Issue names the environment, reviewed commit, operator,
  account/Region, allowed actions, timebox, health checks, rollback target, and
  stop procedure.
- [ ] Inventory exact checkout/config/data roots, owners, permissions, current
  revisions, service units/users, process IDs, and current health for OLD and
  NEW. Confirm no path or stop target overlaps.
- [ ] Read current listeners and proxy configuration. Confirm all OLD and NEW
  app/dependency ports are distinct, available for their intended role, and
  loopback/private where required. Check that no unrelated listener is targeted.
- [ ] Confirm each hostname has exactly the intended virtual host, TLS
  certificate coverage, upstream, and DNS target/TTL. Detect duplicate
  `server_name` entries, wildcard/default-host collisions, stale records, and
  unintended public listeners. Proposed NEW DNS remains untouched until a
  separate explicit change gate passes.
- [ ] Confirm MongoDB connection identities, database names, users, volumes,
  backup/recovery points, and write targets are distinct. Check any cache,
  queue, object storage, upload directory, or shared filesystem used by either
  app for the same isolation.
- [ ] Confirm independent auth configuration, session/signing keys, cookie
  domains, browser profile paths, and test accounts. Do not copy or print
  credentials, cookies, tokens, or profile contents.
- [ ] Confirm log, audit, receipt, ledger, checkpoint, and evidence paths are
  separate and retained. Verify the rollback revision/config is available
  without deleting or rewriting evidence.
- [ ] Confirm start/stop commands name only the selected environment's exact
  services. No broad process kill, shared dependency restart, cleanup, or
  deletion is part of this contract.
- [ ] Capture read-only OLD/reference health and revision evidence before the
  NEW change so the post-check can demonstrate it was untouched.

Any unknown, overlap, unexpected listener, ambiguous ownership, failed health
check, or missing rollback target is a stop condition. Resolve it in the
activation review; do not improvise during the window.

## Activation order

This is a future operator sequence only; it does not authorize execution.

1. Review this contract and the separate live activation approval. Reconfirm
   the target, reviewed revision, preflight results, timebox, operator,
   communications, stop/rollback commands, and evidence plan.
2. Capture sanitized OLD and NEW baselines: exact revisions, service state,
   listeners, health, and state/config identities. Keep secrets and private
   identifiers out of shared evidence.
3. Start only the selected environment's isolated dependencies that are
   confirmed stopped and required. Verify their own health and storage identity.
4. Start that environment's exact app service(s). Verify expected revision,
   readiness, normal authentication, and dependency connectivity on the private
   loopback endpoints.
5. Only after a separate approved proxy/DNS change gate, apply the reviewed
   host-to-upstream mapping. Validate TLS, hostname routing, health, and login
   for each changed name. Never expose database or app development ports.
6. Run only the short acceptance steps in the owning Issue. Capture sanitized
   results, exact revision, timestamps, health results, and any failed stage.
7. Recheck OLD/reference health and revision against its baseline after NEW
   activation. A changed or unavailable OLD environment fails the independence
   proof; stop the selected NEW work and follow the approved rollback.

No hostname should be activated until its folder/service/port/state/proxy map
is populated with verified values and all collision checks pass.

## Health, stop, and recovery

Health checks must be specified in the activation Issue using verified paths.
At minimum, independently check for each environment: expected hostname and
TLS certificate, exact app revision, documented readiness response, normal
login/session behavior, app-to-database health, and no listener on an
unintended public interface. An open port, running process, or green CI alone
does not establish application readiness or live acceptance.

At the end of a demo window:

1. Save sanitized acceptance output and required logs/evidence; preserve
   receipts, ledgers, checkpoints, and database state.
2. If routing was separately changed, follow that change's approved reversal
   order and verify the intended hostname state. Do not alter OLD routing as an
   ad hoc fix for NEW.
3. Stop only the exact app/dependency services started for the selected demo,
   in reverse dependency order: app first, then only its newly started
   dependencies. Do not stop pre-existing or shared/uncertain services.
4. Verify selected services returned to their recorded baseline and the other
   environment still matches its baseline. Record sanitized final health.
5. If rollback is partial, ambiguous, or makes either environment unhealthy,
   stop further changes and report it through the owning Issue.

Recovery means restarting the preserved, accepted revision with its matching
configuration and state under its environment-specific procedure. Preserve
both demos, data, volumes, addresses, DNS records, proxy configurations,
ledgers, and evidence. **Delete nothing.** No cleanup, repurpose, or retirement
is implied.

## Old/reference untouched proof

Before and after any separately approved NEW activation, compare the sanitized
OLD baseline and final read-only inventory: revision, exact service/process
state, listener ownership, health, and relevant configuration/data identity.
The NEW change must use only its verified isolated roots and targets. Record
the comparison with timestamps and the NEW change identifier. If the OLD
baseline cannot be established or is not preserved, independence is unproven;
do not claim acceptance. This design document itself contains no live proof.

## Separate live activation gate

M3 repository design does not authorize a cloud, DNS, proxy, network, or service
mutation. Before any such work, open/update an owning Issue with explicit
approval for the exact environment and actions; the fully verified mapping and
collision checklist; account/Region and target identities; operator and
timebox; expected health checks; evidence plan; and exact stop/rollback steps.
Review the change plan and obtain the required approval at that time. If any
mapping field remains `VERIFY-BEFORE-ACTIVATION`, do not activate. Keep both
environments recoverable and delete nothing.
