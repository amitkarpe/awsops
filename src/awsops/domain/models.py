"""Validated, public-safe evidence records; no runtime or provider dependencies."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any

EVIDENCE_VERSION = "s3-ssl-policy-v2"
STATUSES = frozenset({"COMPLIANT", "NON_COMPLIANT", "UNKNOWN", "UNAVAILABLE"})


def canonical_digest(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def require_text(value: Any, pattern: str, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError("invalid " + label)


@dataclass(frozen=True)
class Finding:
    finding_id: str
    account_alias: str
    control_key: str
    resource_ref: str
    region: str
    provider_status: str
    evidence_digest: str
    observed_at: int
    evidence_version: str = EVIDENCE_VERSION

    def __post_init__(self) -> None:
        require_text(self.finding_id, r"finding-[a-f0-9]{20}", "finding reference")
        require_text(self.account_alias, r"lab-(dev|poc|qa|sec)", "account alias")
        require_text(self.resource_ref, r"bucket-ref-[a-f0-9]{20}", "resource reference")
        require_text(self.evidence_digest, r"[a-f0-9]{64}", "evidence digest")
        if self.control_key != "s3_ssl" or self.region != "ap-southeast-1":
            raise ValueError("unsupported control or Region")
        if self.provider_status not in STATUSES or self.evidence_version != EVIDENCE_VERSION:
            raise ValueError("invalid evidence contract")
        if type(self.observed_at) is not int or self.observed_at < 0:
            raise ValueError("invalid observation time")

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)
