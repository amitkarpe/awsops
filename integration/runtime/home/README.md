# Home NEW demo rebuild

This is the KISS rebuild path for the read-only NEW `config2` + `sec2` demo.
It starts from Git plus one pinned LibreChat upstream commit. It never copies the
retained EC2 `.env`, MongoDB, certificates, browser state or filesystem tree.


## Canonical lifecycle

Use one KISS flow from the `awsops` checkout. Keep all private values under the
existing owner-only configuration boundary.

1. **Start:** follow sections 4-6 to start MongoDB, config2 and LibreChat on
   loopback. Start the optional public route only for a remote demo.
2. **Status:** confirm `http://127.0.0.1:4313/api/health` and
   `http://127.0.0.1:4311/api/config` return HTTP 200.
3. **Validate:** run:

   ```bash
   python scripts/home_demo.py validate
   ```

   The command performs read-only loopback GETs and validates the repo-owned
   agent/MCP contract plus the latest private canonical browser evidence. It
   fails closed unless config2 is READY/non-partial with four aliases, eight
   checks and two controls, and sec2 has one read-only tool, zero actions and
   the three archived canonical prompt results.
4. **Stop:** stop the optional public route first, stop the foreground/local config2
   and LibreChat processes, then stop only Home MongoDB:

   ```bash
   docker compose -f integration/runtime/home/docker-compose.yaml down
   ```

This lifecycle never starts the retained EC2 and never changes AWS, IAM, DNS,
networking or authentication architecture.

## 1. Prerequisites

Supported baseline: Ubuntu 24.04 x86-64.

Required locally:

- Git;
- Python 3.12+;
- Node.js 24+ and npm;
- Docker with Compose support;
- an existing approved AWS SSO/profile when live Config/Harness reads are needed.

Check without changing anything:

```bash
python scripts/home_demo.py check
```

## 2. Prepare the pinned LibreChat source

From the `awsops` checkout:

```bash
python scripts/home_demo.py prepare ~/awsops-home-demo
python scripts/home_demo.py verify ~/awsops-home-demo
```

The script clones only the source pin recorded in
`integration/runtime/librechat-runtime.json`. It refuses an existing non-empty
LibreChat target and never copies EC2 files.

## 3. Private owner inputs

Keep private values outside the public repository, for example under
`~/.config/awsops/` with owner-only permissions.

Use these committed schemas only as checklists:

- `integration/runtime/env/config2.env.example`;
- `integration/runtime/env/config2-agent.env.example`;
- `integration/runtime/home/home-demo.env.example`.

For LibreChat, copy the pinned upstream `.env.example` to the **local pinned
LibreChat clone** as `.env`, then set local secrets there. Do not copy the EC2
`.env` and do not commit the local file.

## 4. Start isolated MongoDB

```bash
docker compose -f integration/runtime/home/docker-compose.yaml up -d mongodb
```

Only `127.0.0.1:27111` is exposed. The named volume is local Home DEV state and
is not source truth.

## 5. Build and start config2 locally

```bash
cd integration/config_dashboard
npm ci
npm run build
npm run prepare:runtime
set -a
. ~/.config/awsops/config2.env
set +a
npm start
```

Health check:

```bash
curl -fsS http://127.0.0.1:4313/api/health
```

Live `/api/diagnostics` and `/api/controls` require the existing approved AWS
Config read path and exact private bindings; local startup itself creates no AWS
resources and performs no mutation.

The Issue #65 cockpit is on the same config2 root page. To show last-call
AgentCore status, set the same `AWSOPS_HARNESS_TELEMETRY_FILE` absolute path in
the private config2 and Compliance Agent environments. Create its parent as an
owner-private directory before starting either process. The MCP process writes
only a mode-0600 bounded result/time/latency record after its existing Harness
call; config2 reads it. A missing, failed, or stale record visibly degrades the
cockpit and does not affect Status/Explain/Plan answers. The stable route says
`NOT_REPORTED` until M1 has a separately verified integration.

## 6. Prepare LibreChat + Compliance Agent

In a second shell:

```bash
cd ~/awsops-home-demo/librechat
cp /absolute/path/to/awsops/integration/runtime/home/librechat.yaml.example librechat.yaml
cp .env.example .env
# Fill only local/private values in .env and export the values from
# ~/.config/awsops/home-demo.env before starting.
npm ci
npm run frontend
PATH="$(dirname "$AWSOPS_HOME_PYTHON"):$PATH" npm run backend
```

The venv directory must be first on `PATH` because LibreChat does not expand environment variables in an MCP stdio `command` field. The repo-owned YAML therefore uses `python3` and exposes exactly one MCP server key:
`awsops_compliance_agent`. It runs
`python -m integration.compliance_agent.mcp_server` from the Home `awsops`
checkout and points it at local config2.

The canonical agent definition remains
`integration/compliance_agent/librechat-agent.json`. Register it through the
normal authenticated LibreChat owner/admin path; do not copy the EC2 database or
browser session to reproduce an agent record.

## 7. Browser acceptance

After normal local login, use the same three prompts:

1. `Status`
2. `Explain what needs attention`
3. `Give me a remediation plan without making changes`

The repository Playwright contract remains
`integration/compliance_agent/browser_acceptance.cjs`. A local/browser pass is
application acceptance; AWS provider correctness remains a separate readback.

## 8. Reset

Stop only Home DEV processes:

```bash
docker compose -f integration/runtime/home/docker-compose.yaml down
```

To rebuild LibreChat, preserve anything you intentionally need, then choose a new
empty Home target and rerun `home_demo.py prepare`. Git remains source truth.

## One stable public route (Roadmap v2 M1 / Issue #63)

The first choice, an owner-controlled stable Cloudflare tunnel, has no local
Cloudflare origin certificate, tunnel token or named-tunnel configuration on
Home. Tailscale is installed and authenticated and supplies a stable Home
`*.ts.net` name. Funnel is the selected second choice. **Activation is pending
the owner's tailnet Funnel enablement**; the CLI currently refuses with
`Funnel is not enabled on your tailnet.` No public route was created by that
attempt. Ngrok has no local auth configuration and is not a fallback here.

From the exact Home `awsops` release checkout, after the local lifecycle above
is healthy and current-head browser acceptance has passed:

```bash
python scripts/home_demo.py public-start
python scripts/home_demo.py public-status
python scripts/home_demo.py public-stop
```

`public-start` runs the canonical read-only `validate` contract before it
enables Funnel. It refuses any pre-existing unrelated Tailscale Serve/Funnel
route and exposes only Home sec2 at `127.0.0.1:4311` through HTTPS port 443.
Home requires existing noninteractive `sudo` permission for the exact Funnel
route change; the script does not change Tailscale operator settings.
`public-status` reads back the exact route and local sec2 health. `public-stop`
turns off only that exact route; config2, sec2, MongoDB and Home-local URLs keep
running. If status reports unhealthy, stop the public route and recover the
local services before starting it again. The stable URL is printed locally by
the commands; keep owner-private tunnel details outside Git. No router
forwarding, Route53 change, wildcard DNS or retained EC2 is involved.

If `validate` reports stale or unbound browser evidence after a release change,
rerun the existing canonical browser acceptance from that exact release head;
do not bypass or weaken the validator. A prior Cloudflare quick tunnel remains
an optional temporary transport and is not the stable M1 route.
