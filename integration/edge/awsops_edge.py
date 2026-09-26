"""Render an additive NEW-only Nginx include and bounded Route 53 plan.

This module is deliberately offline: it reads operator-supplied JSON and writes
plans to stdout. It never calls AWS, writes host configuration, or controls a
service.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


OPS_HOST = "ops2.astromedicomp.org."
SEC_HOST = "sec2.astromedicomp.org."
OLD_HOSTS = {"ops.astromedicomp.org.", "sec.astromedicomp.org."}
NEW_HOSTS = {OPS_HOST, SEC_HOST}
DNS_TTL_SECONDS = 60
TLS_IDENTITY = "awsops-ops2-sec2"


class EdgeConfigError(ValueError):
    """Raised when inputs are missing, conflicting, or outside the fixed scope."""


def _dns_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise EdgeConfigError(f"invalid {field}")
    name = value.rstrip(".").lower()
    labels = name.split(".")
    if len(labels) < 2 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in labels
    ):
        raise EdgeConfigError(f"invalid {field}")
    return name + "."


def _port(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1024 <= value <= 65535:
        raise EdgeConfigError(f"invalid {field}")
    return value


def _unit(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.@:-]+\.service", value):
        raise EdgeConfigError(f"invalid {field}")
    if "aws-secops" in value.lower():
        raise EdgeConfigError(f"{field} must identify a NEW awsops service")
    return value


def _absolute_path(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or not re.fullmatch(r"/[A-Za-z0-9_./-]+", value):
        raise EdgeConfigError(f"invalid {field}")
    path = PurePosixPath(value)
    if ".." in path.parts or "aws-secops" in value.lower():
        raise EdgeConfigError(f"{field} must be a NEW absolute path")
    return str(path)


def _paths_disjoint(values: list[tuple[str, str]]) -> None:
    paths = [(name, PurePosixPath(value)) for name, value in values]
    for index, (left_name, left) in enumerate(paths):
        for right_name, right in paths[index + 1 :]:
            if left == right or left in right.parents or right in left.parents:
                raise EdgeConfigError(f"{left_name} and {right_name} must be separate")


def validate_config(config: Any) -> dict[str, Any]:
    """Validate a closed schema; hostname scope is fixed to ops2/sec2."""
    if not isinstance(config, dict) or set(config) != {"dns_target_fqdn", "ops", "sec", "tls"}:
        raise EdgeConfigError("config must contain only dns_target_fqdn, ops, sec, and tls")

    target = _dns_name(config["dns_target_fqdn"], "dns_target_fqdn")
    if target in OLD_HOSTS or target in NEW_HOSTS:
        raise EdgeConfigError("DNS target must be a separate retained-host A-record name")

    services: dict[str, dict[str, Any] | None] = {"ops": None, "sec": None}
    roots: list[tuple[str, str]] = []
    configured_ports: list[int] = []
    configured_units: list[str] = []
    for name in ("ops", "sec"):
        raw = config[name]
        if raw is None and name == "ops":
            continue
        if not isinstance(raw, dict) or set(raw) != {"service_unit", "runtime_root", "state_root", "loopback_port"}:
            raise EdgeConfigError(f"{name} config has missing or unexpected fields")
        service = _unit(raw["service_unit"], f"{name}.service_unit")
        runtime_root = _absolute_path(raw["runtime_root"], f"{name}.runtime_root")
        state_root = _absolute_path(raw["state_root"], f"{name}.state_root")
        port = _port(raw["loopback_port"], f"{name}.loopback_port")
        services[name] = {
            "service_unit": service,
            "runtime_root": runtime_root,
            "state_root": state_root,
            "loopback_port": port,
        }
        roots.extend(((f"{name}.runtime_root", runtime_root), (f"{name}.state_root", state_root)))
        configured_ports.append(port)
        configured_units.append(service)

    if services["sec"] is None:
        raise EdgeConfigError("sec config must identify a verified NEW LibreChat service")
    if len(configured_units) != len(set(configured_units)):
        raise EdgeConfigError("NEW service units must be distinct")
    if len(configured_ports) != len(set(configured_ports)):
        raise EdgeConfigError("NEW loopback ports must be distinct")
    _paths_disjoint(roots)

    tls = config["tls"]
    if not isinstance(tls, dict) or set(tls) != {"identity", "certificate_file", "private_key_file"}:
        raise EdgeConfigError("tls config has missing or unexpected fields")
    if tls["identity"] != TLS_IDENTITY:
        raise EdgeConfigError("TLS identity must be the dedicated NEW identity")
    certificate = _absolute_path(tls["certificate_file"], "tls.certificate_file")
    private_key = _absolute_path(tls["private_key_file"], "tls.private_key_file")
    if certificate == private_key:
        raise EdgeConfigError("TLS certificate and key paths must differ")
    certificate_dir = PurePosixPath(certificate).parent
    if certificate_dir != PurePosixPath(private_key).parent or certificate_dir.name != TLS_IDENTITY:
        raise EdgeConfigError("TLS files must use the dedicated NEW certificate directory")
    _paths_disjoint(roots + [("tls.certificate_directory", str(certificate_dir))])

    return {
        "dns_target_fqdn": target,
        "ops": services["ops"],
        "sec": services["sec"],
        "tls": {
            "identity": TLS_IDENTITY,
            "certificate_file": certificate,
            "private_key_file": private_key,
        },
    }


def _configured_hosts(config: dict[str, Any]) -> list[tuple[str, str]]:
    hosts = []
    if config["ops"] is not None:
        hosts.append(("ops", OPS_HOST))
    hosts.append(("sec", SEC_HOST))
    return hosts


def _record_name(record: Any) -> str | None:
    if not isinstance(record, dict) or not isinstance(record.get("Name"), str):
        return None
    try:
        return _dns_name(record["Name"], "record name")
    except EdgeConfigError:
        return None


def plan_dns(config: Any, record_sets_document: Any) -> dict[str, Any]:
    """Return a Route 53 ChangeBatch containing only safe CREATEs for ops2/sec2."""
    values = validate_config(config)
    if not isinstance(record_sets_document, dict) or not isinstance(record_sets_document.get("ResourceRecordSets"), list):
        raise EdgeConfigError("record-set input must contain ResourceRecordSets")
    records = record_sets_document["ResourceRecordSets"]
    target = values["dns_target_fqdn"]
    target_records = [
        item for item in records
        if _record_name(item) == target and isinstance(item, dict) and item.get("Type") == "A"
    ]
    if len(target_records) != 1:
        raise EdgeConfigError("retained-host target must have exactly one existing A record set")

    changes = []
    configured = {hostname for _, hostname in _configured_hosts(values)}
    for hostname in (OPS_HOST, SEC_HOST):
        existing = [item for item in records if _record_name(item) == hostname]
        if hostname not in configured:
            if existing:
                raise EdgeConfigError(f"DNS record exists without a configured NEW service for {hostname.rstrip('.')}")
            continue
        if not existing:
            changes.append({
                "Action": "CREATE",
                "ResourceRecordSet": {
                    "Name": hostname,
                    "Type": "CNAME",
                    "TTL": DNS_TTL_SECONDS,
                    "ResourceRecords": [{"Value": target}],
                },
            })
            continue

        exact = (
            len(existing) == 1
            and existing[0].get("Type") == "CNAME"
            and existing[0].get("TTL") == DNS_TTL_SECONDS
            and existing[0].get("ResourceRecords") == [{"Value": target}]
        )
        if not exact:
            raise EdgeConfigError(f"conflicting DNS record for {hostname.rstrip('.')}")

    if len(changes) > 2 or any(
        item["ResourceRecordSet"]["Name"] not in NEW_HOSTS for item in changes
    ):
        raise EdgeConfigError("DNS plan exceeded the fixed NEW hostname scope")
    return {
        "Comment": "awsops NEW-only aliases; OLD and target records are never changed",
        "Changes": changes,
    }


def render_nginx(config: Any) -> str:
    """Render only NEW host blocks; callers must install as an additive include."""
    values = validate_config(config)
    tls = values["tls"]
    output = [
        "# Generated by awsops_edge.py; additive NEW-only include; never replace the OLD site.",
        f"# Dedicated certificate identity: {tls['identity']}",
        "server {",
        "    listen 80;",
        f"    server_name {OPS_HOST.rstrip('.')} {SEC_HOST.rstrip('.')};",
        "    return 308 https://$host$request_uri;",
        "}",
    ]
    host_map = _configured_hosts(values)
    output[4] = f"    server_name {' '.join(host.rstrip('.') for _, host in host_map)};"
    for name, hostname in host_map:
        service = values[name]
        output.extend([
            "",
            "server {",
            "    listen 443 ssl;",
            f"    server_name {hostname.rstrip('.')};",
            f"    ssl_certificate {tls['certificate_file']};",
            f"    ssl_certificate_key {tls['private_key_file']};",
            "",
            "    location / {",
            f"        proxy_pass http://127.0.0.1:{service['loopback_port']};",
            "        proxy_http_version 1.1;",
            "        proxy_set_header Upgrade $http_upgrade;",
            '        proxy_set_header Connection "upgrade";',
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_set_header X-Forwarded-Proto $scheme;",
            "    }",
            "}",
        ])
    return "\n".join(output) + "\n"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EdgeConfigError("unable to read valid JSON input") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline awsops NEW edge planner; no apply or service commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    dns_parser = subparsers.add_parser("plan-dns", help="plan only the two fixed NEW Route 53 aliases")
    dns_parser.add_argument("--config", type=Path, required=True)
    dns_parser.add_argument("--record-sets", type=Path, required=True)
    nginx_parser = subparsers.add_parser("render-nginx", help="render an additive NEW-only Nginx include to stdout")
    nginx_parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        config = _read_json(args.config)
        if args.command == "plan-dns":
            plan = plan_dns(config, _read_json(args.record_sets))
            result = {"status": "READY" if plan["Changes"] else "UNCHANGED", "change_batch": plan}
            sys.stdout.write(json.dumps(result, indent=2) + "\n")
        else:
            sys.stdout.write(render_nginx(config))
    except EdgeConfigError as exc:
        sys.stderr.write(f"awsops-edge: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
