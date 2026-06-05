"""Tests for YAML profile loading."""

import pytest

from modbus_diagnostic_studio.models.profile import ProfileDefinition
from modbus_diagnostic_studio.profiles.loader import (
    list_builtin_profiles,
    load_builtin_profile,
    load_profile_from_dict,
)
from modbus_diagnostic_studio.profiles.validator import validate_profile

EXPECTED_BUILTIN_PROFILES = {
    "generic_meter",
    "chint_dtsu71",
    "eastron_sdm630",
    "eastron_sdm230",
    "janitza_umg604",
    "dtsu666",
}


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

    assert EXPECTED_BUILTIN_PROFILES.issubset(set(profiles))


@pytest.mark.parametrize("profile_id", sorted(EXPECTED_BUILTIN_PROFILES))
def test_load_expected_builtin_returns_valid_profile(profile_id: str) -> None:
    profile = load_builtin_profile(profile_id)

    assert isinstance(profile, ProfileDefinition)
    assert profile.profile_id == profile_id
    assert validate_profile(profile) == []


def test_load_builtin_chint_dtsu71_returns_valid_profile() -> None:
    profile = load_builtin_profile("chint_dtsu71")

    assert isinstance(profile, ProfileDefinition)
    assert profile.profile_id == "chint_dtsu71"
    assert profile.status == "observed_from_huawei_smartlogger"
    assert validate_profile(profile) == []


@pytest.mark.parametrize(
    ("profile_id", "expected_status"),
    [
        ("eastron_sdm630", "partial_imported_from_bridge"),
        ("eastron_sdm230", "partial_imported_from_bridge"),
        ("janitza_umg604", "imported_from_bridge"),
        ("dtsu666", "partial_imported_from_bridge"),
    ],
)
def test_reference_profiles_imported_from_bridge_have_expected_status(
    profile_id: str,
    expected_status: str,
) -> None:
    profile = load_builtin_profile(profile_id)

    assert profile.status == expected_status
    assert profile.registers


@pytest.mark.parametrize(
    ("profile_id", "variable", "address", "unit"),
    [
        ("eastron_sdm630", "voltage_ln_l1_v", 0, "V"),
        ("eastron_sdm630", "energy_total_wh", 342, "kWh"),
        ("eastron_sdm230", "current_l1_a", 6, "A"),
        ("eastron_sdm230", "energy_total_wh", 342, "kWh"),
        ("janitza_umg604", "voltage_ln_l1_v", 19000, "V"),
        ("janitza_umg604", "energy_export_total_wh", 19076, "Wh"),
        ("dtsu666", "voltage_ll_l12_v", 8192, "V"),
        ("dtsu666", "energy_export_total_wh", 4136, "kWh"),
        ("chint_dtsu71", "current_l1_a", 2102, "A"),
        ("chint_dtsu71", "reactive_energy_negative_total_kvarh", 2222, "kvarh"),
    ],
)
def test_imported_profiles_include_key_registers(
    profile_id: str,
    variable: str,
    address: int,
    unit: str,
) -> None:
    profile = load_builtin_profile(profile_id)
    registers = {register.variable: register for register in profile.registers}

    assert variable in registers
    assert registers[variable].address == address
    assert registers[variable].unit == unit


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
