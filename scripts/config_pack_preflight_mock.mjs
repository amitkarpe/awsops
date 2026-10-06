import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { preflight } from '../integration/config_dashboard/conformance-pack/preflight.mjs';
import { syntheticPreflight } from '../integration/config_dashboard/conformance-pack/preflight.synthetic.mjs';
const root = new URL('../', import.meta.url);
const head = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
const f = syntheticPreflight(head);
const summary = preflight(f.expected, f.plan, f.approval, f.facts, f.now);
const destination = new URL('artifacts/config-pack-preflight/', root);
mkdirSync(destination, { recursive: true });
writeFileSync(new URL('mock-preflight.json', destination), JSON.stringify({
  ...summary, checkoutHead: head, templateSha256: f.plan.source.templateSha256,
}, null, 2) + '\n');
console.log('CONFIG_PACK_MOCK_PASS synthetic-only executionAllowed=false awsCalls=0');
