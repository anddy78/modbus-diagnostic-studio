"""Tests for YAML profile loading."""

import pytest

from modbus_diagnostic_studio.models.profile import ProfileDefinition
from modbus_diagnostic_studio.profiles.loader import (
    list_builtin_profiles,
    load_builtin_profile,
    load_profile_from_dict,
)
from modbus_diagnostic_studio.profiles.validator import validate_profile


def minimal_profile_dict() -> dict:
    return {
        "profile_id": "test_meter",
        "name": "Test Meter",
        "registers": [
            {
                "variable": "voltage_l1_v",
                "address": 0,
                "type": "float32",
                "unit": "V",
            }
        ],
    }


def test_list_builtin_profiles_includes_expected_profiles() -> None:
    profiles = list_builtin_profiles()

    assert "generic_meter" in profiles
    assert "chint_dtsu71" in profiles


def test_load_builtin_generic_meter_returns_valid_profile() -> None:
    profile = load_builtin_profile("generic_meter")

    assert isinstance(profile, ProfileDefinition)
    assert profile.profile_id == "generic_meter"
    assert validate_profile(profile) == []


def test_load_builtin_chint_dtsu71_returns_valid_profile() -> None:
    profile = load_builtin_profile("chint_dtsu71")

    assert isinstance(profile, ProfileDefinition)
    assert profile.profile_id == "chint_dtsu71"
    assert profile.status == "observed_from_huawei_smartlogger"
    assert validate_profile(profile) == []


def test_load_profile_from_dict_minimal_valid_profile() -> None:
    profile = load_profile_from_dict(minimal_profile_dict())

    assert profile.profile_id == "test_meter"
    assert profile.name == "Test Meter"
    assert profile.default_function == 3
    assert len(profile.registers) == 1
    assert profile.registers[0].scale == 1.0


def test_load_profile_from_dict_missing_critical_field_raises() -> None:
    data = minimal_profile_dict()
    del data["profile_id"]

    with pytest.raises(ValueError, match="profile_id"):
        load_profile_from_dict(data)


def test_load_builtin_profile_missing_profile_raises() -> None:
    with pytest.raises(ValueError, match="not found"):
        load_builtin_profile("does_not_exist")
