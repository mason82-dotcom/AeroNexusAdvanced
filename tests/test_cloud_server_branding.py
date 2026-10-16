"""Pilot 2 branding: fail-closed, local-only changes, preserved DJI auth."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/brand_cloud_server.py"
SPEC = importlib.util.spec_from_file_location("brand_cloud", SCRIPT)
brand = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(brand)


def source(tmp_path):
    web = tmp_path / "edge/runtime/upstream/web"
    (web / "src/locales").mkdir(parents=True)
    (web / "src/locales/de.ts").write_text(
        'export default {\n  "Pilot Cloud API Demo": "AeroNexus Pilot",\n'
        '  "Anmelden": "Anmelden",\n}\n', encoding="utf-8")
    (web / "index.html").write_text(
        '<html><head><title>AeroNexus</title></head></html>',
        encoding="utf-8")
    edge = tmp_path / "edge"
    template = tmp_path / "deploy/cloud-server/compose.brand.yaml"
    template.parent.mkdir(parents=True)
    template.write_text("services:\n  control:\n    image: aeronexusadvanced/control:branded\n")
    return web, edge, template


def test_preflight_detects_original_branded_strings(tmp_path):
    web, _, _ = source(tmp_path)
    changes, needed = brand.check_pilot_source(web)
    assert needed
    assert len(changes) == 2
    assert brand.NEW_LOCALE in changes[web / "src/locales/de.ts"]
    assert brand.NEW_TITLE in changes[web / "index.html"]
    assert brand.OLD_LOCALE in (web / "src/locales/de.ts").read_text()


def test_brand_apply_preserves_both_source_backups_and_is_idempotent(tmp_path):
    web, edge, template = source(tmp_path)
    old_index = (web / "index.html").read_bytes()
    old_locale = (web / "src/locales/de.ts").read_bytes()
    changes, _ = brand.check_pilot_source(web)
    brand.apply_brand(web, changes, edge, template)
    assert (edge / "branding-backup/index.html").read_bytes() == old_index
    assert (edge / "branding-backup/src/locales/de.ts").read_bytes() == old_locale
    assert (edge / "compose.brand.yaml").read_bytes() == template.read_bytes()
    assert brand.NEW_TITLE in (web / "index.html").read_text()
    assert brand.NEW_LOCALE in (web / "src/locales/de.ts").read_text()
    assert "Anmelden" in (web / "src/locales/de.ts").read_text()
    changes, needed = brand.check_pilot_source(web)
    assert not needed
    assert changes == {}
    brand.apply_brand(web, changes, edge, template)
    assert (edge / "branding-backup/index.html").read_bytes() == old_index


def test_brand_fails_closed_if_localization_unknown_or_duplicated(tmp_path):
    web, _, _ = source(tmp_path)
    locale = web / "src/locales/de.ts"
    locale.write_text("no longer a known upstream localization")
    with pytest.raises(ValueError, match="eindeutige"):
        brand.check_pilot_source(web)
    locale.write_text(brand.OLD_LOCALE + "\n" + brand.OLD_LOCALE)
    with pytest.raises(ValueError, match="eindeutige"):
        brand.check_pilot_source(web)


def test_brand_does_not_overwrite_a_different_existing_overlay(tmp_path):
    web, edge, template = source(tmp_path)
    (edge / "compose.brand.yaml").write_text("CUSTOM LOCAL SETTINGS")
    changes, _ = brand.check_pilot_source(web)
    with pytest.raises(RuntimeError, match="Abweichende"):
        brand.apply_brand(web, changes, edge, template)


def test_api_connection_values_only_returns_nonsecrets(monkeypatch):
    monkeypatch.setattr(brand.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(stdout='["SERVER_HOST=192.168.178.63",'
                                              '"BROKER_HOST=192.168.178.63",'
                                              '"BROKER_PORT=1884",'
                                              '"DJI_APP_LICENSE=PRIVATE",'
                                              '"DJI_APP_KEY=PRIVATE"]'))
    values = brand.api_connection_values("aeronexusadvanced-cloud-api-1")
    assert values == {"SERVER_HOST": "192.168.178.63",
                      "BROKER_HOST": "192.168.178.63", "BROKER_PORT": "1884"}


def test_brand_env_keys_drops_secrets(tmp_path):
    f = tmp_path / ".env"
    f.write_text('SERVER_HOST=192.168.178.63\n'
                 'WORKSPACE_NAME="AeroNexusAdvanced"\n'
                 'PLATFORM_NAME="AeroNexusAdvanced"\n'
                 'DJI_APP_LICENSE=PRIVATE\nDJI_APP_KEY=PRIVATE\n')
    assert brand.env_keys(f) == {
        "SERVER_HOST": "192.168.178.63",
        "WORKSPACE_NAME": "AeroNexusAdvanced",
        "PLATFORM_NAME": "AeroNexusAdvanced",
    }


def test_compose_brand_image_is_separate_from_rollback_and_build_is_explicit():
    overlay = (ROOT / "deploy/cloud-server/compose.brand.yaml").read_text()
    core = (ROOT / "deploy/cloud-server/compose.core.yaml").read_text()
    assert "image: aeronexusadvanced/control:branded" in overlay
    assert "image: aeronexus/control:local" in core
    assert "VITE_DJI_APP_LICENSE: ${DJI_APP_LICENSE:?required}" in overlay
    assert "VITE_BASE_URL: http://${SERVER_HOST:?required}:6789/" in overlay
    assert "VITE_WS_URL: ws://${SERVER_HOST:?required}:6789/api/v1/ws" in overlay
    assert "  control:" in overlay
    for service in ("mysql", "redis", "emqx", "api", "minio", "minio-init"):
        assert f"  {service}:" not in overlay
    assert "docker compose up" not in SCRIPT.read_text()
    assert "docker build" not in SCRIPT.read_text()


def test_read_only_command_never_writes(monkeypatch, tmp_path, capsys):
    web, edge, template = source(tmp_path)
    (edge / ".env").write_text(
        'SERVER_HOST=192.168.178.63\n'
        'WORKSPACE_NAME="AeroNexusAdvanced"\n'
        'PLATFORM_NAME="AeroNexusAdvanced"\n')
    monkeypatch.setattr(brand, "EDGE", edge)
    monkeypatch.setattr(brand, "WEB", web)
    monkeypatch.setattr(brand, "OVERLAY_TEMPLATE", template)
    monkeypatch.setattr(brand, "api_connection_values", lambda name: {
        "SERVER_HOST": "192.168.178.63",
        "BROKER_HOST": "192.168.178.63",
        "BROKER_PORT": "1884",
    })
    assert brand.main([]) == 0
    assert "NUR PRÜFUNG" in capsys.readouterr().out
    assert brand.OLD_LOCALE in (web / "src/locales/de.ts").read_text()
    assert not (edge / "compose.brand.yaml").exists()
