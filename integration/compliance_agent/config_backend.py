"""Strict read-only client for the NEW config2 four-account evidence API."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ALIASES = ("lab-dev", "lab-poc", "lab-qa", "lab-sec")
CONTROLS = (
    "s3-bucket-level-public-access-prohibited",
    "restricted-ssh",
)
STATUSES = {"COMPLIANT", "NON_COMPLIANT", "INSUFFICIENT_DATA", "NOT_APPLICABLE"}
MAX_BACKEND_BYTES = 256 * 1024


class BackendEvidenceError(RuntimeError):
    """The config2 evidence contract is unavailable or incomplete."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BackendEvidenceError("config2 redirect rejected")


def _base(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise BackendEvidenceError("config2 backend must be loopback HTTP")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise BackendEvidenceError("config2 backend URL is not canonical")
    port = parsed.port or 4313
    if not 1024 <= port <= 65535:
        raise BackendEvidenceError("config2 backend port is invalid")
    return f"http://{parsed.hostname}:{port}"


def _get_json(base_url: str, path: str, *, timeout: float = 65.0) -> dict[str, Any]:
    base = _base(base_url)
    request = Request(base + path, headers={"Origin": base, "Accept": "application/json"})
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200 or "application/json" not in response.headers.get("content-type", "").lower():
                raise BackendEvidenceError("config2 returned an unexpected response")
            raw = response.read(MAX_BACKEND_BYTES + 1)
            if len(raw) > MAX_BACKEND_BYTES:
                raise BackendEvidenceError("config2 response is too large")
            value = json.loads(raw)
    except BackendEvidenceError:
        raise
    except Exception as exc:
        raise BackendEvidenceError("config2 unavailable") from exc
    if not isinstance(value, dict):
        raise BackendEvidenceError("config2 returned invalid JSON")
    return value


def current_evidence(base_url: str = "http://127.0.0.1:4313") -> dict[str, Any]:
    diagnostics = _get_json(base_url, "/api/diagnostics")
    provider = diagnostics.get("components", {}).get("configProvider", {})
    if diagnostics.get("ready") is not True or provider.get("status") != "READY":
        raise BackendEvidenceError("four-account Config provider is not READY")

    snapshot = _get_json(base_url, "/api/controls?environment=ALL&refresh=1")
    if (
        snapshot.get("environment") != "ALL"
        or snapshot.get("available") is not True
        or snapshot.get("partial") is not False
        or snapshot.get("availableAccounts") != 4
        or snapshot.get("totalAccounts") != 4
    ):
        raise BackendEvidenceError("four-account Config snapshot is incomplete")

    accounts = snapshot.get("accounts")
    if not isinstance(accounts, list):
        raise BackendEvidenceError("Config account evidence is invalid")
    aliases = [row.get("alias") for row in accounts if isinstance(row, dict) and row.get("available") is True]
    if tuple(sorted(aliases)) != tuple(sorted(ALIASES)) or len(aliases) != 4:
        raise BackendEvidenceError("Config aliases do not match the registered LAB scope")

    rules = snapshot.get("rules")
    if not isinstance(rules, list) or len(rules) != 8:
        raise BackendEvidenceError("expected exactly eight account/control checks")

    seen: set[tuple[str, str]] = set()
    checks: list[dict[str, Any]] = []
    for row in rules:
        if not isinstance(row, dict):
            raise BackendEvidenceError("Config rule evidence is invalid")
        allowed = {
            "accountAlias", "ConfigRuleName", "category", "status",
            "count", "capped", "warning",
        }
        if set(row) - allowed:
            raise BackendEvidenceError("config2 exposed fields outside the public-safe contract")
        alias = row.get("accountAlias")
        control = row.get("ConfigRuleName")
        status = row.get("status")
        count = row.get("count")
        key = (alias, control)
        if alias not in ALIASES or control not in CONTROLS or status not in STATUSES or key in seen:
            raise BackendEvidenceError("Config rule evidence is outside the v1 contract")
        if count is not None and (type(count) is not int or count < 0):
            raise BackendEvidenceError("Config affected count is invalid")
        if status == "COMPLIANT" and count != 0:
            raise BackendEvidenceError("compliant evidence must have zero affected resources")
        if status == "NON_COMPLIANT" and type(count) is not int:
            raise BackendEvidenceError("non-compliant evidence needs an affected-resource count")
        seen.add(key)
        checks.append({
            "account_alias": alias,
            "control": control,
            "category": row.get("category"),
            "status": status,
            "affected_resources": count,
            "capped": row.get("capped") is True,
            "warning": row.get("warning") is True,
        })

    expected = {(alias, control) for alias in ALIASES for control in CONTROLS}
    if seen != expected:
        raise BackendEvidenceError("Config evidence does not contain the exact 4 x 2 matrix")

    checks.sort(key=lambda item: (ALIASES.index(item["account_alias"]), CONTROLS.index(item["control"])))
    return {
        "version": 2,
        "source": "awsops config2",
        "fetched_at": snapshot.get("fetchedAt"),
        "aliases": list(ALIASES),
        "controls": list(CONTROLS),
        "checks": checks,
        "read_only": True,
        "identifiers_available": False,
    }
