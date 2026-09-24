"""Exact, read-only prepare/freeze contract."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from .models import Finding


def _digest(value: dict[str, str]) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FrozenScope:
    batch_id: str
    scope_hash: str
    control_key: str
    account_alias: str
    resource_ref: str
    region: str
    evidence_digest: str
    provider_status: str = "NON_COMPLIANT"
    live_execution_authorized: bool = False

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-f0-9]{20}", self.batch_id):
            raise ValueError("invalid batch id")
        if not re.fullmatch(r"[a-f0-9]{24}", self.scope_hash):
            raise ValueError("invalid scope hash")
        if self.live_execution_authorized:
            raise ValueError("M2 cannot authorize execution")

    def public_dict(self) -> dict[str, object]:
        return {
            "version": 1,
            "batch_id": self.batch_id,
            "scope_hash": self.scope_hash,
            "control_key": self.control_key,
            "account_alias": self.account_alias,
            "resource_ref": self.resource_ref,
            "region": self.region,
            "evidence_digest": self.evidence_digest,
            "provider_status": self.provider_status,
            "live_execution_authorized": False,
        }


def freeze_finding(finding: Finding) -> FrozenScope:
    if finding.provider_status != "NON_COMPLIANT":
        raise ValueError("only a current non-compliant finding can be prepared")
    payload = {
        "control_key": finding.control_key,
        "account_alias": finding.account_alias,
        "resource_ref": finding.resource_ref,
        "region": finding.region,
        "evidence_digest": finding.evidence_digest,
        "provider_status": finding.provider_status,
    }
    digest = _digest(payload)
    scope_hash = hashlib.sha256(("scope:" + digest).encode()).hexdigest()[:24]
    batch_id = hashlib.sha256(("batch:" + scope_hash).encode()).hexdigest()[:20]
    return FrozenScope(
        batch_id=batch_id,
        scope_hash=scope_hash,
        control_key=finding.control_key,
        account_alias=finding.account_alias,
        resource_ref=finding.resource_ref,
        region=finding.region,
        evidence_digest=finding.evidence_digest,
    )
