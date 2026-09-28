"""Focused offline guards for the Issue #49 browser output binding."""
from pathlib import Path
import json
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "integration/compliance_agent/browser_contract.cjs"
RUNNER = ROOT / "integration/compliance_agent/browser_acceptance.cjs"


class ComplianceAgentBrowserContractTests(unittest.TestCase):
    def node(self, body):
        script = "const c=require(" + json.dumps(str(CONTRACT)) + ");" + body
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    @staticmethod
    def evidence():
        aliases = ["lab-dev", "lab-poc", "lab-qa", "lab-sec"]
        controls = ["s3-bucket-level-public-access-prohibited", "restricted-ssh"]
        checks = []
        for index, alias in enumerate(aliases):
            checks.append({"account_alias": alias, "control": controls[0],
                           "status": "NON_COMPLIANT" if index == 0 else "COMPLIANT",
                           "affected_resources": 3 if index == 0 else 0})
            checks.append({"account_alias": alias, "control": controls[1],
                           "status": "NON_COMPLIANT" if index == 1 else "COMPLIANT",
                           "affected_resources": 2 if index == 1 else 0})
        return {"source": "awsops config2", "fetched_at": "2026-09-27T00:00:00Z",
                "aliases": aliases, "controls": controls, "checks": checks,
                "identifiers_available": False}

    def matrix(self):
        return """| Account | 🪣 S3 BPA | 🔐 Restricted SSH |
| --- | --- | --- |
| lab-dev | 🔴 NON_COMPLIANT (3 affected) | ✅ COMPLIANT |
| lab-poc | ✅ COMPLIANT | 🔴 NON_COMPLIANT (2 affected) |
| lab-qa | ✅ COMPLIANT | ✅ COMPLIANT |
| lab-sec | ✅ COMPLIANT | ✅ COMPLIANT |"""

    @staticmethod
    def rendered(answer):
        lines = answer.splitlines()
        tables = []
        index = 0
        while index < len(lines):
            if lines[index].startswith("|") and index + 1 < len(lines) and lines[index + 1].startswith("| ---"):
                cells = lambda line: [cell.strip() for cell in line.strip()[1:-1].split("|")]
                table = [cells(lines[index])]
                index += 2
                while index < len(lines) and lines[index].startswith("|"):
                    table.append(cells(lines[index])); index += 1
                tables.append(table)
            else:
                index += 1
        return {"guardrailCount": 1, "trailingText": "",
                "guardrailText": "🛡️ Read-only: No AWS changes executed.", "tables": tables}

    def assert_mode(self, mode, answer):
        tool = {"answer": answer, "mutation": False, "evidence": self.evidence()}
        body = "const t=" + json.dumps(tool) + ";const r=" + json.dumps(self.rendered(answer)) + ";" \
               + "console.log(c.assertAnswer(" + json.dumps(mode) + ",t,r).mode);"
        self.assertEqual(self.node(body), mode)

    def test_status_exact_matrix_and_guardrail(self):
        answer = self.matrix() + "\n\n2 of 8 checks need attention.\n\n" \
                 + "🛡️ **Read-only:** No AWS changes executed."
        self.assert_mode("status", answer)

    def test_explain_is_matrix_plus_evidence_backed_attention_only(self):
        answer = self.matrix() + """

| Needs attention | Why | Affected |
| --- | --- | --- |
| lab-dev — S3 BPA | bucket-level Block Public Access is not in the compliant configuration. | 3 |
| lab-poc — Restricted SSH | unrestricted SSH ingress is present. | 2 |

🛡️ **Read-only:** No AWS changes executed."""
        self.assert_mode("explain", answer)

    def test_plan_is_matrix_plus_no_change_rows_only(self):
        answer = self.matrix() + """

| Alias | Control | Evidence | Suggested change | Execution |
| --- | --- | --- | --- | --- |
| lab-dev | S3 BPA | 🔴 NON_COMPLIANT (3 affected) | Bring bucket-level Block Public Access into the compliant configuration. | 🚫 Not executed |
| lab-poc | Restricted SSH | 🔴 NON_COMPLIANT (2 affected) | Remove unrestricted SSH ingress; if access is required, replace it with an approved source. | 🚫 Not executed |

🛡️ **Read-only:** No AWS changes executed."""
        self.assert_mode("plan", answer)

    def test_persisted_tool_output_must_equal_final_assistant(self):
        answer = self.matrix() + "\n\n🛡️ **Read-only:** No AWS changes executed."
        tool = {"answer": answer, "mutation": False, "evidence": self.evidence()}
        messages = [
            {"isCreatedByUser": False, "text": "", "content": [
                {"type": "tool_call", "tool_call": {"id": "call-1",
                 "name": "ask_compliance_agent",
                 "output": json.dumps(tool)}}]},
            {"isCreatedByUser": False, "text": answer},
        ]
        body = "const m=" + json.dumps(messages) + ";console.log(c.persistedBinding(m).toolCallId);"
        self.assertEqual(self.node(body), "call-1")
        messages[-1]["text"] += "\nExtra outer-agent prose"
        body = "const m=" + json.dumps(messages) + ";try{c.persistedBinding(m);process.exit(2)}catch(e){console.log(e.message)}"
        self.assertEqual(self.node(body), "OUTER_AGENT_REWRITE_DETECTED")

    def test_live_style_effective_tool_markdown_is_authoritative(self):
        answer = self.matrix() + "\n\n2 of 8 checks need attention.\n\n" \
                 + "🛡️ **Read-only:** No AWS changes executed."
        messages = [
            {"isCreatedByUser": False, "text": "", "content": [
                {"type": "tool_call", "tool_call": {"id": "call-live",
                 "name": "ask_compliance_agent_mcp_awsops_compliance_agent",
                 "output": answer}},
                {"type": "text", "text": answer},
            ]},
        ]
        body = "const m=" + json.dumps(messages) + ";const b=c.persistedBinding(m);" \
               + "console.log(JSON.stringify({id:b.toolCallId,raw:b.toolResult.persistedOutput,mode:c.assertAnswer('status',b.toolResult," \
               + json.dumps(self.rendered(answer)) + ").mode}));"
        self.assertEqual(json.loads(self.node(body)),
                         {"id": "call-live", "raw": True, "mode": "status"})

    def test_invention_and_guardrail_variants_fail_closed(self):
        base = self.matrix() + "\n\n🛡️ **Read-only:** No AWS changes executed."
        tool = {"answer": base, "mutation": False, "evidence": self.evidence()}
        cases = [
            base.replace("lab-sec", "lab-prod"),
            base.replace("\n\n🛡", "\n\nPort 22 is publicly exposed.\n\n🛡"),
            base.replace("🛡️ **Read-only:**", "> 🛡️ **Read-only:**"),
            base + "\nTrailing prose",
        ]
        for answer in cases:
            broken = dict(tool, answer=answer)
            body = "const t=" + json.dumps(broken) + ";const r=" + json.dumps(self.rendered(answer)) \
                   + ";try{c.assertAnswer('status',t,r);process.exit(2)}catch(e){console.log('blocked')}"
            self.assertEqual(self.node(body), "blocked")

    def test_settled_wait_ignores_stable_not_ready_samples(self):
        body = """let n=0;c.waitForSettledSnapshot(async()=>{n++;return n<3?{ready:false}:{ready:true,value:'ok'}},
{attempts:8,stableSamples:2,pause:async()=>{}}).then(v=>console.log(JSON.stringify({n,value:v.value})))
.catch(e=>{console.error(e.message);process.exit(2)});"""
        self.assertEqual(json.loads(self.node(body)), {"n": 4, "value": "ok"})

    def test_archive_and_diagnostics_are_bounded(self):
        self.assertEqual(self.node("console.log(JSON.stringify(c.archiveRequest('conversation-1')));"),
                         '{"path":"/api/convos/archive","method":"POST","body":{"arg":{"conversationId":"conversation-1","isArchived":true}}}')
        body = "const rows=[];for(let i=0;i<99;i++)c.recordDiagnostic(rows,c.safeDiagnostic({stage:'status',method:'POST',url:'https://sec2.astromedicomp.org/api/agents/chat?token=secret',status:200,headerNames:['Authorization','Cookie'],base:'https://sec2.astromedicomp.org'}));console.log(JSON.stringify({n:rows.length,row:rows[0]}));"
        value = json.loads(self.node(body))
        self.assertEqual(value["n"], 32)
        self.assertNotIn("secret", json.dumps(value))
        self.assertTrue(value["row"]["authorization_present"])

    def test_runner_never_exports_auth_or_deletes_conversations(self):
        source = RUNNER.read_text()
        for forbidden in ["storageState(", ".cookies(", "localStorage.getItem", "allHeaders(",
                          "api/convos/delete", "api/convos/all", "Reject", "s3_ssl", "candidate.json"]:
            self.assertNotIn(forbidden, source)
        self.assertIn("contract.archiveRequest(conversationId)", source)
        self.assertIn("/api/agents/${encodeURIComponent(agentId)}/expanded", source)
        self.assertIn("EXACT_AGENT_DETAIL_REQUIRED", source)
        self.assertIn("getByTestId('model-selector-button')", source)
        self.assertIn("locator('#model-search')", source)
        self.assertIn("getByRole('option').filter({hasText: AGENT})", source)
        self.assertNotIn("Agent configuration form", source)
        self.assertIn("connectOverCDP", source)
        self.assertIn("--host-resolver-rules=MAP sec2.astromedicomp.org 127.0.0.1", source)
        self.assertIn("loopback_origin", source)
        self.assertIn("127\\.0\\.0\\.1", source)
        self.assertIn("localhost", source)
        self.assertIn("DEFAULT_BASE", source)
        self.assertIn("BROWSER_TIMEOUT", source)
        self.assertIn("pathname === '/api/agents/chat' || pathname.startsWith('/api/agents/chat/')", source)
        self.assertIn("!pathname.endsWith('/abort')", source)
        self.assertIn("start?.conversationId", source)
        self.assertIn("PERSISTED_CONVERSATION_REQUIRED", source)
        self.assertIn("registerConversation(conversationId)", source)
        self.assertNotIn("waitForURL(\`/c/\${conversationId}", source)
        self.assertIn(".screenshot({path: screenshot})", source)
        self.assertIn("console_types: consoleTypes", source)
        self.assertIn("page_error_types: pageErrorTypes", source)
        self.assertIn("browser_auth_exported: false", source)


if __name__ == "__main__":
    unittest.main()
