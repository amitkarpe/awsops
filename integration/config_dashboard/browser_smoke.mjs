// Public synthetic browser evidence only. Never launch the production provider.
import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import mechanics from "../compliance_agent/browser_acceptance.cjs";
import { createServer } from "./server.mjs";
import { REGISTRY } from "./org-aggregator.mjs";

const output = fileURLToPath(new URL("../../artifacts/cloud-browser/", import.meta.url));
process.env.PLAYWRIGHT_BROWSERS_PATH ||= fileURLToPath(new URL("../../artifacts/playwright-browsers", import.meta.url));
const { chromium } = await import("playwright");
const aliases = REGISTRY.aliases;
const control = REGISTRY.controls[0];

test("config2 synthetic browser: filter, masked details, fail-closed evidence", { timeout: 90000 }, async () => {
  await mkdir(output, { recursive: true });
  // Remove only this runner's generated evidence, so a failed rerun cannot show old PASS images.
  for (const name of ["cockpit.png", "resources.png", "unavailable.png", "manifest.json"])
    await rm(`${output}/${name}`, { force: true });
  const manifest = { version: 1, mode: "SYNTHETIC_CONFIG2_ONLY", outcome: "RUNNING",
    git_head: mechanics.currentGitHead(), browser_auth_exported: false,
    storage_state_exported: false, checks: [], screenshots: [] };
  const save = () => writeFile(`${output}/manifest.json`, JSON.stringify(manifest, null, 2) + "\n");
  await save();
  let state = "complete";
  let detailFailure = false;
  let browser;
  let context;
  let outsideRequests = 0;
  let writes = 0;
  let pageErrors = 0;
  const previousTelemetry = process.env.AWSOPS_HARNESS_TELEMETRY_FILE;
  delete process.env.AWSOPS_HARNESS_TELEMETRY_FILE; // Never read owner telemetry.
  const provider = {
    async list(environment) {
      assert.ok(environment === "ALL" || aliases.includes(environment));
      if (state === "unavailable") throw Error("SYNTHETIC_UNAVAILABLE");
      const selected = environment === "ALL" ? aliases : [environment];
      const available = selected.filter(alias => state !== "partial" || alias !== "lab-qa");
      const fetchedAt = new Date().toISOString();
      return { environment, region: REGISTRY.region, available: available.length > 0,
        partial: available.length !== selected.length, availableAccounts: available.length,
        totalAccounts: selected.length, fetchedAt,
        accounts: selected.map(alias => ({ alias, available: available.includes(alias),
          fetchedAt, ruleCount: available.includes(alias) ? 2 : 0 })),
        rules: available.flatMap(accountAlias => REGISTRY.controls.map(item => ({
          accountAlias, ConfigRuleName: item.id, category: item.category,
          status: accountAlias === "lab-dev" && item.id === control.id ? "NON_COMPLIANT" : "COMPLIANT",
          count: accountAlias === "lab-dev" && item.id === control.id ? 1 : 0,
          private_id: "synthetic-hidden-marker",
        }))), recorders: [], private_id: "synthetic-hidden-marker" };
    },
    async details(alias, requestedControl) {
      assert.equal(alias, "lab-dev");
      assert.equal(requestedControl, control.id);
      if (detailFailure) throw Error("SYNTHETIC_DETAILS_UNAVAILABLE");
      const now = new Date().toISOString();
      return { alias, control: requestedControl, status: "NON_COMPLIANT", affectedCount: 1,
        fetchedAt: now, truncated: false,
        resources: [{ reference: "resource-01", type: control.resourceLabel,
          status: "NON_COMPLIANT", lastEvaluatedAt: now, private_id: "synthetic-hidden-marker" }] };
    },
  };
  // Existing HTTP boundary and production-built assets; only the provider is synthetic.
  const server = createServer(provider);
  try {
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    const base = `http://127.0.0.1:${server.address().port}`;
    browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage"],
      env: { PATH: process.env.PATH, LANG: "C.UTF-8" } });
    context = await browser.newContext({ viewport: { width: 1440, height: 1000 },
      serviceWorkers: "block", acceptDownloads: false });
    await context.route("**/*", route => {
      if (!mechanics.localRoute(route.request().url(), base)) {
        outsideRequests++;
        return route.abort();
      }
      if (!["GET", "HEAD"].includes(route.request().method())) {
        writes++;
        return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.on("pageerror", () => pageErrors++);
    const visible = (locator, code) => mechanics.requireVisible(locator, code, 15000);
    const rows = count => page.waitForFunction(n => document.querySelectorAll("tbody tr").length === n, count);
    const screenshot = async name => {
      await page.evaluate(() => {
        const stamp = document.createElement("div");
        stamp.id = "synthetic-evidence-label";
        stamp.textContent = "SYNTHETIC CLOUD TEST — NO LIVE AWS OR OWNER SESSION";
        stamp.style.cssText = "position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#172554;color:white;padding:12px;text-align:center;font:16px sans-serif";
        document.body.append(stamp);
      });
      await page.screenshot({ path: `${output}/${name}`, fullPage: true });
      await page.locator("#synthetic-evidence-label").evaluate(node => node.remove());
      manifest.screenshots.push({ file: name,
        sha256: createHash("sha256").update(await readFile(`${output}/${name}`)).digest("hex") });
    };
    await page.goto(base, { waitUntil: "domcontentloaded" });
    await visible(page.getByRole("heading", { name: "Compliance dashboard", exact: true }), "DASHBOARD_REQUIRED");
    await rows(8);
    const cockpit = page.getByRole("region", { name: "Demo cockpit" });
    await visible(cockpit.getByText("8 checks / 2 controls", { exact: true }), "EXACT_MATRIX_REQUIRED");
    await visible(cockpit.getByText("DEGRADED", { exact: true }), "NO_TELEMETRY_MUST_DEGRADE");
    await visible(cockpit.getByText("UNAVAILABLE", { exact: true }), "NO_HARNESS_REQUIRED");
    assert.ok((await cockpit.innerText()).includes("READ-ONLY / 0 actions"));
    manifest.checks.push("synthetic 4x2 rendered; absent Harness stays DEGRADED; zero actions");
    await screenshot("cockpit.png");

    await page.getByLabel("Account", { exact: true }).selectOption("lab-dev");
    await rows(2);
    await page.getByRole("button", { name: "Controls", exact: false }).first().click();
    await page.getByRole("textbox", { name: "Search controls" }).fill("restricted-ssh");
    await rows(1);
    assert.ok((await page.locator("tbody").innerText()).includes("restricted-ssh"));
    await page.getByRole("textbox", { name: "Search controls" }).fill("");
    await rows(2);
    await page.getByRole("button", { name: `View affected resources for lab-dev ${control.id}`, exact: true }).click();
    const dialog = page.getByRole("dialog");
    await visible(dialog.getByText("resource-01", { exact: true }), "MASKED_DETAIL_REQUIRED");
    assert.ok(!(await page.locator("body").innerText()).includes("synthetic-hidden-marker"));
    manifest.checks.push("account and search filters; masked resource detail rendered");
    await screenshot("resources.png");
    await page.getByRole("button", { name: "Close details", exact: true }).click();
    detailFailure = true;
    await page.getByRole("button", { name: `View affected resources for lab-dev ${control.id}`, exact: true }).click();
    await visible(dialog.getByRole("alert"), "DETAIL_FAILURE_REQUIRED");
    assert.ok((await dialog.innerText()).includes("unavailable or stale"));
    assert.equal(await dialog.getByText("resource-01", { exact: true }).count(), 0);
    await page.getByRole("button", { name: "Close details", exact: true }).click();
    manifest.checks.push("failed detail does not retain old resource evidence");

    state = "partial";
    await page.getByLabel("Account", { exact: true }).selectOption("ALL");
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await rows(6);
    await visible(page.getByRole("alert").filter({ hasText: "Partial evidence: 3 of 4" }), "PARTIAL_REQUIRED");
    assert.ok(!(await page.locator("tbody").innerText()).includes("lab-qa"));
    manifest.checks.push("partial evidence excludes missing account, with explicit warning");
    state = "unavailable";
    await page.getByRole("button", { name: "Refresh", exact: true }).click();
    await visible(page.getByRole("alert").filter({ hasText: "No successful inventory is asserted" }), "UNAVAILABLE_REQUIRED");
    await rows(0);
    await visible(page.getByText("Inventory unavailable", { exact: true }), "EMPTY_INVENTORY_REQUIRED");
    await screenshot("unavailable.png");
    manifest.checks.push("unavailable evidence removes prior inventory");
    assert.equal(outsideRequests, 0, "NO_EXTERNAL_BROWSER_REQUESTS");
    assert.equal(writes, 0, "NO_BROWSER_WRITES");
    assert.equal(pageErrors, 0, "NO_PAGE_ERRORS");
    manifest.browser_version = browser.version();
    manifest.outside_requests = outsideRequests;
    manifest.write_requests = writes;
    manifest.page_errors = pageErrors;
    manifest.outcome = "CLOUD_BROWSER_MOCK_PASS";
  } catch (error) {
    manifest.outcome = "CLOUD_BROWSER_MOCK_FAIL";
    throw error;
  } finally {
    await context?.close();
    await browser?.close();
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    if (previousTelemetry === undefined) delete process.env.AWSOPS_HARNESS_TELEMETRY_FILE;
    else process.env.AWSOPS_HARNESS_TELEMETRY_FILE = previousTelemetry;
    await save();
  }
  console.log("CLOUD_BROWSER_MOCK_PASS synthetic-only; no owner-auth or provider acceptance");
});
