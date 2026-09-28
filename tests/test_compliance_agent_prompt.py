import unittest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from integration.compliance_agent.agent import _bounded_model_answer, _canonical_answer, _record_harness_result, _response_mode, build_prompt


class ComplianceAgentPromptTests(unittest.TestCase):
    def test_harness_telemetry_contains_only_bounded_public_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "harness.json"
            with patch.dict(os.environ, {"AWSOPS_HARNESS_TELEMETRY_FILE": str(target)}):
                _record_harness_result("READY", 123)
            record = json.loads(target.read_text())
            self.assertEqual(set(record), {"version", "status", "latency_ms", "checked_at"})
            self.assertEqual(record["status"], "READY")
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_owner_starters_select_one_response_mode(self):
        self.assertEqual(_response_mode("Status"), "STATUS")
        self.assertEqual(_response_mode("Explain what needs attention"), "EXPLAIN")
        self.assertEqual(
            _response_mode("Give me a remediation plan without making changes"),
            "PLAN",
        )

    def test_status_prompt_does_not_include_other_mode_layouts(self):
        prompt = build_prompt("Status", {"checks": []})
        self.assertIn("RESPONSE_MODE:\nSTATUS", prompt)
        self.assertIn("STATUS MODE:", prompt)
        self.assertNotIn("| Needs attention | Why | Affected |", prompt)
        self.assertNotIn("| Alias | Control | Evidence | Suggested change | Execution |", prompt)

    def test_explain_prompt_excludes_plan_guidance(self):
        prompt = build_prompt("Explain what needs attention", {"checks": []})
        self.assertIn("RESPONSE_MODE:\nEXPLAIN", prompt)
        self.assertIn("| Needs attention | Why | Affected |", prompt)
        self.assertNotIn("| Alias | Control | Evidence | Suggested change | Execution |", prompt)

    @staticmethod
    def evidence():
        aliases = ["lab-dev", "lab-poc", "lab-qa", "lab-sec"]
        controls = ["s3-bucket-level-public-access-prohibited", "restricted-ssh"]
        return {
            "aliases": aliases,
            "controls": controls,
            "checks": [
                {"account_alias": alias, "control": control, "status": "NON_COMPLIANT",
                 "affected_resources": 1}
                for alias in aliases for control in controls
            ],
        }

    def test_model_format_drift_fails_closed_to_canonical_status(self):
        evidence = self.evidence()
        drifted = (
            '| Account | 🪣 S3 BPA | 🔐 Restricted SSH |\n'
            '| --- | --- | --- |\n'
            '| lab-dev | 🔴 NON_COMPLIANT (1) | 🔴 NON_COMPLIANT (1) |\n'
            '“🛡️ Read-only: No AWS changes executed.”'
        )
        answer = _bounded_model_answer("Status", evidence, drifted)
        self.assertEqual(answer, _canonical_answer("Status", evidence))
        self.assertIn("🔴 NON_COMPLIANT (1 affected)", answer)
        self.assertTrue(answer.endswith("🛡️ **Read-only:** No AWS changes executed."))
        self.assertNotIn("“", answer)

    def test_plan_prompt_excludes_explain_guidance(self):
        prompt = build_prompt(
            "Give me a remediation plan without making changes",
            {"checks": []},
        )
        self.assertIn("RESPONSE_MODE:\nPLAN", prompt)
        self.assertIn("| Alias | Control | Evidence | Suggested change | Execution |", prompt)
        self.assertNotIn("| Needs attention | Why | Affected |", prompt)
        self.assertIn("No AWS changes executed", prompt)
        self.assertIn("do not prefix it with `>`", prompt)
        self.assertNotIn("> 🛡️ **Read-only:**", prompt)


if __name__ == "__main__":
    unittest.main()
