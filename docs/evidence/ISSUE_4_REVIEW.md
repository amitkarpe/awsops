# Issue #4 - G implementation review

Baseline: `6c51e4ff378ff1a1639f687fe9a93ecc2a292b2d`.
Scope: M2 read/prepare/readback correctness, not live approval or remediation.

## Reproduced before changing code

The original TLS predicate blob was independently reconstructed and matched
Git blob SHA `341400677c14f5a039a0623b5a99489fbc4bf134`.
Four negative cases failed against that exact function: a narrow principal,
one S3 action, a different bucket resource, and an additional narrowing
condition. Each was incorrectly accepted as proving full transport coverage.
The replacement regression checks refuse all four and additional variants.

Code review also identified unmarked inventory truncation, a status-only digest
and caller-supplied preparation evidence. Tests now exercise their replacements:
explicit pagination/completeness, full policy fingerprints, and fresh provider
rereads before freezing a nominated candidate.

## Validation

The test suite is offline and synthetic. It verifies policy recognition,
identity/Region/owner guards, pagination boundaries, provider error handling,
privacy, fresh/changed evidence, TTL, unique scope, tamper rejection, readback
and probe opt-in behavior. See the owning PR for exact-head CI and test count.
No test output is presented as real LAB or native Reject evidence.

## Live discovery and remaining gate

G used the existing personal-LAB AWS app link for STS GetCallerIdentity and
Organizations ListAccounts. The personal controller and four registered alias
names were found. Other listed accounts were excluded. No target policy read,
AssumeRole credential export, deployment or AWS resource mutation occurred.

The app's run_script contract binds each call to a connected account link and
does not expose a target-session argument. The local execution container has
no authorized target SDK sessions. The new exact-head reader must therefore
run through the existing authorized LAB read-role runner before M2 acceptance.
Changing trust, registering accounts, exporting credentials, or substituting
controller/Config evidence would not satisfy this gate.

## Deliberately not claimed

No four-account live read/prepare/readback PASS, no native Reject PASS, no
runtime deployment, no M3 completion and no archival/cutover of aws-secops.
