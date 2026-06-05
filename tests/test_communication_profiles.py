"""Tests for passive communication profile loading."""

import pytest

from modbus_diagnostic_studio.models.communication_profile import CommunicationProfile
from modbus_diagnostic_studio.sniffer.communication_profiles import (
    list_builtin_communication_profiles,
    load_builtin_communication_profile,
    load_communication_profile_from_dict,
)


def test_list_builtin_communication_profiles_includes_expected_profiles() -> None:
    profiles = list_builtin_communication_profiles()

    assert {
        "generic_modbus_rtu",
        "smartlogger_chint_dtsu71",
        "smartlogger_janitza_umg604",
        "inverter_meter_generic",
    }.issubset(set(profiles))


def test_load_builtin_generic_modbus_rtu() -> None:
    profile = load_builtin_communication_profile("generic_modbus_rtu")

    assert isinstance(profile, CommunicationProfile)
    assert profile.profile_id == "generic_modbus_rtu"
    assert profile.expected_functions == [3, 4]
    assert profile.expected_requests == []


def test_load_builtin_smartlogger_chint_dtsu71() -> None:
    profile = load_builtin_communication_profile("smartlogger_chint_dtsu71")

    assert profile.profile_id == "smartlogger_chint_dtsu71"
    assert profile.expected_slave_ids == [11]
    assert profile.linked_register_profile == "chint_dtsu71"


def test_expected_requests_for_dtsu71_profile() -> None:
    profile = load_builtin_communication_profile("smartlogger_chint_dtsu71")

    assert len(profile.expected_requests) == 2
    assert profile.expected_requests[0].address == 2102
    assert profile.expected_requests[0].quantity == 42
    assert profile.expected_requests[1].address == 2158
    assert profile.expected_requests[1].quantity == 66


def test_missing_builtin_profile_raises() -> None:
    with pytest.raises(ValueError, match="not found"):
        load_builtin_communication_profile("missing_profile")


def test_load_communication_profile_from_minimal_valid_dict() -> None:
    profile = load_communication_profile_from_dict(
        {
            "profile_id": "test_profile",
            "name": "Test Profile",
        }
    )

    assert profile.profile_id == "test_profile"
    assert profile.name == "Test Profile"
    assert profile.expected_requests == []
