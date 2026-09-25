"""Offline guard tests. These do not claim a successful native login."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'integration/canary/browser.cjs'
ACCEPTANCE = ROOT / 'integration/canary/browser_acceptance.cjs'
CONTRACT = ROOT / 'integration/canary/browser_contract.cjs'


@unittest.skipUnless(shutil.which('node'), 'Node is required for browser guard contracts')
class CanaryBrowserTests(unittest.TestCase):
    def invoke(self, body):
        result = subprocess.run(['node', '-e', 'const g=require(' + json.dumps(str(SCRIPT)) + ');' + body],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def invoke_contract(self, body):
        result = subprocess.run(['node', '-e', 'const c=require(' + json.dumps(str(CONTRACT)) + ');' + body],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_same_origin_is_exact(self):
        urls = ['http://127.0.0.1:4311/api/convos', 'https://127.0.0.1:4311',
                'http://127.0.0.1:4312', 'https://example.test', 'not a URL']
        actual = self.invoke('console.log(JSON.stringify(' + json.dumps(urls) + '.map(g.localRoute)));')
        self.assertEqual(json.loads(actual), [True, False, False, False, False])

    def test_private_file_and_symlink_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / 'state.json'
            private.write_text('{"synthetic":true}')
            private.chmod(0o600)
            self.assertEqual(self.invoke('console.log(g.privateFile(' + json.dumps(str(private)) + ').synthetic);'), 'true')
            private.chmod(0o644)
            self.assertEqual(self.invoke('try {g.privateFile(' + json.dumps(str(private)) + ');process.exit(1)} catch {console.log("denied")}'), 'denied')
            private.chmod(0o600)
            link = Path(directory) / 'alias.json'
            link.symlink_to(private)
            self.assertEqual(self.invoke('try {g.privateFile(' + json.dumps(str(link)) + ');process.exit(1)} catch {console.log("denied")}'), 'denied')

    def test_no_browser_auth_export(self):
        source = SCRIPT.read_text()
        for forbidden in ['storageState(', '.cookies(', 'localStorage.getItem', 'allHeaders(', 'Authorization:']:
            self.assertNotIn(forbidden, source)
        self.assertIn("getByTestId('login-button')", source)
        self.assertIn("native_decision: 'NOT_RUN'", source)

    def test_reject_browser_uses_bound_card_single_submit_and_archive(self):
        source = ACCEPTANCE.read_text()
        self.assertIn('contract.waitForSettledSnapshot', source)
        self.assertIn('contract.assertApprovalSnapshot', source)
        self.assertIn('contract.assertSingleRejectSubmission', source)
        self.assertIn('contract.archiveRequest(conversationId)', source)
        self.assertIn('contract.assertArchived(archiveReadback,conversationId)', source)
        self.assertNotIn("api(page,'/api/convos/'+encodeURIComponent(conversationId),'DELETE')", source)
        self.assertIn('diagnostics};', source)
        self.assertIn("STALE_AGENT_CLEANUP_FAILED", source)
        self.assertIn("agentCleanup=removed.ok||removed.status===404", source)
        self.assertIn("contract.archiveRequest(conversationId)", source)
        self.assertIn("requiredPermission=2", source)
        self.assertIn("AGENT_NOT_PERSISTED", source)
        self.assertIn("getByPlaceholder('Search agents by name',{exact:true})", source)
        self.assertIn("stage='agent_search_probe'", source)
        self.assertIn("stage='agent_search_reopen'", source)
        self.assertIn("stage='agent_search_wait'", source)
        self.assertIn("stage='agent_option_wait'", source)
        self.assertIn("stage='agent_option_click'", source)
        self.assertIn("getAttribute('aria-expanded')", source)
        self.assertIn("agentSelect.press('Escape')", source)
        self.assertIn("await agentSelect.click()", source)
        self.assertIn("stage='agent_select_wait'", source)
        self.assertIn("AGENT_SELECTION_NOT_READY", source)
        self.assertIn("stage='agent_select_submit'", source)
        self.assertIn("for(let i=0;i<120;i++)", source)
        self.assertIn("selectAgent.isDisabled()", source)
        self.assertIn("stage='agent_builder_open'", source)
        self.assertIn("stage='agent_combobox_semantic_probe'", source)
        self.assertIn("stage='agent_combobox_text_fallback'", source)
        self.assertIn("hasText:'Create New Agent'", source)
        self.assertIn("AGENT_COMBOBOX_REQUIRED", source)
        self.assertIn("stage='agent_combobox_wait'", source)
        self.assertIn("stage='agent_combobox_click'", source)
        self.assertIn("timeout:30000", source)
        self.assertIn("agent_builder_navigation", source)
        self.assertIn("agent_builder_button_wait", source)
        self.assertIn("agent_builder_form_wait", source)
        self.assertIn("agent_builder_recover", source)
        self.assertIn("agent_builder_recover_wait", source)
        self.assertIn("timeout:5000", source)
        self.assertIn("timeout:10000", source)
        self.assertIn("agent_builder_current_page", source)
        self.assertIn("AGENT_BUILDER_PAGE_REQUIRED", source)
        self.assertIn("openAgentBuilder(page,value=>{stage=value},false)", source)

    def test_exact_card_tool_scope_identity_and_reject_only_controls(self):
        self.invoke_contract("""
const assert=require('node:assert/strict');
const candidate={control:'s3_ssl',account_alias:'lab-dev',resource_ref:'bucket-ref-'+'a'.repeat(20),expected_evidence_digest:'b'.repeat(64)};
const snapshot={cardCount:1,visible:true,toolCallCount:1,outputCount:1,toolCallId:'call_0123456789',
  toolText:'Completed function: decide_s3_ssl_reject_only',scopeText:JSON.stringify(candidate),
  buttons:{reject:1,approve:0,edit:0,respond:0,submit:1}};
assert.equal(c.assertApprovalSnapshot(snapshot,{toolName:'decide_s3_ssl_reject_only',candidate}),snapshot.toolCallId);
for(const bad of [
  {...snapshot,cardCount:2},
  {...snapshot,toolCallCount:0},
  {...snapshot,toolText:'Completed function: unrelated'},
  {...snapshot,scopeText:'control s3_ssl account_alias lab-poc'},
  {...snapshot,buttons:{...snapshot.buttons,approve:1}},
  {...snapshot,buttons:{...snapshot.buttons,submit:2}},
]) assert.throws(()=>c.assertApprovalSnapshot(bad,{toolName:'decide_s3_ssl_reject_only',candidate}));
""")

    def test_settled_card_wait_rejects_churn_and_accepts_stable_snapshot(self):
        self.invoke_contract("""
const assert=require('node:assert/strict');
(async()=>{
  const values=[{text:'partial'},{text:'settled'},{text:'settled'},{text:'settled'}];
  const result=await c.waitForSettledSnapshot(async()=>values.shift(),{attempts:4,stableSamples:3,pause:async()=>{}});
  assert.deepEqual(result,{text:'settled'});
  let n=0;
  await assert.rejects(c.waitForSettledSnapshot(async()=>({text:String(n++)}),
    {attempts:3,stableSamples:3,pause:async()=>{}}),/APPROVAL_CARD_NOT_SETTLED/);
})().catch(error=>{console.error(error);process.exitCode=1});
""")

    def test_duplicate_or_mismatched_resume_is_rejected(self):
        self.invoke_contract("""
const assert=require('node:assert/strict');
const expected={agentId:'agent-1',conversationId:'conversation-1',toolCallId:'call-1'};
const request={method:'POST',route:'agents_resume',status:200,body:{agent_id:'agent-1',conversationId:'conversation-1',
  endpoint:'agents',generationCreatedAt:123,actionId:'action-1',decisions:[{decision:'reject',tool_call_id:'call-1'}]}};
assert.deepEqual(c.assertSingleRejectSubmission([request],expected),{count:1,status:200});
assert.throws(()=>c.assertSingleRejectSubmission([request,request],expected),/REJECT_SUBMISSION_COUNT/);
assert.throws(()=>c.assertSingleRejectSubmission([{...request,body:{...request.body,decisions:[{decision:'approve',tool_call_id:'call-1'}]}}],expected));
assert.throws(()=>c.assertSingleRejectSubmission([{...request,body:{...request.body,conversationId:'other'}}],expected));
""")

    def test_archive_targets_exact_conversation_and_verifies_archived_state(self):
        self.invoke_contract("""
const assert=require('node:assert/strict');
const request=c.archiveRequest('conversation-1');
assert.deepEqual(request,{path:'/api/convos/archive',method:'POST',body:{arg:{conversationId:'conversation-1',isArchived:true}}});
assert.equal(c.assertArchived({status:200,json:{conversationId:'conversation-1',isArchived:true}},'conversation-1'),true);
for(const result of [
  {status:200,json:{conversationId:'other',isArchived:true}},
  {status:200,json:{conversationId:'conversation-1',isArchived:false}},
  {status:500,json:{conversationId:'conversation-1',isArchived:true}},
]) assert.throws(()=>c.assertArchived(result,'conversation-1'));
assert.throws(()=>c.archiveRequest('/api/convos/all'));
""")

    def test_failure_diagnostics_are_bounded_and_never_include_header_values_or_paths(self):
        self.invoke_contract("""
const assert=require('node:assert/strict');
const d=c.safeDiagnostic({stage:'reject_resume',method:'POST',
  url:'http://127.0.0.1:4311/api/agents/chat/resume?token=private-value',status:403,
  headerNames:['Authorization','Cookie','Content-Type','X-Private-Header']});
assert.deepEqual(d,{stage:'reject_resume',route:'agents_resume',method:'POST',status:403,
  authorization_present:true,cookie_present:true,content_type_present:true,auth_state:'rejected'});
assert(!JSON.stringify(d).includes('private-value'));
assert(!JSON.stringify(d).includes('/api/agents'));
const rows=[];for(let i=0;i<100;i++)c.recordDiagnostic(rows,d);
assert.equal(rows.length,c.MAX_DIAGNOSTICS);
""")
