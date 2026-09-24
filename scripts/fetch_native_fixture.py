"""Explicit immutable source fetch; release and manual-canary profiles stay separate."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
ROOT = Path(__file__).resolve().parents[1]


def main():
    for profile, folder in (("librechat", "native-upstream"), ("canary", "canary-upstream")):
        pin = json.loads((ROOT / "integration" / profile / "upstream.json").read_text())
        checked = {}
        for key, name in (("controller", "resume.js"), ("producer", "client.js")):
            url = "https://raw.githubusercontent.com/{}/{}/{}".format(pin["repository"], pin["commit"], pin[key])
            with urlopen(url, timeout=30) as response:
                raw = response.read(pin["fixture_max_bytes"] + 1)
            digest = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
            if len(raw) > pin["fixture_max_bytes"] or digest != pin[key + "_blob"]:
                raise ValueError("immutable upstream source drift")
            checked[name] = raw
        target = ROOT / "artifacts" / folder
        target.mkdir(parents=True, exist_ok=True)
        for name, raw in checked.items():
            (target / name).write_bytes(raw)
    print("PINNED_RELEASE_AND_CANARY_SOURCES_READY")


if __name__ == "__main__":
    main()
