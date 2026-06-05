"""Tests for profile read plan building."""

import pytest

from modbus_diagnostic_studio.master.read_plan import build_read_plan
from modbus_diagnostic_studio.models.profile import ProfileDefinition, RegisterDefinition
from modbus_diagnostic_studio.profiles.loader import load_builtin_profile


def test_generic_meter_generates_single_block() -> None:
    profile = load_builtin_profile("generic_meter")

    plan = build_read_plan(profile)

    assert len(plan) == 1
    assert plan[0].function_code == 3
    assert plan[0].start_address == 0
    assert plan[0].quantity == 8
    assert plan[0].variables == [
        "voltage_l1_v",
        "current_l1_a",
        "power_total_w",
        "frequency_hz",
    ]


def test_chint_dtsu71_splits_instantaneous_and_energy_blocks() -> None:
    profile = load_builtin_profile("chint_dtsu71")

    plan = build_read_plan(profile)

    assert len(plan) >= 2
    assert plan[0].start_address == 2102
    assert plan[0].quantity == 42
    assert "current_l1_a" in plan[0].variables
    assert "apparent_total_va" in plan[0].variables
    assert plan[1].start_address == 2158
    assert "active_energy_net_total_kwh" in plan[1].variables


def test_max_registers_per_request_splits_blocks() -> None:
    profile = ProfileDefinition(
        profile_id="small_blocks",
        name="Small Blocks",
        max_registers_per_request=4,
        registers=[
            RegisterDefinition(variable="a", address=0, type="float32"),
            RegisterDefinition(variable="b", address=2, type="float32"),
            RegisterDefinition(variable="c", address=4, type="float32"),
        ],
    )

    plan = build_read_plan(profile)

    assert [(block.start_address, block.quantity) for block in plan] == [(0, 4), (4, 2)]
    assert plan[0].variables == ["a", "b"]
    assert plan[1].variables == ["c"]


def test_empty_profile_returns_empty_plan() -> None:
    profile = ProfileDefinition(profile_id="empty", name="Empty")

    assert build_read_plan(profile) == []


def test_invalid_register_type_raises() -> None:
    profile = ProfileDefinition(
        profile_id="invalid",
        name="Invalid",
        registers=[RegisterDefinition(variable="bad", address=0, type="string")],
    )

    with pytest.raises(ValueError, match="Unsupported"):
        build_read_plan(profile)


def test_duplicate_variables_are_not_repeated() -> None:
    profile = ProfileDefinition(
        profile_id="duplicates",
        name="Duplicates",
        registers=[
            RegisterDefinition(variable="a", address=0, type="uint16"),
            RegisterDefinition(variable="a", address=1, type="uint16"),
        ],
    )

    plan = build_read_plan(profile)

    assert plan[0].variables == ["a"]
    assert plan[0].quantity == 1
