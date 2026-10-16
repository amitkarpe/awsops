"""Focused fake SDK proof for the Issue #90 create/approval/cleanup boundary."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from awsops.aws.boto3_s3_canary import Boto3CanaryProvider
from awsops.domain.models import canonical_digest
from awsops.execution.s3_canary import CanaryAdapter, CanaryBinding


class AwsError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class FakeS3:
    def __init__(self):
        self.exists = False
        self.tags = None
        self.block = None
        self.policy = None
        self.objects = []
        self.versions = []
        self.markers = []
        self.writes = []
        self.uncertain = None
        self.wrong_region = False
        self.wrong_owner = False

    def head_bucket(self, **_):
        if not self.exists:
            raise AwsError("404")
        if self.wrong_owner:
            raise AwsError("403")
        return {"ResponseMetadata": {"HTTPHeaders": {
            "x-amz-bucket-region": "us-east-1" if self.wrong_region else "ap-southeast-1"}}}

    def get_bucket_tagging(self, **_):
        if self.tags is None:
            raise AwsError("NoSuchTagSet")
        return {"TagSet": [{"Key": k, "Value": v} for k, v in self.tags.items()]}

    def get_public_access_block(self, **_):
        if self.block is None:
            raise AwsError("NoSuchPublicAccessBlockConfiguration")
        return {"PublicAccessBlockConfiguration": self.block}

    def get_bucket_policy(self, **_):
        if self.policy is None:
            raise AwsError("NoSuchBucketPolicy")
        return {"Policy": json.dumps(self.policy)}

    def list_objects_v2(self, **_):
        return {"Contents": self.objects, "IsTruncated": False}

    def list_object_versions(self, **_):
        return {"Versions": self.versions, "DeleteMarkers": self.markers, "IsTruncated": False}

    def _write(self, step):
        self.writes.append(step)
        if self.uncertain == step:
            raise AwsError("Timeout")

    def create_bucket(self, **_):
        self.exists = True
        self._write("create")

    def put_bucket_tagging(self, **kwargs):
        self.tags = {x["Key"]: x["Value"] for x in kwargs["Tagging"]["TagSet"]}
        self._write("tags")

    def put_public_access_block(self, **kwargs):
        self.block = kwargs["PublicAccessBlockConfiguration"]
        self._write("public_block")

    def put_bucket_policy(self, **kwargs):
        self.policy = json.loads(kwargs["Policy"])
        self._write("policy")

    def delete_bucket(self, **_):
        self.exists = False
        self._write("delete")


class FakeSession:
    profile_name = "amit"
    region_name = "ap-southeast-1"

    def __init__(self, s3, account="000000000001", root=False):
        self.s3, self.account, self.root = s3, account, root

    def client(self, name, **_):
        return self if name == "sts" else self.s3

    def get_caller_identity(self):
        kind = "root" if self.root else "user/amit"
        return {"Account": self.account, "Arn": f"arn:aws:iam::{self.account}:{kind}"}


class ProviderProof(unittest.TestCase):
    def setup_canary(self, directory, *, uncertain=None, root=False, existing=False):
        binding = CanaryBinding("000000000001", "awsops-dev-issue90-s3-canary-0123456789ab")
        s3 = FakeS3()
        s3.uncertain, s3.exists = uncertain, existing
        ledger = Path(directory) / "canary.sqlite"
        provider = Boto3CanaryProvider(FakeSession(s3, root=root), binding, ledger,
                                        clock=lambda: 1800000000, retry_config=object())
        adapter = CanaryAdapter(ledger, binding, provider, source_revision="a" * 40,
                                source_version="v1.0.0-mock", clock=lambda: 1800000000)
        return adapter, s3

    def test_exact_owned_create_readback_and_cleanup(self):
        principal = canonical_digest("fake authenticated human")
        with tempfile.TemporaryDirectory() as directory:
            adapter, s3 = self.setup_canary(directory)
            batch = adapter.prepare(principal)["record"]
            result = adapter.decide(batch["batchId"], batch["scopeDigest"], principal, "APPROVE_ONCE")
            run = result["run"]["record"]
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy"])
            self.assertEqual(run["realWrites"], 4)
            self.assertEqual(run["results"][0]["providerReadback"], "MATCH")
            self.assertEqual((run["results"][0]["compliance"], run["results"][0]["freshness"]),
                             ("UNKNOWN", "NOT_VERIFIED"))
            self.assertTrue(all(s3.block.values()))
            self.assertEqual(s3.tags["cleanup"], "delete")
            self.assertIn("TTL", s3.tags)
            self.assertNotIn(adapter.binding.account_id, json.dumps(result))
            self.assertNotIn(adapter.binding.bucket, json.dumps(result))
            s3.markers = [{"Key": "foreign", "VersionId": "1"}]
            with self.assertRaises(ValueError):
                adapter.cleanup(batch["batchId"], principal)
            self.assertEqual(len(s3.writes), 4)
            s3.markers = []
            self.assertEqual(adapter.cleanup(batch["batchId"], principal)["status"], "DELETED")
            self.assertFalse(s3.exists)
            receipt = adapter.receipt(batch["batchId"], principal)[2]["record"]["results"][0]
            self.assertEqual((receipt["providerReadback"], receipt["execution"]), ("MATCH", "SUCCEEDED"))
            with self.assertRaises(ValueError):
                adapter.cleanup(batch["batchId"], principal)
            self.assertEqual(len(s3.writes), 5)

    def test_reject_uncertain_and_guard_refusals(self):
        principal = canonical_digest("fake authenticated human")
        for scenario in ("reject", "uncertain_create", "uncertain_policy", "preexisting",
                         "root", "region", "owner", "object", "version", "marker", "public_block"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                adapter, s3 = self.setup_canary(directory,
                    uncertain="create" if scenario == "uncertain_create" else
                              "policy" if scenario == "uncertain_policy" else None,
                    root=scenario == "root", existing=scenario == "preexisting")
                if scenario in ("root", "preexisting"):
                    with self.assertRaises(ValueError):
                        adapter.prepare(principal)
                    self.assertEqual(s3.writes, [])
                    continue
                batch = adapter.prepare(principal)["record"]
                if scenario == "region":
                    s3.wrong_region = True
                if scenario == "owner":
                    s3.wrong_owner = True
                if scenario == "object":
                    s3.objects = [{"Key": "foreign"}]
                if scenario == "version":
                    s3.versions = [{"Key": "foreign", "VersionId": "1"}]
                if scenario == "marker":
                    s3.markers = [{"Key": "foreign", "VersionId": "1"}]
                if scenario == "public_block":
                    original = s3.put_public_access_block
                    def weak_block(**kwargs):
                        original(**kwargs)
                        s3.block["RestrictPublicBuckets"] = False
                    s3.put_public_access_block = weak_block
                result = adapter.decide(batch["batchId"], batch["scopeDigest"], principal,
                                        "REJECT" if scenario == "reject" else "APPROVE_ONCE")
                writes = list(s3.writes)
                with self.assertRaises(ValueError):
                    adapter.decide(batch["batchId"], batch["scopeDigest"], principal, "APPROVE_ONCE")
                adapter.reconcile(batch["batchId"], principal)
                self.assertEqual(s3.writes, writes)
                if scenario == "reject":
                    self.assertEqual(writes, [])
                if scenario == "uncertain_create":
                    self.assertEqual(writes, ["create"])
                if scenario == "uncertain_policy":
                    self.assertEqual(writes, ["create", "tags", "public_block", "policy"])
                    self.assertEqual(result["run"]["record"]["results"][0]["execution"], "UNKNOWN")
                    self.assertEqual(result["run"]["record"]["results"][0]["providerReadback"], "MATCH")
                if scenario in ("uncertain_create", "uncertain_policy", "region", "owner", "object", "version", "marker", "public_block"):
                    with self.assertRaises(ValueError):
                        adapter.cleanup(batch["batchId"], principal)

    def test_uncertain_delete_is_observed_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter, s3 = self.setup_canary(directory, uncertain="delete")
            principal = canonical_digest("fake authenticated human")
            batch = adapter.prepare(principal)["record"]
            adapter.decide(batch["batchId"], batch["scopeDigest"], principal, "APPROVE_ONCE")
            self.assertEqual(adapter.cleanup(batch["batchId"], principal)["status"], "UNKNOWN")
            self.assertEqual(adapter.cleanup_state(batch["batchId"], principal)["status"],
                             "ABSENT_AFTER_UNKNOWN")
            receipt = adapter.receipt(batch["batchId"], principal)[2]["record"]["results"][0]
            self.assertEqual((receipt["providerReadback"], receipt["execution"]), ("MATCH", "SUCCEEDED"))
            with self.assertRaises(ValueError):
                adapter.cleanup(batch["batchId"], principal)
            self.assertEqual(s3.writes.count("delete"), 1)


if __name__ == "__main__":
    unittest.main()
