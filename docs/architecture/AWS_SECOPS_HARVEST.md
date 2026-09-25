# aws-secops Harvest Matrix

Status: ACTIVE MIGRATION REFERENCE  
Owner: awsops Issue #1  
Updated: 2026-09-25

## Repository roles

```text
amitkarpe/aws-secops = OLD / frozen source-reference
amitkarpe/awsops     = NEW / canonical product
```

Do not implement new product work in `aws-secops`.

G/X may read old Issues, PRs, commits, tests and scripts only to selectively
harvest proven behavior into `awsops`.

## PR #192 — s3_ssl live Reject-only R&D

Old PR:
`amitkarpe/aws-secops#192`

Current value: **HIGH as evidence/test-pattern source**.

### KEEP / adapt into awsops M3

| Area | Decision | Target |
| --- | --- | --- |
| exact native card validation: one Reject / zero Approve / exact tool+scope | **KEEP** | PR #13 browser acceptance |
| rendered-state waits while card/stream UI is settling | **KEEP** | canonical browser harness |
| auth-safe diagnostics: route/method/status/header-name presence only | **KEEP** | browser troubleshooting |
| supported native Archive cleanup bound to exact conversation | **KEEP** | replace Delete-style conversation cleanup |
| Reject submitted once / no accidental Approve | **KEEP** | acceptance assertion |
| durable REJECTED receipt before continuation | **KEEP CONCEPT** | current awsops ledger/receipt implementation |
| zero remediation/MCP dispatch on Reject | **KEEP** | canary acceptance |
| fresh provider readback = unchanged | **KEEP** | current awsops bound readback |
| race/replay/restart/source-drift/readback failure cases | **KEEP TEST IDEAS** | recovery suite |
| exact source-pin / fail-closed compatibility checks | **KEEP METHOD** | current canary source-pinning |

### REWRITE / do not copy literally

| Old implementation | Decision | Reason |
| --- | --- | --- |
| old retained-host deployment/rollback scripts | **LEAVE** | coupled to old runtime/service layout |
| `pilot_v1/*` packaging | **LEAVE** | clean awsops architecture deliberately removes catch-all package |
| old decision/readback implementation | **REWRITE/ALREADY REPLACED** | awsops has cleaner private ledger + bound provider-readback boundary |
| old local HTTP/HMAC seams | **LEAVE** | awsops uses private OS pipes / clean runtime boundaries |
| old runtime auth workarounds | **LEAVE** | normal auth must stay product-native |

### Important #192 lesson

The 401 investigation proved that a browser-harness failure must not be
mistaken for a production-auth failure.

The cleanup lesson is also explicit:

> use LibreChat's supported **Archive** action for the exact test conversation;
> do not use Delete as the normal test cleanup path.

### Closure rule for old PR #192

Do not continue feature development there.

Keep it open only until the remaining useful browser/recovery patterns are
confirmed in awsops PR #13. Then close it as:

**superseded by awsops migration; retained as R&D/evidence reference**

Do not merge it merely to preserve history.

---

## PR #177 — persistent read-only MCP evidence adapter

Old PR:
`amitkarpe/aws-secops#177`

Current value: **MEDIUM as design/test reference; not needed for current M3**.

### KEEP as design patterns

| Area | Decision |
| --- | --- |
| fixed query surface | **KEEP** |
| account identity verification per page/read | **KEEP** |
| bounded page/item limits | **KEEP** |
| explicit partial/unavailable evidence state | **KEEP** |
| rejection of secret-shaped fields | **KEEP** |
| closed normalized schema | **KEEP** |
| synthetic fixtures | **KEEP** |
| default-off live integration gate | **KEEP CONCEPT** |

### Current action

**DEFER PORTING.**

Do not add this adapter to awsops just for parity.

Only port/rewrite it when a future awsops milestone has a concrete need for a
persistent external evidence source. At that time, fit the pattern into the
clean awsops read-adapter layer rather than copying the old module layout.

### Closure rule for old PR #177

Once the freeze notice is accepted, it may be closed as:

**superseded/deferred under awsops; design retained as reference**

No current awsops milestone depends on merging it.

---

## X / Codex repository rule

When Codex is asked to continue the product:

1. clone/open `amitkarpe/awsops`;
2. read `AGENTS.md`, `CONTEXT.md`, `SPEC.md`, Issue #1 and active Issue/PR;
3. work on the existing awsops branch/PR;
4. read `aws-secops` only when old evidence/code is needed;
5. never create new product Issues/PRs in `aws-secops`.

Recommended handoff:

```text
Primary repository: https://github.com/amitkarpe/awsops
Roadmap: https://github.com/amitkarpe/awsops/issues/1

aws-secops is frozen reference material only.
Do not implement new product work there.

For current M3, continue Issue #11 / PR #13.
Read old aws-secops PR #192 only to harvest missing browser/recovery patterns.
Do not copy old deployment/runtime architecture wholesale.
```

## Cutover sequence

1. finish awsops M3 real authenticated Reject acceptance;
2. confirm #192 browser/recovery harvest is complete;
3. close old PR #192 as superseded/reference;
4. close old PR #177 as deferred/superseded unless a concrete future milestone needs it;
5. keep aws-secops readable as historical evidence;
6. complete M4 selective remediation migration;
7. at M5 parity/cutover, archive aws-secops only after explicit cutover acceptance.
