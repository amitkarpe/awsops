"""Adversarial M2 contracts. All accounts, buckets and providers are synthetic."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from awsops.aws.s3_ssl import AccountBinding, ALIASES, REGION, collect, validate_bindings
from awsops.controls.registry import capability
from awsops.controls.s3_ssl import evaluate_policy, requires_secure_transport
from awsops.domain.freeze import freeze_finding
from awsops.domain.models import canonical_digest
from awsops.runtime.s3_ssl_service import S3SslService
from awsops.runtime.read_probe import probe

BUCKET = "unit-bucket"


def policy(bucket=BUCKET):
    return {"Version": "2012-10-17", "Statement": [{
        "Effect": "Deny", "Principal": "*", "Action": "s3:*",
        "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
    }]}


def bindings():
    return tuple(AccountBinding(alias, str(i).zfill(12)) for i, alias in enumerate(ALIASES, 1))


class FakeClient:
    region = REGION
    def __init__(self, account):
        self.account = account
        self.pages = {None: {"Buckets": [{"Name": BUCKET, "BucketRegion": REGION}]}}
        self.policies = {BUCKET: None}
        self.calls = []
        self.identity_error = False
    def caller_account(self):
        self.calls.append("identity")
        if self.identity_error:
            raise RuntimeError("sensitive provider error")
        return self.account
    def list_bucket_page(self, token):
        self.calls.append("list")
        page = self.pages[token]
        if isinstance(page, Exception):
            raise page
        return deepcopy(page)
    def bucket_policy(self, bucket):
        self.calls.append("policy")
        value = self.policies[bucket]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)


class PolicyTests(unittest.TestCase):
    def test_complete_deny(self):
        self.assertEqual(evaluate_policy(policy(), BUCKET), "COMPLIANT")
        self.assertTrue(requires_secure_transport(policy(), BUCKET))
    def test_missing_policy(self):
        self.assertEqual(evaluate_policy(None, BUCKET), "NON_COMPLIANT")
    def test_empty_statements(self):
        self.assertEqual(evaluate_policy({"Statement": []}, BUCKET), "NON_COMPLIANT")
    def test_incomplete_principal_action_resource_or_condition_never_passes(self):
        changes = [
            {"Principal": {"AWS": "someone"}}, {"Principal": None},
            {"Action": "s3:GetObject"}, {"Resource": "arn:aws:s3:::another/*"},
            {"Resource": f"arn:aws:s3:::{BUCKET}/*"},
            {"Condition": {"Bool": {"aws:SecureTransport": "false", "aws:PrincipalIsAWSService": "false"}}},
            {"Condition": {"Bool": {"aws:SecureTransport": "false"}, "IpAddress": {"aws:SourceIp": "example"}}},
            {"NotAction": "s3:DeleteObject"}, {"Effect": "Allow"},
            {"Condition": {"Bool": {"aws:SecureTransport": True}}},
            {"Condition": {"Bool": {"aws:SecureTransport": 0}}},
        ]
        for delta in changes:
            with self.subTest(delta=delta):
                value = policy()
                value["Statement"][0].update(delta)
                self.assertEqual(evaluate_policy(value, BUCKET), "UNKNOWN")
    def test_malformed_policy_is_unknown(self):
        for value in ([], "oops", {}, {"Statement": "oops"}, {"Statement": [None]}):
            with self.subTest(value=value):
                self.assertEqual(evaluate_policy(value, BUCKET), "UNKNOWN")
    def test_split_bucket_object_statements(self):
        value = policy()
        first = value["Statement"][0]
        second = deepcopy(first)
        first["Resource"] = f"arn:aws:s3:::{BUCKET}"
        second["Resource"] = f"arn:aws:s3:::{BUCKET}/*"
        value["Statement"].append(second)
        self.assertEqual(evaluate_policy(value, BUCKET), "COMPLIANT")
    def test_star_and_boolean_forms(self):
        value = policy()
        statement = value["Statement"][0]
        statement.update(Principal={"AWS": "*"}, Action=["s3:*"], Resource="*")
        statement["Condition"]["Bool"]["aws:SecureTransport"] = False
        self.assertEqual(evaluate_policy(value, BUCKET), "COMPLIANT")
    def test_capability_has_no_executor(self):
        cap = capability("s3_ssl")
        self.assertTrue(cap.prepare and cap.verify)
        self.assertFalse(cap.remediate or cap.live_execution_authorized)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.bindings = bindings()
        self.clients = {b.alias: FakeClient(b.account_id) for b in self.bindings}
        self.now = 1000
        self.service = S3SslService(self.read, clock=lambda: self.now)
    def read(self):
        return collect(self.bindings, lambda b: self.clients[b.alias], clock=lambda: self.now)
    def target(self):
        return next(row for row in self.service.status()["findings"] if row["account_alias"] == "lab-dev")
    def prepare(self):
        row = self.target()
        return self.service.prepare(alias="lab-dev", resource_ref=row["resource_ref"], expected_evidence_digest=row["evidence_digest"])
    def test_exact_distinct_bindings(self):
        for values in (tuple(reversed(self.bindings)), self.bindings[:3], tuple(AccountBinding(a, self.bindings[0].account_id) for a in ALIASES)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_bindings(values)
        self.assertNotIn(self.bindings[0].account_id, repr(self.bindings[0]))
    def test_wrong_region_binding(self):
        with self.assertRaises(ValueError):
            AccountBinding("lab-dev", self.bindings[0].account_id, "us-east-1")
    def test_identity_mismatch_no_provider_reads(self):
        client = self.clients["lab-dev"]
        client.account = str(9).zfill(12)
        result = self.read()
        self.assertFalse(result["complete"])
        self.assertEqual(client.calls, ["identity"])
        self.assertEqual(result["accounts"][0]["reason"], "ACCOUNT_MISMATCH")
    def test_identity_unavailable_no_provider_reads(self):
        self.clients["lab-dev"].identity_error = True
        self.assertTrue(self.read()["partial"])
        self.assertEqual(self.clients["lab-dev"].calls, ["identity"])
    def test_client_region_mismatch(self):
        self.clients["lab-dev"].region = "us-east-1"
        self.assertTrue(self.read()["partial"])
        self.assertEqual(self.clients["lab-dev"].calls, [])
    def test_bucket_region_mismatch_or_missing(self):
        for region in (None, "us-east-1"):
            client = self.clients["lab-dev"]
            client.calls.clear()
            client.pages[None]["Buckets"][0]["BucketRegion"] = region
            self.assertTrue(self.read()["partial"])
            self.assertNotIn("policy", client.calls)
    def test_empty_inventory_is_complete(self):
        for client in self.clients.values():
            client.pages = {None: {"Buckets": []}}
        result = self.read()
        self.assertTrue(result["complete"])
        self.assertEqual(result["findings"], [])
    def test_resource_limit_is_explicit(self):
        client = self.clients["lab-dev"]
        names = [f"unit-bucket-{i:02d}" for i in range(20)]
        client.pages = {None: {"Buckets": [{"Name": n, "BucketRegion": REGION} for n in names], "ContinuationToken": "more"}}
        client.policies = dict.fromkeys(names)
        result = self.read()
        self.assertTrue(result["partial"])
        self.assertEqual(result["accounts"][0]["reason"], "RESOURCE_LIMIT")
        self.assertEqual(client.calls.count("policy"), 20)
        self.assertEqual(client.calls.count("list"), 1)
    def test_real_pagination_and_stable_identity(self):
        client = self.clients["lab-dev"]
        client.pages[None]["ContinuationToken"] = "page-two"
        client.pages["page-two"] = {"Buckets": [{"Name": "unit-second", "BucketRegion": REGION}]}
        client.policies["unit-second"] = None
        result = self.read()
        self.assertTrue(result["complete"])
        self.assertEqual(result["accounts"][0]["pages_read"], 2)
        self.assertEqual(result["accounts"][0]["resource_count"], 2)
    def test_cycle_duplicate_and_malformed_page_fail_closed(self):
        scenarios = [
            {None: {"Buckets": [], "ContinuationToken": "x"}, "x": {"Buckets": [], "ContinuationToken": "x"}},
            {None: {"Buckets": [{"Name": BUCKET, "BucketRegion": REGION}] * 2}},
            {None: {"Buckets": "wrong"}},
            {None: {"Buckets": [], "ContinuationToken": ""}},
            {None: {"Buckets": [{"Name": BUCKET, "BucketRegion": REGION}] * 21}},
        ]
        for pages in scenarios:
            with self.subTest(pages=pages):
                client = self.clients["lab-dev"]
                client.pages = pages
                client.calls.clear()
                self.assertTrue(self.read()["partial"])
                self.assertNotIn("policy", client.calls)
    def test_page_budget(self):
        client = self.clients["lab-dev"]
        client.pages = {None if i == 0 else str(i): {"Buckets": [], "ContinuationToken": str(i+1)} for i in range(5)}
        result = self.read()
        self.assertEqual(client.calls.count("list"), 5)
        self.assertEqual(result["accounts"][0]["reason"], "PAGE_LIMIT")
    def test_provider_failure_is_sanitized(self):
        self.clients["lab-dev"].policies[BUCKET] = RuntimeError("NoSuchBucketPolicy private-secret-name")
        result = self.read()
        self.assertTrue(result["partial"])
        self.assertEqual(result["accounts"][0]["findings"][0]["provider_status"], "UNAVAILABLE")
        self.assertNotIn("private-secret-name", json.dumps(result))
    def test_same_status_policy_change_changes_digest_not_finding_id(self):
        self.clients["lab-dev"].policies[BUCKET] = {"Statement": [], "Id": "one"}
        first = self.target()
        self.clients["lab-dev"].policies[BUCKET]["Id"] = "two"
        second = self.target()
        self.assertEqual(first["provider_status"], second["provider_status"])
        self.assertEqual(first["finding_id"], second["finding_id"])
        self.assertNotEqual(first["evidence_digest"], second["evidence_digest"])
    def test_timestamp_change_does_not_change_policy_digest(self):
        first = self.target()
        self.now += 10
        second = self.target()
        self.assertNotEqual(first["observed_at"], second["observed_at"])
        self.assertEqual(first["evidence_digest"], second["evidence_digest"])
    def test_public_safe_report(self):
        output = json.dumps(self.read())
        self.assertNotIn(BUCKET, output)
        for b in self.bindings:
            self.assertNotIn(b.account_id, output)
        self.assertNotIn("provider_policy", output)
    def test_prepare_rereads_changed_evidence(self):
        row = self.target()
        self.clients["lab-dev"].policies[BUCKET] = {"Statement": [], "Id": "changed"}
        with self.assertRaisesRegex(ValueError, "changed"):
            self.service.prepare(alias="lab-dev", resource_ref=row["resource_ref"], expected_evidence_digest=row["evidence_digest"])
    def test_prepare_does_not_accept_fabricated_report(self):
        with self.assertRaises(TypeError):
            self.service.prepare({"findings": []}, alias="lab-dev", resource_ref="fake")
    def test_tampered_digest_rejected(self):
        row = self.target()
        with self.assertRaises(ValueError):
            self.service.prepare(alias="lab-dev", resource_ref=row["resource_ref"], expected_evidence_digest="a" * 64)
    def test_partial_fleet_cannot_prepare(self):
        row = self.target()
        self.clients["lab-sec"].pages = {None: RuntimeError("unavailable")}
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.service.prepare(alias="lab-dev", resource_ref=row["resource_ref"], expected_evidence_digest=row["evidence_digest"])
    def test_unknown_or_compliant_cannot_prepare(self):
        for value in (policy(), {"Statement": [{"Effect": "Allow"}]}):
            self.clients["lab-dev"].policies[BUCKET] = value
            with self.assertRaises(ValueError):
                self.prepare()
    def test_fresh_unique_freezes_and_unchanged_readback(self):
        first, second = self.prepare(), self.prepare()
        self.assertNotEqual(first.batch_id, second.batch_id)
        self.assertFalse(first.live_execution_authorized)
        self.assertTrue(self.service.readback(first)["unchanged"])
    def test_expiry_at_exact_boundary(self):
        frozen = self.prepare()
        self.now = frozen.expires_at
        with self.assertRaisesRegex(ValueError, "expired"):
            self.service.readback(frozen)
    def test_edited_scope_and_unknown_batch_rejected(self):
        frozen = self.prepare()
        with self.assertRaises(ValueError):
            replace(frozen, scope_hash="f" * 64)
        other = S3SslService(self.read, clock=lambda: self.now)
        with self.assertRaises(ValueError):
            other.readback(frozen)
    def test_same_status_changed_readback(self):
        frozen = self.prepare()
        self.clients["lab-dev"].policies[BUCKET] = {"Statement": []}
        result = self.service.readback(frozen)
        self.assertEqual(result["state"], "NON_COMPLIANT")
        self.assertFalse(result["unchanged"])
    def test_unavailable_readback_never_success(self):
        frozen = self.prepare()
        self.clients["lab-dev"].policies[BUCKET] = RuntimeError("access denied")
        result = self.service.readback(frozen)
        self.assertEqual(result["state"], "UNAVAILABLE")
        self.assertFalse(result["unchanged"])
    def test_stale_future_and_invalid_ttl(self):
        from awsops.domain.models import Finding
        finding = Finding(**self.target())
        for kwargs in ({"now": self.now + 61}, {"now": self.now - 1}, {"now": self.now, "ttl": 301}, {"now": self.now, "ttl": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                freeze_finding(finding, **kwargs)
    def test_read_probe_has_no_native_decision(self):
        result = probe(self.service, "lab-dev")
        self.assertEqual(result["outcome"], "PASS")
        self.assertEqual(result["native_decision"], "NOT_RUN")
        self.assertEqual(result["remediation"], "NOT_IMPLEMENTED")
    def test_json_key_order_canonicalization(self):
        self.assertEqual(canonical_digest({"a": 1, "b": 2}), canonical_digest({"b": 2, "a": 1}))


if __name__ == "__main__":
    unittest.main()
