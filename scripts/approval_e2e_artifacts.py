#!/usr/bin/env python3
"""Generate deterministic, synthetic Issue #90 approval-flow artifacts.

This command exercises the application path with the test-only SDK and verifier.
It does not construct the production provider or contact AWS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from awsops.execution import s3_canary
from test_issue90_approval_e2e import make_case

FIXED_TIME = 1_800_000_000
def synthetic_uuid_hex(number: int) -> str:
    """Return a deterministic UUID-shaped value without long digit runs."""
    digits = f"{number:020x}"
    # Interleave alphabetic hex nibbles so prefixed identifiers never resemble
    # a private 12-digit account value to the canonical artifact reader.
    return "".join(digits[offset:offset + 5] + marker for offset, marker in zip(
        range(0, 20, 5), ("abc", "def", "abc", "def")))


UUIDS = iter(synthetic_uuid_hex(number) for number in range(1, 100))
FAKE_ACCOUNT = "999999999999"
FAKE_BUCKET = "awsops-dev-issue90-s3-canary-zzzzzzzzzzzz"


def deterministic_uuid():
    return SimpleNamespace(hex=next(UUIDS))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_receipt(receipt: list[dict]) -> None:
    if [item.get("kind") for item in receipt] != ["Batch", "Decision", "Run", "Evidence"]:
        raise ValueError("INVALID_FOUR_ENVELOPE_RECEIPT")
    evidence = receipt[3].get("record", {})
    if evidence.get("provenance") != "SYNTHETIC" or evidence.get("limitation") != "SYNTHETIC_ONLY":
        raise ValueError("SIMULATED_EVIDENCE_LABEL_MISSING")
    exported = json.dumps(receipt, sort_keys=True)
    if FAKE_ACCOUNT in exported or FAKE_BUCKET in exported or "TEST_ONLY_SIMULATED_APPROVAL" in exported:
        raise ValueError("UNSANITIZED_TEST_ARTIFACT")


def emit_case(root: Path, scenario: str, operation, source_revision: str) -> dict:
    with patch.object(s3_canary.uuid, "uuid4", side_effect=deterministic_uuid):
        with tempfile.TemporaryDirectory(prefix="awsops-approval-e2e-") as scratch:
            flow, _sdk, _clock, _factory_calls, _batch, _authority, packet, _verifier = make_case(
                Path(scratch), source_revision=source_revision, clock=[FIXED_TIME])
            packet = operation(flow, packet) or packet
            receipt = flow.receipt(packet)
            audit = flow.audit(packet)
            validate_receipt(receipt)
            audit_text = json.dumps(audit, sort_keys=True)
            if (audit.get("provenance") != "SYNTHETIC"
                    or audit.get("limitation") != "SYNTHETIC_ONLY"
                    or FAKE_ACCOUNT in audit_text or FAKE_BUCKET in audit_text
                    or "TEST_ONLY_SIMULATED_APPROVAL" in audit_text):
                raise ValueError("UNSANITIZED_TEST_AUDIT")
            receipt_name = scenario + ".receipt.json"
            audit_name = scenario + ".audit.json"
            write_json(root / receipt_name, receipt)
            write_json(root / audit_name, audit)
            return {"name": scenario, "receipt": receipt_name, "audit": audit_name}


def success(flow, packet):
    flow.decide(packet)
    flow.cleanup(packet)


def reject(flow, packet):
    from dataclasses import replace

    packet = replace(packet, decision="REJECT")
    flow.decide(packet)
    return packet


def partial_cleanup(flow, packet):
    # The shared fake SDK exposes a refusal switch used by the focused regression.
    provider = flow.adapter_factory()
    s3 = provider.provider.s3
    s3.fail_tags_preflight_after_create = True
    flow.decide(packet)
    flow.cleanup(packet)


def uncertain_policy(flow, packet):
    provider = flow.adapter_factory()
    provider.provider.s3.uncertain = "policy"
    flow.decide(packet)


def uncertain_delete(flow, packet):
    flow.decide(packet)
    provider = flow.adapter_factory()
    provider.provider.s3.uncertain = "delete"
    flow.cleanup(packet)
    flow.cleanup(packet)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="new or empty disposable output directory")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("output directory must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()

    cases = [
        emit_case(output, "success", success, head),
        emit_case(output, "uncertain-policy", uncertain_policy, head),
        emit_case(output, "reject", reject, head),
        emit_case(output, "partial-setup-cleanup", partial_cleanup, head),
        emit_case(output, "uncertain-delete", uncertain_delete, head),
    ]

    write_json(output / "app-e2e-summary.json", {
        "schemaVersion": "awsops-canary-e2e/1",
        "approval": "TEST_SIMULATION",
        "provider": "FAKE_SDK",
        "actualAwsCalls": 0,
        "reportedAttemptCountsAreActualAwsCalls": False,
        "sourceRevision": head,
        "cases": cases,
    })
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
