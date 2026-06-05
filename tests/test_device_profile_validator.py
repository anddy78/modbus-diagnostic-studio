"""Tests for device profile validation."""

from dataclasses import replace

from modbus_diagnostic_studio.device_profiles.validator import (
    validate_device_profile,
    validate_role_links,
)
from modbus_diagnostic_studio.models.device_profile import (
    DeviceProfileDefinition,
    DeviceProfileRoleLink,
)


def valid_device_profile() -> DeviceProfileDefinition:
    return DeviceProfileDefinition(
        device_id="sample_meter",
        name="Sample Meter",
        device_type="meter",
        roles=[
            DeviceProfileRoleLink(
                role="slave",
                profile_id="generic_meter",
                profile_type="register_profile",
            )
        ],
    )


def test_profile_without_device_id_produces_error() -> None:
    messages = validate_device_profile(replace(valid_device_profile(), device_id=""))

    assert any(message.startswith("ERROR:") and "device_id" in message for message in messages)


def test_profile_without_roles_produces_warning() -> None:
    messages = validate_device_profile(replace(valid_device_profile(), roles=[]))

    assert any(message.startswith("WARNING:") and "no role links" in message for message in messages)


def test_enabled_role_without_profile_id_produces_clear_error() -> None:
    profile = replace(
        valid_device_profile(),
        roles=[DeviceProfileRoleLink(role="slave", profile_id="", profile_type="register_profile")],
    )

    messages = validate_role_links(profile)

    assert any(message.startswith("ERROR:") and "profile_id" in message for message in messages)


def test_disabled_empty_role_is_non_blocking_warning() -> None:
    profile = replace(
        valid_device_profile(),
        roles=[
            DeviceProfileRoleLink(
                role="slave",
                profile_id="",
                profile_type="register_profile",
                enabled=False,
            )
        ],
    )

    messages = validate_role_links(profile)

    assert any(message.startswith("WARNING:") and "disabled" in message for message in messages)


def test_existing_register_profile_link_is_ok() -> None:
    messages = validate_role_links(
        valid_device_profile(),
        available_register_profile_ids={"generic_meter"},
    )

    assert messages == []


def test_missing_communication_profile_link_produces_warning() -> None:
    profile = replace(
        valid_device_profile(),
        roles=[
            DeviceProfileRoleLink(
                role="master",
                profile_id="missing_comm_profile",
                profile_type="communication_profile",
            )
        ],
    )

    messages = validate_role_links(
        profile,
        available_communication_profile_ids={"smartlogger_chint_dtsu71"},
    )

    assert any(
        message.startswith("WARNING:") and "missing_comm_profile" in message
        for message in messages
    )
