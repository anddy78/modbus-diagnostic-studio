"""Tests for profile validation."""

from dataclasses import replace

from modbus_diagnostic_studio.models.profile import (
    ProfileDefinition,
    RegisterDefinition,
)
from modbus_diagnostic_studio.profiles.loader import load_builtin_profile
from modbus_diagnostic_studio.profiles.validator import validate_profile


def valid_profile() -> ProfileDefinition:
    return ProfileDefinition(
        profile_id="test_profile",
        name="Test Profile",
        registers=[
            RegisterDefinition(
                variable="voltage_l1_v",
                address=0,
                type="float32",
                unit="V",
            )
        ],
    )


def test_generic_meter_builtin_has_no_validation_errors() -> None:
    assert validate_profile(load_builtin_profile("generic_meter")) == []


def test_chint_dtsu71_builtin_has_no_validation_errors() -> None:
    assert validate_profile(load_builtin_profile("chint_dtsu71")) == []


def test_empty_profile_id_generates_error() -> None:
    errors = validate_profile(replace(valid_profile(), profile_id=""))

    assert any("profile_id" in error for error in errors)


def test_invalid_default_function_generates_error() -> None:
    errors = validate_profile(replace(valid_profile(), default_function=6))

    assert any("default_function" in error for error in errors)


def test_invalid_word_order_generates_error() -> None:
    errors = validate_profile(replace(valid_profile(), word_order="little"))

    assert any("word_order" in error for error in errors)


def test_invalid_register_type_generates_error() -> None:
    profile = replace(
        valid_profile(),
        registers=[
            RegisterDefinition(
                variable="voltage_l1_v",
                address=0,
                type="string",
            )
        ],
    )

    errors = validate_profile(profile)

    assert any("type" in error for error in errors)


def test_duplicate_variable_generates_error() -> None:
    profile = replace(
        valid_profile(),
        registers=[
            RegisterDefinition(variable="voltage_l1_v", address=0, type="float32"),
            RegisterDefinition(variable="voltage_l1_v", address=2, type="float32"),
        ],
    )

    errors = validate_profile(profile)

    assert any("duplicate variable" in error for error in errors)


def test_duplicate_address_generates_error() -> None:
    profile = replace(
        valid_profile(),
        registers=[
            RegisterDefinition(variable="voltage_l1_v", address=0, type="float32"),
            RegisterDefinition(variable="current_l1_a", address=0, type="float32"),
        ],
    )

    errors = validate_profile(profile)

    assert any("duplicate address" in error for error in errors)
