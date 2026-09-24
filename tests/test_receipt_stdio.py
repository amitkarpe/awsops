from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from awsops.approval.decisions import DecisionStore, NativeBinding
from awsops.domain.freeze import freeze_finding
from awsops.domain.models import Finding
from awsops.runtime.receipt_stdio import dispatch, MAX_INPUT


class ReceiptPipeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='awsops-pipe-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'decisions.sqlite3'
        self.store = DecisionStore(self.path)
        now = int(time.time())
        self.frozen = freeze_finding(Finding('finding-'+'a'*20, 'lab-dev', 's3_ssl', 'bucket-ref-'+'b'*20,
                                            'ap-southeast-1', 'NON_COMPLIANT', 'c'*64, now), now=now)
        self.binding = NativeBinding('native-user', 'system:single-tenant', 'conversation', 'action', '123', 'call')

    def message(self, operation):
        msg = {'version': 1, 'operation': operation, 'binding': asdict(self.binding)}
        if operation == 'register':
            msg['frozen'] = self.frozen.public_dict()
        else:
            msg['batch_id'] = self.frozen.batch_id
        if operation == 'record':
            msg.update(scope_hash=self.frozen.scope_hash, decision='reject')
        return msg

    def run_pipe(self, message=None, raw=None, path=None):
        result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'integration/librechat/receipt_entry.py'),
                                 '--database', str(path or self.path)],
                                input=raw if raw is not None else json.dumps(message).encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8,
                                env={'LANG': 'C.UTF-8'})
        self.assertEqual(result.stderr, b'')
        return result.returncode, json.loads(result.stdout)

    def register(self):
        code, result = self.run_pipe(self.message('register'))
        self.assertEqual(code, 0)
        self.assertFalse(result['dispatch_allowed'])
        return result

    def test_real_subprocess_register_reject_commit_and_reopen(self):
        self.register()
        code, result = self.run_pipe(self.message('record'))
        self.assertEqual(code, 0)
        self.assertEqual(result['receipt']['outcome'], 'REJECTED')
        self.assertEqual(result['resume_value']['call']['type'], 'reject')
        events = DecisionStore(self.path).timeline(self.frozen.batch_id, self.binding)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[-1]['event_hash'], result['receipt']['event_hash'])

    def test_synthetic_approve_is_blocked(self):
        self.register()
        msg = self.message('record'); msg['decision'] = 'approve'
        code, result = self.run_pipe(msg)
        self.assertEqual(code, 0)
        self.assertEqual(result['receipt']['outcome'], 'APPROVE_BLOCKED')
        self.assertEqual(result['resume_value']['call']['type'], 'reject')
        self.assertFalse(result['dispatch_allowed'])

    def test_missing_ledger_is_not_created(self):
        missing = self.path.parent / 'missing.sqlite3'
        code, result = self.run_pipe(self.message('record'), path=missing)
        self.assertEqual(code, 2)
        self.assertFalse(missing.exists())
        self.assertFalse(result['dispatch_allowed'])

    def test_empty_ledger_is_not_initialized_by_request(self):
        empty = self.path.parent / 'empty.sqlite3'; empty.touch(mode=0o600)
        code, _ = self.run_pipe(self.message('record'), path=empty)
        self.assertEqual(code, 2); self.assertEqual(empty.stat().st_size, 0)

    def test_private_parent_and_file_required(self):
        self.register()
        for target in (self.path, self.path.parent):
            previous = target.stat().st_mode & 0o777
            try:
                target.chmod(0o755 if target.is_dir() else 0o644)
                self.assertEqual(self.run_pipe(self.message('record'))[0], 2)
            finally:
                target.chmod(previous)

    def test_symlink_is_refused(self):
        link = self.path.parent / 'link.sqlite3'; link.symlink_to(self.path)
        self.assertEqual(self.run_pipe(self.message('record'), path=link)[0], 2)

    def test_unregistered_binding_fails_closed(self):
        code, result = self.run_pipe(self.message('record'))
        self.assertEqual(code, 2); self.assertNotIn('resume_value', result)

    def test_replay_denied_and_audit_cannot_continue(self):
        self.register(); self.assertEqual(self.run_pipe(self.message('record'))[0], 0)
        code, result = self.run_pipe(self.message('record'))
        self.assertEqual(code, 2); self.assertNotIn('resume_value', result)
        code, audit = self.run_pipe(self.message('inspect'))
        self.assertEqual(code, 0); self.assertEqual(len(audit['events']), 2)
        self.assertNotIn('resume_value', audit); self.assertNotIn('binding', audit)

    def test_binding_drift_does_not_consume(self):
        self.register()
        msg = self.message('record'); msg['binding']['principal_id'] = 'other-user'
        self.assertEqual(self.run_pipe(msg)[0], 2)
        self.assertEqual(len(self.store.timeline(self.frozen.batch_id, self.binding)), 1)

    def test_duplicate_keys_nonfinite_and_oversized_json(self):
        for raw in (b'{"version":1,"version":1}', b'{"version":NaN}', b'x'*(MAX_INPUT+1)):
            with self.subTest(size=len(raw)):
                code, result = self.run_pipe(raw=raw)
                self.assertEqual(code, 2); self.assertNotIn('resume_value', result)

    def test_exact_schema_no_arbitrary_operations_or_resources(self):
        for mutation in ({'operation': 'execute'}, {'url': 'https://example.invalid'}, {'version': True},
                         {'frozen': {'live_execution_authorized': True}}):
            msg = self.message('register'); msg.update(mutation)
            self.assertEqual(self.run_pipe(msg)[0], 2)

    def test_output_never_echoes_private_input(self):
        msg = self.message('record'); msg['private'] = 'do-not-echo-this-value'
        _, result = self.run_pipe(msg)
        self.assertNotIn('do-not-echo', repr(result))
        self.assertNotIn(str(self.path), repr(result))


class NativeNodeRehearsalTests(unittest.TestCase):
    def test_node_contracts(self):
        import shutil
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required; do not silently skip native integration tests')
        env = dict(os.environ, AWSOPS_TEST_PYTHON=sys.executable)
        result = subprocess.run([node, '--test', str(ROOT / 'tests/native_runtime.test.cjs')],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        if env.get('AWSOPS_REQUIRE_NATIVE_FIXTURE') == '1':
            self.assertIn('# skipped 0', result.stdout, result.stdout)
        summary = [line for line in result.stdout.splitlines()
                   if line.startswith(('# tests ', '# pass ', '# fail ', '# skipped '))]
        print('Native Node rehearsal: ' + '; '.join(summary), flush=True)


if __name__ == '__main__':
    unittest.main()
