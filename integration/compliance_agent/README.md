# awsops Compliance Agent — Issue #39 recovery slice

Owner: https://github.com/amitkarpe/awsops/issues/39

This package reuses the proven Compliance Agent v1 evidence-first pattern while
keeping the current migration slice strictly read-only.

Flow:

```text
sec2 LibreChat
  -> ask_compliance_agent
  -> config2 loopback API
  -> exact 4 LAB aliases x 2 controls
  -> tool-free AgentCore Harness reasoning
  -> status / explanation / no-change plan
```

The evidence adapter accepts only:

- `lab-dev`, `lab-poc`, `lab-qa`, `lab-sec`;
- `s3-bucket-level-public-access-prohibited`;
- `restricted-ssh`;
- public-safe status/count/freshness fields.

It rejects partial matrices and unexpected fields. Account IDs, resource IDs,
raw Config rule metadata, credentials and private findings are not exposed to
the model.

Runtime inputs stay private:

- `AWSOPS_CONFIG_BACKEND_URL` — defaults to `http://127.0.0.1:4313`;
- `COMPLIANCE_AGENT_V1_HARNESS_ARN` — existing approved tool-free Harness;
- `AWS_REGION` — defaults to `ap-southeast-1`.
- `AWSOPS_HARNESS_TELEMETRY_FILE` — optional existing owner-private absolute
  path shared with config2 for the M2 cockpit; the agent atomically records
  only last-call success/failure, latency, and time. Telemetry write failure
  never changes the answer or triggers another Harness call.

No remediation, re-arm, generic AWS tool or Issue #11 flow is included here.

## KISS response contract

Issue #49 keeps the reasoning/evidence contract unchanged and standardizes only
the presentation:

- one 4-account x 2-control Markdown matrix first;
- compact status emojis: ✅ compliant, 🔴 non-compliant, ⚠️ insufficient data,
  ⚪ not applicable;
- Status, Explain, and Plan are mutually exclusive response modes;
- **Explain** adds only a short attention table using aliases and aggregate counts;
- **Plan** adds only a short remediation table whose execution column is always
  `🚫 Not executed`;
- every answer ends with `🛡️ Read-only: No AWS changes executed.`;
- no repeated prose when the table already communicates the same fact.

Live compliance values are never hardcoded; every cell remains derived from the
authoritative config2 evidence packet.

## LibreChat registration contract

Use MCP server key `awsops_compliance_agent` so LibreChat exposes exactly:

`ask_compliance_agent_mcp_awsops_compliance_agent`

The MCP process is:

```text
python3 -m integration.compliance_agent.mcp_server
```

Private runtime environment must supply the existing approved Harness ARN and,
when not using the default, the config2 loopback URL. Do not place either
private value in Git.

Agent registration source:
https://github.com/amitkarpe/awsops/blob/g/issue-39-g-implementation/integration/compliance_agent/librechat-agent.json

X must validate the effective LibreChat tool name after installation before the
agent record is enabled. If the installed name differs, stop and reconcile the
server key/spec rather than widening the agent tool list.

## Authenticated browser acceptance

Architecture, flow and critical lessons are in
`docs/architecture/PLAYWRIGHT_E2E.md`.

`browser_acceptance.cjs` is the single NEW sec2 Playwright harness for the
three owner prompts. It adapts the proven normal-login, settled-render,
same-origin diagnostics and Archive mechanics from the deferred PR #13 without
carrying its Reject/candidate/receipt logic.

Harvest boundary:

- **KEEP / adapt:** owner-only input guards, normal authentication or an
  existing loopback CDP session, native Agent selection clicks, three-sample
  settled-render waits, route/method/status/header-name diagnostics, exact
  conversation binding, and supported Archive/readback.
- **LEAVE behind:** approval cards, Reject, `s3_ssl`, candidates, receipts,
  dispatch/provider readback, disposable agents, canary services and all
  executor/remediation behavior.

The runner requires an owner-only directory and uses the Playwright already
installed below its private `app/` runtime. `manifest.json` must be mode `0600`:

```json
{
  "purpose": "awsops-issue49-compliance-agent-browser",
  "base_url": "https://sec2.astromedicomp.org",
  "agent_name": "AWS Ops Compliance Agent",
  "git_head": "REVIEWED_40_HEX_GIT_HEAD",
  "browser_mode": "launch",
  "loopback_origin": true
}
```

For `launch`, private `state/login.json` supplies the existing NEW owner login. On the retained AWS demo host, set `loopback_origin: true` so Chromium resolves only `sec2.astromedicomp.org` to the local Nginx listener while preserving the public hostname/TLS contract. Leave it false/absent on normal external clients.
For Home acceptance, set `base_url` to the exact loopback HTTP origin or the exact provider-assigned `https://*.trycloudflare.com` origin and leave `loopback_origin` false. The temporary tunnel must point only to Home sec2 loopback; keep its assigned hostname and private manifest out of Git.
For an already-authenticated browser, set `browser_mode` to `cdp` and add a
loopback-only `cdp_endpoint`; the harness attaches without exporting browser
state and closes only its own page. Run from the reviewed checkout:

```text
node integration/compliance_agent/browser_acceptance.cjs PRIVATE_OWNER_ONLY_ROOT
```

The harness uses a fresh conversation for Status, Explain and no-change Plan.
For each turn it requires exactly one `ask_compliance_agent` call, binds the
persisted tool result to the persisted final assistant text, validates the
rendered tables and exact final guardrail, writes an owner-only screenshot and
sanitized evidence manifest, then archives that exact conversation and reads
back `isArchived=true`. It never calls conversation Delete and never exports
cookies, tokens or Playwright storage state.

Screenshots are limited to the final assistant message element so login fields,
account chrome and unrelated conversations are excluded. The owner-only
manifest contains only reviewed Git head, prompt, digests, structural counts,
safe console/page-error classes, screenshot SHA256, Archive result and bounded
diagnostics; raw conversation/tool IDs stay private and are stored only as
digests.

`COMPLIANCE_UI_PASS` is repository/runtime evidence for G's live review. It is
not AWS mutation evidence. `COMPLIANCE_UI_BLOCKED` reports only a bounded stage
and safe route/status/header-presence diagnostics; inspect private state before
retrying so a prior conversation is not duplicated.
