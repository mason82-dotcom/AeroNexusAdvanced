#!/usr/bin/env python3
"""Stage the visual DJI Vue theme without rebuilding the working DJI application.

Reads the compiled Nginx HTML from the active control container, inserts one
stylesheet <link>, and prepares a separate read-only Compose file mount.

Default: completely read-only. --apply: writes only ignored private files
in cloud-server/edge. Never builds/restarts containers, touches secrets, or
modifies Cloud API, JSBridge, app code, MQTT or the image.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
EDGE = ROOT / "cloud-server/edge"
PORTAL = ROOT / "deploy/cloud-server/control-portal"
THEME = PORTAL / "pilot-ui.css"
PORTAL_OVERLAY = EDGE / "compose.portal.yaml"
THEME_OVERLAY = EDGE / "compose.theme.yaml"
RUNTIME = EDGE / "pilot-ui-runtime"
BACKUP = RUNTIME / "index.original.html"
THEMED = RUNTIME / "index.html"
CONTAINER = "aeronexusadvanced-cloud-control-1"
IMAGE = "aeronexusadvanced/control:branded"
NGINX_INDEX = "/usr/share/nginx/html/index.html"
MOUNT_TARGET = "/usr/share/nginx/html/index.html"
LINK = '<link rel="stylesheet" href="/aeronexus/pilot-ui.css" data-aeronexus-runtime-theme="v1">'
PORTAL_TARGET = "target: /usr/share/nginx/html/aeronexus"


def docker_read(*args: str) -> bytes:
    """Read Docker only, with no secret-bearing log output."""
    try:
        result = subprocess.run(
            ["docker", *args], capture_output=True, timeout=25, check=True
        )
    except (subprocess.SubprocessError, OSError) as error:
        raise RuntimeError("Docker-Container kann nicht sicher gelesen werden") from error
    return result.stdout


def read_live_html() -> str:
    image = docker_read("inspect", "--format", "{{.Config.Image}}", CONTAINER).decode(
        "utf-8", "strict"
    ).strip()
    if image != IMAGE:
        raise ValueError("Der Webcontainer verwendet nicht das erwartete branded-Image")
    raw = docker_read("exec", CONTAINER, "cat", NGINX_INDEX)
    if len(raw) < 150 or len(raw) > 200_000:
        raise ValueError("Unerwartete Größe des DJI-Nginx-Einstiegs")
    return raw.decode("utf-8", "strict")


def valid_source(html: str) -> None:
    """Never accidentally replace the operational compiled Vue with a source template."""
    if len(re.findall(r"</head\s*>", html, flags=re.I)) != 1:
        raise ValueError("Kein eindeutiger HTML-Head im laufenden Vue-Image")
    if not re.search(r'<div\s+id=["\'](?:demo-app|app)["\']', html, flags=re.I):
        raise ValueError("DJI-Vue-App-Mountpoint im ausgelieferten HTML nicht erkannt")
    if not re.search(r"<script\b", html, flags=re.I) or "/assets/" not in html:
        raise ValueError("Keine gebauten DJI-Vue-Assets im Web-HTML erkannt")
    if ("/aeronexus/pilot-ui.css" in html or "data-aeronexus-runtime-theme" in html):
        raise ValueError("Ein Theme wurde bereits in der Live-HTML gefunden; nicht überschreiben")


def patch_html(original: str) -> str:
    valid_source(original)
    return re.sub(r"</head\s*>", LINK + "\n</head>", original, count=1, flags=re.I)


def overlay_content(index: Path) -> str:
    return (
        "# Optional theme only; preserve ALL existing DJI Vue compiled assets.\n"
        "# Compose with core + brand + portal + this file. Only control affected.\n"
        "services:\n"
        "  control:\n"
        "    volumes:\n"
        "      - type: bind\n"
        f"        source: {json.dumps(str(index.resolve()))}\n"
        f"        target: {MOUNT_TARGET}\n"
        "        read_only: true\n"
        "        bind:\n"
        "          create_host_path: false\n"
    )


def preflight(html: str, theme: Path, portal_overlay: Path) -> str:
    valid_source(html)
    if not theme.is_file() or theme.is_symlink() or theme.stat().st_size < 500:
        raise ValueError("Versioniertes AeroNexus-Theme nicht gefunden")
    if not portal_overlay.is_file() or portal_overlay.is_symlink():
        raise ValueError("Das aktive Portal-Compose-Overlay fehlt")
    overlay = portal_overlay.read_text(encoding="utf-8")
    if PORTAL_TARGET not in overlay or "read_only: true" not in overlay:
        raise ValueError("Das Portal-Compose-Overlay hat kein read-only-Mount")
    if not (PORTAL / "index.html").is_file():
        raise ValueError("Die vorhandene Portalseite fehlt")
    return patch_html(html)


def private_directory(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("Privater Staging-Ordner ist ein Symlink")
    path.mkdir(mode=0o700, exist_ok=True)
    if not path.is_dir():
        raise ValueError("Privater Staging-Pfad ist kein Verzeichnis")
    if path.stat().st_mode & 0o077:
        raise ValueError("Privater Staging-Ordner hat zu offene Rechte")


def write_exact(path: Path, contents: bytes) -> str:
    """Create-only staging: never replace operator edits or previous image backup."""
    if path.is_symlink():
        raise ValueError("Staging-Datei darf kein Symlink sein")
    if path.exists():
        if not path.is_file() or path.read_bytes() != contents:
            raise ValueError("Bereits vorhandene Staging-Datei weicht ab; Abbruch")
        return "vorhanden"
    fd, tmp = tempfile.mkstemp(prefix=".anx-html-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
        os.chmod(tmp, 0o600)
        os.link(tmp, path)  # fail if path was created concurrently
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return "erstellt"


def stage(original: str, modified: str, runtime: Path, overlay: Path) -> dict[str, str]:
    private_directory(runtime)
    # Validate all existing destination files before creating anything.
    contents = {
        runtime / "index.original.html": original.encode("utf-8"),
        runtime / "index.html": modified.encode("utf-8"),
        overlay: overlay_content(runtime / "index.html").encode("utf-8"),
    }
    for path, data in contents.items():
        if path.is_symlink() or (path.exists() and (
                not path.is_file() or path.read_bytes() != data)):
            raise ValueError("Vorhandenes lokales Staging weicht ab: " + path.name)
    return {p.name: write_exact(p, data) for p, data in contents.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Private HTML-/Compose-Stagingdateien anlegen; keine Containeraktion")
    args = parser.parse_args(argv)
    try:
        original = read_live_html()
        modified = preflight(original, THEME, PORTAL_OVERLAY)
        if args.apply:
            files = stage(original, modified, RUNTIME, THEME_OVERLAY)
            print("THEME-STAGING OK:", ", ".join(k + "=" + v for k, v in files.items()))
            print("Keine Images gebaut oder Container neu gestartet")
        else:
            print("PREFLIGHT OK – gebautes DJI Vue + CSS vorhanden")
            print("Nur Prüfung: keine Dateien, Container oder DJI-Parameter verändert")
        return 0
    except (OSError, ValueError, RuntimeError, UnicodeError) as error:
        print(f"THEME-STAGING ABGEBROCHEN ({type(error).__name__}): {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
