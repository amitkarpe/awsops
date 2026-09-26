import { createHash } from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const exec = promisify(execFile);
export const ACCOUNT_ALIASES = Object.freeze(["lab-dev", "lab-poc", "lab-qa", "lab-sec"]);
export const REGION = "ap-southeast-1";
export const CONTROLS = Object.freeze([
  "s3-bucket-level-public-access-prohibited",
  "restricted-ssh",
]);
const STATES = new Set(["COMPLIANT", "NON_COMPLIANT", "INSUFFICIENT_DATA", "NOT_APPLICABLE"]);
const keyFor = (...parts) =>
  createHash("sha256").update(JSON.stringify(parts)).digest("hex").slice(0, 24);

const CONTROL_METADATA = new Map([
  ["s3-bucket-level-public-access-prohibited", {
    sourceIdentifier: "S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED",
    category: "S3",
  }],
  ["restricted-ssh", {
    sourceIdentifier: "INCOMING_SSH_DISABLED",
    category: "Security Groups",
  }],
]);

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

    const value = { fetchedAt, accounts };
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
  };
}
