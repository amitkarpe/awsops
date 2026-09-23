"""Application service for the complete M2 read/prepare/readback path."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from awsops.domain.freeze import FrozenScope, freeze_finding
from awsops.domain.models import Finding


class S3SslService:
    def __init__(self, read_report: Callable[[], dict[str, Any]]):
        self._read_report = read_report

    def status(self) -> dict[str, Any]:
        report = self._read_report()
        if report.get("control_key") != "s3_ssl" or report.get("read_only") is not True:
            raise ValueError("invalid s3_ssl evidence report")
        if report.get("aws_writes") != 0:
            raise ValueError("read report claims AWS writes")
        return report

    @staticmethod
    def _find(report: dict[str, Any], alias: str, resource_ref: str) -> Finding:
        matches = [
            row for row in report.get("findings", [])
            if row.get("account_alias") == alias and row.get("resource_ref") == resource_ref
        ]
        if len(matches) != 1:
            raise ValueError("exact finding not found")
        return Finding(**matches[0])

    def prepare(self, report: dict[str, Any], *, alias: str, resource_ref: str) -> FrozenScope:
        finding = self._find(report, alias, resource_ref)
        return freeze_finding(finding)

    def readback(self, frozen: FrozenScope) -> dict[str, Any]:
        current = self.status()
        try:
            finding = self._find(current, frozen.account_alias, frozen.resource_ref)
        except ValueError:
            return {
                "version": 1,
                "batch_id": frozen.batch_id,
                "scope_hash": frozen.scope_hash,
                "state": "UNAVAILABLE",
                "unchanged": False,
                "aws_writes": 0,
                "read_only": True,
            }
        unchanged = (
            finding.provider_status == frozen.provider_status
            and finding.evidence_digest == frozen.evidence_digest
        )
        return {
            "version": 1,
            "batch_id": frozen.batch_id,
            "scope_hash": frozen.scope_hash,
            "state": finding.provider_status,
            "finding_evidence_digest": finding.evidence_digest,
            "unchanged": unchanged,
            "aws_writes": 0,
            "read_only": True,
        }
