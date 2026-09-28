#!/usr/bin/env python3
"""Prepare/verify a Home DEV LibreChat source tree from the pinned Git source.

This script never reads the retained EC2 filesystem, creates AWS resources, or
writes credentials. It prepares source only; private configuration remains an
owner-local step documented in integration/runtime/home/README.md.
"""
from __future__ import annotations

import ast
import argparse
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
PIN_FILE = ROOT / "integration" / "runtime" / "librechat-runtime.json"
HOME_FILES = (
    ROOT / "integration" / "runtime" / "home" / "docker-compose.yaml",
    ROOT / "integration" / "runtime" / "home" / "librechat.yaml.example",
    ROOT / "integration" / "runtime" / "home" / "home-demo.env.example",
)
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
ALIASES = ("lab-dev", "lab-poc", "lab-qa", "lab-sec")
CONTROLS = (
    "s3-bucket-level-public-access-prohibited",
    "restricted-ssh",
)
CONFIG2_DEFAULT = "http://127.0.0.1:4313"
SEC2_DEFAULT = "http://127.0.0.1:4311"
BROWSER_EVIDENCE_DEFAULT = Path.home() / ".config" / "awsops" / "browser" / "evidence"


def load_pin() -> dict[str, object]:
    value = json.loads(PIN_FILE.read_text(encoding="utf-8"))
    required = {"repository", "repository_url", "release", "commit"}
    if set(value) < required:
        raise RuntimeError("runtime pin is incomplete")
    if value["repository"] != "LibreChat-AI/LibreChat":
        raise RuntimeError("unexpected LibreChat repository")
    if not COMMIT_RE.fullmatch(str(value["commit"])):
        raise RuntimeError("runtime pin commit must be exact")
    if value["release"] != "v0.8.8-rc1":
        raise RuntimeError("unexpected LibreChat release")
    return value


def run(argv: list[str], *, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def version_major(command: str) -> int | None:
    try:
        raw = run([command, "--version"])
    except (OSError, subprocess.CalledProcessError):
        return None
    match = re.search(r"(\d+)", raw)
    return int(match.group(1)) if match else None


def check_prerequisites() -> None:
    missing = [name for name in ("git", "node", "npm", "docker") if shutil.which(name) is None]
    if missing:
        raise RuntimeError("missing required commands: " + ", ".join(missing))
    if platform.system() != "Linux":
        raise RuntimeError("Home demo baseline is Linux/Ubuntu")
    if sys.version_info < (3, 12):
        raise RuntimeError("Python 3.12+ is required")
    if (version_major("node") or 0) < 24:
        raise RuntimeError("Node.js 24+ is required")
    load_pin()
    for path in HOME_FILES:
        if not path.is_file():
            raise RuntimeError(f"missing runtime file: {path.relative_to(ROOT)}")
    print("HOME_DEMO_PREREQS_OK")


def verify(target: Path) -> None:
    pin = load_pin()
    clone = target.expanduser().resolve() / "librechat"
    if not (clone / ".git").is_dir():
        raise RuntimeError("pinned LibreChat checkout is missing")
    head = run(["git", "rev-parse", "HEAD"], cwd=clone)
    if head != pin["commit"]:
        raise RuntimeError("LibreChat checkout does not match the pinned commit")
    package = json.loads((clone / "package.json").read_text(encoding="utf-8"))
    if package.get("version") != pin["release"]:
        raise RuntimeError("LibreChat package version does not match the pin")
    print("HOME_DEMO_SOURCE_VERIFIED")


def prepare(target: Path) -> None:
    pin = load_pin()
    target = target.expanduser().resolve()
    clone = target / "librechat"
    if clone.exists():
        raise RuntimeError("refusing existing LibreChat target; choose a new empty Home target")
    target.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--filter=blob:none", "--no-checkout", str(pin["repository_url"]), str(clone)])
    run(["git", "fetch", "--depth", "1", "origin", str(pin["commit"])], cwd=clone)
    run(["git", "checkout", "--detach", str(pin["commit"])], cwd=clone)
    verify(target)
    print(f"HOME_DEMO_SOURCE_READY {clone}")


def loopback_base(value: str, label: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port is None
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(f"{label} must be an exact loopback HTTP origin")
    return value.rstrip("/")


def fetch_json(url: str) -> object:
    with urlopen(url, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"read-only health request returned HTTP {response.status}")
        return json.loads(response.read())


def current_git_head() -> str:
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if not COMMIT_RE.fullmatch(head):
        raise RuntimeError("current Git head is unavailable")
    return head


def browser_manifest(evidence_root: Path, expected_git_head: str) -> dict[str, object]:
    evidence_root = evidence_root.expanduser().resolve()
    candidates = sorted(
        (path / "manifest.json" for path in evidence_root.glob("issue49-*") if path.is_dir()),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
    )
    if not candidates or not candidates[-1].is_file():
        raise RuntimeError("canonical browser acceptance evidence is missing")
    value = json.loads(candidates[-1].read_text(encoding="utf-8"))
    if value.get("outcome") != "COMPLIANCE_UI_PASS":
        raise RuntimeError("canonical browser acceptance did not pass")
    if value.get("git_head") != expected_git_head:
        raise RuntimeError("canonical browser acceptance is stale or unbound")
    if value.get("tool_count") != 1 or value.get("action_count") != 0:
        raise RuntimeError("sec2 must expose exactly one read-only tool and zero actions")
    if value.get("browser_auth_exported") is not False or value.get("storage_state_exported") is not False:
        raise RuntimeError("browser acceptance exported private authentication state")
    results = value.get("results")
    if not isinstance(results, list) or len(results) != 3:
        raise RuntimeError("canonical three-prompt browser evidence is incomplete")
    modes = {row.get("mode") for row in results if isinstance(row, dict)}
    if modes != {"status", "explain", "plan"}:
        raise RuntimeError("browser evidence modes do not match the canonical prompts")
    if any(row.get("checks") != 8 or row.get("archived") is not True for row in results):
        raise RuntimeError("browser evidence matrix or Archive cleanup is incomplete")
    return value


def validate_agent_files() -> None:
    agent_path = ROOT / "integration" / "compliance_agent" / "librechat-agent.json"
    agent = json.loads(agent_path.read_text(encoding="utf-8"))
    expected_tool = "ask_compliance_agent_mcp_awsops_compliance_agent"
    if agent.get("tools") != [expected_tool] or agent.get("actions") not in (None, []):
        raise RuntimeError("agent definition must contain one read-only tool and zero actions")

    server_path = ROOT / "integration" / "compliance_agent" / "mcp_server.py"
    tree = ast.parse(server_path.read_text(encoding="utf-8"), filename=str(server_path))
    tools = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            function = call.func if call else decorator
            if isinstance(function, ast.Attribute) and function.attr == "tool":
                tools.append(node.name)
    if tools != ["ask_compliance_agent"]:
        raise RuntimeError("MCP server must expose exactly ask_compliance_agent")

    yaml_path = ROOT / "integration" / "runtime" / "home" / "librechat.yaml.example"
    lines = yaml_path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("mcpServers:") + 1
    except ValueError as error:
        raise RuntimeError("Home LibreChat MCP configuration is missing") from error
    keys = []
    for line in lines[start:]:
        if line and not line.startswith(" "):
            break
        match = re.fullmatch(r"  ([a-zA-Z0-9_]+):", line)
        if match:
            keys.append(match.group(1))
    if keys != ["awsops_compliance_agent"]:
        raise RuntimeError("Home LibreChat must configure exactly one MCP server")


def validate_runtime(
    config2_base: str,
    sec2_base: str,
    evidence_root: Path,
    *,
    fetcher=fetch_json,
    expected_git_head: str | None = None,
) -> None:
    config2 = loopback_base(config2_base, "config2 URL")
    sec2 = loopback_base(sec2_base, "sec2 URL")
    validate_agent_files()

    health = fetcher(f"{config2}/api/health")
    if not isinstance(health, dict) or health.get("mode") != "AWS_READ_ONLY" or health.get("remediation") is not False:
        raise RuntimeError("config2 health is not the read-only contract")
    if tuple(health.get("environments", ())) != ALIASES or set(health.get("controls", ())) != set(CONTROLS):
        raise RuntimeError("config2 health matrix is not exactly four aliases by two controls")

    diagnostics = fetcher(f"{config2}/api/diagnostics")
    provider = diagnostics.get("components", {}).get("configProvider", {}) if isinstance(diagnostics, dict) else {}
    if not isinstance(diagnostics, dict) or diagnostics.get("status") != "READY" or diagnostics.get("ready") is not True:
        raise RuntimeError("config2 diagnostics are not READY")
    if tuple(provider.get("aliases", ())) != ALIASES or provider.get("availableAccounts") != 4 or provider.get("totalAccounts") != 4:
        raise RuntimeError("config2 diagnostics do not prove all four aliases")

    controls = fetcher(f"{config2}/api/controls?environment=ALL&refresh=1")
    if not isinstance(controls, dict) or controls.get("partial") is not False or controls.get("available") is not True:
        raise RuntimeError("config2 evidence is partial or unavailable")
    accounts = controls.get("accounts")
    rules = controls.get("rules")
    if not isinstance(accounts, list) or [row.get("alias") for row in accounts] != list(ALIASES):
        raise RuntimeError("config2 evidence aliases are incomplete or reordered")
    if not isinstance(rules, list) or len(rules) != 8:
        raise RuntimeError("config2 evidence must contain exactly eight checks")
    matrix = {(row.get("accountAlias"), row.get("ConfigRuleName")) for row in rules}
    expected = {(alias, control) for alias in ALIASES for control in CONTROLS}
    if matrix != expected:
        raise RuntimeError("config2 evidence is not the exact four by two matrix")

    sec2_config = fetcher(f"{sec2}/api/config")
    if not isinstance(sec2_config, dict):
        raise RuntimeError("sec2 application health is unavailable")
    browser_manifest(evidence_root, expected_git_head or current_git_head())
    print("HOME_DEMO_VALIDATION_OK aliases=4 checks=8 controls=2 tools=1 actions=0 prompts=3 archived=3")


def tailscale_state() -> tuple[dict[str, object], dict[str, object]]:
    if shutil.which("tailscale") is None:
        raise RuntimeError("Tailscale CLI is unavailable")
    status = json.loads(run(["tailscale", "status", "--json"]))
    if status.get("BackendState") != "Running" or status.get("Self", {}).get("Online") is not True:
        raise RuntimeError("Tailscale is not online")
    funnel = json.loads(run(["tailscale", "funnel", "status", "--json"]))
    return status, funnel


def funnel_url(status: dict[str, object]) -> str:
    dns_name = status.get("Self", {}).get("DNSName")
    if not isinstance(dns_name, str) or not dns_name.endswith(".ts.net."):
        raise RuntimeError("stable Tailscale DNS name is unavailable")
    return f"https://{dns_name.rstrip('.')}"


def exact_funnel(funnel: dict[str, object]) -> bool:
    web = funnel.get("Web", {})
    ports = funnel.get("TCP", {})
    allowed = funnel.get("AllowFunnel", {})
    if not isinstance(web, dict) or len(web) != 1 or not isinstance(ports, dict) or len(ports) != 1:
        return False
    if not isinstance(allowed, dict) or len(allowed) != 1 or next(iter(allowed.values())) is not True:
        return False
    if str(next(iter(ports))) != "443":
        return False
    host_port = next(iter(web))
    if not isinstance(host_port, str) or not host_port.endswith(":443") or host_port not in allowed:
        return False
    site = next(iter(web.values()))
    handlers = site.get("Handlers", {}) if isinstance(site, dict) else {}
    return (isinstance(handlers, dict) and len(handlers) == 1 and
            next(iter(handlers.values()), {}).get("Proxy") == SEC2_DEFAULT)


def change_funnel(argv: list[str]) -> None:
    try:
        subprocess.run(
            ["tailscale", "funnel", *argv],
            check=True,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
    except subprocess.CalledProcessError as error:
        output = (error.stdout or "") + (error.stderr or "")
        if "Funnel is not enabled on your tailnet" in output:
            raise RuntimeError("Tailscale Funnel requires owner tailnet enablement") from error
        raise RuntimeError("Tailscale Funnel route change failed") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Tailscale Funnel route change timed out; check tailnet enablement") from error


def public_start() -> None:
    status, funnel = tailscale_state()
    validate_runtime(CONFIG2_DEFAULT, SEC2_DEFAULT, BROWSER_EVIDENCE_DEFAULT)
    if funnel:
        if exact_funnel(funnel):
            print(f"HOME_DEMO_PUBLIC_READY {funnel_url(status)}")
            return
        raise RuntimeError("an existing Tailscale route must be preserved")
    serve = json.loads(run(["tailscale", "serve", "status", "--json"]))
    if serve:
        raise RuntimeError("an existing Tailscale Serve route must be preserved")
    change_funnel(["--bg", "--yes", SEC2_DEFAULT])
    status, funnel = tailscale_state()
    if not exact_funnel(funnel):
        raise RuntimeError("Tailscale did not install the exact sec2-only route")
    print(f"HOME_DEMO_PUBLIC_READY {funnel_url(status)}")


def public_status() -> None:
    status, funnel = tailscale_state()
    if not funnel:
        print("HOME_DEMO_PUBLIC_OFF")
        return
    if not exact_funnel(funnel):
        raise RuntimeError("Tailscale route differs from the sec2-only contract")
    fetch_json(f"{SEC2_DEFAULT}/api/config")
    print(f"HOME_DEMO_PUBLIC_READY {funnel_url(status)}")


def public_stop() -> None:
    _, funnel = tailscale_state()
    if not funnel:
        print("HOME_DEMO_PUBLIC_OFF")
        return
    if not exact_funnel(funnel):
        raise RuntimeError("refusing to stop an unrelated Tailscale route")
    change_funnel(["--https=443", "--yes", "off"])
    _, remaining = tailscale_state()
    if remaining:
        raise RuntimeError("Tailscale public route remains active")
    print("HOME_DEMO_PUBLIC_OFF")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="awsops Home demo source bootstrap")
    sub = value.add_subparsers(dest="action", required=True)
    sub.add_parser("check", help="validate local prerequisites and committed runtime contract")
    validate = sub.add_parser("validate", help="fail-closed read-only Home runtime validation")
    validate.add_argument("--config2-url", default=CONFIG2_DEFAULT)
    validate.add_argument("--sec2-url", default=SEC2_DEFAULT)
    validate.add_argument("--browser-evidence", type=Path, default=BROWSER_EVIDENCE_DEFAULT)
    sub.add_parser("public-start", help="validate Home and expose only sec2 through Tailscale Funnel")
    sub.add_parser("public-status", help="read back the exact sec2-only Tailscale route")
    sub.add_parser("public-stop", help="disable only the exact sec2-only Tailscale route")
    for action in ("prepare", "verify"):
        p = sub.add_parser(action)
        p.add_argument("target", type=Path)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        if args.action == "check":
            check_prerequisites()
        elif args.action == "prepare":
            prepare(args.target)
        elif args.action == "validate":
            validate_runtime(args.config2_url, args.sec2_url, args.browser_evidence)
        elif args.action == "public-start":
            public_start()
        elif args.action == "public-status":
            public_status()
        elif args.action == "public-stop":
            public_stop()
        else:
            verify(args.target)
    except (RuntimeError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"HOME_DEMO_REFUSED: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
