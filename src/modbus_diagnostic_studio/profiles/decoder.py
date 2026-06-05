"""Profile-driven Modbus register decoding."""

from __future__ import annotations

from dataclasses import dataclass

from modbus_diagnostic_studio.core.endian import (
    registers_to_float32,
    registers_to_s16,
    registers_to_s32,
    registers_to_u16,
    registers_to_u32,
)
from modbus_diagnostic_studio.models.profile import ProfileDefinition


@dataclass(frozen=True)
class DecodedProfileValue:
    """A decoded value from a profile register definition."""

    variable: str
    value: int | float
    unit: str | None
    address: int
    type: str
    scale: float
    description: str


_REGISTERS_REQUIRED = {
    "uint16": 1,
    "int16": 1,
    "uint32": 2,
    "int32": 2,
    "float32": 2,
}


def _required_registers(value_type: str) -> int:
    if value_type not in _REGISTERS_REQUIRED:
        raise ValueError(f"Unsupported profile value type: {value_type}")
    return _REGISTERS_REQUIRED[value_type]


def _apply_scale(value: int | float, scale: float) -> int | float:
    if scale == 1:
        return value
    return value * scale


def decode_register_value(
    registers: list[int],
    value_type: str,
    scale: float = 1.0,
    word_order: str = "normal",
) -> int | float:
    """Decode one typed profile value from Modbus registers."""
    required = _required_registers(value_type)
    if len(registers) < required:
        raise ValueError(
            f"{value_type} requires {required} register(s), got {len(registers)}"
        )

    selected = registers[:required]
    if value_type == "uint16":
        value: int | float = registers_to_u16(selected)[0]
    elif value_type == "int16":
        value = registers_to_s16(selected)[0]
    elif value_type == "uint32":
        value = registers_to_u32(selected, word_order=word_order)
    elif value_type == "int32":
        value = registers_to_s32(selected, word_order=word_order)
    elif value_type == "float32":
        value = registers_to_float32(selected, word_order=word_order)
    else:
        raise ValueError(f"Unsupported profile value type: {value_type}")

    return _apply_scale(value, scale)


def decode_profile_registers(
    profile: ProfileDefinition,
    start_address: int,
    registers: list[int],
) -> list[DecodedProfileValue]:
    """Decode all complete profile values contained in a register block."""
    decoded: list[DecodedProfileValue] = []
    end_address = start_address + len(registers)

    for definition in sorted(profile.registers, key=lambda item: item.address):
        try:
            required = _required_registers(definition.type)
        except ValueError:
            raise ValueError(
                f"Unsupported type for {definition.variable}: {definition.type}"
            )

        value_start = definition.address
        value_end = value_start + required
        if value_start < start_address or value_end > end_address:
            continue

        offset = value_start - start_address
        raw_registers = registers[offset : offset + required]
        value = decode_register_value(
            raw_registers,
            definition.type,
            scale=definition.scale,
            word_order=profile.word_order,
        )
        decoded.append(
            DecodedProfileValue(
                variable=definition.variable,
                value=value,
                unit=definition.unit,
                address=definition.address,
                type=definition.type,
                scale=definition.scale,
                description=definition.description,
            )
        )

    return decoded


def decoded_values_to_dict(values: list[DecodedProfileValue]) -> dict[str, int | float]:
    """Return a variable-to-value dictionary for decoded profile values."""
    return {value.variable: value.value for value in values}
