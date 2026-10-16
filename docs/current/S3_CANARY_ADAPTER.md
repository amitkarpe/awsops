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
The public MOCK account projection is `mock-a`, matching the existing core2
receipt reader; private `CanaryBinding` remains restricted to `amit`. Non-MOCK
projection remains `amit`. The emitted scope digest binds the projected alias.
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

## Home provider source slice — awaiting Manager source review

`src/awsops/aws/boto3_s3_canary.py` and `scripts/s3_canary_operator.py` add one
fixed SDK route for a **new** `awsops-dev-issue90-s3-canary-<12 lowercase letters
or digits>` bucket. This source slice has only fake-SDK proof; it has made no AWS
call. The existing adapter now freezes an absent exact name before any creation.
Its private SQLite ledger records `create`, `tags`, `public_block`, `policy` and
`delete` intent before each call. An uncertain call is never replayed. The
provider accepts only profile `amit` in `ap-southeast-1`, compares fresh non-root
STS with the owner-private expected account, and rejects preexisting buckets.
Its reads require exact owner/Region, this ledger's acknowledged creation, exact
task tags, an empty object listing **and** empty version/delete-marker listing,
all four public-access-block flags, and no policy before the TLS-deny write.

The private binding file stays under `~/.AGENTS-temp/manager/home-migration-20261016/`;
the private receipt/operation ledger stays under `~/.AGENTS-temp/awsops/`.
The operator uses a local OS account and an interactive terminal for a human to
review/type the exact bucket and frozen digest. A digest, imported JSON or model
message is not human authentication. Only the human runs `approve` or `reject`.
`approve` prints a four-envelope canonical bundle for the existing core2 reader;
its origin remains an imported assertion there until that product independently
authenticates it. `reconcile` emits the same run without another write. The
same command reports any uncertain cleanup status separately on stderr without
replaying DeleteBucket. The schema's `-mock` sourceVersion label is retained even for real mode because v1
requires it; mode, write counts and provenance carry the actual distinction.

After Manager accepts this source and separately dispatches a concrete live
slice, the human-operated sequence is:

```sh
PY=/home/dev/.config/awsops/venv/bin/python
BUCKET=awsops-dev-issue90-s3-canary-0123456789ab  # replace suffix with one reviewed, unique private name
$PY scripts/s3_canary_operator.py prepare --bucket "$BUCKET"
BATCH_ID='replace-with-batchId-from-prepare'; SCOPE_DIGEST='replace-with-scopeDigest-from-prepare'
$PY scripts/s3_canary_operator.py approve --bucket "$BUCKET" --batch-id "$BATCH_ID" --scope-digest "$SCOPE_DIGEST"
$PY scripts/s3_canary_operator.py reconcile --bucket "$BUCKET" --batch-id "$BATCH_ID"
$PY scripts/s3_canary_operator.py cleanup --bucket "$BUCKET" --batch-id "$BATCH_ID"
```

The placeholder values above must be replaced before shell execution; private
bucket/account details do not enter a public PR or receipt. `reject` uses the same
arguments as `approve` and performs zero provider writes. The four write attempts
are CreateBucket, PutBucketTagging, PutPublicAccessBlock and PutBucketPolicy; one
later DeleteBucket is allowed only with a retained receipt and all four prior
acknowledgments. The task tags include `TTL` for the next UTC day and
`cleanup=delete`; neither tag schedules deletion automatically. No unknown
in-flight operation, changed policy, missing public block, foreign object,
version or delete marker may be deleted by this command.

The rough incremental cost assumption is one empty S3 bucket, zero stored
objects and fewer than 100 request calls for one bounded sequence: expected
well below USD0.01, subject to actual request pricing and usage. It is not a
hard cap. Before live creation, Manager must reconcile observed prior spend
across both workers against the USD100 total ceiling, reverify the private
identity, and have the human approve this exact frozen batch. Do not infer
those gates from source acceptance or fake receipts. See [AWS S3 pricing](https://aws.amazon.com/s3/pricing/)
for the live rate check.
