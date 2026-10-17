"""Pilot-2 local Cloud API wayline metadata, fixed loopback origin, GET only.

The interactive CLI alone can log in to obtain a session. The web adapter
never logs in, refreshes tokens, follows downloads or issues flight commands.
"""
import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from getpass import getpass
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
from uuid import UUID

import httpx


ORIGIN = "http://127.0.0.1:6789"
PAGE_SIZE = 50
MAX_PAGES = 10
MAX_BODY = 1024 * 1024
CACHE_SECONDS = 30
TEMPLATE_TYPES = {0: "waypoint", 1: "mapping_2d", 2: "mapping_3d", 3: "mapping_strip"}


class LocalWaylineError(ValueError):
    """Only a fixed, non-sensitive status code may leave this module."""


@dataclass(frozen=True)
class Credentials:
    workspace_id: str
    access_token: str = field(repr=False)

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict):
            raise LocalWaylineError("configuration_error")
        try:
            workspace = str(UUID(value["workspace_id"]))
            token = value["access_token"]
        except (KeyError, ValueError, TypeError, AttributeError):
            raise LocalWaylineError("configuration_error") from None
        if not isinstance(token, str) or not re.fullmatch(r"[\x21-\x7e]{16,8192}", token):
            raise LocalWaylineError("configuration_error")
        return cls(workspace, token)


def credentials_path() -> Path:
    return Path(os.environ.get("AERONEXUS_LOCAL_WAYLINES_FILE",
                               "~/.config/aeronexusadvanced/pilot-waylines.json")).expanduser()


def load_credentials(path: Path) -> Credentials | None:
    """No symlink, FIFO, foreign owner or group/world-readable credential file."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError:
        raise LocalWaylineError("configuration_error") from None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 16384):
            raise LocalWaylineError("configuration_error")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(16385)
        if len(data) > 16384:
            raise LocalWaylineError("configuration_error")
        return Credentials.parse(json.loads(data))
    except (OSError, ValueError, UnicodeError):
        raise LocalWaylineError("configuration_error") from None
    finally:
        os.close(fd)


async def _json_response(response: httpx.Response) -> dict:
    if response.status_code in (401, 403):
        raise LocalWaylineError("authentication_required")
    if response.status_code != 200:
        raise LocalWaylineError("upstream_error")
    body = bytearray()
    async for chunk in response.aiter_bytes():
        if len(body) + len(chunk) > MAX_BODY:
            raise LocalWaylineError("invalid_response")
        body.extend(chunk)
    try:
        result = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        raise LocalWaylineError("invalid_response") from None
    if not isinstance(result, dict) or type(result.get("code")) is not int:
        raise LocalWaylineError("invalid_response")
    if result["code"] != 0:
        raise LocalWaylineError("business_error")
    if not isinstance(result.get("data"), dict):
        raise LocalWaylineError("invalid_response")
    return result["data"]


def _bounded_int(value, maximum):
    return value if type(value) is int and 0 <= value <= maximum else None


def _route(row: dict) -> dict:
    if not isinstance(row, dict):
        raise LocalWaylineError("invalid_response")
    try:
        route_id = str(UUID(row["id"]))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise LocalWaylineError("invalid_response") from None
    name = row.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        raise LocalWaylineError("invalid_response")
    model = row.get("drone_model_key")
    if not isinstance(model, str) or not re.fullmatch(r"0-[0-9]{1,5}-[0-9]{1,5}", model):
        model = None  # unknown format cannot establish aircraft compatibility
    codes = row.get("template_types")
    if not isinstance(codes, list) or len(codes) > 16 or any(_bounded_int(c, 255) is None for c in codes):
        raise LocalWaylineError("invalid_response")
    return {"wayline_id": route_id, "name": name.strip(),
            "device_model_key": model,
            "template_types": [TEMPLATE_TYPES[c] for c in codes if c in TEMPLATE_TYPES],
            "template_type_codes": codes,
            "updated_at_ms": _bounded_int(row.get("update_time"), 253402300799999)}


async def read_waylines(credentials: Credentials, *, transport=None) -> dict:
    """Bounded ordered pagination. No signed links, users, S3 keys or positions."""
    path = f"/wayline/api/v1/workspaces/{credentials.workspace_id}/waylines"
    routes, seen, total, returned_size = [], set(), None, None
    async with httpx.AsyncClient(base_url=ORIGIN, timeout=5, trust_env=False,
                                 follow_redirects=False, transport=transport) as client:
        for page in range(1, MAX_PAGES + 1):
            async with client.stream("GET", path, headers={"x-auth-token": credentials.access_token},
                                     params={"page": page, "page_size": PAGE_SIZE,
                                             "order_by": "create_time asc"}) as response:
                data = await _json_response(response)
            items, pagination = data.get("list"), data.get("pagination")
            if not isinstance(items, list) or len(items) > PAGE_SIZE or not isinstance(pagination, dict):
                raise LocalWaylineError("invalid_response")
            count = _bounded_int(pagination.get("total"), 10000000)
            size = _bounded_int(pagination.get("page_size"), PAGE_SIZE)
            if (count is None or not size or type(pagination.get("page")) is not int
                    or pagination["page"] != page or len(items) > size):
                raise LocalWaylineError("invalid_response")
            if (total is not None and total != count) or (returned_size is not None and returned_size != size):
                raise LocalWaylineError("inventory_changed")
            total, returned_size = count, size
            for item in items:
                route = _route(item)
                if route["wayline_id"] in seen:
                    raise LocalWaylineError("inventory_changed")
                seen.add(route["wayline_id"])
                routes.append(route)
            if len(routes) > total or (len(routes) < total and len(items) < size):
                raise LocalWaylineError("invalid_response")
            if len(routes) == total:
                break
        return {"state": "connected", "workspace_id": credentials.workspace_id,
                "waylines": routes, "reported_total": total,
                "max_pages": MAX_PAGES, "requested_page_size": PAGE_SIZE,
                "pagination_complete": len(routes) == total,
                "snapshot_consistency_verified": False,
                "updated_at": datetime.now(timezone.utc).isoformat()}


class LocalWaylineReader:
    """On-demand cache; failure clears routes, old successes cannot look current."""
    def __init__(self):
        self._lock = asyncio.Lock()
        self._credentials = None
        self._until = 0.0
        self._result = None

    async def read(self) -> dict:
        async with self._lock:
            try:
                credentials = load_credentials(credentials_path())
            except LocalWaylineError:
                self._credentials, self._result = None, None
                return {"state": "configuration_error", "waylines": []}
            if credentials is None:
                self._credentials, self._result = None, None
                return {"state": "not_configured", "waylines": []}
            if credentials == self._credentials and time.monotonic() < self._until:
                return self._result
            try:
                result = await asyncio.wait_for(read_waylines(credentials), timeout=15)
            except LocalWaylineError as exc:
                result = {"state": str(exc), "waylines": []}
            except (httpx.HTTPError, OSError, TimeoutError):
                result = {"state": "unavailable", "waylines": []}
            self._credentials = credentials
            self._until = time.monotonic() + CACHE_SECONDS
            self._result = result
            return result


async def login(username: str, password: str, flag: int, *, transport=None) -> Credentials:
    """Explicit terminal setup only, never called by the web application."""
    async with httpx.AsyncClient(base_url=ORIGIN, timeout=5, trust_env=False,
                                 follow_redirects=False, transport=transport) as client:
        async with client.stream("POST", "/manage/api/v1/login",
                                 json={"username": username, "password": password, "flag": flag}) as response:
            data = await _json_response(response)
    return Credentials.parse(data)


def save_credentials(path: Path, credentials: Credentials) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.parent.stat()
    if path.parent.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise LocalWaylineError("configuration_error")
    fd, temporary = tempfile.mkstemp(prefix=".pilot-waylines-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"workspace_id": credentials.workspace_id,
                       "access_token": credentials.access_token}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lokale Pilot-2-Waylines lesen; keine Flugbefehle.")
    parser.add_argument("--configure", action="store_true", help="Am lokalen Cloud-Server anmelden und Sitzung privat speichern")
    parser.add_argument("--account", choices=("web", "pilot"), default="web")
    args = parser.parse_args()
    try:
        if args.configure:
            username = input("Lokaler Cloud-Benutzername: ").strip()
            password = getpass("Lokales Cloud-Passwort (wird nicht gespeichert): ")
            credentials = asyncio.run(login(username, password, 1 if args.account == "web" else 2))
            # Verify the scoped GET before replacing any previously working file.
            asyncio.run(asyncio.wait_for(read_waylines(credentials), timeout=15))
            save_credentials(credentials_path(), credentials)
            print("Lokale Wayline-Anbindung eingerichtet; Sitzung privat gespeichert.")
        else:
            result = asyncio.run(LocalWaylineReader().read())
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["state"] == "connected" else 1
    except (LocalWaylineError, httpx.HTTPError, OSError, TimeoutError, EOFError):
        print("Lokale Cloud-Einrichtung fehlgeschlagen. Server, Kontotyp, Anmeldung und private Dateirechte am Pi prüfen; keine Zugangsdaten im Chat senden.")
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
