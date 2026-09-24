"""Offline guard tests. These do not claim a successful native login."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'integration/canary/browser.cjs'


@unittest.skipUnless(shutil.which('node'), 'Node is required for browser guard contracts')
class CanaryBrowserTests(unittest.TestCase):
    def invoke(self, body):
        result = subprocess.run(['node', '-e', 'const g=require(' + json.dumps(str(SCRIPT)) + ');' + body],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_same_origin_is_exact(self):
        urls = ['http://127.0.0.1:4311/api/convos', 'https://127.0.0.1:4311',
                'http://127.0.0.1:4312', 'https://example.test', 'not a URL']
        actual = self.invoke('console.log(JSON.stringify(' + json.dumps(urls) + '.map(g.localRoute)));')
        self.assertEqual(json.loads(actual), [True, False, False, False, False])

    def test_private_file_and_symlink_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / 'state.json'
            private.write_text('{"synthetic":true}')
            private.chmod(0o600)
            self.assertEqual(self.invoke('console.log(g.privateFile(' + json.dumps(str(private)) + ').synthetic);'), 'true')
            private.chmod(0o644)
            self.assertEqual(self.invoke('try {g.privateFile(' + json.dumps(str(private)) + ');process.exit(1)} catch {console.log("denied")}'), 'denied')
            private.chmod(0o600)
            link = Path(directory) / 'alias.json'
            link.symlink_to(private)
            self.assertEqual(self.invoke('try {g.privateFile(' + json.dumps(str(link)) + ');process.exit(1)} catch {console.log("denied")}'), 'denied')

    def test_no_browser_auth_export(self):
        source = SCRIPT.read_text()
        for forbidden in ['storageState(', '.cookies(', 'localStorage.getItem', 'allHeaders(', 'Authorization:']:
            self.assertNotIn(forbidden, source)
        self.assertIn("getByTestId('login-button')", source)
        self.assertIn("native_decision: 'NOT_RUN'", source)
