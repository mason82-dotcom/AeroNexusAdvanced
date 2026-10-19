"""Fail-closed DJI Vue theme staging; no operational or DJI changes."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pi/stage_dji_vue_theme.py"
SPEC = importlib.util.spec_from_file_location("stage_dji_vue_theme", SCRIPT)
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def example(tmp_path):
    web = tmp_path / "cloud-server/edge/runtime/upstream/web"
    web.mkdir(parents=True)
    html = web / "index.html"
    html.write_text(
        '<!DOCTYPE html><html><head><title>AeroNexusAdvanced</title></head>'
        '<body><div id="demo-app"></div><script type="module" '
        'src="/src/main.ts"></script></body></html>', encoding="utf-8")
    theme = tmp_path / "deploy/cloud-server/control-portal/pilot-ui.css"
    theme.parent.mkdir(parents=True)
    theme.write_text("/* AeroNexusAdvanced */\n" + "body {color: inherit;}\n" * 35,
                     encoding="utf-8")
    overlay = tmp_path / "cloud-server/edge/compose.portal.yaml"
    overlay.write_text("services:\n  control:\n    volumes:\n"
                       "      - type: bind\n"
                       "        target: /usr/share/nginx/html/aeronexus\n"
                       "        read_only: true\n", encoding="utf-8")
    backup = tmp_path / "cloud-server/edge/pilot-ui-backup/index.html"
    return html, theme, overlay, backup


def test_preflight_fails_closed_for_unrecognized_upstream(tmp_path):
    html, css, overlay, backup = example(tmp_path)
    original, _ = stage.preflight(html, css, overlay)
    assert "demo-app" in original
    html.write_text("<html><head></head><body>unknown</body></html>")
    with pytest.raises(ValueError, match="Vue-App-Einstieg"):
        stage.preflight(html, css, overlay)


def test_requires_existing_readonly_portal_mount(tmp_path):
    html, css, overlay, backup = example(tmp_path)
    overlay.write_text("services:\n  control:\n    ports:\n      - 8085:80\n")
    with pytest.raises(ValueError, match="read-only-Mount"):
        stage.preflight(html, css, overlay)


def test_adds_only_css_link_and_preserves_original_vue(tmp_path):
    html, css, overlay, backup = example(tmp_path)
    original, _ = stage.preflight(html, css, overlay)
    patched = stage.patch_html(original)
    assert patched.replace(stage.LINK + "\n", "") == original.replace(
        "</head>", "  </head>")
    assert patched.count(stage.LINK) == 1
    assert 'src="/src/main.ts"' in patched
    assert stage.apply(html, backup, original, patched).startswith("Theme-Link")
    assert backup.read_text(encoding="utf-8") == original
    assert backup.stat().st_mode & 0o777 == 0o600
    assert stage.patch_html(html.read_text(encoding="utf-8")) == patched
    assert stage.apply(html, backup, patched, patched).startswith("Bereits")


def test_refuses_foreign_backup(tmp_path):
    html, css, overlay, backup = example(tmp_path)
    original, _ = stage.preflight(html, css, overlay)
    backup.parent.mkdir(parents=True)
    backup.write_text("custom original source")
    with pytest.raises(RuntimeError, match="Backup"):
        stage.apply(html, backup, original, stage.patch_html(original))
    assert html.read_text(encoding="utf-8") == original


def test_refuses_duplicate_and_foreign_css_links(tmp_path):
    html, css, overlay, _ = example(tmp_path)
    html.write_text(html.read_text().replace("</head>", stage.LINK*2 + "</head>"))
    with pytest.raises(ValueError, match="Mehrfaches"):
        stage.preflight(html, css, overlay)
    html.write_text(html.read_text().replace(stage.LINK*2,
                                             '<link data-aeronexus-theme="v2" href="/other.css">'))
    with pytest.raises(ValueError, match="Abweichendes"):
        stage.preflight(html, css, overlay)


def test_dryrun_never_writes(tmp_path, monkeypatch, capsys):
    html, css, overlay, backup = example(tmp_path)
    old = html.read_bytes()
    monkeypatch.setattr(stage, "HTML", html)
    monkeypatch.setattr(stage, "CSS", css)
    monkeypatch.setattr(stage, "PORTAL_OVERLAY", overlay)
    monkeypatch.setattr(stage, "BACKUP", backup)
    assert stage.main([]) == 0
    assert "PREFLIGHT OK" in capsys.readouterr().out
    assert html.read_bytes() == old
    assert not backup.exists()


def test_css_is_scoped_and_does_not_hide_device_controls():
    css = (ROOT / "deploy/cloud-server/control-portal/pilot-ui.css").read_text()
    assert ".login > .ant-form" in css
    assert ".demo-project-sidebar-wrapper" in css
    assert ".ant-layout-header.header" in css
    assert "display: none" not in css
    assert "pointer-events: none" not in css
    assert "position: fixed" not in css
    assert "@media (max-width: 720px)" in css


def test_no_docker_dji_upload_or_credential_access():
    script = SCRIPT.read_text()
    assert "subprocess" not in script
    assert "docker compose" not in script.lower()
    assert "DJI_APP_KEY" not in script
    assert "DJI_APP_LICENSE" not in script
    assert "mqtt" in script.lower()
