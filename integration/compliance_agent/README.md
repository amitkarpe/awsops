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

No remediation, re-arm, generic AWS tool or Issue #11 flow is included here.

The MCP surface intentionally returns **only the final Markdown string** to
LibreChat. The richer evidence envelope remains inside the Python agent for
tests and internal validation, but it is no longer exposed to the outer
LibreChat model. This reduces the opportunity for a second model pass to invent
or reinterpret evidence. The authenticated browser acceptance below still
fails closed if LibreChat rewrites even that final string.

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


## Authenticated browser acceptance — Issue #49

The canonical browser harness is:

`integration/compliance_agent/browser_acceptance.cjs`

It selectively reuses the proven browser mechanics from current `awsops` PR
#13 and frozen `aws-secops` PR #192: normal LibreChat login, same-origin
request observation, settled-turn sampling, exact tool-call binding, persisted
message readback and supported Archive cleanup. Reject/Approve/canary/executor
logic is deliberately not reused.

The harness runs three fresh conversations:

1. `Status`
2. `Explain what needs attention`
3. `Give me a remediation plan without making changes`

For each conversation it requires exactly one `ask_compliance_agent` tool
call, extracts that tool's final Markdown, reads the persisted assistant
message from `/api/messages/<conversation>`, and requires an exact normalized
match. Any outer-agent rewrite is a failure.

It additionally fails on:

- missing or extra LAB aliases/controls;
- mixed Status / Explain / Plan layouts;
- quoted/blockquoted/trailing guardrail text;
- invented account IDs, ARNs, resource IDs, IPs/CIDRs, port 22, bastion,
  sensitive-data, public-internet or exploitability claims;
- any answer that does not end exactly with
  `🛡️ **Read-only:** No AWS changes executed.`

Runtime inputs stay private. The harness expects an owner-only root directory
containing `state/login.json` (mode 0600), plus
`AWSOPS_PLAYWRIGHT_MODULE` pointing at an existing approved Playwright
installation. It never exports cookies, bearer tokens or browser storage state.
Screenshots and JSON manifests are written only under the private
`evidence/` directory and must not be committed.

Every exact test conversation is Archived and read back as
`isArchived=true`; the harness never Deletes conversations.
