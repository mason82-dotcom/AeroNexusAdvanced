"""Private, bounded, read-only DJI HMS transition history.

Records only normalized HMS alarm metadata, never raw MQTT payloads or coordinates.
SQLite persistence survives service restarts. The MQTT thread never writes here:
CloudOsdIngest calls record_snapshot on the asyncio event-loop thread.
"""
from __future__ import annotations

from collections import deque
from itertools import islice
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3

from datetime import timezone


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("HMS receive time must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

MAX_EVENTS = 3000
EVENT_ACTIONS = frozenset(("appeared", "reappeared", "resolved", "updated", "observed"))
_VISIBLE = ("code", "device_domain", "level", "module", "message", "message_source")


def default_history_path() -> Path:
    raw = os.environ.get("AERONEXUS_HMS_HISTORY_PATH")
    return Path(raw).expanduser() if raw else (
        Path.home() / ".config" / "aeronexusadvanced" / "hms-history.sqlite3"
    )


def _identity(alert: dict) -> tuple[str, str]:
    return str(alert.get("code") or ""), str(alert.get("device_domain") or "")


class HmsHistory:
    """Last MAX_EVENTS HMS transitions; optional private SQLite persistence."""

    def __init__(self, path: Path | None = None, *, limit: int = MAX_EVENTS):
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise ValueError("Invalid HMS history retention")
        self.limit = limit
        self.path = Path(path) if path is not None else None
        self.events = deque(maxlen=limit)
        # Secondary references, not copies of events. Keep only retained entries.
        self._events_by_device: dict[tuple[str, str, str], deque[dict]] = {}
        self.storage_error = False
        self._last_action: dict[tuple[str, str, str, str, str], str] = {}
        if self.path is not None:
            try:
                self._load()
            except (OSError, ValueError, sqlite3.Error):
                # A bad disk must never disrupt the read-only MQTT feed.
                self.storage_error = True

    def _connect(self):
        assert self.path is not None
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError("HMS history symlink denied")
        self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if not self.path.exists():
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(fd)
        if self.path.is_symlink() or not self.path.is_file():
            raise ValueError("Invalid HMS history target")
        os.chmod(self.path, 0o600)
        conn = sqlite3.connect(self.path, timeout=3.0)
        conn.execute("""CREATE TABLE IF NOT EXISTS hms_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry TEXT NOT NULL
        )""")
        return conn

    def _load(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT entry FROM hms_history ORDER BY id DESC LIMIT ?", (self.limit,)
            ).fetchall()
        for (raw,) in reversed(rows):
            item = json.loads(raw)
            if not isinstance(item, dict) or item.get("action") not in EVENT_ACTIONS:
                raise ValueError("Invalid saved HMS history")
            self._remember(item)

    def _remember(self, entry: dict):
        # Keep the per-device index consistent with the bounded global deque,
        # including when restoring the last retained entries from SQLite.
        if len(self.events) == self.limit:
            expired = self.events[0]
            expired_key = (expired["provider"], expired["project_id"], expired["device_id"])
            device_entries = self._events_by_device[expired_key]
            device_entries.popleft()
            if not device_entries:
                del self._events_by_device[expired_key]
        self.events.append(entry)
        device_key = (entry["provider"], entry["project_id"], entry["device_id"])
        self._events_by_device.setdefault(device_key, deque()).append(entry)
        key = (*device_key, entry["code"], entry["device_domain"])
        self._last_action[key] = entry["action"]

    def _persist(self, items: list[dict]):
        if self.path is None or self.storage_error or not items:
            return
        try:
            with self._connect() as conn:
                conn.executemany(
                    "INSERT INTO hms_history(entry) VALUES (?)",
                    [(json.dumps(item, ensure_ascii=False, separators=(",", ":")),)
                     for item in items],
                )
                conn.execute(
                    """DELETE FROM hms_history WHERE id NOT IN (
                        SELECT id FROM hms_history ORDER BY id DESC LIMIT ?
                    )""", (self.limit,),
                )
        except (OSError, ValueError, sqlite3.Error):
            self.storage_error = True

    def record_snapshot(self, device_key: tuple, previous: tuple[dict, ...] | None,
                        current: tuple[dict, ...], observed_at: datetime,
                        source_timestamp_ms: int | None = None) -> None:
        """Append only state transitions after a validated, ordered HMS snapshot."""
        provider, project_id, device_id = device_key
        if not current and not previous:
            return
        before = {_identity(a): a for a in (previous or ())}
        after = {_identity(a): a for a in current}
        actions: list[tuple[str, dict]] = []
        for identity, alert in before.items():
            if identity not in after:
                actions.append(("resolved", alert))
        for identity, alert in after.items():
            if identity not in before:
                last = self._last_action.get((provider.value, project_id, device_id,
                                              identity[0], identity[1]))
                action = ("reappeared" if last == "resolved" else
                          "observed" if previous is None and last in (
                              "appeared", "reappeared", "observed", "updated") else
                          "appeared")
                actions.append((action, alert))
            elif any(alert.get(k) != before[identity].get(k) for k in ("level", "module")):
                actions.append(("updated", alert))

        entries = []
        for action, alert in actions:
            entry = {
                "provider": provider.value, "project_id": project_id,
                "device_id": device_id, "action": action,
                "observed_at": utc_iso(observed_at),
                "source_timestamp_ms": source_timestamp_ms,
                **{field: alert.get(field) for field in _VISIBLE},
            }
            entries.append(entry)
            self._remember(entry)
        self._persist(entries)

    def list_events(self, *, provider: str | None = None,
                    project_id: str | None = None, device_id: str | None = None,
                    limit: int = 50, offset: int = 0) -> dict:
        if type(limit) is not int or not 1 <= limit <= 200 or type(offset) is not int or offset < 0:
            raise ValueError("Invalid HMS history pagination")
        # The cockpit always supplies the complete device identity. Use the
        # retained per-device index rather than scanning unrelated events.
        if provider is not None and project_id is not None and device_id is not None:
            matched = self._events_by_device.get((provider, project_id, device_id), ())
            total = len(matched)
            page = list(islice(reversed(matched), offset, offset + limit))
        else:
            page = []
            total = 0
            end = offset + limit
            for item in reversed(self.events):
                if ((provider is not None and item["provider"] != provider)
                        or (project_id is not None and item["project_id"] != project_id)
                        or (device_id is not None and item["device_id"] != device_id)):
                    continue
                if offset <= total < end:
                    page.append(item)
                total += 1
        return {"total": total, "limit": limit, "offset": offset,
                "persistent": self.path is not None and not self.storage_error,
                "storage_error": self.storage_error,
                "events": page}
