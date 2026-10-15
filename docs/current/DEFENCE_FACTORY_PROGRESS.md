# Issue90 — native M2/M4 source and live gates

Dot is the sole native implementer. M1 merged in PR91; controller inspection
UNKNOWN requests are superseded by owner override, not live writers. #13 remains
deferred; #89 retained fixtures remain prohibited targets.

## Source outcomes

- Shared `contracts/defence-factory/intake.cjs`: bounded 256 KiB/500-row strict
  UTF-8 synthetic CSV/JSON intake. Duplicate keys/rows, prototype fields, invalid
  dates/columns, private identifier/credential shapes fail with a generic error.
  Output is safe alias projection; imported provenance cannot become attested.
- 24 catalog candidates; live coverage UNKNOWN. Unknown controls map to a
  non-executable review category. Only mock-a/mock-b are accepted for import;
  a real target cannot be registered via a file.
- `node contracts/defence-factory/import.cjs json < synthetic-input.json` produces
  normalized output only. No network, provider client, models or storage.
- `plan.cjs` freezes exact one-control synthetic targets, revisions, fixed action,
  deterministic SHA-256 scope, UTC expiry and source digests. REJECT is zero
  dispatch. APPROVE_ONCE stays APPROVE_BLOCKED: imported/offline data is never a
  trusted human principal or live authorization. Replay cannot dispatch either.
- The companion UI reuses its existing executor for MOCK group decisions and
  per-resource evidence. It is not a second AWS executor.

Focused boundary checks are justified by a new untrusted-input/digest boundary;
no framework/dependency introduced. Run `node contracts/defence-factory/intake-check.cjs`.
Existing successful OIDC/Config proof remains run38113762515; no repeat to inflate
coverage. Offline tests cannot replace fresh private identity or provider proof.

## M3 and M4 live gates

A real target registration must be issued by trusted private configuration for
alias amit, Singapore, exact role/resource binding, never from this input file.
There is no accepted additional-account registration or cross-account permission.
No Organizations discovery/provisioning or IAM/trust expansion is implemented.

A future AWS-owned execution adapter must accept only a durable authenticated
batch-bound decision and immutable scope, persist request/receipt before calls,
read back exact provider state, and reconcile uncertain acknowledgements without
replay. The current seam deliberately has no apply function. Add it only after
exact effective narrow credentials, disposable target/ownership, rollback/cleanup
and cost gates are proven. #89's existing demo resources are excluded.

Live target/effective-role results are recorded in the owning issue, not invented
here. Root/other connected identity cannot substitute for the approved narrow
execution role. A missing role binding blocks that live step only; offline source
and MOCK progress continue.

## Cost, cleanup and acceptance limits

This source work creates zero AWS resources and $0 recurring infrastructure.
Read API cost, if any, is not assumed free. No canary exists to clean up. Existing
resources and evidence are retained. No real provider write, Config convergence,
new-account readiness or real-viewer acceptance is claimed. M5 handoff must retain
these gaps rather than close the issue as fully live-complete.

Historical M3 attempt, 2026-10-15: connection reauthentication initially blocked
STS before execution. The later owning-Issue checkpoint6192833060 supersedes that
transient blocker: access inspection completed privately and read-only. No fresh
Config acquisition or remediation occurred. The current gate is an approved
narrow execution binding. See the [review-only role proposal](../proposals/defence-lab-execution/README.md).
No proposed IAM, trust, Environment, document or canary is installed by that packet.
