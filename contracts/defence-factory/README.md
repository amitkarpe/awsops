# Defence Factory v1 — external evidence boundary

Owning issues: [awsops #90](https://github.com/amitkarpe/awsops/issues/90) and
[agentcore2 #39](https://github.com/mytestlab123/agentcore2/issues/39).
M1 defines an inert interchange contract, not an executor, import UI or permission.
`v1.schema.json` and `synthetic-finding.json` are byte-identical in both repos.
awsops owns the canonical wire contract; agentcore2 consumes a pinned mirror.
A contract change must update both copies and their acceptance receipts together.
No frontend, provider adapter or legacy public Finding type is copied.

## Records and trust

Every envelope has exactly `schemaVersion`, `kind`, and `record`. Unknown fields
are rejected recursively. Seven discriminated kinds: Finding, Control,
TargetRegistration, Batch, Decision, Run, Evidence. The examples contain invented
aliases only. JSON Schema validates structure, not truth or permission.

- Finding: exact dataset/revision, safe resource alias, control/severity,
  compliance and independently stated observation/evaluation/freshness.
- Control: stable versioned catalog ID, fixed capability or null, and honest
  CATALOG_CANDIDATE / MOCK_SUPPORTED / LAB_READ_SUPPORTED / WRITE_GATED support.
- TargetRegistration: public projection only. Trusted private backend maps an
  approved alias to account, role and resource identity. This public record never
  registers a target or authorizes AssumeRole. Only `amit` may bind a real target
  for #90; mock-a/mock-b are synthetic. Old lab-dev/poc/qa/sec are excluded here.
- Batch: exact deduplicated targets, evidence/revision bindings, fixed action and
  expected change, registry version, mode, freeze and expiry, scope digest.
- Decision: immutable one-time choice bound to exact batch/digest/expiry and
  trusted principal-binding digest. Only the authenticated backend can originate
  a real decision. Imported JSON and browser tokens cannot grant authority.
- Run: stable identity and per-resource results; independent execution, provider
  readback, compliance and freshness, plus actual versus simulated write counts.
- Evidence: source revision/version, separately known hosted version (null when
  not observed), timestamps, provenance and explicit limitations.

All timestamps are UTC RFC3339 strings ending Z, validated with format checking.
No native IDs, names, account numbers, ARNs, secrets, free-form tags, endpoints,
credentials or raw exception bodies belong in these records. Aliases are assigned
by the trusted adapter, not copied from arbitrary source fields. A syntactically
valid alias can still contain private text: adapters MUST use controlled mappings,
not assume a regex is a privacy detector. Unknown raw rule labels are mapped to an
opaque review alias outside the executable catalog; never echo raw labels/errors.

## Mandatory semantic checks (adapters implement in subsequent milestones)

Schema validation alone is NOT an admission boundary. Before importing/displaying,
reject oversize/invalid UTF-8, duplicate JSON keys, duplicate/conflicting row IDs,
unknown fields and private data; enforce size/row limits before parsing. Decode
CSV cells as inert data; escape output for HTML/Markdown and CSV formula hazards.
Never follow imported URLs, load code, make network calls or persist authority.
An imported statement always remains IMPORTED_ASSERTION regardless of its claimed
provenance. Only an authenticated acquisition adapter may attest provider reads.

1. Resolve every target to the same dataset, control/capability and private
   registration revision. Reject missing/duplicate/extra targets and mixed modes.
   New registrations and writable capabilities remain gated, never inferred.
2. Freeze exact scope before presenting approval. Expiry must follow freeze and
   may not be extended by a decision. Decision expiry is no later than batch
   expiry; decision time must be inside the validity interval.
3. Compute SHA-256 over UTF-8 canonical JSON of the complete Batch record with
   `scopeDigest` omitted: recursively sort object keys by ASCII, no whitespace,
   no floating-point values, retain array order. Emit JSON strings with non-ASCII
   characters unescaped. Target arrays sort by accountAlias/resourceAlias/
   controlId/findingId before freezing. Reordering after freeze invalidates scope.
   Cross-language golden vectors are an M2 admission requirement.
4. Commit one terminal decision atomically before continuation. Rejection,
   unauthorized principal, stale evidence, expiry, drift, scope mismatch or replay
   yields zero provider writes and no executor dispatch. Audit recording is allowed.
5. Per-target execution checks current authority and drift before each remaining
   mutation. Reconcile uncertain acknowledgements by read-only receipt lookup;
   never generate a fresh run or replay a confirmed write. Resume the SAME run.
6. Results cover only exact frozen targets. Counts equal per-target sums. MOCK
   and LAB_READ realWrites MUST be zero. MOCK cannot emit real provider evidence;
   synthetic MATCH is explicitly simulated. UNKNOWN mode cannot execute.
7. VERIFIED requires all selected targets terminal with required provider match,
   COMPLIANT and FRESH independent evidence. Missing targets, stale evaluation,
   PARTIAL/UNKNOWN/NOT_ACQUIRED never become zero/compliant/VERIFIED. Successful
   acquisition is not successful remediation. Preserve original Config evidence.
8. Catalog candidate count (target 20–30), live discovered rules and evaluated
   resources are separate metrics. Unmeasured coverage stays UNKNOWN/null.

M1 does not implement or enable any of these execution paths. Runtime use is
blocked until the relevant adapter and its focused boundary checks are accepted.
No IAM/trust change, #89 fixture write, provider call or new resource follows from
this file. Real canary work retains every #90 identity/security/cost gate.

## Reuse decision

KEEP: agentcore2 standalone showcase frozen revisions, consumed decisions,
strict synthetic packet admission, per-target outcomes and existing journal.
KEEP: awsops domain freeze and durable native decision guarantees; existing live
Approve remains disabled. REWRITE only the shared safe projection/admission seam.
LEAVE BEHIND: promoting the legacy mock-backend's optional default-allow guard,
overwritable decisions/repeated fresh execute as a trusted backend; raw
`accountId`/resource name/tags in legacy Finding are not wire-safe exports.

Validation for M1: Draft202012Validator.check_schema; validate the synthetic
fixture with FormatChecker; reject unknown/private fields and invalid timestamps;
verify mirrors byte-for-byte; run existing focused source checks. No new test
framework or broad browser run. This contract is deliberately not wired into the
existing runtime until M2–M4 implement the required semantics.
