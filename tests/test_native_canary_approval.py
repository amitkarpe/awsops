"""Native callback bridge contract; approval is synthetic and MOCK-only."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sqlite3
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
from awsops.runtime.prepare_native_canary import prepare_native_canary
from awsops.approval.decisions import DecisionStore
from test_issue90_approval_e2e import assert_four_envelope_contract, make_case
from test_s3_canary_provider import FakeS3, FakeSession


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
const config = {version:1, enabled:true, agent_id:'test-agent', python:'/usr/bin/python3',
  source_root:process.argv[9], database:process.argv[11], source_revision:process.argv[10],
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
    with tempfile.TemporaryDirectory(prefix="native-callback-db-") as directory:
        state = Path(directory) / "state"
        state.mkdir(mode=0o700)
        database = state / "native.sqlite"
        DecisionStore(database)
        return json.loads(subprocess.run(
            ["node", "-e", source, str(ROOT / "integration/librechat/native_gate.cjs"),
             authority.batch_id, authority.scope_digest, authority.digest, decision, str(now),
             str(authority.decision_expires_at), sys.executable, str(ROOT), authority.source_revision,
             str(database)], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout)


def native_context(authority, *, now=1800000000, decision="approve", claimed=True):
    return NativeCanaryDecision.from_host_callback(
        native_callback(authority, now=now, decision=decision, claimed=claimed),
        authority, received_at=now)


class NativeCanaryApprovalTests(unittest.TestCase):
    def test_authenticated_pause_producer_freshly_prepares_fixed_target_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            now = 1800000000
            bucket = "awsops-dev-issue90-s3-canary-0123456789ab"
            account = "000000000001"
            binding_file = root / "binding.json"
            binding_file.write_text(json.dumps({"account_id": account, "bucket": bucket}))
            binding_file.chmod(0o600)
            read_config = root / "read.json"
            read_config.write_text(json.dumps({
                "region": "ap-southeast-1", "source_account_id": account, "profile": "amit",
                "accounts": [{"alias": alias, "account_id": str(i).zfill(12)}
                             for i, alias in enumerate(("lab-dev", "lab-poc", "lab-qa", "lab-sec"), 1)]
            }))
            # load_config requires the exact registered LAB aliases; the fixed
            # canary account must also be the selected source identity.
            config_value = json.loads(read_config.read_text())
            config_value["accounts"][0]["account_id"] = account
            read_config.write_text(json.dumps(config_value))
            read_config.chmod(0o600)
            source_file = root / "SOURCE_REVISION"
            source_file.write_text("a" * 40 + "\n")
            source_file.chmod(0o644)
            ledger = root / "canary.sqlite"
            fake_s3 = FakeS3()
            fake_s3.clock = [now]
            def session_factory(*, profile_name, region_name):
                self.assertEqual((profile_name, region_name), ("amit", "ap-southeast-1"))
                return FakeSession(fake_s3, account=account)
            from awsops.aws.boto3_s3_canary import Boto3CanaryProvider
            def provider_factory(session, binding, path):
                return Boto3CanaryProvider(session, binding, path, clock=lambda: fake_s3.clock[0],
                                           retry_config=object())
            message = {"version": 1, "operation": "prepare_native_canary",
                "binding": {"principal_id": "authenticated-owner", "tenant_id": "tenant:home",
                    "conversation_id": "conversation-1", "action_id": "action-1",
                    "generation_id": str(now), "tool_call_id": "call-1",
                    "tool": "approve_s3_canary_once"}, "pause_expires_at": now + 300}
            native_ledger = root / "native.sqlite"
            result = prepare_native_canary(message, database=ledger, native_database=native_ledger,
                binding_file=binding_file,
                read_config=read_config, source_revision="a" * 40, source_version="v1.0.0-mock",
                source_revision_file=source_file,
                session_factory=session_factory, provider_factory=provider_factory,
                clock=lambda: fake_s3.clock[0])
            self.assertTrue(result["ok"])
            self.assertFalse(result["dispatch_allowed"])
            self.assertEqual(result["control"], "s3_canary")
            self.assertEqual(result["expires_at"], now + 300)
            self.assertEqual(fake_s3.writes, [])
            self.assertEqual(native_ledger.stat().st_mode & 0o777, 0o600)
            self.assertEqual(ledger.stat().st_mode & 0o777, 0o600)
            with sqlite3.connect(native_ledger) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
            from awsops.application.s3_canary_approval import CanaryApprovalApplication
            from awsops.execution.s3_canary import CanaryBinding
            app = CanaryApprovalApplication(ledger, CanaryBinding(account, bucket),
                source_revision="a" * 40, source_version="v1.0.0-mock",
                adapter_factory=lambda: None, mode="APPROVED_LAB_WRITE", clock=lambda: fake_s3.clock[0])
            authority, _ = app._load_authority(result["batch_id"])
            self.assertEqual(authority.digest, result["authority_digest"])
            self.assertEqual(authority.principal_binding_digest,
                canonical_digest({"principal_id": "authenticated-owner", "tenant_id": "tenant:home"}))
            self.assertEqual(authority.allowed_actions, ("create", "tags", "public_block", "policy"))
            with sqlite3.connect(ledger) as db:
                db.execute("INSERT INTO canaries VALUES (?,?,?,?,?,?)",
                    ("preserved-sentinel", "{}", "existing-principal", "existing-binding", None, None))
            from awsops.runtime.prepare_native_canary import _provision_ledgers
            from awsops.execution.s3_canary import CanaryBinding
            _provision_ledgers(native_ledger, ledger, CanaryBinding(account, bucket),
                source_revision="a" * 40, source_version="v1.0.0-mock", clock=lambda: fake_s3.clock[0])
            with sqlite3.connect(ledger) as db:
                self.assertEqual(db.execute("SELECT payload FROM canaries WHERE batch_id=?",
                    ("preserved-sentinel",)).fetchone(), ("{}",))
            self.assertEqual(fake_s3.writes, [])
            expiring_ledger = root / "expiring.sqlite"
            fake_s3.clock[0] = now
            def expiring_provider(session, binding, path):
                provider = Boto3CanaryProvider(session, binding, path,
                    clock=lambda: fake_s3.clock[0], retry_config=object())
                inspect = provider.inspect
                def delayed_inspect(*args, **kwargs):
                    fake_s3.clock[0] += 5
                    return inspect(*args, **kwargs)
                provider.inspect = delayed_inspect
                return provider
            short_pause = {**message, "pause_expires_at": now + 5}
            with self.assertRaisesRegex(ValueError, "CANARY_PREPARATION_EXPIRED"):
                prepare_native_canary(short_pause, database=expiring_ledger, binding_file=binding_file,
                    read_config=read_config, source_revision="a" * 40, source_version="v1.0.0-mock",
                    source_revision_file=source_file, session_factory=session_factory,
                    provider_factory=expiring_provider, clock=lambda: fake_s3.clock[0])
            with sqlite3.connect(expiring_ledger) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM canaries").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM application_authority").fetchone()[0], 0)
            missing_binding = root / "missing-binding.private.json"
            missing_application_ledger = root / "missing-canary.sqlite"
            missing_native_ledger = root / "missing-native.sqlite"
            with self.assertRaisesRegex(ValueError, "PRIVATE_RUNTIME_FILE_REQUIRED"):
                prepare_native_canary(message, database=missing_application_ledger,
                    native_database=missing_native_ledger, binding_file=missing_binding,
                    read_config=read_config, source_revision="a" * 40,
                    source_version="v1.0.0-mock", source_revision_file=source_file,
                    session_factory=session_factory,
                    provider_factory=lambda *_args: self.fail("provider before binding readiness"),
                    clock=lambda: fake_s3.clock[0])
            self.assertFalse(missing_application_ledger.exists())
            self.assertFalse(missing_native_ledger.exists())
            source_file.write_text("b" * 40 + "\n")
            with self.assertRaisesRegex(ValueError, "SOURCE_REVISION_DRIFT"):
                prepare_native_canary(message, database=ledger, binding_file=binding_file,
                    read_config=read_config, source_revision="a" * 40, source_version="v1.0.0-mock",
                    source_revision_file=source_file, session_factory=session_factory,
                    provider_factory=lambda *_args: self.fail("provider construction preceded source check"),
                    clock=lambda: fake_s3.clock[0])

    def test_default_node_dispatch_runs_private_child_and_reopens_synthetic_reject_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            now = int(time.time())
            # Synthetic identity + inert fake SDK; APPROVED_LAB_WRITE only lets
            # the existing application path accept the deliberately synthetic reject fixture.
            principal = canonical_digest({"principal_id": "test-owner", "tenant_id": "tenant:test-tenant"})
            app, fake_s3, _clock, _factory_calls, _batch, authority, _packet, _ = make_case(
                directory, mode="APPROVED_LAB_WRITE", principal_digest=principal, clock=[now])
            native_db = Path(directory) / "native.sqlite"
            DecisionStore(native_db)
            binding_file = Path(directory) / "private-binding.json"
            binding_file.write_text(json.dumps({"account_id": app.binding.account_id, "bucket": app.binding.bucket}))
            binding_file.chmod(0o600)
            record = {"version": 1, "operation": "native_canary_reject",
                "batch_id": authority.batch_id, "authority_digest": authority.digest,
                "scope_digest": authority.scope_digest, "source_revision": authority.source_revision,
                "decision": "reject", "decided_at": now,
                "expires_at": authority.decision_expires_at,
                "binding": {"principal_id": "test-owner", "tenant_id": "tenant:test-tenant",
                    "conversation_id": "conversation-test", "action_id": "action-test",
                    "generation_id": str(now), "tool_call_id": "call-test",
                    "tool": "approve_s3_canary_once"}}
            source = r"""
const gate = require(process.argv[1]);
const config = {version:1, enabled:true, agent_id:'test-agent', python:process.argv[2],
  source_root:process.argv[3], database:process.argv[4], source_revision:process.argv[7],
  application_database:process.argv[5], application_binding:process.argv[6], source_version:'v1.0.0-mock'};
const record = JSON.parse(process.argv[8]);
(async () => {
  const first = await gate.dispatchNativeCanaryReject(config, record);
  const reopened = await gate.dispatchNativeCanaryReject(config, record);
  process.stdout.write(JSON.stringify({first, reopened, bytes:Buffer.byteLength(JSON.stringify({first,reopened}))}));
})().catch(() => { process.exitCode = 2; });
"""
            output = subprocess.run([
                "node", "-e", source, str(ROOT / "integration/librechat/native_gate.cjs"),
                sys.executable, str(ROOT), str(native_db), str(app.path), str(binding_file),
                authority.source_revision, json.dumps(record, separators=(",", ":")),
            ], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
            result = json.loads(output)
            for attempt in (result["first"], result["reopened"]):
                receipts = attempt["receipts"]
                self.assertEqual([item["kind"] for item in receipts], ["Batch", "Decision", "Run", "Evidence"])
                self.assertEqual(receipts[1]["record"]["choice"], "REJECT")
                self.assertEqual(receipts[2]["record"]["status"], "REJECTED")
                self.assertEqual(receipts[2]["record"]["realWrites"], 0)
                self.assertEqual(receipts[2]["record"]["simulatedWrites"], 0)
                self.assertEqual(attempt["resumeValue"]["call-test"], {"type": "reject", "reason": "REJECTED"})
            self.assertEqual(result["first"]["receipts"], result["reopened"]["receipts"])
            self.assertLess(result["bytes"], 16_384)
            with sqlite3.connect(app.path) as db:
                saved = db.execute("SELECT packet_digest,choice FROM application_authority WHERE batch_id=?",
                                   (authority.batch_id,)).fetchone()
            self.assertIsNotNone(saved[0])
            self.assertEqual(saved[1], "REJECT")
            self.assertEqual(fake_s3.writes, [])

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
