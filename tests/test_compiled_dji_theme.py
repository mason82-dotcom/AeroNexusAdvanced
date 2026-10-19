"""No-build DJI Vue theme: preserve exactly the working JS app and image."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pi/stage_compiled_dji_theme.py"
SPEC = importlib.util.spec_from_file_location("compiled_theme", SCRIPT)
theme = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(theme)

COMPILED = (
    '<!doctype html><html lang="en"><head><meta charset="UTF-8">'
    '<title>AeroNexusAdvanced</title>'
    '<script type="module" crossorigin src="/assets/index-abcd1234.js"></script>'
    '<link rel="stylesheet" href="/assets/index-bbbb.css"></head>'
    '<body><div id="demo-app"></div></body></html>'
)


def setup(tmp_path):
    portal = tmp_path / "deploy/cloud-server/control-portal"
    portal.mkdir(parents=True)
    (portal / "index.html").write_text("<html>Portal</html>")
    (portal / "pilot-ui.css").write_text("/* AeroNexusAdvanced */\n" + "p{margin:0}\n"*70)
    edge = tmp_path / "cloud-server/edge"
    edge.mkdir(parents=True)
    existing = edge / "compose.portal.yaml"
    existing.write_text(
        "services:\n  control:\n    volumes:\n      - type: bind\n"
        "        target: /usr/share/nginx/html/aeronexus\n"
        "        read_only: true\n"
    )
    return portal, edge, existing


def test_only_one_stylesheet_link_added():
    patched = theme.patch_html(COMPILED)
    assert patched.count(theme.LINK) == 1
    assert patched.replace(theme.LINK + "\n", "") == COMPILED
    assert '/assets/index-abcd1234.js' in patched
    assert '<div id="demo-app"></div>' in patched


def test_unknown_entry_or_existing_injection_fails():
    for bad in (
        COMPILED.replace('id="demo-app"', 'id="unknown"'),
        COMPILED.replace('/assets/index-abcd1234.js', '/src/main.ts'),
        COMPILED.replace("</head>", theme.LINK + "</head>"),
        '<html><head></head><body></body></html>',
    ):
        with pytest.raises(ValueError):
            theme.patch_html(bad)


def test_preflight_requires_portal_and_real_stylesheet(tmp_path, monkeypatch):
    portal, edge, overlay = setup(tmp_path)
    monkeypatch.setattr(theme, "PORTAL", portal)
    result = theme.preflight(COMPILED, portal / "pilot-ui.css", overlay)
    assert theme.LINK in result
    overlay.write_text("services:\n  control: {}\n")
    with pytest.raises(ValueError, match="read-only"):
        theme.preflight(COMPILED, portal / "pilot-ui.css", overlay)


def test_stage_creates_only_private_readonly_overlays(tmp_path):
    portal, edge, overlay = setup(tmp_path)
    runtime = edge / "pilot-ui-runtime"
    target = edge / "compose.theme.yaml"
    modified = theme.patch_html(COMPILED)
    result = theme.stage(COMPILED, modified, runtime, target)
    assert all(x == "erstellt" for x in result.values())
    assert (runtime / "index.original.html").read_text() == COMPILED
    assert (runtime / "index.html").read_text() == modified
    assert runtime.stat().st_mode & 0o777 == 0o700
    for p in (runtime / "index.html", runtime / "index.original.html", target):
        assert p.stat().st_mode & 0o777 == 0o600
    compose = target.read_text()
    assert "  control:" in compose
    assert "read_only: true" in compose
    assert "create_host_path: false" in compose
    assert "target: /usr/share/nginx/html/index.html" in compose
    assert "ports:" not in compose
    assert "image:" not in compose
    assert "command:" not in compose
    assert all(x == "vorhanden" for x in
               theme.stage(COMPILED, modified, runtime, target).values())


def test_conflict_fails_without_overwriting(tmp_path):
    portal, edge, overlay = setup(tmp_path)
    runtime = edge / "pilot-ui-runtime"
    modified = theme.patch_html(COMPILED)
    theme.stage(COMPILED, modified, runtime, edge / "compose.theme.yaml")
    original_backup = runtime / "index.original.html"
    original_backup.write_text("a different operator backup")
    with pytest.raises(ValueError, match="weicht ab"):
        theme.stage(COMPILED, modified, runtime, edge / "compose.theme.yaml")
    assert original_backup.read_text() == "a different operator backup"


def test_docker_reads_current_branded_image_and_html_only(monkeypatch):
    calls = []
    def fake(*args):
        calls.append(args)
        if args[0] == "inspect":
            return (theme.IMAGE + "\n").encode()
        return COMPILED.encode()
    monkeypatch.setattr(theme, "docker_read", fake)
    assert theme.read_live_html() == COMPILED
    assert calls == [
        ("inspect", "--format", "{{.Config.Image}}", theme.CONTAINER),
        ("exec", theme.CONTAINER, "cat", theme.NGINX_INDEX)
    ]


def test_reject_wrong_running_image(monkeypatch):
    monkeypatch.setattr(theme, "docker_read", lambda *args: b"other/image:latest\n")
    with pytest.raises(ValueError, match="branded-Image"):
        theme.read_live_html()


def test_script_only_reads_docker_and_never_builds():
    script = SCRIPT.read_text()
    assert '"exec", CONTAINER, "cat", NGINX_INDEX' in script
    assert '"inspect", "--format"' in script
    assert "docker compose" not in script
    assert "docker build" not in script
    assert "DJI_APP_LICENSE" not in script
    assert "DJI_APP_KEY" not in script
    assert "yarn" not in script
