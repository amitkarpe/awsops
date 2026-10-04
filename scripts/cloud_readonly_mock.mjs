import { mkdirSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { validateEvidence } from '../integration/cloud_readonly/contract.mjs';
import { syntheticInput } from '../integration/cloud_readonly/synthetic.mjs';
const root = new URL('../', import.meta.url);
const { binding, evidence, now } = syntheticInput();
const summary = validateEvidence(binding, evidence, now);
const head = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
if (!/^[a-f0-9]{40}$/.test(head)) throw Error('INVALID_CHECKOUT_HEAD');
const destination = new URL('artifacts/cloud-readonly/', root);
mkdirSync(destination, { recursive: true });
writeFileSync(new URL('mock-contract.json', destination), JSON.stringify({
  ...summary, evidenceKind: 'SYNTHETIC_ONLY', checkoutHead: head, awsCalls: 0,
}, null, 2) + '\n');
console.log('CLOUD_READONLY_MOCK_PASS cells=8 awsCalls=0 liveReadiness=NOT_VERIFIED');
