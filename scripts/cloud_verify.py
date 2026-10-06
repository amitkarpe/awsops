#!/usr/bin/env python3
"""Run the repository-only CI checks; never start Home services or call AWS.

Use --bootstrap for public downloads and the online dependency audit.
Without it, dependencies/fixtures must already exist; downloads/audit are skipped.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "integration/config_dashboard"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true", help="allow public dependency/source downloads")
    args = parser.parse_args()
    env = dict(os.environ, AWSOPS_REQUIRE_NATIVE_FIXTURE="1", AWS_EC2_METADATA_DISABLED="true")
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / "artifacts/playwright-browsers"))
    failures = []
    summary = []

    def skip(reason: str) -> None:
        print(f"SKIP {reason}", flush=True)
        summary.append((reason, "SKIP"))

    def run(label: str, argv: list[str], cwd: Path = ROOT) -> bool:
        start = time.monotonic()
        print(f"RUN {label}: {shlex.join(argv)} (cwd={cwd})", flush=True)
        try:
            code = subprocess.run(argv, cwd=cwd, env=env, check=False).returncode
        except OSError as error:
            print(f"UNAVAILABLE {label}: {error}", flush=True)
            code = 127
        print(f"{'PASS' if code == 0 else 'FAIL'} {label} exit={code} seconds={time.monotonic() - start:.1f}", flush=True)
        summary.append((label, "PASS" if code == 0 else f"FAIL (exit {code})"))
        if code:
            failures.append(label)
        return code == 0

    python = sys.executable
    print("Repository/synthetic browser checks only; no live provider or owner-auth acceptance.", flush=True)
    if args.bootstrap:
        run("pinned native fixtures", [python, "scripts/fetch_native_fixture.py"])
        run("dashboard dependency install", ["npm", "ci", "--no-audit"], DASHBOARD)
        run("dependency audit (high/critical gate)", ["npm", "audit", "--audit-level=high"], DASHBOARD)
        run("headless Chromium install", ["node", "node_modules/playwright/cli.js", "install", "--only-shell", "chromium"], DASHBOARD)
    else:
        skip("public downloads and online dependency audit: use --bootstrap for CI parity")

    # Both fixtures must exist: the producer suite otherwise silently skips cases.
    if all((ROOT / "artifacts/native-upstream" / name).is_file() for name in ("client.js", "resume.js")):
        run("Python and native contracts", [python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
    else:
        print("FAIL native fixtures missing; run with --bootstrap", flush=True)
        failures.append("native fixtures missing")
        summary.append(("native fixtures missing", "FAIL"))
    run("read-only evidence boundary", ["node", "--test", "tests/cloud_readonly.test.mjs"])
    run("synthetic read-only artifact", ["node", "scripts/cloud_readonly_mock.mjs"])
    run("cockpit projection", ["node", "--test", "tests/demo_cockpit.test.cjs"])
    run("runtime prerequisites", [python, "scripts/home_demo.py", "check"])
    run("Compose configuration only", ["docker", "compose", "-f", "integration/runtime/home/docker-compose.yaml", "config", "-q"])
    if args.bootstrap:
        with tempfile.TemporaryDirectory(prefix="awsops-cloud-source-") as target:
            if run("pinned runtime source prepare", [python, "scripts/home_demo.py", "prepare", target]):
                run("pinned runtime source verify", [python, "scripts/home_demo.py", "verify", target])
            else:
                skip("source verify: prepare failed")
    else:
        skip("pinned runtime source prepare/verify: public Git download requires --bootstrap")
    run("dashboard lint", ["npm", "run", "lint"], DASHBOARD)
    run("Conformance Pack offline validation", ["npm", "run", "validate:pack"], DASHBOARD)
    run("synthetic Config Pack preflight", ["node", "scripts/config_pack_preflight_mock.mjs"])
    if run("dashboard build", ["npm", "run", "build"], DASHBOARD):
        run("artifact read permissions", ["npm", "run", "prepare:runtime"], DASHBOARD)
        run("synthetic config2 browser journey", ["npm", "run", "test:browser"], DASHBOARD)
    else:
        skip("artifact read permissions: build failed")
        skip("synthetic config2 browser journey: build failed")
    skip("GitHub CI result: inspect the PR's exact-head workflow run separately")
    skip("Home runtime/browser acceptance: needs private services, login and canonical evidence")
    skip("Tailscale/Funnel lifecycle: owner-local routing and separate authority")
    skip("AWS readback/deployment/remediation: requires separate AWS authority and identity")
    print(f"CLOUD_VERIFY {'FAIL' if failures else 'PASS'} failures={len(failures)}", flush=True)
    # Only fixed labels/statuses enter the summary, never child output or private state.
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary_path).open("a", encoding="utf-8") as output:
            output.write("## Repository verification\n\n")
            output.write("Contract/build/synthetic browser evidence only; no live provider or owner-auth acceptance.\n\n")
            output.write("| Check | Result |\n| --- | --- |\n")
            for label, status in summary:
                output.write(f"| {label} | {status} |\n")
            output.write(f"\nCLOUD_VERIFY {'FAIL' if failures else 'PASS'} failures={len(failures)}\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
