import unittest

from integration.compliance_agent.agent import _normalize_final_answer, _response_mode, build_prompt


class ComplianceAgentPromptTests(unittest.TestCase):
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
        self.assertNotIn("| Priority | Control | Suggested change | Execution |", prompt)

    def test_explain_prompt_excludes_plan_guidance(self):
        prompt = build_prompt("Explain what needs attention", {"checks": []})
        self.assertIn("RESPONSE_MODE:\nEXPLAIN", prompt)
        self.assertIn("| Needs attention | Why | Affected |", prompt)
        self.assertNotIn("| Priority | Control | Suggested change | Execution |", prompt)

    def test_final_guardrail_normalization_is_exact(self):
        raw = '| Account | x | y |\n"🛡️ **Read-only:** No AWS changes executed"'
        self.assertTrue(_normalize_final_answer(raw).endswith(
            "🛡️ **Read-only:** No AWS changes executed."
        ))

    def test_plan_prompt_excludes_explain_guidance(self):
        prompt = build_prompt(
            "Give me a remediation plan without making changes",
            {"checks": []},
        )
        self.assertIn("RESPONSE_MODE:\nPLAN", prompt)
        self.assertIn("| Priority | Control | Suggested change | Execution |", prompt)
        self.assertNotIn("| Needs attention | Why | Affected |", prompt)
        self.assertIn("No AWS changes executed", prompt)
        self.assertIn("do not prefix it with `>`", prompt)
        self.assertNotIn("> 🛡️ **Read-only:**", prompt)


if __name__ == "__main__":
    unittest.main()
