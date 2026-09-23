# M2 — read-only s3_ssl vertical slice

## Flow

```text
private account bindings
      ↓
exact alias + STS identity verification
      ↓
fixed S3 ListBuckets / GetBucketPolicy reads
      ↓
alias-only normalized findings + digests
      ↓
prepare one exact current NON_COMPLIANT finding
      ↓
deterministic batch_id + scope_hash
      ↓
fresh provider readback
```

## Boundaries

- aliases are fixed: `lab-dev`, `lab-poc`, `lab-qa`, `lab-sec`;
- Region is fixed to `ap-southeast-1`;
- account IDs are private runtime input and are never emitted;
- at most 20 sorted buckets per account trigger policy reads;
- raw bucket names are hashed to resource references before output;
- the AWS adapter exposes only identity, ListBuckets, and GetBucketPolicy reads;
- `s3_ssl` has DETECT / EXPLAIN / PREPARE / VERIFY capability and no REMEDIATE capability;
- freeze output has `live_execution_authorized=false`;
- no legacy S3 BPA/SSH executor is imported.

## Readback semantics

A readback is **unchanged** only when the exact frozen resource remains in the same provider state with the same finding evidence digest.

An unavailable/missing resource is not success.

M2 performs no AWS mutation.
