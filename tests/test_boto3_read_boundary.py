"""SDK calls are stubbed: no credentials, live calls or boto3 install required."""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from awsops.aws.boto3_s3_ssl import Boto3S3ReadClient, DEFAULT_READ_ROLE, assume_role_factory
from awsops.aws.s3_ssl import AccountBinding, ALIASES, REGION
from awsops.runtime.read_probe import load_config, main


class ProviderError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class FakeSDK:
    def __init__(self, account, role=DEFAULT_READ_ROLE):
        self.account = account
        self.role = role
        self.calls = []
        self.policy = '{"Statement": []}'
        self.error = None
    def get_caller_identity(self):
        self.calls.append(("identity", {}))
        return {"Account": self.account, "Arn": f"arn:aws:sts::{self.account}:assumed-role/{self.role}/test"}
    def list_buckets(self, **kwargs):
        self.calls.append(("list", kwargs))
        return {"Buckets": []}
    def get_bucket_policy(self, **kwargs):
        self.calls.append(("policy", kwargs))
        if self.error:
            raise self.error
        return {"Policy": self.policy}
    def assume_role(self, **kwargs):
        self.calls.append(("assume", kwargs))
        return {"Credentials": {"AccessKeyId": "unit-only", "SecretAccessKey": "unit-only", "SessionToken": "unit-only"}}


class FakeSession:
    region_name = REGION
    def __init__(self, sdk):
        self.sdk = sdk
    def client(self, _service, *, region_name):
        assert region_name == REGION
        return self.sdk


class BotoBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.binding = AccountBinding("lab-dev", str(1).zfill(12))
        self.sdk = FakeSDK(self.binding.account_id)
        self.client = Boto3S3ReadClient(FakeSession(self.sdk), self.binding)
    def test_identity_required(self):
        for call in (lambda: self.client.list_bucket_page(None), lambda: self.client.bucket_policy("unit-bucket")):
            with self.assertRaises(ValueError):
                call()
        self.assertEqual(self.sdk.calls, [])
    def test_wrong_role_denied(self):
        self.sdk.role = "OtherRole"
        with self.assertRaises(ValueError):
            self.client.caller_account()
    def test_wrong_target_account_denied(self):
        self.sdk.account = str(2).zfill(12)
        with self.assertRaises(ValueError):
            self.client.caller_account()
    def test_bound_list_and_owner_guard(self):
        self.client.caller_account()
        self.client.list_bucket_page("continuation")
        self.client.bucket_policy("unit-bucket")
        self.assertEqual(self.sdk.calls[-2], ("list", {"BucketRegion": REGION, "MaxBuckets": 20, "ContinuationToken": "continuation"}))
        self.assertEqual(self.sdk.calls[-1][1]["ExpectedBucketOwner"], self.binding.account_id)
    def test_structured_missing_policy_only(self):
        self.client.caller_account()
        self.sdk.error = ProviderError("NoSuchBucketPolicy")
        self.assertIsNone(self.client.bucket_policy("unit-bucket"))
        for error in (ProviderError("AccessDenied"), RuntimeError("NoSuchBucketPolicy")):
            self.sdk.error = error
            with self.assertRaises(Exception):
                self.client.bucket_policy("unit-bucket")
    def test_duplicate_non_json_or_oversized_policy(self):
        self.client.caller_account()
        for raw in ('{"Statement": [], "Statement": {}}', '{"x": NaN}', 'x' * 131073, 'not-json', 'null', '[]', '"string"'):
            self.sdk.policy = raw
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                self.client.bucket_policy("unit-bucket")
    def test_source_mismatch_prevents_assume(self):
        with self.assertRaises(ValueError):
            assume_role_factory(FakeSession(self.sdk), expected_source_account=str(9).zfill(12), session_factory=lambda **kw: None)
        self.assertEqual([c[0] for c in self.sdk.calls], ["identity"])
    def test_source_region_mismatch(self):
        session = FakeSession(self.sdk)
        session.region_name = "us-east-1"
        with self.assertRaises(ValueError):
            assume_role_factory(session, expected_source_account=self.binding.account_id)
        self.assertEqual(self.sdk.calls, [])
    def test_fixed_assume_role_and_target_verification(self):
        factory = assume_role_factory(FakeSession(self.sdk), expected_source_account=self.binding.account_id,
                                      session_factory=lambda **kwargs: FakeSession(FakeSDK(self.binding.account_id)))
        target = factory(self.binding)
        self.assertEqual(target.caller_account(), self.binding.account_id)
        request = self.sdk.calls[-1][1]
        self.assertEqual(request["RoleArn"], f"arn:aws:iam::{self.binding.account_id}:role/{DEFAULT_READ_ROLE}")
        self.assertEqual(request["DurationSeconds"], 900)
    def test_cli_requires_explicit_read_confirmation(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as result:
            main(["--config", "unused", "--alias", "lab-dev"])
        self.assertEqual(result.exception.code, 2)
    def test_cli_sanitizes_config_failure(self):
        output = StringIO()
        with redirect_stdout(output):
            status = main(["--config", "/private/should-not-print", "--alias", "lab-dev", "--confirm-lab-read-only"])
        self.assertEqual(status, 2)
        self.assertNotIn("/private", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["outcome"], "BLOCKED")
    def test_private_config_is_exact(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            data = {"region": REGION, "profile": "unit", "source_account_id": str(9).zfill(12),
                    "accounts": [{"alias": a, "account_id": str(i).zfill(12)} for i, a in enumerate(ALIASES, 1)]}
            path.write_text(json.dumps(data))
            self.assertEqual(len(load_config(path)[1]), 4)
            data["arbitrary_role"] = "not-allowed"
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
