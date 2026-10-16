"""Fixed disposable-canary seam; SDK and operator wiring live in separate files.

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
    exists: bool = True
    public_blocked: bool = True
    tags_absent: bool = False
    public_block_absent: bool = False


class CanaryProvider(Protocol):
    # MOCK is mandatory for fakes. Only separately reviewed live wiring may use
    # APPROVED_LAB_WRITE; this module does not construct such a provider.
    mode: str
    def inspect(self, binding: CanaryBinding) -> Observation: ...
    def put_policy(self, binding: CanaryBinding, policy: dict,
                   before_call: Callable[[], None]) -> None: ...
    def create_bucket(self, binding: CanaryBinding, before_call: Callable[[], None]) -> None: ...
    def tag_bucket(self, binding: CanaryBinding, frozen_at: str, before_call: Callable[[], None]) -> None: ...
    def block_public_access(self, binding: CanaryBinding, before_call: Callable[[], None]) -> None: ...
    def inspect_cleanup(self, binding: CanaryBinding, *, deleting: bool = False) -> Observation: ...
    def delete_bucket(self, binding: CanaryBinding, before_call: Callable[[], None]) -> None: ...


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
            db.execute("CREATE TABLE IF NOT EXISTS operations (batch_id TEXT NOT NULL, step TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY(batch_id,step))")

    def _check_file(self) -> None:
        mode = self.path.lstat().st_mode
        if self.path.is_symlink() or not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
            raise ValueError("PRIVATE_LEDGER_REQUIRED")

    def _db(self):
        self._check_file()
        db = sqlite3.connect(self.path, isolation_level=None)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _read(self, *, allow_absent: bool = False) -> Observation:
        o = self.provider.inspect(self.binding)
        if (self.provider.mode != self.mode or type(o) is not Observation or o.account_id != self.binding.account_id
                or o.region != REGION or o.bucket != self.binding.bucket
                or type(o.observed_at) is not int
                or not 0 <= int(self.clock()) - o.observed_at <= MAX_EVIDENCE_AGE):
            raise ValueError("TARGET_OR_EVIDENCE_UNVERIFIED")
        if o.exists is False:
            if not allow_absent or o.policy is not None or o.empty is not True:
                raise ValueError("TARGET_OR_EVIDENCE_UNVERIFIED")
        elif (o.exists is not True or o.disposable is not True or o.empty is not True
              or o.public_blocked is not True):
            raise ValueError("TARGET_OR_EVIDENCE_UNVERIFIED")
        return o

    def _evidence_digest(self, o: Observation) -> str:
        return canonical_digest([self.binding.account_id, REGION, self.binding.bucket,
                                 o.policy, o.disposable, o.empty, o.exists, o.public_blocked])

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
        o = self._read(allow_absent=self.mode in ("MOCK", "APPROVED_LAB_WRITE"))
        if self.mode == "APPROVED_LAB_WRITE":
            # This milestone creates its own canary. Existing buckets are never targets.
            if o.exists:
                raise ValueError("EXISTING_BUCKET_NOT_A_CANARY")
            with closing(self._db()) as db:
                if db.execute("SELECT 1 FROM canaries WHERE binding=?", (self._binding_digest(),)).fetchone():
                    raise ValueError("CANARY_ALREADY_PREPARED")
        # Never overwrite an existing policy or weaken security to make a demo.
        if o.policy is not None:
            raise ValueError("CANARY_POLICY_ALREADY_PRESENT")
        now = int(self.clock())
        batch = {"batchId": "batch-canary-" + uuid.uuid4().hex,
                 "datasetId": "dataset-canary", "registryVersion": 1, "mode": self.mode,
                 "frozenAt": stamp(now), "expiresAt": stamp(now + MAX_PREPARE_TTL),
                 "targets": [{"findingId": "finding-canary", "resource": {
                     # Public MOCK identity is synthetic; private binding stays amit.
                     "accountAlias": "mock-a" if self.mode == "MOCK" else "amit", "resourceAlias": RESOURCE,
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
            result = self._result(batch, decision)
            if choice == "REJECT":
                result["run"]["record"]["status"] = "REJECTED"
            # Consume rejected decisions too. Commit BEFORE any provider operation.
            # Persist a reconcilable same-run audit atomically with the one-use
            # decision, including a crash immediately after this commit.
            db.execute("UPDATE canaries SET decision=?,result=? WHERE batch_id=?",
                       (json.dumps(decision), json.dumps(result), batch_id))
            db.commit()
        if choice != "REJECT":
            try:
                before = self._read(allow_absent=self.mode in ("MOCK", "APPROVED_LAB_WRITE"))
                if (self._evidence_digest(before) == batch["targets"][0]["evidenceDigest"] and before.policy is None
                        and batch["frozenAt"] <= stamp(int(self.clock())) < batch["expiresAt"]):
                    if self.mode == "MOCK":
                        lifecycle = ("create_bucket", "tag_bucket", "block_public_access", "put_policy")
                        if all(callable(getattr(self.provider, method, None)) for method in lifecycle):
                            self._apply_live(batch_id, batch, result)
                        else:
                            def apply_mock_policy(before_call: Callable[[], None]) -> None:
                                before_call()
                                self.provider.put_policy(self.binding, self._policy())

                            if self._attempt(batch_id, "policy", result, batch["expiresAt"], apply_mock_policy):
                                result["run"]["record"]["results"][0]["execution"] = "SUCCEEDED"
                    else:
                        self._apply_live(batch_id, batch, result)
                    if result["run"]["record"]["realWrites"] or result["run"]["record"]["simulatedWrites"]:
                        self._readback(result)
            except Exception:
                pass
        self._save(batch_id, result)
        return {"batch": envelope("Batch", deepcopy(batch)),
                "decision": envelope("Decision", decision), **result}

    def _attempt(self, batch_id: str, step: str, result: dict, expires_at: str,
                 call: Callable[[Callable[[], None]], None]) -> bool:
        """Journal intent, then count only a claimed SDK mutation boundary."""
        with closing(self._db()) as db:
            db.execute("INSERT INTO operations VALUES (?,?,'INTENT')", (batch_id, step))
        key = "simulatedWrites" if self.mode == "MOCK" else "realWrites"
        claimed = False

        def before_call() -> None:
            nonlocal claimed
            if claimed or not stamp(int(self.clock())) < expires_at:
                raise ValueError("MUTATION_BOUNDARY_EXPIRED_OR_REUSED")
            original = deepcopy(result)
            candidate = deepcopy(result)
            next_run = candidate["run"]["record"]
            next_run[key] = next_run["results"][0][key] = next_run[key] + 1
            next_run["status"] = "NEEDS_REVIEW"
            next_run["results"][0]["execution"] = "UNKNOWN"
            candidate["evidence"]["record"]["realWrites"] = next_run["realWrites"]
            with closing(self._db()) as db:
                db.execute("BEGIN IMMEDIATE")
                updated = db.execute("UPDATE operations SET state='CALLING' WHERE batch_id=? AND step=? AND state='INTENT'",
                                     (batch_id, step))
                if updated.rowcount != 1:
                    raise ValueError("MUTATION_CLAIM_UNAVAILABLE")
                db.execute("UPDATE canaries SET result=? WHERE batch_id=?", (json.dumps(candidate), batch_id))
                db.commit()
            # A slow local commit can consume the remaining approval window.
            if not stamp(int(self.clock())) < expires_at:
                with closing(self._db()) as db:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute("UPDATE operations SET state='REFUSED' WHERE batch_id=? AND step=? AND state='CALLING'",
                               (batch_id, step))
                    db.execute("UPDATE canaries SET result=? WHERE batch_id=?", (json.dumps(original), batch_id))
                    db.commit()
                raise ValueError("MUTATION_BOUNDARY_EXPIRED")
            result.clear()
            result.update(candidate)
            claimed = True

        try:
            call(before_call)
        except Exception:
            if not claimed:
                with closing(self._db()) as db:
                    db.execute("UPDATE operations SET state='REFUSED' WHERE batch_id=? AND step=? AND state='INTENT'",
                               (batch_id, step))
            return False
        if not claimed:
            with closing(self._db()) as db:
                db.execute("UPDATE operations SET state='REFUSED' WHERE batch_id=? AND step=? AND state='INTENT'",
                           (batch_id, step))
            return False
        with closing(self._db()) as db:
            db.execute("UPDATE operations SET state='ACK' WHERE batch_id=? AND step=?", (batch_id, step))
        return True

    def _apply_live(self, batch_id: str, batch: dict, result: dict) -> None:
        if not self._attempt(batch_id, "create", result, batch["expiresAt"],
                             lambda claim: self.provider.create_bucket(self.binding, claim)):
            return
        if not self._attempt(batch_id, "tags", result, batch["expiresAt"],
                             lambda claim: self.provider.tag_bucket(self.binding, batch["frozenAt"], claim)):
            return
        if not self._attempt(batch_id, "public_block", result, batch["expiresAt"],
                             lambda claim: self.provider.block_public_access(self.binding, claim)):
            return
        # The fixed policy is written only after fresh owner/tag/emptiness/PAB proof.
        before_policy = self._read()
        if before_policy.policy is not None:
            return
        if self._attempt(batch_id, "policy", result, batch["expiresAt"],
                         lambda claim: self.provider.put_policy(self.binding, self._policy(), claim)):
            result["run"]["record"]["results"][0]["execution"] = "SUCCEEDED"

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
            ops = dict(db.execute("SELECT step,state FROM operations WHERE batch_id=?", (batch_id,)))
        if not row or row[0] != principal or row[1] is None or row[2] != self._binding_digest():
            raise ValueError("NO_RECONCILABLE_RUN")
        result = json.loads(row[1])
        write_ops = {step: state for step, state in ops.items() if step != "delete"}
        attempted = sum(state in ("CALLING", "ACK") for state in write_ops.values())
        if attempted:
            r = result["run"]["record"]
            key = "simulatedWrites" if self.mode == "MOCK" else "realWrites"
            r[key] = r["results"][0][key] = max(r[key], attempted)
            result["evidence"]["record"]["realWrites"] = r["realWrites"]
            if "CALLING" in write_ops.values():
                r["status"] = "NEEDS_REVIEW"
                r["results"][0]["execution"] = "UNKNOWN"
            elif all(write_ops.get(step) == "ACK" for step in
                     ("create", "tags", "public_block", "policy")):
                # Recover a crash after the final SDK ACK but before decide()
                # saved its completed execution result. Readback remains an
                # independent observation and does not establish compliance.
                r["results"][0]["execution"] = "SUCCEEDED"
        if result["run"]["record"]["status"] == "NEEDS_REVIEW" and "delete" not in ops:
            self._readback(result)
            self._save(batch_id, result)
        return result

    def receipt(self, batch_id: str, principal: str) -> list[dict]:
        """One sanitized canonical bundle for the existing core2 reader."""
        with closing(self._db()) as db:
            row = db.execute("SELECT payload,principal,decision,binding FROM canaries WHERE batch_id=?",
                             (batch_id,)).fetchone()
        if not row or row[1] != principal or row[2] is None or row[3] != self._binding_digest():
            raise ValueError("NO_RECONCILABLE_RUN")
        result = self.reconcile(batch_id, principal)
        return [envelope("Batch", json.loads(row[0])), envelope("Decision", json.loads(row[2])),
                result["run"], result["evidence"]]

    def cleanup(self, batch_id: str, principal: str, *, expires_at: int) -> dict:
        """Delete only an acknowledged task-created empty bucket; retain receipts."""
        if self.mode not in ("MOCK", "APPROVED_LAB_WRITE"):
            raise ValueError("LIVE_CLEANUP_ONLY")
        if type(expires_at) is not int or int(self.clock()) >= expires_at:
            raise ValueError("CLEANUP_AUTHORITY_EXPIRED")
        with closing(self._db()) as db:
            row = db.execute("SELECT principal,result,binding FROM canaries WHERE batch_id=?", (batch_id,)).fetchone()
            ops = dict(db.execute("SELECT step,state FROM operations WHERE batch_id=?", (batch_id,)))
        if (not row or row[0] != principal or row[1] is None or row[2] != self._binding_digest()
                or ops.get("create") != "ACK" or "delete" in ops):
            raise ValueError("CLEANUP_NOT_PROVEN")
        # The provider accepts only an acknowledged creation and a contiguous
        # sequence of ACK or known-no-call setup states, then checks current state.
        self.provider.inspect_cleanup(self.binding)
        with closing(self._db()) as db:
            db.execute("INSERT INTO operations VALUES (?,?,'INTENT')", (batch_id, "delete"))
        claimed = False

        def before_call() -> None:
            nonlocal claimed
            if int(self.clock()) >= expires_at:
                raise ValueError("CLEANUP_AUTHORITY_EXPIRED")
            with closing(self._db()) as db:
                db.execute("BEGIN IMMEDIATE")
                updated = db.execute("UPDATE operations SET state='CALLING' WHERE batch_id=? AND step='delete' AND state='INTENT'",
                                     (batch_id,))
                if updated.rowcount != 1:
                    raise ValueError("DELETE_CLAIM_UNAVAILABLE")
                db.commit()
            # A delayed durable claim must not authorize a call after cleanup expiry.
            if int(self.clock()) >= expires_at:
                with closing(self._db()) as db:
                    db.execute("BEGIN IMMEDIATE")
                    db.execute("UPDATE operations SET state='REFUSED' WHERE batch_id=? AND step='delete' AND state='CALLING'",
                               (batch_id,))
                    db.commit()
                raise ValueError("CLEANUP_AUTHORITY_EXPIRED")
            claimed = True

        try:
            self.provider.delete_bucket(self.binding, before_call)
        except Exception:
            if not claimed:
                with closing(self._db()) as db:
                    db.execute("UPDATE operations SET state='REFUSED' WHERE batch_id=? AND step='delete' AND state='INTENT'",
                               (batch_id,))
                return {"status": "REFUSED_NO_CALL", "deleted": False}
            return {"status": "UNKNOWN", "deleted": False}
        if not claimed:
            with closing(self._db()) as db:
                db.execute("UPDATE operations SET state='REFUSED' WHERE batch_id=? AND step='delete' AND state='INTENT'",
                           (batch_id,))
            return {"status": "REFUSED_NO_CALL", "deleted": False}
        # A successful SDK acknowledgment is insufficient on its own.
        try:
            absent = self._read(allow_absent=True).exists is False
        except Exception:
            absent = False
        if not absent:
            return {"status": "UNKNOWN", "deleted": False}
        with closing(self._db()) as db:
            db.execute("UPDATE operations SET state='ACK' WHERE batch_id=? AND step='delete'", (batch_id,))
        return {"status": "DELETED", "deleted": True}

    def cleanup_state(self, batch_id: str, principal: str) -> dict:
        """Read-only reconciliation of an uncertain delete; never replay it."""
        with closing(self._db()) as db:
            row = db.execute("SELECT principal,binding FROM canaries WHERE batch_id=?", (batch_id,)).fetchone()
            op = db.execute("SELECT state FROM operations WHERE batch_id=? AND step='delete'",
                            (batch_id,)).fetchone()
        if not row or row[0] != principal or row[1] != self._binding_digest():
            raise ValueError("NO_RECONCILABLE_RUN")
        if op is None:
            return {"status": "NOT_REQUESTED"}
        if op[0] in ("INTENT", "REFUSED"):
            return {"status": "REFUSED_NO_CALL", "deleted": False}
        try:
            absent = self._read(allow_absent=True).exists is False
        except Exception:
            return {"status": "UNKNOWN"}
        if op[0] == "ACK":
            return {"status": "DELETED_CONFIRMED" if absent else "DRIFT"}
        return {"status": "ABSENT_AFTER_UNKNOWN" if absent else "NEEDS_REVIEW"}
