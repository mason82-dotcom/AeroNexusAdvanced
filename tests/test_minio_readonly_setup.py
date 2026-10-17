"""Verify provisioning never contacts real MinIO or prints credentials."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import stat
import sys

import pytest
from dotenv import dotenv_values


def load_script():
    source = (Path(__file__).resolve().parents[1] /
              "scripts/pi/configure_minio_readonly.py")
    spec = importlib.util.spec_from_file_location("configure_minio_readonly", source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def private_file(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o600)


def test_new_reader_has_scoped_policy_private_settings_and_no_root_leak(
        tmp_path, monkeypatch, capsys):
    mod = load_script()
    root = tmp_path / "project"
    private_file(root / ".env", "AERONEXUS_STATUS_TOKEN=existing-private-token\n")
    private_file(root / "cloud-server/edge/.env",
                 "MINIO_ROOT_USER=rootuser\n"
                 "MINIO_ROOT_PASSWORD='p!:@ss word'\nMINIO_BUCKET=dji-cloud\n")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        assert kwargs["env"]["MC_HOST_anxadmin"].startswith("http://rootuser:")
        assert "@127.0.0.1:9000" in kwargs["env"]["MC_HOST_anxadmin"]
        assert kwargs["env"]["MC_CONFIG_DIR"]
        assert kwargs["stdout"] is not None and kwargs["stderr"] is not None
        return SimpleNamespace(returncode=0)

    class MockMinio:
        def __init__(self, endpoint, access_key, secret_key, secure):
            assert endpoint == "127.0.0.1:9000"
            assert access_key.startswith("anxmedia") and len(access_key) <= 20
            assert len(secret_key) >= 40 and not secure
        def list_objects(self, bucket, recursive):
            assert bucket == "dji-cloud" and recursive is True
            return iter([SimpleNamespace(object_name="photo/DJI_001.JPG")])
        def stat_object(self, bucket, key):
            assert key == "photo/DJI_001.JPG"

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setitem(sys.modules, "minio", SimpleNamespace(Minio=MockMinio))
    result = mod.configure(root, "/fake/mc")
    assert "restart" in result
    assert len(calls) == 3
    assert calls[0][0][1:5] == ["admin", "policy", "create", "anxadmin"]
    assert calls[1][0][1:5] == ["admin", "user", "add", "anxadmin"]
    assert calls[2][0][1:5] == ["admin", "policy", "attach", "anxadmin"]
    user = calls[1][0][5]
    assert calls[2][0][-2:] == ["--user", user]
    policy = calls[0][0][5]
    assert calls[2][0][5] == policy
    settings = dotenv_values(root / ".env")
    assert settings["AERONEXUS_MINIO_ACCESS_KEY"] == user
    assert settings["AERONEXUS_MINIO_BUCKET"] == "dji-cloud"
    assert settings["AERONEXUS_STATUS_TOKEN"] == "existing-private-token"
    assert stat.S_IMODE((root / ".env").stat().st_mode) == 0o600
    assert "rootuser" not in (root / ".env").read_text()
    assert "p!:@ss" not in (root / ".env").read_text()
    assert "anxmedia" not in capsys.readouterr().out
    with pytest.raises(RuntimeError, match="already exist"):
        mod.configure(root, "/fake/mc")
    assert len(calls) == 3


def test_refuses_non_private_and_missing_configuration(tmp_path, monkeypatch):
    mod = load_script()
    root = tmp_path / "project"
    private_file(root / "cloud-server/edge/.env",
                 "MINIO_ROOT_USER=root\nMINIO_ROOT_PASSWORD=secret\nMINIO_BUCKET=dji-cloud\n")
    private_file(root / ".env", "")
    (root / ".env").chmod(0o644)
    with pytest.raises(RuntimeError, match="0600"):
        mod.configure(root, "/fake/mc")
    (root / ".env").chmod(0o600)
    (root / "cloud-server/edge/.env").write_text(
        "MINIO_ROOT_USER=root\nMINIO_ROOT_PASSWORD=secret\nMINIO_BUCKET=other\n")
    with pytest.raises(RuntimeError, match="dji-cloud"):
        mod.configure(root, "/fake/mc")


def test_refuses_existing_partial_configuration(tmp_path):
    mod = load_script()
    root = tmp_path / "project"
    private_file(root / ".env",
                 "AERONEXUS_MINIO_ACCESS_KEY=already-present\n")
    private_file(root / "cloud-server/edge/.env",
                 "MINIO_ROOT_USER=root\nMINIO_ROOT_PASSWORD=secret\nMINIO_BUCKET=dji-cloud\n")
    with pytest.raises(RuntimeError, match="already exist"):
        mod.configure(root, "/fake/mc")
