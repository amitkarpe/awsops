"""Optional boto3 adapter for the fixed M2 read path.

This module exposes no generic AWS operation. It can only assume the configured
read role and perform STS identity, S3 ListBuckets, and S3 GetBucketPolicy.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from .s3_ssl import AccountBinding, REGION

DEFAULT_READ_ROLE = "ChatGPTCrossAccountReadRole"


class Boto3S3ReadClient:
    def __init__(self, session: Any):
        self._sts = session.client("sts", region_name=REGION)
        self._s3 = session.client("s3", region_name=REGION)

    def caller_account(self) -> str:
        return str(self._sts.get_caller_identity()["Account"])

    def list_bucket_names(self) -> list[str]:
        response = self._s3.list_buckets()
        return sorted(
            str(item["Name"])
            for item in response.get("Buckets", [])
            if isinstance(item, Mapping) and isinstance(item.get("Name"), str)
        )

    def bucket_policy(self, bucket: str) -> Mapping[str, Any]:
        return json.loads(self._s3.get_bucket_policy(Bucket=bucket)["Policy"])


def assume_role_factory(source_session: Any, *, role_name: str = DEFAULT_READ_ROLE):
    if role_name != DEFAULT_READ_ROLE:
        raise ValueError("M2 uses one fixed read role")

    def factory(binding: AccountBinding) -> Boto3S3ReadClient:
        creds = source_session.client("sts", region_name=REGION).assume_role(
            RoleArn=f"arn:aws:iam::{binding.account_id}:role/{role_name}",
            RoleSessionName="awsops-s3-ssl-read",
        )["Credentials"]
        boto3 = __import__("boto3")
        session = boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=REGION,
        )
        return Boto3S3ReadClient(session)

    return factory
