"""Provider-first pause binding; providers are synthetic, store is genuine."""
from copy import deepcopy
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from test_s3_ssl import FakeClient, bindings, collect, policy, BUCKET
from awsops.approval.decisions import DecisionStore, NativeBinding
from awsops.runtime.prepare_pause import prepare_and_register, _private_config
from awsops.runtime.native_decision import NativeDecisionAdapter
from awsops.runtime.s3_ssl_service import S3SslService


class PreparePauseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "ledger.sqlite3"
        self.now = 10000
        self.clock = lambda: self.now
        self.bound = bindings()
        self.clients = {b.alias: FakeClient(b.account_id) for b in self.bound}
        self.service = S3SslService(lambda: collect(self.bound, lambda b: self.clients[b.alias], clock=self.clock), clock=self.clock)
        self.store = DecisionStore(self.db, clock=self.clock)
        self.binding = NativeBinding("native-user", "system:single-tenant", "conversation-1", "action-1", "123", "call-1")
        from dataclasses import asdict
        target = self.service.status()["findings"][0]
        self.message = {"version":1, "operation":"prepare_pause", "binding":asdict(self.binding),
                        "pause_expires_at":self.now+120, "candidate":{"control":"s3_ssl", "account_alias":target["account_alias"],
                        "resource_ref":target["resource_ref"], "expected_evidence_digest":target["evidence_digest"]}}
        for client in self.clients.values():
            client.calls.clear()

    def prepare(self, message=None, store=None):
        return prepare_and_register(self.service, store or self.store, self.message if message is None else message, clock=self.clock)

    def test_fresh_provider_read_precedes_durable_registration(self):
        value = self.prepare()
        self.assertEqual(sum(c.calls.count("policy") for c in self.clients.values()), 4)
        events = DecisionStore(self.db, clock=self.clock).timeline(value["batch_id"], self.binding)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "PREPARE_FROZEN")
        self.assertEqual(value["event_hash"], events[0]["event_hash"])
        self.assertEqual(value["binding_digest"], self.binding.digest())
        self.assertLessEqual(events[0]["payload"]["frozen"]["expires_at"], self.message["pause_expires_at"])
        self.assertNotIn("frozen", value)

    def test_registered_scope_drives_existing_reject_receipt(self):
        value = self.prepare()
        result = NativeDecisionAdapter(self.store).after_native_claim(batch_id=value["batch_id"], scope_hash=value["scope_hash"], binding=self.binding, decision="reject")
        self.assertEqual(result.receipt.outcome, "REJECTED")
        self.assertEqual(result.resolution()["call-1"]["type"], "reject")

    def test_caller_frozen_report_and_extra_fields_are_rejected_before_reads(self):
        for key in ("frozen", "report", "account_id", "role", "decision"):
            value = deepcopy(self.message); value[key] = {}
            with self.subTest(key=key), self.assertRaises(ValueError): self.prepare(value)
        self.assertFalse(any(c.calls for c in self.clients.values()))

    def test_invalid_candidate_cannot_supply_ids_or_scope(self):
        for field,value in (("control","ssh"),("account_alias","lab-prod"),("resource_ref","raw-bucket"),("expected_evidence_digest","fake")):
            m=deepcopy(self.message);m["candidate"][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):self.prepare(m)

    def test_changed_policy_same_status_requires_new_selection(self):
        self.clients["lab-dev"].policies[BUCKET] = {"Statement":[]}
        with self.assertRaises(ValueError): self.prepare()

    def test_partial_or_unknown_cannot_register(self):
        for value in (RuntimeError("private"),{"Statement":[{"Effect":"Allow"}]}):
            self.clients["lab-dev"].policies[BUCKET]=value
            with self.subTest(value=str(type(value))), self.assertRaises(ValueError): self.prepare()

    def test_expired_invalid_future_or_boolean_expiry_before_reads(self):
        for expiry in (self.now, self.now-1, self.now+90000, True, "123"):
            m=deepcopy(self.message);m["pause_expires_at"]=expiry
            with self.subTest(expiry=expiry), self.assertRaises(ValueError):self.prepare(m)
        self.assertFalse(any(c.calls for c in self.clients.values()))

    def test_expiry_during_provider_read_never_returns_readiness(self):
        original=self.service.prepare
        def delayed(**kwargs):
            f=original(**kwargs);self.now+=121;return f
        self.service.prepare=delayed
        with self.assertRaises(ValueError):self.prepare()

    def test_storage_failure_never_returns_ready(self):
        class Broken(DecisionStore):
            def register(self,*args): raise OSError("private filesystem error")
        with self.assertRaises(OSError): self.prepare(store=Broken(self.db,clock=self.clock))

    def test_lost_ack_leaves_orphan_record_not_approval(self):
        saved=[]
        class Lost(DecisionStore):
            def register(self,frozen,binding):
                saved.append(frozen.batch_id);super().register(frozen,binding);raise OSError("lost ack")
        with self.assertRaises(OSError):self.prepare(store=Lost(self.db,clock=self.clock))
        events=self.store.timeline(saved[0],self.binding)
        self.assertEqual([e["kind"] for e in events],["PREPARE_FROZEN"])
        self.assertFalse(events[0]["payload"]["frozen"]["live_execution_authorized"])

    def test_fresh_preparations_never_reuse_batch(self):
        self.assertNotEqual(self.prepare()["batch_id"],self.prepare()["batch_id"])

    def test_private_config_refuses_symlink_and_broad_permissions(self):
        p=Path(self.temp.name)/"config.json";p.write_text("{}");p.chmod(0o600);_private_config(p)
        link=Path(self.temp.name)/"link";link.symlink_to(p)
        with self.assertRaises(ValueError):_private_config(link)
        p.chmod(0o644)
        with self.assertRaises(ValueError):_private_config(p)

    def test_node_producer_suite(self):
        root=Path(__file__).resolve().parents[1]
        node=shutil.which("node")
        if not node:
            if os.getenv("AWSOPS_REQUIRE_NATIVE_FIXTURE")=="1":self.fail("Node required")
            self.skipTest("Node unavailable locally")
        result=subprocess.run([node,"--test",str(root/"tests/pause_runtime.test.cjs")],cwd=root,
                              env={**os.environ,"AWSOPS_TEST_PYTHON":sys.executable},capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        print("Producer Node rehearsal: "+"; ".join(x for x in result.stdout.splitlines() if x.startswith(("# tests ","# pass ","# fail ","# skipped "))))


if __name__ == "__main__":
    unittest.main()
