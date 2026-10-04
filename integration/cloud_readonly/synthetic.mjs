// Public invented inputs; never load private bindings or AWS configuration.
import { ALIASES, CONTROLS, REGION, requestPlan } from './contract.mjs';
export function syntheticInput() {
  const now = 1801612800000;
  const binding = { region: REGION, aggregator: 'synthetic-only', collector: {
    accountId: '0'.repeat(12), roleName: 'synthetic-readonly',
    roleId: `AROA${'A'.repeat(17)}`, sessionName: 'synthetic-session',
  }, targets: Object.fromEntries(ALIASES.map((alias, i) => [alias, {
    accountId: String(i + 1).padStart(12, '0'),
    rules: Object.fromEntries(CONTROLS.map(control => [control, `OrgConfigRule-${control}-synthetic`])),
  }])) };
  const c = binding.collector;
  const evidence = { region: REGION, collectedAt: now,
    identity: { Account: c.accountId,
      Arn: `arn:aws:sts::${c.accountId}:assumed-role/${c.roleName}/${c.sessionName}`,
      UserId: `${c.roleId}:${c.sessionName}` },
    results: requestPlan(binding).map(p => ({ alias: p.alias, control: p.control,
      response: { AggregateComplianceByConfigRules: [{ ...p.input.Filters,
        Compliance: { ComplianceType: 'NON_COMPLIANT', ComplianceContributorCount: { CappedCount: 1, CapExceeded: false } },
      }] } })),
  };
  return { binding, evidence, now };
}
