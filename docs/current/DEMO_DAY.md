# Demo Day: OLD and NEW LAB demos

Home DEV is the normal development path. Use the retained AWS host for short Demo/UAT sessions. Keep both demo generations and their state; delete nothing.

## 30-second precheck

Open each HTTPS URL in a fresh browser tab and confirm there is no certificate warning. The canonical NEW dashboard entry is `config2`; `sec2` is its separate LibreChat/Compliance Agent surface. OLD `ops` redirects to OLD config. Existing `ops2` routing is compatibility-only and is not part of the expected journey. Have the existing private access for each generation ready. Do not put credentials in this checklist or a screen recording.

| Demo | Click sequence | Say/show | Expected result |
| --- | --- | --- | --- |
| OLD sec: <https://sec.astromedicomp.org/> | Open the URL; sign in with the existing OLD account; open **Chat History**, **Agent Builder**, and **Prompts**. | “This is the preserved reference LibreChat demo.” | **Welcome back** login, authenticated `/c/new` chat composer, and all three sidebar controls were browser-verified. Do not create a new account or submit a chat for this walkthrough. |
| OLD ops: <https://ops.astromedicomp.org/> | Open the URL using the existing OLD access method. | “The reference operator/config endpoint is protected.” | Redirect to the protected config endpoint; unauthenticated HTTP 401 is expected. No public click-through ops GUI was observed. |
| NEW config dashboard: <https://config2.astromedicomp.org/> | Authenticate with the existing NEW dashboard access; select one finding and observe its status and freshness. | “This is the isolated read-only four-environment Config view. It reports S3 Block Public Access and restricted SSH evidence.” | Protected config2 dashboard with current, non-partial evidence. No action or remediation control is available. |
| NEW Compliance Agent: <https://sec2.astromedicomp.org/login> | Sign in with the existing NEW owner account; select **AWS Ops Compliance Agent**; ask **Status**, **Explain what needs attention**, then **Give me a remediation plan without making changes**. | “The dashboard and agent use the same evidence. The agent explains and plans but cannot change AWS.” | Each answer starts with the compact **4-account × 2-control** Markdown table and status emojis. **Explain** adds only the attention table; **Plan** adds only the suggested-change table with **🚫 Not executed**. Every answer ends **🛡️ Read-only: No AWS changes executed.** |

## If NEW is transiently down

Use the NEW-only [start, health, restart, and recovery sequence](../../CONTEXT.md#dual-demo-operation). Config2 is the persistent `awsops-config2-app` service on loopback port 4313. Check its diagnostics before restarting anything. Restart only the affected NEW config2 or sec2 component; do not stop or edit OLD services.

## Two-minute final check

Reopen OLD `sec` and `ops`, then NEW `config2` and `sec2`. Confirm valid TLS, OLD `ops -> config`, expected authentication challenges on both dashboards, and both LibreChat login pages. Confirm config2 diagnostics are READY and the NEW agent has exactly one read-only tool. Existing ops2 compatibility may remain but is not a Demo Day step. Issue #11 and governed S3/SSH remediation/re-arm remain deferred and are not Demo Day capabilities. Record only sanitized pass/fail notes.
