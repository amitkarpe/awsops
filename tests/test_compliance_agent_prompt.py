import unittest

from integration.compliance_agent.agent import _response_mode, build_prompt


class ComplianceAgentPromptTests(unittest.TestCase):
    def test_owner_starters_select_one_response_mode(self):
        self.assertEqual(_response_mode("Status"), "STATUS")
        self.assertEqual(_response_mode("Explain what needs attention"), "EXPLAIN")
        self.assertEqual(
            _response_mode("Give me a remediation plan without making changes"),
            "PLAN",
        )

    def test_prompt_makes_modes_mutually_exclusive(self):
        prompt = build_prompt("Explain what needs attention", {"checks": []})
        self.assertIn("RESPONSE_MODE:\nEXPLAIN", prompt)
        self.assertIn("never combine modes", prompt)
        self.assertIn("Do not include a remediation-plan table", prompt)
        self.assertIn("No AWS changes executed", prompt)


if __name__ == "__main__":
    unittest.main()
