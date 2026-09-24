"""Fresh provider-backed preparation; UI input only nominates a candidate."""
from __future__ import annotations

from copy import deepcopy
import time
from typing import Any, Callable

from awsops.aws.s3_ssl import ALIASES, REGION
from awsops.domain.freeze import MAX_EVIDENCE_AGE, FrozenScope, freeze_finding
from awsops.domain.models import EVIDENCE_VERSION, Finding, require_text

MAX_PENDING = 128


class S3SslService:
    def __init__(self, read_report: Callable[[], dict[str, Any]], *, clock: Callable[[], float] = time.time):
        self._read_report = read_report
        self._clock = clock
        self._frozen: dict[str, FrozenScope] = {}

    def status(self) -> dict[str, Any]:
        report = self._read_report()
        if not isinstance(report, dict) or report.get("version") != EVIDENCE_VERSION:
            raise ValueError("invalid evidence version")
        if report.get("control_key") != "s3_ssl" or report.get("region") != REGION or report.get("read_only") is not True:
            raise ValueError("invalid s3_ssl evidence report")
        if type(report.get("aws_writes")) is not int or report["aws_writes"] != 0:
            raise ValueError("invalid read-only capability")
        accounts = report.get("accounts", [])
        if tuple(a.get("alias") for a in accounts) != ALIASES:
            raise ValueError("invalid registered account coverage")
        if type(report.get("complete")) is not bool or report.get("partial") is not (not report["complete"]):
            raise ValueError("invalid completeness contract")
        for row in report.get("findings", []):
            Finding(**row)
        return deepcopy(report)

    @staticmethod
    def _find(report: dict, alias: str, ref: str) -> Finding:
        if report["complete"] is not True or any(a.get("identity_verified") is not True or a.get("complete") is not True for a in report["accounts"]):
            raise ValueError("incomplete or unverified evidence cannot prepare")
        matches = [row for row in report["findings"] if row["account_alias"] == alias and row["resource_ref"] == ref]
        if len(matches) != 1:
            raise ValueError("exact finding unavailable")
        return Finding(**matches[0])

    def prepare(self, *, alias: str, resource_ref: str, expected_evidence_digest: str) -> FrozenScope:
        require_text(expected_evidence_digest, r"[a-f0-9]{64}", "expected evidence digest")
        finding = self._find(self.status(), alias, resource_ref)
        if finding.evidence_digest != expected_evidence_digest:
            raise ValueError("provider evidence changed; read and select again")
        now = int(self._clock())
        self._frozen = {key: value for key, value in self._frozen.items() if value.expires_at > now}
        if len(self._frozen) >= MAX_PENDING:
            raise ValueError("pending preparation limit reached")
        frozen = freeze_finding(finding, now=now)
        self._frozen[frozen.batch_id] = frozen
        return frozen

    def readback(self, frozen: FrozenScope) -> dict:
        if not isinstance(frozen, FrozenScope) or self._frozen.get(frozen.batch_id) != frozen:
            raise ValueError("unknown or edited frozen batch")
        if int(self._clock()) >= frozen.expires_at:
            raise ValueError("frozen batch expired")
        result = {"version": EVIDENCE_VERSION, "batch_id": frozen.batch_id,
                  "scope_hash": frozen.scope_hash, "state": "UNAVAILABLE", "unchanged": False,
                  "read_only": True, "aws_writes": 0}
        try:
            finding = self._find(self.status(), frozen.finding.account_alias, frozen.finding.resource_ref)
        except ValueError:
            return result
        if not 0 <= int(self._clock()) - finding.observed_at <= MAX_EVIDENCE_AGE:
            return result
        result.update(state=finding.provider_status, finding_evidence_digest=finding.evidence_digest,
                      unchanged=finding.provider_status == frozen.finding.provider_status
                      and finding.evidence_version == frozen.finding.evidence_version
                      and finding.evidence_digest == frozen.finding.evidence_digest)
        return result
