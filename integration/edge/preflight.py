"""Read-only M2 edge inventory. Raw evidence stays in a private operator directory."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any, Callable

from integration.edge.awsops_edge import (
    CONFIG_HOST, DNS_TTL_SECONDS, HOST_TLS_IDENTITIES, OLD_CONFIG_HOST,
    OLD_HOSTS, OPS_HOST, SEC_HOST, TLS_IDENTITY, _dns_name, _record_name,
)


ZONE_NAME = "astromedicomp.org."
PUBLIC_NAMES = OLD_HOSTS | {OLD_CONFIG_HOST, OPS_HOST, CONFIG_HOST, SEC_HOST}
TOOLS_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
MAX_COMMAND_BYTES = 2_000_000
SHOW_PROPERTIES = (
    "Id", "LoadState", "ActiveState", "SubState", "MainPID",
    "WorkingDirectory", "StateDirectory", "EnvironmentFiles",
)
TARGET_A_JQ = '[.ResourceRecordSets[] | select(.Name==$target and .Type=="A")] | length == 1'


class PreflightError(ValueError):
    """A missing or unsafe explicit input."""


@dataclass(frozen=True)
class CommandResult:
    code: int
    stdout: str
    stderr: str = ""


def _optional_unit(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.@:-]+\.service", value):
        raise PreflightError("unit names must be explicit service units")
    return value


def _optional_path(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"/[A-Za-z0-9_./-]+", value) or ".." in Path(value).parts:
        raise PreflightError("host config paths must be explicit absolute paths")
    return value


def validate_inputs(raw: Any) -> dict[str, Any]:
    expected = {
        "aws_profile", "hosted_zone_id", "dns_target_fqdn", "units",
        "candidate_ports", "nginx_config_file", "certbot_config_dir", "dns01_role_name",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise PreflightError("private config has missing or unexpected fields")
    profile = raw["aws_profile"]
    zone_id = raw["hosted_zone_id"]
    if not isinstance(profile, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", profile):
        raise PreflightError("verified AWS profile is required")
    if not isinstance(zone_id, str) or not re.fullmatch(r"Z[A-Z0-9]{8,}", zone_id):
        raise PreflightError("verified hosted-zone identifier is required")
    try:
        target = _dns_name(raw["dns_target_fqdn"], "dns_target_fqdn")
    except ValueError as exc:
        raise PreflightError("verified DNS target is required") from exc
    if target in PUBLIC_NAMES:
        raise PreflightError("DNS target must be a separate retained-host name")
    units = raw["units"]
    if not isinstance(units, dict):
        raise PreflightError("unit mapping must be explicit")
    legacy_units = {"old_ops", "old_sec", "new_ops", "new_sec"}
    dashboard_units = {"old_ops", "old_config", "old_sec", "new_config", "new_sec"}
    if set(units) == legacy_units:
        dashboard_mode = False
    elif set(units) == dashboard_units:
        dashboard_mode = True
    else:
        raise PreflightError("unit mapping must match the legacy or config2 dashboard roles")
    units = {key: _optional_unit(value) for key, value in units.items()}
    named_units = [value for value in units.values() if value]
    if len(named_units) != len(set(named_units)):
        raise PreflightError("OLD and NEW unit names must be distinct")
    ports = raw["candidate_ports"]
    expected_ports = {"config", "sec"} if dashboard_mode else {"ops", "sec"}
    if not isinstance(ports, dict) or set(ports) != expected_ports:
        raise PreflightError(f"candidate_ports must have {sorted(expected_ports)} slots")
    for role, value in ports.items():
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 1024 <= value <= 65535):
            raise PreflightError(f"invalid {role} candidate port")
    selected_ports = [value for value in ports.values() if value is not None]
    if len(selected_ports) != len(set(selected_ports)):
        raise PreflightError("candidate ports must be distinct")
    role = raw["dns01_role_name"]
    if role is not None and (not isinstance(role, str) or not re.fullmatch(r"[A-Za-z0-9_+=,.@-]{1,64}", role)):
        raise PreflightError("DNS-01 role must be explicitly verified")
    return {
        "aws_profile": profile,
        "hosted_zone_id": zone_id,
        "dns_target_fqdn": target,
        "units": units,
        "candidate_ports": ports,
        "nginx_config_file": _optional_path(raw["nginx_config_file"]),
        "certbot_config_dir": _optional_path(raw["certbot_config_dir"]),
        "dns01_role_name": role,
        "dashboard_mode": dashboard_mode,
    }


def _reject_symlink_components(path: Path) -> None:
    current = Path("/")
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise PreflightError("private paths may not traverse a symlink")


def prepare_private_dir(path: Path) -> Path:
    if not path.is_absolute() or path == Path("/") or ".." in path.parts:
        raise PreflightError("output directory must be an explicit absolute path")
    repo = Path(__file__).resolve().parents[2]
    if path == repo or repo in path.parents:
        raise PreflightError("private evidence must stay outside the repository")
    _reject_symlink_components(path)
    if path.exists():
        info = path.stat()
        if not path.is_dir() or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise PreflightError("existing output directory must be owner-only")
        if any(path.iterdir()):
            raise PreflightError("use a fresh empty evidence directory")
    else:
        if not path.parent.is_dir():
            raise PreflightError("output parent directory must already exist")
        path.mkdir(mode=0o700)
    return path


def _save(directory: Path, name: str, value: Any) -> None:
    payload = json.dumps(value, sort_keys=True, indent=2, default=str).encode() + b"\n"
    fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        raise


class BotoReadOnly:
    """Only fixed SDK read methods; the profile is selected explicitly."""

    def __init__(self, profile: str):
        import boto3  # Loaded only for an actual operator run, never for fixtures.
        session = boto3.Session(profile_name=profile)
        self.sts = session.client("sts")
        self.route53 = session.client("route53")
        self.iam = session.client("iam")

    def identity(self) -> dict[str, Any]:
        return self.sts.get_caller_identity()

    def zone(self, zone_id: str) -> dict[str, Any]:
        return self.route53.get_hosted_zone(Id=zone_id)

    def records(self, zone_id: str) -> dict[str, Any]:
        rows = []
        for page in self.route53.get_paginator("list_resource_record_sets").paginate(HostedZoneId=zone_id):
            rows.extend(page["ResourceRecordSets"])
            if len(rows) > 2000:
                raise PreflightError("hosted zone exceeds bounded record inventory")
        return {"ResourceRecordSets": rows}

    def policies(self, role_name: str) -> dict[str, Any]:
        attached = self.iam.list_attached_role_policies(RoleName=role_name)
        inline = self.iam.list_role_policies(RoleName=role_name)
        if attached.get("IsTruncated") or inline.get("IsTruncated"):
            raise PreflightError("IAM policy inventory is truncated")
        managed_rows = attached.get("AttachedPolicies", [])
        inline_names = inline.get("PolicyNames", [])
        if len(managed_rows) + len(inline_names) > 20:
            raise PreflightError("IAM policy inventory exceeds bounded review")
        documents = []
        for row in managed_rows:
            arn = row["PolicyArn"]
            policy = self.iam.get_policy(PolicyArn=arn)["Policy"]
            version = self.iam.get_policy_version(
                PolicyArn=arn, VersionId=policy["DefaultVersionId"]
            )["PolicyVersion"]
            documents.append({"kind": "managed", "policy": policy, "version": version})
        for name in inline_names:
            documents.append({
                "kind": "inline", "name": name,
                "document": self.iam.get_role_policy(RoleName=role_name, PolicyName=name),
            })
        return {"role_name": role_name, "documents": documents}


class FixedHostReads:
    """Fixed argv only; no shell, service control, or configuration write."""

    def __init__(self, evidence_dir: Path):
        self.evidence_dir = evidence_dir

    def run(self, argv: tuple[str, ...]) -> CommandResult:
        allowed = (
            argv == ("dig", "+short", "NS", ZONE_NAME.rstrip("."))
            or argv == ("systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain")
            or argv == ("ss", "-H", "-ltnp")
            or (len(argv) == 4 and argv[:3] == ("nginx", "-T", "-c") and argv[3].startswith("/"))
            or (len(argv) == 4 + len(SHOW_PROPERTIES)
                and argv[:2] == ("systemctl", "show")
                and _optional_unit(argv[2]) is not None
                and argv[3:-1] == tuple(f"--property={name}" for name in SHOW_PROPERTIES)
                and argv[-1] == "--no-pager")
            or (len(argv) == 8 and argv[0] == "certbot" and argv[1] in {"certificates", "plugins"}
                and argv[2] == "--config-dir" and argv[4] == "--work-dir" and argv[6] == "--logs-dir")
            or (len(argv) == 7 and argv[:4] == ("jq", "-e", "--arg", "target")
                and argv[5] == TARGET_A_JQ
                and argv[6] == str(self.evidence_dir / "PRIVATE_ROUTE53_PLANNER_JSON"))
        )
        if not allowed:
            raise PreflightError("host command is outside the fixed read-only allowlist")
        executable = shutil.which(argv[0], path=TOOLS_PATH)
        if executable is None:
            return CommandResult(127, "", "tool unavailable")
        env = {
            "PATH": TOOLS_PATH, "HOME": str(self.evidence_dir),
            "LANG": "C.UTF-8", "PAGER": "cat", "SYSTEMD_PAGER": "cat",
        }
        try:
            completed = subprocess.run(
                [executable, *argv[1:]], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=self.evidence_dir, env=env, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return CommandResult(125, "", "command unavailable or timed out")
        if len(completed.stdout) + len(completed.stderr) > MAX_COMMAND_BYTES:
            return CommandResult(125, "", "bounded output exceeded")
        return CommandResult(
            completed.returncode,
            completed.stdout.decode("utf-8", "replace"),
            completed.stderr.decode("utf-8", "replace"),
        )


def _read_aws(directory: Path, name: str, operation: Callable[[], Any]) -> Any | None:
    try:
        response = operation()
    except Exception as exc:
        _save(directory, name, {"error_type": type(exc).__name__})
        return None
    _save(directory, name, response)
    return response


def _read_host(directory: Path, name: str, host: Any, argv: tuple[str, ...]) -> CommandResult:
    try:
        response = host.run(argv)
    except Exception as exc:
        response = CommandResult(125, "", type(exc).__name__)
    _save(directory, name, {"code": response.code, "stdout": response.stdout, "stderr": response.stderr})
    return response


def _unit_fields(response: CommandResult) -> dict[str, str]:
    if response.code != 0:
        return {}
    return dict(line.split("=", 1) for line in response.stdout.splitlines() if "=" in line)


def _vhosts(response: CommandResult) -> set[str] | None:
    if response.code != 0:
        return None
    uncommented = "\n".join(line.split("#", 1)[0] for line in response.stdout.splitlines())
    names = set()
    for match in re.finditer(r"(?m)^\s*server_name\s+([^;]+);", uncommented):
        names.update(value.lower().rstrip(".") for value in match.group(1).split())
    return names


def _listeners(response: CommandResult) -> tuple[set[int], dict[int, set[int]]] | None:
    if response.code != 0:
        return None
    ports: set[int] = set()
    pids: dict[int, set[int]] = {}
    for line in response.stdout.splitlines():
        fields = line.split()
        if len(fields) < 5 or ":" not in fields[3]:
            return None
        try:
            port = int(fields[3].rsplit(":", 1)[1])
        except ValueError:
            return None
        ports.add(port)
        address = fields[3].rsplit(":", 1)[0]
        if address.startswith("127.") or address in {"[::1]", "::1"}:
            pids[port] = {int(value) for value in re.findall(r"pid=(\d+)", line)}
    return ports, pids


def _separation(units: dict[str, dict[str, str]]) -> str:
    old = [row for role, row in units.items() if role.startswith("old_")]
    new = [row for role, row in units.items() if role.startswith("new_")]
    if not all(row.get("WorkingDirectory") and row.get("StateDirectory") for row in old + new):
        return "UNKNOWN"
    for field in ("WorkingDirectory", "StateDirectory"):
        for left in old:
            for right in new:
                a, b = Path(left[field]), Path(right[field])
                if a == b or a in b.parents or b in a.parents:
                    return "SHARED"
    return "SEPARATE"


def _dns_status(records: list[dict[str, Any]], name: str, target: str) -> str:
    matching = [row for row in records if _record_name(row) == name]
    if not matching:
        return "ABSENT"
    if name in OLD_HOSTS:
        return "PRESENT"
    exact = len(matching) == 1 and matching[0].get("Type") == "CNAME" \
        and matching[0].get("TTL") == DNS_TTL_SECONDS \
        and matching[0].get("ResourceRecords") == [{"Value": target}]
    return "EXACT" if exact else "CONFLICT"


def collect(config: dict[str, Any], output_dir: Path, aws: Any, host: Any | None = None) -> dict[str, Any]:
    values = validate_inputs(config)
    directory = prepare_private_dir(output_dir)
    host = host or FixedHostReads(directory)
    identity = _read_aws(directory, "sts.json", aws.identity)
    zone = _read_aws(directory, "zone.json", lambda: aws.zone(values["hosted_zone_id"]))
    response = _read_aws(directory, "route53-records.json", lambda: aws.records(values["hosted_zone_id"]))
    dig = _read_host(directory, "delegation.json", host, ("dig", "+short", "NS", ZONE_NAME.rstrip(".")))
    nginx = CommandResult(125, "")
    if values["nginx_config_file"]:
        nginx = _read_host(directory, "nginx.json", host, ("nginx", "-T", "-c", values["nginx_config_file"]))
    inventory = _read_host(directory, "units.json", host, ("systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain"))
    listeners = _read_host(directory, "listeners.json", host, ("ss", "-H", "-ltnp"))
    unit_rows: dict[str, dict[str, str]] = {}
    for role, unit in values["units"].items():
        if unit:
            read = _read_host(directory, f"unit-{role}.json", host, (
                "systemctl", "show", unit,
                *(f"--property={property_name}" for property_name in SHOW_PROPERTIES),
                "--no-pager",
            ))
            unit_rows[role] = _unit_fields(read)
    certs = plugins = CommandResult(125, "")
    if values["certbot_config_dir"]:
        work = directory / "certbot-work"
        logs = directory / "certbot-logs"
        work.mkdir(mode=0o700)
        logs.mkdir(mode=0o700)
        flags = ("--config-dir", values["certbot_config_dir"], "--work-dir", str(work), "--logs-dir", str(logs))
        certs = _read_host(directory, "certificates.json", host, ("certbot", "certificates", *flags))
        plugins = _read_host(directory, "certbot-plugins.json", host, ("certbot", "plugins", *flags))
    policies = None
    if values["dns01_role_name"]:
        policies = _read_aws(directory, "iam-policies.json", lambda: aws.policies(values["dns01_role_name"]))

    records = response.get("ResourceRecordSets") if isinstance(response, dict) else None
    records = records if isinstance(records, list) else []
    target = values["dns_target_fqdn"]
    planner = {"ResourceRecordSets": [
        row for row in records
        if _record_name(row) in PUBLIC_NAMES
        or (_record_name(row) == target and row.get("Type") == "A")
    ]}
    target_a = sum(_record_name(row) == target and row.get("Type") == "A" for row in planner["ResourceRecordSets"]) == 1
    if target_a:
        _save(directory, "PRIVATE_ROUTE53_PLANNER_JSON", planner)
        assertion = _read_host(directory, "target-a-assertion.json", host, (
            "jq", "-e", "--arg", "target", target, TARGET_A_JQ,
            str(directory / "PRIVATE_ROUTE53_PLANNER_JSON"),
        ))
        target_a = assertion.code == 0 and assertion.stdout.strip() == "true"
    dns = {name.rstrip("."): _dns_status(records, name, target) if response else "UNKNOWN" for name in sorted(PUBLIC_NAMES)}
    expected_ns = {
        name.rstrip(".").lower() for name in (zone or {}).get("DelegationSet", {}).get("NameServers", [])
    }
    observed_ns = {name.rstrip(".").lower() for name in dig.stdout.splitlines()} if dig.code == 0 else set()
    zone_verified = bool(
        identity and isinstance(zone, dict)
        and zone.get("HostedZone", {}).get("Name") == ZONE_NAME
        and zone.get("HostedZone", {}).get("Config", {}).get("PrivateZone") is False
        and expected_ns and expected_ns == observed_ns
    )
    vhosts = _vhosts(nginx)
    sockets = _listeners(listeners)
    candidate_free = {
        role: port for role, port in values["candidate_ports"].items()
        if port is not None and sockets is not None and port not in sockets[0]
    }
    candidate_occupied = bool(
        sockets is not None and any(
            port is not None and port in sockets[0]
            for port in values["candidate_ports"].values()
        )
    )
    dashboard_mode = values["dashboard_mode"]
    new_names = (OPS_HOST, CONFIG_HOST, SEC_HOST) if dashboard_mode else (OPS_HOST, SEC_HOST)
    new_dns = {name.rstrip("."): dns[name.rstrip(".")] for name in new_names}
    dns_collision = "CONFLICT" in new_dns.values()
    separation = _separation(unit_rows)
    old_host_names = set(OLD_HOSTS) | ({OLD_CONFIG_HOST} if dashboard_mode else set())
    old_hosts = {name.rstrip(".") for name in old_host_names}
    new_hosts = {name.rstrip(".") for name in new_names}
    old_vhosts = "UNKNOWN" if vhosts is None else ("PRESENT" if old_hosts <= vhosts else "INCOMPLETE")
    new_vhosts = "UNKNOWN" if vhosts is None else ("PRESENT" if new_hosts <= vhosts else "INCOMPLETE")
    allowed_states = {"active", "inactive", "failed", "activating", "deactivating", "reloading"}
    unit_states = {}
    for role in values["units"]:
        state = unit_rows.get(role, {}).get("ActiveState", "").lower()
        unit_states[role] = state.upper() if state in allowed_states else "UNKNOWN"
    backend_role = "new_config" if dashboard_mode else "new_ops"
    backend_pid = unit_rows.get(backend_role, {}).get("MainPID", "")
    backend_listening = bool(
        sockets is not None and backend_pid.isdigit() and int(backend_pid) > 0
        and any(int(backend_pid) in pids for pids in sockets[1].values())
    )
    backend = "YES" if unit_states.get(backend_role) == "ACTIVE" and backend_listening else (
        "NO" if values["units"].get(backend_role) and unit_states.get(backend_role) == "INACTIVE" else "UNKNOWN"
    )
    cert_blocks = re.split(r"(?m)^\s*Certificate Name:\s*", certs.stdout) if certs.code == 0 else []
    if dashboard_mode:
        domain_by_role = {
            "ops": OPS_HOST.rstrip("."), "config": CONFIG_HOST.rstrip("."), "sec": SEC_HOST.rstrip("."),
        }
        cert_status = {}
        for role_name, identity_name in HOST_TLS_IDENTITIES.items():
            present = any(
                block.startswith(identity_name + "\n") and domain_by_role[role_name] in block
                for block in cert_blocks[1:]
            )
            cert_status[role_name] = "CERT_PRESENT" if present else "UNKNOWN"
        tls = "CERT_PRESENT" if all(value == "CERT_PRESENT" for value in cert_status.values()) else "UNKNOWN"
    else:
        matched_cert = any(
            block.startswith(TLS_IDENTITY + "\n")
            and OPS_HOST.rstrip(".") in block and SEC_HOST.rstrip(".") in block
            for block in cert_blocks[1:]
        )
        cert_status = {"shared": "CERT_PRESENT" if matched_cert else "UNKNOWN"}
        tls = cert_status["shared"]
    plugin = "PRESENT" if plugins.code == 0 and "dns-route53" in plugins.stdout.lower() else "UNKNOWN"
    iam = "DOCUMENTS_CAPTURED_REVIEW_REQUIRED" if isinstance(policies, dict) and policies.get("documents") else "UNKNOWN"
    collision = "CONFLICT" if dns_collision or separation == "SHARED" or candidate_occupied else (
        "UNKNOWN" if separation == "UNKNOWN" or vhosts is None or sockets is None else "CLEAR"
    )
    reasons = []
    if not zone_verified: reasons.append("DNS_AUTHORITY_UNVERIFIED")
    if not target_a: reasons.append("TARGET_A_UNVERIFIED")
    if any(value != "PRESENT" for key, value in dns.items() if key in old_hosts): reasons.append("OLD_DNS_BASELINE_UNVERIFIED")
    if dns_collision: reasons.append("NEW_DNS_CONFLICT")
    if candidate_occupied: reasons.append("CANDIDATE_PORT_OCCUPIED")
    if inventory.code != 0 or any(state == "UNKNOWN" for state in unit_states.values()):
        reasons.append("SERVICE_INVENTORY_UNVERIFIED")
    if sockets is None or len(candidate_free) != 2:
        reasons.append("CANDIDATE_PORTS_UNVERIFIED")
    if old_vhosts != "PRESENT": reasons.append("OLD_EDGE_BASELINE_UNVERIFIED")
    if separation != "SEPARATE": reasons.append("STATE_SEPARATION_UNVERIFIED")
    reasons.extend(("AUTH_SESSION_SEPARATION_UNVERIFIED", "BROWSER_EVIDENCE_SEPARATION_UNVERIFIED"))
    if tls != "CERT_PRESENT" or plugin != "PRESENT" or iam != "DOCUMENTS_CAPTURED_REVIEW_REQUIRED":
        reasons.append("TLS_DNS01_UNVERIFIED")
    else:
        reasons.append("DNS01_EFFECTIVE_COVERAGE_UNVERIFIED")
    if backend != "YES":
        reasons.append("CONFIG2_BACKEND_UNVERIFIED" if dashboard_mode else "OPS2_BACKEND_UNVERIFIED")
    if collision != "CLEAR": reasons.append("COLLISION_UNRESOLVED")
    activation_ready = not reasons
    summary = {
        "schema_version": 2 if dashboard_mode else 1,
        "mode": "CONFIG2_DASHBOARD" if dashboard_mode else "LEGACY_TWO_HOST",
        "status": "READY" if activation_ready else "NOT_READY",
        "activation_ready": activation_ready,
        "dns": {"owner_zone_verified": zone_verified, "target_a_verified": target_a, "records": dns},
        "edge": {"old_vhosts": old_vhosts, "new_vhosts": new_vhosts},
        "service_inventory": "VERIFIED" if inventory.code == 0 else "UNKNOWN",
        "services": unit_states,
        "listeners": {
            "inventory": "VERIFIED" if sockets is not None else "UNKNOWN",
            "listener_count": len(sockets[0]) if sockets is not None else None,
            "candidate_free_at_snapshot": candidate_free,
        },
        "separation": {"runtime_state": separation, "auth_session": "UNKNOWN", "browser_evidence": "UNKNOWN"},
        "tls_dns01": {
            "certificate": tls, "certificates": cert_status, "plugin": plugin,
            "policy_documents": iam, "effective_coverage": "UNKNOWN",
        },
        ("config2_backend" if dashboard_mode else "ops2_backend"): backend,
        "collision": collision,
        "reasons": sorted(set(reasons)),
    }
    _save(directory, "PUBLIC_SAFE_SUMMARY.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Issue #33 M2 preflight; no apply mode")
    parser.add_argument("--config", type=Path, required=True, help="private explicit input JSON")
    parser.add_argument("--output-dir", type=Path, required=True, help="fresh private evidence directory")
    args = parser.parse_args(argv)
    try:
        os.umask(0o077)
        repo = Path(__file__).resolve().parents[2]
        if (not args.config.is_absolute() or ".." in args.config.parts
                or args.config == repo or repo in args.config.parents):
            raise PreflightError("private input config must be an owner-only absolute file")
        _reject_symlink_components(args.config)
        config_info = args.config.lstat()
        if (stat.S_ISLNK(config_info.st_mode) or not stat.S_ISREG(config_info.st_mode)
                or config_info.st_uid != os.getuid()
                or stat.S_IMODE(config_info.st_mode) & 0o077):
            raise PreflightError("private input config must be an owner-only absolute file")
        values = validate_inputs(json.loads(args.config.read_text(encoding="utf-8")))
        directory = prepare_private_dir(args.output_dir)
        summary = collect(values, directory, BotoReadOnly(values["aws_profile"]))
    except Exception as exc:
        sys.stderr.write(f"awsops-preflight: {type(exc).__name__}; readiness not established\n")
        return 3
    sys.stdout.write(json.dumps(summary, sort_keys=True) + "\n")
    return 0 if summary["activation_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
