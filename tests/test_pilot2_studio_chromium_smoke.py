"""Offline contract tests for optional real-Chromium Studio DOM smoke."""
import importlib.util
from pathlib import Path
import subprocess
from unittest.mock import patch

from aeronexus.studio_page import render_studio


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi/pilot2_studio_chromium_smoke.py"
SPEC = importlib.util.spec_from_file_location("pilot2_studio_chromium_smoke", SCRIPT)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_browser_fixture_embeds_actual_diagnostic_logic_not_full_page():
    fixture = smoke.build_fixture()
    page = render_studio()
    block = page[page.index(smoke.START):page.index(smoke.END, page.index(smoke.START))]
    assert block in fixture
    assert "__STUDIO_JS__" not in fixture
    assert 'id="pilot2-action-load"' in fixture
    assert "full_content_verified:true" in fixture
    assert "oldSignal.aborted===true" in fixture
    assert "<link " not in fixture
    assert "<iframe" not in fixture
    assert 'window.fetch(' not in fixture


def test_browser_runner_is_file_only_and_blocks_network_lookups():
    with patch.object(smoke, "browser_binary", return_value="/usr/bin/chromium"):
        with patch.object(smoke.subprocess, "run", return_value=subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='<html data-pilot2-browser-smoke="PASS"><body></body></html>',
            stderr="",
        )) as call:
            assert smoke.run_smoke() == 0
    command = call.call_args.args[0]
    assert command[0] == "/usr/bin/chromium"
    assert command[-1].startswith("file:///")
    assert command[-2] == "--dump-dom"
    assert "--headless=new" in command
    assert "--disable-background-networking" in command
    assert "--host-resolver-rules=MAP * 0.0.0.0" in command
    assert not any("no-sandbox" in item for item in command)
    assert call.call_args.kwargs["timeout"] == 45


def test_browser_result_only_accepts_explicit_success_marker():
    with patch.object(smoke.subprocess, "run", return_value=subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout='<html data-pilot2-browser-smoke="FAIL"></html>',
        stderr="private-untrusted",
    )):
        assert smoke.run_smoke(browser="/usr/bin/chromium") == 1


def test_browser_unavailable_does_not_claim_pass():
    with patch.object(smoke, "browser_binary", return_value=None):
        assert smoke.run_smoke() == 2
