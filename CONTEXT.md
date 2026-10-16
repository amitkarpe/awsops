# Current context — Defence Factory MVP

Repository: `amitkarpe/awsops`; `aws-secops` remains reference/archive only.

Updated 16 October 2026. Manager coordinates; existing repository X is sole writer
under the current #90 owner override. This task is repository-only, for M review.
AGENTS.md and SPEC.md contain the owner MVP-FIRST DEVELOPMENT POLICY.

M1/M2 source merged PR91/92; existing M4 offline approval/evidence seam and companion
MOCK GUI are reused. #86 Config read proof remains accepted; read role unchanged.
#89 fixtures remain protected. The former S3-only and three-role IAM proposals are
superseded by one reusable PowerUserAccess-based LAB role in PR93. Existing OIDC,
short fixed manual execution, identity check, Approve Once and provider readback.
No separate dispatcher or cross-account architecture for this MVP.

[Current design](docs/proposals/defence-lab-execution/README.md).
The [current owner override](https://github.com/amitkarpe/awsops/issues/90#issuecomment-6207039365)
supersedes earlier DOT-only, USD10 and repeated live-GO language. This delegated
milestone is narrower: repository-only, no AWS/provider operation, PR for M review.
No root, company/PROD access, secret exposure or destructive shortcuts.

Current source milestone: [fixed disposable S3-canary adapter](docs/current/S3_CANARY_ADAPTER.md)
uses canonical Batch/Decision/Run/Evidence and durable one-time claims, only `amit`.
Fake-provider proof distinguishes simulated writes and independent readback from
UNKNOWN Config compliance/freshness. Legacy native Approve remains blocked.
PR #94 included no live provider/SDK, AWS operation or protected #89 change.
Actual viewer, hosted release, MOCK and REAL AWS evidence stay distinct.

Home's Issue #90 source slice adds an exact SDK provider and human-operated
operator route for one new empty canary. Live approve and cleanup both fail
closed because no separately trusted canary approval binding is wired. PR95 is
merged; the follow-up handles only proven acknowledged partial creation using
fake-SDK proof. The owner-private binding is not in Git; no AWS call or resource
is part of this source milestone. See the provider section of the canary adapter
note.
