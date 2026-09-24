"""Fetch pinned native producer/controller for explicit CI rehearsal only."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    pin = json.loads((ROOT / "integration/librechat/upstream.json").read_text())
    destination = ROOT / "artifacts" / "native-upstream"
    checked = {}
    for key, name in (("controller", "resume.js"), ("producer", "client.js")):
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(pin["repository"], pin["commit"], pin[key])
        with urlopen(url, timeout=30) as response:
            raw = response.read(pin["fixture_max_bytes"] + 1)
        if len(raw) > pin["fixture_max_bytes"]:
            raise ValueError("oversized pinned fixture")
        digest = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        if digest != pin[key + "_blob"]:
            raise ValueError("upstream source drift")
        checked[name] = raw
    destination.mkdir(parents=True, exist_ok=True)
    for name, raw in checked.items():
        (destination / name).write_bytes(raw)
    print("PINNED_NATIVE_PRODUCER_AND_CONTROLLER_READY")


if __name__ == "__main__":
    main()
