# Migration decision — aws-secops -> awsops

Issue #1 governs this migration.

## Decision

Do **not** fork or copy the old repository. Port only accepted behavior into the new layered architecture.

Reference baseline:
- `aws-secops` release `compliance-agent-v1.0.0` at `5d4121eb7e3621d04ae2e05c3b66fdd89879b7e0`;
- roadmap work that added sanitized capability metadata, scalable findings, bounded selection, exceptions/audit, and governed `s3_ssl`;
- merged native final-decision receipt boundary from source PR #194;
- source PR #192 only as **draft/partial R&D** for live `s3_ssl`, deployment, browser, and recovery patterns.

## Migration matrix

| Area | Decision | Source signal | awsops treatment |
|---|---|---|---|
| Agent/control model | **REWRITE** | `agents/compliance-agent-v1` capability adapter is well-bounded but carries v1 routing names and old product ceilings | Keep capability-state semantics; define a smaller control registry independent of old agent packaging |
| AWS Config/live read adapters | **REWRITE** | Accepted Config evidence plus PR #192 `live_s3_ssl.py` fixed read pattern | One provider adapter per evidence family; fixed operations, bounded results, normalized output |
| Account alias/identity binding | **KEEP contract** | Four alias model and STS verification are repeatedly proven | Preserve aliases/canonical ordering and exact identity verification; never publish account IDs |
| Prepare/freeze | **KEEP contract, REWRITE code** | Existing exact batch/scope hashes and server-owned selection | New `domain` freeze contract; no dependency on old pilots |
| Native approval | **KEEP contract, REWRITE integration** | LibreChat native ASK is proven; old hook is runtime-specific | Keep one native UI mechanism; runtime adapter cannot authorize or widen scope |
| Decision receipt/audit | **KEEP core** | Source PR #194 durable-before-continuation, replay/mismatch denial, blocked Approve | Port behavior into `approval`; preserve exact binding and fail-closed semantics |
| Exception model | **KEEP contract, REWRITE code** | `exceptions_audit.py` proves deterministic owner/reason/reference/expiry + append-only evidence | Rebuild as a small domain service after base freeze path is clean |
| Execution boundary | **KEEP safety contract, REWRITE implementation** | v1 fixed CodeBuild/controller path proves bounded execution but is coupled to old runtime | Defer until M4; choose simplest durable explicit executor per control |
| Provider readback | **KEEP contract** | Release explicitly separates provider truth from Config convergence | Every future mutation requires direct readback; read-only slices also emit evidence digests |
| LibreChat integration | **REWRITE** | Source hooks/installers are version/runtime specific | Thin version-pinned runtime adapter only; domain contracts remain runtime-neutral |
| Browser E2E | **KEEP technique, REWRITE harness** | WSL -> Windows Chrome -> Windows Node -> Playwright is proven | One canonical E2E harness; disposable profile; no cookie/profile export |
| Deployment/runtime scripts | **REWRITE** | PR #192 has useful deploy/rollback learning but many old-path assumptions | Idempotent deploy/check/rollback owned by awsops; no issue-specific script sprawl |
| IaC | **SELECTIVE KEEP** | Old infra contains retained LAB/runtime resources and historical stacks | Import only resources still required by accepted architecture; no bulk copy |
| Current docs | **REWRITE** | Old CONTEXT/SPEC/ROADMAP contain stale rollout truth | Small current-only docs in awsops |
| Historical evidence/docs | **LEAVE BEHIND** | `docs/implementation`, `docs/research`, release history | Link to source when needed; do not duplicate history |
| `pilot_v1` catch-all | **LEAVE BEHIND** | Mixed server, MCP, campaign, receipt and legacy execution responsibilities | Replace with explicit packages/layers |
| Experiments/examples | **LEAVE BEHIND by default** | Historical R&D | Port only when a current milestone names a proven dependency |
| CI/tests | **REWRITE harness; KEEP acceptance ideas** | Old suite is broad and rollout-specific | Small deterministic tests per contract; one repository test command |

## Clean layout

```text
src/awsops/
  domain/      # findings, freeze, digests, common contracts
  aws/         # fixed provider reads + identity verification
  controls/    # control definitions and capability policy
  approval/    # native decision receipts / audit boundary
  execution/   # explicit bounded mutation adapters (M4+)
  runtime/     # LibreChat/MCP/deployment integration
tests/
docs/architecture/
.github/workflows/
```

## Import rules

1. Prefer behavior-level rewrite over file copy.
2. New code must depend inward toward domain contracts, not on runtime glue.
3. `runtime` may call domain/approval; domain never imports LibreChat/MCP.
4. `execution` is absent from read-only control capability until explicitly enabled.
5. Source PR #192 is not accepted truth until equivalent behavior passes in awsops.
6. No historical Issue-specific filenames in product modules.

## M1 exit criteria

- control files describe only current awsops truth;
- migration matrix exists;
- layered package skeleton exists;
- dependency-free bootstrap test passes locally/CI;
- no legacy implementation copied.
