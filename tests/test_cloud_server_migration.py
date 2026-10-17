"""Cold migration tooling: path safety and read-only staging contracts."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/migrate_cloud_server.py"
SPEC = importlib.util.spec_from_file_location("cloud_migration", SCRIPT)
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


def test_path_containment_does_not_trust_string_prefix(tmp_path):
    source = tmp_path / "AeroNexus"
    source.mkdir()
    neighbor = tmp_path / "AeroNexusAdvanced"
    neighbor.mkdir()
    assert migration.under(source / "edge", source)
    assert not migration.under(neighbor, source)
    assert not migration.under(source, neighbor)


def test_minio_storage_location_and_dynamic_expansion(tmp_path):
    source = tmp_path / "AeroNexus"
    edge = source / "edge"
    edge.mkdir(parents=True)
    env = edge / ".env"
    env.write_text("MINIO_DATA_DIR=./data/minio\nSECRET=never-print-this\n")
    location, external = migration.minio_path(env, edge)
    assert location == (edge / "data/minio").resolve()
    assert external is False
    external_mount = tmp_path / "external-minio"
    external_mount.mkdir()
    env.write_text(f"MINIO_DATA_DIR={external_mount}\n")
    assert migration.minio_path(env, edge) == (external_mount, True)
    env.write_text("MINIO_DATA_DIR=$HOME/minio\n")
    with pytest.raises(RuntimeError, match="dynamic"):
        migration.minio_path(env, edge)


def fake_source(tmp_path):
    source = tmp_path / "AeroNexus"
    target_parent = tmp_path / "AeroNexusAdvanced"
    target_parent.mkdir()
    for rel in migration.REQUIRED:
        path = source / rel
        if path.name == ".env" or path.suffix in (".yml", ".conf", ".csv", ".sh"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("conf\n")
        else:
            path.mkdir(parents=True, exist_ok=True)
    (source / "edge/data/minio").mkdir(parents=True)
    (source / "edge/.env").write_text("MINIO_DATA_DIR=./data/minio\n")
    template = target_parent / "compose.core.yaml"
    template.write_text("name: aeronexusadvanced-cloud\n")
    return source, target_parent / "cloud-server", template


def test_preflight_accepts_stopped_self_contained_source(tmp_path):
    source, target, template = fake_source(tmp_path)
    minio, external = migration.validate_source(source, target, template)
    assert minio == source / "edge/data/minio"
    assert external is False


def test_preflight_rejects_missing_required_path(tmp_path):
    source, target, template = fake_source(tmp_path)
    (source / "api/docker/application.yml").unlink()
    with pytest.raises(RuntimeError, match="Notwendiger"):
        migration.validate_source(source, target, template)


def test_preflight_rejects_symlinked_database(tmp_path):
    source, target, template = fake_source(tmp_path)
    real = source / "external_database"
    real.mkdir()
    database = source / "edge/data/mysql"
    database.rmdir()
    database.symlink_to(real)
    with pytest.raises(RuntimeError, match="Symlink"):
        migration.validate_source(source, target, template)


def test_compose_validator_rejects_legacy_mount(tmp_path, monkeypatch):
    source = tmp_path / "AeroNexus"
    source.mkdir()
    staged = tmp_path / "AeroNexusAdvanced/cloud-server.partial"
    (staged / "edge").mkdir(parents=True)
    (staged / "edge/.env").write_text("REDIS_PASSWORD=redacted\n")
    (staged / "edge/.env").chmod(0o600)
    data = {"name": migration.PROJECT, "services": {
        name: {"volumes": []} for name in migration.CORE}}
    data["services"]["emqx"]["volumes"] = [{
        "type": "bind", "source": str(source / "telemetry/emqx/acl.conf"),
        "target": "/opt/emqx/etc/acl.conf",
    }]
    monkeypatch.setattr(migration, "run", lambda *args, **kwargs:
                        SimpleNamespace(stdout=json.dumps(data)))
    with pytest.raises(RuntimeError, match="alte Projekt"):
        migration.validate_compose(staged, source)
    data["services"]["emqx"]["volumes"][0]["source"] = str(
        staged / "telemetry/emqx/acl.conf")
    migration.validate_compose(staged, source)


def test_compose_validator_rejects_extra_services(tmp_path, monkeypatch):
    source = tmp_path / "AeroNexus"
    source.mkdir()
    staged = tmp_path / "AeroNexusAdvanced/cloud-server.partial"
    (staged / "edge").mkdir(parents=True)
    (staged / "edge/.env").write_text("x\n")
    (staged / "edge/.env").chmod(0o600)
    data = {"name": migration.PROJECT, "services": {
        name: {} for name in (*migration.CORE, "farming")}}
    monkeypatch.setattr(migration, "run", lambda *args, **kwargs:
                        SimpleNamespace(stdout=json.dumps(data)))
    with pytest.raises(RuntimeError, match="unerwartete"):
        migration.validate_compose(staged, source)


def test_never_automatically_starts_or_deletes_original_server():
    text = SCRIPT.read_text()
    assert "shutil.rmtree" not in text
    assert "docker compose up" not in text
    assert "docker compose down" not in text
    assert "docker rm" not in text
    assert "os.remove" not in text
    assert "copy_cold(source, partial)" in text
    assert "validate_compose(partial, source)" in text
    assert "partial.rename(target)" in text
    assert 'edge/docker-compose.legacy.yml' in text
    assert 'edge/docker-compose.yml' in text


def test_minimal_compose_is_isolated_and_uses_local_images():
    compose = (ROOT / "deploy/cloud-server/compose.core.yaml").read_text()
    assert "name: aeronexusadvanced-cloud" in compose
    assert "restart: \"no\"" in compose
    for service in migration.CORE:
        assert f"  {service}:\n" in compose
    for image in migration.IMAGES:
        assert f"image: {image}" in compose
    assert "1884:1883" in compose
    assert "127.0.0.1:18083:18083" in compose
    assert "minio-init.sh" in compose
    assert "../telemetry/emqx/acl.conf" in compose
    assert "aeronexusadvanced.service" not in compose
    assert "services:\n  mapping:" not in compose


def test_mediamtx_livestream_without_logins_but_lan_only():
    compose = (ROOT / "deploy/cloud-server/compose.core.yaml").read_text()
    assert "  mediamtx:\n" in compose and "network_mode: host" in compose
    assert "./mediamtx.yml:/mediamtx.yml:ro" in compose
    config = (ROOT / "deploy/cloud-server/mediamtx.yml").read_text()
    assert "authMethod: internal" in config and "authHTTPAddress" not in config
    users = config.split("authInternalUsers:", 1)[1].split("\nrtmp:", 1)[0]
    assert "0.0.0.0/0" not in users and "::/0" not in users
    assert '"192.168.178.0/24", "127.0.0.1/32", "::1/128"' in users
    admin = users.split("- action: playback", 1)[1]
    assert '"192.168.178.0/24"' not in admin and "- action: api" in admin
    assert "apiAddress: 127.0.0.1:9997" in config
    from aeronexus.lan_access import HOME_SUBNET
    assert str(HOME_SUBNET) in users


def test_migrated_secrets_are_gitignored():
    ignore = (ROOT / ".gitignore").read_text()
    assert "/cloud-server/" in ignore
