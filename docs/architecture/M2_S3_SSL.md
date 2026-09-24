# M2 evidence and preparation contract

## What is implemented

`verified fixed-role reads -> complete bounded inventory -> policy evidence ->
fresh exact prepare -> expiring scope -> fresh provider readback`

The operator provides four distinct private alias/account bindings plus the
expected controller identity and a local SDK profile. Neither accounts nor
credentials are accepted from a model. All four target sessions verify STS
account and fixed read-role identity before S3 reads. BucketRegion is checked
on every inventory row; GetBucketPolicy includes ExpectedBucketOwner.

ListBuckets is paginated with MaxBuckets=20 and BucketRegion=ap-southeast-1.
At most five pages and twenty bucket policies per account are processed.
Continuation cycles, duplicate rows, limits, malformed responses and missing
Regions are explicit incomplete states. An empty complete inventory is valid.
No unpaginated compatibility fallback exists for older SDKs.

## Conservative evaluator, not a general IAM engine

COMPLIANT requires conventional Deny statements covering both the exact bucket
and every object, all principals, all S3 actions, and only the
aws:SecureTransport=false Boolean condition. Separate bucket/object deny
statements may jointly provide that coverage. Wildcard resource/action forms
and the AWS="*" principal form are recognized.

An absent policy or empty statement set is NON_COMPLIANT for this contract.
Other unproven forms are UNKNOWN, including additional conditions such as an
AWS-service-principal exemption, narrow actions/principals, wrong resources,
negated policy elements and malformed documents. They require later reviewed
support; this reader does not pretend to reproduce the AWS Config evaluator.
A separate complete qualifying deny can still prove the requirement.

Read errors are UNAVAILABLE. Only the structured NoSuchBucketPolicy service
error means absent policy; exception text is never interpreted as that result.

## Evidence and fresh preparation

Each digest includes canonical provider-policy JSON, private account-binding
digest, alias/resource reference, Region, status and evaluator version. Public
results expose none of the raw provider policy, account ID or bucket name.
Formatting/key order is normalized. Array ordering/other policy edits are
conservatively treated as changes; this is not general IAM semantic equivalence.
Timestamps are separate, so merely rereading does not alter a policy digest.

The UI nominates a resource reference and expected evidence digest. Prepare
accepts no caller report; it performs a fresh provider read, rejects partial
or unverified fleet coverage, and compares the exact candidate digest. Only
known NON_COMPLIANT evidence no older than sixty seconds can be frozen.
Every preparation has a new UUID, scope digest and at most five-minute TTL.
There are at most 128 pending in-process preparations. They confer no execution
permission, and process restart requires fresh preparation.

Readback only accepts a known unedited unexpired preparation. A same-status
policy edit, a changed identity binding, UNKNOWN, missing resource or partial
provider read cannot be reported as unchanged.

## Opt-in runtime probe

Entry point: `awsops.runtime.read_probe`. It requires a private local config,
an explicit registered alias and `--confirm-lab-read-only`. Config has exactly
`region`, `source_account_id`, `profile`, and `accounts` (alias/account_id pairs).
Keep it outside Git, for example under `.private/`. An existing SDK runner must
support the paginated ListBuckets parameters; missing support fails closed.

The probe uses only the existing fixed read role. It returns sanitized evidence
for read -> first exact NON_COMPLIANT candidate in the selected alias -> fresh
prepare -> readback. It exits nonzero on partial/no-candidate/changed/unavailable
results. It never resets a bucket to make a test pass. Provider/config errors
are suppressed from public output. No UI login, native Reject, deployment or
AWS mutation is performed. A PASS here is M2 read-path proof, not M3 proof.

The `aws_writes=0` report field describes this reader's absent mutation path;
it is not a CloudTrail certificate or proof about other actors in an account.
The test suite instruments read calls. Live acceptance must record the actual
runner revision, verified target identities (sanitized), calls and readback.

## Primary references

- AWS Config rule meaning: https://docs.aws.amazon.com/config/latest/developerguide/s3-bucket-ssl-requests-only.html
- AWS S3 HTTPS-only example and Principal/Action/Resource coverage: https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-bucket-policies.html
- ListBuckets pagination and Region filtering: https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListBuckets.html
- GetBucketPolicy expected-owner guard: https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetBucketPolicy.html
- AWS-service-principal exemption (currently UNKNOWN here): https://docs.aws.amazon.com/AmazonS3/latest/userguide/amazon-s3-policy-keys.html
