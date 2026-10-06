"""Offline final M3 acceptance-packet contract tests."""
from pathlib import Path
import copy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from awsops.domain.m3_acceptance import VERSION, validate_m3_acceptance


def packet():
    return {
        "version": VERSION,
        "control": "s3_ssl",
        "account_alias": "lab-dev",
        "pr_head": "a" * 40,
        "scope_hash": "b" * 64,
        "receipt_hash": "c" * 64,
        "normal_auth": True,
        "native_decision": "REJECTED",
        "dispatch_attempts": 0,
        "provider_readback": "UNCHANGED",
        "conversation_archived": True,
        "canary_stopped": True,
        "retained_services_unchanged": True,
        "sanitized": True,
    }


class M3AcceptanceEvidenceTests(unittest.TestCase):
    def test_complete_public_packet_passes(self):
        self.assertEqual(validate_m3_acceptance(packet()), packet())

    def test_every_acceptance_gate_fails_closed(self):
        cases = {
            "normal_auth": False,
            "native_decision": "APPROVED",
            "dispatch_attempts": 1,
            "provider_readback": "CHANGED",
            "conversation_archived": False,
            "canary_stopped": False,
            "retained_services_unchanged": False,
            "sanitized": False,
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                candidate = packet()
                candidate[key] = value
                with self.assertRaises(ValueError):
                    validate_m3_acceptance(candidate)

    def test_private_or_secret_shaped_extra_fields_are_rejected(self):
        for key in ("account_id", "arn", "endpoint", "token", "cookie", "native_user_id", "raw_policy"):
            with self.subTest(key=key):
                candidate = packet()
                candidate[key] = "should-not-be-public"
                with self.assertRaises(ValueError):
                    validate_m3_acceptance(candidate)

    def test_identifiers_are_public_safe_forms_only(self):
        for key, value in (
            ("account_alias", "123456789012"),
            ("pr_head", "not-a-commit"),
            ("scope_hash", "arn:aws:s3:::private"),
            ("receipt_hash", "secret"),
        ):
            with self.subTest(key=key):
                candidate = packet()
                candidate[key] = value
                with self.assertRaises(ValueError):
                    validate_m3_acceptance(candidate)


if __name__ == "__main__":
    unittest.main()
