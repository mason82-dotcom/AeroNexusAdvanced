import asyncio

from aeronexus import probe_devices
from aeronexus.flighthub_device_list import ObservedAircraft
from aeronexus.providers import ProviderKind

P = "93df839d-ae74-4f04-842e-2f1f81c89a66"
O = "105ddd05-34ce-46b6-a872-cb32b8c98f64"

def variables():
    return {"AERONEXUS_DJI_BASE_URL": "https://api-openapi.dji.com",
            "AERONEXUS_DJI_TOKEN": "not-a-real-token",
            "AERONEXUS_DJI_PROJECT_UUID": P,
            "AERONEXUS_DJI_ORGANIZATION_UUID": O}


def test_probe_public_counts(monkeypatch):
    async def fake_read(config, project_uuid):
        assert config.kind == ProviderKind.PUBLIC_V2
        assert project_uuid == P
        return (ObservedAircraft("a", "A", True),
                ObservedAircraft("b", "B", False),
                ObservedAircraft("c", "C", None))
    monkeypatch.setattr(probe_devices, "read_public_aircraft", fake_read)
    assert asyncio.run(probe_devices.probe("public", variables())) == (3, 1, 1)


def test_probe_onprem_page(monkeypatch):
    async def fake_read(config, org_uuid, *, page, page_size):
        assert config.kind == ProviderKind.ONPREM_V2
        assert org_uuid == O and page == 3 and page_size == 10
        return (ObservedAircraft("a", "A", True),)
    monkeypatch.setattr(probe_devices, "read_onprem_aircraft", fake_read)
    assert asyncio.run(probe_devices.probe(
        "onprem", variables(), page=3, page_size=10)) == (1, 1, 0)


def test_cli_prints_only_summary(monkeypatch, capsys):
    async def fake_probe(provider, values, *, page, page_size):
        return (3, 1, 1)
    monkeypatch.setattr(probe_devices, "probe", fake_probe)
    for name, value in variables().items():
        monkeypatch.setenv(name, value)
    assert probe_devices.main(["--provider", "public"]) == 0
    output = capsys.readouterr().out
    assert "Aircraft on this page: 3" in output
    assert "Online: 1; Offline: 1; Unknown: 1" in output
    assert "not-a-real-token" not in output


def test_cli_redacts_failures(monkeypatch, capsys):
    async def failing_probe(provider, values, *, page, page_size):
        raise RuntimeError("secret value must not be printed")
    monkeypatch.setattr(probe_devices, "probe", failing_probe)
    for name, value in variables().items():
        monkeypatch.setenv(name, value)
    assert probe_devices.main(["--provider", "public"]) == 1
    assert "secret value" not in capsys.readouterr().out


def test_cli_missing_token(monkeypatch, capsys):
    import pytest
    for name, value in variables().items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("AERONEXUS_DJI_TOKEN")
    with pytest.raises(SystemExit) as exc:
        probe_devices.main(["--provider", "public"])
    assert exc.value.code == 2
    assert "AERONEXUS_DJI_TOKEN" in capsys.readouterr().err
