import http from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { ACCOUNT_ALIASES, CONTROLS, REGION, REGISTRY, createOrgAggregatorProvider } from "./org-aggregator.mjs";

const root = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_HOST = "config2.astromedicomp.org";
const LAB_ALIASES = ACCOUNT_ALIASES;
const TELEMETRY_MAX_AGE_MS = 15 * 60 * 1000;

function exactMatrix(snapshot) {
  const rules = Array.isArray(snapshot.rules) ? snapshot.rules : [];
  const fetchedAt = Date.parse(snapshot.fetchedAt);
  const fresh = Number.isFinite(fetchedAt) && fetchedAt <= Date.now() + 60000 &&
    Date.now() - fetchedAt <= 5 * 60 * 1000;
  const seen = new Set(rules.map((rule) => `${rule.accountAlias}:${rule.ConfigRuleName}`));
  const expected = new Set(
    LAB_ALIASES.flatMap((alias) => CONTROLS.map((control) => `${alias}:${control}`)),
  );
  return fresh && rules.length === expected.size && seen.size === expected.size &&
    [...expected].every((key) => seen.has(key)) &&
    rules.every((rule) => ["COMPLIANT", "NON_COMPLIANT"].includes(rule.status) &&
      Number.isInteger(rule.count) && rule.count >= 0 &&
      (rule.status !== "COMPLIANT" || rule.count === 0)) &&
    snapshot.available === true && snapshot.partial === false &&
    snapshot.availableAccounts === LAB_ALIASES.length && snapshot.totalAccounts === LAB_ALIASES.length;
}

async function harnessTelemetry() {
  const unavailable = { status: "UNAVAILABLE", provider: "AgentCore Harness", model: "Not reported",
    latencyMs: null, result: "NOT_REPORTED", checkedAt: null };
  const filename = process.env.AWSOPS_HARNESS_TELEMETRY_FILE;
  if (!filename || !path.isAbsolute(filename)) return unavailable;
  try {
    const record = JSON.parse(await readFile(filename, "utf8"));
    const checkedAt = Date.parse(record.checked_at);
    if (record.version !== 1 || !["READY", "DEGRADED"].includes(record.status) ||
        !Number.isInteger(record.latency_ms) || record.latency_ms < 0 || record.latency_ms > 90000 ||
        !Number.isFinite(checkedAt) || checkedAt > Date.now() + 60000)
      return unavailable;
    const fresh = Date.now() - checkedAt <= TELEMETRY_MAX_AGE_MS;
    return { status: fresh ? record.status : "STALE", provider: "AgentCore Harness",
      model: "Not reported", latencyMs: record.latency_ms,
      result: fresh ? (record.status === "READY" ? "ANSWERED" : "FAILED") : "STALE",
      checkedAt: new Date(checkedAt).toISOString() };
  } catch {
    return unavailable;
  }
}

async function agentContract() {
  try {
    const source = JSON.parse(await readFile(path.resolve(root, "../compliance_agent/librechat-agent.json"), "utf8"));
    const tools = source.tools;
    const actions = source.actions ?? [];
    if (!Array.isArray(tools) || !Array.isArray(actions)) throw Error("Invalid agent contract");
    return { valid: tools.length === 1 && tools[0] === "ask_compliance_agent_mcp_awsops_compliance_agent" &&
      actions.length === 0, toolCount: tools.length, actionCount: actions.length };
  } catch {
    return { valid: false, toolCount: null, actionCount: null };
  }
}

function safeRule(rule) {
  return {
    accountAlias: rule.accountAlias,
    ConfigRuleName: rule.ConfigRuleName,
    category: rule.category,
    status: rule.status,
    count: rule.count,
    capped: rule.capped === true,
    warning: rule.warning === true,
  };
}

function safeSnapshot(snapshot) {
  return {
    environment: snapshot.environment,
    region: snapshot.region,
    available: snapshot.available === true,
    partial: snapshot.partial === true,
    availableAccounts: snapshot.availableAccounts,
    totalAccounts: snapshot.totalAccounts,
    fetchedAt: snapshot.fetchedAt || null,
    accounts: Array.isArray(snapshot.accounts)
      ? snapshot.accounts.map((account) => ({
          alias: account.alias,
          available: account.available === true,
          fetchedAt: account.fetchedAt || null,
          ruleCount: account.ruleCount ?? null,
          ...(account.message ? { message: account.message } : {}),
        }))
      : [],
    rules: Array.isArray(snapshot.rules) ? snapshot.rules.map(safeRule) : [],
    recorders: Array.isArray(snapshot.recorders)
      ? snapshot.recorders.map((recorder) => ({
          accountAlias: recorder.accountAlias,
          recording: recorder.recording,
          lastStatus: recorder.lastStatus,
          lastStatusChangeTime: recorder.lastStatusChangeTime,
        }))
      : [],
  };
}

export function createServer(provider) {
  return http.createServer(async (req, res) => {
    const port = req.socket.localPort;
    const allowedHosts = new Set([
      `127.0.0.1:${port}`,
      `localhost:${port}`,
      PUBLIC_HOST,
    ]);
    const allowedOrigins = new Set([
      `http://127.0.0.1:${port}`,
      `http://localhost:${port}`,
      `https://${PUBLIC_HOST}`,
    ]);

    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader(
      "Content-Security-Policy",
      "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'",
    );

    const json = (status, body) => {
      res.writeHead(status, { "Content-Type": "application/json" });
      if (req.method === "HEAD") return res.end();
      res.end(JSON.stringify(body));
    };

    const host = String(req.headers.host || "").toLowerCase();
    const origin = req.headers.origin;
    if (
      !allowedHosts.has(host) ||
      (origin && !allowedOrigins.has(origin)) ||
      req.headers["sec-fetch-site"] === "cross-site"
    )
      return json(403, { error: "Approved same-origin access only" });

    if (!["GET", "HEAD"].includes(req.method || ""))
      return json(405, { error: "Read-only service: GET/HEAD only" });

    let url;
    try {
      url = new URL(req.url, `http://${host}`);
    } catch {
      return json(400, { error: "Invalid URL" });
    }

    try {
      if (url.pathname === "/api/health") {
        return json(200, {
          mode: "AWS_READ_ONLY",
          region: REGION,
          environments: LAB_ALIASES,
          allAccounts: true,
          controls: CONTROLS,
          registryVersion: REGISTRY.version,
          remediation: false,
        });
      }

      if (url.pathname === "/api/diagnostics") {
        let snapshot;
        try {
          snapshot = await provider.list("ALL", false);
        } catch {
          return json(503, {
            status: "NOT_READY",
            ready: false,
            checkedAt: new Date().toISOString(),
            components: {
              configProvider: {
                status: "NOT_READY",
                message: "Four-account Config evidence is unavailable.",
              },
            },
          });
        }
        const ready = exactMatrix(snapshot);
        return json(ready ? 200 : 503, {
          status: ready ? "READY" : "DEGRADED",
          ready,
          checkedAt: new Date().toISOString(),
          components: {
            configProvider: {
              status: ready ? "READY" : "DEGRADED",
              availableAccounts: Number(snapshot.availableAccounts) || 0,
              totalAccounts: LAB_ALIASES.length,
              aliases: LAB_ALIASES,
              fetchedAt: snapshot.fetchedAt || null,
              ...(ready
                ? {}
                : { message: "Config evidence is partial or outside the exact 4 x 2 contract." }),
            },
          },
        });
      }

      if (url.pathname === "/api/cockpit") {
        let snapshot;
        try {
          snapshot = await provider.list("ALL", false);
        } catch {
          snapshot = null;
        }
        const rules = Array.isArray(snapshot?.rules) ? snapshot.rules : [];
        const fetchedAt = Date.parse(snapshot?.fetchedAt);
        const fresh = Number.isFinite(fetchedAt) && fetchedAt <= Date.now() + 60000 &&
          Date.now() - fetchedAt <= 5 * 60 * 1000;
        const evidenceReady = snapshot && exactMatrix(snapshot) && fresh;
        const [harness, contract] = await Promise.all([harnessTelemetry(), agentContract()]);
        const agentReady = contract.valid && harness.status === "READY";
        return json(200, {
          status: evidenceReady && agentReady ? "READY" : "DEGRADED",
          aliases: LAB_ALIASES,
          controls: CONTROLS.length,
          checks: snapshot ? rules.length : null,
          evidence: { status: evidenceReady ? "READY" : "DEGRADED",
            fetchedAt: fresh ? new Date(fetchedAt).toISOString() : null },
          agent: { status: agentReady ? "AVAILABLE" : harness.status === "DEGRADED" ? "DEGRADED" : "UNVERIFIED",
            toolCount: contract.toolCount, actionCount: contract.actionCount },
          harness,
          stableRoute: { status: "NOT_REPORTED" },
          guardrail: "READ-ONLY / 0 actions",
        });
      }

      if (url.pathname === "/api/controls") {
        const environment = url.searchParams.get("environment") || "ALL";
        if (environment !== "ALL" && !LAB_ALIASES.includes(environment))
          return json(400, { error: "Unknown registered LAB alias" });
        const snapshot = await provider.list(
          environment,
          url.searchParams.get("refresh") === "1",
        );
        return json(200, safeSnapshot(snapshot));
      }

      if (url.pathname === "/api/resources") {
        if ([...url.searchParams.keys()].sort().join(",") !== "alias,control")
          return json(400, { error: "Exactly one registered alias and control are required" });
        const alias = url.searchParams.get("alias");
        const control = url.searchParams.get("control");
        if (!LAB_ALIASES.includes(alias) || !CONTROLS.includes(control))
          return json(400, { error: "Unknown registered account/control" });
        if (typeof provider.details !== "function")
          return json(503, { error: "Affected-resource evidence is unavailable" });
        const result = await provider.details(alias, control);
        const metadata = REGISTRY.controls.find((item) => item.id === control);
        if (result?.alias !== alias || result?.control !== control ||
            !["COMPLIANT", "NON_COMPLIANT"].includes(result.status) ||
            !Number.isInteger(result.affectedCount) || result.affectedCount < 0 ||
            typeof result.truncated !== "boolean" ||
            !Number.isFinite(Date.parse(result.fetchedAt)) ||
            !Array.isArray(result.resources) || result.resources.length > 10 ||
            result.resources.some((row, index) =>
              row?.reference !== `resource-${String(index + 1).padStart(2, "0")}` ||
              row?.type !== metadata.resourceLabel || row?.status !== "NON_COMPLIANT" ||
              !Number.isFinite(Date.parse(row?.lastEvaluatedAt))))
          throw Error("Affected-resource evidence is invalid");
        return json(200, {
          registryVersion: REGISTRY.version,
          alias, control, status: result.status,
          affectedCount: result.affectedCount,
          fetchedAt: result.fetchedAt,
          truncated: result.truncated,
          resources: result.resources.map((row) => ({
            reference: row.reference, type: row.type, status: row.status,
            lastEvaluatedAt: row.lastEvaluatedAt,
          })),
        });
      }

      if (url.pathname.startsWith("/api/"))
        return json(404, { error: "Read-only API route not found" });

      const relative = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
      const distRoot = path.resolve(root, "dist");
      const target = path.resolve(distRoot, relative);
      if (target !== distRoot && !target.startsWith(distRoot + path.sep))
        return json(404, { error: "Not found" });
      const data = await readFile(target);
      const mime =
        {
          ".html": "text/html",
          ".js": "text/javascript",
          ".css": "text/css",
          ".svg": "image/svg+xml",
        }[path.extname(target)] || "application/octet-stream";
      res.writeHead(200, { "Content-Type": mime });
      if (req.method === "HEAD") return res.end();
      res.end(data);
    } catch (error) {
      const status =
        error?.code === "ENOENT" && !url.pathname.startsWith("/api/") ? 404 : 502;
      return json(status, {
        error:
          status === 404
            ? "Not found"
            : "Config evidence read failed. No fallback or mutation was attempted.",
      });
    }
  });
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  if (process.argv.length !== 2) throw Error("No runtime modes are accepted");
  const port = Number(process.env.PORT || 4313);
  if (!Number.isInteger(port) || port < 1024 || port > 65535)
    throw Error("PORT must be an explicit non-privileged loopback port");
  const provider = createOrgAggregatorProvider();
  createServer(provider).listen(port, "127.0.0.1", () => {
    console.log(`awsops config2 read-only dashboard listening on 127.0.0.1:${port}`);
  });
}
