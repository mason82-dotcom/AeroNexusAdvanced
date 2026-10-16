import pytest
from aeronexus.inventory import Inventory, Project, DeviceType
from aeronexus.providers import ProviderKind
from aeronexus.sync_pipeline import ingest_project_batch

K = ProviderKind.PUBLIC_V2
OTHER = ProviderKind.ONPREM_V2

def inventory():
    inv = Inventory()
    inv.add_project(Project(K, "p", "Project"))
    return inv

def test_full_batch():
    inv = inventory()
    counts = ingest_project_batch(inv, K, "p",
        [{"device_id": "a", "name": "Aircraft", "kind": "aircraft"},
         {"device_id": "r", "name": "Remote", "kind": "controller"}],
        [{"device_id": "a", "online": True, "latitude": 49.0, "longitude": 8.0,
          "battery_percent": 80, "rtk_state": "fixed"}])
    assert counts == (2, 1)
    assert len(inv.devices(K, "p")) == 2
    assert inv.telemetry(K, "p", "a").battery_percent == 80

def test_bad_telemetry_rolls_back_devices():
    inv = inventory()
    with pytest.raises(ValueError):
        ingest_project_batch(inv, K, "p",
            [{"device_id": "a", "name": "Aircraft", "kind": "aircraft"}],
            [{"device_id": "a", "battery_percent": 120}])
    assert inv.devices() == ()

def test_unknown_device_rolls_back():
    inv = inventory()
    with pytest.raises(ValueError):
        ingest_project_batch(inv, K, "p",
            [{"device_id": "a", "name": "Aircraft", "kind": "aircraft"}],
            [{"device_id": "missing", "online": True}])
    assert inv.devices() == ()

def test_dock_rejected_atomically():
    inv = inventory()
    with pytest.raises(ValueError):
        ingest_project_batch(inv, K, "p",
            [{"device_id": "a", "name": "Aircraft", "kind": "aircraft"},
             {"device_id": "dock", "name": "Dock", "kind": "dock"}], [])
    assert inv.devices() == ()

def test_missing_project():
    with pytest.raises(ValueError):
        ingest_project_batch(Inventory(), K, "missing",
            [{"device_id": "a", "name": "Aircraft", "kind": "aircraft"}], [])

def test_bad_telemetry_container():
    with pytest.raises(ValueError):
        ingest_project_batch(inventory(), K, "p", [], "invalid")

def test_idempotent():
    inv = inventory()
    devices = [{"device_id": "a", "name": "Aircraft", "kind": "aircraft"}]
    data = [{"device_id": "a", "online": True}]
    ingest_project_batch(inv, K, "p", devices, data)
    ingest_project_batch(inv, K, "p", devices, data)
    assert len(inv.devices()) == 1

def test_provider_isolation():
    inv = inventory()
    inv.add_project(Project(OTHER, "p", "Other"))
    ingest_project_batch(inv, K, "p",
        [{"device_id": "a", "name": "Aircraft", "kind": "aircraft"}], [])
    assert inv.devices(OTHER, "p") == ()

def test_existing_snapshot_survives_empty_batch():
    inv = inventory()
    ingest_project_batch(inv, K, "p",
        [{"device_id": "a", "name": "Aircraft", "kind": "aircraft"}],
        [{"device_id": "a", "online": True}])
    ingest_project_batch(inv, K, "p", [], [])
    assert inv.telemetry(K, "p", "a").online is True
