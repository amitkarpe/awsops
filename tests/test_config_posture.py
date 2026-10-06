import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("config_posture", ROOT / "scripts/config_posture.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ACCOUNT = "1" * 12


def fixture():
    return {
        "get-caller-identity": {"Account": ACCOUNT, "Arn": f"arn:aws:sts::{ACCOUNT}:assumed-role/{m.ROLE}/awsops-readonly"},
        "describe-configuration-recorders": {"ConfigurationRecorders": [{"name": "private-recorder", "recordingGroup": {"allSupported": True}}]},
        "describe-configuration-recorder-status": {"ConfigurationRecordersStatus": [{"name": "private-recorder", "recording": True, "lastStatus": "Success"}]},
        "describe-config-rules": {"ConfigRules": [{"ConfigRuleName": "private-rule", "ConfigRuleState": "ACTIVE"}]},
        "describe-compliance-by-config-rule": {"ComplianceByConfigRules": [{"ConfigRuleName": "private-rule", "Compliance": {"ComplianceType": "NON_COMPLIANT"}}]},
    }


class PostureTests(unittest.TestCase):
    def run_fixture(self, values):
        calls = []
        def call(op, token):
            calls.append((op, token))
            value = values[op]
            if isinstance(value, Exception):
                raise value
            return value
        return m.acquire(call, ACCOUNT, m.REGION), calls

    def test_public_projection_and_absence_are_scoped(self):
        result, calls = self.run_fixture(fixture())
        self.assertEqual(result["CONFIG_ACQUISITION"], "PASS")
        self.assertEqual(result["NONCOMPLIANT_RULES"], 1)
        self.assertEqual(result["EVALUATION_FRESHNESS"], "NOT_VERIFIED")
        self.assertEqual(len(calls), 5)
        self.assertNotRegex(json.dumps(result), r"private-|arn:|111111111111")
        values = fixture()
        values["describe-configuration-recorders"]["ConfigurationRecorders"] = []
        values["describe-configuration-recorder-status"]["ConfigurationRecordersStatus"] = []
        values["describe-config-rules"]["ConfigRules"] = []
        values["describe-compliance-by-config-rule"]["ComplianceByConfigRules"] = []
        result, _ = self.run_fixture(values)
        self.assertEqual(result["RECORDER_PRESENT"], "NO")
        self.assertEqual(result["TOTAL_RULES"], 0)  # actual complete empty inventory only
        values = fixture()
        values["describe-configuration-recorder-status"]["ConfigurationRecordersStatus"][0]["recording"] = False
        self.assertEqual(self.run_fixture(values)[0]["RECORDING"], "NO")

    def test_denied_errors_partial_and_malformed_never_become_zero(self):
        for value in [m.Rejected("ACCESS_DENIED"), RuntimeError("private account response"), {},
                      {"ConfigurationRecorders": [], "Error": "private failure"}]:
            values = fixture(); values["describe-configuration-recorders"] = value
            result, calls = self.run_fixture(values)
            self.assertEqual(result["CONFIG_ACQUISITION"], "BLOCKED")
            self.assertEqual(result["RECORDER_PRESENT"], "UNKNOWN")
            self.assertIsNone(result["TOTAL_RULES"])
            self.assertEqual(len(calls), 2)
            self.assertNotIn("private", json.dumps(result))
        for op, key, field, value in [
            ("describe-configuration-recorder-status", "ConfigurationRecordersStatus", "name", "other"),
            ("describe-config-rules", "ConfigRules", "ConfigRuleState", "DELETING"),
            ("describe-compliance-by-config-rule", "ComplianceByConfigRules", "ConfigRuleName", "other"),
            ("describe-compliance-by-config-rule", "ComplianceByConfigRules", "Compliance", {}),
        ]:
            values = fixture(); values[op][key][0][field] = value
            result, _ = self.run_fixture(values)
            self.assertNotEqual(result["CONFIG_ACQUISITION"], "PASS")
            self.assertIsNone(result["TOTAL_RULES"])
        values = fixture(); values["describe-config-rules"]["ConfigRules"] *= 2
        self.assertEqual(self.run_fixture(values)[0]["REASON"], "INCONSISTENT")

    def test_recorder_arn_reconciliation_preserves_optional_omission(self):
        arn = f"arn:aws:config:{m.REGION}:{ACCOUNT}:configuration-recorder/private-recorder/id-one"
        for recorder_arn, status_arn, expected in (
            (arn, arn, "PASS"), (arn, None, "PASS"), (None, arn, "PASS"),
            (arn, arn.replace("id-one", "id-two"), "PARTIAL"),
        ):
            values = fixture()
            if recorder_arn is not None:
                values["describe-configuration-recorders"]["ConfigurationRecorders"][0]["arn"] = recorder_arn
            if status_arn is not None:
                values["describe-configuration-recorder-status"]["ConfigurationRecordersStatus"][0]["arn"] = status_arn
            result, calls = self.run_fixture(values)
            self.assertEqual(result["CONFIG_ACQUISITION"], expected)
            self.assertNotRegex(json.dumps(result), r"private-|arn:|111111111111|id-two")
            if expected == "PARTIAL":
                self.assertEqual(result["REASON"], "INCONSISTENT")
                self.assertEqual(result["RECORDER_PRESENT"], "UNKNOWN")
                self.assertIsNone(result["TOTAL_RULES"])
                self.assertEqual(len(calls), 3)  # no rule reads after identity drift

    def test_identity_region_fail_before_config(self):
        values = fixture(); values["get-caller-identity"]["Account"] = "2" * 12
        result, calls = self.run_fixture(values)
        self.assertEqual(result["OIDC_IDENTITY"], "FAIL")
        self.assertEqual(len(calls), 1)
        def forbidden(*args):
            self.fail("Region mismatch must not call a provider")
        self.assertEqual(m.acquire(forbidden, ACCOUNT, "us-east-1")["REGION"], "FAIL")

    def test_pagination_budget_and_incomplete_cap(self):
        values = fixture(); calls = []
        def caller(op, token):
            calls.append(op)
            if op not in {"describe-config-rules", "describe-compliance-by-config-rule"}:
                return values[op]
            page = int(token or "0")
            names = [f"private-rule-{page * 100 + i}" for i in range(100)]
            if op == "describe-config-rules":
                data = {"ConfigRules": [{"ConfigRuleName": n, "ConfigRuleState": "ACTIVE"} for n in names]}
            else:
                data = {"ComplianceByConfigRules": [{"ConfigRuleName": n, "Compliance": {"ComplianceType": "INSUFFICIENT_DATA"}} for n in names]}
            if page < 4: data["NextToken"] = str(page + 1)
            return data
        result = m.acquire(caller, ACCOUNT, m.REGION)
        self.assertEqual(len(calls), 13)  # one STS + twelve Config
        self.assertEqual(result["INSUFFICIENT_DATA_RULES"], 500)
        def unfinished(op, token):
            response = caller(op, token)
            if op == "describe-config-rules":
                response["NextToken"] = str(int(token or "0") + 1)
            return response
        calls.clear()
        result = m.acquire(unfinished, ACCOUNT, m.REGION)
        self.assertEqual(result["REASON"], "INCOMPLETE_PAGINATION")
        self.assertEqual(len(calls), 8)  # STS, two recorder reads, five pages; stop
        self.assertIsNone(result["TOTAL_RULES"])
        values["describe-config-rules"]["NextToken"] = "repeated-private-token"
        result, calls = self.run_fixture(values)
        self.assertEqual(result["REASON"], "INCOMPLETE_PAGINATION")
        self.assertIsNone(result["TOTAL_RULES"])
        values["describe-config-rules"] = {"ConfigRules": [{"ConfigRuleName": str(i)} for i in range(501)]}
        self.assertEqual(self.run_fixture(values)[0]["REASON"], "INCOMPLETE_PAGINATION")

    def test_disabled_entrypoint_never_creates_caller(self):
        with patch.dict(os.environ, {"CONFIG_ACQUISITION_ENABLED": "false"}, clear=True), patch.object(m, "AwsCaller") as caller, patch("sys.argv", ["config_posture.py"]), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.main(), 1)
            caller.assert_not_called()
            self.assertIn("CONFIG_ACQUISITION=BLOCKED", out.getvalue())
            self.assertIn("REASON=NOT_ACQUIRED", out.getvalue())

    def test_cli_boundary_has_no_retries_fallback_or_raw_errors(self):
        env = {"PATH": "/usr/bin", "AWS_ACCESS_KEY_ID": "fake", "AWS_SECRET_ACCESS_KEY": "fake", "AWS_SESSION_TOKEN": "fake"}
        with patch.dict(os.environ, env, clear=True), patch.object(m.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, b"", b"AccessDenied: private response")
            caller = m.AwsCaller()
            with self.assertRaisesRegex(m.Rejected, "^ACCESS_DENIED$"):
                caller("describe-config-rules", "private-token")
            args, kwargs = run.call_args
            self.assertEqual(args[0][:3], ["aws", "configservice", "describe-config-rules"])
            self.assertEqual(caller.config_calls, 1)
            self.assertIn("--no-paginate", args[0])
            self.assertEqual(kwargs["env"]["AWS_MAX_ATTEMPTS"], "1")
            self.assertEqual(kwargs["env"]["AWS_CONFIG_FILE"], "/dev/null")
            self.assertLessEqual(kwargs["timeout"], 15)
            caller.deadline = 0
            with self.assertRaises(m.Rejected): caller("describe-config-rules", None)
            self.assertEqual(run.call_count, 1)
        with patch.dict(os.environ, env, clear=True), patch.object(m.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, b"{}", b"")
            caller = m.AwsCaller()
            for operation in m.OPERATIONS:
                caller(operation, None)
                service = "sts" if operation == "get-caller-identity" else "configservice"
                self.assertEqual(run.call_args.args[0][:3], ["aws", service, operation])
            self.assertEqual(caller.config_calls, 4)
            caller.config_calls = 12
            with self.assertRaisesRegex(m.Rejected, "^INCOMPLETE_PAGINATION$"):
                caller("describe-configuration-recorders", None)
            self.assertEqual(run.call_count, 5)  # cap rejects before subprocess
        with patch.dict(os.environ, {**env, "AWS_ENDPOINT_URL_CONFIG": "https://invalid.example"}, clear=True):
            with self.assertRaises(m.Rejected): m.AwsCaller()

    def test_policy_is_exact_proposal_and_workflow_stays_disabled(self):
        p = json.loads((ROOT / "integration/cloud_readonly/account-local.proposed.json").read_text())
        self.assertEqual(len(p["Statement"]), 2)
        first, second = p["Statement"]
        self.assertEqual(first["Action"], ["config:DescribeConfigurationRecorders", "config:DescribeConfigurationRecorderStatus"])
        self.assertEqual(second["Action"], ["config:DescribeConfigRules", "config:DescribeComplianceByConfigRule"])
        self.assertEqual(first["Resource"], "arn:aws:config:ap-southeast-1:<APPROVED_LAB_ACCOUNT_ID>:configuration-recorder/*/*")
        self.assertEqual(second["Resource"], "*")
        for statement in p["Statement"]:
            self.assertEqual(set(statement), {"Sid", "Effect", "Action", "Resource", "Condition"})
            self.assertEqual(statement["Effect"], "Allow")
            self.assertEqual(statement["Condition"], {"StringEquals": {"aws:RequestedRegion": m.REGION}})
        workflow = (ROOT / ".github/workflows/awsops-readonly.yml").read_text()
        self.assertIn("CONFIG_ACQUISITION_ENABLED: 'false'", workflow)
        self.assertIn("if: github.ref == 'refs/heads/main' && github.event_name == 'workflow_dispatch'", workflow)
        self.assertIn("if: env.CONFIG_ACQUISITION_ENABLED == 'true'", workflow)
        self.assertIn("disable-retry: true", workflow)
        self.assertIn("role-duration-seconds: 900", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("inputs:", workflow)


if __name__ == "__main__":
    unittest.main()
