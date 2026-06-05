"""Tests for profile-driven register decoding."""

import struct

import pytest

from modbus_diagnostic_studio.profiles.decoder import (
    decode_profile_registers,
    decode_register_value,
    decoded_values_to_dict,
)
from modbus_diagnostic_studio.profiles.loader import load_builtin_profile


def float32_registers(value: float) -> list[int]:
    """Return big-endian Modbus registers for a float32 value."""
    return list(struct.unpack(">HH", struct.pack(">f", value)))


def test_decode_register_value_uint16() -> None:
    assert decode_register_value([123], "uint16") == 123


def test_decode_register_value_int16_negative() -> None:
    assert decode_register_value([0xFF85], "int16") == -123


def test_decode_register_value_uint32_normal() -> None:
    assert decode_register_value([0x1234, 0x5678], "uint32") == 0x12345678


def test_decode_register_value_uint32_swap() -> None:
    assert (
        decode_register_value([0x5678, 0x1234], "uint32", word_order="swap")
        == 0x12345678
    )


def test_decode_register_value_int32_negative() -> None:
    assert decode_register_value([0xFFFF, 0xFF85], "int32") == -123


def test_decode_register_value_float32_normal() -> None:
    assert decode_register_value(float32_registers(230.5), "float32") == pytest.approx(
        230.5
    )


def test_decode_register_value_float32_swap() -> None:
    registers = list(reversed(float32_registers(230.5)))

    assert decode_register_value(
        registers, "float32", word_order="swap"
    ) == pytest.approx(230.5)


def test_decode_register_value_applies_scale() -> None:
    assert decode_register_value([100], "uint16", scale=0.1) == pytest.approx(10.0)


def test_decode_register_value_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        decode_register_value([1], "string")


def test_decode_register_value_rejects_insufficient_registers() -> None:
    with pytest.raises(ValueError, match="requires"):
        decode_register_value([1], "float32")


def test_decode_profile_registers_generic_meter() -> None:
    profile = load_builtin_profile("generic_meter")
    registers = (
        float32_registers(230.5)
        + float32_registers(10.25)
        + float32_registers(1234.0)
        + float32_registers(50.0)
    )

    decoded = decode_profile_registers(profile, start_address=0, registers=registers)
    values = decoded_values_to_dict(decoded)

    assert values["voltage_l1_v"] == pytest.approx(230.5)
    assert values["current_l1_a"] == pytest.approx(10.25)
    assert values["power_total_w"] == pytest.approx(1234.0)
    assert values["frequency_hz"] == pytest.approx(50.0)


def test_decode_profile_registers_chint_dtsu71_key_values() -> None:
    profile = load_builtin_profile("chint_dtsu71")
    block_values = [
        1.25,
        2.5,
        3.75,
        230.5,
        231.5,
        232.5,
        231.5,
        399.0,
        400.0,
        401.0,
        400.0,
        50.0,
    ]
    registers: list[int] = []
    for value in block_values:
        registers.extend(float32_registers(value))

    decoded = decode_profile_registers(profile, start_address=2102, registers=registers)
    values = decoded_values_to_dict(decoded)

    assert values["current_l1_a"] == pytest.approx(1.25)
    assert values["current_l2_a"] == pytest.approx(2.5)
    assert values["current_l3_a"] == pytest.approx(3.75)
    assert values["voltage_ln_l1_v"] == pytest.approx(230.5)
    assert values["frequency_hz"] == pytest.approx(50.0)


def test_decode_profile_registers_omits_partial_value() -> None:
    profile = load_builtin_profile("generic_meter")
    registers = float32_registers(230.5) + [0x4124]

    decoded = decode_profile_registers(profile, start_address=0, registers=registers)
    values = decoded_values_to_dict(decoded)

    assert "voltage_l1_v" in values
    assert "current_l1_a" not in values


def test_decode_profile_registers_omits_out_of_block_value() -> None:
    profile = load_builtin_profile("generic_meter")
    registers = float32_registers(10.25)

    decoded = decode_profile_registers(profile, start_address=2, registers=registers)
    values = decoded_values_to_dict(decoded)

    assert "voltage_l1_v" not in values
    assert values["current_l1_a"] == pytest.approx(10.25)
