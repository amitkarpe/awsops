"""Optional SDK boundary: verified fixed-role reads, never arbitrary AWS calls."""
from __future__ import annotations

import json
from typing import Any, Callable

from .s3_ssl import AccountBinding, PAGE_SIZE, REGION

DEFAULT_READ_ROLE = "ChatGPTCrossAccountReadRole"


def _object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate provider JSON key")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> None:
    raise ValueError("non-JSON provider number")


class Boto3S3ReadClient:
    def __init__(self, session: Any, binding: AccountBinding):
        self.region = session.region_name
        if self.region != binding.region:
            raise ValueError("target session Region mismatch")
        self._binding = binding
        self._verified = False
        self._sts = session.client("sts", region_name=REGION)
        self._s3 = session.client("s3", region_name=REGION)

    def caller_account(self) -> str:
        identity = self._sts.get_caller_identity()
        account = identity.get("Account", "")
        prefix = f"arn:aws:sts::{self._binding.account_id}:assumed-role/{DEFAULT_READ_ROLE}/"
        self._verified = account == self._binding.account_id and str(identity.get("Arn", "")).startswith(prefix)
        if not self._verified:
            raise ValueError("target account or read-role identity mismatch")
        return account

    def _guard(self) -> None:
        if not self._verified:
            raise ValueError("target identity must be verified before provider reads")

    def list_bucket_page(self, token: str | None) -> dict:
        self._guard()
        params = {"BucketRegion": REGION, "MaxBuckets": PAGE_SIZE}
        if token is not None:
            params["ContinuationToken"] = token
        # Unsupported older SDKs fail closed; never fall back to unbounded reads.
        return self._s3.list_buckets(**params)

    def bucket_policy(self, bucket: str) -> dict | None:
        self._guard()
        try:
            response = self._s3.get_bucket_policy(Bucket=bucket, ExpectedBucketOwner=self._binding.account_id)
        except Exception as exc:
            error = getattr(exc, "response", {})
            if isinstance(error, dict) and error.get("Error", {}).get("Code") == "NoSuchBucketPolicy":
                return None
            raise
        raw = response.get("Policy")
        if not isinstance(raw, str) or len(raw.encode("utf-8")) > 131072:
            raise ValueError("invalid provider policy response")
        policy = json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_constant)
        if not isinstance(policy, dict):
            raise ValueError("provider policy must be an object")
        return policy


def assume_role_factory(source_session: Any, *, expected_source_account: str,
                        session_factory: Callable[..., Any] | None = None):
    """Operator-only wiring. Existing role credentials stay inside this process."""
    if source_session.region_name != REGION:
        raise ValueError("controller Region mismatch")
    if not isinstance(expected_source_account, str) or not expected_source_account.isascii() or not expected_source_account.isdigit() or len(expected_source_account) != 12:
        raise ValueError("invalid expected controller account")
    sts = source_session.client("sts", region_name=REGION)
    if sts.get_caller_identity().get("Account") != expected_source_account:
        raise ValueError("controller account mismatch")
    if session_factory is None:
        import boto3
        session_factory = boto3.Session

    def factory(binding: AccountBinding) -> Boto3S3ReadClient:
        credentials = sts.assume_role(
            RoleArn=f"arn:aws:iam::{binding.account_id}:role/{DEFAULT_READ_ROLE}",
            RoleSessionName="awsops-s3-ssl-read",
            DurationSeconds=900,
        )["Credentials"]
        session = session_factory(aws_access_key_id=credentials["AccessKeyId"],
                                  aws_secret_access_key=credentials["SecretAccessKey"],
                                  aws_session_token=credentials["SessionToken"], region_name=REGION)
        return Boto3S3ReadClient(session, binding)
    return factory
