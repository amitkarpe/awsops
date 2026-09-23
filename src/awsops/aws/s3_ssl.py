"""Fixed read-only S3 TLS evidence collector."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Mapping, Protocol

from awsops.controls.s3_ssl import CONTROL_KEY, requires_secure_transport
from awsops.domain.models import Finding, canonical_digest

ALIASES = ("lab-dev", "lab-poc", "lab-qa", "lab-sec")
REGION = "ap-southeast-1"
MAX_BUCKETS_PER_ACCOUNT = 20


class S3ReadClient(Protocol):
    def caller_account(self) -> str: ...
    def list_bucket_names(self) -> list[str]: ...
    def bucket_policy(self, bucket: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class AccountBinding:
    alias: str
    account_id: str

    def __post_init__(self) -> None:
        if self.alias not in ALIASES:
            raise ValueError("unregistered LAB alias")
        if not (len(self.account_id) == 12 and self.account_id.isdigit()):
            raise ValueError("invalid private account binding")


def resource_ref(bucket_name: str) -> str:
    return "bucket-ref-" + hashlib.sha256(bucket_name.encode("utf-8")).hexdigest()[:12]


def _finding(alias: str, ref: str, status: str) -> Finding:
    evidence = {
        "account_alias": alias,
        "control_key": CONTROL_KEY,
        "resource_ref": ref,
        "region": REGION,
        "provider_status": status,
    }
    return Finding(
        finding_id="finding-" + canonical_digest(evidence)[:20],
        account_alias=alias,
        control_key=CONTROL_KEY,
        resource_ref=ref,
        region=REGION,
        provider_status=status,
        evidence_digest=canonical_digest(evidence),
    )


def collect(
    bindings: tuple[AccountBinding, ...],
    client_factory: Callable[[AccountBinding], S3ReadClient],
) -> dict[str, Any]:
    aliases = tuple(binding.alias for binding in bindings)
    if aliases != ALIASES:
        raise ValueError("bindings must be the exact registered LAB aliases in canonical order")

    accounts: list[dict[str, Any]] = []
    all_findings: list[Finding] = []

    for binding in bindings:
        client = client_factory(binding)
        if client.caller_account() != binding.account_id:
            accounts.append({
                "alias": binding.alias,
                "identity_verified": False,
                "region": REGION,
                "state": "UNAVAILABLE",
                "reason": "ACCOUNT_MISMATCH",
                "resource_count": 0,
                "findings": [],
            })
            continue

        findings: list[Finding] = []
        for bucket in sorted(client.list_bucket_names())[:MAX_BUCKETS_PER_ACCOUNT]:
            ref = resource_ref(bucket)
            try:
                status = "COMPLIANT" if requires_secure_transport(client.bucket_policy(bucket)) else "NON_COMPLIANT"
            except Exception as exc:
                status = "NON_COMPLIANT" if "NoSuchBucketPolicy" in str(exc) else "UNAVAILABLE"
            findings.append(_finding(binding.alias, ref, status))

        findings.sort(key=lambda item: item.resource_ref)
        all_findings.extend(findings)
        public = [finding.public_dict() for finding in findings]
        account_evidence = {
            "alias": binding.alias,
            "identity_verified": True,
            "region": REGION,
            "state": "AVAILABLE" if findings else "UNAVAILABLE",
            "resource_count": len(findings),
            "status_counts": {
                status: sum(item.provider_status == status for item in findings)
                for status in ("COMPLIANT", "NON_COMPLIANT", "UNAVAILABLE")
            },
            "findings": public,
        }
        account_evidence["provider_evidence_digest"] = canonical_digest(account_evidence)
        accounts.append(account_evidence)

    public_findings = [finding.public_dict() for finding in all_findings]
    report = {
        "version": 1,
        "control_key": CONTROL_KEY,
        "region": REGION,
        "accounts": accounts,
        "findings": public_findings,
        "read_only": True,
        "aws_writes": 0,
        "raw_identifiers_emitted": False,
    }
    report["evidence_digest"] = canonical_digest(report)
    return report
