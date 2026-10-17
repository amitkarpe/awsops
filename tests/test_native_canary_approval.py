"""Native callback bridge contract; approval is synthetic and MOCK-only."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from awsops.application.s3_canary_approval import VerifiedOwnerDecision
from awsops.domain.models import canonical_digest
from awsops.runtime.native_canary_approval import (
    NativeCanaryApprovalAdapter,
    NativeCanaryDecision,
    NativeCanaryBinding,
)
from awsops.runtime.receipt_stdio import dispatch as receipt_dispatch
from test_issue90_approval_e2e import assert_four_envelope_contract, make_case


class SimulatedNativeVerifier:
    """Test-only verifier. It cannot authorize a non-MOCK app."""
    def __init__(self, context):
        self.context = context

    def verify(self, packet, authority, *, action, now):
        context = self.context
        if (context.batch_id != authority.batch_id
                or context.authority_digest != authority.digest
                or context.scope_digest != authority.scope_digest
                or context.source_revision != authority.source_revision
                or context.principal_id != "test-owner"
                or context.tenant_id != "tenant:test-tenant"
                or packet.proof != context.digest
                or packet.issued_at != context.decided_at
                or packet.decision != ("APPROVE_ONCE" if context.decision == "approve" else "REJECT")
                or action not in ("DECISION", "CLEANUP", "AUDIT_READ")
                or now < context.decided_at):
            raise ValueError("SIMULATED_NATIVE_BINDING_MISMATCH")
        if action == "DECISION" and now >= min(context.expires_at, authority.decision_expires_at):
            raise ValueError("SIMULATED_NATIVE_DECISION_EXPIRED")
        if action == "CLEANUP" and (not authority.cleanup.enabled or now >= authority.cleanup.expires_at):
            raise ValueError("SIMULATED_NATIVE_CLEANUP_EXPIRED")
        return VerifiedOwnerDecision(
            packet_digest=packet.digest,
            authority_digest=authority.digest,
            principal_binding_digest=authority.principal_binding_digest,
            decision=packet.decision,
            assurance="TEST_SIMULATION",
            verifier_id="TEST_ONLY_NATIVE_SIMULATOR",
            verified_at=now,
        )


def native_callback(authority, *, now=1800000000, decision="approve", claimed=True):
    if not claimed:
        raise ValueError("NATIVE_PAUSE_CLAIM_REQUIRED")
    source = r'''
const gate = require(process.argv[1]);
const config = {version:1, enabled:true, agent_id:'test-agent', python:process.argv[8],
  source_root:process.argv[9], database:process.argv[9]+'/unused-native.sqlite', source_revision:process.argv[10],
  application_database:process.argv[9]+'/unused-application.sqlite',
  application_binding:process.argv[9]+'/unused-binding.json', source_version:'v1.0.0-mock'};
const pending = {actionId:'test-action', expiresAt:Number(process.argv[7])*1000,
  payload:{type:'tool_approval', action_requests:[{name:gate.CANARY_WIRE_TOOL, tool_call_id:'test-call',
    arguments:{control:'s3_canary', batch_id:process.argv[2], scope_digest:process.argv[3], authority_digest:process.argv[4]}}],
    review_configs:[{tool_call_id:'test-call', allowed_decisions:['approve','reject']} ]}};
const job = {status:'requires_action', createdAt:1800000000, metadata:{userId:'test-owner',tenantId:'test-tenant',
  agent_id:'test-agent',endpoint:'agents',pendingAction:pending}};
const req = {user:{id:'test-owner',tenantId:'test-tenant'},body:{conversationId:'test-conversation',actionId:'test-action',
  generationCreatedAt:1800000000,agent_id:'test-agent',endpoint:'agents',decisions:[{tool_call_id:'test-call',decision:process.argv[5]}]}};
const prepared = gate.prepareNativeCanaryRequest({req,job,pendingAction:pending,streamId:'test-conversation'},config);
// Model the host's one-winner pause CAS and reread its committed generation.
let state = job.status;
const claimed = state === 'requires_action'; if (claimed) state = 'running';
const liveJob = {...job,status:state,metadata:{...job.metadata}};
if (claimed) { delete liveJob.metadata.pendingAction; delete liveJob.metadata.pendingActionId; }
gate.afterNativeCanaryClaim({req,job,pendingAction:pending,streamId:'test-conversation',prepared,
  claimResult:claimed,manager:{getJob:async()=>liveJob}},config, callback=>callback)
  .then(value=>process.stdout.write(JSON.stringify(value)));
'''
    return json.loads(subprocess.run(
        ["node", "-e", source, str(ROOT / "integration/librechat/native_gate.cjs"),
         authority.batch_id, authority.scope_digest, authority.digest, decision, str(now),
         str(authority.decision_expires_at), sys.executable, str(ROOT), authority.source_revision], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout)


def native_context(authority, *, now=1800000000, decision="approve", claimed=True):
    return NativeCanaryDecision.from_host_callback(
        native_callback(authority, now=now, decision=decision, claimed=claimed),
        authority, received_at=now)


class NativeCanaryApprovalTests(unittest.TestCase):
    def test_production_reject_recorder_uses_application_packet_claim_and_canonical_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            now = int(time.time())
            principal = canonical_digest({"principal_id": "test-owner", "tenant_id": "tenant:test-tenant"})
            app, s3, _clock, factory_calls, _batch, authority, _packet, _ = make_case(
                directory, principal_digest=principal, clock=[now])
            native = {"version": 1, "operation": "native_canary_reject",
                "batch_id": authority.batch_id, "authority_digest": authority.digest,
                "scope_digest": authority.scope_digest, "source_revision": authority.source_revision,
                "decision": "reject", "decided_at": now,
                "expires_at": authority.decision_expires_at,
                "binding": {"principal_id": "test-owner", "tenant_id": "tenant:test-tenant",
                    "conversation_id": "conversation-1", "action_id": "action-1",
                    "generation_id": str(now), "tool_call_id": "call-1",
                    "tool": "approve_s3_canary_once"}}
            result = receipt_dispatch(None, native, None, app.path,
                {"account_id": app.binding.account_id, "bucket": app.binding.bucket}, app.version)
            application = result["application_result"]
            self.assertEqual(application["decision"]["record"]["choice"], "REJECT")
            self.assertEqual(application["run"]["record"]["status"], "REJECTED")
            self.assertEqual(application["run"]["record"]["realWrites"], 0)
            self.assertEqual(application["run"]["record"]["simulatedWrites"], 0)
            self.assertEqual([item["kind"] for item in result["application_receipts"]],
                             ["Batch", "Decision", "Run", "Evidence"])
            saved = app._load_authority(authority.batch_id)[1]
            self.assertIsNotNone(saved[0])
            self.assertEqual(saved[3], "REJECT")
            self.assertEqual(s3.writes, [])
            self.assertEqual(factory_calls[0], 1)  # only setup's fixture adapter was constructed

    def test_native_approval_cleanup_and_audit_use_one_packet_and_keep_cleanup_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            app, s3, _clock, factory_calls, _batch, authority, _packet, _ = make_case(directory)
            factory_calls[0] = 0
            context = native_context(authority)
            bridge = NativeCanaryApprovalAdapter(app, SimulatedNativeVerifier(context))

            result = bridge.decide(context)
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy"])
            self.assertEqual(result["run"]["record"]["simulatedWrites"], 4)
            self.assertEqual(result["run"]["record"]["realWrites"], 0)
            self.assertEqual(result["evidence"]["record"]["provenance"], "SYNTHETIC")
            self.assertEqual(result["evidence"]["record"]["limitation"], "SYNTHETIC_ONLY")
            assert_four_envelope_contract(self, [result[k] for k in ("batch", "decision", "run", "evidence")])

            # Same context replay reconciles the same packet without dispatching again.
            self.assertEqual(bridge.decide(context)["run"]["record"]["runId"], result["run"]["record"]["runId"])
            self.assertEqual(bridge.cleanup(context), {"status": "DELETED", "deleted": True})
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy", "delete"])
            audit = bridge.audit(context)
            self.assertEqual(audit["decision"], "APPROVE_ONCE")
            self.assertEqual(audit["verification"], "TEST_SIMULATION")
            self.assertEqual(audit["cleanupOperationState"], "ACK")
            self.assertEqual(audit["operations"][-1], {"step": "delete", "state": "ACK"})
            public = json.dumps({"result": result, "receipt": bridge.receipt(context), "audit": audit})
            self.assertNotIn("test-owner", public)
            self.assertNotIn("test-conversation", public)
            self.assertNotIn(context.digest, public)
            self.assertEqual(factory_calls[0], 4)  # decision, replay, cleanup, audit

    def test_missing_trusted_verifier_and_unwon_pause_claim_fail_before_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            app, s3, _clock, factory_calls, _batch, authority, _packet, _ = make_case(directory)
            factory_calls[0] = 0
            context = native_context(authority)
            with self.assertRaisesRegex(ValueError, "TRUSTED_HUMAN_APPROVAL_BINDING_REQUIRED"):
                NativeCanaryApprovalAdapter(app).decide(context)
            self.assertEqual(factory_calls[0], 0)
            self.assertEqual(s3.writes, [])

            with self.assertRaisesRegex(ValueError, "NATIVE_PAUSE_CLAIM_REQUIRED"):
                native_context(authority, claimed=False)
            self.assertEqual(factory_calls[0], 0)
            self.assertEqual(s3.writes, [])

    def test_native_binding_and_canonical_authority_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            app, s3, _clock, factory_calls, _batch, authority, _packet, _ = make_case(directory)
            factory_calls[0] = 0
            altered = native_context(authority)
            other = replace(altered, authority_digest=canonical_digest(["other-owner"]))
            with self.assertRaisesRegex(ValueError, "NATIVE_OWNER_DECISION_BINDING_MISMATCH"):
                NativeCanaryApprovalAdapter(app, SimulatedNativeVerifier(other)).decide(other)
            extended = replace(altered, expires_at=authority.decision_expires_at + 1)
            with self.assertRaisesRegex(ValueError, "NATIVE_OWNER_DECISION_BINDING_MISMATCH"):
                NativeCanaryApprovalAdapter(app, SimulatedNativeVerifier(extended)).decide(extended)
            wrong_tool = native_callback(authority)
            wrong_tool["binding"]["tool"] = "decide_s3_ssl_reject_only"
            with self.assertRaisesRegex(ValueError, "UNSUPPORTED_NATIVE_CANARY_TOOL"):
                NativeCanaryDecision.from_host_callback(wrong_tool, authority, received_at=1800000000)
            self.assertEqual(factory_calls[0], 0)
            self.assertEqual(s3.writes, [])

    def test_simulated_callback_cannot_authorize_live_provider_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            app, s3, _clock, factory_calls, _batch, authority, _packet, _ = make_case(directory)
            factory_calls[0] = 0
            app.mode = "APPROVED_LAB_WRITE"
            context = native_context(authority)
            with self.assertRaisesRegex(ValueError, "TEST_SIMULATION_CANNOT_AUTHORIZE_LIVE_PROVIDER"):
                NativeCanaryApprovalAdapter(app, SimulatedNativeVerifier(context)).decide(context)
            self.assertEqual(factory_calls[0], 0)
            self.assertEqual(s3.writes, [])

    def test_distinct_native_contexts_have_one_durable_packet_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            app, s3, _clock, factory_calls, _batch, authority, _packet, _ = make_case(directory)
            factory_calls[0] = 0
            first = native_context(authority)
            second = replace(first, native_binding=replace(first.native_binding, action_id="other-action"))
            second = replace(second, decision_record_hash=second.digest)
            barrier = Barrier(2)

            class RacingVerifier(SimulatedNativeVerifier):
                def verify(self, packet, authority, *, action, now):
                    result = super().verify(packet, authority, action=action, now=now)
                    if action == "DECISION":
                        barrier.wait(timeout=10)
                    return result

            bridges = [NativeCanaryApprovalAdapter(app, RacingVerifier(context))
                       for context in (first, second)]

            def decide(pair):
                bridge, context = pair
                try:
                    return context, bridge.decide(context), None
                except ValueError as exc:
                    return context, None, str(exc)

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(decide, zip(bridges, (first, second))))
            winners = [item for item in outcomes if item[1] is not None]
            losers = [item for item in outcomes if item[2] is not None]
            self.assertEqual(len(winners), 1)
            self.assertEqual([item[2] for item in losers], ["APPROVAL_ALREADY_CONSUMED"])
            winning_context = winners[0][0]
            winning_bridge = bridges[0] if winning_context is first else bridges[1]
            self.assertEqual(winning_bridge.audit(winning_context)["packetDigest"],
                             winning_bridge._bound_application(winning_context)[1].digest)
            self.assertEqual(s3.writes, ["create", "tags", "public_block", "policy"])
            self.assertEqual(factory_calls[0], 1)

    def test_expired_callback_blocks_mutation_but_keeps_read_only_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            app, s3, clock, factory_calls, _batch, authority, _packet, _ = make_case(directory)
            factory_calls[0] = 0
            context = native_context(authority)
            bridge = NativeCanaryApprovalAdapter(app, SimulatedNativeVerifier(context))
            bridge.decide(context)
            prior_writes = list(s3.writes)
            clock[0] = authority.decision_expires_at
            factory_calls[0] = 0
            with self.assertRaisesRegex(ValueError, "APPROVAL_DECISION_EXPIRED"):
                bridge.decide(context)
            self.assertEqual(factory_calls[0], 0)
            self.assertEqual(s3.writes, prior_writes)
            audit = bridge.audit(context)
            self.assertEqual(audit["readAuthorization"], "VERIFIED_READ_ONLY")
            self.assertEqual(s3.writes, prior_writes)


if __name__ == "__main__":
    unittest.main()
