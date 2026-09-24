"""Bounded, identity-verified provider evidence; no mutation methods."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from typing import Any, Callable, Mapping, Protocol

from awsops.controls.s3_ssl import evaluate_policy
from awsops.domain.models import EVIDENCE_VERSION, Finding, STATUSES, canonical_digest

ALIASES = ("lab-dev", "lab-poc", "lab-qa", "lab-sec")
REGION = "ap-southeast-1"
PAGE_SIZE = 20
MAX_PAGES = 5
MAX_BUCKETS_PER_ACCOUNT = 20


class S3ReadClient(Protocol):
    region: str
    def caller_account(self) -> str: ...
    def list_bucket_page(self, token: str | None) -> Mapping[str, Any]: ...
    def bucket_policy(self, bucket: str) -> Mapping[str, Any] | None: ...


@dataclass(frozen=True)
class AccountBinding:
    alias: str
    account_id: str = field(repr=False)
    region: str = REGION

    def __post_init__(self) -> None:
        if self.alias not in ALIASES or self.region != REGION:
            raise ValueError("unregistered LAB alias or Region")
        if not isinstance(self.account_id, str) or len(self.account_id) != 12 or not self.account_id.isascii() or not self.account_id.isdigit():
            raise ValueError("invalid private account binding")


def validate_bindings(bindings: tuple[AccountBinding, ...]) -> None:
    if tuple(b.alias for b in bindings) != ALIASES or len({b.account_id for b in bindings}) != len(ALIASES):
        raise ValueError("exact distinct registered LAB bindings required")


def resource_ref(binding: AccountBinding, name: str) -> str:
    return "bucket-ref-" + canonical_digest([binding.alias, binding.account_id, binding.region, name])[:20]


def _inventory(client: S3ReadClient) -> tuple[list[str], bool, str, int]:
    names: list[str] = []
    tokens: set[str] = set()
    token = None
    for page_number in range(1, MAX_PAGES + 1):
        response = client.list_bucket_page(token)
        if not isinstance(response, Mapping) or not isinstance(response.get("Buckets"), list):
            return [], False, "MALFORMED_INVENTORY", page_number
        rows = response["Buckets"]
        if len(rows) > PAGE_SIZE:
            return [], False, "OVERSIZED_PAGE", page_number
        for row in rows:
            if not isinstance(row, Mapping) or not isinstance(row.get("Name"), str) or re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", row["Name"]) is None:
                return [], False, "MALFORMED_BUCKET", page_number
            if row.get("BucketRegion") != REGION:
                return [], False, "BUCKET_REGION_UNVERIFIED", page_number
            if row["Name"] in names:
                return [], False, "DUPLICATE_BUCKET", page_number
            names.append(row["Name"])
        next_token = response.get("ContinuationToken")
        if next_token is not None and (not isinstance(next_token, str) or not 1 <= len(next_token) <= 1024 or next_token in tokens):
            return [], False, "INVALID_CONTINUATION", page_number
        if len(names) > MAX_BUCKETS_PER_ACCOUNT or (len(names) == MAX_BUCKETS_PER_ACCOUNT and next_token is not None):
            return sorted(names)[:MAX_BUCKETS_PER_ACCOUNT], False, "RESOURCE_LIMIT", page_number
        if next_token is None:
            return sorted(names), True, "COMPLETE", page_number
        tokens.add(next_token)
        token = next_token
    return sorted(names), False, "PAGE_LIMIT", MAX_PAGES


def collect(bindings: tuple[AccountBinding, ...], client_factory: Callable[[AccountBinding], S3ReadClient],
            *, clock: Callable[[], float] = time.time) -> dict[str, Any]:
    validate_bindings(bindings)
    accounts: list[dict] = []
    findings: list[dict] = []
    for binding in bindings:
        account = {"alias": binding.alias, "region": REGION, "identity_verified": False,
                   "complete": False, "state": "UNAVAILABLE", "reason": "PROVIDER_UNAVAILABLE",
                   "resource_count": 0, "pages_read": 0, "findings": []}
        try:
            client = client_factory(binding)
            if client.region != REGION:
                account["reason"] = "CLIENT_REGION_MISMATCH"
                accounts.append(account)
                continue
            if client.caller_account() != binding.account_id:
                account["reason"] = "ACCOUNT_MISMATCH"
                accounts.append(account)
                continue
            account["identity_verified"] = True
            names, complete, reason, pages = _inventory(client)
            account.update(complete=complete, reason=reason, pages_read=pages)
        except Exception:
            accounts.append(account)
            continue
        rows: list[dict] = []
        for name in names:
            ref = resource_ref(binding, name)
            policy = None
            read_ok = False
            try:
                policy = client.bucket_policy(name)
                # Reject non-JSON provider values; do not hash exception messages.
                canonical_digest(policy)
                status = evaluate_policy(policy, name)
                read_ok = True
            except Exception:
                status = "UNAVAILABLE"
                account["complete"] = False
                account["reason"] = "POLICY_READ_UNAVAILABLE"
            evidence = {"version": EVIDENCE_VERSION, "alias": binding.alias,
                        "account_binding_digest": canonical_digest([binding.account_id, REGION]),
                        "region": REGION, "resource_ref": ref, "status": status,
                        "provider_policy": policy if read_ok else {"read": "UNAVAILABLE"}}
            finding = Finding("finding-" + canonical_digest([binding.alias, ref])[:20],
                              binding.alias, "s3_ssl", ref, REGION, status,
                              canonical_digest(evidence), int(clock()))
            rows.append(finding.public_dict())
        rows.sort(key=lambda row: row["resource_ref"])
        account.update(findings=rows, resource_count=len(rows),
                       state="AVAILABLE" if account["complete"] else "PARTIAL",
                       status_counts={s: sum(row["provider_status"] == s for row in rows) for s in sorted(STATUSES)})
        account["provider_evidence_digest"] = canonical_digest([row["evidence_digest"] for row in rows])
        accounts.append(account)
        findings.extend(rows)
    complete = all(a["identity_verified"] and a["complete"] for a in accounts)
    report = {"version": EVIDENCE_VERSION, "control_key": "s3_ssl", "region": REGION,
              "accounts": accounts, "findings": findings, "complete": complete, "partial": not complete,
              "observed_at": int(clock()), "read_only": True, "aws_writes": 0,
              "raw_identifiers_emitted": False}
    # Timestamps describe freshness, not policy equality.
    report["evidence_digest"] = canonical_digest([
        {"alias": a["alias"], "verified": a["identity_verified"], "complete": a["complete"],
         "reason": a["reason"], "evidence": a.get("provider_evidence_digest")} for a in accounts])
    return report
