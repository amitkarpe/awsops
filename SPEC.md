# Specification

Status: **ACTIVE — migration bootstrap**

## Goal

Build a small AWS security-operations agent platform that moves from evidence to governed action without giving the model broad AWS mutation authority.

## Architecture

```text
AWS evidence/read adapters
        ↓
normalized findings + control registry
        ↓
prepare + exact freeze
        ↓
native human decision
        ↓
decision receipt + audit
        ↓
bounded executor capability
        ↓
provider readback + verification
```

Modules stay separate:
- `domain` — normalized contracts and frozen scope;
- `aws` — fixed provider reads and identity verification;
- `controls` — per-control definitions/capabilities;
- `approval` — human-decision and durable receipt boundary;
- `execution` — explicit bounded mutation adapters only;
- `runtime` — product/runtime integration, never domain authority.

## Security invariants

- Model output is not authorization.
- No generic model-accessible AWS API/mutation tool.
- Exact account/resource/action scope is server-owned and frozen before approval.
- Reject never dispatches remediation.
- Provider readback is execution truth; asynchronous security/compliance systems are separate evidence.
- Uncertain mutation is not success and must not be blindly retried.
- Public Git state contains aliases/digests only, not private identifiers or auth material.

## Migration scope

M1 is repository-only.

M2 introduces one fixed **read-only** personal-LAB `s3_ssl` vertical slice.

M3 adds native Reject-only approval and durable decision evidence for `s3_ssl`; live remediation remains disabled.

M4 may selectively add the two previously proven bounded LAB mutation controls after separate acceptance.

Company/office/PROD is outside current scope.
