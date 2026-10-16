#!/usr/bin/env python3
"""Safely STAGE the stopped legacy DJI Cloud API server under AeroNexusAdvanced.

This utility never starts/stops/removes containers, modifies the original,
rewrites DJI credentials, or deletes source data. Default is a read-only check.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

CORE = ("mysql", "redis", "emqx", "minio", "minio-init", "api", "control")
IMAGES = (
    "mysql:8.4.11",
    "redis:7.2.5",
    "emqx/emqx:5.8.6",
    "aeronexus/minio:RELEASE.2025-10-15T17-29-55Z-an1",
    "aeronexus/api:local",
    "aeronexus/control:local",
)
COPIES = (
    "edge",
    "api/docker",
    "api/patches",
    "control/docker",
    "control/patches",
    "telemetry/emqx",
    "evidence/docker/minio",
    "evidence/scripts/minio-init.sh",
    "fleet/sql",
)
REQUIRED = (
    "edge/.env",
    "edge/docker-compose.yml",
    "edge/runtime/upstream/backend",
    "edge/runtime/upstream/web",
    "edge/runtime/initdb",
    "edge/runtime/emqx/auth-bootstrap.csv",
    "edge/data/mysql",
    "edge/data/redis",
    "edge/data/emqx",
    "api/docker/application.yml",
    "telemetry/emqx/acl.conf",
    "evidence/scripts/minio-init.sh",
)
PROJECT = "aeronexusadvanced-cloud"
LEGACY_PREFIX = "aeronexus-edge-"
MARGIN_BYTES = 1024 ** 3


def under(path: Path, parent: Path) -> bool:
    """No string-prefix shortcuts: /aeronexus-old is not /aeronexus."""
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def minio_path(env_file: Path, old_edge: Path) -> tuple[Path, bool]:
    """Read only MINIO_DATA_DIR, never print or parse the secret values."""
    value = None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if re.match(r"\s*(?:export\s+)?MINIO_DATA_DIR\s*=", line):
            value = line.partition("=")[2].strip().strip("\"'")
    if not value:
        return (old_edge / "data/minio").resolve(), False
    # Shell substitutions do not have a safe unambiguous filesystem meaning.
    if "$" in value or "~" in value:
        raise RuntimeError("MINIO_DATA_DIR uses dynamic expansion; inspect locally")
    path = Path(value)
    path = path if path.is_absolute() else old_edge / path
    path = path.resolve()
    return path, not under(path, old_edge)


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, text=True, **kwargs)


def running_legacy_containers() -> tuple[str, ...]:
    result = run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True)
    return tuple(name for name in result.stdout.splitlines()
                 if name.startswith(LEGACY_PREFIX))


def other_project_containers() -> tuple[str, ...]:
    result = run(
        ["docker", "ps", "-a", "--filter",
         "label=com.docker.compose.project=" + PROJECT,
         "--format", "{{.Names}}"], capture_output=True)
    return tuple(name for name in result.stdout.splitlines() if name.strip())


def missing_images() -> tuple[str, ...]:
    result = []
    for image in IMAGES:
        status = subprocess.run(["docker", "image", "inspect", image],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                check=False)
        if status.returncode:
            result.append(image)
    return tuple(result)


def validate_source(source: Path, target: Path, template: Path) -> tuple[Path, bool]:
    if not source.is_dir():
        raise RuntimeError("Quellprojekt existiert nicht")
    if not target.parent.is_dir():
        raise RuntimeError("AeroNexusAdvanced-Verzeichnis existiert nicht")
    if under(target, source) or under(source, target) or target == source:
        raise RuntimeError("Quelle und Ziel dürfen nicht ineinander liegen")
    if not template.is_file():
        raise RuntimeError("Compose-Vorlage fehlt; zuerst AeroNexusAdvanced aktualisieren")
    for relative in REQUIRED:
        if not (source / relative).exists():
            raise RuntimeError(f"Notwendiger Pfad fehlt: {relative}")
    for relative in ("edge/data/mysql", "edge/data/redis", "edge/data/emqx"):
        if (source / relative).is_symlink():
            raise RuntimeError(f"Persistenter Datenpfad ist ein Symlink: {relative}")
    data_path, external = minio_path(source / "edge/.env", source / "edge")
    if not data_path.is_dir():
        raise RuntimeError("MinIO-Datenträger/Verzeichnis ist nicht gemountet")
    if under(data_path, source) and (source / "edge/data/minio").is_symlink():
        raise RuntimeError("MinIO-Daten sind ein Symlink; manuelle Migration nötig")
    return data_path, external


def estimate_bytes(source: Path, external_minio: bool) -> int:
    # sudo du makes the cold-copy estimate accurate for root-owned MySQL data.
    selected = [str(source / rel) for rel in COPIES if (source / rel).exists()]
    result = run(["sudo", "du", "-scb", "--", *selected], capture_output=True)
    size = int(result.stdout.splitlines()[-1].split()[0])
    return size


def copy_cold(source: Path, stage: Path) -> None:
    """rsync -a preserves the numeric owners/modes required by MySQL/EMQX."""
    for rel in COPIES:
        src = source / rel
        if not src.exists():
            # Runtime copy works without some optional source-only patch dirs.
            continue
        parent = stage / Path(rel).parent
        parent.mkdir(parents=True, exist_ok=True)
        run(["sudo", "rsync", "-a", "--", str(src), str(parent) + "/"])


def validate_compose(stage: Path, old_source: Path) -> None:
    """Compose JSON is secret-bearing: keep in RAM and print no environment."""
    edge = stage / "edge"
    result = run(
        ["docker", "compose", "-f", "compose.core.yaml", "config", "--format", "json"],
        cwd=edge, capture_output=True)
    parsed = json.loads(result.stdout)
    if parsed.get("name") != PROJECT:
        raise RuntimeError("Compose-Projektname stimmt nicht; Migration gestoppt")
    actual = set(parsed.get("services", {}))
    if actual != set(CORE):
        raise RuntimeError("Minimales Compose enthält unerwartete Dienste")
    for name, service in parsed["services"].items():
        for volume in service.get("volumes", ()):
            if volume.get("type") != "bind":
                continue
            location = volume.get("source")
            if isinstance(location, str) and under(Path(location), old_source):
                raise RuntimeError(
                    f"Docker-Mount von {name} zeigt noch ins alte Projekt")
    env = stage / "edge/.env"
    if (env.stat().st_mode & 0o077) != 0:
        raise RuntimeError("Kopierte .env muss Rechte 0600 besitzen")


def stage_migration(source: Path, target: Path, template: Path,
                    external_minio: bool) -> None:
    if target.exists() or target.is_symlink():
        raise RuntimeError("Ziel existiert bereits; niemals überschreiben")
    partial = target.with_name(target.name + ".partial")
    if partial.exists() or partial.is_symlink():
        raise RuntimeError("Unvollständiger Zielordner vorhanden; erst prüfen")
    active = running_legacy_containers()
    if active:
        raise RuntimeError("Alter Docker-Stack läuft; Kaltkopie verweigert: "
                           + ", ".join(active))
    existing = other_project_containers()
    if existing:
        raise RuntimeError("Neues Compose-Projekt hat bereits Container: "
                           + ", ".join(existing))
    missing = missing_images()
    if missing:
        raise RuntimeError("Benötigte lokale Docker-Images fehlen: "
                           + ", ".join(missing))
    if (source / "edge/docker-compose.override.yml").exists():
        raise RuntimeError("Legacy Compose Override vorhanden: TLS/Ports zuerst prüfen; "
                           "nicht stillschweigend eine andere Serverkonfiguration starten")
    needed = estimate_bytes(source, external_minio)
    free = shutil.disk_usage(target.parent).free
    if free < needed + MARGIN_BYTES:
        raise RuntimeError("Nicht genug freier Platz für die Kaltkopie und 1 GiB Reserve")
    print("Kaltkopie:", round(needed / 1024**3, 2), "GiB;",
          "frei:", round(free / 1024**3, 2), "GiB")
    partial.mkdir(mode=0o700)
    try:
        copy_cold(source, partial)
        # Compose only the seven essential, locally available services.
        shutil.copyfile(template, partial / "edge/compose.core.yaml")
        run(["sudo", "chmod", "600", str(partial / "edge/.env")])
        validate_compose(partial, source)
        if external_minio:
            print("Hinweis: Externer MinIO-Datenträger bleibt am bisherigen Mount.")
        partial.rename(target)
    except Exception:
        print("Kopie nicht abgeschlossen; Zwischenordner bleibt zur Prüfung: "
              + str(partial), file=sys.stderr)
        raise
    print("MIGRATION STAGED:", target)
    print("Original bleibt erhalten; alle Container bleiben gestoppt.")
    print("Nächster Schritt: Compose/Volume-Prüfung und gezielter manueller Start.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="store_true",
                        help="stopped legacy stack cold-copy to new project folder")
    parser.add_argument("--source", type=Path,
                        default=Path.home() / "Projekte/AeroNexus")
    parser.add_argument("--target", type=Path,
                        default=Path.home() / "Projekte/AeroNexusAdvanced/cloud-server")
    args = parser.parse_args(argv)
    source, target = args.source.expanduser().resolve(), args.target.expanduser()
    template = Path(__file__).resolve().parents[1] / "deploy/cloud-server/compose.core.yaml"
    try:
        data_path, external = validate_source(source, target, template)
        print("Quelle:", source)
        print("Ziel:", target)
        print("MinIO:", "externes Volume" if external else "im Quellprojekt")
        print("Legacy Container aktiv:", len(running_legacy_containers()))
        print("Benötigte Images fehlen:", len(missing_images()))
        if args.stage:
            stage_migration(source, target, template, external)
        else:
            print("NUR PRÜFUNG: Keine Dateien oder Container geändert.")
            print("Zur sicheren Kaltkopie: python3 scripts/migrate_cloud_server.py --stage")
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        # Our paths and validation messages only. Never show raw Compose
        # output: it can contain credentials or license material.
        print(f"Migration abgebrochen ({type(exc).__name__}): "
              + (str(exc) if not isinstance(exc, subprocess.CalledProcessError)
                 else "lokaler Docker/rsync/du-Befehl fehlgeschlagen"),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
