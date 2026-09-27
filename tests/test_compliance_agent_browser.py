"""Focused Issue #49 browser/output-binding regression tests."""

from pathlib import Path
import json
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "integration" / "compliance_agent" / "browser_contract.cjs"
BROWSER = ROOT / "integration" / "compliance_agent" / "browser_acceptance.cjs"
MCP = ROOT / "integration" / "compliance_agent" / "mcp_server.py"


def matrix():
    return """| Account | 🪣 S3 BPA | 🔐 Restricted SSH |
| --- | --- | --- |
| lab-dev | 🔴 NON_COMPLIANT (2) | 🔴 NON_COMPLIANT (1) |
| lab-poc | 🔴 NON_COMPLIANT (3) | 🔴 NON_COMPLIANT (1) |
| lab-qa | ✅ COMPLIANT | 🔴 NON_COMPLIANT (1) |
| lab-sec | ✅ COMPLIANT | ✅ COMPLIANT |"""


STATUS = matrix() + """

6 of 8 checks need attention.

🛡️ **Read-only:** No AWS changes executed."""

EXPLAIN = matrix() + """

| Needs attention | Why | Affected |
| --- | --- | --- |
| S3 BPA | Bucket-level Block Public Access is not in the compliant configuration. | 5 |
| Restricted SSH | Unrestricted SSH ingress is present. | 3 |

🛡️ **Read-only:** No AWS changes executed."""

PLAN = matrix() + """

| Priority | Control | Suggested change | Execution |
| --- | --- | --- | --- |
| P1 | S3 BPA | Bring bucket-level Block Public Access into the compliant configuration. | 🚫 Not executed |
| P2 | Restricted SSH | Remove unrestricted SSH ingress and use an approved source if access is required. | 🚫 Not executed |

🛡️ **Read-only:** No AWS changes executed."""


@unittest.skipUnless(shutil.which("node"), "Node is required for browser contracts")
class ComplianceAgentBrowserContractTests(unittest.TestCase):
    def node(self, body):
        script = "const c=require(" + json.dumps(str(CONTRACT)) + ");" + body
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_status_explain_plan_contracts_are_mutually_exclusive(self):
        payload = json.dumps({"status": STATUS, "explain": EXPLAIN, "plan": PLAN})
        out = self.node(
            "const a=" + payload + ";"
            "for(const [mode,text] of Object.entries(a)) c.assertAnswerContract(mode,text);"
            "console.log('PASS');"
        )
        self.assertEqual(out, "PASS")

    def test_tool_output_must_equal_persisted_assistant_message(self):
        tool = "Output\n" + EXPLAIN
        history = [
            {"isCreatedByUser": True, "text": "Explain what needs attention"},
            {"isCreatedByUser": False, "unfinished": False, "text": EXPLAIN},
        ]
        out = self.node(
            "const r=c.assertToolToAssistantBinding('explain',"
            + json.dumps(tool)
            + ","
            + json.dumps(history)
            + ");console.log(r.digest.length);"
        )
        self.assertEqual(out, "64")

        rewritten = history[:-1] + [{
            "isCreatedByUser": False,
            "unfinished": False,
            "text": EXPLAIN.replace(
                "🛡️ **Read-only:** No AWS changes executed.",
                "Use a bastion with a trusted CIDR.\n\n🛡️ **Read-only:** No AWS changes executed.",
            ),
        }]
        out = self.node(
            "try{c.assertToolToAssistantBinding('explain',"
            + json.dumps(tool)
            + ","
            + json.dumps(rewritten)
            + ");process.exit(2)}catch(e){console.log(e.message)}"
        )
        self.assertEqual(out, "OUTER_AGENT_REWRITE")

    def test_invented_network_and_risk_details_fail_closed(self):
        bad = EXPLAIN.replace(
            "🛡️ **Read-only:** No AWS changes executed.",
            "Restrict 0.0.0.0/0 on port 22 because sensitive data may be exposed.\n\n"
            "🛡️ **Read-only:** No AWS changes executed.",
        )
        out = self.node(
            "try{c.assertAnswerContract('explain',"
            + json.dumps(bad)
            + ");process.exit(2)}catch(e){console.log(e.message)}"
        )
        self.assertEqual(out, "INVENTED_DETAIL")

    def test_guardrail_must_be_plain_exact_and_last(self):
        quoted = STATUS.replace(
            "🛡️ **Read-only:** No AWS changes executed.",
            '"🛡️ **Read-only:** No AWS changes executed."',
        )
        out = self.node(
            "try{c.assertAnswerContract('status',"
            + json.dumps(quoted)
            + ");process.exit(2)}catch(e){console.log(e.message)}"
        )
        self.assertIn(out, {"GUARDRAIL_EXACT", "GUARDRAIL_QUOTED"})

    def test_archive_is_exact_and_read_back(self):
        out = self.node(
            "const r=c.archiveRequest('conversation-1');"
            "if(r.path!=='/api/convos/archive'||r.method!=='POST'||"
            "r.body.arg.conversationId!=='conversation-1'||r.body.arg.isArchived!==true)process.exit(2);"
            "c.assertArchived({status:200,json:{conversationId:'conversation-1',isArchived:true}},'conversation-1');"
            "console.log('PASS');"
        )
        self.assertEqual(out, "PASS")

    def test_browser_reuses_safe_patterns_and_never_exports_auth(self):
        source = BROWSER.read_text()
        self.assertIn("waitForSettledSnapshot", source)
        self.assertIn("/api/messages/", source)
        self.assertIn("archiveConversation", source)
        self.assertIn("assertToolToAssistantBinding", source)
        contract_source = CONTRACT.read_text()
        self.assertIn("/api/convos/archive", contract_source)
        self.assertIn("page.screenshot", source)
        self.assertNotIn("storageState(", source)
        self.assertNotIn(".cookies(", source)
        self.assertNotIn("localStorage", source)
        self.assertNotIn("sessionStorage", source)
        self.assertNotIn("method: 'DELETE'", source)
        self.assertNotIn("method='DELETE'", source)

    def test_mcp_exposes_only_final_markdown_string(self):
        source = MCP.read_text()
        self.assertIn('def ask_compliance_agent(request: str) -> str:', source)
        self.assertIn('return answer(request)["answer"]', source)


if __name__ == "__main__":
    unittest.main()
