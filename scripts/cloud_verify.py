#!/usr/bin/env python3
"""Run the repository-only CI checks; never start Home services or call AWS.

Use --bootstrap for public downloads (fixtures, npm packages, pinned source).
Without it, dependencies/fixtures must already exist and no download is requested.
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
    failures = []

    def run(label: str, argv: list[str], cwd: Path = ROOT) -> bool:
        start = time.monotonic()
        print(f"RUN {label}: {shlex.join(argv)} (cwd={cwd})", flush=True)
        try:
            code = subprocess.run(argv, cwd=cwd, env=env, check=False).returncode
        except OSError as error:
            print(f"UNAVAILABLE {label}: {error}", flush=True)
            code = 127
        print(f"{'PASS' if code == 0 else 'FAIL'} {label} exit={code} seconds={time.monotonic() - start:.1f}", flush=True)
        if code:
            failures.append(label)
        return code == 0

    python = sys.executable
    print("Repository checks only; results do not certify live/browser acceptance.", flush=True)
    if args.bootstrap:
        run("pinned native fixtures", [python, "scripts/fetch_native_fixture.py"])
        run("dashboard dependency install", ["npm", "ci"], DASHBOARD)
    else:
        print("SKIP public downloads: use --bootstrap on a clean checkout", flush=True)

    # Both fixtures must exist: the producer suite otherwise silently skips cases.
    if all((ROOT / "artifacts/native-upstream" / name).is_file() for name in ("client.js", "resume.js")):
        run("Python and native contracts", [python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
    else:
        print("FAIL native fixtures missing; run with --bootstrap", flush=True)
        failures.append("native fixtures missing")
    run("cockpit projection", ["node", "--test", "tests/demo_cockpit.test.cjs"])
    run("runtime prerequisites", [python, "scripts/home_demo.py", "check"])
    run("Compose configuration only", ["docker", "compose", "-f", "integration/runtime/home/docker-compose.yaml", "config", "-q"])
    if args.bootstrap:
        with tempfile.TemporaryDirectory(prefix="awsops-cloud-source-") as target:
            if run("pinned runtime source prepare", [python, "scripts/home_demo.py", "prepare", target]):
                run("pinned runtime source verify", [python, "scripts/home_demo.py", "verify", target])
            else:
                print("SKIP source verify: prepare failed", flush=True)
    else:
        print("SKIP pinned runtime source prepare/verify: public Git download requires --bootstrap", flush=True)
    run("Conformance Pack offline validation", ["npm", "run", "validate:pack"], DASHBOARD)
    if run("dashboard build", ["npm", "run", "build"], DASHBOARD):
        run("artifact read permissions", ["npm", "run", "prepare:runtime"], DASHBOARD)
    else:
        print("SKIP artifact read permissions: build failed", flush=True)
    print("SKIP GitHub CI result: inspect the PR's exact-head workflow run separately")
    print("SKIP Home runtime/browser acceptance: needs private services, login and canonical evidence")
    print("SKIP Tailscale/Funnel lifecycle: owner-local routing and separate authority")
    print("SKIP AWS readback/deployment/remediation: requires separate AWS authority and identity")
    print(f"CLOUD_VERIFY {'FAIL' if failures else 'PASS'} failures={len(failures)}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
