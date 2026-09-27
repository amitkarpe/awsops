#!/usr/bin/env python3
"""Prepare/verify a Home DEV LibreChat source tree from the pinned Git source.

This script never reads the retained EC2 filesystem, creates AWS resources, or
writes credentials. It prepares source only; private configuration remains an
owner-local step documented in integration/runtime/home/README.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PIN_FILE = ROOT / "integration" / "runtime" / "librechat-runtime.json"
HOME_FILES = (
    ROOT / "integration" / "runtime" / "home" / "docker-compose.yaml",
    ROOT / "integration" / "runtime" / "home" / "librechat.yaml.example",
    ROOT / "integration" / "runtime" / "home" / "home-demo.env.example",
)
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


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
    if (version_major("node") or 0) < 22:
        raise RuntimeError("Node.js 22+ is required")
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


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="awsops Home demo source bootstrap")
    sub = value.add_subparsers(dest="action", required=True)
    sub.add_parser("check", help="validate local prerequisites and committed runtime contract")
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
        else:
            verify(args.target)
    except (RuntimeError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"HOME_DEMO_REFUSED: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
