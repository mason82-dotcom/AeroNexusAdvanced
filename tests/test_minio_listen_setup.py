"""The event-policy provisioner uses the installed SDK's keyword-only API."""
import importlib.util
import inspect
from pathlib import Path

import pytest
from minio.minioadmin import MinioAdmin

from test_minio_readonly_setup import private_file


@pytest.fixture
def setup(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "scripts/pi/grant_minio_listen.py"
    spec = importlib.util.spec_from_file_location("grant_minio_listen", source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    private_file(tmp_path / ".env", "AERONEXUS_MINIO_ACCESS_KEY=reader\n"
                 "AERONEXUS_MINIO_SECRET_KEY=reader-secret\nAERONEXUS_MINIO_BUCKET=dji-cloud\n")
    private_file(tmp_path / "cloud-server/edge/.env", "MINIO_ROOT_USER=admin\n"
                 "MINIO_ROOT_PASSWORD=private-admin-secret\nMINIO_BUCKET=dji-cloud\n")
    checks = iter((False, True))
    monkeypatch.setattr(mod, "listen_allowed", lambda *a: next(checks))
    return mod, tmp_path


def test_keyword_constructor_and_additive_listen_policy(setup, monkeypatch):
    mod, root = setup
    calls = []
    signature = inspect.signature(MinioAdmin)
    class Admin:
        def policy_add(self, name, *, policy):
            calls.append(("add", name, policy))
        def attach_policy(self, policies, *, user):
            calls.append(("attach", policies, user))
    def factory(*args, **kwargs):
        signature.bind(*args, **kwargs)  # real SDK signature; rejects positional endpoint
        assert kwargs["endpoint"] == "127.0.0.1:9000" and kwargs["secure"] is False
        creds = kwargs["credentials"].retrieve()
        assert creds.access_key == "admin" and creds.secret_key == "private-admin-secret"
        return Admin()
    monkeypatch.setattr("minio.minioadmin.MinioAdmin", factory)
    message = mod.grant(root)
    name = calls[0][1]
    assert calls == [
        ("add", name, {"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Action": ["s3:ListenBucketNotification"],
             "Resource": ["arn:aws:s3:::dji-cloud"]}]}),
        ("attach", [name], "reader")]
    assert "secret" not in message and "restart" in message


def test_constructor_errors_are_redacted(setup, monkeypatch):
    mod, root = setup
    def fail(**kwargs):
        raise TypeError("private-admin-secret")
    monkeypatch.setattr("minio.minioadmin.MinioAdmin", fail)
    with pytest.raises(RuntimeError, match="MinIO admin request failed") as error:
        mod.grant(root)
    assert "secret" not in str(error.value)
