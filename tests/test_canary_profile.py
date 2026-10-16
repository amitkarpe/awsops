"""Source compatibility and deterministic transport guards; not browser acceptance."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[1]


class CanaryProfileTests(unittest.TestCase):
    def node(self, code):
        result = subprocess.run(['node', '-e', code], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_exact_source_render_and_guard_order(self):
        fixture = ROOT / 'artifacts/canary-upstream'
        if not (fixture / 'client.js').exists():
            if os.environ.get('AWSOPS_REQUIRE_NATIVE_FIXTURE') == '1':
                self.fail('canary fixture required')
            self.skipTest('canary fixture not fetched')
        self.node("""const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const p=require('./integration/canary/source_profile.cjs');
for(const [component,name] of [['resume','resume.js'],['pause','client.js']]) {
 const raw=fs.readFileSync('artifacts/canary-upstream/'+name);const result=p.render(raw,component).toString();
 new vm.Script(result);assert.throws(()=>p.render(Buffer.concat([raw,Buffer.from(' ')]),component));
 assert.throws(()=>p.render(Buffer.from(result),component));
 if(component==='resume') {
  assert(result.indexOf('.prepareNativeRequest(')>result.indexOf('const mapped = resolveResumeValue'));
  assert(result.indexOf('.persistNativeDecision(')>result.indexOf('if (!claimed)'));
  assert(result.indexOf('.persistNativeDecision(')<result.indexOf('// ACK immediately;'));
  assert(result.includes('AWSOPS_MANUAL_CANARY_ONLY'));
 } else {
  const start=result.indexOf('  async handleRunInterrupt('), stop=result.indexOf('  async chatCompletion(',start);
  const method=result.slice(start,stop);assert(method.indexOf('.beforePause(')<method.indexOf('this.stagedApproval ='));
  assert(method.indexOf('this.stagedApproval =')<method.indexOf('this.publishStagedApproval()'));
 }
}
""")

    def test_model_only_nominates_candidate_or_reports_tool_return(self):
        self.node("""const assert=require('assert/strict'),f=require('./integration/canary/fixture_model.cjs');
const c={control:'s3_ssl',account_alias:'lab-dev',resource_ref:'bucket-ref-'+'a'.repeat(20),expected_evidence_digest:'b'.repeat(64)};
const body={model:'awsops-canary-fixed',messages:[],tools:[{function:{name:f.TOOL}}]};
const r=f.responseFor(body,c);assert.equal(r.tool_calls[0].function.name,f.TOOL);assert.deepEqual(JSON.parse(r.tool_calls[0].function.arguments),c);
assert(!f.responseFor({...body,messages:[{role:'tool',content:'Rejected'}]},c).tool_calls);
assert.throws(()=>f.responseFor({...body,tools:[]},c));assert.throws(()=>f.responseFor({...body,model:'other'},c));
""")

    def test_mcp_dispatch_always_fails_and_is_counted(self):
        self.node("""const assert=require('assert/strict'),f=require('./integration/canary/mcp_guard.cjs');let count=0;
const list=f.answer({method:'tools/list'},()=>count++);assert.equal(list.tools.length,1);assert.equal(list.tools[0].name,f.TOOL);
assert.equal(count,0);assert.equal(f.answer({method:'tools/call'},()=>count++).isError,true);assert.equal(count,1);
assert.equal(f.answer({method:'unknown'},()=>count++),null);
""")
