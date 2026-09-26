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
CONFIG_HOST = "config2.astromedicomp.org."
OLD_HOSTS = {"ops.astromedicomp.org.", "sec.astromedicomp.org."}
OLD_CONFIG_HOST = "config.astromedicomp.org."
NEW_HOSTS = {OPS_HOST, CONFIG_HOST, SEC_HOST}
DNS_TTL_SECONDS = 60
TLS_IDENTITY = "awsops-ops2-sec2"  # Retained two-host configuration format.
HOST_TLS_IDENTITIES = {"ops": "awsops-ops2", "config": "awsops-config2", "sec": "awsops-sec2"}


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


def _tls_config(raw: Any, identity: str) -> dict[str, str]:
    if not isinstance(raw, dict) or set(raw) != {"identity", "certificate_file", "private_key_file"}:
        raise EdgeConfigError("tls config has missing or unexpected fields")
    if raw["identity"] != identity:
        raise EdgeConfigError("TLS identity must be the dedicated NEW identity")
    certificate = _absolute_path(raw["certificate_file"], "tls.certificate_file")
    private_key = _absolute_path(raw["private_key_file"], "tls.private_key_file")
    certificate_dir = PurePosixPath(certificate).parent
    if certificate == private_key:
        raise EdgeConfigError("TLS certificate and key paths must differ")
    if certificate_dir != PurePosixPath(private_key).parent or certificate_dir.name != identity:
        raise EdgeConfigError("TLS files must use the dedicated NEW certificate directory")
    return {"identity": identity, "certificate_file": certificate, "private_key_file": private_key}


def validate_config(config: Any) -> dict[str, Any]:
    """Keep the legacy format; an explicit config slot selects the dashboard map."""
    required = {"dns_target_fqdn", "ops", "sec", "tls"}
    if not isinstance(config, dict) or set(config) not in (required, required | {"config"}):
        raise EdgeConfigError("config must contain dns_target_fqdn, ops, sec, tls, and optionally config")
    dashboard = "config" in config
    if dashboard and config["ops"] is not None:
        raise EdgeConfigError("ops must be null: ops2 is an entry redirect, not a backend")
    target = _dns_name(config["dns_target_fqdn"], "dns_target_fqdn")
    if target in OLD_HOSTS | {OLD_CONFIG_HOST} or target in NEW_HOSTS:
        raise EdgeConfigError("DNS target must be a separate retained-host A-record name")

    services: dict[str, dict[str, Any] | None] = {"ops": None, "sec": None}
    roots: list[tuple[str, str]] = []
    configured_ports: list[int] = []
    configured_units: list[str] = []
    for name in (("config", "sec") if dashboard else ("ops", "sec")):
        raw = config[name]
        if raw is None and name == "ops":
            continue
        fields = {"service_unit", "runtime_root", "state_root", "loopback_port"}
        if name == "config":
            fields.add("basic_auth_file")
        if not isinstance(raw, dict) or set(raw) != fields:
            raise EdgeConfigError(f"{name} config has missing or unexpected fields")
        service = _unit(raw["service_unit"], f"{name}.service_unit")
        runtime_root = _absolute_path(raw["runtime_root"], f"{name}.runtime_root")
        state_root = _absolute_path(raw["state_root"], f"{name}.state_root")
        port = _port(raw["loopback_port"], f"{name}.loopback_port")
        services[name] = {
            "service_unit": service, "runtime_root": runtime_root,
            "state_root": state_root, "loopback_port": port,
        }
        if name == "config":
            auth = _absolute_path(raw["basic_auth_file"], "config.basic_auth_file")
            services[name]["basic_auth_file"] = auth
            roots.append(("config.basic_auth_file", auth))
        roots.extend(((f"{name}.runtime_root", runtime_root), (f"{name}.state_root", state_root)))
        configured_ports.append(port)
        configured_units.append(service)
    if len(configured_units) != len(set(configured_units)):
        raise EdgeConfigError("NEW service units must be distinct")
    if len(configured_ports) != len(set(configured_ports)):
        raise EdgeConfigError("NEW loopback ports must be distinct")

    if dashboard:
        raw_tls = config["tls"]
        if not isinstance(raw_tls, dict) or set(raw_tls) != set(HOST_TLS_IDENTITIES):
            raise EdgeConfigError("dashboard tls must contain exactly ops, config, and sec")
        tls = {name: _tls_config(raw_tls[name], identity) for name, identity in HOST_TLS_IDENTITIES.items()}
        roots.extend((f"tls.{name}", str(PurePosixPath(value["certificate_file"]).parent)) for name, value in tls.items())
    else:
        tls = _tls_config(config["tls"], TLS_IDENTITY)
        roots.append(("tls.certificate_directory", str(PurePosixPath(tls["certificate_file"]).parent)))
    _paths_disjoint(roots)
    return {"dns_target_fqdn": target, **services, "tls": tls}


def _configured_hosts(config: dict[str, Any]) -> list[tuple[str, str]]:
    if "config" in config:
        return [("ops", OPS_HOST), ("config", CONFIG_HOST), ("sec", SEC_HOST)]
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
    """Plan missing NEW aliases only; the HTTP redirect is a separate Nginx change."""
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
    planned_hosts = (OPS_HOST, CONFIG_HOST, SEC_HOST) if "config" in values else (OPS_HOST, SEC_HOST)
    for hostname in planned_hosts:
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

    if len(changes) > len(planned_hosts) or any(
        item["ResourceRecordSet"]["Name"] not in NEW_HOSTS for item in changes
    ):
        raise EdgeConfigError("DNS plan exceeded the fixed NEW hostname scope")
    return {
        "Comment": "awsops NEW-only aliases; OLD and target records are never changed",
        "Changes": changes,
    }


def render_nginx(config: Any) -> str:
    """Render NEW routing only. Output is a candidate, never a live readiness claim."""
    values = validate_config(config)
    dashboard = "config" in values
    host_map = _configured_hosts(values)
    identities = ", ".join(HOST_TLS_IDENTITIES.values()) if dashboard else TLS_IDENTITY
    output = [
        "# Generated by awsops_edge.py; NEW-only candidate; never replace the OLD site.",
        "# Replace matching NEW blocks, do not install duplicate server_name definitions.",
        f"# Dedicated certificate identities: {identities}",
        "server {",
        "    listen 80;",
        f"    server_name {' '.join(host.rstrip('.') for _, host in host_map)};",
        "    return 308 https://$host$request_uri;",
        "}",
    ]
    for name, hostname in host_map:
        tls = values["tls"][name] if dashboard else values["tls"]
        output.extend([
            "", "server {", "    listen 443 ssl;",
            f"    server_name {hostname.rstrip('.')};",
            f"    ssl_certificate {tls['certificate_file']};",
            f"    ssl_certificate_key {tls['private_key_file']};",
        ])
        if dashboard and name == "ops":
            output.extend([
                "    location = /health {",
                "        default_type text/plain;",
                '        return 200 "entry redirect configured\\n";',
                "    }",
                "    location / {",
                f"        return 308 https://{CONFIG_HOST.rstrip('.')}$request_uri;",
                "    }", "}",
            ])
            continue
        service = values[name]
        if dashboard and name == "config":
            output.extend([
                '    auth_basic "awsops Config Dashboard";',
                f"    auth_basic_user_file {service['basic_auth_file']};",
            ])
        output.extend([
            "", "    location / {",
            f"        proxy_pass http://127.0.0.1:{service['loopback_port']};",
            "        proxy_http_version 1.1;",
        ])
        if dashboard and name == "config":
            output.extend([
                "        limit_except GET HEAD { deny all; }",
                '        proxy_set_header Authorization "";',
            ])
        else:
            output.extend([
                "        proxy_set_header Upgrade $http_upgrade;",
                '        proxy_set_header Connection "upgrade";',
            ])
        output.extend([
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_set_header X-Forwarded-Proto $scheme;",
            "    }", "}",
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
    dns_parser = subparsers.add_parser("plan-dns", help="plan only the configured fixed NEW Route 53 aliases")
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
