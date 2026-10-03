# Cloud browser parity — #77 M2

Delivery: [draft PR #79](https://github.com/amitkarpe/awsops/pull/79).
Scope: public/synthetic config2 only. Owner-authenticated sec2 and AWS provider
acceptance are unchanged. This is a browser test, not a deployment or live proof.

## Classification

| Existing path | Classification | What it proves |
| --- | --- | --- |
| `tests/test_compliance_agent_browser.py`, `browser_contract.cjs` | Cloud-safe offline contract | Rendered-answer rules using synthetic inputs; no browser/login |
| `tests/demo_cockpit.test.cjs` | Cloud-safe service fixture | HTTP projection/masking with synthetic providers; no browser |
| `integration/config_dashboard/browser_smoke.mjs` (M2) | Cloud-safe built UI + service fixture | Real Chromium, built React assets and existing HTTP server with injected synthetic provider |
| `integration/compliance_agent/browser_acceptance.cjs` | Owner-auth/private runtime | Normal login, persisted tool/assistant/DOM binding and exact Archive cleanup; not run by cloud verification |
| `home_demo.py validate`, public route lifecycle | Home/private integration | Exact-head owner evidence and actual services/route; remains explicitly skipped |
| Deferred #11/#13 Reject journey | Separate deferred private/provider scope | Not activated or copied into this test |

M2 reuses the existing Playwright library, `localRoute` same-origin guard,
`requireVisible` readiness helper and `currentGitHead` evidence binding. Only
these existing helpers are exported from the private runner; its CLI, login,
private-file checks and acceptance logic are unchanged. No second browser
framework, private session import, CDP attach or auth/storage export is added.
The new test covers previously untested real dashboard interaction rather than
duplicating the HTTP assertions alone.

## Journey and boundaries

The fixture calls `createServer(provider)` directly; it never constructs the AWS
provider or starts the production CLI. The server binds `127.0.0.1` on an OS-picked
port. All provider values are in-memory synthetic aliases/control data; inherited
Harness telemetry is temporarily unset, so no private telemetry file is read.

One bounded headless journey exercises:

1. Eight rendered checks across four aliases/two controls; missing Harness keeps
   cockpit DEGRADED and the read-only/zero-actions guardrail visible.
2. Account selection and control search, then a masked affected-resource dialog.
3. Failed resource read: old detail must disappear and an unavailable alert render.
4. Partial evidence: missing account is excluded, with a visible warning.
5. Unavailable evidence: prior inventory disappears and no successful inventory
   is asserted.

The fresh non-persistent Chromium context blocks service workers/downloads and
all browser requests outside the exact fixture origin or using non-read methods.
Unexpected attempts/page errors fail the journey. Browser child environment is
restricted to PATH/LANG; no private login/profile/session is loaded. No external
Compliance Agent link is clicked. Context, browser and fixture server close in
`finally`. The local provider contains no SDK/CLI/network call.

## Run and evidence

Use the same cloud/CI command:

```bash
npm_config_cache=/tmp/awsops-npm python scripts/cloud_verify.py --bootstrap
```

Bootstrap installs exact `playwright@1.63.0` and its pinned Chromium headless
shell via the official Playwright installer. Browser cache defaults to ignored
`artifacts/playwright-browsers`; override `PLAYWRIGHT_BROWSERS_PATH` if needed.
Linux Chromium shared-library dependencies must already exist. If absent, install
the documented Playwright system prerequisites in the approved cloud/CI image;
there is no Home fallback. Public npm/GitHub/Playwright CDN downloads are needed.
See [official browser setup](https://playwright.dev/docs/browsers).

After dependencies, browser and build exist, a focused run is:

```bash
cd integration/config_dashboard
npm run test:browser
```

Without `--bootstrap`, canonical verification still requires the browser journey;
missing Chromium fails rather than skipping or falling back to HTTP-only proof.
If build fails, the browser step is explicitly skipped while the overall command
remains failed. Audit, lint and all existing M1 checks remain required.

Only these generated public-safe files are uploaded by CI for seven days:
`artifacts/cloud-browser/manifest.json`, `cockpit.png`, `resources.png`,
`unavailable.png`. Screenshots carry a synthetic/no-live-AWS watermark. Manifest
records Git head, synthetic mode, outcome, completed checks and screenshot SHA256
hashes; PASS includes browser version and zero unexpected-request/error counts.
No traces, HAR, cookies, storage state, private findings or owner images are
written/uploaded. A rerun removes only these owned generated files before writing
RUNNING; failure records FAIL, so old PASS evidence cannot satisfy a fresh run.
Do not interpret `CLOUD_BROWSER_MOCK_PASS` as `COMPLIANCE_UI_PASS` or AWS truth.

## Execution evidence

Base: `0e96b6c94f35e413130b33cba07a0b13eeaee652` (merged PR #78), verified against
remote main on 2026-10-03. Reused the approved cloud environment; preserved clean
older worktrees and created `/workspace/awsops-browser-parity` from current main.
No competing M2 PR was open. AGENTS/CONTEXT/SPEC/ROADMAP matched the previously
read M1 tree; #77 M2 supplies scope and acceptance. No additional repo skill was
needed. Draft PR body will bind the final head and exact CI/artifact evidence.

- Clean baseline `cloud_verify.py --bootstrap`: PASS before M2 changes.
- Initial browser install: FAIL, unwritable `/home/agent/.cache/ms-playwright`.
  Corrected by a repo-owned ignored writable browser cache.
- Official Chromium download in this cloud workspace: BLOCKED, HTTP 403
  `Domain forbidden` for `cdn.playwright.dev`. No proxy/CDN workaround used.
- Browser test without installed Chromium: FAIL as intended, with a failure
  manifest. This is an environment blocker, not a passed cloud browser journey.
- Full cloud command: FAIL with exactly two failures (Chromium installation and
  browser launch). All other checks PASS: audit reports zero vulnerabilities,
  161 Python tests, HTTP cockpit, lint, pack validation, source preparation,
  TypeScript/Vite build and runtime permissions. No failing step was hidden.
- First [CI run 37116249518](https://github.com/amitkarpe/awsops/actions/runs/37116249518):
  browser downloaded/launched; rendered 4x2 cockpit passed, then the account
  selector timed out. Corrected the test to match its combobox accessible name;
  no application change. Failure manifest remained FAIL with only the completed
  synthetic cockpit screenshot.
- Corrected implementation head: `7ad7ee6bf1208d582f6031f35cd614cad890f206`.
  [CI run 37116344309](https://github.com/amitkarpe/awsops/actions/runs/37116344309):
  **SUCCESS**, all canonical checks including Chromium installation and the full
  synthetic browser journey PASS. Journey took 1.8 seconds, Chromium
  `153.0.8010.12`; the audit reported zero vulnerabilities.
- Downloaded and inspected [artifact 11271890982](https://github.com/amitkarpe/awsops/actions/runs/37116344309/artifacts/11271890982):
  exactly one manifest and three labeled PNGs; all screenshot hashes verified.
  Manifest outcome `CLOUD_BROWSER_MOCK_PASS`, five completed check groups, zero
  external/write requests/page errors, auth/storage export both false. Visually
  reviewed dashboard, masked-resource dialog and unavailable-inventory evidence.
  The manifest binds actual checked-out PR merge SHA
  `fb12270096800e0a0914d2678604a0d21b01be47`, while the run metadata binds the
  implementation branch head above. This is GitHub's validation merge ref, not
  a merge into main.
- Final documentation-inclusive head, CI result and artifact link are in PR #79's
  body. Cloud-workspace bootstrap is still blocked by the official download
  restriction despite the proven GitHub-hosted browser PASS. Do not claim full
  acceptance in that workspace until its approved network/image setup supplies
  the pinned browser. Do not route around its access policy or use Home.

No AWS calls/mutation, IAM/OIDC, Home/office, private secret access, public exposure,
Tailscale/DNS/TLS, deployment or merge. Remaining owner/private and provider paths
retain their original boundaries. M3 identity work is outside this PR.

HANDOFF: DOT
