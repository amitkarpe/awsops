# Demo Day: OLD and NEW LAB demos

Home DEV is the normal development path. Use the retained AWS host for short Demo/UAT sessions. Keep both demo generations and their state; delete nothing.

## 30-second precheck

Open each HTTPS URL in a fresh browser tab and confirm there is no certificate warning. `sec` and `sec2` should show LibreChat login; `ops2` should show the **awsops ops2** read-only status page. `ops` redirects to the protected OLD config endpoint and requires its existing access method. The OLD and NEW logins are separate; have the pre-existing private account for each at hand. Do not put credentials in this checklist or a screen recording.

| Demo | Click sequence | Say/show | Expected result |
| --- | --- | --- | --- |
| OLD sec: <https://sec.astromedicomp.org/> | Open the URL; sign in with the existing OLD account; open **Chat History**, **Agent Builder**, and **Prompts**. | “This is the preserved reference LibreChat demo.” | **Welcome back** login, authenticated `/c/new` chat composer, and all three sidebar controls were browser-verified. Do not create a new account or submit a chat for this walkthrough. |
| OLD ops: <https://ops.astromedicomp.org/> | Open the URL using the existing OLD access method. | “The reference operator/config endpoint is protected.” | Redirect to the protected config endpoint; unauthenticated HTTP 401 is expected. No public click-through ops GUI was observed. |
| NEW sec2: <https://sec2.astromedicomp.org/login> | Sign in with the existing **NEW-only** account; open **Chat History**, **Agent Builder**, **Prompts**, then **New chat** from the sidebar. | “This is the separate awsops LibreChat demo. The normal login and navigation work.” | Authenticated `/c/new` and all four sidebar controls were exercised in a real browser. Do not submit a chat, approval, or Reject canary during this walkthrough. |
| NEW ops2: <https://ops2.astromedicomp.org/> | Read the status page; click **Open sec2 login**. | “This is intentionally a read-only landing, not an operator mutation UI.” | **awsops ops2** page, then the sec2 login screen. |

## If NEW is transiently down

Use the NEW-only start/health/recovery sequence in [CONTEXT.md](../../CONTEXT.md#dual-demo-operation), which points to the accepted Issue #33 PR #35 handoff. The sec2 db, model, and app units are transient; check their status and the NEW loopback `/login` before recovery. Do not stop or edit OLD services. The ops2 page is served by Nginx without an app unit.

## Two-minute final check

Reopen all four tabs. Confirm authenticated OLD `sec` New chat, protected `ops` redirect, authenticated NEW `sec2` New chat, and `ops2` status/link. From an independent client, confirm HTTPS succeeds without certificate errors; `sec`, `sec2 /login`, and `ops2 /health` should return HTTP 200, while `ops` should redirect to its protected endpoint. The Issue #11 native Reject flow is deferred and is not a Demo Day gate. Record only sanitized pass/fail notes.
