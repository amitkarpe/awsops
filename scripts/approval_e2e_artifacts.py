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

DEFAULT_OUTPUT = Path.home() / ".AGENTS-temp/awsops/approval-e2e-20261016"
FIXED_TIME = 1_800_000_000
UUIDS = iter(f"{number:032x}" for number in range(1, 100))


def deterministic_uuid():
    return SimpleNamespace(hex=next(UUIDS))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit_case(root: Path, scenario: str, operation, source_revision: str) -> None:
    (root / scenario).mkdir(parents=True, exist_ok=True)
    with patch.object(s3_canary.uuid, "uuid4", side_effect=deterministic_uuid):
        with tempfile.TemporaryDirectory(prefix="awsops-approval-e2e-") as scratch:
            flow, _sdk, _clock, _factory_calls, _batch, _authority, packet, _verifier = make_case(
                Path(scratch), source_revision=source_revision, clock=[FIXED_TIME])
            packet = operation(flow, packet) or packet
            write_json(root / scenario / "four-envelope.json", flow.receipt(packet))
            write_json(root / scenario / "application-audit.json", flow.audit(packet))


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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE).stdout.strip()

    for scenario, operation in (
        ("success-with-cleanup", success),
        ("partial-setup-cleanup", partial_cleanup),
        ("uncertain-policy", uncertain_policy),
        ("uncertain-delete", uncertain_delete),
        ("rejected", reject),
    ):
        emit_case(output, scenario, operation, head)

    write_json(output / "manifest.json", {
        "schemaVersion": "awsops-issue90-approval-e2e-artifacts/1",
        "sourceRevision": head,
        "artifactClass": "SYNTHETIC_ONLY",
        "approvalAssurance": "TEST_SIMULATION",
        "providerMode": "MOCK",
        "awsCalls": 0,
        "core2Import": "Use each scenario/four-envelope.json as the four-envelope v1 array.",
        "audit": "Separate application-audit.json; not part of the four-envelope v1 schema.",
        "scenarios": ["success-with-cleanup", "partial-setup-cleanup", "uncertain-policy",
                      "uncertain-delete", "rejected"],
        "limitation": "No human approval, live provider read, compliance convergence, or AWS action is evidenced.",
    })
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
