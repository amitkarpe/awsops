"""Public-safe final M3 Reject acceptance evidence contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

VERSION = "m3-reject-acceptance-v1"
FIELDS = frozenset({
    "version", "control", "account_alias", "pr_head", "scope_hash", "receipt_hash",
    "normal_auth", "native_decision", "dispatch_attempts", "provider_readback",
    "conversation_archived", "canary_stopped", "retained_services_unchanged", "sanitized",
})


def _text(value: Any, pattern: str, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError("invalid " + label)


@dataclass(frozen=True)
class M3AcceptanceEvidence:
    version: str
    control: str
    account_alias: str
    pr_head: str
    scope_hash: str
    receipt_hash: str
    normal_auth: bool
    native_decision: str
    dispatch_attempts: int
    provider_readback: str
    conversation_archived: bool
    canary_stopped: bool
    retained_services_unchanged: bool
    sanitized: bool

    def __post_init__(self) -> None:
        if self.version != VERSION or self.control != "s3_ssl":
            raise ValueError("invalid acceptance contract")
        _text(self.account_alias, r"lab-(dev|poc|qa|sec)", "account alias")
        _text(self.pr_head, r"[a-f0-9]{40}", "PR head")
        _text(self.scope_hash, r"[a-f0-9]{64}", "scope hash")
        _text(self.receipt_hash, r"[a-f0-9]{64}", "receipt hash")
        if type(self.normal_auth) is not bool or self.normal_auth is not True:
            raise ValueError("normal authentication not proven")
        if self.native_decision != "REJECTED":
            raise ValueError("native Reject not proven")
        if type(self.dispatch_attempts) is not int or self.dispatch_attempts != 0:
            raise ValueError("zero dispatch not proven")
        if self.provider_readback != "UNCHANGED":
            raise ValueError("provider readback not proven")
        for label, value in (
            ("conversation archive", self.conversation_archived),
            ("canary stop", self.canary_stopped),
            ("retained services", self.retained_services_unchanged),
            ("sanitization", self.sanitized),
        ):
            if type(value) is not bool or value is not True:
                raise ValueError(label + " not proven")

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_m3_acceptance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("invalid acceptance packet fields")
    packet = M3AcceptanceEvidence(**value)
    return packet.public_dict()
