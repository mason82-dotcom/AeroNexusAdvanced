"""Read-only, idempotent DJI MinIO object indexing.

The index contains object metadata only. Objects are never downloaded,
renamed, copied or deleted during a scan. Run the scan explicitly on the Pi.
This module does not access DJI APIs and cannot issue flight commands.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
from urllib.parse import urlsplit
from uuid import uuid4

from .studio_workspace import Workspace, WorkspaceError


# These are catalogue formats, not an assertion that each can be shown in a
# browser. Raw/DNG/TIFF, subtitle and large video objects remain index-only.
DJI_MIME_BY_EXT = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".thm": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
    ".dng": "image/x-adobe-dng", ".tif": "image/tiff", ".tiff": "image/tiff",
    ".mp4": "video/mp4", ".mov": "video/quicktime",
    ".lrf": "application/octet-stream", ".srt": "text/plain",
}
BROWSER_PREVIEW_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_BROWSER_PREVIEW_BYTES = 32 * 1024 * 1024
_ID_RE = re.compile(r"[0-9a-f]{64}\Z")
_BUCKET_RE = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]\Z")
DB_NAME = "dji_minio_media.sqlite3"


class DjiMediaError(ValueError):
    """Safe to show in diagnostics without revealing MinIO credentials."""


def media_id(bucket: str, key: str) -> str:
    return hashlib.sha256((bucket + "\0" + key).encode("utf-8")).hexdigest()


def classify(key: str) -> str | None:
    return DJI_MIME_BY_EXT.get(PurePosixPath(key).suffix.lower())


def _time(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class MinioMediaSettings:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool

    @classmethod
    def from_env(cls) -> "MinioMediaSettings":
        endpoint = os.getenv("AERONEXUS_MINIO_ENDPOINT", "http://127.0.0.1:9000").strip()
        access_key = os.getenv("AERONEXUS_MINIO_ACCESS_KEY", "")
        secret_key = os.getenv("AERONEXUS_MINIO_SECRET_KEY", "")
        bucket = os.getenv("AERONEXUS_MINIO_BUCKET", "dji-cloud").strip()
        if not access_key or not secret_key:
            raise DjiMediaError("MinIO read-only credentials are not configured")
        if not _BUCKET_RE.fullmatch(bucket):
            raise DjiMediaError("Invalid configured MinIO bucket")
        parts = urlsplit(endpoint)
        if (parts.scheme not in {"http", "https"} or not parts.hostname
                or parts.username or parts.password or parts.path not in ("", "/")
                or parts.query or parts.fragment):
            raise DjiMediaError("Invalid MinIO endpoint URL")
        try:
            port = parts.port
        except ValueError as exc:
            raise DjiMediaError("Invalid MinIO endpoint port") from exc
        host = parts.hostname
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower() == "localhost"
        if parts.scheme == "http" and not loopback:
            raise DjiMediaError("Non-loopback MinIO endpoints require HTTPS")
        if not 1 <= (port or (443 if parts.scheme == "https" else 80)) <= 65535:
            raise DjiMediaError("Invalid MinIO endpoint port")
        netloc = parts.netloc
        return cls(netloc, access_key, secret_key, bucket, parts.scheme == "https")


def minio_client(settings: MinioMediaSettings):
    """Import optional MinIO SDK only for an explicit network operation."""
    try:
        from minio import Minio
    except ImportError as exc:
        raise DjiMediaError("Install optional dependency: pip install -e '.[minio]'") from exc
    return Minio(settings.endpoint, access_key=settings.access_key,
                 secret_key=settings.secret_key, secure=settings.secure)


class DjiMediaIndex:
    def __init__(self, root: Path | None = None):
        self.root = Workspace(root).root
        self.path = self.root / DB_NAME

    def _connect(self, *, write: bool) -> sqlite3.Connection | None:
        if self.path.is_symlink():
            raise DjiMediaError("Refusing symlinked DJI media index")
        if not self.path.exists():
            if not write:
                return None
            try:
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(self.path, flags, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
        if not self.path.is_file() or self.path.stat().st_mode & 0o077:
            raise DjiMediaError("DJI media index must be a private 0600 file")
        if write:
            conn = sqlite3.connect(self.path, timeout=30)
        else:
            conn = sqlite3.connect("file:" + str(self.path) + "?mode=ro",
                                   uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        if write:
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("""CREATE TABLE IF NOT EXISTS media (
                id TEXT PRIMARY KEY,
                bucket TEXT NOT NULL,
                object_key TEXT NOT NULL,
                filename TEXT NOT NULL,
                mime TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                etag TEXT,
                modified_at TEXT,
                scan_marker TEXT NOT NULL,
                UNIQUE(bucket, object_key)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS scans (
                bucket TEXT PRIMARY KEY, completed_at TEXT NOT NULL,
                indexed INTEGER NOT NULL, added INTEGER NOT NULL,
                updated INTEGER NOT NULL, removed INTEGER NOT NULL
            )""")
        return conn

    def scan(self, client, bucket: str) -> dict:
        """Full paginated scan; prune stale index entries only on success.

        A list_objects failure rolls back all changes. Nothing is written to
        MinIO. Repeated scans are stable; replacement objects are updated.
        """
        if not _BUCKET_RE.fullmatch(bucket):
            raise DjiMediaError("Invalid configured MinIO bucket")
        db = self._connect(write=True)
        assert db is not None
        marker = uuid4().hex
        added = updated = unchanged = ignored = 0
        try:
            with db:
                for obj in client.list_objects(bucket, recursive=True):
                    key = getattr(obj, "object_name", None)
                    if not isinstance(key, str) or not key or len(key) > 2048:
                        ignored += 1
                        continue
                    if getattr(obj, "is_dir", False) or any(ord(c) < 32 for c in key):
                        ignored += 1
                        continue
                    mime = classify(key)
                    size = getattr(obj, "size", None)
                    if mime is None or not isinstance(size, int) or size < 0:
                        ignored += 1
                        continue
                    item_id = media_id(bucket, key)
                    values = (item_id, bucket, key, PurePosixPath(key).name[:240],
                              mime, size, getattr(obj, "etag", None),
                              _time(getattr(obj, "last_modified", None)), marker)
                    old = db.execute(
                        "SELECT mime,size_bytes,etag,modified_at FROM media WHERE id=?",
                        (item_id,)).fetchone()
                    if old is None:
                        added += 1
                    elif tuple(old) == (values[4], values[5], values[6], values[7]):
                        unchanged += 1
                    else:
                        updated += 1
                    db.execute("""INSERT INTO media
                        (id,bucket,object_key,filename,mime,size_bytes,etag,modified_at,scan_marker)
                        VALUES (?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(id) DO UPDATE SET
                        filename=excluded.filename,mime=excluded.mime,
                        size_bytes=excluded.size_bytes,etag=excluded.etag,
                        modified_at=excluded.modified_at,scan_marker=excluded.scan_marker""",
                        values)
                removed = db.execute(
                    "DELETE FROM media WHERE bucket=? AND scan_marker != ?",
                    (bucket, marker)).rowcount
                total = db.execute("SELECT COUNT(*) FROM media WHERE bucket=?",
                                   (bucket,)).fetchone()[0]
                completed = _time(datetime.now(timezone.utc))
                db.execute("""INSERT INTO scans
                    (bucket,completed_at,indexed,added,updated,removed)
                    VALUES (?,?,?,?,?,?)
                    ON CONFLICT(bucket) DO UPDATE SET
                    completed_at=excluded.completed_at,indexed=excluded.indexed,
                    added=excluded.added,updated=excluded.updated,removed=excluded.removed""",
                    (bucket, completed, total, added, updated, removed))
            return {"bucket": bucket, "indexed": total, "added": added,
                    "updated": updated, "unchanged": unchanged,
                    "removed_from_index": removed, "ignored": ignored,
                    "scanned_at": completed}
        finally:
            db.close()

    @staticmethod
    def _public(row: sqlite3.Row) -> dict:
        return {"id": row["id"], "name": row["filename"],
                "mime": row["mime"], "size_bytes": row["size_bytes"],
                "modified_at": row["modified_at"],
                "previewable": row["mime"] in BROWSER_PREVIEW_MIMES
                and row["size_bytes"] <= MAX_BROWSER_PREVIEW_BYTES}

    def list(self, *, query: str = "", limit: int = 100, offset: int = 0) -> dict:
        if not 1 <= limit <= 200 or not 0 <= offset <= 1_000_000 or len(query) > 120:
            raise DjiMediaError("Invalid DJI media catalogue pagination")
        db = self._connect(write=False)
        if db is None:
            return {"media": [], "total": 0, "last_scanned_at": None}
        try:
            where = ""
            args = []
            if query:
                escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                where = " WHERE filename LIKE ? ESCAPE '\\'"
                args = ["%" + escaped + "%"]
            count = db.execute("SELECT COUNT(*) FROM media" + where, args).fetchone()[0]
            media = db.execute("SELECT * FROM media" + where +
                               " ORDER BY modified_at DESC,id LIMIT ? OFFSET ?",
                               [*args, limit, offset]).fetchall()
            stamp = db.execute("SELECT MAX(completed_at) FROM scans").fetchone()[0]
            return {"media": [self._public(row) for row in media],
                    "total": count, "last_scanned_at": stamp}
        finally:
            db.close()

    def get(self, item_id: str) -> dict | None:
        if not _ID_RE.fullmatch(item_id):
            return None
        db = self._connect(write=False)
        if db is None:
            return None
        try:
            row = db.execute("SELECT * FROM media WHERE id=?", (item_id,)).fetchone()
            return dict(row) if row is not None else None
        finally:
            db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only DJI MinIO bucket index (no object modifications)")
    parser.add_argument("--env-file", default=".env",
                        help="Private gateway .env file; environment variables take precedence")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate settings and bucket access without changing the local index")
    args = parser.parse_args(argv)
    try:
        if args.env_file:
            # python-dotenv is already installed by pydantic-settings. Do not
            # print values or override existing explicitly exported settings.
            from dotenv import load_dotenv
            load_dotenv(args.env_file, override=False)
        settings = MinioMediaSettings.from_env()
        client = minio_client(settings)
        if args.dry_run:
            # This is a bucket metadata read, not a destructive S3 operation.
            client.stat_object(settings.bucket, "__aeronexus_nonexistent_probe__") if False else None
            iterator = client.list_objects(settings.bucket, recursive=True)
            first = next(iter(iterator), None)
            print(json.dumps({"bucket": settings.bucket, "read_access": "ok",
                              "first_object_exists": first is not None}))
            return 0
        report = DjiMediaIndex().scan(client, settings.bucket)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (DjiMediaError, WorkspaceError, OSError, sqlite3.Error) as exc:
        print("DJI media index error: " + str(exc).split("\n", 1)[0],
              file=__import__("sys").stderr)
        return 1
    except Exception:
        # MinIO SDK failures can include untrusted response details; never
        # reflect endpoint, object keys or access credentials into logs.
        print("DJI media index error: MinIO scan failed; index transaction rolled back",
              file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
