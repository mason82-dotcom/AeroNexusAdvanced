"""On-Pi workspace storage: permissions, persistence and bounded media."""
import json
import os
from pathlib import Path

import pytest

from aeronexus.studio_workspace import (
    Workspace, WorkspaceError, MAX_MEDIA_BYTES, safe_id,
)
from aeronexus.wpml_export import WaypointMission


def mission(name="Matrice 4T Plan"):
    return WaypointMission.model_validate({
        "name": name,
        "waypoints": [
            {"latitude": 49.12, "longitude": 8.5},
            {"latitude": 49.14, "longitude": 8.6},
        ],
    })


def test_mission_persists_and_updates_atomically(tmp_path):
    ws = Workspace(tmp_path / "private")
    one = ws.save_mission(mission())
    assert one["mission"]["name"] == "Matrice 4T Plan"
    assert len(ws.list_missions()) == 1
    assert ws.get_mission(one["id"]) == one
    another = Workspace(tmp_path / "private")
    saved = another.save_mission(mission("Inspektion West"), one["id"])
    assert saved["id"] == one["id"]
    assert another.get_mission(one["id"])["mission"]["name"] == "Inspektion West"
    assert len(ws.list_missions()) == 1
    ws.delete_mission(one["id"])
    assert ws.list_missions() == []


def test_private_workspace_and_media_permissions(tmp_path):
    ws = Workspace(tmp_path / "data")
    item = ws.save_mission(mission())
    assert ws.root.stat().st_mode & 0o077 == 0
    assert ws.missions_dir.stat().st_mode & 0o077 == 0
    assert (ws.missions_dir / (item["id"] + ".json")).stat().st_mode & 0o077 == 0
    media = ws.save_media(filename="thermal.jpg", mime="image/jpeg",
                          content=b"\xff\xd8\xff" + b"safe-photo-data")
    _, filepath = ws.get_media(media["id"])
    assert filepath.stat().st_mode & 0o077 == 0
    assert (ws.media_dir / (media["id"] + ".json")).stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("unsafe", ["../etc/passwd", "../", "", "abc", "A" * 36])
def test_invalid_workspace_ids_fail_closed(tmp_path, unsafe):
    ws = Workspace(tmp_path / "safe")
    with pytest.raises(WorkspaceError):
        ws.get_mission(unsafe)
    with pytest.raises(WorkspaceError):
        ws.get_media(unsafe)


def test_nonexistent_updates_and_deletes_do_not_create_items(tmp_path):
    ws = Workspace(tmp_path / "private")
    missing = "00000000-0000-4000-8000-000000000000"
    with pytest.raises(WorkspaceError, match="not found"):
        ws.save_mission(mission(), missing)
    with pytest.raises(WorkspaceError, match="not found"):
        ws.delete_mission(missing)
    assert ws.list_missions() == []


def test_media_upload_and_deletion(tmp_path):
    ws = Workspace(tmp_path / "private")
    content = b"\x89PNG\r\n\x1a\n" + b"fake-test-content"
    item = ws.save_media(filename="route.png", mime="image/png", content=content)
    assert item["name"] == "route.png"
    assert item["size_bytes"] == len(content)
    assert len(ws.list_media()) == 1
    metadata, path = Workspace(tmp_path / "private").get_media(item["id"])
    assert metadata == item
    assert path.read_bytes() == content
    ws.delete_media(item["id"])
    assert ws.list_media() == []
    assert not path.exists()


@pytest.mark.parametrize("filename,mime,content", [
    ("safe.html", "text/html", b"<script>alert(1)</script>"),
    ("false.jpg", "image/jpeg", b"<html>not a photo</html>"),
    ("wrong.mp4", "video/mp4", b"BAD!bad!"),
    ("../../", "image/jpeg", b"\xff\xd8\xffdata"),
    ("x.png", "image/png", b""),
    ("x.webp", "image/webp", b"RIFF1234NOPE"),
])
def test_invalid_media_is_rejected(tmp_path, filename, mime, content):
    ws = Workspace(tmp_path / "private")
    with pytest.raises(WorkspaceError):
        ws.save_media(filename=filename, mime=mime, content=content)
    assert ws.list_media() == []


def test_rejects_publicly_readable_root(tmp_path):
    root = tmp_path / "insecure"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o755)
    with pytest.raises(WorkspaceError, match="0700"):
        Workspace(root)


def test_upload_truncates_long_filenames(tmp_path):
    ws = Workspace(tmp_path / "safe")
    result = ws.save_media(filename="A" * 500 + ".jpg", mime="image/jpeg",
                           content=b"\xff\xd8\xffdata")
    assert len(result["name"]) == 120
    assert not (ws.media_dir / ("A" * 120)).exists()
