import pytest

from aeronexus import probe_state
from aeronexus.providers import DeviceSnapshot, ProviderKind


SN = "1ZRDH3V000000TEST"
PROJECT = "93df839d-ae74-4f04-842e-2f1f81c89a66"
TOKEN = "TOP-SECRET-TOKEN"


def setup_env(monkeypatch):
    monkeypatch.setenv("AERONEXUS_DJI_BASE_URL", "https://api-openapi.dji.com")
    monkeypatch.setenv("AERONEXUS_DJI_TOKEN", TOKEN)
    monkeypatch.setenv("AERONEXUS_DJI_PROJECT_UUID", PROJECT)
    monkeypatch.setenv("AERONEXUS_DJI_DEVICE_SN", SN)


def test_probe_uses_scoped_reader(monkeypatch):
    import asyncio
    observed = {}
    async def reader(config, project_uuid, device_id):
        observed.update(project_uuid=project_uuid, device_id=device_id,
                        token=config.access_token)
        return DeviceSnapshot(ProviderKind.PUBLIC_V2, SN, online=True)
    monkeypatch.setattr(probe_state, "read_public_aircraft_state", reader)
    snap = asyncio.run(probe_state.probe({
        "AERONEXUS_DJI_BASE_URL": "https://api-openapi.dji.com",
        "AERONEXUS_DJI_TOKEN": TOKEN,
        "AERONEXUS_DJI_PROJECT_UUID": PROJECT,
        "AERONEXUS_DJI_DEVICE_SN": SN,
    }))
    assert snap.online is True
    assert observed == {"project_uuid": PROJECT, "device_id": SN, "token": TOKEN}


def test_probe_redacts_sensitive_values(monkeypatch, capsys):
    setup_env(monkeypatch)
    async def reader(values):
        return DeviceSnapshot(ProviderKind.PUBLIC_V2, SN, online=True,
                              latitude=49.25123, longitude=8.50512,
                              battery_percent=83, height_m=50,
                              rtk_satellites=19, rtk_state="is_fixed:1")
    monkeypatch.setattr(probe_state, "probe", reader)
    assert probe_state.main() == 0
    output = capsys.readouterr().out
    assert "Battery: 83 %" in output
    assert "Height: 50 m" in output
    assert "GPS coordinates present: yes (not displayed)" in output
    assert SN not in output and PROJECT not in output and TOKEN not in output
    assert "49.25123" not in output and "8.50512" not in output
    assert "is_fixed:1" not in output


def test_probe_redacts_error_message(monkeypatch, capsys):
    setup_env(monkeypatch)
    async def reader(values):
        raise RuntimeError(f"Unexpected: {TOKEN} / {SN}")
    monkeypatch.setattr(probe_state, "probe", reader)
    assert probe_state.main() == 1
    output = capsys.readouterr().out
    assert TOKEN not in output and SN not in output


def test_probe_missing_env(monkeypatch, capsys):
    setup_env(monkeypatch)
    monkeypatch.delenv("AERONEXUS_DJI_TOKEN")
    assert probe_state.main() == 2
    assert "AERONEXUS_DJI_TOKEN" in capsys.readouterr().out
