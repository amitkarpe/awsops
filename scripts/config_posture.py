#!/usr/bin/env python3
"""Fixed account-local Config reader. Disabled in the workflow until owner approval.

Tests inject a caller; imports and --help never call AWS. No raw data is logged.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

REGION = "ap-southeast-1"
ROLE = "awsops-github-readonly"
OPERATIONS = {
    "get-caller-identity": ("sts", None),
    "describe-configuration-recorders": ("config", "ConfigurationRecorders"),
    "describe-configuration-recorder-status": ("config", "ConfigurationRecordersStatus"),
    "describe-config-rules": ("config", "ConfigRules"),
    "describe-compliance-by-config-rule": ("config", "ComplianceByConfigRules"),
}


class Rejected(Exception):
    """Only fixed codes may cross the public boundary."""


def require(condition, code="UNKNOWN"):
    if not condition:
        raise Rejected(code)


def blank():
    return dict(OIDC_IDENTITY="NOT_ACQUIRED", REGION="NOT_ACQUIRED",
                CONFIG_ACQUISITION="BLOCKED", REASON="NOT_ACQUIRED",
                RECORDER_PRESENT="UNKNOWN", RECORDING="UNKNOWN", RECORDER_SCOPE="UNKNOWN",
                RULE_INVENTORY_COMPLETE="NO", TOTAL_RULES=None, COMPLIANT_RULES=None,
                NONCOMPLIANT_RULES=None, INSUFFICIENT_DATA_RULES=None, NOT_APPLICABLE_RULES=None,
                EVALUATION_FRESHNESS="NOT_VERIFIED", STATIC_KEYS="NONE")


def rows(response, key):
    allowed = {key, "NextToken"} if key in {"ConfigRules", "ComplianceByConfigRules"} else {key}
    require(isinstance(response, dict) and set(response) <= allowed and isinstance(response.get(key), list))
    require(all(isinstance(row, dict) for row in response[key]))
    return response[key]


def named(items, field):
    result = {}
    for row in items:
        name = row.get(field)
        require(isinstance(name, str) and 0 < len(name) <= 256)
        require(name not in result, "INCONSISTENT")
        result[name] = row
    return result


def pages(call, operation, key):
    result, seen, token = [], set(), None
    for _ in range(5):
        response = call(operation, token)
        result.extend(rows(response, key))
        require(len(result) <= 500, "INCOMPLETE_PAGINATION")
        token = response.get("NextToken")
        if token is None or token == "":
            return result
        require(isinstance(token, str) and 0 < len(token) <= 8192)
        require(token not in seen, "INCOMPLETE_PAGINATION")
        seen.add(token)
    raise Rejected("INCOMPLETE_PAGINATION")


def acquire(call, expected_account, region):
    """Independent expected identity is owner-private, never taken from responses."""
    summary = blank()
    try:
        require(region == REGION, "REGION_MISMATCH")
        require(isinstance(expected_account, str) and re.fullmatch(r"\d{12}", expected_account), "IDENTITY_MISMATCH")
        identity = call("get-caller-identity", None)
        require(isinstance(identity, dict) and identity.get("Account") == expected_account and
                identity.get("Arn") == f"arn:aws:sts::{expected_account}:assumed-role/{ROLE}/awsops-readonly",
                "IDENTITY_MISMATCH")
        summary.update(OIDC_IDENTITY="PASS", REGION="PASS")
        recorders = rows(call("describe-configuration-recorders", None), "ConfigurationRecorders")
        statuses = rows(call("describe-configuration-recorder-status", None), "ConfigurationRecordersStatus")
        require(len(recorders) <= 1 and len(statuses) <= 1, "INCONSISTENT")
        recorder_map, status_map = named(recorders, "name"), named(statuses, "name")
        require(recorder_map.keys() == status_map.keys(), "INCONSISTENT")
        recorder_known = True
        if not recorders:
            summary.update(RECORDER_PRESENT="NO", RECORDING="NO", RECORDER_SCOPE="NOT_APPLICABLE")
        else:
            recorder, status = recorders[0], statuses[0]
            require(type(status.get("recording")) is bool)
            group = recorder.get("recordingGroup")
            require(isinstance(group, dict))
            strategy = group.get("recordingStrategy", {}).get("useOnly")
            if strategy in ("ALL_SUPPORTED_RESOURCE_TYPES", "INCLUSION_BY_RESOURCE_TYPES", "EXCLUSION_BY_RESOURCE_TYPES"):
                scope = strategy
            elif strategy is None and group.get("allSupported") is True:
                scope = "ALL_SUPPORTED_RESOURCE_TYPES"
            elif strategy is None and group.get("allSupported") is False and isinstance(group.get("resourceTypes"), list) and group["resourceTypes"]:
                scope = "INCLUSION_BY_RESOURCE_TYPES"
            else:
                scope = "UNKNOWN"
            recorder_known = scope != "UNKNOWN" and status.get("lastStatus") == "Success"
            summary.update(RECORDER_PRESENT="YES", RECORDING="YES" if status["recording"] else "NO", RECORDER_SCOPE=scope)
        rules = named(pages(call, "describe-config-rules", "ConfigRules"), "ConfigRuleName")
        compliance = named(pages(call, "describe-compliance-by-config-rule", "ComplianceByConfigRules"), "ConfigRuleName")
        require(rules.keys() == compliance.keys(), "INCONSISTENT")
        require(all(row.get("ConfigRuleState") == "ACTIVE" for row in rules.values()), "INCONSISTENT")
        counts = {state: 0 for state in ("COMPLIANT", "NON_COMPLIANT", "INSUFFICIENT_DATA", "NOT_APPLICABLE")}
        for row in compliance.values():
            value = row.get("Compliance")
            require(isinstance(value, dict) and isinstance(value.get("ComplianceType"), str) and value["ComplianceType"] in counts)
            counts[value["ComplianceType"]] += 1
        summary.update(RULE_INVENTORY_COMPLETE="YES", TOTAL_RULES=len(rules),
                       COMPLIANT_RULES=counts["COMPLIANT"], NONCOMPLIANT_RULES=counts["NON_COMPLIANT"],
                       INSUFFICIENT_DATA_RULES=counts["INSUFFICIENT_DATA"], NOT_APPLICABLE_RULES=counts["NOT_APPLICABLE"],
                       CONFIG_ACQUISITION="PASS" if recorder_known else "PARTIAL",
                       REASON="COMPLETE" if recorder_known else "UNKNOWN")
    except Rejected as error:
        code = str(error)
        if code not in {"REGION_MISMATCH", "IDENTITY_MISMATCH", "ACCESS_DENIED", "INCOMPLETE_PAGINATION", "INCONSISTENT", "UNKNOWN"}:
            code = "UNKNOWN"
        summary.update(CONFIG_ACQUISITION="PARTIAL" if code in {"INCOMPLETE_PAGINATION", "INCONSISTENT"} else "BLOCKED", REASON=code)
        if code == "IDENTITY_MISMATCH":
            summary["OIDC_IDENTITY"] = "FAIL"
        if code == "REGION_MISMATCH":
            summary["REGION"] = "FAIL"
    except Exception:
        summary.update(CONFIG_ACQUISITION="BLOCKED", REASON="UNKNOWN")
    return summary


class AwsCaller:
    def __init__(self):
        self.deadline = time.monotonic() + 120
        self.config_calls = 0
        # Only the three temporary credentials exported by the proven OIDC action.
        require(all(os.environ.get(k) for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")))
        require(not any(k.startswith("AWS_ENDPOINT_URL") for k in os.environ))
        self.env = {k: os.environ[k] for k in ("PATH", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN") if k in os.environ}
        self.env.update(AWS_REGION=REGION, AWS_DEFAULT_REGION=REGION, AWS_MAX_ATTEMPTS="1",
                        AWS_RETRY_MODE="standard", AWS_PAGER="", AWS_EC2_METADATA_DISABLED="true",
                        AWS_CONFIG_FILE="/dev/null", AWS_SHARED_CREDENTIALS_FILE="/dev/null",
                        AWS_IGNORE_CONFIGURED_ENDPOINT_URLS="true")

    def __call__(self, operation, token):
        require(operation in OPERATIONS)
        service, _ = OPERATIONS[operation]
        require(token is None or operation in {"describe-config-rules", "describe-compliance-by-config-rule"})
        if service == "config":
            self.config_calls += 1
            require(self.config_calls <= 12, "INCOMPLETE_PAGINATION")
        remaining = self.deadline - time.monotonic()
        require(remaining > 0)
        argv = ["aws", service, operation, "--region", REGION, "--output", "json", "--no-paginate",
                "--cli-connect-timeout", "5", "--cli-read-timeout", "10"]
        if token is not None:
            argv += ["--next-token", token]
        try:
            result = subprocess.run(argv, env=self.env, capture_output=True, timeout=min(15, remaining), check=False)
            if result.returncode:
                denied = b"AccessDenied" in result.stderr or b"UnauthorizedOperation" in result.stderr
                raise Rejected("ACCESS_DENIED" if denied else "UNKNOWN")
            require(len(result.stdout) <= 4 * 1024 * 1024)
            return json.loads(result.stdout)
        except Rejected:
            raise
        except Exception:
            raise Rejected("UNKNOWN") from None


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    summary = blank()
    # Committed workflow sets false. No input/variable/secret may enable this gate.
    if os.environ.get("CONFIG_ACQUISITION_ENABLED") == "true":
        try:
            require(os.environ.get("GITHUB_ACTIONS") == "true" and
                    os.environ.get("GITHUB_REPOSITORY") == "amitkarpe/awsops" and
                    os.environ.get("GITHUB_REF") == "refs/heads/main" and
                    os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch")
            summary = acquire(AwsCaller(), os.environ.get("EXPECTED_ACCOUNT_ID"), os.environ.get("AWS_REGION"))
        except Exception:
            summary.update(REASON="UNKNOWN")
    # Bind public evidence to GitHub source/run without echoing arbitrary env values.
    for key, env_key, pattern in (("SOURCE_SHA", "GITHUB_SHA", r"[0-9a-f]{40}"),
                                  ("RUN_ID", "GITHUB_RUN_ID", r"[0-9]{1,20}")):
        value = os.environ.get(env_key, "")
        summary[key] = value if re.fullmatch(pattern, value) else "NOT_VERIFIED"
    output = "\n".join(f"{key}={json.dumps(value) if value is None or type(value) is int else value}" for key, value in summary.items()) + "\n"
    print(output, end="")
    if destination := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(destination).open("a", encoding="utf-8") as stream:
            stream.write(output)
    return 0 if summary["CONFIG_ACQUISITION"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
