"""Fixed isolated child entrypoint for the authenticated canary Reject path."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from awsops.runtime.receipt_stdio import main

if __name__ == "__main__":
    raise SystemExit(main())
