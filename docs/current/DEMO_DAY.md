# Demo Day: Home NEW and retained OLD LAB demos

Home DEV is the active NEW demo runtime. The retained AWS host is stopped with
its EBS/EIP preserved, so the OLD and AWS-hosted NEW names are recovery/demo
paths rather than always-on endpoints. Delete nothing.

## 30-second precheck

1. Confirm local config2 health on `http://127.0.0.1:4313/api/health`.
2. Confirm the owner-private temporary HTTPS tunnel reaches Home sec2 without a
   certificate warning.
3. Have the existing private Home owner login ready. Never put credentials or
   the provider-assigned hostname in this file or a screen recording.

| Demo | Click sequence | Say/show | Expected result |
| --- | --- | --- | --- |
| Home config2 | Open local config2; select one finding and observe its status and freshness. | “This is the isolated read-only four-environment Config view. It reports S3 Block Public Access and restricted SSH evidence.” | READY, non-partial evidence for four aliases and eight checks. No action or remediation control is available. |
| Home sec2 | Open the owner-private temporary HTTPS URL; sign in with the Home owner account; select **AWS Ops Compliance Agent**; ask **Status**, **Explain what needs attention**, then **Give me a remediation plan without making changes**. | “The dashboard and agent use the same evidence. The agent explains and plans but cannot change AWS.” | Each answer starts with the compact **4-account × 2-control** Markdown table. Explain adds only the attention table; Plan adds only the suggested-change table with **🚫 Not executed**. Every answer ends exactly **🛡️ Read-only: No AWS changes executed.** |

The Playwright acceptance harness verifies persisted-tool to rendered-output
equality and archives only its test conversations. The accepted Home run has
exactly one read-only MCP tool and zero actions.

## Retained OLD/AWS demo

The retained `amit` EC2 is stopped. Its OLD `sec/ops/config` and AWS-hosted NEW
`sec2/config2` services are expected to be unavailable while stopped. Starting
that retained host is a separate approved recovery/demo action. Do not change or
delete its EBS, Elastic IP, DNS, certificates, auth or OLD state.

## If Home NEW is transiently down

Use the [Home start, health, restart and recovery sequence](../../CONTEXT.md).
Check config2 diagnostics before restarting anything. Restart only the affected
Home config2, LibreChat, MongoDB or temporary tunnel process.

## Two-minute final check

Confirm Home config2 is READY/non-partial with four aliases and eight checks.
Open the owner-private Home sec2 HTTPS URL and confirm valid TLS and normal
login. Run Status once and confirm the agent has exactly one read-only tool.
Issue #11 and governed S3/SSH remediation/re-arm remain deferred and are not
Demo Day capabilities. Record only sanitized pass/fail notes.
