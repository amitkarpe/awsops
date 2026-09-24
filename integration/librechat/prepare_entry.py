"""Private, isolated interpreter entrypoint; not a network or model tool."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from awsops.runtime.prepare_pause import main

raise SystemExit(main())
