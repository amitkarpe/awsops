"""Offline canary runtime guards; no live authentication/provider claims."""
from pathlib import Path
import json, subprocess, tempfile, unittest

ROOT=Path(__file__).resolve().parents[1]

class CanaryAcceptanceContracts(unittest.TestCase):
    def node(self,code):
        p=subprocess.run(["node","-e",code],cwd=ROOT,capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_approval_hook_default_export_and_browser_never_exports_auth(self):
        hook=(ROOT/"integration/canary/approval_hook.cjs").read_text()
        browser=(ROOT/"integration/canary/browser_acceptance.cjs").read_text()
        self.assertIn(".approvalHook",hook)
        for forbidden in ["storageState(", ".cookies(", "return body.token", "console.log(auth.token)", "Authorization: body.token"]:
            self.assertNotIn(forbidden,browser)
        self.assertIn("decision!=='reject'",browser)
        self.assertIn("dispatchAttempts!==0",browser)
        self.assertIn("provider_readback:'PENDING'",browser)
        self.assertIn("pythonLink.isSymbolicLink()",browser)
        self.assertIn("(pythonTarget.mode&0o022)!==0",browser)

    def test_runtime_config_is_exact_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve(); app=root/"app"; controllers=app/"api/server/controllers/agents"
            controllers.mkdir(parents=True); (app/"node_modules/js-yaml").mkdir(parents=True)
            (app/"node_modules/js-yaml/index.js").write_text("exports.load=JSON.parse;exports.dump=x=>JSON.stringify(x);")
            manifest={"purpose":"awsops-issue11-isolated-auth-canary","root":str(root),
                      "model":"DETERMINISTIC_FIXTURE","tools":["decide_s3_ssl_reject_only_mcp_awsops"]}
            (root/"manifest.json").write_text(json.dumps(manifest)); (app/"librechat.yaml").write_text("{}")
            code=f"""const c=require('./integration/canary/runtime_config.cjs');const r={json.dumps(str(root))};
const a=c.configure(r),b=c.configure(r);const fs=require('fs'),p=require('path');
const cfg=JSON.parse(fs.readFileSync(p.join(r,'app/librechat.yaml'),'utf8'));
if(!a.configured||!b.configured)process.exit(2);
if(cfg.endpoints.agents.toolApproval.ask[0]!==c.TOOL||cfg.endpoints.agents.toolApproval.allow.length)process.exit(3);
if(cfg.mcpServers.awsops.args[1]!==r||cfg.endpoints.custom[0].baseURL!=='http://127.0.0.1:4312/v1')process.exit(4);
if(!fs.existsSync(p.join(r,'app/api/server/controllers/agents/awsops-native-gate.cjs')))process.exit(5);
"""
            self.node(code)

    def test_readback_runner_requires_rejected_bound_receipt(self):
        src=(ROOT/"integration/canary/readback.py").read_text()
        self.assertIn('EXACT_REJECT_RECEIPT_REQUIRED',src)
        self.assertIn('result.get("unchanged") is True',src)
        self.assertIn('"aws_writes":0',src)

if __name__=="__main__": unittest.main()
