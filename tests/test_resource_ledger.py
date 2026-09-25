from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from awsops.resources.ledger import LedgerRow, parse_date, render_markdown, right_size_t3


class ResourceLedgerTests(unittest.TestCase):
    def test_date_formats(self):
        self.assertEqual(parse_date("2026-09-25"), date(2026, 9, 25))
        self.assertEqual(parse_date("30-09-26"), date(2026, 9, 30))

    def test_right_size_keeps_medium_when_memory_headroom_is_thin(self):
        result = right_size_t3({
            "mem_total_gib": 3.74,
            "mem_available_gib": 2.05,
            "swap_total_gib": 0.0,
            "cpu_14d_avg_pct": 1.63,
            "root_used_pct": 92.0,
        })
        self.assertEqual(result["recommendation"], "KEEP-t3.medium")
        self.assertIn("no swap", result["reason"])
        self.assertIn("92%", result["reason"])

    def test_right_size_needs_complete_metrics(self):
        self.assertEqual(right_size_t3({})["recommendation"], "NEEDS-EVIDENCE")

    def test_render_is_kiss_and_uses_aliases(self):
        row = LedgerRow(
            "awsops", "amit", "EC2 retained demo host", 1, "running",
            "LibreChat runtime", "EST", "RETAIN", "LIVE",
            resource_name="agentcore-issue19-librechat-poc-r01", created=date(2026, 9, 2),
        )
        text = render_markdown(
            [row],
            verified_at="2026-09-25T03:30:00+00:00",
            coverage="test",
            sizing={"recommendation": "KEEP-t3.medium", "reason": "test"},
            cost_snapshot={
                "priority": [{
                    "priority": "HIGH",
                    "account": "amit",
                    "name": "EC2 Compute",
                    "state": "running",
                    "cost": "USD 10 MTD",
                    "action": "KEEP"
                }],
                "accounts": [{
                    "account": "amit",
                    "period": "test",
                    "actual_usd": 10.0,
                    "note": "test"
                }]
            },
        )
        self.assertIn("23d (created)", text)
        self.assertIn("**amit**", text)
        self.assertIn("agentcore-issue19-librechat-poc-r01", text)
        self.assertNotIn("ResourceARN", text)

    def test_bad_enum_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid ledger enum"):
            LedgerRow("awsops", "amit", "EC2 host", 1, "running", "demo", "BAD", "RETAIN", "LIVE")


if __name__ == "__main__":
    unittest.main()
