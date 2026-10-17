#!/usr/bin/env python3
"""Install session handoff into the migrated Cloud UI. No builds or starts."""
import argparse
from pathlib import Path
import os
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "cloud-server/edge/runtime/upstream/web"
ASSET = "aeronexus-wayline-session.js"
TAG = f'<script defer src="/{ASSET}"></script>'


def install(web: Path, asset: Path, *, apply=False) -> bool:
    index = web / "index.html"
    enums = web / "src/types/enums.ts"
    target = web / "public" / ASSET
    if index.is_symlink() or enums.is_symlink() or target.is_symlink() or target.parent.is_symlink():
        raise ValueError("Symlink im Web-Quellpfad; keine Änderung")
    content = index.read_text()
    keys = enums.read_text()
    for literal in ("'x-auth-token'", "'workspace_id'"):
        if literal not in keys:
            raise ValueError("Unerwartete lokale Cloud-Sitzungsschlüssel")
    expected = asset.read_text()
    if target.exists() and target.read_text() != expected:
        raise ValueError("Abweichendes Sitzungs-Hilfsskript vorhanden; keine Änderung")
    if content.count(TAG) > 1 or content.count("</body>") != 1:
        raise ValueError("Unerwartete index.html-Struktur")
    changed = TAG not in content or not target.exists()
    if not apply or not changed:
        return changed
    backup = web / ".aeronexus-session-index.backup"
    if not backup.exists():
        # Source HTML contains no credentials; preserve it for explicit rollback.
        with backup.open("x") as stream:
            stream.write(content)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(asset, target)
    updated = content if TAG in content else content.replace("</body>", TAG + "\n</body>")
    fd, temporary = tempfile.mkstemp(dir=index.parent, prefix=".session-index-")
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(updated)
        os.chmod(temporary, index.stat().st_mode & 0o777)
        os.replace(temporary, index)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        changed = install(WEB, ROOT / "deploy/cloud-server" / ASSET, apply=args.apply)
    except (OSError, ValueError) as exc:
        print("Web-Sitzungsübergabe nicht vorbereitet:", type(exc).__name__)
        return 1
    print("Web-Sitzungsübergabe:", "vorbereitet" if args.apply and changed else "Änderung nötig" if changed else "bereits vorbereitet")
    print("Der Control-Webcontainer muss danach gezielt neu gebaut werden; kein automatischer Start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
