import { execFile } from "node:child_process";
import { readFileSync } from "node:fs";
import { promisify } from "node:util";

const exec = promisify(execFile);
export const REGISTRY = Object.freeze(JSON.parse(readFileSync(new URL("./control-registry.json", import.meta.url), "utf8")));
export const ACCOUNT_ALIASES = Object.freeze(REGISTRY.aliases);
export const REGION = REGISTRY.region;
export const CONTROLS = Object.freeze(REGISTRY.controls.map((control) => control.id));
const STATES = new Set(["COMPLIANT", "NON_COMPLIANT", "INSUFFICIENT_DATA", "NOT_APPLICABLE"]);
const CONTROL_METADATA = new Map(REGISTRY.controls.map((control) => [control.id, control]));
const DETAIL_LIMIT = 10;
const DETAIL_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

function requiredText(name, value) {
  if (typeof value !== "string" || !value.trim()) throw Error(`${name} is required`);
  return value.trim();
}

export function parseTargets(raw = process.env.AWSOPS_CONFIG_TARGETS_JSON || "") {
  let rows;
  try {
    rows = JSON.parse(raw);
  } catch {
    throw Error("four-account runtime mapping unavailable");
  }
  if (!Array.isArray(rows) || rows.length !== ACCOUNT_ALIASES.length)
    throw Error("exactly four runtime targets are required");

  const result = new Map();
  for (const row of rows) {
    if (
      !row ||
      Object.keys(row).sort().join(",") !== "account_id,alias" ||
      !ACCOUNT_ALIASES.includes(row.alias) ||
      !/^\d{12}$/.test(row.account_id) ||
      result.has(row.alias)
    )
      throw Error("invalid four-account runtime mapping");
    result.set(row.alias, row.account_id);
  }
  if (
    result.size !== ACCOUNT_ALIASES.length ||
    ACCOUNT_ALIASES.some((alias) => !result.has(alias)) ||
    new Set(result.values()).size !== ACCOUNT_ALIASES.length
  )
    throw Error("four-account targets must be exact and distinct");
  return result;
}

export function aggregatorName(value = process.env.AWSOPS_CONFIG_AGGREGATOR_NAME || "") {
  const name = requiredText("AWSOPS_CONFIG_AGGREGATOR_NAME", value);
  if (!/^[A-Za-z0-9_-]{1,256}$/.test(name)) throw Error("invalid Config aggregator name");
  return name;
}

export async function awsJson(args) {
  const env = { ...process.env };
  for (const name of Object.keys(env))
    if (
      name.startsWith("AWS_ENDPOINT_URL") ||
      [
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_ROLE_ARN",
      ].includes(name)
    )
      delete env[name];

  Object.assign(env, {
    AWS_REGION: REGION,
    AWS_DEFAULT_REGION: REGION,
    AWS_PAGER: "",
    AWS_IGNORE_CONFIGURED_ENDPOINT_URLS: "true",
    AWS_MAX_ATTEMPTS: "2",
  });

  const { stdout } = await exec(
    "aws",
    [
      ...args,
      "--region",
      REGION,
      "--output",
      "json",
      "--no-cli-pager",
      "--cli-connect-timeout",
      "5",
      "--cli-read-timeout",
      "30",
    ],
    { env, timeout: 45000, maxBuffer: 8 * 1024 * 1024 },
  );
  const value = JSON.parse(stdout || "{}");
  if (!value || typeof value !== "object") throw Error("invalid AWS Config response");
  return value;
}

function baseRuleName(rawName) {
  if (CONTROLS.includes(rawName)) return rawName;
  for (const name of CONTROLS)
    if (rawName.startsWith(`OrgConfigRule-${name}-`)) return name;
  return null;
}

function publicRule(alias, name, status, contributor) {
  const meta = CONTROL_METADATA.get(name);
  return {
    accountAlias: alias,
    ConfigRuleName: name,
    category: meta.category,
    status,
    count:
      status === "COMPLIANT"
        ? 0
        : status === "NON_COMPLIANT" && Number.isInteger(contributor?.CappedCount)
          ? contributor.CappedCount
          : null,
    capped: status === "NON_COMPLIANT" && contributor?.CapExceeded === true,
    warning: false,
  };
}

export function createOrgAggregatorProvider({
  run = awsJson,
  targets = parseTargets(),
  aggregator = aggregatorName(),
  now = Date.now,
} = {}) {
  if (!(targets instanceof Map) || targets.size !== ACCOUNT_ALIASES.length)
    throw Error("four-account runtime mapping unavailable");

  const reverse = new Map([...targets].map(([alias, accountId]) => [accountId, alias]));
  let cache = null;

  async function load(refresh = false) {
    if (cache && now() - cache.at < (refresh ? 2000 : 30000)) return cache.value;

    const response = await run([
      "configservice",
      "describe-aggregate-compliance-by-config-rules",
      "--configuration-aggregator-name",
      aggregator,
    ]);
    const rows = response.AggregateComplianceByConfigRules;
    if (!Array.isArray(rows) || rows.length > 500)
      throw Error("unexpected aggregate compliance response");

    const byAlias = new Map(ACCOUNT_ALIASES.map((alias) => [alias, new Map()]));
    const rawNames = new Map();
    for (const row of rows) {
      const alias = reverse.get(row?.AccountId);
      const rawName = row?.ConfigRuleName;
      if (!alias || row?.AwsRegion !== REGION || typeof rawName !== "string") continue;
      const name = baseRuleName(rawName);
      if (!name) continue;
      const status = row?.Compliance?.ComplianceType;
      if (!STATES.has(status)) throw Error("unexpected aggregate compliance state");
      const account = byAlias.get(alias);
      if (account.has(name)) throw Error("duplicate account/control evidence");
      account.set(name, publicRule(alias, name, status, row?.Compliance?.ComplianceContributorCount));
      rawNames.set(`${alias}:${name}`, rawName);
    }

    const fetchedAt = new Date(now()).toISOString();
    const accounts = ACCOUNT_ALIASES.map((alias) => {
      const controlMap = byAlias.get(alias);
      const complete =
        controlMap.size === CONTROLS.length &&
        CONTROLS.every((control) => controlMap.has(control));
      return {
        alias,
        available: complete,
        fetchedAt: complete ? fetchedAt : null,
        ruleCount: complete ? CONTROLS.length : null,
        rules: complete ? CONTROLS.map((control) => controlMap.get(control)) : [],
        ...(complete ? {} : { message: "Exact two-control Config evidence is incomplete." }),
      };
    });

    const value = { fetchedAt, accounts, rawNames };
    cache = { at: now(), value };
    return value;
  }

  return {
    environments: ACCOUNT_ALIASES,
    allAccounts: true,

    async list(selection = "ALL", refresh = false) {
      if (selection !== "ALL" && !ACCOUNT_ALIASES.includes(selection))
        throw Error("Unknown account selection");

      const source = await load(refresh);
      const selected =
        selection === "ALL"
          ? source.accounts
          : source.accounts.filter((account) => account.alias === selection);
      const available = selected.filter((account) => account.available);

      return {
        environment: selection,
        region: REGION,
        available: available.length > 0,
        partial: available.length !== selected.length,
        availableAccounts: available.length,
        totalAccounts: selected.length,
        fetchedAt:
          available.length === selected.length && available.length
            ? available.map((account) => account.fetchedAt).sort()[0]
            : available.length
              ? available.map((account) => account.fetchedAt).sort()[0]
              : null,
        accounts: selected.map(({ alias, available, fetchedAt, ruleCount, message }) => ({
          alias,
          available,
          fetchedAt,
          ruleCount,
          ...(message ? { message } : {}),
        })),
        rules: available.flatMap((account) => account.rules),
        recorders: [],
      };
    },

    async details(alias, control) {
      if (!ACCOUNT_ALIASES.includes(alias) || !CONTROLS.includes(control))
        throw Error("Unknown registered account/control");
      const source = await load(false);
      const account = source.accounts.find((row) => row.alias === alias);
      const rule = account?.rules.find((row) => row.ConfigRuleName === control);
      const rawName = source.rawNames.get(`${alias}:${control}`);
      if (!account?.available || !rule || !rawName ||
          !Number.isFinite(Date.parse(account.fetchedAt)) ||
          now() - Date.parse(account.fetchedAt) > 5 * 60 * 1000 ||
          !["COMPLIANT", "NON_COMPLIANT"].includes(rule.status) ||
          !Number.isInteger(rule.count) || rule.count < 0)
        throw Error("Account/control detail evidence is unavailable");
      if (rule.status === "COMPLIANT") {
        if (rule.count !== 0) throw Error("Compliant count mismatch");
        return { alias, control, status: rule.status, affectedCount: 0,
          fetchedAt: source.fetchedAt, truncated: false, resources: [] };
      }
      const response = await run([
        "configservice", "get-aggregate-compliance-details-by-config-rule",
        "--configuration-aggregator-name", aggregator,
        "--config-rule-name", rawName,
        "--account-id", targets.get(alias),
        "--aws-region", REGION,
        "--compliance-type", "NON_COMPLIANT",
        "--max-items", String(DETAIL_LIMIT + 1),
      ]);
      const rows = response.AggregateEvaluationResults;
      if (!Array.isArray(rows) || rows.length > DETAIL_LIMIT + 1 ||
          rows.length === 0 ||
          (rule.count < rows.length && !rule.capped) ||
          (rule.count > rows.length && !response.NextToken && !rule.capped))
        throw Error("Affected-resource evidence is incomplete");
      const metadata = CONTROL_METADATA.get(control);
      const resources = rows.slice(0, DETAIL_LIMIT).map((row, index) => {
        const qualifier = row?.EvaluationResultIdentifier?.EvaluationResultQualifier;
        const evaluated = Date.parse(row?.ResultRecordedTime);
        if (row?.AccountId !== targets.get(alias) || row?.AwsRegion !== REGION ||
            row?.ComplianceType !== "NON_COMPLIANT" || qualifier?.ConfigRuleName !== rawName ||
            qualifier?.ResourceType !== metadata.resourceType ||
            typeof qualifier?.ResourceId !== "string" || !qualifier.ResourceId ||
            !Number.isFinite(evaluated) || evaluated > now() + 60000 ||
            now() - evaluated > DETAIL_MAX_AGE_MS)
          throw Error("Affected-resource evidence is stale or mismatched");
        return { reference: `resource-${String(index + 1).padStart(2, "0")}`,
          type: metadata.resourceLabel, status: "NON_COMPLIANT",
          lastEvaluatedAt: new Date(evaluated).toISOString() };
      });
      return { alias, control, status: rule.status, affectedCount: rule.count,
        fetchedAt: source.fetchedAt,
        truncated: rule.capped || rows.length > DETAIL_LIMIT || Boolean(response.NextToken) || rule.count > DETAIL_LIMIT,
        resources };
    },
  };
}
