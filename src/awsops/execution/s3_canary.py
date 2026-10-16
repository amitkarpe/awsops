"""Fixed disposable-canary seam. No SDK, CLI, endpoint or live provider wiring.

Only a trusted authenticated backend may call prepare/decide. Imported Batch or
Decision JSON is never authority. The injected provider owns private resolution
and must attest exact identity, disposable ownership and emptiness on every read.
Legacy native decisions remain reject-only and are not consumed here.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from typing import Callable, Protocol
import uuid

from awsops.controls.s3_ssl import evaluate_policy
from awsops.domain.freeze import MAX_EVIDENCE_AGE, MAX_PREPARE_TTL
from awsops.domain.models import canonical_digest, require_text

REGION = "ap-southeast-1"
RESOURCE = "resource-disposable-s3-canary"
CONTROL = "s3-ssl-requests-only"


def stamp(now: int) -> str:
    return datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")


def envelope(kind: str, record: dict) -> dict:
    return {"schemaVersion": "defence-factory/1", "kind": kind, "record": record}


@dataclass(frozen=True, repr=False)
class CanaryBinding:
    account_id: str = field(repr=False)
    bucket: str = field(repr=False)
    account_alias: str = "amit"
    region: str = REGION

    def __post_init__(self) -> None:
        require_text(self.account_id, r"[0-9]{12}", "private account binding")
        require_text(self.bucket, r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", "private bucket binding")
        if self.account_alias != "amit" or self.region != REGION:
            raise ValueError("UNAPPROVED_TARGET")


@dataclass(frozen=True, repr=False)
class Observation:
    account_id: str
    region: str
    bucket: str
    disposable: bool
    empty: bool
    observed_at: int
    policy: dict | None


class CanaryProvider(Protocol):
    # MOCK is mandatory for fakes. Only separately reviewed live wiring may use
    # APPROVED_LAB_WRITE; this module does not construct such a provider.
    mode: str
    def inspect(self, binding: CanaryBinding) -> Observation: ...
    def put_policy(self, binding: CanaryBinding, policy: dict) -> None: ...


class CanaryAdapter:
    """One private SQLite file, fixed target/action, durable claim before writes.

    The owner-private directory/file and authenticated caller are trusted, just as
    with DecisionStore. A principal digest is a binding, not authentication. Store
    must persist across restarts; lost/ambiguous claims never cause write replay.
    """
    def __init__(self, path: Path, binding: CanaryBinding, provider: CanaryProvider,
                 *, source_revision: str, source_version: str, clock: Callable = time.time):
        require_text(source_revision, r"[a-f0-9]{40}", "source revision")
        require_text(source_version, r"v[0-9]+\.[0-9]+\.[0-9]+-mock", "contract source version")
        if type(binding) is not CanaryBinding or provider.mode not in ("MOCK", "APPROVED_LAB_WRITE"):
            raise ValueError("UNAPPROVED_TARGET")
        self.path, self.binding, self.provider = Path(path), binding, provider
        self.revision, self.version, self.clock, self.mode = source_revision, source_version, clock, provider.mode
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600) if not self.path.exists() else None
        if fd is not None:
            os.close(fd)
        self._check_file()
        with closing(self._db()) as db:
            db.execute("CREATE TABLE IF NOT EXISTS canaries (batch_id TEXT PRIMARY KEY, payload TEXT NOT NULL, principal TEXT NOT NULL, binding TEXT NOT NULL, decision TEXT, result TEXT)")

    def _check_file(self) -> None:
        mode = self.path.lstat().st_mode
        if self.path.is_symlink() or not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
            raise ValueError("PRIVATE_LEDGER_REQUIRED")

    def _db(self):
        self._check_file()
        db = sqlite3.connect(self.path, isolation_level=None)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _read(self) -> Observation:
        o = self.provider.inspect(self.binding)
        if (self.provider.mode != self.mode or type(o) is not Observation or o.account_id != self.binding.account_id
                or o.region != REGION or o.bucket != self.binding.bucket
                or o.disposable is not True or o.empty is not True
                or type(o.observed_at) is not int
                or not 0 <= int(self.clock()) - o.observed_at <= MAX_EVIDENCE_AGE):
            raise ValueError("TARGET_OR_EVIDENCE_UNVERIFIED")
        return o

    def _evidence_digest(self, o: Observation) -> str:
        return canonical_digest([self.binding.account_id, REGION, self.binding.bucket,
                                 o.policy, o.disposable, o.empty])

    def _binding_digest(self) -> str:
        return canonical_digest([self.binding.account_id, self.binding.bucket, REGION, self.mode])

    def _policy(self) -> dict:
        bucket = "arn:aws:s3:::" + self.binding.bucket
        return {"Version": "2012-10-17", "Statement": [{
            "Effect": "Deny", "Principal": "*", "Action": "s3:*",
            "Resource": [bucket, bucket + "/*"],
            "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}

    def prepare(self, principal: str) -> dict:
        require_text(principal, r"[a-f0-9]{64}", "trusted principal binding")
        o = self._read()
        # Never overwrite an existing policy or weaken security to make a demo.
        if o.policy is not None:
            raise ValueError("CANARY_POLICY_ALREADY_PRESENT")
        now = int(self.clock())
        batch = {"batchId": "batch-canary-" + uuid.uuid4().hex,
                 "datasetId": "dataset-canary", "registryVersion": 1, "mode": self.mode,
                 "frozenAt": stamp(now), "expiresAt": stamp(now + MAX_PREPARE_TTL),
                 "targets": [{"findingId": "finding-canary", "resource": {
                     "accountAlias": "amit", "resourceAlias": RESOURCE,
                     "resourceType": "AWS::S3::Bucket", "region": REGION},
                     "controlId": CONTROL, "revision": 1,
                     "evidenceDigest": self._evidence_digest(o),
                     "capabilityId": "s3-require-tls", "expectedChange": "DENY_INSECURE_TRANSPORT"}]}
        batch["scopeDigest"] = canonical_digest(batch)
        with closing(self._db()) as db:
            db.execute("INSERT INTO canaries VALUES (?,?,?,?,NULL,NULL)",
                       (batch["batchId"], json.dumps(batch), principal, self._binding_digest()))
        return envelope("Batch", deepcopy(batch))

    def decide(self, batch_id: str, scope_digest: str, principal: str, choice: str) -> dict:
        if choice not in ("APPROVE_ONCE", "REJECT"):
            raise ValueError("INVALID_DECISION")
        with closing(self._db()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload,principal,decision,binding FROM canaries WHERE batch_id=?", (batch_id,)).fetchone()
            if not row or row[1] != principal or row[2] is not None or row[3] != self._binding_digest():
                raise ValueError("UNAUTHORIZED_OR_CONSUMED")
            batch = json.loads(row[0])
            scope = {k: v for k, v in batch.items() if k != "scopeDigest"}
            if (canonical_digest(scope) != scope_digest or batch["scopeDigest"] != scope_digest
                    or batch["mode"] != self.mode):
                raise ValueError("SCOPE_DRIFT")
            now = int(self.clock())
            if not batch["frozenAt"] <= stamp(now) < batch["expiresAt"]:
                raise ValueError("PREPARATION_EXPIRED_OR_FUTURE")
            decision = {"decisionId": "decision-canary-" + uuid.uuid4().hex,
                        "batchId": batch_id, "scopeDigest": scope_digest, "choice": choice,
                        "decidedAt": stamp(now), "expiresAt": batch["expiresAt"],
                        "principalBindingDigest": principal, "receiptId": "receipt-canary-" + uuid.uuid4().hex}
            # Consume rejected decisions too. Commit BEFORE any provider operation.
            db.execute("UPDATE canaries SET decision=? WHERE batch_id=?", (json.dumps(decision), batch_id))
            db.commit()
        result = self._result(batch, decision)
        if choice == "REJECT":
            result["run"]["record"]["status"] = "REJECTED"
        else:
            try:
                before = self._read()
                if (self._evidence_digest(before) == batch["targets"][0]["evidenceDigest"] and before.policy is None
                        and batch["frozenAt"] <= stamp(int(self.clock())) < batch["expiresAt"]):
                    r = result["run"]["record"]
                    # Count attempted calls conservatively even on uncertain acknowledgment.
                    key = "simulatedWrites" if self.mode == "MOCK" else "realWrites"
                    r[key] = r["results"][0][key] = 1
                    r["status"] = "NEEDS_REVIEW"
                    r["results"][0]["execution"] = "UNKNOWN"
                    result["evidence"]["record"]["realWrites"] = r["realWrites"]
                    self._save(batch_id, result)
                    try:
                        self.provider.put_policy(self.binding, self._policy())
                        r["results"][0]["execution"] = "SUCCEEDED"
                    except Exception:
                        pass  # Never export provider exception bodies or retry writes.
                    self._readback(result)
            except Exception:
                pass
        self._save(batch_id, result)
        return {"decision": envelope("Decision", decision), **result}

    def _result(self, batch: dict, decision: dict) -> dict:
        run_id = "run-canary-" + decision["decisionId"].removeprefix("decision-canary-")
        return {"run": envelope("Run", {"runId": run_id, "batchId": batch["batchId"],
            "decisionId": decision["decisionId"], "mode": self.mode, "status": "BLOCKED",
            "realWrites": 0, "simulatedWrites": 0, "results": [{"findingId": "finding-canary",
            "resourceAlias": RESOURCE, "execution": "NOT_RUN", "providerReadback": "NOT_ACQUIRED",
            "compliance": "UNKNOWN", "freshness": "NOT_VERIFIED", "realWrites": 0,
            "simulatedWrites": 0, "receiptId": decision["receiptId"]}]}),
            "evidence": envelope("Evidence", {"evidenceId": "evidence-canary-" + uuid.uuid4().hex,
            "runId": run_id, "sourceRevision": self.revision, "sourceVersion": self.version,
            "hostedVersion": None, "recordedAt": stamp(int(self.clock())), "realWrites": 0,
            "provenance": "SYNTHETIC" if self.mode == "MOCK" else "TRUSTED_PROVIDER_READ",
            "limitation": "SYNTHETIC_ONLY" if self.mode == "MOCK" else "FRESHNESS_NOT_VERIFIED"})}

    def _readback(self, result: dict) -> None:
        r = result["run"]["record"]
        r["status"] = "NEEDS_REVIEW"
        try:
            observed = self._read()
            match = evaluate_policy(observed.policy, self.binding.bucket) == "COMPLIANT"
            r["results"][0]["providerReadback"] = "MATCH" if match else "MISMATCH"
        except Exception:
            r["results"][0]["providerReadback"] = "UNKNOWN"
        # Config evaluation/freshness remain independent and unacquired: never VERIFIED.
        result["evidence"]["record"]["realWrites"] = r["realWrites"]
        result["evidence"]["record"]["recordedAt"] = stamp(int(self.clock()))

    def _save(self, batch_id: str, result: dict) -> None:
        with closing(self._db()) as db:
            db.execute("UPDATE canaries SET result=? WHERE batch_id=?", (json.dumps(result), batch_id))

    def reconcile(self, batch_id: str, principal: str) -> dict:
        """Read only, SAME run. No decision replay or fresh write on uncertainty."""
        with closing(self._db()) as db:
            row = db.execute("SELECT principal,result,binding FROM canaries WHERE batch_id=?", (batch_id,)).fetchone()
        if not row or row[0] != principal or row[1] is None or row[2] != self._binding_digest():
            raise ValueError("NO_RECONCILABLE_RUN")
        result = json.loads(row[1])
        if result["run"]["record"]["status"] == "NEEDS_REVIEW":
            self._readback(result)
        return result
