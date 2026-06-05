"""Device profile models for role-oriented Modbus device definitions."""

from __future__ import annotations

from dataclasses import dataclass, field


class DeviceRole:
    """Common device role identifiers."""

    SLAVE = "slave"
    MASTER = "master"
    MASTER_TARGET = "master_target"
    DASHBOARD = "dashboard"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True)
class DeviceProfileRoleLink:
    """Link one device role to a concrete profile definition."""

    role: str
    profile_id: str
    profile_type: str
    description: str = ""
    enabled: bool = True


@dataclass(frozen=True)
class DeviceProfileDefinition:
    """A physical or logical device with one or more Modbus-facing roles."""

    device_id: str
    name: str
    manufacturer: str = ""
    model: str = ""
    device_type: str = "generic"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    roles: list[DeviceProfileRoleLink] = field(default_factory=list)
    source: str = "unknown"
    status: str = "draft"
    notes: str = ""
