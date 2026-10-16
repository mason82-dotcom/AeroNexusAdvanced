#!/usr/bin/env python3
"""Safely brand the migrated DJI Pilot 2 web source; never touch DJI auth.

Default is read-only verification. --apply changes *only* a Vue localization
entry, the HTML page title, and a Compose build overlay. It neither builds nor
starts/stops containers. Rebuilding is a separate, explicit user operation.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PROJECT = Path(__file__).resolve().parents[1]
EDGE = PROJECT / "cloud-server/edge"
WEB = EDGE / "runtime/upstream/web"
OVERLAY_TEMPLATE = PROJECT / "deploy/cloud-server/compose.brand.yaml"
OLD_LOCALE = '"Pilot Cloud API Demo": "AeroNexus Pilot"'
NEW_LOCALE = '"Pilot Cloud API Demo": "AeroNexusAdvanced"'
OLD_TITLE = "<title>AeroNexus</title>"
NEW_TITLE = "<title>AeroNexusAdvanced</title>"
EXPECTED = "192.168.178.63"
SERVICES = frozenset(("mysql", "redis", "emqx", "minio", "minio-init", "api", "control"))


def env_keys(path: Path) -> dict[str, str]:
    """Read only the harmless settings explicitly returned by this function."""
    wanted = {"SERVER_HOST", "WORKSPACE_NAME", "PLATFORM_NAME"}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in wanted:
            result[key.strip()] = value.strip().strip("'\"")
    return result


def check_pilot_source(web: Path) -> tuple[dict[Path, str], bool]:
    """Require exactly one known localization and one known page title."""
    changes: dict[Path, str] = {}
    changed = False
    for relative, before, after in (
        ("src/locales/de.ts", OLD_LOCALE, NEW_LOCALE),
        ("index.html", OLD_TITLE, NEW_TITLE),
    ):
        path = web / relative
        content = path.read_text(encoding="utf-8")
        previous = content.count(before)
        branded = content.count(after)
        if previous + branded != 1:
            raise ValueError(
                f"{relative}: erwartete eindeutige Kennzeichnung fehlt "
                "oder tritt mehrfach auf; nichts verändern"
            )
        if previous == 1:
            changes[path] = content.replace(before, after, 1)
            changed = True
    return changes, changed


def api_connection_values(container: str) -> dict[str, str]:
    """Read Docker metadata but expose only three non-secret endpoints."""
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{json .Config.Env}}", container],
        check=True, text=True, capture_output=True,
    )
    data = json.loads(result.stdout)
    allowed = {"SERVER_HOST", "BROKER_HOST", "BROKER_PORT"}
    parsed = {}
    for item in data:
        key, sep, value = item.partition("=")
        if sep and key in allowed:
            parsed[key] = value
    return parsed


def compose_safety(edge: Path, template: Path) -> None:
    """Interpolate compose in-memory; never print secret-bearing JSON."""
    # Compose needs both files in the same directory for relative build paths.
    temp = edge / ".compose.brand.validate.yaml"
    if temp.exists():
        raise RuntimeError("Temporäre Compose-Prüfdatei existiert bereits")
    try:
        shutil.copyfile(template, temp)
        result = subprocess.run(
            ["docker", "compose", "-f", "compose.core.yaml", "-f",
             temp.name, "config", "--format", "json"],
            cwd=edge, check=True, text=True, capture_output=True)
        config = json.loads(result.stdout)
        if config.get("name") != "aeronexusadvanced-cloud":
            raise RuntimeError("Unerwarteter Docker-Compose-Projektname")
        services = config.get("services", {})
        if set(services) != SERVICES:
            raise RuntimeError("Compose-Overlay würde den Dienstumfang ändern")
        control = services["control"]
        if control.get("image") != "aeronexusadvanced/control:branded":
            raise RuntimeError("Branded-Image-Tag nicht isoliert")
        web = (edge / "runtime/upstream/web").resolve()
        if Path(control["build"]["context"]).resolve() != web:
            raise RuntimeError("Falscher Web-Build-Kontext")
        if not any(int(port["target"]) == 80 and
                   str(port.get("published")) == "8085"
                   for port in control.get("ports", ())):
            raise RuntimeError("Pilot-2-Web-Port wurde verändert")
    finally:
        if temp.exists():
            temp.unlink()


def atomic_write(path: Path, contents: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".branding-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(contents)
        os.chmod(tmp, path.stat().st_mode & 0o777)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def apply_brand(web: Path, changes: dict[Path, str], edge: Path, template: Path) -> None:
    backups = edge / "branding-backup"
    backups.mkdir(mode=0o700, exist_ok=True)
    backups.chmod(0o700)
    for path, replacement in changes.items():
        relative = path.relative_to(web)
        original = backups / relative
        original.parent.mkdir(parents=True, exist_ok=True)
        if not original.exists():
            # Preserve the original patched source for exact rollback.
            shutil.copy2(path, original)
        atomic_write(path, replacement)
        print("Aktualisiert:", relative.as_posix())
    dest = edge / "compose.brand.yaml"
    if dest.exists() and dest.read_bytes() != template.read_bytes():
        raise RuntimeError("Abweichende lokale Compose-Branding-Datei vorhanden")
    if not dest.exists():
        shutil.copy2(template, dest)
        print("Compose-Build-Overlay: bereit")
    print("Nur Quelldateien vorbereitet. Keine Container oder Images geändert.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="branding to the local source, without build or restart")
    parser.add_argument("--expected-host", default=EXPECTED,
                        help="the Pi IPv4 address expected by DJI Pilot 2")
    args = parser.parse_args(argv)
    try:
        env = env_keys(EDGE / ".env")
        source = {
            "SERVER_HOST": env.get("SERVER_HOST", ""),
            "WORKSPACE_NAME": env.get("WORKSPACE_NAME", ""),
            "PLATFORM_NAME": env.get("PLATFORM_NAME", ""),
        }
        print("SERVER_HOST:", source["SERVER_HOST"] or "(fehlt)")
        print("WORKSPACE_NAME:", source["WORKSPACE_NAME"] or "(fehlt)")
        print("PLATFORM_NAME:", source["PLATFORM_NAME"] or "(fehlt)")
        api = api_connection_values("aeronexusadvanced-cloud-api-1")
        for name in ("SERVER_HOST", "BROKER_HOST", "BROKER_PORT"):
            print(f"DJI API {name}:", api.get(name) or "(fehlt)")
        if source["SERVER_HOST"] != args.expected_host:
            raise RuntimeError("Die Cloud-.env enthält nicht die erwartete Pi-IP")
        if source["WORKSPACE_NAME"] != "AeroNexusAdvanced" or (
            source["PLATFORM_NAME"] != "AeroNexusAdvanced"
        ):
            raise RuntimeError("Workspace-/Plattformnamen in Cloud-.env prüfen")
        if (api.get("SERVER_HOST") != args.expected_host or
                api.get("BROKER_HOST") != args.expected_host or
                api.get("BROKER_PORT") != "1884"):
            raise RuntimeError("Die laufende DJI API verwendet eine andere "
                               "Server- oder Broker-Adresse; erst korrigieren")
        changes, changed = check_pilot_source(WEB)
        if not OVERLAY_TEMPLATE.is_file():
            raise RuntimeError("Branding-Compose-Vorlage fehlt")
        if args.apply:
            compose_safety(EDGE, OVERLAY_TEMPLATE)
            apply_brand(WEB, changes, EDGE, OVERLAY_TEMPLATE)
        else:
            print("Web-Quellcode:", "Branding erforderlich" if changed
                  else "bereits AeroNexusAdvanced")
            print("NUR PRÜFUNG: keinerlei Dateien oder Container verändert")
            print("Nächster Schritt: python3 scripts/brand_cloud_server.py --apply")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError,
            KeyError, json.JSONDecodeError) as exc:
        # Never output interpolated docker config, shell .env, or Docker Env.
        kind = type(exc).__name__
        message = (str(exc) if not isinstance(exc, subprocess.CalledProcessError)
                   else "Docker-Konfiguration/Container nicht lesbar")
        print(f"BRANDING ABGEBROCHEN ({kind}): {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
