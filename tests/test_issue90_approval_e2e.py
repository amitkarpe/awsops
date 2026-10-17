"""Application-level Issue #90 approval flow; all identities and SDK calls are synthetic."""
from contextlib import redirect_stderr
from dataclasses import replace
import io
import json
from pathlib import Path
import sys
from threading import Barrier
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "scripts")]

from awsops.application.s3_canary_approval import (
    CanaryApprovalApplication, OwnerApprovalPacket, VerifiedOwnerDecision,
)
from awsops.aws.boto3_s3_canary import Boto3CanaryProvider
from awsops.domain.models import canonical_digest
from awsops.execution.s3_canary import CanaryAdapter, CanaryBinding
from test_s3_canary_provider import FakeS3, FakeSession
import s3_canary_operator


SYNTHETIC_ACCOUNT = "999999999999"
SYNTHETIC_BUCKET = "awsops-dev-issue90-s3-canary-zzzzzzzzzzzz"
SYNTHETIC_PRINCIPAL = canonical_digest(["TEST_SIMULATION", "owner-fixture-only"])
SOURCE = "a" * 40


def assert_four_envelope_contract(testcase, envelopes):
    schema = json.loads((ROOT / "contracts/defence-factory/v1.schema.json").read_text())
    testcase.assertEqual([item["kind"] for item in envelopes], ["Batch", "Decision", "Run", "Evidence"])
    for item in envelopes:
        testcase.assertEqual(set(item), {"schemaVersion", "kind", "record"})
        testcase.assertEqual(item["schemaVersion"], "defence-factory/1")
        definition = schema["$defs"][item["kind"].lower()]
        testcase.assertEqual(set(item["record"]), set(definition["required"]))
        for name, prop in definition["properties"].items():
            if "enum" in prop:
                testcase.assertIn(item["record"][name], prop["enum"])
        if item["kind"] == "Run":
            for result in item["record"]["results"]:
                testcase.assertEqual(set(result), set(schema["$defs"]["result"]["required"]))
                for name, prop in schema["$defs"]["result"]["properties"].items():
                    if "enum" in prop:
                        testcase.assertIn(result[name], prop["enum"])


class FakeSdkCanaryProvider(Boto3CanaryProvider):
    """Test-only SDK fake; production provider mode remains write-capable."""
    mode = "MOCK"


class SimulatedOwnerVerifier:
    """Test-only proof generator; it is not imported by application code."""
    def __init__(self, *, wrong_principal: bool = False, verifier_id="TEST_ONLY_SIMULATOR"):
        self.wrong_principal = wrong_principal
        self.verifier_id = verifier_id
        self.actions = []

    def verify(self, packet, authority, *, action, now):
        self.actions.append(action)
        if packet.proof != "TEST_ONLY_SIMULATED_APPROVAL":
            raise ValueError("SIMULATED_PROOF_MISMATCH")
        principal = "0" * 64 if self.wrong_principal else authority.principal_binding_digest
        return VerifiedOwnerDecision(
            packet_digest=packet.digest,
            authority_digest=authority.digest,
            principal_binding_digest=principal,
            decision=packet.decision,
            assurance="TEST_SIMULATION",
            verifier_id=self.verifier_id,
            verified_at=now,
        )


def make_case(directory, *, source_revision=SOURCE, mode="MOCK", verifier=True, cleanup=True,
              cleanup_ttl=3600, clock=None, uncertain=None, principal_digest=SYNTHETIC_PRINCIPAL):
    clock = clock if clock is not None else [1800000000]
    binding = CanaryBinding(SYNTHETIC_ACCOUNT, SYNTHETIC_BUCKET)
    s3 = FakeS3()
    s3.uncertain, s3.clock = uncertain, clock
    ledger = Path(directory) / "canary.sqlite"
    factory_calls = [0]

    def adapter_factory():
        factory_calls[0] += 1
        provider_type = FakeSdkCanaryProvider if mode == "MOCK" else Boto3CanaryProvider
        provider = provider_type(
            FakeSession(s3, account=SYNTHETIC_ACCOUNT), binding, ledger,
            clock=lambda: clock[0], retry_config=object())
        return CanaryAdapter(ledger, binding, provider, source_revision=source_revision,
                             source_version="v1.0.0-mock", clock=lambda: clock[0])

    prep = adapter_factory()
    decision_verifier = SimulatedOwnerVerifier() if verifier is True else verifier
    flow = CanaryApprovalApplication(
        ledger, binding, source_revision=source_revision, source_version="v1.0.0-mock",
        adapter_factory=adapter_factory, mode=mode, verifier=decision_verifier,
        clock=lambda: clock[0])
    cleanup_expiry = clock[0] + cleanup_ttl if cleanup else None
    batch = flow.prepare(
        prep, principal_digest, now=clock[0],
        estimated_incremental_cost_microusd=7000,
        cleanup_reserve_microusd=1000 if cleanup else 0,
        incremental_cost_limit_microusd=9000,
        cleanup_expires_at=cleanup_expiry)
    authority, _ = flow._load_authority(batch["record"]["batchId"])
    packet = OwnerApprovalPacket(
        packet_id="TEST_PACKET_ISSUE90_SYNTHETIC",
        authority_digest=authority.digest,
        principal_binding_digest=principal_digest,
        decision="APPROVE_ONCE",
        issued_at=clock[0],
        expires_at=authority.lifecycle_expires_at,
        proof="TEST_ONLY_SIMULATED_APPROVAL")
    return flow, s3, clock, factory_calls, batch, authority, packet, decision_verifier


class ApprovalApplicationProof(unittest.TestCase):
    def test_one_simulated_packet_covers_approval_cleanup_reconcile_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, s3, _clock, _factory_calls, batch, _authority, packet, verifier = make_case(directory)
            first = flow.decide(packet)
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy"])
            self.assertEqual(first["run"]["record"]["simulatedWrites"], 4)
            self.assertEqual(first["run"]["record"]["realWrites"], 0)
            self.assertEqual(first["evidence"]["record"]["provenance"], "SYNTHETIC")
            self.assertEqual(first["evidence"]["record"]["limitation"], "SYNTHETIC_ONLY")

            replayed = flow.decide(packet)
            self.assertEqual(replayed["run"]["record"]["runId"], first["run"]["record"]["runId"])
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy"])

            self.assertEqual(flow.cleanup(packet), {"status": "DELETED", "deleted": True})
            self.assertEqual(flow.cleanup(packet)["status"], "DELETED_CONFIRMED")
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy", "delete"])
            four = flow.receipt(packet)
            assert_four_envelope_contract(self, four)
            self.assertEqual([item["kind"] for item in four], ["Batch", "Decision", "Run", "Evidence"])
            self.assertEqual(four[2]["record"]["simulatedWrites"], 4)
            audit = flow.audit(packet)
            self.assertEqual(audit["verification"], "TEST_SIMULATION")
            self.assertEqual(audit["provenance"], "SYNTHETIC")
            self.assertEqual(audit["limitation"], "SYNTHETIC_ONLY")
            self.assertEqual(audit["cleanupStatus"], "DELETED_CONFIRMED")
            self.assertTrue(audit["cleanupAttempted"])
            self.assertEqual(audit["cleanupOperationState"], "ACK")
            self.assertEqual(audit["readAuthorization"], "VERIFIED_READ_ONLY")
            self.assertEqual([event["step"] for event in audit["operations"]],
                             ["create", "tags", "public_block", "policy", "delete"])
            exported = json.dumps({"batch": batch, "four": four, "audit": audit})
            self.assertNotIn(SYNTHETIC_ACCOUNT, exported)
            self.assertNotIn(SYNTHETIC_BUCKET, exported)
            self.assertNotIn("TEST_ONLY_SIMULATED_APPROVAL", exported)
            self.assertEqual(verifier.actions, ["DECISION", "DECISION", "CLEANUP", "CLEANUP",
                                                "AUDIT_READ", "AUDIT_READ"])

    def test_reject_is_audited_without_provider_writes_or_cleanup_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, s3, clock, _factory_calls, _batch, authority, packet, _verifier = make_case(
                directory, cleanup=False)
            rejected = replace(packet, decision="REJECT", expires_at=authority.decision_expires_at)
            result = flow.decide(rejected)
            self.assertEqual(s3.writes, [])
            self.assertEqual(result["run"]["record"]["status"], "REJECTED")
            with self.assertRaisesRegex(ValueError, "CLEANUP_AUTHORITY_EXPIRED_OR_MISSING"):
                flow.cleanup(rejected)
            self.assertEqual(s3.writes, [])
            self.assertEqual(clock[0], 1800000000)

    def test_partial_acknowledged_setup_can_use_same_packet_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, s3, _clock, _factory_calls, _batch, _authority, packet, verifier = make_case(directory)
            s3.fail_tags_preflight_after_create = True
            result = flow.decide(packet)
            self.assertEqual(s3.writes, ["create"])
            self.assertEqual(result["run"]["record"]["simulatedWrites"], 1)
            self.assertEqual(flow.cleanup(packet), {"status": "DELETED", "deleted": True})
            self.assertEqual(s3.writes, ["create", "delete"])
            self.assertEqual(flow.receipt(packet)[2]["record"]["simulatedWrites"], 1)
            audit = flow.audit(packet)
            self.assertEqual(audit["cleanupStatus"], "DELETED")
            self.assertTrue(audit["cleanupAttempted"])
            self.assertEqual(verifier.actions,
                             ["DECISION", "CLEANUP", "AUDIT_READ", "AUDIT_READ"])

    def test_uncertain_policy_and_delete_are_reconciled_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, s3, _clock, _factory_calls, _batch, _authority, packet, _verifier = make_case(
                directory, uncertain="policy")
            result = flow.decide(packet)
            self.assertEqual(result["run"]["record"]["simulatedWrites"], 4)
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy"])
            self.assertEqual(flow.decide(packet)["run"]["record"]["runId"],
                             result["run"]["record"]["runId"])
            with self.assertRaisesRegex(ValueError, "CLEANUP_SETUP_UNCERTAIN"):
                flow.cleanup(packet)
            self.assertEqual(s3.writes.count("policy"), 1)
            self.assertNotIn("delete", s3.writes)

        with tempfile.TemporaryDirectory() as directory:
            flow, s3, _clock, _factory_calls, _batch, _authority, packet, _verifier = make_case(directory)
            flow.decide(packet)
            s3.uncertain = "delete"
            self.assertEqual(flow.cleanup(packet), {"status": "UNKNOWN", "deleted": False})
            self.assertEqual(flow.cleanup(packet)["status"], "ABSENT_AFTER_UNKNOWN")
            self.assertEqual(s3.writes.count("delete"), 1)
            self.assertEqual(flow.receipt(packet)[2]["record"]["simulatedWrites"], 4)
            audit = flow.audit(packet)
            self.assertEqual(audit["operations"][-1], {"step": "delete", "state": "CALLING"})
            self.assertTrue(audit["cleanupAttempted"])

    def test_cleanup_expiry_advanced_during_preflight_stops_sdk_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, s3, clock, _factory_calls, _batch, _authority, packet, _verifier = make_case(
                directory, cleanup_ttl=301)
            flow.decide(packet)
            s3.expire_on_cleanup_versions = True
            result = flow.cleanup(packet)
            self.assertEqual(result, {"status": "REFUSED_NO_CALL", "deleted": False})
            self.assertEqual(clock[0], packet.expires_at)
            self.assertNotIn("delete", s3.writes)
            self.assertEqual(flow.audit(packet)["operations"][-1],
                             {"step": "delete", "state": "REFUSED"})

    def test_missing_invalid_or_test_only_decision_blocks_before_provider_factory(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, _s3, _clock, factory_calls, _batch, _authority, packet, _verifier = make_case(
                directory, mode="APPROVED_LAB_WRITE", verifier=None)
            factory_calls[0] = 0
            with self.assertRaisesRegex(ValueError, "TRUSTED_HUMAN_APPROVAL_BINDING_REQUIRED"):
                flow.decide(packet)
            self.assertEqual(factory_calls[0], 0)

        with tempfile.TemporaryDirectory() as directory:
            bad_verifier = SimulatedOwnerVerifier(wrong_principal=True)
            flow, _s3, _clock, factory_calls, _batch, _authority, packet, _ = make_case(
                directory, mode="APPROVED_LAB_WRITE", verifier=bad_verifier)
            factory_calls[0] = 0
            with self.assertRaisesRegex(ValueError, "OWNER_DECISION_VERIFICATION_FAILED"):
                flow.decide(packet)
            self.assertEqual(factory_calls[0], 0)

        with tempfile.TemporaryDirectory() as directory:
            flow, _s3, _clock, factory_calls, _batch, _authority, packet, _ = make_case(directory)
            live_verification = SimulatedOwnerVerifier()
            flow.verifier = live_verification
            flow.mode = "APPROVED_LAB_WRITE"
            factory_calls[0] = 0
            with self.assertRaisesRegex(ValueError, "TEST_SIMULATION_CANNOT_AUTHORIZE_LIVE_PROVIDER"):
                flow.decide(packet)
            self.assertEqual(factory_calls[0], 0)

    def test_packet_authority_drift_and_expiry_never_construct_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, _s3, clock, factory_calls, _batch, authority, packet, _verifier = make_case(directory)
            variants = (
                replace(authority, scope_digest="0" * 64),
                replace(authority, source_revision="b" * 40),
                replace(authority, resource_binding_digest="0" * 64,
                        cleanup=replace(authority.cleanup, resource_binding_digest="0" * 64)),
                replace(authority, incremental_cost_limit_microusd=10000),
                replace(authority, cleanup=replace(authority.cleanup, expires_at=authority.cleanup.expires_at + 60)),
            )
            for changed in variants:
                with self.subTest(authority=changed):
                    factory_calls[0] = 0
                    changed_packet = replace(packet, authority_digest=changed.digest,
                                             expires_at=changed.lifecycle_expires_at)
                    with self.assertRaises(ValueError):
                        flow.decide(changed_packet)
                    self.assertEqual(factory_calls[0], 0)

            wrong_owner = replace(packet, principal_binding_digest="0" * 64)
            with self.assertRaisesRegex(ValueError, "APPROVAL_PACKET_SCOPE_OR_EXPIRY_MISMATCH"):
                flow.decide(wrong_owner)
            self.assertEqual(factory_calls[0], 0)

            clock[0] = authority.decision_expires_at
            with self.assertRaisesRegex(ValueError, "APPROVAL_DECISION_EXPIRED"):
                flow.decide(packet)
            self.assertEqual(factory_calls[0], 0)

    def test_current_source_and_private_binding_drift_block_before_provider_factory(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, s3, _clock, factory_calls, _batch, _authority, packet, _verifier = make_case(directory)
            factory_calls[0] = 0
            flow.revision = "b" * 40
            with self.assertRaisesRegex(ValueError, "APPLICATION_SOURCE_DRIFT"):
                flow.decide(packet)
            self.assertEqual(factory_calls[0], 0)
            self.assertEqual(s3.writes, [])

            flow.revision = SOURCE
            flow.binding = CanaryBinding(SYNTHETIC_ACCOUNT,
                                         "awsops-dev-issue90-s3-canary-foreign")
            with self.assertRaisesRegex(ValueError, "APPLICATION_PRIVATE_BINDING_DRIFT"):
                flow.decide(packet)
            self.assertEqual(factory_calls[0], 0)
            self.assertEqual(s3.writes, [])

    def test_distinct_packet_race_has_one_audit_winner_and_replay_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, s3, _clock, factory_calls, _batch, _authority, packet, _ = make_case(directory)
            other = replace(packet, packet_id="TEST_PACKET_ISSUE90_OTHER")
            barrier = Barrier(2)
            delegate = SimulatedOwnerVerifier()

            class RacingVerifier:
                def verify(self, value, authority, *, action, now):
                    result = delegate.verify(value, authority, action=action, now=now)
                    if action == "DECISION":
                        barrier.wait(timeout=10)
                    return result

            flow.verifier = RacingVerifier()
            factory_calls[0] = 0

            def decide(value):
                try:
                    return (value, flow.decide(value), None)
                except ValueError as exc:
                    return (value, None, str(exc))

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(decide, (packet, other)))
            winners = [row for row in outcomes if row[1] is not None]
            losers = [row for row in outcomes if row[2] is not None]
            self.assertEqual(len(winners), 1)
            self.assertEqual([row[2] for row in losers], ["APPROVAL_ALREADY_CONSUMED"])
            winning_packet = winners[0][0]
            losing_packet = other if winning_packet.digest == packet.digest else packet
            self.assertEqual(factory_calls[0], 1)
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy"])

            winning_audit = flow.audit(winning_packet)
            self.assertEqual(winning_audit["packetDigest"], winning_packet.digest)
            self.assertEqual(winning_audit["decision"], "APPROVE_ONCE")
            self.assertEqual(winning_audit["verifierId"], "TEST_ONLY_SIMULATOR")

            # Verification is pure; the durable CAS, not the verifier, consumes
            # the decision. A replay cannot rewrite the winning audit identity.
            flow.verifier = SimulatedOwnerVerifier(verifier_id="TEST_ONLY_REPLAY_VERIFIER")
            replay = flow.decide(winning_packet)
            self.assertEqual(replay["run"]["record"]["simulatedWrites"], 4)
            self.assertEqual(flow.audit(winning_packet)["verifierId"], "TEST_ONLY_SIMULATOR")
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy"])
            self.assertEqual(factory_calls[0], 2)  # Initial winner plus read-only replay.
            with self.assertRaisesRegex(ValueError, "APPROVAL_ALREADY_CONSUMED"):
                flow.decide(losing_packet)
            self.assertEqual(factory_calls[0], 2)

    def test_expired_packet_blocks_mutation_but_allows_verified_durable_read(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, s3, clock, factory_calls, _batch, _authority, packet, verifier = make_case(directory)
            flow.decide(packet)
            writes = list(s3.writes)
            clock[0] = packet.expires_at
            factory_calls[0] = 0
            with self.assertRaisesRegex(ValueError, "APPROVAL_PACKET_SCOPE_OR_EXPIRY_MISMATCH"):
                flow.decide(packet)
            with self.assertRaisesRegex(ValueError, "APPROVAL_PACKET_SCOPE_OR_EXPIRY_MISMATCH"):
                flow.cleanup(packet)
            self.assertEqual(factory_calls[0], 0)
            self.assertEqual(s3.writes, writes)

            audit = flow.audit(packet)
            self.assertEqual(audit["readAuthorization"], "VERIFIED_READ_ONLY")
            self.assertEqual(audit["cleanupAttempted"], False)
            receipt = flow.receipt(packet)
            self.assertEqual(receipt[2]["record"]["simulatedWrites"], 4)
            self.assertEqual(s3.writes, writes)
            self.assertEqual(verifier.actions[-2:], ["AUDIT_READ", "AUDIT_READ"])

    def test_decision_and_initial_audit_commit_together_for_restart_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            flow, s3, _clock, _factory_calls, _batch, _authority, packet, _verifier = make_case(directory)
            adapter_factory = flow.adapter_factory

            def stop_after_decision_commit():
                adapter = adapter_factory()
                adapter._read = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("simulated stop"))
                return adapter

            flow.adapter_factory = stop_after_decision_commit
            result = flow.decide(packet)
            self.assertEqual(result["run"]["record"]["simulatedWrites"], 0)
            self.assertEqual(s3.writes, [])
            flow.adapter_factory = adapter_factory
            restarted = CanaryApprovalApplication(
                Path(directory) / "canary.sqlite", flow.binding, source_revision=SOURCE,
                source_version="v1.0.0-mock", adapter_factory=adapter_factory,
                mode="MOCK", verifier=flow.verifier, clock=flow.clock)
            recovered = restarted.decide(packet)
            self.assertEqual(recovered["run"]["record"]["runId"], result["run"]["record"]["runId"])
            self.assertEqual(s3.writes, [])

    def test_real_operator_default_deny_does_not_construct_provider(self):
        stderr = io.StringIO()
        with patch.object(s3_canary_operator, "adapter_for") as factory, redirect_stderr(stderr):
            result = s3_canary_operator.main([
                "approve", "--bucket", SYNTHETIC_BUCKET,
                "--batch-id", "batch-canary-" + "1" * 32,
                "--scope-digest", "a" * 64])
        self.assertEqual(result, 2)
        factory.assert_not_called()
        self.assertIn("TRUSTED_HUMAN_APPROVAL_BINDING_REQUIRED", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
