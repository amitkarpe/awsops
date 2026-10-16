#!/usr/bin/env python3
"""Human-operated Issue #90 canary only. Importing this file never calls AWS."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from awsops.domain.models import canonical_digest
from awsops.execution.s3_canary import CanaryAdapter, CanaryBinding, REGION

BINDING = Path.home() / ".AGENTS-temp/manager/home-migration-20261016/lab-binding.private.json"
LEDGER = Path.home() / ".AGENTS-temp/awsops/issue90-s3-canary.sqlite"
BUCKET = re.compile(r"awsops-dev-issue90-s3-canary-[a-z0-9]{12}")


def private_binding(bucket: str) -> CanaryBinding:
    if BUCKET.fullmatch(bucket) is None:
        raise ValueError("INVALID_CANARY_NAME")
    if BINDING.is_symlink() or stat.S_IMODE(BINDING.stat().st_mode) & 0o077:
        raise ValueError("PRIVATE_BINDING_REQUIRED")
    value = json.loads(BINDING.read_text())
    if value.get("accountAlias") != "amit" or value.get("profile") != "amit" or value.get("region") != REGION:
        raise ValueError("UNAPPROVED_LAB_BINDING")
    return CanaryBinding(value["accountId"], bucket)


def operator_principal() -> str:
    # OS access to the private file and interactive TTY are the local operator
    # boundary. This digest binds a session; it is not authentication by itself.
    return canonical_digest(["awsops-issue90-local-operator", os.getuid()])


def source_revision() -> str:
    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                      text=True, check=True).stdout.strip():
        raise ValueError("CLEAN_SOURCE_REQUIRED")
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def adapter_for(bucket: str) -> CanaryAdapter:
    binding = private_binding(bucket)
    LEDGER.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if LEDGER.parent.is_symlink() or stat.S_IMODE(LEDGER.parent.stat().st_mode) & 0o077:
        raise ValueError("PRIVATE_LEDGER_DIRECTORY_REQUIRED")
    import boto3
    from awsops.aws.boto3_s3_canary import Boto3CanaryProvider
    session = boto3.Session(profile_name="amit", region_name=REGION)
    provider = Boto3CanaryProvider(session, binding, LEDGER)
    return CanaryAdapter(LEDGER, binding, provider, source_revision=source_revision(),
                         source_version="v1.0.0-mock")


def human_confirmation(action: str, bucket: str, scope: str) -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise ValueError("HUMAN_TTY_REQUIRED")
    phrase = f"{action} {scope[:12]} {bucket}"
    print("Exact private target:", bucket)
    print("Frozen scope digest:", scope)
    print("Fixed calls: CreateBucket, PutBucketTagging, PutPublicAccessBlock, PutBucketPolicy; cleanup uses DeleteBucket only.")
    print("Cost assumption: one empty bucket, four write attempts, bounded readback; shared experiment spend must be checked separately.")
    if input("Type '" + phrase + "' to continue: ") != phrase:
        raise ValueError("HUMAN_CONFIRMATION_MISMATCH")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "approve", "reject", "reconcile", "cleanup"))
    parser.add_argument("--bucket", required=True, help="Exact private task-created bucket name")
    parser.add_argument("--batch-id")
    parser.add_argument("--scope-digest")
    args = parser.parse_args(argv)
    try:
        if args.operation == "approve":
            raise ValueError(
                "TRUSTED_HUMAN_APPROVAL_BINDING_REQUIRED: live approval needs an independently trusted, "
                "single-use owner approval bound to this batch and scope; TTY text and CLI digests are not proof"
            )
        if args.operation != "prepare" and not args.batch_id:
            raise ValueError("BATCH_ID_REQUIRED")
        if args.operation in ("approve", "reject") and not args.scope_digest:
            raise ValueError("SCOPE_DIGEST_REQUIRED")
        adapter = adapter_for(args.bucket)
        principal = operator_principal()
        if args.operation == "prepare":
            output = adapter.prepare(principal)
            print("PRIVATE OPERATOR REVIEW: create one empty bucket; apply fixed tags, all four public blocks and TLS-deny policy.")
            print("One-day TTL; exact bucket:", args.bucket)
        elif args.operation in ("approve", "reject"):
            human_confirmation("APPROVE" if args.operation == "approve" else "REJECT",
                               args.bucket, args.scope_digest)
            adapter.decide(args.batch_id, args.scope_digest, principal,
                           "APPROVE_ONCE" if args.operation == "approve" else "REJECT")
            output = adapter.receipt(args.batch_id, principal)
        elif args.operation == "reconcile":
            output = adapter.receipt(args.batch_id, principal)
            cleanup = adapter.cleanup_state(args.batch_id, principal)
            if cleanup["status"] != "NOT_REQUESTED":
                print("CLEANUP_RECONCILIATION:" + json.dumps(cleanup, sort_keys=True), file=sys.stderr)
        else:
            human_confirmation("DELETE", args.bucket, args.batch_id)
            output = adapter.cleanup(args.batch_id, principal)
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        # Never print SDK errors, private account IDs or raw provider evidence.
        print("CANARY_OPERATOR_BLOCKED:" + (str(exc) if isinstance(exc, ValueError) else "PROVIDER_UNAVAILABLE"),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
