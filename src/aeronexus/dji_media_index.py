"""Compatibility API for the Phase-20 page, backed by the shared Studio index.

Scanning is delegated to minio_media_index and its dedicated read-only account.
The former var/dji-media-index.sqlite3 is never opened or modified.
"""
from .minio_media_index import DjiMediaIndex, DjiMediaError, media_kind

MediaIndexError = DjiMediaError


def index_summary() -> dict:
    return DjiMediaIndex().summary()


def browse_media(*, kind=None, query="", limit=50, offset=0) -> dict:
    result = DjiMediaIndex().list(query=query, limit=limit, offset=offset, kind=kind)
    return {"state": "ready" if result["last_scanned_at"] else "not_indexed",
            "total": result["total"], "limit": limit, "offset": offset,
            "items": [{"id": row["id"], "name": row["name"],
                       "kind": media_kind(row["mime"]),
                       "extension": "." + row["name"].rsplit(".", 1)[-1].lower(),
                       "size_bytes": row["size_bytes"],
                       "uploaded_at": row["modified_at"]} for row in result["media"]]}


def main(argv=None) -> int:
    """Preserve the old CLI's dry-run default and explicit --apply contract."""
    import argparse
    from .minio_media_index import main as scan_main
    parser = argparse.ArgumentParser(description="Legacy entry point; use aeronexus.minio_media_index")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-objects", type=int, default=250000)
    args = parser.parse_args(argv)
    forwarded = ["--max-objects", str(args.max_objects)]
    if not args.apply:
        forwarded.append("--dry-run")
    return scan_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
