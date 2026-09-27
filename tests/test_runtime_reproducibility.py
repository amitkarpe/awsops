import json
import os
from pathlib import Path
import re
import subprocess
import time
import unittest
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "integration" / "runtime"


class RuntimeReproducibilityTests(unittest.TestCase):
    def test_public_runtime_contract_has_no_private_identifier_shapes(self):
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in RUNTIME.rglob("*")
            if path.is_file()
        )
        self.assertIsNone(re.search(r"\barn:aws(?:-[a-z]+)?:", text))
        self.assertIsNone(re.search(r"(?<![0-9])\d{12}(?![0-9])", text))
        self.assertNotIn("AWS_SECRET_ACCESS_KEY=", text)
        self.assertNotIn("AWS_SESSION_TOKEN=", text)

    def test_host_inventory_and_home_ports_are_exact(self):
        inventory = json.loads((RUNTIME / "accepted-host.json").read_text())
        self.assertEqual(inventory["config2"]["listen"], "127.0.0.1:4313")
        self.assertEqual(inventory["sec2"]["app_listen"], "127.0.0.1:4311")
        self.assertEqual(inventory["sec2"]["database_listen"], "127.0.0.1:27111")
        self.assertFalse(inventory["sec2"]["deferred_issue11_model"]["canonical_home_required"])
        compose = (RUNTIME / "home" / "docker-compose.yaml").read_text()
        self.assertIn('"127.0.0.1:27111:27017"', compose)

    def test_persistent_service_templates_replace_transient_launch_knowledge(self):
        config = (RUNTIME / "systemd" / "awsops-config2-app.service").read_text()
        db = (RUNTIME / "systemd" / "awsops-sec2-db.service").read_text()
        app = (RUNTIME / "systemd" / "awsops-sec2-app.service").read_text()
        deferred = (RUNTIME / "systemd" / "awsops-sec2-model-issue11.service").read_text()
        self.assertIn("EnvironmentFile=/etc/awsops/config2.env", config)
        self.assertIn("127.0.0.1 --port 27111", db)
        self.assertIn("EnvironmentFile=/etc/awsops/sec2-service.env", app)
        self.assertIn("DEFERRED ISSUE #11 ONLY", deferred)
        for value in (config, db, app, deferred):
            self.assertNotIn("/run/systemd/transient", value)

    def test_config2_can_start_and_answer_local_health_without_aws_calls(self):
        port = 4319
        env = dict(os.environ)
        env.update({
            "PORT": str(port),
            "AWSOPS_CONFIG_AGGREGATOR_NAME": "synthetic-home-smoke",
            "AWSOPS_CONFIG_TARGETS_JSON": json.dumps([
                {"alias": alias, "account_id": ("1" * 11) + str(index)}
                for index, alias in enumerate(
                    ("lab-dev", "lab-poc", "lab-qa", "lab-sec"), start=1
                )
            ]),
        })
        process = subprocess.Popen(
            ["node", "server.mjs"],
            cwd=ROOT / "integration" / "config_dashboard",
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            body = None
            for _ in range(30):
                try:
                    request = Request(
                        f"http://127.0.0.1:{port}/api/health",
                        headers={"Host": f"127.0.0.1:{port}"},
                    )
                    with urlopen(request, timeout=1) as response:
                        body = json.loads(response.read())
                    break
                except Exception:
                    time.sleep(0.1)
            self.assertIsNotNone(body)
            self.assertEqual(body["mode"], "AWS_READ_ONLY")
            self.assertFalse(body["remediation"])
            self.assertEqual(len(body["environments"]), 4)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def test_librechat_pin_is_exact_and_home_mcp_is_read_only_agent(self):
        pin = json.loads((RUNTIME / "librechat-runtime.json").read_text())
        self.assertEqual(pin["repository"], "LibreChat-AI/LibreChat")
        self.assertRegex(pin["commit"], r"^[0-9a-f]{40}$")
        yaml = (RUNTIME / "home" / "librechat.yaml.example").read_text()
        self.assertIn("awsops_compliance_agent", yaml)
        self.assertIn("integration.compliance_agent.mcp_server", yaml)
        self.assertNotIn("decide_s3_ssl_reject_only", yaml)


if __name__ == "__main__":
    unittest.main()
