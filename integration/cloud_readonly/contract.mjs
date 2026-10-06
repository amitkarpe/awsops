// Offline contract only: no AWS client, credentials, process execution or network.
import { readFileSync } from 'node:fs';
const registry = JSON.parse(readFileSync(new URL('../config_dashboard/control-registry.json', import.meta.url)));
export const ALIASES = Object.freeze(registry.aliases);
export const CONTROLS = Object.freeze(registry.controls.map(c => c.id));
export const REGION = registry.region;
const fail = () => { throw new Error('READONLY_CONTRACT_REJECTED'); };
const requireThat = condition => { if (!condition) fail(); };
const keys = (value, expected) => requireThat(value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).sort().join(',') === [...expected].sort().join(','));
const matches = (value, pattern) => typeof value === 'string' && pattern.test(value);

export function validateBindings(binding) {
  keys(binding, ['region', 'collector', 'aggregator', 'targets']);
  requireThat(binding.region === REGION);
  keys(binding.collector, ['accountId', 'roleName', 'roleId', 'sessionName']);
  const c = binding.collector;
  requireThat(matches(c.accountId, /^\d{12}$/) && matches(c.roleName, /^[\w+=,.@-]{1,64}$/) &&
    matches(c.roleId, /^AROA[A-Z0-9]{17}$/) && matches(c.sessionName, /^[\w+=,.@-]{2,64}$/));
  requireThat(matches(binding.aggregator, /^[A-Za-z0-9_-]{1,256}$/));
  keys(binding.targets, ALIASES);
  const accounts = new Set();
  for (const alias of ALIASES) {
    const target = binding.targets[alias];
    keys(target, ['accountId', 'rules']);
    requireThat(matches(target.accountId, /^\d{12}$/) && !accounts.has(target.accountId));
    accounts.add(target.accountId);
    keys(target.rules, CONTROLS);
    const names = Object.values(target.rules);
    requireThat(new Set(names).size === CONTROLS.length && names.every(n => matches(n, /^[A-Za-z0-9_-]{1,128}$/)));
  }
}

// These are data, not executable commands. Future acquisition must use this exact
// bounded request plan only after the owner gate; no discovery or resource detail.
export function requestPlan(binding) {
  validateBindings(binding);
  return ALIASES.flatMap(alias => CONTROLS.map(control => ({
    alias, control, region: REGION,
    operation: 'DescribeAggregateComplianceByConfigRules',
    input: { ConfigurationAggregatorName: binding.aggregator, Limit: 2,
      Filters: { AccountId: binding.targets[alias].accountId, AwsRegion: REGION,
        ConfigRuleName: binding.targets[alias].rules[control] } },
  })));
}

export function validateEvidence(binding, evidence, now) {
  validateBindings(binding);
  keys(evidence, ['region', 'collectedAt', 'identity', 'results']);
  requireThat(evidence.region === REGION && Number.isSafeInteger(now) && Number.isSafeInteger(evidence.collectedAt) &&
    evidence.collectedAt <= now && now - evidence.collectedAt <= 300000);
  keys(evidence.identity, ['Account', 'Arn', 'UserId']);
  const c = binding.collector;
  requireThat(evidence.identity.Account === c.accountId &&
    evidence.identity.Arn === `arn:aws:sts::${c.accountId}:assumed-role/${c.roleName}/${c.sessionName}` &&
    evidence.identity.UserId === `${c.roleId}:${c.sessionName}`);
  const plan = requestPlan(binding);
  requireThat(Array.isArray(evidence.results) && evidence.results.length === plan.length);
  const seen = new Set();
  for (const result of evidence.results) {
    keys(result, ['alias', 'control', 'response']);
    const expected = plan.find(p => p.alias === result.alias && p.control === result.control);
    requireThat(expected && !seen.has(`${result.alias}:${result.control}`));
    seen.add(`${result.alias}:${result.control}`);
    // A token, error, empty page, extra account/rule or duplicate cannot pass.
    keys(result.response, ['AggregateComplianceByConfigRules']);
    const rows = result.response.AggregateComplianceByConfigRules;
    requireThat(Array.isArray(rows) && rows.length === 1);
    const row = rows[0];
    keys(row, ['AccountId', 'AwsRegion', 'ConfigRuleName', 'Compliance']);
    requireThat(row.AccountId === expected.input.Filters.AccountId && row.AwsRegion === REGION &&
      row.ConfigRuleName === expected.input.Filters.ConfigRuleName);
    keys(row.Compliance, ['ComplianceType', 'ComplianceContributorCount']);
    requireThat(['COMPLIANT', 'NON_COMPLIANT'].includes(row.Compliance.ComplianceType));
    const count = row.Compliance.ComplianceContributorCount;
    keys(count, ['CappedCount', 'CapExceeded']);
    requireThat(Number.isSafeInteger(count.CappedCount) && count.CappedCount >= 0 && count.CapExceeded === false);
  }
  // Fixed allowlist only. No private identities, findings, timestamps or hashes
  // of guessable private identifiers escape. Validation is not provenance.
  return { contractVersion: 1, status: 'OFFLINE_CONTRACT_VALID', region: REGION,
    aliases: [...ALIASES], controls: [...CONTROLS], verifiedCells: plan.length,
    liveReadiness: 'NOT_VERIFIED', evaluationFreshness: 'NOT_VERIFIED' };
}
