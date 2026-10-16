import pytest
from aeronexus.inventory import Device, DeviceType, Inventory, Project
from aeronexus.providers import DeviceSnapshot, ProviderKind

PUBLIC = ProviderKind.PUBLIC_V2
ONPREM = ProviderKind.ONPREM_V2

def test_register_project_and_devices():
    inventory = Inventory()
    inventory.add_project(Project(PUBLIC, "p1", "Test"))
    inventory.add_device(Device(PUBLIC, "p1", "drone1", DeviceType.AIRCRAFT, "Matrice"))
    inventory.add_device(Device(PUBLIC, "p1", "dock1", DeviceType.DOCK, "Dock"))
    assert len(inventory.devices(PUBLIC, "p1")) == 2
    assert inventory.devices(ONPREM) == ()

def test_reject_device_without_project():
    with pytest.raises(ValueError, match="Project"):
        Inventory().add_device(Device(PUBLIC, "p1", "d1", DeviceType.DOCK, "Dock"))

def test_provider_isolation():
    inventory = Inventory()
    inventory.add_project(Project(PUBLIC, "same", "Public"))
    inventory.add_project(Project(ONPREM, "same", "Onprem"))
    inventory.add_device(Device(PUBLIC, "same", "same", DeviceType.AIRCRAFT, "A"))
    inventory.add_device(Device(ONPREM, "same", "same", DeviceType.DOCK, "B"))
    inventory.update_telemetry("same", DeviceSnapshot(PUBLIC, "same", online=True))
    assert inventory.telemetry(PUBLIC, "same", "same").online is True
    assert inventory.telemetry(ONPREM, "same", "same") is None

def test_reject_unknown_telemetry():
    with pytest.raises(ValueError, match="unknown device"):
        Inventory().update_telemetry("p1", DeviceSnapshot(PUBLIC, "missing"))

def test_reject_conflicting_project():
    inventory = Inventory()
    inventory.add_project(Project(PUBLIC, "p1", "First"))
    with pytest.raises(ValueError, match="Conflicting"):
        inventory.add_project(Project(PUBLIC, "p1", "Second"))

def test_reject_conflicting_device():
    inventory = Inventory()
    inventory.add_project(Project(PUBLIC, "p1", "First"))
    inventory.add_device(Device(PUBLIC, "p1", "d1", DeviceType.DOCK, "Dock"))
    with pytest.raises(ValueError, match="Conflicting"):
        inventory.add_device(Device(PUBLIC, "p1", "d1", DeviceType.AIRCRAFT, "Aircraft"))

@pytest.mark.parametrize("project_id,name", [("", "Name"), ("id", " "), (" ", "Name")])
def test_invalid_project(project_id, name):
    with pytest.raises(ValueError):
        Project(PUBLIC, project_id, name)

@pytest.mark.parametrize("project_id,device_id,name", [("", "d", "Name"), ("p", "", "Name"), ("p", "d", " ")])
def test_invalid_device(project_id, device_id, name):
    with pytest.raises(ValueError):
        Device(PUBLIC, project_id, device_id, DeviceType.DOCK, name)

def test_idempotent_registration():
    inventory = Inventory()
    project = Project(PUBLIC, "p1", "Name")
    device = Device(PUBLIC, "p1", "d1", DeviceType.DOCK, "Dock")
    inventory.add_project(project)
    inventory.add_project(project)
    inventory.add_device(device)
    inventory.add_device(device)
    assert len(inventory.projects()) == 1
    assert len(inventory.devices()) == 1
