"""Focused fake SDK proof for the Issue #90 create/approval/cleanup boundary."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from awsops.aws.boto3_s3_canary import Boto3CanaryProvider
from awsops.domain.models import canonical_digest
from awsops.execution.s3_canary import CanaryAdapter, CanaryBinding


def cleanup(adapter, batch, principal):
    return adapter.cleanup(batch["batchId"], principal,
                           expires_at=int(adapter.clock()) + 3600)


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
        self.head_calls = 0
        self.fail_head_on_call = None
        self.expire_on_head_call = None
        self.expire_on_versions = False
        self.foreign_after_create = False
        self.fail_tags_preflight_after_create = False
        self.fail_public_block_preflight_after_tags = False
        self.expire_on_cleanup_versions = False
        self.fail_versions_once = False
        self.fail_public_block_once = False
        self.clock = None

    def head_bucket(self, **_):
        self.head_calls += 1
        if self.fail_head_on_call == self.head_calls:
            raise AwsError("403")
        if self.expire_on_head_call == self.head_calls:
            self.clock[0] += 301
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
        if self.fail_public_block_once:
            self.fail_public_block_once = False
            raise AwsError("503")
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
        if self.fail_versions_once:
            self.fail_versions_once = False
            raise AwsError("503")
        if self.expire_on_cleanup_versions and self.exists:
            self.clock[0] += 301
            self.expire_on_cleanup_versions = False
        if self.expire_on_versions and self.exists and self.tags is None:
            self.clock[0] += 301
            self.expire_on_versions = False
        return {"Versions": self.versions, "DeleteMarkers": self.markers, "IsTruncated": False}

    def _write(self, step):
        self.writes.append(step)
        if self.uncertain == step:
            raise AwsError("Timeout")

    def create_bucket(self, **_):
        self.exists = True
        # S3 enables all four Block Public Access flags on newly created buckets.
        self.block = {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
        if self.fail_tags_preflight_after_create:
            self.fail_versions_once = True
        if self.foreign_after_create:
            self.objects = [{"Key": "foreign"}]
        self._write("create")

    def put_bucket_tagging(self, **kwargs):
        self.tags = {x["Key"]: x["Value"] for x in kwargs["Tagging"]["TagSet"]}
        if self.fail_public_block_preflight_after_tags:
            self.fail_public_block_once = True
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
    def setup_canary(self, directory, *, uncertain=None, root=False, existing=False, clock=None):
        clock = clock if clock is not None else [1800000000]
        binding = CanaryBinding("000000000001", "awsops-dev-issue90-s3-canary-0123456789ab")
        s3 = FakeS3()
        s3.uncertain, s3.exists = uncertain, existing
        s3.clock = clock
        ledger = Path(directory) / "canary.sqlite"
        provider = Boto3CanaryProvider(FakeSession(s3, root=root), binding, ledger,
                                        clock=lambda: clock[0], retry_config=object())
        adapter = CanaryAdapter(ledger, binding, provider, source_revision="a" * 40,
                                source_version="v1.0.0-mock", clock=lambda: clock[0])
        return adapter, s3

    def test_no_call_refusals_and_expiry_keep_exact_attempt_counts(self):
        principal = canonical_digest("fake authenticated human")
        for scenario, expected in (("first_guard", []), ("later_guard", ["create"]),
                                   ("first_expiry", []), ("later_expiry", ["create"])):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                clock = [1800000000]
                adapter, s3 = self.setup_canary(directory, clock=clock)
                batch = adapter.prepare(principal)["record"]
                if scenario == "first_guard":
                    s3.fail_head_on_call = s3.head_calls + 2
                elif scenario == "later_guard":
                    s3.foreign_after_create = True
                elif scenario == "first_expiry":
                    s3.expire_on_head_call = s3.head_calls + 2
                else:
                    s3.expire_on_versions = True
                result = adapter.decide(batch["batchId"], batch["scopeDigest"], principal, "APPROVE_ONCE")
                self.assertEqual(s3.writes, expected)
                self.assertEqual(result["run"]["record"]["realWrites"], len(expected))
                with sqlite3.connect(adapter.path) as db:
                    states = dict(db.execute("SELECT step,state FROM operations WHERE batch_id=?",
                                             (batch["batchId"],)))
                self.assertEqual(states["create"], "ACK" if expected else "REFUSED")
                if expected:
                    self.assertEqual(states["tags"], "REFUSED")
                for _ in range(2):
                    readback = adapter.reconcile(batch["batchId"], principal)
                    self.assertEqual(readback["run"]["record"]["realWrites"], len(expected))
                    self.assertEqual(readback["evidence"]["record"]["realWrites"], len(expected))
                self.assertEqual(s3.writes, expected)

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
                cleanup(adapter, batch, principal)
            self.assertEqual(len(s3.writes), 4)
            s3.markers = []
            self.assertEqual(cleanup(adapter, batch, principal)["status"], "DELETED")
            self.assertFalse(s3.exists)
            receipt = adapter.receipt(batch["batchId"], principal)[2]["record"]["results"][0]
            self.assertEqual((receipt["providerReadback"], receipt["execution"]), ("MATCH", "SUCCEEDED"))
            with self.assertRaises(ValueError):
                cleanup(adapter, batch, principal)
            self.assertEqual(len(s3.writes), 5)

    def test_reconcile_recovers_acknowledged_policy_before_result_save(self):
        principal = canonical_digest("fake authenticated human")
        with tempfile.TemporaryDirectory() as directory:
            adapter, s3 = self.setup_canary(directory)
            batch = adapter.prepare(principal)["record"]
            save = adapter._save
            adapter._save = lambda *_args: (_ for _ in ()).throw(RuntimeError("simulated process stop"))
            with self.assertRaises(RuntimeError):
                adapter.decide(batch["batchId"], batch["scopeDigest"], principal, "APPROVE_ONCE")
            adapter._save = save

            result = adapter.reconcile(batch["batchId"], principal)
            record = result["run"]["record"]
            finding = record["results"][0]
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy"])
            self.assertEqual(record["realWrites"], 4)
            self.assertEqual(finding["execution"], "SUCCEEDED")
            self.assertEqual(finding["providerReadback"], "MATCH")
            self.assertEqual(finding["compliance"], "UNKNOWN")
            self.assertEqual(finding["freshness"], "NOT_VERIFIED")

    def test_cleanup_of_known_partial_setup_and_foreign_state_refusal(self):
        principal = canonical_digest("fake authenticated human")
        for failed_step, expected in (("tags", ["create"]),
                                      ("public_block", ["create", "tags"])):
            with self.subTest(failed_step=failed_step), tempfile.TemporaryDirectory() as directory:
                adapter, s3 = self.setup_canary(directory)
                batch = adapter.prepare(principal)["record"]
                if failed_step == "tags":
                    s3.fail_tags_preflight_after_create = True
                else:
                    s3.fail_public_block_preflight_after_tags = True
                adapter.decide(batch["batchId"], batch["scopeDigest"], principal, "APPROVE_ONCE")
                self.assertEqual(s3.writes, expected)

                result = cleanup(adapter, batch, principal)
                self.assertEqual(result, {"status": "DELETED", "deleted": True})
                self.assertEqual(s3.writes, expected + ["delete"])
                self.assertEqual(adapter.cleanup_state(batch["batchId"], principal)["status"],
                                 "DELETED_CONFIRMED")
                with self.assertRaises(ValueError):
                    cleanup(adapter, batch, principal)
                self.assertEqual(s3.writes, expected + ["delete"])

        with tempfile.TemporaryDirectory() as directory:
            adapter, s3 = self.setup_canary(directory)
            batch = adapter.prepare(principal)["record"]
            s3.fail_public_block_preflight_after_tags = True
            adapter.decide(batch["batchId"], batch["scopeDigest"], principal, "APPROVE_ONCE")
            inspect_cleanup = adapter.provider.inspect_cleanup

            def refuse_delete_preflight(binding, *, deleting=False):
                if deleting:
                    raise ValueError("CLEANUP_STATE_DRIFT")
                return inspect_cleanup(binding, deleting=deleting)

            adapter.provider.inspect_cleanup = refuse_delete_preflight
            self.assertEqual(cleanup(adapter, batch, principal),
                             {"status": "REFUSED_NO_CALL", "deleted": False})
            self.assertEqual(s3.writes, ["create", "tags"])
            self.assertEqual(adapter.cleanup_state(batch["batchId"], principal)["status"],
                             "REFUSED_NO_CALL")

        for drift in ("tag", "policy", "object", "version", "marker"):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as directory:
                adapter, s3 = self.setup_canary(directory)
                batch = adapter.prepare(principal)["record"]
                s3.fail_public_block_preflight_after_tags = True
                adapter.decide(batch["batchId"], batch["scopeDigest"], principal, "APPROVE_ONCE")
                if drift == "tag":
                    s3.tags["foreign"] = "leave-alone"
                elif drift == "policy":
                    s3.policy = {"Statement": [{"Sid": "foreign"}]}
                elif drift == "object":
                    s3.objects = [{"Key": "foreign"}]
                elif drift == "version":
                    s3.versions = [{"Key": "foreign", "VersionId": "1"}]
                else:
                    s3.markers = [{"Key": "foreign", "VersionId": "1"}]
                before = list(s3.writes)
                with self.assertRaises(ValueError):
                    cleanup(adapter, batch, principal)
                self.assertEqual(s3.writes, before)

    def test_cleanup_accepts_default_all_true_public_block_after_tag_refusal(self):
        principal = canonical_digest("fake authenticated human")
        with tempfile.TemporaryDirectory() as directory:
            adapter, s3 = self.setup_canary(directory)
            batch = adapter.prepare(principal)["record"]
            s3.fail_tags_preflight_after_create = True
            adapter.decide(batch["batchId"], batch["scopeDigest"], principal, "APPROVE_ONCE")

            self.assertEqual(s3.writes, ["create"])
            self.assertEqual(s3.block, {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            })
            self.assertEqual(cleanup(adapter, batch, principal),
                             {"status": "DELETED", "deleted": True})
            self.assertEqual(s3.writes, ["create", "delete"])

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
                reconciled = adapter.reconcile(batch["batchId"], principal)
                self.assertEqual(s3.writes, writes)
                if scenario == "reject":
                    self.assertEqual(writes, [])
                if scenario == "uncertain_create":
                    self.assertEqual(writes, ["create"])
                    self.assertEqual(result["run"]["record"]["realWrites"], 1)
                    self.assertEqual(reconciled["run"]["record"]["realWrites"], 1)
                    for _ in range(2):
                        with self.assertRaises(ValueError):
                            cleanup(adapter, batch, principal)
                    self.assertEqual(s3.writes, ["create"])
                if scenario == "uncertain_policy":
                    self.assertEqual(writes, ["create", "tags", "public_block", "policy"])
                    self.assertEqual(result["run"]["record"]["realWrites"], 4)
                    self.assertEqual(reconciled["run"]["record"]["realWrites"], 4)
                    self.assertEqual(result["run"]["record"]["results"][0]["execution"], "UNKNOWN")
                    self.assertEqual(result["run"]["record"]["results"][0]["providerReadback"], "MATCH")
                if scenario in ("uncertain_create", "uncertain_policy", "region", "owner", "object", "version", "marker", "public_block"):
                    with self.assertRaises(ValueError):
                        cleanup(adapter, batch, principal)

    def test_uncertain_delete_is_observed_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter, s3 = self.setup_canary(directory, uncertain="delete")
            principal = canonical_digest("fake authenticated human")
            batch = adapter.prepare(principal)["record"]
            adapter.decide(batch["batchId"], batch["scopeDigest"], principal, "APPROVE_ONCE")
            self.assertEqual(cleanup(adapter, batch, principal)["status"], "UNKNOWN")
            self.assertEqual(adapter.cleanup_state(batch["batchId"], principal)["status"],
                             "ABSENT_AFTER_UNKNOWN")
            receipt = adapter.receipt(batch["batchId"], principal)[2]["record"]["results"][0]
            self.assertEqual((receipt["providerReadback"], receipt["execution"]), ("MATCH", "SUCCEEDED"))
            with self.assertRaises(ValueError):
                cleanup(adapter, batch, principal)
            self.assertEqual(s3.writes.count("delete"), 1)


if __name__ == "__main__":
    unittest.main()
