import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { requestPlan, validateEvidence } from '../integration/cloud_readonly/contract.mjs';
import { syntheticInput } from '../integration/cloud_readonly/synthetic.mjs';
const row = e => e.results[0].response.AggregateComplianceByConfigRules[0];
test('bounded eight-cell plan and public summary never claim AWS readiness', () => {
  const { binding, evidence, now } = syntheticInput();
  const plan = requestPlan(binding);
  assert.equal(plan.length, 8);
  assert.ok(plan.every(p => p.region === 'ap-southeast-1' && p.operation === 'DescribeAggregateComplianceByConfigRules' && p.input.Limit === 2 && !('NextToken' in p.input)));
  const output = validateEvidence(binding, evidence, now);
  assert.deepEqual(output, { contractVersion: 1, status: 'OFFLINE_CONTRACT_VALID', region: 'ap-southeast-1',
    aliases: ['lab-dev','lab-poc','lab-qa','lab-sec'], controls: ['s3-bucket-level-public-access-prohibited','restricted-ssh'],
    verifiedCells: 8, liveReadiness: 'NOT_VERIFIED', evaluationFreshness: 'NOT_VERIFIED' });
  assert.doesNotMatch(JSON.stringify(output), /arn:|\d{12}|synthetic-session|NON_COMPLIANT|OrgConfigRule/);
  row(evidence).Compliance.ComplianceType = 'COMPLIANT';
  assert.deepEqual(validateEvidence(binding, evidence, now), output);
});
test('identity, alias, Region and rule drift fail closed with a fixed error', () => {
  const cases = [
    b => { b.region = 'us-east-1'; },
    b => { delete b.targets['lab-sec']; },
    b => { b.targets.prod = b.targets['lab-dev']; },
    b => { b.targets['lab-qa'].accountId = b.targets['lab-dev'].accountId; },
    b => { b.collector.accountId = '<OWNER_ACCOUNT>'; },
    b => { b.collector.roleId = 'unknown'; },
    b => { b.collector.roleName = '*'; },
    b => { b.targets['lab-dev'].rules['restricted-ssh'] = b.targets['lab-dev'].rules['s3-bucket-level-public-access-prohibited']; },
  ];
  for (const mutate of cases) { const { binding, evidence, now } = syntheticInput(); mutate(binding);
    assert.throws(() => validateEvidence(binding, evidence, now), /^Error: READONLY_CONTRACT_REJECTED$/); }
  for (const mutate of [
    e => { e.identity.Account = '9'.repeat(12); },
    e => { e.identity.Arn += '-different-role'; },
    e => { e.identity.UserId = 'recreated-role'; },
    e => { e.region = 'us-east-1'; },
    e => { row(e).AwsRegion = 'us-east-1'; },
    e => { row(e).AccountId = '9'.repeat(12); },
    e => { row(e).ConfigRuleName += '-rebound'; },
  ]) { const { binding, evidence, now } = syntheticInput(); mutate(evidence);
    assert.throws(() => validateEvidence(binding, evidence, now), /^Error: READONLY_CONTRACT_REJECTED$/); }
});
test('partial, stale, future, unknown, malformed and paginated evidence cannot pass', () => {
  for (const mutate of [
    e => { e.results.pop(); }, e => { e.results[1] = e.results[0]; },
    e => { e.results[0].alias = 'prod'; },
    e => { e.results[0].response.NextToken = 'private-token'; },
    e => { e.results[0].response.Error = 'private-error'; },
    e => { e.results[0].response.AggregateComplianceByConfigRules = []; },
    e => { e.results[0].response.AggregateComplianceByConfigRules.push(row(e)); },
    e => { e.collectedAt -= 300001; }, e => { e.collectedAt += 1; },
    e => { e.collectedAt = true; },
    e => { row(e).Compliance.ComplianceType = 'INSUFFICIENT_DATA'; },
    e => { row(e).Compliance.ComplianceContributorCount.CapExceeded = true; },
    e => { row(e).Compliance.ComplianceContributorCount.CappedCount = true; },
    e => { row(e).Compliance.ComplianceContributorCount.CappedCount = -1; },
    e => { row(e).Compliance.ComplianceContributorCount.CappedCount = 0.5; },
    e => { e.identity.private = 'do-not-publish'; },
    e => { e.results = null; }, e => { e.identity = null; },
  ]) { const { binding, evidence, now } = syntheticInput(); mutate(evidence);
    assert.throws(() => validateEvidence(binding, evidence, now), /^Error: READONLY_CONTRACT_REJECTED$/); }
});
test('placeholder owner bindings are intentionally unusable', () => {
  const binding = JSON.parse(readFileSync(new URL('../integration/cloud_readonly/bindings.example.json', import.meta.url)));
  assert.throws(() => requestPlan(binding), /READONLY_CONTRACT_REJECTED/);
});
test('proposed identity policy has one read action; trust has exact repository environment and audience', () => {
  const read = name => JSON.parse(readFileSync(new URL(`../integration/cloud_readonly/${name}.proposed.json`, import.meta.url)));
  assert.deepEqual(read('permissions').Statement, [{ Effect: 'Allow', Action: 'config:DescribeAggregateComplianceByConfigRules',
    Resource: 'arn:aws:config:ap-southeast-1:<COLLECTOR_ACCOUNT>:config-aggregator/<AGGREGATOR_ID>',
    Condition: { StringEquals: { 'aws:RequestedRegion': 'ap-southeast-1' } } }]);
  const trust = read('trust').Statement;
  assert.equal(trust.length, 1);
  assert.equal(trust[0].Action, 'sts:AssumeRoleWithWebIdentity');
  assert.deepEqual(trust[0].Condition, { StringEquals: {
    'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
    'token.actions.githubusercontent.com:sub': 'repo:amitkarpe/awsops:environment:awsops-lab-readonly',
  } });
  assert.equal(trust[0].Principal.Federated, 'arn:aws:iam::<COLLECTOR_ACCOUNT>:oidc-provider/token.actions.githubusercontent.com');
});
