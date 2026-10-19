#!/usr/bin/env python3
"""Stage the versioned AeroNexus theme for the private DJI Vue source.

Dry-run by default; --apply only inserts a stylesheet link in the local
Vue index.html after making a protected backup. It does not run npm, Docker,
DJI commands, or change the original Pilot 2 login/SDK integration.

The CSS is supplied by the already mounted /aeronexus/ static directory.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
EDGE = ROOT / "cloud-server" / "edge"
WEB = EDGE / "runtime" / "upstream" / "web"
HTML = WEB / "index.html"
CSS = ROOT / "deploy" / "cloud-server" / "control-portal" / "pilot-ui.css"
PORTAL_OVERLAY = EDGE / "compose.portal.yaml"
BACKUP = EDGE / "pilot-ui-backup" / "index.html"

LINK = '    <link rel="stylesheet" href="/aeronexus/pilot-ui.css" data-aeronexus-theme="v1" />'
APP_IDS = ('id="demo-app"', 'id="app"', "id='demo-app'", "id='app'")
MODULE_ENTRIES = ('src="/src/main.ts"', 'src="/src/main.js"',
                  'src="./src/main.ts"', 'src="./src/main.js"')
PORTAL_TARGET = "target: /usr/share/nginx/html/aeronexus"


def preflight(html: Path, css: Path, overlay: Path) -> tuple[str, str]:
    """Fail closed if private upstream version or static mount is unexpected."""
    if not html.is_file() or html.is_symlink():
        raise ValueError("Lokaler Vue-Einstieg fehlt oder ist ein Symlink")
    if not css.is_file() or css.is_symlink():
        raise ValueError("AeroNexus-Stylesheet fehlt oder ist ein Symlink")
    if not overlay.is_file() or overlay.is_symlink():
        raise ValueError("Portal-Overlay fehlt oder ist ein Symlink")
    mount = overlay.read_text(encoding="utf-8")
    if PORTAL_TARGET not in mount or "read_only: true" not in mount:
        raise ValueError("Portal-Overlay entspricht nicht dem erwarteten read-only-Mount")
    original = html.read_text(encoding="utf-8")
    if not any(marker in original for marker in APP_IDS):
        raise ValueError("Unbekannter DJI-Vue-App-Einstieg – kein Theme-Patch")
    if not any(marker in original for marker in MODULE_ENTRIES):
        raise ValueError("Unbekannte DJI-Vite-Einstiegsdatei – kein Theme-Patch")
    if len(re.findall(r"</head\s*>", original, flags=re.I)) != 1:
        raise ValueError("HTML-Head nicht eindeutig")
    stylesheet = css.read_text(encoding="utf-8")
    if "AeroNexusAdvanced" not in stylesheet or len(stylesheet) < 500:
        raise ValueError("Unbekanntes Stylesheet")
    if original.count('data-aeronexus-theme="v1"') > 1:
        raise ValueError("Mehrfaches Theme-Tag erkannt")
    if 'data-aeronexus-theme=' in original and LINK not in original:
        raise ValueError("Abweichendes bestehendes Theme-Tag – nicht überschreiben")
    if LINK in original and original.count(LINK) != 1:
        raise ValueError("Theme-Link nicht eindeutig")
    if '/aeronexus/pilot-ui.css' in original and LINK not in original:
        raise ValueError("Anderer CSS-Link bereits vorhanden")
    return original, stylesheet


def patch_html(original: str) -> str:
    """Only add a link to CSS; preserve every byte of the DJI Vue scripts."""
    if LINK in original:
        return original
    return re.sub(r"</head\s*>", LINK + "\n  </head>", original, count=1, flags=re.I)


def apply(html: Path, backup: Path, original: str, updated: str) -> str:
    if original == updated:
        return "Bereits aktiviert – keine Dateien geändert"
    if backup.exists():
        if backup.is_symlink() or not backup.is_file() or backup.read_text(encoding="utf-8") != original:
            raise RuntimeError("Vorhandenes Pilot-UI-Backup ist abweichend – Abbruch")
    else:
        backup.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        backup.parent.chmod(0o700)
        # Exclusive creation; does not replace an operator's backup.
        with backup.open("x", encoding="utf-8") as stream:
            stream.write(original)
        backup.chmod(0o600)
    fd, name = tempfile.mkstemp(prefix=".anx-theme-", suffix=".html", dir=html.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(updated)
        os.chmod(name, stat.S_IMODE(html.stat().st_mode))
        os.replace(name, html)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return "Theme-Link in privatem Vue-Quellcode vorbereitet; Docker unverändert"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Vue-HTML mit gesichertem CSS-Link vorbereiten; kein Build")
    args = parser.parse_args(argv)
    try:
        original, _ = preflight(HTML, CSS, PORTAL_OVERLAY)
        updated = patch_html(original)
        if args.apply:
            print(apply(HTML, BACKUP, original, updated))
            print("Nur nach separatem Review: branded control Image neu bauen, danach control allein neu erstellen.")
        else:
            print("PREFLIGHT OK – Vue-Theme", "bereits verlinkt" if updated == original else "vorbereitbar")
            print("Keine Dateien, Container, MQTT- oder DJI-Parameter verändert")
        return 0
    except (OSError, ValueError, RuntimeError, UnicodeError) as error:
        # No original HTML, keys, environment or exception payloads are printed.
        print(f"THEME ABGEBROCHEN ({type(error).__name__}): {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
