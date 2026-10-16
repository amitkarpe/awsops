# Fixed disposable S3 canary — source milestone (#90)

`src/awsops/execution/s3_canary.py` connects the existing canonical Batch / Decision /
Run / Evidence records to one injected provider. There is no AWS SDK, CLI, HTTP
entry point, workflow dispatch or live provider installation in this milestone.

## Fixed scope and approval

- Only private `CanaryBinding` for `amit`, `ap-southeast-1`, one exact disposable
  empty bucket. Public output uses `resource-disposable-s3-canary`; never a bucket
  name/account ID. No inventory, target creation, deletion or #89 resource access.
- Reuse `s3-require-tls` / `DENY_INSECURE_TRANSPORT` from the existing contract,
  scope digest convention, preparation TTL/freshness constants and conservative
  policy recognizer. Encryption was a design candidate, but has no canonical
  capability yet; this slice does not invent a new wire action or alter mirrors.
- Trusted backend `prepare(principal_digest)` reads fresh exact provider evidence
  and stores the immutable batch. No existing policy is overwritten. A compliant
  or unfamiliar existing policy is left intact, without manufacturing drift.
- Trusted backend `decide(batch_id, scope_digest, principal_digest, choice)` binds
  authenticated human Approve Once/Reject to that saved batch. Imported JSON,
  digest possession and browser assertions do not authenticate a principal.
- SQLite commits the one-time decision before any provider call. Approve rechecks
  exact account/Region/resource, disposable ownership, emptiness, current policy
  digest and expiry before the fixed TLS-deny write. Reject, stale, drift, wrong
  identity/principal/scope and replay perform zero writes.
- `reconcile(batch_id, principal_digest)` reads back the SAME run, never rewrites.
  The private ledger must survive process restarts. Ambiguous acknowledgment or a
  process interruption after a claim requires reconciliation, never a new batch
  to retry. A consumed decision with no saved run requires operator review.

## Provider and evidence boundary

The provider protocol exposes only `inspect(binding)` and `put_policy(binding,
fixed_policy)`. Later live wiring must independently prove exact private identity,
owner-designated disposable ownership/tags, emptiness (including versions), and
absence of clients/protected fixtures. A boolean supplied by an untrusted caller
is not such proof. No generic model-controlled AWS method is exposed.

Fake providers use MOCK: all writes are **simulated**, provenance SYNTHETIC.
The optional APPROVED_LAB_WRITE protocol mode is not connected to a live client.
Write counts conservatively count attempted calls when acknowledgment is unknown.
Provider MATCH does not imply Config compliance convergence: compliance UNKNOWN,
freshness NOT_VERIFIED, run NEEDS_REVIEW, never VERIFIED. No Config call occurs.
Actual source revision/version are caller-supplied; hostedVersion stays null.
The current shared v1 schema requires the showcase `-mock` source-version label;
this is not an observed hosted/live release claim.

The existing `DecisionStore`, native gate, `APPROVE_BLOCKED` and legacy Reject-only
behavior remain unchanged. No consumer/schema mirror change or frontend work.

## Focused offline proof

```sh
python3 -m unittest discover -s tests -p test_s3_canary.py -v
node contracts/defence-factory/intake-check.cjs
```

One fake-provider proof covers approval/readback, Reject, stale, drift, identity,
emptiness, scope/principal mismatch, uncertain acknowledgment, unavailable readback
and durable restart/replay exclusion. Envelope fields and state enums are checked
against `contracts/defence-factory/v1.schema.json` without a new dependency;
private bindings never appear in exported records.

Next: M reviews this source PR. No AWS/provider operation, IAM installation,
protected #89 change or live canary proof was performed by this milestone.
