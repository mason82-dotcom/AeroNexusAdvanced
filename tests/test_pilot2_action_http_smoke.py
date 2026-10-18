"""Offline security checks for the in-process, no-deploy Pi HTTP acceptance script."""
import asyncio
import importlib
import importlib.util
import json
from pathlib import Path

import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pi/pilot2_studio_action_http_smoke.py"
_spec = importlib.util.spec_from_file_location("aeronexus_studio_pilot_http_smoke_test", _SCRIPT)
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)
appmod = importlib.import_module("aeronexus.app")


def _safe_report():
    return {
        "state": "connected", "checked": 2, "total": 2,
        "recognized_actions": 4, "unknown_actions": 6,
        "read_only": True, "wpml_semantics_verified": False,
        "flight_compatibility_verified": False,
        "full_content_verified": False,
        "anonymous_types": [
            {"alias": "A01", "occurrences": 6, "file_count": 2,
             "locations": {"waypoint": 6},
             "triggers": {"betweenAdjacentPoints": 6}},
        ],
        "waylines": [
            {"index": 1, "route_count": 2, "schema": "1.0.6",
             "known_actions": 1, "unknown_actions": 3},
            {"index": 2, "route_count": 1, "schema": "1.0.6",
             "known_actions": 3, "unknown_actions": 3},
        ],
    }


def test_smoke_enforces_two_unauthorized_denials_without_scanning(monkeypatch):
    prior = "previous-bearer-only-in-this-test-environment"
    monkeypatch.setenv("AERONEXUS_STATUS_TOKEN", prior)
    old = getattr(appmod.app.state, "pilot2_action_summary", None)
    class Reader:
        calls = 0
        async def read(self):
            self.calls += 1
            return _safe_report()
    fake = Reader()
    result = asyncio.run(smoke.run_smoke(reader=fake))
    assert result["state"] == "connected"
    assert result["checked"] == 2
    assert result["unknown_actions"] == 6
    # Two authorized calls; requests lacking a valid bearer never reach reader.
    assert fake.calls == 2
    assert getattr(appmod.app.state, "pilot2_action_summary", None) is old
    assert smoke.os.environ["AERONEXUS_STATUS_TOKEN"] == prior
    assert "A01" not in json.dumps(result)
    assert "anonymous_types" not in result


def test_smoke_rejects_an_unsafe_report_and_restores_process_state(monkeypatch):
    monkeypatch.delenv("AERONEXUS_STATUS_TOKEN", raising=False)
    class Reader:
        async def read(self):
            unsafe = _safe_report()
            unsafe["flight_compatibility_verified"] = True
            return unsafe
    with pytest.raises(RuntimeError, match="read-only/compatibility boundaries violated"):
        asyncio.run(smoke.run_smoke(reader=Reader()))
    assert "AERONEXUS_STATUS_TOKEN" not in smoke.os.environ


def test_smoke_rejects_offline_reader_failure_without_network_or_dji_write():
    class Reader:
        async def read(self):
            return {"state": "unavailable", "read_only": True,
                    "wpml_semantics_verified": False,
                    "flight_compatibility_verified": False,
                    "full_content_verified": False}
    with pytest.raises(RuntimeError, match="inventory unavailable or incomplete"):
        asyncio.run(smoke.run_smoke(reader=Reader()))


def test_smoke_script_explicitly_uses_in_process_asgi_without_listener():
    source = _SCRIPT.read_text()
    assert "ASGITransport(app=app_module.app)" in source
    assert "patch.object(app_module, \"lan_mode_enabled\", return_value=False)" in source
    assert "secrets.token_urlsafe(48)" in source
    assert "app.state.pilot2_action_summary" not in source or "app_module.app.state.pilot2_action_summary" in source
    assert "uvicorn.run(" not in source
    assert "subprocess." not in source
    assert "server.start" not in source
    assert "method=\"POST\"" not in source
