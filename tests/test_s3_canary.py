"""One focused fake-provider proof; no SDK, network, or real AWS operations."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from awsops.domain.models import canonical_digest
from awsops.execution.s3_canary import CanaryAdapter, CanaryBinding, Observation


class FakeProvider:
    mode = "MOCK"

    def __init__(self, clock, binding):
        self.clock, self.binding = clock, binding
        self.policy, self.writes, self.fail_ack, self.fail_read = None, 0, False, False
        self.drift = {}

    def inspect(self, binding):
        if self.fail_read:
            raise RuntimeError("private provider failure must not escape")
        return replace(Observation(binding.account_id, binding.region, binding.bucket,
                                   True, True, self.clock[0], deepcopy(self.policy)), **self.drift)

    def put_policy(self, binding, policy):
        self.writes += 1
        self.policy = deepcopy(policy)
        if self.fail_ack:
            raise RuntimeError("uncertain acknowledgment")


class CanaryProof(unittest.TestCase):
    def test_fixed_approval_readback_and_zero_write_boundaries(self):
        schema = json.loads((Path(__file__).resolve().parents[1] / "contracts/defence-factory/v1.schema.json").read_text())
        def check_envelope(value):
            self.assertEqual(set(value), {"schemaVersion", "kind", "record"})
            self.assertEqual(value["schemaVersion"], "defence-factory/1")
            definition = schema["$defs"][value["kind"].lower()]
            self.assertEqual(set(value["record"]), set(definition["required"]))
            for name, prop in definition["properties"].items():
                if "enum" in prop:
                    self.assertIn(value["record"][name], prop["enum"])
            if value["kind"] == "Run":
                for row in value["record"]["results"]:
                    self.assertEqual(set(row), set(schema["$defs"]["result"]["required"]))
                    for name, prop in schema["$defs"]["result"]["properties"].items():
                        if "enum" in prop:
                            self.assertIn(row[name], prop["enum"])
        principal = canonical_digest("synthetic authenticated owner")
        for scenario in ("approve", "reject", "stale", "drift", "identity", "nonempty", "scope", "principal", "ack", "readback"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                clock = [1800000000]
                binding = CanaryBinding("000000000001", "synthetic-canary")
                provider = FakeProvider(clock, binding)
                path = Path(tmp) / "canary.sqlite"
                adapter = CanaryAdapter(path, binding, provider, source_revision="a" * 40,
                                        source_version="v1.0.0-mock", clock=lambda: clock[0])
                batch = adapter.prepare(principal)
                check_envelope(batch)
                b = batch["record"]
                self.assertEqual(b["targets"][0]["resource"]["accountAlias"], "mock-a")
                self.assertEqual(adapter.binding.account_alias, "amit")
                if scenario == "stale":
                    clock[0] += 301
                if scenario == "drift":
                    provider.policy = {"Statement": []}
                if scenario == "identity":
                    provider.drift = {"account_id": "000000000002"}
                if scenario == "nonempty":
                    provider.drift = {"empty": False}
                provider.fail_ack = scenario == "ack"
                if scenario in ("scope", "principal", "stale"):
                    with self.assertRaises(ValueError):
                        adapter.decide(b["batchId"], "0" * 64 if scenario == "scope" else b["scopeDigest"],
                                       "0" * 64 if scenario == "principal" else principal, "APPROVE_ONCE")
                    self.assertEqual(provider.writes, 0)
                    continue
                if scenario == "readback":
                    original_put = provider.put_policy
                    def put_then_read_failure(binding, policy):
                        original_put(binding, policy)
                        provider.fail_read = True
                    provider.put_policy = put_then_read_failure
                result = adapter.decide(b["batchId"], b["scopeDigest"], principal,
                                        "REJECT" if scenario == "reject" else "APPROVE_ONCE")
                for record in result.values():
                    check_envelope(record)
                run = result["run"]["record"]
                success = scenario in ("approve", "ack", "readback")
                self.assertEqual(provider.writes, int(success))
                self.assertEqual(run["realWrites"], 0)
                self.assertEqual(run["simulatedWrites"], int(success))
                self.assertNotEqual(run["status"], "VERIFIED")
                self.assertEqual(run["results"][0]["compliance"], "UNKNOWN")
                self.assertEqual(run["results"][0]["freshness"], "NOT_VERIFIED")
                if success:
                    self.assertEqual(run["results"][0]["providerReadback"], "UNKNOWN" if scenario == "readback" else "MATCH")
                # Restart proves a persisted claim, not a process-local replay set.
                restarted = CanaryAdapter(path, binding, provider, source_revision="a" * 40,
                                          source_version="v1.0.0-mock", clock=lambda: clock[0])
                with self.assertRaises(ValueError):
                    restarted.decide(b["batchId"], b["scopeDigest"], principal, "APPROVE_ONCE")
                provider.fail_read = False
                reconciled = restarted.reconcile(b["batchId"], principal)
                self.assertEqual(reconciled["run"]["record"]["runId"], run["runId"])
                self.assertEqual(provider.writes, int(success))
                for record in reconciled.values():
                    check_envelope(record)
                exported = json.dumps(result)
                for private in (binding.account_id, binding.bucket, "arn:", "private provider"):
                    self.assertNotIn(private, exported)
        with self.assertRaises(ValueError):
            CanaryBinding("000000000001", "synthetic-canary", account_alias="lab-dev")
        # Projection only: even this non-MOCK preparation uses a fake, never AWS.
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeProvider(clock, binding)
            provider.mode = "APPROVED_LAB_WRITE"
            provider.drift = {"exists": False, "disposable": False, "public_blocked": False}
            adapter = CanaryAdapter(Path(tmp) / "canary.sqlite", binding, provider,
                                    source_revision="a" * 40, source_version="v1.0.0-mock",
                                    clock=lambda: clock[0])
            batch = adapter.prepare(principal)
            self.assertEqual(batch["record"]["targets"][0]["resource"]["accountAlias"], "amit")
            self.assertEqual(provider.writes, 0)


if __name__ == "__main__":
    unittest.main()
