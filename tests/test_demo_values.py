"""Tests for slave demo meter scenario helpers."""

from __future__ import annotations

import random
import struct

import pytest

from modbus_diagnostic_studio.models.profile import ProfileDefinition, RegisterDefinition
from modbus_diagnostic_studio.slave.demo_values import (
    MeterDemoScenario,
    MeterScenarioMode,
    apply_random_variation,
    build_demo_register_values,
    calculate_meter_values,
    classify_meter_variable,
    encode_demo_value_for_register,
    map_physical_value_for_register,
)


def test_classify_meter_variable_common_kinds() -> None:
    assert classify_meter_variable("voltage_ln_l1_v", unit="V") == "voltage_ln"
    assert classify_meter_variable("voltage_ll_l12_v", unit="V") == "voltage_ll"
    assert classify_meter_variable("current_l1_a", unit="A") == "current"
    assert classify_meter_variable("frequency_hz", unit="Hz") == "frequency"
    assert classify_meter_variable("power_factor_total", unit="") == "power_factor"
    assert classify_meter_variable("active_energy_import_total_kwh", unit="kWh") == "energy_import"
    assert classify_meter_variable("active_energy_export_total_kwh", unit="kWh") == "energy_export"


def test_apply_random_variation_is_deterministic_with_rng() -> None:
    rng = random.Random(123)

    varied = apply_random_variation(100.0, 2.0, rng=rng)

    assert varied == pytest.approx(98.20945439540378)


def test_encode_demo_value_for_float32() -> None:
    register = RegisterDefinition(variable="test_f32", address=0, type="float32")

    encoded = encode_demo_value_for_register(register, 1.5)
    packed = struct.pack(">f", 1.5)

    assert encoded == [
        int.from_bytes(packed[:2], "big"),
        int.from_bytes(packed[2:], "big"),
    ]


def test_single_phase_scenario_zeroes_other_phases() -> None:
    values = calculate_meter_values(
        MeterDemoScenario(
            mode=MeterScenarioMode.SINGLE_PHASE,
            total_active_power_w=2300.0,
        )
    )

    assert values.l1.active_power_w == pytest.approx(2300.0)
    assert values.l2.active_power_w == 0.0
    assert values.l3.active_power_w == 0.0


def test_three_phase_balanced_splits_power_evenly() -> None:
    values = calculate_meter_values(
        MeterDemoScenario(
            mode=MeterScenarioMode.THREE_PHASE_BALANCED,
            total_active_power_w=3000.0,
        )
    )

    assert values.l1.active_power_w == pytest.approx(1000.0)
    assert values.l2.active_power_w == pytest.approx(1000.0)
    assert values.l3.active_power_w == pytest.approx(1000.0)
    assert values.total_active_power_w == pytest.approx(3000.0)


def test_three_phase_unbalanced_keeps_total_but_varies_phases() -> None:
    values = calculate_meter_values(
        MeterDemoScenario(
            mode=MeterScenarioMode.THREE_PHASE_UNBALANCED,
            total_active_power_w=3000.0,
            imbalance_percent=20.0,
        )
    )

    assert values.total_active_power_w == pytest.approx(3000.0)
    assert len({values.l1.active_power_w, values.l2.active_power_w, values.l3.active_power_w}) > 1


def test_three_phase_single_phase_load_only_active_phase_has_current() -> None:
    values = calculate_meter_values(
        MeterDemoScenario(
            mode=MeterScenarioMode.THREE_PHASE_SINGLE_PHASE_LOAD,
            active_phase="L2",
            total_active_power_w=1800.0,
        )
    )

    assert values.l1.current_a == 0.0
    assert values.l2.active_power_w == pytest.approx(1800.0)
    assert values.l3.current_a == 0.0


def test_power_factor_reactive_and_apparent_are_coherent() -> None:
    values = calculate_meter_values(
        MeterDemoScenario(
            mode=MeterScenarioMode.SINGLE_PHASE,
            total_active_power_w=2300.0,
            power_factor=0.8,
        )
    )

    assert values.l1.apparent_power_va == pytest.approx(2875.0)
    assert values.l1.reactive_power_var > 0.0


def test_accumulate_energy_increases_import_energy() -> None:
    values = calculate_meter_values(
        MeterDemoScenario(
            mode=MeterScenarioMode.THREE_PHASE_BALANCED,
            total_active_power_w=3600.0,
            accumulate_energy=True,
            elapsed_seconds=3600.0,
            energy_import_kwh=100.0,
        )
    )

    assert values.energy_import_kwh == pytest.approx(103.6)


def test_map_physical_value_for_register_typical_names() -> None:
    meter_values = calculate_meter_values(
        MeterDemoScenario(mode=MeterScenarioMode.THREE_PHASE_BALANCED)
    )
    register = RegisterDefinition(
        variable="voltage_ll_l23_v",
        address=10,
        type="float32",
        unit="V",
    )

    mapped = map_physical_value_for_register(register, meter_values)

    assert mapped == pytest.approx(meter_values.l2.voltage_ll)


def test_build_demo_register_values_with_fake_profile_and_scenario() -> None:
    profile = ProfileDefinition(
        profile_id="demo_meter",
        name="Demo Meter",
        default_function=4,
        registers=[
            RegisterDefinition(variable="voltage_l1_v", address=0, type="float32", unit="V"),
            RegisterDefinition(variable="current_l1_a", address=2, type="float32", unit="A"),
            RegisterDefinition(variable="power_total_w", address=4, type="float32", unit="W"),
            RegisterDefinition(variable="mystery_value", address=6, type="float32"),
        ],
    )

    result = build_demo_register_values(
        profile,
        scenario=MeterDemoScenario(mode=MeterScenarioMode.SINGLE_PHASE, total_active_power_w=2300.0),
        variation_percent=0.0,
        rng=random.Random(1),
    )

    assert result.generated_count == 6
    assert result.skipped_count == 1
    assert result.warnings == []
    assert ("Input Registers", 0) in result.values
    assert ("Input Registers", 5) in result.values
