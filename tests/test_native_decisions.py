"""Synthetic decision tests; never connect to a cloud or native UI."""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from awsops.approval.decisions import DecisionError, DecisionReceipt, DecisionStore, NativeBinding, TOOL, _TRIGGERS
from awsops.domain.freeze import freeze_finding
from awsops.domain.models import Finding
from awsops.runtime.native_decision import NativeDecisionAdapter

NOW = 1790211000


def make_frozen(now=NOW):
    finding = Finding("finding-" + "a" * 20, "lab-dev", "s3_ssl", "bucket-ref-" + "b" * 20,
                      "ap-southeast-1", "NON_COMPLIANT", "c" * 64, now)
    return freeze_finding(finding, now=now)


def make_binding():
    return NativeBinding("test-principal", "test-tenant", "test-conversation", "test-action", "test-generation", "test-tool-call")


def competing_process(arguments):
    path, batch, scope, decision = arguments
    store = DecisionStore(Path(path), clock=lambda: NOW)
    try:
        return store.record(batch_id=batch, scope_hash=scope, binding=make_binding(), decision=decision).outcome
    except DecisionError as exc:
        return str(exc)


class NativeDecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "decisions.sqlite3"
        self.now = NOW
        self.store = DecisionStore(self.path, clock=lambda: self.now)
        self.frozen = make_frozen()
        self.binding = make_binding()
        self.prepare_hash = self.store.register(self.frozen, self.binding)

    def decide(self, decision="reject", **changes):
        args = dict(batch_id=self.frozen.batch_id, scope_hash=self.frozen.scope_hash, binding=self.binding, decision=decision)
        args.update(changes)
        return self.store.record(**args)

    def test_reject_is_committed_before_return(self):
        receipt = self.decide()
        self.assertEqual(receipt.outcome, "REJECTED")
        self.assertFalse(receipt.public_dict()["dispatch_allowed"])
        reopened = DecisionStore(self.path, clock=lambda: NOW)
        events = reopened.timeline(self.frozen.batch_id, self.binding)
        self.assertEqual([e["kind"] for e in events], ["PREPARE_FROZEN", "NATIVE_DECISION"])
        self.assertEqual(events[-1]["event_hash"], receipt.event_hash)
        self.assertEqual(events[-1]["payload"]["prepare_event_hash"], self.prepare_hash)

    def test_approve_is_a_blocked_receipt_not_authority(self):
        receipt = self.decide("approve")
        self.assertEqual(receipt.outcome, "APPROVE_BLOCKED")
        self.assertFalse(receipt.public_dict()["dispatch_allowed"])
        self.assertEqual(self.store.timeline(self.frozen.batch_id, self.binding)[-1]["payload"]["decision"], "approve")

    def test_native_adapter_returns_only_reject(self):
        adapter = NativeDecisionAdapter(self.store)
        continuation = adapter.after_native_claim(batch_id=self.frozen.batch_id, scope_hash=self.frozen.scope_hash,
                                                  binding=self.binding, decision="approve")
        self.assertEqual(continuation.resolution(), {self.binding.tool_call_id: {"type": "reject", "reason": "LIVE_EXECUTION_NOT_AUTHORIZED"}})
        self.assertEqual(continuation.receipt.outcome, "APPROVE_BLOCKED")

    def test_native_reject_reason_and_receipt(self):
        result = NativeDecisionAdapter(self.store).after_native_claim(batch_id=self.frozen.batch_id, scope_hash=self.frozen.scope_hash,
                                                                      binding=self.binding, decision="reject")
        self.assertEqual(result.reason, "REJECTED")
        self.assertEqual(result.receipt.outcome, "REJECTED")

    def test_duplicate_or_conflicting_decisions_are_not_resumed(self):
        self.decide()
        for choice in ("reject", "approve"):
            with self.assertRaisesRegex(DecisionError, "ALREADY_RECORDED"):
                self.decide(choice)
        self.assertEqual(len(self.store.timeline(self.frozen.batch_id, self.binding)), 2)

    def test_reopen_does_not_reset_consumption(self):
        self.decide()
        self.store = DecisionStore(self.path, clock=lambda: NOW)
        with self.assertRaisesRegex(DecisionError, "ALREADY_RECORDED"):
            self.decide()

    def test_every_native_identity_field_is_bound(self):
        for field in ("principal_id", "tenant_id", "conversation_id", "action_id", "generation_id", "tool_call_id"):
            with self.subTest(field=field), self.assertRaisesRegex(DecisionError, "BINDING_MISMATCH"):
                self.decide(binding=replace(self.binding, **{field: "different"}))
        self.assertEqual(len(self.store.timeline(self.frozen.batch_id, self.binding)), 1)

    def test_wrong_tool_is_rejected_before_store(self):
        for name in ("execute_remediation", "s3_bpa", "restricted_ssh", "", TOOL + "_lookalike"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                replace(self.binding, tool=name)

    def test_raw_mapping_is_not_native_context(self):
        with self.assertRaisesRegex(DecisionError, "INVALID_NATIVE_BINDING"):
            self.decide(binding=asdict(self.binding))

    def test_unrecognized_decisions(self):
        for choice in ("APPROVE", "APPROVE_ALL", "edit", "respond", "", None, True, [], {}):
            with self.subTest(choice=choice), self.assertRaisesRegex(DecisionError, "UNSUPPORTED_DECISION"):
                self.decide(choice)

    def test_scope_mismatch_and_unknown_batch(self):
        with self.assertRaisesRegex(DecisionError, "BINDING_MISMATCH"):
            self.decide(scope_hash="d" * 64)
        with self.assertRaisesRegex(DecisionError, "NOT_FOUND"):
            self.decide(batch_id="e" * 32)

    def test_expiry_is_exclusive(self):
        self.now = self.frozen.expires_at
        with self.assertRaisesRegex(DecisionError, "EXPIRED"):
            self.decide()
        self.assertEqual(len(self.store.timeline(self.frozen.batch_id, self.binding)), 1)

    def test_last_valid_second(self):
        self.now = self.frozen.expires_at - 1
        self.assertEqual(self.decide().outcome, "REJECTED")

    def test_clock_rollback_is_denied(self):
        self.now = NOW - 1
        with self.assertRaisesRegex(DecisionError, "FUTURE"):
            self.decide()

    def test_future_or_expired_registration(self):
        future = make_frozen(NOW + 1)
        expired = make_frozen(NOW - 300)
        for frozen in (future, expired):
            with self.subTest(frozen=frozen.batch_id), self.assertRaisesRegex(DecisionError, "EXPIRED_OR_FUTURE"):
                self.store.register(frozen, self.binding)

    def test_duplicate_registration_cannot_rebind(self):
        with self.assertRaisesRegex(DecisionError, "ALREADY_REGISTERED"):
            self.store.register(self.frozen, replace(self.binding, principal_id="other"))

    def test_forged_frozen_dataclass_is_revalidated(self):
        other = make_frozen()
        object.__setattr__(other, "scope_hash", "a" * 64)
        with self.assertRaisesRegex(ValueError, "invalid frozen scope"):
            self.store.register(other, self.binding)

    def test_connect_failure_yields_no_continuation(self):
        with patch.object(self.store, "_connect", side_effect=sqlite3.OperationalError("test storage unavailable")):
            with self.assertRaises(sqlite3.OperationalError):
                NativeDecisionAdapter(self.store).after_native_claim(batch_id=self.frozen.batch_id, scope_hash=self.frozen.scope_hash,
                                                                    binding=self.binding, decision="reject")
        self.assertEqual(len(self.store.timeline(self.frozen.batch_id, self.binding)), 1)

    def test_failure_after_insert_rolls_back(self):
        original = self.store._append
        def fail(*args):
            original(*args)
            raise OSError("test disk failure")
        with patch.object(self.store, "_append", side_effect=fail):
            with self.assertRaises(OSError):
                self.decide()
        self.assertEqual(len(self.store.timeline(self.frozen.batch_id, self.binding)), 1)
        self.assertEqual(self.decide().outcome, "REJECTED")

    def test_commit_failure_rolls_back_and_emits_no_result(self):
        with patch.object(self.store, "_commit", side_effect=sqlite3.OperationalError("test commit failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.decide()
        self.assertEqual(len(self.store.timeline(self.frozen.batch_id, self.binding)), 1)
        self.assertEqual(self.decide().outcome, "REJECTED")

    def test_adapter_rejects_wrong_receipt_response(self):
        receipt = DecisionReceipt(self.frozen.batch_id, self.frozen.scope_hash, "REJECTED", "a" * 64, NOW)
        for wrong in (None, {"outcome": "REJECTED"}, replace(receipt, outcome="APPROVE_BLOCKED"), replace(receipt, scope_hash="d" * 64)):
            with patch.object(self.store, "record", return_value=wrong), self.assertRaises(DecisionError):
                NativeDecisionAdapter(self.store).after_native_claim(batch_id=self.frozen.batch_id, scope_hash=self.frozen.scope_hash,
                                                                    binding=self.binding, decision="reject")

    def test_threads_have_one_decision_winner(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(competing_process, [(str(self.path), self.frozen.batch_id, self.frozen.scope_hash, "reject")] * 6))
        self.assertEqual(results.count("REJECTED"), 1)
        self.assertEqual(results.count("DECISION_ALREADY_RECORDED"), 5)

    def test_processes_with_conflicting_choices_have_one_winner(self):
        ctx = multiprocessing.get_context("spawn")
        arguments = [(str(self.path), self.frozen.batch_id, self.frozen.scope_hash, choice) for choice in ("approve", "reject")]
        with ctx.Pool(2) as pool:
            results = pool.map(competing_process, arguments)
        self.assertEqual(results.count("DECISION_ALREADY_RECORDED"), 1)
        self.assertEqual(sum(r in ("APPROVE_BLOCKED", "REJECTED") for r in results), 1)
        self.assertEqual(len(self.store.timeline(self.frozen.batch_id, self.binding)), 2)

    def test_ledger_update_and_delete_are_blocked(self):
        self.decide()
        with sqlite3.connect(self.path) as db:
            for sql in ("UPDATE events SET kind='NATIVE_DECISION'", "DELETE FROM events"):
                with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
                    db.execute(sql)

    def test_chain_tampering_fails_even_with_trigger_restored(self):
        self.decide()
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER events_no_update")
            db.execute("UPDATE events SET event_hash=? WHERE sequence=2", ("e" * 64,))
            db.execute(_TRIGGERS["events_no_update"])
        with self.assertRaisesRegex(DecisionError, "INTEGRITY_FAILURE"):
            DecisionStore(self.path)

    def test_schema_or_version_drift_is_not_repaired_silently(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER events_no_delete")
        with self.assertRaisesRegex(DecisionError, "SCHEMA_DRIFT"):
            DecisionStore(self.path)
        with sqlite3.connect(self.path) as db:
            db.execute(_TRIGGERS["events_no_delete"])
            db.execute("PRAGMA user_version=2")
        with self.assertRaisesRegex(DecisionError, "UNSUPPORTED_LEDGER_VERSION"):
            DecisionStore(self.path)

    def test_private_identity_values_are_not_in_ledger(self):
        self.decide()
        data = json.dumps(self.store.timeline(self.frozen.batch_id, self.binding))
        for value in asdict(self.binding).values():
            self.assertNotIn(value, data)
        self.assertNotIn(self.binding.principal_id, repr(self.binding))

    def test_timeline_is_bound_but_can_read_expired_decision(self):
        self.decide()
        self.now += 1000
        self.assertEqual(len(self.store.timeline(self.frozen.batch_id, self.binding)), 2)
        with self.assertRaises(DecisionError):
            self.store.timeline(self.frozen.batch_id, replace(self.binding, tenant_id="other"))

    def test_database_is_not_silently_recreated(self):
        self.path.unlink()
        with self.assertRaises(OSError):
            self.decide()
        self.assertFalse(self.path.exists())

    @unittest.skipUnless(os.name == "posix", "POSIX file permissions")
    def test_broad_file_permissions_and_symlinks_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(DecisionError, "UNSAFE_DATABASE_FILE"):
            DecisionStore(self.path)
        self.path.chmod(0o600)
        link = self.path.parent / "link.sqlite3"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(DecisionError, "UNSAFE_DATABASE_PATH"):
            DecisionStore(link)

    def test_no_cloud_executor_or_platform_dependency(self):
        for relative in ("approval/decisions.py", "runtime/native_decision.py"):
            source = (ROOT / "src/awsops" / relative).read_text()
            tree = ast.parse(source)
            names = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    names.append(node.module or "")
            for name in names:
                self.assertFalse(name.startswith(("boto3", "botocore", "awsops.aws", "awsops.execution", "mcp", "librechat")), name)


if __name__ == "__main__":
    unittest.main()
