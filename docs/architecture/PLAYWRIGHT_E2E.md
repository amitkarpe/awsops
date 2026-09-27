# Playwright E2E — Compliance Agent

Status: canonical browser-acceptance pattern  
Owner: Roadmap #1; proven by Issue #49 / PR #54

## Purpose

Unit/contract tests can prove parsers and prompt rules, but they cannot prove what
the owner actually sees in LibreChat. The Issue #49 screenshots exposed the key
gap: the MCP tool could return acceptable evidence while the outer agent rewrote
the final answer.

The Playwright harness therefore verifies the **whole application path**, not just
the tool call.

## Flow

```mermaid
flowchart LR
  A[Private owner-only runtime] --> B[Playwright]
  B --> C[Normal sec2 login]
  C --> D[Verify exact agent\n1 read-only tool / 0 actions]
  D --> E[Fresh prompt\nStatus / Explain / Plan]
  E --> F[/api/agents/chat admission]
  F --> G[Persisted conversation ID]
  G --> H[Persisted MCP output]
  H --> I[Persisted assistant text]
  I --> J[Settled rendered DOM]
  J --> K[Contract assertions]
  K --> L[Assistant-only screenshot]
  L --> M[Archive exact conversation]
  M --> N[Read back isArchived=true]
```

For each prompt the harness requires:

1. a fresh conversation;
2. exactly one Compliance Agent tool call;
3. persisted MCP output == persisted final assistant text;
4. rendered tables + final guardrail matching the same contract;
5. no invented aliases, controls, IDs, IPs/CIDRs, ports, policies or risk claims;
6. an owner-only screenshot + digest manifest;
7. supported **Archive** cleanup and archive readback.

## What we reused

| Source | Keep / adapt | Leave behind |
| --- | --- | --- |
| `awsops` PR #13 | normal auth, browser diagnostics, settled-state checks, exact conversation cleanup | Reject/Approve/canary workflow |
| frozen `aws-secops` PR #192 | Playwright interaction patterns, Archive cleanup, browser-failure lessons | old deployment, receipts, candidates, executor/remediation logic |
| Issue #49 / PR #54 | canonical Compliance Agent binding/assertion contract | no generic browser framework |

The rule is: **reuse proven browser mechanics, not old product coupling**.

## Critical learning

- **Browser truth has three layers.** Check persisted tool output, persisted
  assistant text, and rendered DOM. A screenshot alone is too weak.
- **Stable is not the same as complete.** A repeated `ready=false` snapshot must
  never satisfy settling; only completed snapshots can become stable.
- **Bind to server truth.** Use the conversation ID admitted by
  `/api/agents/chat*`; do not depend on URL navigation timing.
- **Verify the full agent record.** Search/list responses may omit tool details;
  read the expanded agent record before asserting one tool / zero actions.
- **UI selectors drift.** Reuse current LibreChat-supported selectors and API
  behavior, and return bounded failure codes when the UI changes.
- **Do not mutate networking to make a browser test work.** On the retained host,
  the harness may map only `sec2.astromedicomp.org -> 127.0.0.1` inside Chromium
  while keeping the public hostname/TLS contract unchanged.
- **Model formatting is not a safety boundary.** If model output drifts, the agent
  falls back to deterministic evidence rendering; Playwright verifies the final
  browser result.
- **Slow turns need readiness, not arbitrary sleeps.** Plan can take longer than
  Status; the harness waits on persisted/rendered completion within a bounded
  envelope.
- **Evidence must stay private.** Never export cookies, bearer tokens, Playwright
  storage state, raw conversation IDs or raw private findings.
- **Cleanup is Archive, not Delete.** Exact test conversations are archived and
  read back as archived.

## What Playwright proves — and does not prove

**Proves:** normal login, exact agent selection, one-tool/zero-action contract,
prompt admission, persisted tool-to-assistant binding, rendered structure,
guardrail, sanitized evidence capture and Archive cleanup.

**Does not prove:** AWS provider correctness, Config convergence, exploitability,
or any remediation result. Config2/provider readback remains the evidence source;
this browser harness is application/runtime acceptance only.

## Runner

Canonical files:

- `integration/compliance_agent/browser_acceptance.cjs`
- `integration/compliance_agent/browser_contract.cjs`
- `tests/test_compliance_agent_browser.py`

Run only from an owner-only private root:

```text
node integration/compliance_agent/browser_acceptance.cjs PRIVATE_OWNER_ONLY_ROOT
```

Operational inputs, launch/CDP modes and private-file requirements remain in
`integration/compliance_agent/README.md`.

Acceptance is `COMPLIANCE_UI_PASS` with Status / Explain / Plan all passing,
each conversation archived, `browser_auth_exported=false`,
`storage_state_exported=false`, one read-only tool and zero actions.
