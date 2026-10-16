"""One exact, journal-backed personal-LAB S3 canary provider.

Only the operator entrypoint constructs this class. SDK calls stay fixed and
private; no caller-supplied AWS command, policy, account or inventory is accepted.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable

from awsops.domain.models import canonical_digest
from awsops.execution.s3_canary import CanaryBinding, Observation, REGION


def _error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    return str(response.get("Error", {}).get("Code", "")) if isinstance(response, dict) else ""


def _object(pairs: list[tuple[str, Any]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("DUPLICATE_POLICY_KEY")
        value[key] = item
    return value


def _reject_constant(_value: str) -> None:
    raise ValueError("INVALID_POLICY_NUMBER")


def fixed_policy(bucket: str) -> dict:
    resource = "arn:aws:s3:::" + bucket
    return {"Version": "2012-10-17", "Statement": [{
        "Effect": "Deny", "Principal": "*", "Action": "s3:*",
        "Resource": [resource, resource + "/*"],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}


def frozen_tags(binding: CanaryBinding, frozen_at: str) -> dict[str, str]:
    day = datetime.fromisoformat(frozen_at.replace("Z", "+00:00")).astimezone(timezone.utc).date()
    expiry = (day + timedelta(days=1)).strftime("%d-%m-%y")
    return {"Name": binding.bucket, "dev": "amit", "project": "awsops",
            "created": day.isoformat(), "tools": "cdx", "environment": "dev",
            "owner": "amit", "version": "v1", "TTL": expiry, "ttl": expiry,
            "purpose": "disposable-s3-tls-canary", "phase": "issue90",
            "cleanup": "delete"}


class Boto3CanaryProvider:
    mode = "APPROVED_LAB_WRITE"

    def __init__(self, session: Any, binding: CanaryBinding, ledger: Path,
                 *, clock: Callable[[], float] = time.time, retry_config: Any = None):
        if (session.profile_name != "amit" or session.region_name != REGION
                or binding.account_alias != "amit" or binding.region != REGION
                or not binding.bucket.startswith("awsops-dev-issue90-s3-canary-")):
            raise ValueError("UNAPPROVED_LAB_BINDING")
        self.binding, self.ledger, self.clock = binding, Path(ledger), clock
        # A single SDK attempt per mutation; an uncertain acknowledgment is
        # reconciled by reads, never silently retried by botocore.
        if retry_config is None:
            from botocore.config import Config
            retry_config = Config(retries={"total_max_attempts": 1})
        self.sts = session.client("sts", region_name=REGION)
        self.s3 = session.client("s3", region_name=REGION,
                                 config=retry_config)

    def _identity(self) -> None:
        value = self.sts.get_caller_identity()
        account, arn = value.get("Account"), str(value.get("Arn", ""))
        if (account != self.binding.account_id or ":root" in arn
                or not (arn.startswith(f"arn:aws:iam::{account}:user/")
                        or arn.startswith(f"arn:aws:sts::{account}:assumed-role/"))):
            raise ValueError("PRIVATE_NONROOT_IDENTITY_MISMATCH")

    def _row(self) -> tuple[str | None, str | None]:
        """Creation acknowledgment and frozen tags must come from this private ledger."""
        if not self.ledger.is_file():
            raise ValueError("PRIVATE_JOURNAL_MISSING")
        with closing(sqlite3.connect(self.ledger.as_uri() + "?mode=ro", uri=True)) as db:
            rows = db.execute("SELECT c.payload,o.state FROM canaries c JOIN operations o "
                              "ON c.batch_id=o.batch_id WHERE c.binding=? AND o.step='create'",
                              (canonical_digest([self.binding.account_id, self.binding.bucket,
                                                 REGION, self.mode]),)).fetchall()
        if len(rows) > 1:
            raise ValueError("AMBIGUOUS_CREATION_JOURNAL")
        return rows[0] if rows else (None, None)

    def _operation(self, step: str, state: str = "INTENT") -> bool:
        return self._operations().get(step) == state

    def _operations(self) -> dict[str, str]:
        with closing(sqlite3.connect(self.ledger.as_uri() + "?mode=ro", uri=True)) as db:
            rows = db.execute("SELECT o.step,o.state FROM canaries c JOIN operations o "
                              "ON c.batch_id=o.batch_id WHERE c.binding=?",
                              (canonical_digest([self.binding.account_id, self.binding.bucket,
                                                 REGION, self.mode]),)).fetchall()
        if len({step for step, _state in rows}) != len(rows):
            raise ValueError("AMBIGUOUS_OPERATION_JOURNAL")
        return dict(rows)

    def _head(self) -> bool:
        try:
            response = self.s3.head_bucket(Bucket=self.binding.bucket,
                                           ExpectedBucketOwner=self.binding.account_id)
        except Exception as exc:
            if _error_code(exc) in ("404", "NoSuchBucket", "NotFound"):
                return False
            raise
        headers = response.get("ResponseMetadata", {}).get("HTTPHeaders", {})
        if headers.get("x-amz-bucket-region") != REGION:
            raise ValueError("CANARY_REGION_UNVERIFIED")
        return True

    def inspect(self, binding: CanaryBinding) -> Observation:
        if binding != self.binding:
            raise ValueError("CANARY_BINDING_MISMATCH")
        self._identity()
        exists = self._head()
        if not exists:
            return Observation(binding.account_id, REGION, binding.bucket, False, True,
                               int(self.clock()), None, exists=False, public_blocked=False)
        expected_owner = {"Bucket": binding.bucket, "ExpectedBucketOwner": binding.account_id}
        payload, creation = self._row()
        try:
            tags_response = self.s3.get_bucket_tagging(**expected_owner)
            tags = {item["Key"]: item["Value"] for item in tags_response["TagSet"]}
        except Exception as exc:
            if _error_code(exc) != "NoSuchTagSet":
                raise
            tags = {}
        try:
            block = self.s3.get_public_access_block(**expected_owner)["PublicAccessBlockConfiguration"]
        except Exception as exc:
            if _error_code(exc) != "NoSuchPublicAccessBlockConfiguration":
                raise
            block = {}
        try:
            raw = self.s3.get_bucket_policy(**expected_owner)["Policy"]
            if not isinstance(raw, str) or len(raw.encode()) > 131072:
                raise ValueError("CANARY_POLICY_INVALID")
            policy = json.loads(raw, object_pairs_hook=_object, parse_constant=_reject_constant)
            if not isinstance(policy, dict):
                raise ValueError("CANARY_POLICY_INVALID")
        except Exception as exc:
            if _error_code(exc) != "NoSuchBucketPolicy":
                raise
            policy = None
        objects = self.s3.list_objects_v2(**expected_owner, MaxKeys=1)
        versions = self.s3.list_object_versions(**expected_owner, MaxKeys=1)
        empty = (not objects.get("Contents") and not objects.get("IsTruncated")
                 and not versions.get("Versions") and not versions.get("DeleteMarkers")
                 and not versions.get("IsTruncated"))
        expected_tags = frozen_tags(binding, json.loads(payload)["frozenAt"]) if payload else None
        owned = creation == "ACK" and tags == expected_tags
        blocked = block == {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
        return Observation(binding.account_id, REGION, binding.bucket, owned, bool(empty),
                           int(self.clock()), policy, exists=True, public_blocked=blocked,
                           tags_absent=not tags, public_block_absent=not block)

    def inspect_cleanup(self, binding: CanaryBinding, *, deleting: bool = False) -> Observation:
        if binding != self.binding:
            raise ValueError("CANARY_BINDING_MISMATCH")
        ops = self._operations()
        if ops.get("create") != "ACK":
            raise ValueError("CLEANUP_CREATION_NOT_ACKNOWLEDGED")
        if ("delete" in ops) != deleting or (deleting and ops.get("delete") != "INTENT"):
            raise ValueError("CLEANUP_DELETE_STATE_MISMATCH")
        stopped = False
        for step in ("tags", "public_block", "policy"):
            state = ops.get(step)
            if state == "ACK":
                if stopped:
                    raise ValueError("CLEANUP_SETUP_SEQUENCE_DRIFT")
            elif state in (None, "INTENT", "REFUSED"):
                stopped = True
            else:
                raise ValueError("CLEANUP_SETUP_UNCERTAIN")

        try:
            observed = self.inspect(binding)
        except Exception:
            raise ValueError("CLEANUP_READBACK_UNAVAILABLE") from None
        if not observed.exists or not observed.empty:
            raise ValueError("CLEANUP_NOT_EMPTY_TASK_BUCKET")
        if ops.get("tags") == "ACK":
            if not observed.disposable:
                raise ValueError("CLEANUP_TAG_OWNERSHIP_MISMATCH")
        elif not observed.tags_absent:
            raise ValueError("CLEANUP_UNEXPECTED_TAGS")
        if ops.get("public_block") == "ACK":
            if not observed.public_blocked:
                raise ValueError("CLEANUP_PUBLIC_BLOCK_MISMATCH")
        elif not (observed.public_block_absent or observed.public_blocked):
            raise ValueError("CLEANUP_UNEXPECTED_PUBLIC_BLOCK")
        if ops.get("policy") == "ACK":
            if observed.policy != fixed_policy(binding.bucket):
                raise ValueError("CLEANUP_POLICY_MISMATCH")
        elif observed.policy is not None:
            raise ValueError("CLEANUP_UNEXPECTED_POLICY")
        return observed

    def create_bucket(self, binding: CanaryBinding, before_call: Callable[[], None]) -> None:
        if binding != self.binding or not self._operation("create"):
            raise ValueError("CREATION_NOT_JOURNALED")
        self._identity()
        if self._head():
            raise ValueError("BUCKET_ALREADY_EXISTS")
        before_call()
        self.s3.create_bucket(Bucket=binding.bucket,
                              CreateBucketConfiguration={"LocationConstraint": REGION})

    def tag_bucket(self, binding: CanaryBinding, frozen_at: str,
                   before_call: Callable[[], None]) -> None:
        if binding != self.binding or not self._operation("create", "ACK") or not self._operation("tags"):
            raise ValueError("TAGGING_NOT_JOURNALED")
        observed = self.inspect(binding)
        if not observed.exists or not observed.empty or observed.policy is not None:
            raise ValueError("CANARY_STATE_DRIFT")
        tags = frozen_tags(binding, frozen_at)
        tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
        before_call()
        self.s3.put_bucket_tagging(Bucket=binding.bucket, ExpectedBucketOwner=binding.account_id,
                                   Tagging={"TagSet": tag_set})

    def block_public_access(self, binding: CanaryBinding, before_call: Callable[[], None]) -> None:
        if binding != self.binding or not self._operation("tags", "ACK") or not self._operation("public_block"):
            raise ValueError("PUBLIC_BLOCK_NOT_JOURNALED")
        observed = self.inspect(binding)
        if not observed.disposable or not observed.empty or observed.policy is not None:
            raise ValueError("CANARY_STATE_DRIFT")
        before_call()
        self.s3.put_public_access_block(Bucket=binding.bucket, ExpectedBucketOwner=binding.account_id,
            PublicAccessBlockConfiguration={"BlockPublicAcls": True, "IgnorePublicAcls": True,
                                            "BlockPublicPolicy": True, "RestrictPublicBuckets": True})

    def put_policy(self, binding: CanaryBinding, policy: dict,
                   before_call: Callable[[], None]) -> None:
        if (binding != self.binding or canonical_digest(policy) != canonical_digest(fixed_policy(binding.bucket))
                or not self._operation("public_block", "ACK") or not self._operation("policy")):
            raise ValueError("POLICY_NOT_JOURNALED_OR_FIXED")
        observed = self.inspect(binding)
        if not observed.disposable or not observed.empty or not observed.public_blocked or observed.policy is not None:
            raise ValueError("CANARY_STATE_DRIFT")
        body = json.dumps(policy, sort_keys=True, separators=(",", ":"))
        before_call()
        self.s3.put_bucket_policy(Bucket=binding.bucket, ExpectedBucketOwner=binding.account_id,
                                  Policy=body)

    def delete_bucket(self, binding: CanaryBinding, before_call: Callable[[], None]) -> None:
        if binding != self.binding or not self._operation("create", "ACK") or not self._operation("delete"):
            raise ValueError("DELETE_NOT_JOURNALED")
        self.inspect_cleanup(binding, deleting=True)
        before_call()
        self.s3.delete_bucket(Bucket=binding.bucket, ExpectedBucketOwner=binding.account_id)
