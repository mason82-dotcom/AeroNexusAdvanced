#!/usr/bin/env python3
"""Explicit one-time HTTPS download of DJI's official HMS translation catalog.

Never invoked automatically by the server. Keeps vendor text out of Git, updates
a local private 0600 file atomically and rejects redirects or oversized content.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener, HTTPRedirectHandler
from aeronexus.hms_catalog import CATALOG_MAX_BYTES, KEY, MAX_ENTRIES, catalog_path

OFFICIAL_URL = (
    "https://terra-1-g.djicdn.com/"
    "fee90c2e03e04e8da67ea6f56365fc76/"
    "SDK%20%E6%96%87%E6%A1%A3/CloudAPI/hms.json"
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError("DJI HMS catalog redirect rejected")


def validate(data: bytes) -> int:
    obj = json.loads(data)
    if not isinstance(obj, dict) or not 100 <= len(obj) <= MAX_ENTRIES:
        raise ValueError("Unexpected DJI HMS catalog size")
    usable = sum(isinstance(k, str) and KEY.fullmatch(k)
                 and isinstance(v, dict) and
                 any(isinstance(v.get(x), str) and v[x].strip() for x in ("de", "en"))
                 for k, v in obj.items())
    if usable < 100:
        raise ValueError("HMS catalog has too few usable messages")
    return usable


def install(dest: Path) -> int:
    opener = build_opener(ProxyHandler({}), HTTPSHandler(), NoRedirect())
    with opener.open(Request(OFFICIAL_URL, method="GET"), timeout=25) as response:
        if response.status != 200:
            raise ValueError("DJI HMS catalog HTTP failure")
        data = response.read(CATALOG_MAX_BYTES + 1)
    if len(data) > CATALOG_MAX_BYTES:
        raise ValueError("DJI HMS catalog too large")
    count = validate(data)
    if dest.exists() and dest.is_symlink():
        raise ValueError("Refusing symlink target")
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode="wb", dir=dest.parent, prefix=".hms-",
                                     delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        os.chmod(tmp.name, 0o600)
        name = tmp.name
    try:
        os.replace(name, dest)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=catalog_path())
    args = parser.parse_args()
    os.umask(0o077)
    count = install(args.output.expanduser().resolve())
    print(f"DJI HMS copy catalog installed: {count} entries; permissions 0600")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
