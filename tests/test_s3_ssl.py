from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from awsops.aws.s3_ssl import ALIASES, AccountBinding, MAX_BUCKETS_PER_ACCOUNT, collect
from awsops.controls.registry import capability
from awsops.controls.s3_ssl import requires_secure_transport
from awsops.runtime.s3_ssl_service import S3SslService


COMPLIANT = {
    "Statement": [{
        "Effect": "Deny",
        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
    }]
}
NON_COMPLIANT = {"Statement": []}


class FakeClient:
    def __init__(self, account_id, buckets, policies):
        self.account_id = account_id
        self.buckets = list(buckets)
        self.policies = policies
        self.policy_reads = []

    def caller_account(self):
        return self.account_id

    def list_bucket_names(self):
        return list(self.buckets)

    def bucket_policy(self, bucket):
        self.policy_reads.append(bucket)
        value = self.policies[bucket]
        if isinstance(value, Exception):
            raise value
        return value


def bindings():
    return tuple(AccountBinding(alias, f"{index:012d}") for index, alias in enumerate(ALIASES, start=1))


class S3SslTests(unittest.TestCase):
    def test_secure_transport_semantics(self):
        self.assertTrue(requires_secure_transport(COMPLIANT))
        self.assertFalse(requires_secure_transport(NON_COMPLIANT))

    def test_capability_is_prepare_verify_but_not_remediate(self):
        cap = capability("s3_ssl")
        self.assertTrue(cap.detect and cap.explain and cap.prepare and cap.verify)
        self.assertFalse(cap.remediate)
        self.assertFalse(cap.live_execution_authorized)

    def test_exact_alias_order_is_required(self):
        current = bindings()
        bad = (current[1], current[0], current[2], current[3])
        with self.assertRaisesRegex(ValueError, "exact registered LAB aliases"):
            collect(bad, lambda binding: None)

    def test_identity_mismatch_fails_closed(self):
        current = bindings()
        clients = {
            b.alias: FakeClient("999999999999" if b.alias == "lab-dev" else b.account_id, ["bucket-a"], {"bucket-a": NON_COMPLIANT})
            for b in current
        }
        report = collect(current, lambda binding: clients[binding.alias])
        dev = report["accounts"][0]
        self.assertFalse(dev["identity_verified"])
        self.assertEqual(dev["state"], "UNAVAILABLE")
        self.assertEqual(clients["lab-dev"].policy_reads, [])
        self.assertEqual(report["aws_writes"], 0)

    def test_reads_are_bounded_and_public_safe(self):
        current = bindings()
        names = [f"private-bucket-{index:02d}" for index in range(25)]
        clients = {
            b.alias: FakeClient(b.account_id, names, {name: NON_COMPLIANT for name in names})
            for b in current
        }
        report = collect(current, lambda binding: clients[binding.alias])
        for alias in ALIASES:
            self.assertEqual(len(clients[alias].policy_reads), MAX_BUCKETS_PER_ACCOUNT)
        text = repr(report)
        self.assertNotIn("private-bucket-", text)
        for b in current:
            self.assertNotIn(b.account_id, text)
        self.assertFalse(report["raw_identifiers_emitted"])
        self.assertEqual(report["aws_writes"], 0)

    def test_no_policy_is_non_compliant_other_error_unavailable(self):
        current = bindings()
        policies = {
            "a": RuntimeError("NoSuchBucketPolicy"),
            "b": RuntimeError("AccessDenied"),
        }
        clients = {
            b.alias: FakeClient(b.account_id, ["a", "b"], policies)
            for b in current
        }
        report = collect(current, lambda binding: clients[binding.alias])
        statuses = [f["provider_status"] for f in report["accounts"][0]["findings"]]
        self.assertEqual(statuses, ["NON_COMPLIANT", "UNAVAILABLE"])

    def test_prepare_and_unchanged_readback(self):
        current = bindings()
        clients = {
            b.alias: FakeClient(b.account_id, ["a"], {"a": NON_COMPLIANT})
            for b in current
        }
        read = lambda: collect(current, lambda binding: clients[binding.alias])
        service = S3SslService(read)
        report = service.status()
        target = next(f for f in report["findings"] if f["account_alias"] == "lab-dev")
        frozen = service.prepare(report, alias="lab-dev", resource_ref=target["resource_ref"])
        self.assertFalse(frozen.live_execution_authorized)
        result = service.readback(frozen)
        self.assertTrue(result["unchanged"])
        self.assertEqual(result["aws_writes"], 0)

    def test_changed_provider_state_is_not_unchanged(self):
        current = bindings()
        clients = {
            b.alias: FakeClient(b.account_id, ["a"], {"a": NON_COMPLIANT})
            for b in current
        }
        read = lambda: collect(current, lambda binding: clients[binding.alias])
        service = S3SslService(read)
        report = service.status()
        target = next(f for f in report["findings"] if f["account_alias"] == "lab-dev")
        frozen = service.prepare(report, alias="lab-dev", resource_ref=target["resource_ref"])
        clients["lab-dev"].policies["a"] = COMPLIANT
        result = service.readback(frozen)
        self.assertFalse(result["unchanged"])
        self.assertEqual(result["state"], "COMPLIANT")

    def test_prepare_rejects_compliant_finding(self):
        current = bindings()
        clients = {
            b.alias: FakeClient(b.account_id, ["a"], {"a": COMPLIANT})
            for b in current
        }
        service = S3SslService(lambda: collect(current, lambda binding: clients[binding.alias]))
        report = service.status()
        target = next(f for f in report["findings"] if f["account_alias"] == "lab-dev")
        with self.assertRaisesRegex(ValueError, "non-compliant"):
            service.prepare(report, alias="lab-dev", resource_ref=target["resource_ref"])


if __name__ == "__main__":
    unittest.main()
