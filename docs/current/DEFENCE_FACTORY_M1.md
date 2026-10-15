# Issue90 M1 — current state and shared vertical contract

Updated 2026-10-15. Implementer: dot, native tools. The owner's updated #90
supersedes Direct/X recovery dependencies. Inspect-only UNKNOWN requests are not
writers. No Direct, X, Factory, AO or AWS operation is part of this change.

## Evidence truth table

| Boundary | Established evidence | Not established / next gate |
|---|---|---|
| Source baseline | main 3179ca23c5c47e5c2620e9ffa0e9a580595de4a2, PR87/88 merged | New M1 source is inert contract work |
| OIDC + Config | [run 38113762515](https://github.com/amitkarpe/awsops/actions/runs/38113762515), [#86 acceptance](https://github.com/amitkarpe/awsops/issues/86#issuecomment-6105704562) | No repeated acquisition; freshness NOT_VERIFIED |
| Scope | personal alias amit, Singapore; exact four Config reads | No cross-account trust or writable provider authority |
| Findings | Four NON_COMPLIANT rule instances, two controls, three resources in prior readback | Not 20–30 live controls; not fresh comprehensive account posture |
| Retained fixtures | [#89 proposal](https://github.com/amitkarpe/awsops/issues/89) | NOT AUTHORIZED TO APPLY; protect SG-1/SG-2/BUCKET-1 |
| GUI | agentcore2 merged v1.9 source; last verified private publication v1.7 | Hosted E2E and real viewer pending; no frontend fork |
| Open PR | Deferred #13 isolated native canary | No changes to its files or runtime; not resumed |

## M1 deliverable

[Strict v1 schema and semantics](../../contracts/defence-factory/README.md) define
Finding, Control, TargetRegistration, Batch, Decision, Run and Evidence. A single
synthetic S3 transport finding anchors the operator journey. Separate immutable
scope, server authority, provider match and compliance freshness are mandatory.
Schema shape is implemented; adapter/runtime admission is intentionally M2–M4.
Public alias projection is separate from the owner-private target binding.

The canonical existing runtime/runbook remains
[DEV_COMPUTE_MODEL](../architecture/DEV_COMPUTE_MODEL.md); this work does not
activate a Home route or replace OIDC. #62/#77 are parent context, not authority
to reuse legacy aliases or expand #90's one-personal-LAB scope.

## Next

M2 adds bounded synthetic CSV/JSON admission and candidate catalog using this
contract. M3 fresh identity/read proof remains separate from offline checks.
M4's exact disposable canary must independently satisfy identity, effective IAM,
resource, rollback and cost gates; no trust/permission widening is implied.
No AWS calls, credentials, new resources or recurring infrastructure cost in M1.
