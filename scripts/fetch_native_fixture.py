"""Fetch one immutable upstream controller for CI rehearsal; verify before use.

No credentials/SDK/packages are used. This is an explicit CI preparation step,
not a silent download while running unit tests.
"""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    pin = json.loads((ROOT / 'integration/librechat/upstream.json').read_text())
    url = 'https://raw.githubusercontent.com/{}/{}/{}'.format(pin['repository'], pin['commit'], pin['controller'])
    with urlopen(url, timeout=30) as response:
        raw = response.read(pin['fixture_max_bytes'] + 1)
    if len(raw) > pin['fixture_max_bytes']:
        raise ValueError('oversized pinned fixture')
    digest = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
    if digest != pin['controller_blob']:
        raise ValueError('upstream source drift')
    destination = ROOT / 'artifacts' / 'native-upstream'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'resume.js').write_bytes(raw)
    print('PINNED_NATIVE_CONTROLLER_READY')


if __name__ == '__main__':
    main()
