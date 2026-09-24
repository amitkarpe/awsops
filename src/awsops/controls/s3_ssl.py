"""S3 TLS control semantics without AWS client/runtime coupling."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CONTROL_KEY = "s3_ssl"
RESOURCE_TYPE = "AWS::S3::Bucket"


def requires_secure_transport(policy: Mapping[str, Any]) -> bool:
    statements = policy.get("Statement", [])
    if isinstance(statements, Mapping):
        statements = [statements]
    if not isinstance(statements, list):
        return False
    for statement in statements:
        if not isinstance(statement, Mapping) or statement.get("Effect") != "Deny":
            continue
        condition = statement.get("Condition", {})
        bool_values = condition.get("Bool", {}) if isinstance(condition, Mapping) else {}
        if isinstance(bool_values, Mapping):
            value = str(bool_values.get("aws:SecureTransport", "")).lower()
            if value == "false":
                return True
    return False
