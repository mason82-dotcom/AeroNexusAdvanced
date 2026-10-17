"""Private on-Pi desktop planning workspace (missions and local media).

Not a DJI API client. All writes affect only ~/.local/share/aeronexusadvanced
(or AERONEXUS_WORKSPACE_DIR). No mission upload or drone-control capability.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import UUID, uuid4

from .wpml_export import WaypointMission
from .geo_planning import GeoObject


MAX_GEO_OBJECTS = 200
MAX_MISSIONS = 200
MAX_MEDIA = 500
MAX_MEDIA_BYTES = 25 * 1024 * 1024
MEDIA_TYPES = {
    "image/jpeg": ".jpg", "image/png": ".png",
    "image/webp": ".webp", "video/mp4": ".mp4",
}
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


class WorkspaceError(ValueError):
    pass


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not _UUID.fullmatch(value):
        raise WorkspaceError("Invalid workspace identifier")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise WorkspaceError("Invalid workspace identifier") from exc


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise WorkspaceError("Workspace permissions must be 0700 and not a symlink")
    return path


def _write_json_atomic(path: Path, data: dict) -> None:
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    if len(encoded) > 128 * 1024:
        raise WorkspaceError("Workspace record too large")
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _read_json(path: Path) -> dict:
    if path.is_symlink():
        raise WorkspaceError("Workspace entry must not be a symlink")
    if not path.is_file() or path.stat().st_size > 128 * 1024:
        raise WorkspaceError("Workspace item not found")
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise WorkspaceError("Invalid workspace item")
    return value


class Workspace:
    def __init__(self, root: Path | None = None):
        root = root or Path(os.environ.get(
            "AERONEXUS_WORKSPACE_DIR", "~/.local/share/aeronexusadvanced")).expanduser()
        self.root = _private_dir(root)
        self.missions_dir = _private_dir(self.root / "missions")
        self.media_dir = _private_dir(self.root / "media")
        self.geo_dir = _private_dir(self.root / "geo_objects")

    def _mission_path(self, item_id: str) -> Path:
        return self.missions_dir / (safe_id(item_id) + ".json")

    def list_missions(self) -> list[dict]:
        result = []
        for path in list(self.missions_dir.glob("*.json"))[:MAX_MISSIONS + 1]:
            try:
                item = _read_json(path)
                mission = WaypointMission.model_validate(item["mission"])
                result.append({"id": item["id"], "name": mission.name,
                               "drone_model": mission.drone_model,
                               "waypoints": len(mission.waypoints),
                               "updated_at": item["updated_at"]})
            except (KeyError, ValueError, OSError, json.JSONDecodeError):
                continue
        return sorted(result, key=lambda x: x["updated_at"], reverse=True)[:MAX_MISSIONS]

    def save_mission(self, mission: WaypointMission, item_id: str | None = None) -> dict:
        if item_id is None:
            if len(list(self.missions_dir.glob("*.json"))) >= MAX_MISSIONS:
                raise WorkspaceError("Maximum number of missions reached")
            item_id = str(uuid4())
        else:
            path = self._mission_path(item_id)
            if not path.is_file() or path.is_symlink():
                raise WorkspaceError("Mission not found")
        record = {"id": item_id, "updated_at": now_utc(), "mission": mission.model_dump()}
        _write_json_atomic(self._mission_path(item_id), record)
        return record

    def get_mission(self, item_id: str) -> dict:
        record = _read_json(self._mission_path(item_id))
        record["mission"] = WaypointMission.model_validate(record["mission"]).model_dump()
        return record

    def delete_mission(self, item_id: str) -> None:
        path = self._mission_path(item_id)
        if not path.is_file() or path.is_symlink():
            raise WorkspaceError("Mission not found")
        path.unlink()

    def _geo_path(self, item_id: str) -> Path:
        return self.geo_dir / (safe_id(item_id) + ".json")

    def list_geo_objects(self) -> list[dict]:
        result = []
        for path in list(self.geo_dir.glob("*.json"))[:MAX_GEO_OBJECTS+1]:
            try:
                item = _read_json(path)
                item["object"] = GeoObject.model_validate(item["object"]).model_dump()
                result.append(item)
            except (KeyError, ValueError, OSError, json.JSONDecodeError):
                continue
        return sorted(result,key=lambda x:x["updated_at"],reverse=True)[:MAX_GEO_OBJECTS]

    def save_geo_object(self, obj: GeoObject, item_id: str | None = None) -> dict:
        if item_id is None:
            if len(list(self.geo_dir.glob("*.json"))) >= MAX_GEO_OBJECTS:
                raise WorkspaceError("Maximum geo objects reached")
            item_id = str(uuid4())
        else:
            path = self._geo_path(item_id)
            if not path.is_file() or path.is_symlink():
                raise WorkspaceError("Geo object not found")
        record = {"id":item_id,"updated_at":now_utc(),"object":obj.model_dump()}
        _write_json_atomic(self._geo_path(item_id),record)
        return record

    def delete_geo_object(self,item_id:str)->None:
        path=self._geo_path(item_id)
        if not path.is_file() or path.is_symlink():
            raise WorkspaceError("Geo object not found")
        path.unlink()

    def _media_metadata_path(self, item_id: str) -> Path:
        return self.media_dir / (safe_id(item_id) + ".json")

    def list_media(self) -> list[dict]:
        result = []
        for path in list(self.media_dir.glob("*.json"))[:MAX_MEDIA + 1]:
            try:
                m = _read_json(path)
                if m.get("mime") in MEDIA_TYPES and self._media_data_path(m["id"], m["mime"]).is_file():
                    result.append(m)
            except (ValueError, OSError, KeyError, json.JSONDecodeError):
                continue
        return sorted(result, key=lambda x: x["created_at"], reverse=True)[:MAX_MEDIA]

    def _media_data_path(self, item_id: str, mime: str) -> Path:
        if mime not in MEDIA_TYPES:
            raise WorkspaceError("Unsupported media format")
        return self.media_dir / (safe_id(item_id) + MEDIA_TYPES[mime])

    @staticmethod
    def valid_magic(mime: str, content: bytes) -> bool:
        if mime == "image/jpeg":
            return content.startswith(b"\xff\xd8\xff")
        if mime == "image/png":
            return content.startswith(b"\x89PNG\r\n\x1a\n")
        if mime == "image/webp":
            return content[:4] == b"RIFF" and content[8:12] == b"WEBP"
        if mime == "video/mp4":
            return content[4:8] == b"ftyp" and content[8:12] not in (b"heic", b"heix")
        return False

    def save_media(self, *, filename: str, mime: str, content: bytes) -> dict:
        if mime not in MEDIA_TYPES or not self.valid_magic(mime, content):
            raise WorkspaceError("Unsupported or invalid media format")
        if not content or len(content) > MAX_MEDIA_BYTES:
            raise WorkspaceError("Media file must be 1 byte to 25 MiB")
        if len(list(self.media_dir.glob("*.json"))) >= MAX_MEDIA:
            raise WorkspaceError("Maximum number of media items reached")
        name = filename.replace("\\", "/").split("/")[-1].strip()[:120]
        if not name or any(ord(char) < 32 for char in name):
            raise WorkspaceError("Invalid media filename")
        item_id = str(uuid4())
        path = self._media_data_path(item_id, mime)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
            data = {"id": item_id, "name": name, "mime": mime,
                    "size_bytes": len(content), "created_at": now_utc(),
                    "notes": "", "latitude": None, "longitude": None}
            _write_json_atomic(self._media_metadata_path(item_id), data)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return data

    def get_media(self, item_id: str) -> tuple[dict, Path]:
        meta = _read_json(self._media_metadata_path(item_id))
        data_path = self._media_data_path(item_id, meta["mime"])
        if not data_path.is_file() or data_path.is_symlink():
            raise WorkspaceError("Media not found")
        return meta, data_path

    def update_media_georef(self, item_id: str, *, latitude: float | None,
                            longitude: float | None, heading_deg: float | None,
                            pitch_deg: float | None, roll_deg: float | None,
                            altitude_m: float | None, captured_at: str | None,
                            notes: str) -> dict:
        meta, _ = self.get_media(item_id)
        meta.update(latitude=latitude,longitude=longitude,
                    heading_deg=heading_deg,pitch_deg=pitch_deg,
                    roll_deg=roll_deg,altitude_m=altitude_m,
                    captured_at=captured_at,notes=notes)
        _write_json_atomic(self._media_metadata_path(item_id),meta)
        return meta

    def delete_media(self, item_id: str) -> None:
        meta, path = self.get_media(item_id)
        path.unlink()
        self._media_metadata_path(item_id).unlink()
