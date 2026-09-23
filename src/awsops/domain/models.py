"""Small public-safe domain records for AWS Ops."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

_STATUS = {"COMPLIANT", "NON_COMPLIANT", "UNAVAILABLE"}
_ALIAS = re.compile(r"[a-z][a-z0-9-]{1,31}\Z")
_REF = re.compile(r"[a-z0-9-]{8,64}\Z")
_REGION = re.compile(r"[a-z]{2}-[a-z]+-\d\Z")


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Finding:
    finding_id: str
    account_alias: str
    control_key: str
    resource_ref: str
    region: str
    provider_status: str
    evidence_digest: str

    def __post_init__(self) -> None:
        if not _ALIAS.fullmatch(self.account_alias):
            raise ValueError("invalid account alias")
        if self.control_key != "s3_ssl":
            raise ValueError("unsupported M2 control")
        if not _REF.fullmatch(self.resource_ref):
            raise ValueError("invalid resource reference")
        if not _REGION.fullmatch(self.region):
            raise ValueError("invalid region")
        if self.provider_status not in _STATUS:
            raise ValueError("invalid provider status")
        if not re.fullmatch(r"[a-f0-9]{64}", self.evidence_digest):
            raise ValueError("invalid evidence digest")

    def public_dict(self) -> dict[str, str]:
        return {
            "finding_id": self.finding_id,
            "account_alias": self.account_alias,
            "control_key": self.control_key,
            "resource_ref": self.resource_ref,
            "region": self.region,
            "provider_status": self.provider_status,
            "evidence_digest": self.evidence_digest,
        }
