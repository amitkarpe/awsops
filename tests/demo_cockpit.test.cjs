const assert = require("node:assert/strict");
const { mkdtemp, writeFile, rm } = require("node:fs/promises");
const { tmpdir } = require("node:os");
const path = require("node:path");
const { test } = require("node:test");

const aliases = ["lab-dev", "lab-poc", "lab-qa", "lab-sec"];
const controls = ["s3-bucket-level-public-access-prohibited", "restricted-ssh"];

test("cockpit fails closed and exposes only bounded public fields", async () => {
  const directory = await mkdtemp(path.join(tmpdir(), "awsops-cockpit-"));
  const telemetry = path.join(directory, "harness.json");
  const previous = process.env.AWSOPS_HARNESS_TELEMETRY_FILE;
  process.env.AWSOPS_HARNESS_TELEMETRY_FILE = telemetry;
  const { createServer } = await import("../integration/config_dashboard/server.mjs");
  const provider = { list: async () => ({
    available: true, partial: false, availableAccounts: 4, totalAccounts: 4,
    fetchedAt: new Date().toISOString(),
    private_account_id: "private-marker",
    rules: aliases.flatMap((accountAlias) => controls.map((ConfigRuleName) =>
      ({ accountAlias, ConfigRuleName, status: "COMPLIANT", private_id: "private-marker" }))),
  }) };
  const server = createServer(provider);
  try {
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const url = `http://127.0.0.1:${server.address().port}/api/cockpit`;
    let body = await (await fetch(url)).json();
    assert.equal(body.status, "DEGRADED");
    assert.equal(body.harness.status, "UNAVAILABLE");
    await writeFile(telemetry, JSON.stringify({ version: 1, status: "READY", latency_ms: 123,
      checked_at: new Date().toISOString(), private_id: "private-marker" }));
    body = await (await fetch(url)).json();
    assert.equal(body.status, "READY");
    assert.equal(body.checks, 8);
    assert.equal(body.agent.toolCount, 1);
    assert.equal(body.agent.actionCount, 0);
    assert.equal(body.harness.latencyMs, 123);
    assert.equal(JSON.stringify(body).includes("private-marker"), false);
    await writeFile(telemetry, JSON.stringify({ version: 1, status: "DEGRADED", latency_ms: 123,
      checked_at: new Date().toISOString() }));
    body = await (await fetch(url)).json();
    assert.equal(body.status, "DEGRADED");
    assert.equal(body.harness.result, "FAILED");
    await writeFile(telemetry, JSON.stringify({ version: 1, status: "READY", latency_ms: 123,
      checked_at: new Date(Date.now() - 16 * 60 * 1000).toISOString() }));
    body = await (await fetch(url)).json();
    assert.equal(body.status, "DEGRADED");
    assert.equal(body.harness.status, "STALE");
  } finally {
    await new Promise((resolve) => server.close(resolve));
    if (previous === undefined) delete process.env.AWSOPS_HARNESS_TELEMETRY_FILE;
    else process.env.AWSOPS_HARNESS_TELEMETRY_FILE = previous;
    await rm(directory, { recursive: true, force: true });
  }
});
