import http from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createOrgAggregatorProvider } from "./org-aggregator.mjs";

const root = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_HOST = "config2.astromedicomp.org";
const LAB_ALIASES = Object.freeze(["lab-dev", "lab-poc", "lab-qa", "lab-sec"]);
const CONTROLS = Object.freeze([
  "s3-bucket-level-public-access-prohibited",
  "restricted-ssh",
]);

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
          region: "ap-southeast-1",
          environments: LAB_ALIASES,
          allAccounts: true,
          controls: CONTROLS,
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
        const rules = Array.isArray(snapshot.rules) ? snapshot.rules : [];
        const seen = new Set(rules.map((rule) => `${rule.accountAlias}:${rule.ConfigRuleName}`));
        const expected = new Set(
          LAB_ALIASES.flatMap((alias) => CONTROLS.map((control) => `${alias}:${control}`)),
        );
        const exactMatrix =
          seen.size === expected.size &&
          [...expected].every((key) => seen.has(key)) &&
          snapshot.available === true &&
          snapshot.partial === false &&
          snapshot.availableAccounts === 4 &&
          snapshot.totalAccounts === 4;
        return json(exactMatrix ? 200 : 503, {
          status: exactMatrix ? "READY" : "DEGRADED",
          ready: exactMatrix,
          checkedAt: new Date().toISOString(),
          components: {
            configProvider: {
              status: exactMatrix ? "READY" : "DEGRADED",
              availableAccounts: Number(snapshot.availableAccounts) || 0,
              totalAccounts: 4,
              aliases: LAB_ALIASES,
              fetchedAt: snapshot.fetchedAt || null,
              ...(exactMatrix
                ? {}
                : { message: "Config evidence is partial or outside the exact 4 x 2 contract." }),
            },
          },
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
