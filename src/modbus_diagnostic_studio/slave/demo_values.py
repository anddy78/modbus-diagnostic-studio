"""Helpers for generating demo meter values in the local slave datastore."""

from __future__ import annotations

from dataclasses import dataclass, field
import random
import struct
from typing import Any

from modbus_diagnostic_studio.gui.profile_views import bank_for_function


@dataclass(frozen=True)
class DemoValueBuildResult:
    """Built raw register values plus summary metadata."""

    values: dict[tuple[str, int], int]
    generated_count: int
    skipped_count: int
    warnings: list[str] = field(default_factory=list)


def classify_meter_variable(
    variable: str,
    description: str = "",
    unit: str = "",
) -> str:
    """Classify a profile register into a meter-oriented semantic bucket."""
    text = " ".join((variable, description, unit)).lower()

    if "voltage" in text:
        if any(token in text for token in ("ll", "line-line", "l12", "l23", "l31")):
            return "voltage_ll"
        return "voltage_ln"
    if "current" in text or unit.lower() == "a":
        return "current"
    if "frequency" in text or unit.lower() == "hz":
        return "frequency"
    if any(token in text for token in ("power_factor", "pf_", " pf", "factor")):
        return "power_factor"
    if "apparent" in text or unit.lower() == "va":
        return "apparent_power"
    if "reactive" in text or unit.lower() == "var":
        return "reactive_power"
    if "power" in text or unit.lower() == "w":
        return "active_power"
    if "energy" in text:
        if "export" in text or "negative" in text:
            return "energy_export"
        return "energy_import"
    return "unknown"


def demo_value_for_class(kind: str, phase_index: int = 0) -> float | None:
    """Return one reasonable demo physical value for a semantic class."""
    voltage_ln_values = [228.0, 229.0, 227.5]
    voltage_ll_values = [395.0, 397.0, 394.0]
    current_values = [5.0, 4.7, 5.3]

    if kind == "voltage_ln":
        return voltage_ln_values[phase_index % len(voltage_ln_values)]
    if kind == "voltage_ll":
        return voltage_ll_values[phase_index % len(voltage_ll_values)]
    if kind == "current":
        return current_values[phase_index % len(current_values)]
    if kind == "active_power":
        return 1100.0 if phase_index >= 0 else 3300.0
    if kind == "reactive_power":
        return 250.0
    if kind == "apparent_power":
        return 1150.0 if phase_index >= 0 else 3450.0
    if kind == "power_factor":
        return 0.97
    if kind == "frequency":
        return 50.0
    if kind == "energy_import":
        return 1234.5
    if kind == "energy_export":
        return 0.0
    return None


def apply_random_variation(
    value: float,
    percent: float,
    rng: random.Random | None = None,
) -> float:
    """Apply a deterministic-friendly uniform variation around *value*."""
    if percent <= 0:
        return value
    generator = rng or random.Random()
    fraction = generator.uniform(-percent / 100.0, percent / 100.0)
    return value * (1.0 + fraction)


def encode_demo_value_for_register(
    register: Any,
    value: float,
    word_order: str = "normal",
) -> list[int]:
    """Encode one physical value back into raw Modbus register words."""
    scale = getattr(register, "scale", 1.0) or 1.0
    raw_value = value / scale
    register_type = getattr(register, "type", "")
    selected_word_order = getattr(register, "word_order", word_order)

    if register_type == "uint16":
        return [_clamp_u16(int(round(raw_value)))]
    if register_type == "int16":
        return [_encode_int16(int(round(raw_value)))]
    if register_type == "uint32":
        return _split_u32(int(round(raw_value)), selected_word_order)
    if register_type == "int32":
        return _split_u32(_encode_int32_value(int(round(raw_value))), selected_word_order)
    if register_type == "float32":
        packed = struct.pack(">f", float(raw_value))
        registers = [
            int.from_bytes(packed[:2], "big"),
            int.from_bytes(packed[2:], "big"),
        ]
        if selected_word_order == "swap":
            return [registers[1], registers[0]]
        return registers
    raise ValueError(f"Unsupported register type for demo encoding: {register_type}")


def build_demo_register_values(
    profile: Any,
    variation_percent: float = 0.0,
    rng: random.Random | None = None,
) -> DemoValueBuildResult:
    """Build raw register words for meter-like values in *profile*."""
    values: dict[tuple[str, int], int] = {}
    generated_count = 0
    skipped_count = 0
    warnings: list[str] = []
    generator = rng or random.Random()
    function_code = int(getattr(profile, "default_function", 3) or 3)
    bank_name = bank_for_function(function_code)
    profile_word_order = getattr(profile, "word_order", "normal")

    for register in getattr(profile, "registers", []):
        kind = classify_meter_variable(
            getattr(register, "variable", ""),
            getattr(register, "description", ""),
            getattr(register, "unit", "") or "",
        )
        if kind == "unknown":
            skipped_count += 1
            continue
        phase_index = _phase_index_for_variable(getattr(register, "variable", ""))
        demo_value = demo_value_for_class(kind, phase_index)
        if demo_value is None:
            skipped_count += 1
            continue
        if kind in {"active_power", "apparent_power"} and _is_total_variable(register.variable):
            demo_value = 3300.0 if kind == "active_power" else 3450.0
        elif kind in {"active_power", "apparent_power"}:
            demo_value = 1100.0 if kind == "active_power" else 1150.0

        try:
            varied_value = apply_random_variation(
                demo_value,
                variation_percent,
                rng=generator,
            )
            encoded = encode_demo_value_for_register(
                register,
                varied_value,
                word_order=profile_word_order,
            )
        except Exception as exc:
            skipped_count += 1
            warnings.append(f"{register.variable}: {exc}")
            continue

        for offset, raw_word in enumerate(encoded):
            values[(bank_name, int(register.address) + offset)] = raw_word
            generated_count += 1

    return DemoValueBuildResult(
        values=values,
        generated_count=generated_count,
        skipped_count=skipped_count,
        warnings=warnings,
    )


def _phase_index_for_variable(variable: str) -> int:
    name = variable.lower()
    if any(token in name for token in ("l2", "_b", "phase_b")):
        return 1
    if any(token in name for token in ("l3", "_c", "phase_c")):
        return 2
    if _is_total_variable(name):
        return -1
    return 0


def _is_total_variable(variable: str) -> bool:
    name = variable.lower()
    return "total" in name or "avg" in name or "net" in name


def _clamp_u16(value: int) -> int:
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"uint16 value out of range: {value}")
    return value


def _encode_int16(value: int) -> int:
    if not -0x8000 <= value <= 0x7FFF:
        raise ValueError(f"int16 value out of range: {value}")
    return value & 0xFFFF


def _encode_int32_value(value: int) -> int:
    if not -0x80000000 <= value <= 0x7FFFFFFF:
        raise ValueError(f"int32 value out of range: {value}")
    return value & 0xFFFFFFFF


def _split_u32(value: int, word_order: str) -> list[int]:
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"uint32 value out of range: {value}")
    registers = [(value >> 16) & 0xFFFF, value & 0xFFFF]
    if word_order == "swap":
        return [registers[1], registers[0]]
    return registers
