import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("home_demo", ROOT / "scripts" / "home_demo.py")
home_demo = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(home_demo)


class HomeDemoValidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.evidence = Path(self.temp.name)
        run = self.evidence / "issue49-live"
        run.mkdir()
        self.manifest = run / "manifest.json"
        self.manifest.write_text(
            json.dumps(
                {
                    "outcome": "COMPLIANCE_UI_PASS",
                    "tool_count": 1,
                    "action_count": 0,
                    "browser_auth_exported": False,
                    "storage_state_exported": False,
                    "results": [
                        {"mode": mode, "checks": 8, "archived": True}
                        for mode in ("status", "explain", "plan")
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.responses = {
            "/api/health": {
                "mode": "AWS_READ_ONLY",
                "remediation": False,
                "environments": list(home_demo.ALIASES),
                "controls": list(home_demo.CONTROLS),
            },
            "/api/diagnostics": {
                "status": "READY",
                "ready": True,
                "components": {
                    "configProvider": {
                        "availableAccounts": 4,
                        "totalAccounts": 4,
                        "aliases": list(home_demo.ALIASES),
                    }
                },
            },
            "/api/controls?environment=ALL&refresh=1": {
                "available": True,
                "partial": False,
                "accounts": [{"alias": alias} for alias in home_demo.ALIASES],
                "rules": [
                    {"accountAlias": alias, "ConfigRuleName": control}
                    for alias in home_demo.ALIASES
                    for control in home_demo.CONTROLS
                ],
            },
            "/api/config": {"app": "LibreChat"},
        }

    def tearDown(self):
        self.temp.cleanup()

    def fetch(self, url):
        for suffix, value in self.responses.items():
            if url.endswith(suffix):
                return value
        raise AssertionError(f"unexpected URL: {url}")

    def validate(self):
        home_demo.validate_runtime(
            "http://127.0.0.1:4313",
            "http://127.0.0.1:4311",
            self.evidence,
            fetcher=self.fetch,
        )

    def test_exact_read_only_contract_passes(self):
        self.validate()

    def test_partial_or_wrong_matrix_fails_closed(self):
        self.responses["/api/controls?environment=ALL&refresh=1"]["partial"] = True
        with self.assertRaisesRegex(RuntimeError, "partial or unavailable"):
            self.validate()

    def test_tool_action_or_archive_drift_fails_closed(self):
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["action_count"] = 1
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "one read-only tool and zero actions"):
            self.validate()

    def test_non_loopback_runtime_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "exact loopback HTTP origin"):
            home_demo.validate_runtime(
                "https://example.invalid",
                "http://127.0.0.1:4311",
                self.evidence,
                fetcher=self.fetch,
            )


if __name__ == "__main__":
    unittest.main()
