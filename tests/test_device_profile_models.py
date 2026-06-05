"""Tests for device profile dataclasses."""

from modbus_diagnostic_studio.models.device_profile import (
    DeviceProfileDefinition,
    DeviceProfileRoleLink,
    DeviceRole,
)


def test_device_profile_role_link_defaults() -> None:
    role_link = DeviceProfileRoleLink(
        role=DeviceRole.SLAVE,
        profile_id="generic_meter",
        profile_type="register_profile",
    )

    assert role_link.role == "slave"
    assert role_link.profile_id == "generic_meter"
    assert role_link.profile_type == "register_profile"
    assert role_link.description == ""
    assert role_link.enabled is True


def test_device_profile_definition_defaults_and_roles() -> None:
    role_link = DeviceProfileRoleLink(
        role=DeviceRole.MASTER,
        profile_id="inverter_meter_generic",
        profile_type="communication_profile",
        description="Demo master role",
    )
    profile = DeviceProfileDefinition(
        device_id="generic_inverter_demo",
        name="Generic Inverter Demo",
        roles=[role_link],
    )

    assert profile.device_id == "generic_inverter_demo"
    assert profile.name == "Generic Inverter Demo"
    assert profile.device_type == "generic"
    assert profile.tags == []
    assert len(profile.roles) == 1
    assert profile.roles[0].description == "Demo master role"
    assert profile.source == "unknown"
    assert profile.status == "draft"
