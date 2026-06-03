"""Endian and word-order helpers for Modbus registers."""

from __future__ import annotations

import struct


def _validate_register(register: int) -> int:
    if not 0 <= register <= 0xFFFF:
        raise ValueError("Register values must be in range 0..65535")
    return register


def _validate_registers(registers: list[int]) -> list[int]:
    return [_validate_register(register) for register in registers]


def _ordered_pair(registers: list[int], word_order: str) -> list[int]:
    values = _validate_registers(registers)
    if len(values) != 2:
        raise ValueError("Exactly 2 registers are required")
    if word_order == "normal":
        return values
    if word_order == "swap":
        return [values[1], values[0]]
    raise ValueError("word_order must be 'normal' or 'swap'")


def registers_to_u16(registers: list[int]) -> list[int]:
    """Return validated unsigned 16-bit register values."""
    return _validate_registers(registers)


def registers_to_s16(registers: list[int]) -> list[int]:
    """Return register values interpreted as signed 16-bit integers."""
    values = _validate_registers(registers)
    return [value - 0x10000 if value & 0x8000 else value for value in values]


def registers_to_u32(registers: list[int], word_order: str = "normal") -> int:
    """Return two registers interpreted as one unsigned 32-bit integer."""
    high, low = _ordered_pair(registers, word_order)
    return (high << 16) | low


def registers_to_s32(registers: list[int], word_order: str = "normal") -> int:
    """Return two registers interpreted as one signed 32-bit integer."""
    value = registers_to_u32(registers, word_order)
    return value - 0x100000000 if value & 0x80000000 else value


def registers_to_float32(registers: list[int], word_order: str = "normal") -> float:
    """Return two registers interpreted as one IEEE 754 float32."""
    ordered = _ordered_pair(registers, word_order)
    data = b"".join(register.to_bytes(2, "big") for register in ordered)
    return struct.unpack(">f", data)[0]
