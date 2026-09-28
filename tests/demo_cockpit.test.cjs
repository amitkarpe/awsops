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
      ({ accountAlias, ConfigRuleName, status: "COMPLIANT", count: 0, private_id: "private-marker" }))),
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

test("affected-resource drill-down masks identifiers and rejects mismatched evidence", async () => {
  const { createOrgAggregatorProvider } = await import("../integration/config_dashboard/org-aggregator.mjs");
  const { createServer } = await import("../integration/config_dashboard/server.mjs");
  const targets = new Map(aliases.map((alias, index) => [alias, String(index + 1).repeat(12)]));
  const privateId = "private-resource-marker";
  let mismatch = false;
  let stale = false;
  const run = async (args) => {
    if (args[1] === "describe-aggregate-compliance-by-config-rules")
      return { AggregateComplianceByConfigRules: aliases.flatMap((alias) => controls.map((control) => ({
        AccountId: targets.get(alias), AwsRegion: "ap-southeast-1", ConfigRuleName: control,
        Compliance: { ComplianceType: "NON_COMPLIANT",
          ComplianceContributorCount: { CappedCount: 1, CapExceeded: false } },
      }))) };
    assert.equal(args[1], "get-aggregate-compliance-details-by-config-rule");
    assert.equal(args.at(-2), "--max-items");
    assert.equal(args.at(-1), "11");
    return { AggregateEvaluationResults: [{
      AccountId: mismatch ? "999999999999" : targets.get("lab-dev"),
      AwsRegion: "ap-southeast-1", ComplianceType: "NON_COMPLIANT",
      ResultRecordedTime: new Date(Date.now() - (stale ? 31 * 24 * 60 * 60 * 1000 : 0)).toISOString(),
      EvaluationResultIdentifier: { EvaluationResultQualifier: {
        ConfigRuleName: controls[0], ResourceType: "AWS::S3::Bucket", ResourceId: privateId,
      } },
    }] };
  };
  const server = createServer(createOrgAggregatorProvider({ run, targets, aggregator: "test" }));
  try {
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const url = `http://127.0.0.1:${server.address().port}/api/resources?alias=lab-dev&control=${controls[0]}`;
    const response = await fetch(url);
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.resources[0].reference, "resource-01");
    assert.equal(body.resources[0].type, "S3 bucket");
    assert.equal(JSON.stringify(body).includes(privateId), false);
    assert.equal(JSON.stringify(body).includes(targets.get("lab-dev")), false);
    mismatch = true;
    assert.equal((await fetch(url)).status, 502);
    mismatch = false;
    stale = true;
    assert.equal((await fetch(url)).status, 502);
    assert.equal((await fetch(url + "&account_id=anything")).status, 400);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
