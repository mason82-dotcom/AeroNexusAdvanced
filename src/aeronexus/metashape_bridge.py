"""Bounded, read-only MinIO exports for the optional GeoSense Metashape worker.

The Pi never imports Metashape and never starts reconstruction. Packages contain
copies plus an independently written, pinned-source worker. No credentials or
object keys are included in manifests or API responses.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
from uuid import uuid4
from zipfile import ZIP_STORED, ZipFile

from .metashape_worker import (CHANNELS, MAX_BYTES, MAX_CAPTURES, MAX_FILE_BYTES, SCHEMA,
                               UPSTREAM_COMMIT, UPSTREAM_URL, _UUID, photo_name)
from .minio_media_index import DjiMediaChanged, DjiMediaError, read_indexed_object
from .multispectral import HEADER_BYTES, MultispectralError, MultispectralService, item_metadata
from .studio_workspace import WorkspaceError, _private_dir, _read_json, _write_json_atomic


MAX_PACKAGES = 3
PACKAGE_TTL = 3600
_EXPORT_LOCK = threading.BoundedSemaphore(1)
_BAND_NAMES = {"G": "Green", "R": "Red", "RE": "RedEdge", "NIR": "NIR"}
WARNINGS = [
    "Metashape-Python-Modul und aktivierte Professional-Lizenz auf einem geeigneten Arbeitsrechner erforderlich.",
    "Nur überlappende Bilder derselben Flugserie verwenden; mindestens drei Bilder garantieren keine Rekonstruktion.",
    "Originale enthalten ihre EXIF/XMP-Metadaten. Das Paket enthält keine MinIO-Zugangsdaten.",
    "MS-Rohbandmosaike sind weder kalibrierte Reflexion noch pixelgleich registrierte NDVI-Produkte.",
    "Gekacheltes GeoTIFF mit Übersichten ist ohne zusätzliche Validierung kein bestätigtes COG.",
]
PACKAGE_README = """AeroNexusAdvanced – optionaler Metashape-Arbeitsauftrag

1. ZIP auf dem Arbeitsrechner vollständig entpacken.
2. Metashape-Python-Modul installieren und Professional-Lizenz aktivieren.
   Zusätzlich wird PyYAML für den separat installierten GeoSense-Code benötigt.
3. GeoSense-Repository separat klonen und auf den im manifest.json genannten
   Commit auschecken (siehe docs/metashape-integration.md im AeroNexus-Repository).
4. Prüfung (startet keine Rekonstruktion):
   python worker.py --upstream /pfad/zu/metashape_ortho --gpu cpu
5. Verarbeitung ausdrücklich starten:
   python worker.py --upstream /pfad/zu/metashape_ortho --gpu cpu --run
   GPU-Optionen: cpu, 0, 1, all. Ergebnisse: results/results.json und GeoTIFFs.

worker.py verwendet die verifizierten GeoSense-Prozessorklassen und arbeitet nur
im neuen results-Ordner. Das ursprüngliche main.py wird nicht aufgerufen; es
verschiebt Dateien und benennt Eingaben um. Eingaben hier sind Arbeitskopien.
Bei einem Fehler gilt der Auftrag als fehlgeschlagen; Ergebnisse nicht als
vollständige Kartierung verwenden. Ein neuer Versuch benötigt z. B.
--output results-retry. Vorhandene Ergebnisse werden nicht überschrieben.

Multispektral: Original-Digitalwerte, keine Reflexionskalibrierung. Die Bänder
werden unabhängig rekonstruiert und sind keine validierte NDVI-Karte.
Nicht als radiometrische Thermografie verwenden. Keine bestätigten COGs.
Originale im MinIO bleiben unverändert. Das Archiv enthält Original-EXIF/XMP.
"""


class MetashapeExportError(ValueError):
    pass


class MetashapeExportBusy(MetashapeExportError):
    pass


class MetashapePackageNotFound(MetashapeExportError):
    pass


def _root(service: MultispectralService) -> Path:
    return _private_dir(service.media.root / "metashape_exports")


def _directory(service: MultispectralService, job_id: str) -> Path:
    if not isinstance(job_id, str) or not _UUID.fullmatch(job_id):
        raise MetashapePackageNotFound("Unknown Metashape package")
    path = _root(service) / job_id
    if path.is_symlink() or not path.is_dir() or path.stat().st_mode & 0o077:
        raise MetashapePackageNotFound("Unknown Metashape package")
    return path


def _purge_expired(root: Path) -> None:
    for path in root.iterdir():
        if (_UUID.fullmatch(path.name) and path.is_dir() and not path.is_symlink()
                and time.time() - path.stat().st_mtime > PACKAGE_TTL):
            shutil.rmtree(path)


def package_info(service: MultispectralService, job_id: str) -> dict:
    path = _directory(service, job_id)
    if time.time() - path.stat().st_mtime > PACKAGE_TTL:
        raise MetashapePackageNotFound("Metashape package expired; prepare it again")
    record = _read_json(path / "record.json")
    return record


def package_path(service: MultispectralService, job_id: str) -> Path:
    package_info(service, job_id)
    path = _directory(service, job_id) / "package.zip"
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise MetashapePackageNotFound("Unknown Metashape package")
    return path


def list_packages(service: MultispectralService) -> list[dict]:
    packages = []
    for path in _root(service).iterdir():
        if not _UUID.fullmatch(path.name):
            continue
        try:
            packages.append(package_info(service, path.name))
        except (MetashapePackageNotFound, WorkspaceError, OSError, ValueError):
            continue
    return sorted(packages, key=lambda p: p["created_at"], reverse=True)


def remove_package(service: MultispectralService, job_id: str) -> None:
    shutil.rmtree(_directory(service, job_id))


def _selection(service: MultispectralService, captures: list[str], mode: str) -> list[dict]:
    if mode not in CHANNELS:
        raise MetashapeExportError("Choose rgb or multispectral")
    if (not isinstance(captures, list) or not 3 <= len(captures) <= MAX_CAPTURES
            or any(not isinstance(c, str) or not _UUID.fullmatch(c) for c in captures)
            or len(set(captures)) != len(captures)):
        raise MetashapeExportError("Select 3–100 distinct captures from one flight")
    files, total = [], 0
    for capture_uuid in captures:
        capture = service.catalog.capture(capture_uuid)
        for channel in CHANNELS[mode]:
            source = capture["rgb"] if channel == "RGB" else capture["bands"].get(_BAND_NAMES[channel])
            if not source:
                raise MetashapeExportError(f"Selected capture is missing {channel}")
            record = service.media.get(source["id"])
            if record is None:
                raise DjiMediaChanged("Selected media is no longer indexed")
            if not 0 < record["size_bytes"] <= MAX_FILE_BYTES:
                raise MetashapeExportError("Selected image exceeds the 64 MiB per-file limit")
            total += record["size_bytes"]
            if total > MAX_BYTES:
                raise MetashapeExportError("Selected originals exceed the 4 GiB package limit")
            files.append({"record": record, "capture_uuid": capture_uuid, "channel": channel,
                          "path": photo_name(capture_uuid, channel)})
    return files


def prepare_package(service: MultispectralService, captures: list[str], mode: str) -> dict:
    if not _EXPORT_LOCK.acquire(blocking=False):
        raise MetashapeExportBusy("A Metashape package is being prepared; try again later")
    directory = None
    try:
        selected = _selection(service, captures, mode)
        root = _root(service)
        _purge_expired(root)
        if sum(1 for p in root.iterdir() if _UUID.fullmatch(p.name)) >= MAX_PACKAGES:
            raise MetashapeExportError("Three packages already retained; delete an old package first")
        total = sum(f["record"]["size_bytes"] for f in selected)
        if shutil.disk_usage(root).free < total + 256 * 1024 ** 2:
            raise MetashapeExportError("Insufficient disk space for package plus 256 MiB reserve")
        settings = service._settings_factory()
        client = service._client_factory(settings)
        job_id = uuid4().hex
        directory = root / job_id
        directory.mkdir(mode=0o700, exist_ok=False)
        manifest = {"schema": SCHEMA, "id": job_id, "mode": mode, "capture_uuids": captures,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "upstream": {"url": UPSTREAM_URL, "commit": UPSTREAM_COMMIT},
                    "radiometry": "uncalibrated_dn" if mode == "multispectral" else "rgb",
                    "warnings": WARNINGS, "files": []}
        archive = directory / "package.zip"
        fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as out, ZipFile(out, "w", compression=ZIP_STORED, allowZip64=True) as zipfile:
            for item in selected:
                record = item["record"]
                try:
                    data = read_indexed_object(record, settings, client, max_bytes=MAX_FILE_BYTES)
                except DjiMediaError:
                    raise
                except Exception as exc:
                    raise DjiMediaError("MinIO original unavailable") from exc
                meta = item_metadata(record["filename"], data[:HEADER_BYTES])
                if (not meta or meta["capture_uuid"] != item["capture_uuid"]
                        or (item["channel"] == "RGB" and meta["kind"] != "rgb")
                        or (item["channel"] != "RGB" and meta["band"] != _BAND_NAMES[item["channel"]])):
                    raise DjiMediaChanged("Capture metadata changed; reindex before export")
                zipfile.writestr(item["path"], data)
                manifest["files"].append({k: item[k] for k in ("path", "capture_uuid", "channel")}
                                        | {"size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            zipfile.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            zipfile.writestr("worker.py", Path(__file__).with_name("metashape_worker.py").read_bytes())
            zipfile.writestr("README.txt", PACKAGE_README)
        info = {"id": job_id, "mode": mode, "captures": len(captures), "files": len(selected),
                "size_bytes": archive.stat().st_size, "created_at": manifest["created_at"],
                "expires_in_seconds": PACKAGE_TTL, "warnings": WARNINGS,
                "download_url": f"/api/v1/multispectral/metashape/packages/{job_id}/file"}
        _write_json_atomic(directory / "record.json", info)
        return info
    except Exception:
        if directory is not None:
            shutil.rmtree(directory, ignore_errors=True)
        raise
    finally:
        _EXPORT_LOCK.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare copied originals for an external Metashape worker")
    parser.add_argument("--env-file", default=".env")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List multispectral captures and package modes")
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--capture", action="append", required=True)
    prepare.add_argument("--mode", choices=tuple(CHANNELS), default="rgb")
    prepare.add_argument("--output", type=Path, required=True, help="New ZIP path; never overwritten")
    args = parser.parse_args(argv)
    try:
        from dotenv import load_dotenv
        from .minio_media_index import DjiMediaIndex
        load_dotenv(args.env_file, override=False)
        service = MultispectralService(DjiMediaIndex())
        if args.command == "list":
            print(json.dumps({"captures": [{"capture_uuid": c["capture_uuid"], "captured_at": c["captured_at"],
                                            "rgb": bool(c["rgb"]), "bands": sorted(c["bands"])}
                                           for c in service.catalog.captures()]}))
            return 0
        if args.output.exists() or args.output.is_symlink():
            raise MetashapeExportError("Output already exists")
        info = prepare_package(service, args.capture, args.mode)
        try:
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as target, package_path(service, info["id"]).open("rb") as source:
                shutil.copyfileobj(source, target)
            print(json.dumps(info))
        finally:
            remove_package(service, info["id"])
        return 0
    except (DjiMediaError, MultispectralError, MetashapeExportError, WorkspaceError, OSError):
        print("Metashape export failed. Check selection, index, private workspace and disk space.",
              file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
