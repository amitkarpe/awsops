"""Exact, expiring preparation; this object is not an execution authorization."""
from __future__ import annotations

from dataclasses import dataclass
import uuid

from .models import EVIDENCE_VERSION, Finding, canonical_digest, require_text

MAX_EVIDENCE_AGE = 60
MAX_PREPARE_TTL = 300


@dataclass(frozen=True)
class FrozenScope:
    batch_id: str
    scope_hash: str
    finding: Finding
    issued_at: int
    expires_at: int
    live_execution_authorized: bool = False

    def __post_init__(self) -> None:
        require_text(self.batch_id, r"[a-f0-9]{32}", "batch id")
        require_text(self.scope_hash, r"[a-f0-9]{64}", "scope hash")
        if not isinstance(self.finding, Finding) or self.finding.provider_status != "NON_COMPLIANT":
            raise ValueError("only a known non-compliant finding may be frozen")
        if type(self.issued_at) is not int or type(self.expires_at) is not int:
            raise ValueError("invalid preparation time")
        if not 0 < self.expires_at - self.issued_at <= MAX_PREPARE_TTL:
            raise ValueError("invalid preparation TTL")
        if not 0 <= self.issued_at - self.finding.observed_at <= MAX_EVIDENCE_AGE:
            raise ValueError("stale or future provider evidence")
        if self.live_execution_authorized is not False or self.scope_hash != canonical_digest(self.payload()):
            raise ValueError("invalid frozen scope")

    def payload(self) -> dict:
        return {"version": EVIDENCE_VERSION, "batch_id": self.batch_id,
                "finding": self.finding.public_dict(), "issued_at": self.issued_at,
                "expires_at": self.expires_at, "live_execution_authorized": False}

    def public_dict(self) -> dict:
        return {**self.payload(), "scope_hash": self.scope_hash}


def freeze_finding(finding: Finding, *, now: int, ttl: int = MAX_PREPARE_TTL) -> FrozenScope:
    if type(ttl) is not int or not 1 <= ttl <= MAX_PREPARE_TTL:
        raise ValueError("invalid preparation TTL")
    batch_id = uuid.uuid4().hex
    payload = {"version": EVIDENCE_VERSION, "batch_id": batch_id,
               "finding": finding.public_dict(), "issued_at": now,
               "expires_at": now + ttl, "live_execution_authorized": False}
    return FrozenScope(batch_id, canonical_digest(payload), finding, now, now + ttl)
