"""Read-only inventory of DJI Pilot 2 uploads in the local MinIO bucket.

Only object-list metadata is imported into a private SQLite index. The scanner
runs MinIO Client in the already-running MinIO container; credentials are read
inside that container and never emitted or passed on the host command line.
No MinIO write operation or download is performed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = PROJECT_ROOT / "var" / "dji-media-index.sqlite3"
CLOUD_ENV = PROJECT_ROOT / "cloud-server" / "edge" / ".env"
MINIO_CONTAINER = "aeronexusadvanced-cloud-minio-1"
EXTENSIONS = {
    "image": frozenset({".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic", ".avif"}),
    "raw": frozenset({".dng", ".cr2", ".nef", ".arw"}),
    "video": frozenset({".mp4", ".mov", ".insv", ".lrf", ".avi"}),
    "audio": frozenset({".wav", ".mp3", ".aac"}),
    "sidecar": frozenset({".srt", ".xmp"}),
}
KNOWN_TYPES = frozenset(EXTENSIONS)
BUCKET_PATTERN = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]\Z")


class MediaIndexError(ValueError):
    """Expected, non-sensitive indexing or index-read failure."""


def bucket_from_cloud_env(path: Path = CLOUD_ENV) -> str:
    """Read only MINIO_BUCKET; never execute or print the secrets in .env."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise MediaIndexError("Cloud-Server-Konfiguration nicht lesbar") from exc
    matches = [line.split("=", 1)[1].strip().strip("'\"")
               for line in lines if re.match(r"^\s*MINIO_BUCKET\s*=", line)]
    if len(matches) != 1 or not BUCKET_PATTERN.fullmatch(matches[0]):
        raise MediaIndexError("MINIO_BUCKET fehlt oder ist ungültig")
    return matches[0]


def classify(key: str) -> tuple[str, str, str] | None:
    if not isinstance(key, str) or not key or len(key) > 4096 or "\x00" in key:
        return None
    name = key.rsplit("/", 1)[-1]
    if not name:
        return None
    ext = Path(name).suffix.lower()
    for kind, suffixes in EXTENSIONS.items():
        if ext in suffixes:
            return kind, ext, name[:512]
    return None


def media_row(entry: dict, bucket: str) -> dict | None:
    """Validate the subset of mc ls --recursive --json output we persist."""
    if not isinstance(entry, dict):
        raise MediaIndexError("Ungültige MinIO-Antwort")
    if entry.get("status") != "success":
        raise MediaIndexError("MinIO meldet einen Listenfehler")
    if entry.get("type") not in ("file", "object"):
        return None
    key = entry.get("key")
    category = classify(key)
    if category is None:
        return None
    size = entry.get("size")
    if type(size) is not int or not 0 <= size <= 2**63 - 1:
        raise MediaIndexError("Ungültige Objektgröße von MinIO")
    modified = entry.get("lastModified") or entry.get("last_modified")
    if not isinstance(modified, str) or len(modified) > 64:
        raise MediaIndexError("Ungültiges Änderungsdatum von MinIO")
    etag = entry.get("etag") or ""
    if not isinstance(etag, str) or len(etag) > 160:
        raise MediaIndexError("Ungültiger ETag von MinIO")
    kind, extension, name = category
    stable_id = hashlib.sha256((bucket + "\0" + key).encode("utf-8")).hexdigest()
    return dict(id=stable_id, bucket=bucket, object_key=key, name=name,
                kind=kind, extension=extension, size_bytes=size,
                last_modified=modified, etag=etag)


# Read-only shell commands. mktemp config exists only inside the container and
# is removed when the command exits. Docker arguments contain no passwords.
_MC_LIST = r'''
set -eu
cfg="$(mktemp -d /tmp/an-media-mc-XXXXXXXX)"
trap 'rm -rf "$cfg"' EXIT
/usr/bin/mc --config-dir "$cfg" alias set local http://127.0.0.1:9000 \
  "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1
/usr/bin/mc --config-dir "$cfg" ls --recursive --json "local/$1"
'''


def list_minio(bucket: str):
    """Yield raw JSON entries from the live MinIO container, streaming."""
    if not BUCKET_PATTERN.fullmatch(bucket):
        raise MediaIndexError("Ungültiger Bucket-Name")
    try:
        proc = subprocess.Popen(
            ["docker", "exec", MINIO_CONTAINER, "/bin/sh", "-c",
             _MC_LIST, "aeronexus-media-index", bucket],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace")
    except OSError as exc:
        raise MediaIndexError("Docker nicht erreichbar") from exc
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if len(line) > 32768:
                raise MediaIndexError("Zu lange MinIO-Metadatenzeile")
            try:
                entry = json.loads(line)
            except ValueError as exc:
                raise MediaIndexError("Ungültiges MinIO-JSON") from exc
            yield entry
        rc = proc.wait()
        if rc != 0:
            # Do not include stderr: third-party tools may output credentials.
            raise MediaIndexError(f"MinIO-Liste fehlgeschlagen (Exitcode {rc})")
    finally:
        if proc.poll() is None:
            proc.terminate()
        if proc.stderr is not None:
            proc.stderr.close()
        if proc.stdout is not None:
            proc.stdout.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _create_schema(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS media (
        id TEXT PRIMARY KEY,
        bucket TEXT NOT NULL,
        object_key TEXT NOT NULL,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        extension TEXT NOT NULL,
        size_bytes INTEGER NOT NULL,
        last_modified TEXT NOT NULL,
        etag TEXT NOT NULL,
        first_seen_at TEXT NOT NULL,
        last_seen_scan TEXT NOT NULL,
        UNIQUE(bucket, object_key)
    );
    CREATE INDEX IF NOT EXISTS media_recent ON media(last_seen_scan, last_modified DESC);
    CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)


def index_entries(entries, bucket: str, db_path: Path = DEFAULT_DATABASE,
                  *, dry_run: bool = False, max_objects: int = 250000) -> dict:
    """Index an entire listing atomically; never remove stored objects.

    If the MinIO listing fails, the scan transaction rolls back and the
    previous successful index stays available.
    """
    if not BUCKET_PATTERN.fullmatch(bucket):
        raise MediaIndexError("Ungültiger Bucket-Name")
    if not isinstance(max_objects, int) or not 1 <= max_objects <= 1000000:
        raise MediaIndexError("Ungültiges Scan-Limit")
    when = datetime.now(timezone.utc).isoformat()
    scan_id = uuid.uuid4().hex
    counts = Counter()
    db = None
    try:
        if not dry_run:
            db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            old_umask = os.umask(0o077)
            try:
                db = sqlite3.connect(db_path, timeout=15)
            finally:
                os.umask(old_umask)
            os.chmod(db_path, 0o600)
            _create_schema(db)
            db.execute("BEGIN")
        for entry in entries:
            counts["seen"] += 1
            if counts["seen"] > max_objects:
                raise MediaIndexError("Scan-Limit überschritten; Index unverändert")
            row = media_row(entry, bucket)
            if row is None:
                counts["ignored"] += 1
                continue
            counts["media"] += 1
            counts[row["kind"]] += 1
            if db is None:
                continue
            previous = db.execute(
                "SELECT size_bytes, last_modified, etag FROM media WHERE id=?",
                (row["id"],)).fetchone()
            if previous is None:
                counts["new"] += 1
            elif previous != (row["size_bytes"], row["last_modified"], row["etag"]):
                counts["updated"] += 1
            else:
                counts["unchanged"] += 1
            db.execute("""
                INSERT INTO media
                  (id,bucket,object_key,name,kind,extension,size_bytes,
                   last_modified,etag,first_seen_at,last_seen_scan)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name,kind=excluded.kind,
                  extension=excluded.extension,size_bytes=excluded.size_bytes,
                  last_modified=excluded.last_modified,etag=excluded.etag,
                  last_seen_scan=excluded.last_seen_scan
                """, (row["id"], row["bucket"], row["object_key"], row["name"],
                      row["kind"], row["extension"], row["size_bytes"],
                      row["last_modified"], row["etag"], when, scan_id))
        if db is not None:
            db.execute("INSERT OR REPLACE INTO meta(name,value) VALUES('scan_id',?)",
                       (scan_id,))
            db.execute("INSERT OR REPLACE INTO meta(name,value) VALUES('scanned_at',?)",
                       (when,))
            db.commit()
    except BaseException:
        if db is not None:
            db.rollback()
        raise
    finally:
        if db is not None:
            db.close()
    return {**dict(counts), "dry_run": dry_run, "scanned_at": when,
            "seen": counts["seen"], "media": counts["media"],
            "new": counts["new"], "updated": counts["updated"],
            "unchanged": counts["unchanged"], "ignored": counts["ignored"]}


def _read_db(path: Path):
    if not path.is_file():
        return None
    try:
        return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    except sqlite3.Error as exc:
        raise MediaIndexError("Privater Medienindex nicht lesbar") from exc


def index_summary(path: Path = DEFAULT_DATABASE) -> dict:
    db = _read_db(path)
    if db is None:
        return {"state": "not_indexed", "total": 0, "total_bytes": 0,
                "kinds": {}, "scanned_at": None}
    try:
        meta = dict(db.execute("SELECT name,value FROM meta"))
        scan_id = meta.get("scan_id")
        if not scan_id:
            return {"state": "not_indexed", "total": 0, "total_bytes": 0,
                    "kinds": {}, "scanned_at": None}
        rows = db.execute(
            "SELECT kind,COUNT(*),COALESCE(SUM(size_bytes),0) FROM media "
            "WHERE last_seen_scan=? GROUP BY kind", (scan_id,)).fetchall()
        kinds = {kind: count for kind, count, _ in rows}
        return {"state": "ready", "total": sum(kinds.values()),
                "total_bytes": sum(size for _, _, size in rows),
                "kinds": kinds, "scanned_at": meta.get("scanned_at")}
    except sqlite3.Error as exc:
        raise MediaIndexError("Fehler beim Lesen des Medienindex") from exc
    finally:
        db.close()


def browse_media(path: Path = DEFAULT_DATABASE, *, kind: str | None = None,
                 query: str = "", limit: int = 50, offset: int = 0) -> dict:
    if kind is not None and kind not in KNOWN_TYPES:
        raise MediaIndexError("Unbekannte Medienart")
    if not 1 <= limit <= 100 or not 0 <= offset <= 1000000 or len(query) > 200:
        raise MediaIndexError("Ungültige Medienfilter")
    db = _read_db(path)
    if db is None:
        return {"state": "not_indexed", "total": 0, "items": [],
                "limit": limit, "offset": offset}
    try:
        scan_id_row = db.execute(
            "SELECT value FROM meta WHERE name='scan_id'").fetchone()
        scan_id = scan_id_row[0] if scan_id_row else ""
        where = "WHERE last_seen_scan=?"
        args = [scan_id]
        if kind:
            where += " AND kind=?"
            args.append(kind)
        if query:
            # LIKE escape: user-entered wildcard characters are literal.
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where += " AND name LIKE ? ESCAPE '\\'"
            args.append("%" + escaped + "%")
        total = db.execute("SELECT COUNT(*) FROM media " + where, args).fetchone()[0]
        rows = db.execute(
            "SELECT id,name,kind,extension,size_bytes,last_modified "
            "FROM media " + where + " ORDER BY last_modified DESC,id ASC "
            "LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
        items = [dict(zip(("id", "name", "kind", "extension",
                           "size_bytes", "uploaded_at"), row)) for row in rows]
        return {"state": "ready", "total": total, "items": items,
                "limit": limit, "offset": offset}
    except sqlite3.Error as exc:
        raise MediaIndexError("Fehler beim Lesen der Medienliste") from exc
    finally:
        db.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="DJI MinIO metadata index (read-only; no media downloads)")
    parser.add_argument("--apply", action="store_true",
                        help="Commit the scanned object metadata to private SQLite")
    parser.add_argument("--max-objects", type=int, default=250000)
    args = parser.parse_args(argv)
    try:
        bucket = bucket_from_cloud_env()
        result = index_entries(list_minio(bucket), bucket,
                               dry_run=not args.apply,
                               max_objects=args.max_objects)
    except MediaIndexError as exc:
        print("FEHLER:", exc, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not args.apply:
        print("Nur Vorprüfung. Für die Übernahme: --apply")
    else:
        print("Index aktualisiert. MinIO-Originaldateien unverändert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
