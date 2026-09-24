"""Explicit opt-in LAB read/prepare/readback probe; no deployment or mutation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from awsops.aws.boto3_s3_ssl import assume_role_factory
from awsops.aws.s3_ssl import AccountBinding, ALIASES, REGION, collect, validate_bindings
from .s3_ssl_service import S3SslService


def load_config(path: Path) -> tuple[dict, tuple[AccountBinding, ...]]:
    if path.stat().st_size > 8192:
        raise ValueError("oversized private configuration")
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) != {"region", "source_account_id", "profile", "accounts"}:
        raise ValueError("invalid private configuration fields")
    if config["region"] != REGION or not isinstance(config["profile"], str) or not config["profile"]:
        raise ValueError("invalid private runtime settings")
    if not isinstance(config["accounts"], list) or any(not isinstance(a, dict) or set(a) != {"alias", "account_id"} for a in config["accounts"]):
        raise ValueError("invalid registered bindings")
    bindings = tuple(AccountBinding(**a) for a in config["accounts"])
    validate_bindings(bindings)
    return config, bindings


def probe(service: S3SslService, alias: str) -> dict[str, Any]:
    report = service.status()
    if not report["complete"]:
        return {"outcome": "BLOCKED_INCOMPLETE", "report": report}
    candidates = [row for row in report["findings"] if row["account_alias"] == alias and row["provider_status"] == "NON_COMPLIANT"]
    if not candidates:
        return {"outcome": "NO_ELIGIBLE_CANDIDATE", "report": report}
    target = sorted(candidates, key=lambda row: row["resource_ref"])[0]
    frozen = service.prepare(alias=alias, resource_ref=target["resource_ref"], expected_evidence_digest=target["evidence_digest"])
    readback = service.readback(frozen)
    return {"outcome": "PASS" if readback["unchanged"] else "READBACK_NOT_UNCHANGED",
            "report": report, "selected": target, "prepare": frozen.public_dict(), "readback": readback,
            "native_decision": "NOT_RUN", "remediation": "NOT_IMPLEMENTED"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Existing personal-LAB read roles only; no AWS writes.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--alias", choices=ALIASES, required=True)
    parser.add_argument("--confirm-lab-read-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        config, bindings = load_config(args.config)
        import boto3
        source = boto3.Session(profile_name=config["profile"], region_name=REGION)
        factory = assume_role_factory(source, expected_source_account=config["source_account_id"])
        result = probe(S3SslService(lambda: collect(bindings, factory)), args.alias)
    except Exception:
        # Never print provider exceptions, local paths, policy bodies or credentials.
        print(json.dumps({"outcome": "BLOCKED", "reason": "PRIVATE_CONFIG_OR_PROVIDER_CHECK_FAILED"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["outcome"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
