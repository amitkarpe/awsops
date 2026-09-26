#!/usr/bin/env python3
"""Validate one public-safe final M3 acceptance packet."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from awsops.domain.m3_acceptance import validate_m3_acceptance


def main() -> int:
    if len(sys.argv) != 2:
        print('{"outcome":"REFUSED","reason":"one JSON path required"}')
        return 2
    try:
        packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        validated = validate_m3_acceptance(packet)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        print('{"outcome":"REFUSED"}')
        return 2
    print(json.dumps({"outcome": "PASS", "version": validated["version"],
                      "pr_head": validated["pr_head"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
