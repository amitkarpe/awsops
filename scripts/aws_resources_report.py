#!/usr/bin/env python3
"""Refresh the KISS AWS resource ledger with read-only SDK calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from awsops.resources.ledger import LedgerRow, parse_date, render_markdown, right_size_t3

REGION = "ap-southeast-1"
PROJECTS = ("aws-secops", "awsops")


def logical_class(resource: str) -> str:
    parts = resource.split(":", 5)
    service = parts[2] if len(parts) > 2 else "unknown"
    detail = parts[5] if len(parts) > 5 else ""
    if service == "lambda":
        return "Lambda function"
    if service == "logs":
        return "CloudWatch log group"
    if service == "codebuild":
        return "CodeBuild project"
    if service == "cloudformation":
        return "CloudFormation stack"
    if service == "s3":
        return "S3 bucket"
    if service == "config":
        return "AWS Config rule"
    if service == "ec2":
        if detail.startswith("security-group-rule/"):
            return "Security Group rule"
        if detail.startswith("security-group/"):
            return "Security Group"
        return "EC2 resource"
    if service == "bedrock-agentcore":
        prefix = detail.split("/", 1)[0]
        return {
            "gateway": "AgentCore Gateway",
            "policy-engine": "AgentCore Policy engine",
            "harness": "AgentCore Harness",
            "runtime": "AgentCore Runtime",
            "workload-identity-directory": "AgentCore workload identity",
        }.get(prefix, "AgentCore resource")
    return f"{service} resource"


def cost_label(resource_class: str) -> str:
    if resource_class in {"Security Group", "Security Group rule", "CloudFormation stack"}:
        return "DIRECT-$0"
    if resource_class.startswith("EC2"):
        return "EST"
    return "USAGE-BASED"


def decision(tags: dict[str, str], as_of) -> str:
    if tags.get("component") == "compliance-agent-v1":
        return "RETAIN"
    ttl = parse_date(tags.get("TTL") or tags.get("ttl"))
    if ttl and ttl < as_of:
        return "CLEANUP-CANDIDATE"
    if ttl:
        return "RETAIN"
    return "REVIEW"


def tag_map(tags) -> dict[str, str]:
    return {str(item.get("Key")): str(item.get("Value")) for item in (tags or []) if item.get("Key") is not None}


def tagged_rows(session, *, alias: str, region: str, verified_at: str) -> list[LedgerRow]:
    client = session.client("resourcegroupstaggingapi", region_name=region)
    as_of = datetime.fromisoformat(verified_at).date()
    groups = {}
    for project in PROJECTS:
        paginator = client.get_paginator("get_resources")
        for page in paginator.paginate(TagFilters=[{"Key": "project", "Values": [project]}]):
            for item in page.get("ResourceTagMappingList", []):
                tags = tag_map(item.get("Tags"))
                cls = logical_class(str(item.get("ResourceARN", "")))
                purpose = tags.get("purpose") or tags.get("component") or "project-owned retained resource"
                key = (project, cls, purpose)
                value = groups.setdefault(key, {"count": 0, "created": [], "decisions": []})
                value["count"] += 1
                created = parse_date(tags.get("created"))
                if created:
                    value["created"].append(created)
                value["decisions"].append(decision(tags, as_of))
    rows = []
    for (project, cls, purpose), value in sorted(groups.items()):
        choices = value["decisions"]
        if "CLEANUP-CANDIDATE" in choices:
            keep = "CLEANUP-CANDIDATE"
        elif choices and all(x == "RETAIN" for x in choices):
            keep = "RETAIN"
        else:
            keep = "REVIEW"
        rows.append(LedgerRow(
            project, alias, cls, value["count"], "present", purpose,
            cost_label(cls), keep, "LIVE",
            created=min(value["created"]) if value["created"] else None,
        ))
    return rows


def metric(client, instance_id: str, name: str, start, end) -> dict:
    response = client.get_metric_statistics(
        Namespace="AWS/EC2", MetricName=name,
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start, EndTime=end, Period=3600, Statistics=["Average", "Maximum"],
    )
    points = response.get("Datapoints", [])
    return {
        "average": sum(float(x.get("Average", 0)) for x in points) / len(points) if points else None,
        "maximum": max((float(x.get("Maximum", 0)) for x in points), default=None),
    }


def price(session, instance_type: str) -> float | None:
    try:
        client = session.client("pricing", region_name="us-east-1")
        response = client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                {"Type": "TERM_MATCH", "Field": "location", "Value": "Asia Pacific (Singapore)"},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
            ], MaxResults=20,
        )
    except Exception:
        return None
    values = []
    for raw in response.get("PriceList", []):
        product = json.loads(raw) if isinstance(raw, str) else raw
        for term in product.get("terms", {}).get("OnDemand", {}).values():
            for dimension in term.get("priceDimensions", {}).values():
                if dimension.get("unit") == "Hrs":
                    value = dimension.get("pricePerUnit", {}).get("USD")
                    if value is not None:
                        values.append(float(value))
    return min(values) if values else None


def host_row(session, *, alias: str, region: str, host_facts: dict) -> tuple[LedgerRow | None, dict]:
    ec2 = session.client("ec2", region_name=region)
    reservations = ec2.describe_instances(Filters=[
        {"Name": "tag:owner", "Values": ["amit"]},
        {"Name": "tag:environment", "Values": ["dev"]},
        {"Name": "tag:purpose", "Values": ["librechat-agentcore-poc"]},
        {"Name": "instance-state-name", "Values": ["running", "stopped"]},
    ]).get("Reservations", [])
    instances = [item for reservation in reservations for item in reservation.get("Instances", [])]
    if len(instances) > 1:
        raise RuntimeError("retained host is ambiguous")
    if not instances:
        return None, host_facts
    instance = instances[0]
    now = datetime.now(timezone.utc)
    cpu = metric(session.client("cloudwatch", region_name=region), instance["InstanceId"], "CPUUtilization", now - timedelta(days=14), now)
    current_price = price(session, str(instance.get("InstanceType")))
    facts = dict(host_facts)
    facts.update({
        "instance_type": instance.get("InstanceType"),
        "state": instance.get("State", {}).get("Name"),
        "launch_time": instance.get("LaunchTime").isoformat() if instance.get("LaunchTime") else None,
        "cpu_14d_avg_pct": cpu.get("average"),
        "cpu_14d_max_pct": cpu.get("maximum"),
        "current_price_usd_hour": current_price,
    })
    monthly = current_price * 730 if current_price is not None else None
    created = datetime.fromisoformat(facts["launch_time"]).date() if facts.get("launch_time") else None
    row = LedgerRow(
        "shared-runtime", alias, "EC2 retained demo host", 1, str(facts.get("state") or "present"),
        "LibreChat + Ops retained personal-LAB runtime", "EST", "RETAIN", "LIVE",
        created=created, monthly_usd=monthly,
    )
    return row, facts


def load_known(path: Path) -> list[LedgerRow]:
    if not path.exists():
        return []
    rows = []
    for item in json.loads(path.read_text()):
        rows.append(LedgerRow(
            item["project"], item["account_alias"], item["resource_class"], int(item["count"]),
            item["state"], item["purpose"], item["cost_label"], item["decision"], item["source"],
            created=parse_date(item.get("created")), first_seen=parse_date(item.get("first_seen")),
            monthly_usd=item.get("monthly_usd"),
        ))
    return rows


def verify_controller(session, expected_account: str, region: str) -> None:
    if not (expected_account.isascii() and expected_account.isdigit() and len(expected_account) == 12):
        raise RuntimeError("expected account must be a private 12-digit runtime value")
    actual = str(session.client("sts", region_name=region).get_caller_identity().get("Account", ""))
    if actual != expected_account:
        raise RuntimeError("controller account mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile")
    parser.add_argument("--alias", default="amit")
    parser.add_argument("--region", default=REGION)
    parser.add_argument("--expected-account", default=os.environ.get("AWSOPS_EXPECTED_ACCOUNT"),
                        help="private expected controller account; prefer AWSOPS_EXPECTED_ACCOUNT")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/current/AWS_RESOURCES.md")
    args = parser.parse_args()
    if args.region != REGION:
        raise SystemExit("only ap-southeast-1 is supported by this ledger")
    if not args.expected_account:
        raise SystemExit("set AWSOPS_EXPECTED_ACCOUNT privately before live discovery")
    import boto3
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    verify_controller(session, args.expected_account, args.region)
    verified_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = load_known(ROOT / "docs/current/aws_resources_known.json")
    cost_snapshot = json.loads((ROOT / "docs/current/aws_cost_snapshot.json").read_text())
    rows.extend(tagged_rows(session, alias=args.alias, region=args.region, verified_at=verified_at))
    host_facts = json.loads((ROOT / "docs/current/aws_host_facts.json").read_text())
    host, host_facts = host_row(session, alias=args.alias, region=args.region, host_facts=host_facts)
    if host:
        rows.insert(0, host)
    sizing = right_size_t3(host_facts)
    text = render_markdown(
        rows,
        verified_at=verified_at,
        coverage="live amit account project tags + live vagent retained EC2 snapshot + explicit repo-evidence seeds",
        sizing=sizing,
        cost_snapshot=cost_snapshot,
    )
    args.output.write_text(text)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
