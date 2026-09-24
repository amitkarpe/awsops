# M3A - durable decision contract, not a second approval system

## Implemented boundary

`trusted provider-backed FrozenScope + server-owned NativeBinding`
`-> register PREPARE_FROZEN -> validated final choice -> durable NATIVE_DECISION`
`-> non-executing reject resolution`

The decision module uses only the standard library and domain records. Its
in-process adapter imports neither AWS clients nor LibreChat. It owns no
executor, network listener, browser session or model-accessible tool.

The future platform-specific integration must authenticate the user, validate
ownership/tenant/action/generation/TTL, and win the paused job's existing claim
before invoking `NativeDecisionAdapter.after_native_claim`. Its name and the
NativeBinding type do not perform those checks for the platform. Never expose
this internal method or registration directly to a model or unauthenticated
HTTP request. A browser-supplied user ID or frozen scope is not trusted context.

## Store and transaction

One private SQLite database contains immutable events. The trusted server
registers a provider-backed FrozenScope and the exact tool, principal, tenant,
conversation, action, generation and tool-call identity. Only the binding
digest is persisted, not those native identity values.

BEGIN IMMEDIATE serializes concurrent claim/check/append operations across
connections. The store checks the registered scope and context, freshness,
expiry and absence of a prior terminal decision in that same transaction.
SQLite synchronous=FULL is configured. The adapter returns only after commit;
connections are explicitly closed. Storage failure propagates with no retry
or continuation. If an acknowledgement is lost after a successful commit, the
receipt remains consumed; bound audit read, not another continuation, is the
recovery path. The caller must terminalize/reconcile its claimed native job.
That platform failure behavior is NOT implemented or proven by this module.

Reject yields REJECTED. An Approve request yields APPROVE_BLOCKED and a reject
resolution with LIVE_EXECUTION_NOT_AUTHORIZED. Both have dispatch_allowed=false.
The adapter does not accept an executor callback and cannot invoke AWS. A
blocked synthetic Approve test is not permission for a live Approve test.

Identical and conflicting repeated decisions are denied. Use the bound audit
read to reconcile a committed receipt after a lost response; never replay a
native continuation. Registration is also single-use and cannot rebind a
prepared scope to another user or paused action.

## Durability and limits

Reopen verifies schema/version, event sequence, canonical payloads, hash links
and prepare/decision consistency. Append-only update/delete triggers prevent
ordinary accidental rewriting. File permissions are private; symlink/broadly
readable database files are rejected on POSIX. Missing files are not silently
recreated during an active operation. A pre-existing unrelated schema or changed
journal mode is refused rather than migrated implicitly.

This small LAB store trusts its filesystem and hosting server. It does not
claim hostile multi-tenant isolation, an external integrity anchor, protection
against a filesystem administrator rewriting the whole chain, full-chain tail
truncation detection, or hardware power-loss certification. It verifies the
small local ledger on each operation; high-volume archival/scaling is not M3A.

The M2 service's planning cache remains in-process. Durable receipts do not
magically restore its cache or a LibreChat checkpoint after restart. Native
recovery, provider readback and terminalization must be wired and proven in
M3's runtime integration. Do not silently rebuild or replay consumed actions.

## Acceptance split

- M2 live read proof is in `../evidence/M2_LAB_READ.json`.
- M3A deterministic tests exercise commit/rollback failure, exact binding,
  replay, scope/time drift, reopen, cross-process races and local tampering.
- No live native choice was made for this package. A real authenticated native
  Reject + receipt + provider readback + cleanup is still required for M3.
- No changes were made to the retained LibreChat deployment or source repo.

## Primary transaction references

- https://www.sqlite.org/lang_transaction.html
- https://docs.python.org/3.12/library/sqlite3.html#how-to-use-the-connection-context-manager

The implementation uses explicit transactions and connection closing rather
than treating a Python connection context manager as a connection lifetime.
