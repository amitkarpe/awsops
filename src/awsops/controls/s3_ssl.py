"""Conservative bucket-policy recognizer, not a general IAM/Config evaluator."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CONTROL_KEY = "s3_ssl"
RESOURCE_TYPE = "AWS::S3::Bucket"


def _strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and value and all(isinstance(x, str) for x in value):
        return set(value)
    return set()


def evaluate_policy(policy: Mapping[str, Any] | None, bucket_name: str) -> str:
    """Prove universal HTTP denial for both this bucket and all its objects.

    Only conventional Deny/Principal=*/Action=s3:* policies are recognized.
    Extra conditions, negated elements and unfamiliar shapes are UNKNOWN unless
    another complete, unconditional-with-respect-to-HTTP deny already proves
    the requirement. UNKNOWN is not eligible for prepare.
    """
    if policy is None:
        return "NON_COMPLIANT"
    if not isinstance(policy, Mapping):
        return "UNKNOWN"
    statements = policy.get("Statement")
    if isinstance(statements, Mapping):
        statements = [statements]
    if not isinstance(statements, list):
        return "UNKNOWN"
    if not statements:
        return "NON_COMPLIANT"
    bucket = "arn:aws:s3:::" + bucket_name
    required = {bucket, bucket + "/*"}
    covered: set[str] = set()
    for statement in statements:
        if not isinstance(statement, Mapping):
            continue
        if set(statement) - {"Sid", "Effect", "Principal", "Action", "Resource", "Condition"}:
            continue
        if statement.get("Effect") != "Deny":
            continue
        principal = statement.get("Principal")
        if principal != "*" and principal != {"AWS": "*"}:
            continue
        if not (_strings(statement.get("Action")) & {"*", "s3:*"}):
            continue
        condition = statement.get("Condition")
        if not isinstance(condition, Mapping) or set(condition) != {"Bool"}:
            continue
        values = condition["Bool"]
        if not isinstance(values, Mapping) or set(values) != {"aws:SecureTransport"}:
            continue
        value = values["aws:SecureTransport"]
        if value is not False and value != "false":
            continue
        resources = _strings(statement.get("Resource"))
        covered.update(required if "*" in resources else required & resources)
    return "COMPLIANT" if covered == required else "UNKNOWN"


def requires_secure_transport(policy: Mapping[str, Any], bucket_name: str) -> bool:
    """Compatibility predicate: false means unproven, not necessarily unsafe."""
    return evaluate_policy(policy, bucket_name) == "COMPLIANT"
