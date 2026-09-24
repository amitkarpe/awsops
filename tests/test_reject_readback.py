"""Bound Reject audit readback, without restoring a native job or planning cache."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import test_prepare_pause as fixtures
from test_s3_ssl import collect, BUCKET
from awsops.approval.decisions import DecisionStore
from awsops.runtime.prepare_pause import readback_after_reject
from awsops.runtime.s3_ssl_service import S3SslService


class RejectReadbackTests(unittest.TestCase):
    setUp = fixtures.PreparePauseTests.setUp
    prepare = fixtures.PreparePauseTests.prepare

    def rejected_readback_message(self):
        value = self.prepare()
        self.store.record(batch_id=value["batch_id"], scope_hash=value["scope_hash"], binding=self.binding, decision="reject")
        return {"version":1, "operation":"readback", "binding":self.message["binding"],
                "batch_id":value["batch_id"], "scope_hash":value["scope_hash"]}

    def readback(self, message):
        # A new service has no in-process preparation cache. Only the bound
        # durable Reject permits this read-only audit comparison.
        service=S3SslService(lambda: collect(self.bound, lambda b: self.clients[b.alias], clock=self.clock), clock=self.clock)
        store=DecisionStore(self.db,clock=self.clock)
        return readback_after_reject(service,store,message,clock=self.clock)

    def test_reopened_reject_readback_does_not_recreate_or_resume_job(self):
        m=self.rejected_readback_message()
        before=self.store.timeline(m["batch_id"],self.binding)
        result=self.readback(m)
        self.assertTrue(result["unchanged"])
        self.assertEqual(result["receipt_event_hash"],before[-1]["event_hash"])
        self.assertNotIn("resume_value",result)
        self.assertEqual(self.store.timeline(m["batch_id"],self.binding),before)

    def test_same_status_policy_drift_fails_durable_readback(self):
        m=self.rejected_readback_message()
        self.clients["lab-dev"].policies[BUCKET]={"Statement":[]}
        result=self.readback(m)
        self.assertEqual(result["state"],"NON_COMPLIANT")
        self.assertFalse(result["unchanged"])

    def test_readback_requires_bound_reject_before_provider_reads(self):
        value=self.prepare()
        m={"version":1,"operation":"readback","binding":self.message["binding"],
           "batch_id":value["batch_id"],"scope_hash":value["scope_hash"]}
        for c in self.clients.values():c.calls.clear()
        with self.assertRaises(ValueError):self.readback(m)
        self.assertFalse(any(c.calls for c in self.clients.values()))
        self.store.record(batch_id=value["batch_id"],scope_hash=value["scope_hash"],binding=self.binding,decision="approve")
        with self.assertRaises(ValueError):self.readback(m)
        self.assertFalse(any(c.calls for c in self.clients.values()))

    def test_readback_rejects_wrong_binding_or_scope_without_reads(self):
        m=self.rejected_readback_message()
        for c in self.clients.values():c.calls.clear()
        bad=deepcopy(m);bad["scope_hash"]="f"*64
        with self.assertRaises(ValueError):self.readback(bad)
        bad=deepcopy(m);bad["binding"]["principal_id"]="other"
        with self.assertRaises(ValueError):self.readback(bad)
        self.assertFalse(any(c.calls for c in self.clients.values()))

    def test_expired_partial_or_unknown_never_reports_unchanged(self):
        m=self.rejected_readback_message()
        self.clients["lab-dev"].policies[BUCKET]=RuntimeError("private")
        self.assertFalse(self.readback(m)["unchanged"])
        self.clients["lab-dev"].policies[BUCKET]={"Statement":[{"Effect":"Allow"}]}
        self.assertFalse(self.readback(m)["unchanged"])
        self.clients["lab-dev"].policies[BUCKET]=None
        self.now+=120
        self.assertFalse(self.readback(m)["unchanged"])


if __name__ == "__main__":
    unittest.main()
