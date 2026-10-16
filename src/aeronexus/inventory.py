"""Read-only, provider-scoped inventory for aircraft and controllers only.

DJI Dock hardware is deliberately excluded from this project.
"""
from dataclasses import dataclass, field
from enum import StrEnum
from .providers import DeviceSnapshot, ProviderKind

class DeviceType(StrEnum):
    AIRCRAFT = "aircraft"
    CONTROLLER = "controller"

@dataclass(frozen=True)
class Project:
    provider: ProviderKind
    project_id: str
    name: str

    def __post_init__(self):
        if not self.project_id.strip() or not self.name.strip():
            raise ValueError("Project ID and name must not be blank")

@dataclass(frozen=True)
class Device:
    provider: ProviderKind
    project_id: str
    device_id: str
    kind: DeviceType
    name: str

    def __post_init__(self):
        if not self.project_id.strip() or not self.device_id.strip() or not self.name.strip():
            raise ValueError("Device identity and name must not be blank")
        if not isinstance(self.kind, DeviceType):
            raise ValueError("Only aircraft and controllers are supported")

@dataclass
class Inventory:
    _projects: dict[tuple[ProviderKind, str], Project] = field(default_factory=dict, repr=False)
    _devices: dict[tuple[ProviderKind, str, str], Device] = field(default_factory=dict, repr=False)
    _telemetry: dict[tuple[ProviderKind, str, str], DeviceSnapshot] = field(default_factory=dict, repr=False)

    def add_project(self, project: Project) -> None:
        key = (project.provider, project.project_id)
        if key in self._projects and self._projects[key] != project:
            raise ValueError("Conflicting project identity")
        self._projects[key] = project

    def add_device(self, device: Device) -> None:
        if (device.provider, device.project_id) not in self._projects:
            raise ValueError("Project must be registered before device")
        key = (device.provider, device.project_id, device.device_id)
        if key in self._devices and self._devices[key] != device:
            raise ValueError("Conflicting device identity")
        self._devices[key] = device

    def update_telemetry(self, project_id: str, snapshot: DeviceSnapshot) -> None:
        key = (snapshot.provider, project_id, snapshot.device_id)
        if key not in self._devices:
            raise ValueError("Telemetry references unknown device")
        self._telemetry[key] = snapshot

    def projects(self, provider: ProviderKind | None = None) -> tuple[Project, ...]:
        return tuple(p for p in self._projects.values() if provider is None or p.provider == provider)

    def devices(self, provider: ProviderKind | None = None, project_id: str | None = None) -> tuple[Device, ...]:
        return tuple(d for d in self._devices.values()
                     if (provider is None or d.provider == provider)
                     and (project_id is None or d.project_id == project_id))

    def telemetry(self, provider: ProviderKind, project_id: str, device_id: str) -> DeviceSnapshot | None:
        return self._telemetry.get((provider, project_id, device_id))
