"""Tests for Modbus register endian helpers."""

import pytest

from modbus_diagnostic_studio.core.endian import (
    registers_to_float32,
    registers_to_s16,
    registers_to_s32,
    registers_to_u16,
    registers_to_u32,
)


def test_registers_to_u16() -> None:
    assert registers_to_u16([0, 42, 65535]) == [0, 42, 65535]


def test_registers_to_s16_positive_and_negative() -> None:
    assert registers_to_s16([0x007B, 0xFF85]) == [123, -123]


def test_registers_to_u32_normal() -> None:
    assert registers_to_u32([0x1234, 0x5678]) == 0x12345678


def test_registers_to_u32_swap() -> None:
    assert registers_to_u32([0x5678, 0x1234], word_order="swap") == 0x12345678


def test_registers_to_s32_negative() -> None:
    assert registers_to_s32([0xFFFF, 0xFF85]) == -123


def test_registers_to_float32_normal() -> None:
    assert registers_to_float32([0x4366, 0x8000]) == pytest.approx(230.5)


def test_registers_to_float32_swap() -> None:
    assert registers_to_float32([0x8000, 0x4366], word_order="swap") == pytest.approx(230.5)


def test_registers_to_u32_rejects_invalid_word_order() -> None:
    with pytest.raises(ValueError, match="word_order"):
        registers_to_u32([0x1234, 0x5678], word_order="little")


def test_registers_reject_out_of_range_value() -> None:
    with pytest.raises(ValueError, match="range"):
        registers_to_u16([0x10000])
