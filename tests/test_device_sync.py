import pytest
from aeronexus.device_sync import DeviceSyncError, parse_devices, register_devices
from aeronexus.inventory import Device, DeviceType, Inventory, Project
from aeronexus.providers import ProviderKind

PUBLIC = ProviderKind.PUBLIC_V2
ONPREM = ProviderKind.ONPREM_V2

def sample():
    return [{"device_id": "a1", "name": "Matrice", "kind": "aircraft"},
            {"device_id": "rc1", "name": "DJI RC", "kind": "controller"}]

def test_parse_aircraft_and_controller():
    devices = parse_devices(PUBLIC, "project", sample())
    assert [d.kind for d in devices] == [DeviceType.AIRCRAFT, DeviceType.CONTROLLER]

def test_register_devices():
    inventory = Inventory()
    inventory.add_project(Project(PUBLIC, "project", "Mission"))
    assert register_devices(inventory, parse_devices(PUBLIC, "project", sample())) == 2
    assert len(inventory.devices(PUBLIC, "project")) == 2

def test_provider_separation():
    inventory = Inventory()
    inventory.add_project(Project(PUBLIC, "p", "Public"))
    inventory.add_project(Project(ONPREM, "p", "On-prem"))
    register_devices(inventory, parse_devices(PUBLIC, "p", sample()))
    assert inventory.devices(ONPREM, "p") == ()

@pytest.mark.parametrize("kind", ["dock", "unknown", "", None, "DOCK"])
def test_reject_unsupported_types(kind):
    with pytest.raises(DeviceSyncError, match="Unsupported"):
        parse_devices(PUBLIC, "p", [{"device_id": "x", "name": "X", "kind": kind}])

def test_reject_duplicate_ids():
    with pytest.raises(DeviceSyncError, match="Duplicate"):
        parse_devices(PUBLIC, "p", [sample()[0], sample()[0]])

@pytest.mark.parametrize("records", ["not-a-list", None, {}, [42], [{"kind": "aircraft", "device_id": 4, "name": "Bad"}]])
def test_reject_bad_records(records):
    with pytest.raises(DeviceSyncError):
        parse_devices(PUBLIC, "p", records)

def test_reject_missing_project_without_partial_import():
    inventory = Inventory()
    with pytest.raises(DeviceSyncError, match="Project"):
        register_devices(inventory, parse_devices(PUBLIC, "p", sample()))
    assert inventory.devices() == ()

def test_reject_conflict_without_partial_import():
    inventory = Inventory()
    inventory.add_project(Project(PUBLIC, "p", "Mission"))
    inventory.add_device(Device(PUBLIC, "p", "rc1", DeviceType.CONTROLLER, "Old"))
    with pytest.raises(DeviceSyncError, match="Conflicting"):
        register_devices(inventory, parse_devices(PUBLIC, "p", sample()))
    assert len(inventory.devices()) == 1

def test_idempotent_import():
    inventory = Inventory()
    inventory.add_project(Project(PUBLIC, "p", "Mission"))
    devices = parse_devices(PUBLIC, "p", sample())
    register_devices(inventory, devices)
    register_devices(inventory, devices)
    assert len(inventory.devices()) == 2
