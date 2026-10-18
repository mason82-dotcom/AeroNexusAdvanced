#!/usr/bin/env python3
"""Validate local Markdown links in tracked documents without network access.

External URLs and in-page anchors are outside scope. Run from any directory:
python scripts/maintenance/check_markdown_links.py
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
INLINE_LINK = re.compile(r"\]\(([^)]+)\)")
SKIP_PREFIXES = ("https://", "http://", "mailto:", "data:", "#")


def tracked_markdown() -> list[Path]:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", "*.md"],
        check=True,
        capture_output=True,
    )
    return [ROOT / p.decode("utf-8") for p in proc.stdout.split(b"\0") if p]


def main() -> int:
    broken: list[str] = []
    files = tracked_markdown()
    for document in files:
        if not document.is_file():
            broken.append(f"{document.relative_to(ROOT)}: tracked file missing")
            continue
        content = document.read_text(encoding="utf-8")
        for match in INLINE_LINK.finditer(content):
            reference = match.group(1).strip()
            if reference.startswith(SKIP_PREFIXES):
                continue
            path = unquote(reference.split("#", 1)[0].split("?", 1)[0])
            if not path or path.startswith("/"):
                continue  # Pure anchor or host-absolute API path, not a repo file.
            target = (document.parent / path).resolve()
            if not target.is_relative_to(ROOT):
                broken.append(f"{document.relative_to(ROOT)} -> outside repository: {reference}")
            elif not target.exists():
                broken.append(f"{document.relative_to(ROOT)} -> {reference}")
    if broken:
        print("Broken local Markdown links:", file=sys.stderr)
        for issue in sorted(broken):
            print(f"  {issue}", file=sys.stderr)
        return 1
    print(f"OK: validated local Markdown links in {len(files)} tracked documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
