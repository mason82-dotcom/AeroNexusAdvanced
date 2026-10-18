#!/usr/bin/env python3
"""Download the exact, SRI-pinned Leaflet assets used by AeroNexus Studio.

Only used for offline Chromium UI tests. Fails closed on changed bytes.
Never contacts DJI, the local Pi or any user workspace.
"""
import argparse
import base64
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen


VERSION = "1.9.4"
BASE_URL = f"https://cdn.jsdelivr.net/npm/leaflet@{VERSION}/dist"
SRI = {
    "leaflet.js": "20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=",
    "leaflet.css": "p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=",
}


def download(path: Path) -> None:
    name = path.name
    if name not in SRI:
        raise ValueError("Unknown Leaflet test asset")
    if path.is_file():
        content = path.read_bytes()
        digest = base64.b64encode(hashlib.sha256(content).digest()).decode("ascii")
        if digest == SRI[name]:
            print(name + ": existing pinned asset verified")
            return
    req = Request(BASE_URL + "/" + name,
                  headers={"User-Agent": "AeroNexusAdvanced-Leaflet-CI/1"})
    with urlopen(req, timeout=30) as response:
        content = response.read(1024 * 1024 + 1)
    if not content or len(content) > 1024 * 1024:
        raise ValueError("Empty or oversized Leaflet asset: " + name)
    digest = base64.b64encode(hashlib.sha256(content).digest()).decode("ascii")
    if digest != SRI[name]:
        raise ValueError("Leaflet asset failed pinned SHA256 integrity: " + name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    print(name + ": SHA256 verified")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in SRI:
        download(args.output / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
