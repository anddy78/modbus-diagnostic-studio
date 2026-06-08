"""Tests for slave demo value generation helpers."""

from __future__ import annotations

import random
import struct

import pytest

from modbus_diagnostic_studio.models.profile import ProfileDefinition, RegisterDefinition
from modbus_diagnostic_studio.slave.demo_values import (
    apply_random_variation,
    build_demo_register_values,
    classify_meter_variable,
    encode_demo_value_for_register,
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


def test_apply_random_variation_zero_percent_is_stable() -> None:
    assert apply_random_variation(50.0, 0.0, rng=random.Random(1)) == 50.0


def test_encode_demo_value_for_uint16() -> None:
    register = RegisterDefinition(variable="test_u16", address=0, type="uint16", scale=0.1)

    assert encode_demo_value_for_register(register, 23.0) == [230]


def test_encode_demo_value_for_int16() -> None:
    register = RegisterDefinition(variable="test_i16", address=0, type="int16")

    assert encode_demo_value_for_register(register, -1.0) == [0xFFFF]


def test_encode_demo_value_for_uint32() -> None:
    register = RegisterDefinition(variable="test_u32", address=0, type="uint32")

    assert encode_demo_value_for_register(register, 65538.0) == [0x0001, 0x0002]


def test_encode_demo_value_for_float32() -> None:
    register = RegisterDefinition(variable="test_f32", address=0, type="float32")

    encoded = encode_demo_value_for_register(register, 1.5)
    packed = struct.pack(">f", 1.5)

    assert encoded == [
        int.from_bytes(packed[:2], "big"),
        int.from_bytes(packed[2:], "big"),
    ]


def test_build_demo_register_values_with_fake_profile() -> None:
    profile = ProfileDefinition(
        profile_id="demo_meter",
        name="Demo Meter",
        default_function=4,
        registers=[
            RegisterDefinition(variable="voltage_l1_v", address=0, type="float32", unit="V"),
            RegisterDefinition(variable="current_l1_a", address=2, type="float32", unit="A"),
            RegisterDefinition(variable="mystery_value", address=4, type="float32"),
        ],
    )

    result = build_demo_register_values(profile, variation_percent=0.0, rng=random.Random(1))

    assert result.generated_count == 4
    assert result.skipped_count == 1
    assert result.warnings == []
    assert ("Input Registers", 0) in result.values
    assert ("Input Registers", 3) in result.values
