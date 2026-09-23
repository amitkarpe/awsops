# Roadmap

Owning roadmap: Issue #1.

## M1 — migration inventory + clean contract — ACTIVE

- clean repository control files;
- KEEP / REWRITE / LEAVE BEHIND matrix;
- layered source layout;
- one dependency-free test command and CI skeleton;
- no legacy implementation copied.

## M2 — read-only s3_ssl vertical slice — NEXT

`LAB identity -> fixed S3 TLS evidence read -> normalized finding -> exact prepare/freeze -> provider readback`

No AWS mutation.

## M3 — native Reject-only decision

`prepare/freeze -> native decision -> durable REJECTED receipt -> zero dispatch -> unchanged readback`

Approve remains structurally blocked for `s3_ssl`.

## M4 — selective bounded remediation migration

Evaluate only:
1. S3 Block Public Access on retained demo scope;
2. restricted SSH on retained unattached demo Security Groups.

Port contracts and safety guards; rewrite coupled executor plumbing when simpler.

## M5 — parity + cutover

- capability parity matrix;
- deployment/runbook;
- deferred list;
- explicit cutover;
- preserve `aws-secops` as reference/archive.

## Permanent boundaries

- no generic model AWS mutation;
- no silent scope widening;
- no company/PROD rollout;
- no destructive source-repo cleanup;
- no third live remediation control before explicit roadmap authority.
