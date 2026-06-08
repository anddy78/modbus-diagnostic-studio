"""Helpers for generating coherent demo meter values in the local slave datastore."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
import struct
from typing import Any

from modbus_diagnostic_studio.gui.profile_views import bank_for_function


class MeterScenarioMode:
    """Supported high-level electrical scenarios for demo meter generation."""

    SINGLE_PHASE = "single_phase"
    THREE_PHASE_BALANCED = "three_phase_balanced"
    THREE_PHASE_UNBALANCED = "three_phase_unbalanced"
    THREE_PHASE_SINGLE_PHASE_LOAD = "three_phase_single_phase_load"


@dataclass(frozen=True)
class MeterDemoScenario:
    """User-editable scenario for coherent meter demo values."""

    mode: str = MeterScenarioMode.THREE_PHASE_BALANCED
    active_phase: str = "L1"
    voltage_ln: float = 230.0
    frequency_hz: float = 50.0
    total_active_power_w: float = 3000.0
    power_factor: float = 0.98
    phase_l1_power_w: float | None = None
    phase_l2_power_w: float | None = None
    phase_l3_power_w: float | None = None
    imbalance_percent: float = 10.0
    energy_import_kwh: float = 1234.5
    energy_export_kwh: float = 0.0
    accumulate_energy: bool = False
    elapsed_seconds: float = 0.0

    def validate(self) -> None:
        if self.voltage_ln <= 0:
            raise ValueError("voltage_ln must be > 0")
        if self.frequency_hz <= 0:
            raise ValueError("frequency_hz must be > 0")
        if self.total_active_power_w < 0:
            raise ValueError("total_active_power_w must be >= 0")
        if not 0.1 <= self.power_factor <= 1.0:
            raise ValueError("power_factor must be in range 0.1..1.0")
        if self.imbalance_percent < 0:
            raise ValueError("imbalance_percent must be >= 0")
        if self.active_phase not in {"L1", "L2", "L3"}:
            raise ValueError("active_phase must be L1, L2, or L3")
        if self.mode not in {
            MeterScenarioMode.SINGLE_PHASE,
            MeterScenarioMode.THREE_PHASE_BALANCED,
            MeterScenarioMode.THREE_PHASE_UNBALANCED,
            MeterScenarioMode.THREE_PHASE_SINGLE_PHASE_LOAD,
        }:
            raise ValueError(f"Unsupported meter scenario mode: {self.mode}")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary for this scenario."""
        return {
            "mode": self.mode,
            "active_phase": self.active_phase,
            "voltage_ln": self.voltage_ln,
            "frequency_hz": self.frequency_hz,
            "total_active_power_w": self.total_active_power_w,
            "power_factor": self.power_factor,
            "phase_l1_power_w": self.phase_l1_power_w,
            "phase_l2_power_w": self.phase_l2_power_w,
            "phase_l3_power_w": self.phase_l3_power_w,
            "imbalance_percent": self.imbalance_percent,
            "energy_import_kwh": self.energy_import_kwh,
            "energy_export_kwh": self.energy_export_kwh,
            "accumulate_energy": self.accumulate_energy,
            "elapsed_seconds": self.elapsed_seconds,
        }


@dataclass(frozen=True)
class PhaseElectricalValues:
    """Electrical values for one phase."""

    voltage_ln: float
    voltage_ll: float
    current_a: float
    active_power_w: float
    reactive_power_var: float
    apparent_power_va: float
    power_factor: float


@dataclass(frozen=True)
class MeterElectricalValues:
    """Coherent aggregate electrical state for a meter."""

    l1: PhaseElectricalValues
    l2: PhaseElectricalValues
    l3: PhaseElectricalValues
    total_active_power_w: float
    total_reactive_power_var: float
    total_apparent_power_va: float
    power_factor: float
    frequency_hz: float
    energy_import_kwh: float
    energy_export_kwh: float


@dataclass(frozen=True)
class DemoValueBuildResult:
    """Built raw register values plus summary metadata."""

    values: dict[tuple[str, int], int]
    generated_count: int
    skipped_count: int
    warnings: list[str] = field(default_factory=list)


def scenario_to_dict(scenario: MeterDemoScenario) -> dict[str, Any]:
    """Convert a scenario to a JSON-compatible dictionary."""
    scenario.validate()
    return scenario.to_dict()


def scenario_from_dict(data: dict[str, Any]) -> MeterDemoScenario:
    """Build and validate a MeterDemoScenario from JSON-compatible data."""
    scenario = MeterDemoScenario(
        mode=str(data.get("mode", MeterScenarioMode.THREE_PHASE_BALANCED)),
        active_phase=str(data.get("active_phase", "L1")),
        voltage_ln=float(data.get("voltage_ln", 230.0)),
        frequency_hz=float(data.get("frequency_hz", 50.0)),
        total_active_power_w=float(data.get("total_active_power_w", 3000.0)),
        power_factor=float(data.get("power_factor", 0.98)),
        phase_l1_power_w=_optional_float(data.get("phase_l1_power_w")),
        phase_l2_power_w=_optional_float(data.get("phase_l2_power_w")),
        phase_l3_power_w=_optional_float(data.get("phase_l3_power_w")),
        imbalance_percent=float(data.get("imbalance_percent", 10.0)),
        energy_import_kwh=float(data.get("energy_import_kwh", 1234.5)),
        energy_export_kwh=float(data.get("energy_export_kwh", 0.0)),
        accumulate_energy=bool(data.get("accumulate_energy", False)),
        elapsed_seconds=float(data.get("elapsed_seconds", 0.0)),
    )
    scenario.validate()
    return scenario


def classify_meter_variable(
    variable: str,
    description: str = "",
    unit: str = "",
) -> str:
    """Classify a profile register into a meter-oriented semantic bucket."""
    text = " ".join((variable, description, unit)).lower()

    if "voltage" in text:
        if any(token in text for token in ("ll", "line-line", "l12", "l23", "l31", "uab", "ubc", "uca")):
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
    """Return one reasonable default physical value for a semantic class."""
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


def calculate_meter_values(scenario: MeterDemoScenario) -> MeterElectricalValues:
    """Calculate a coherent electrical state from *scenario*."""
    scenario.validate()
    voltage_ll = scenario.voltage_ln * math.sqrt(3.0)

    phase_powers = _phase_powers_for_scenario(scenario)
    phases = {
        "L1": _phase_values(scenario.voltage_ln, voltage_ll, phase_powers[0], scenario.power_factor),
        "L2": _phase_values(scenario.voltage_ln, voltage_ll, phase_powers[1], scenario.power_factor),
        "L3": _phase_values(scenario.voltage_ln, voltage_ll, phase_powers[2], scenario.power_factor),
    }

    total_active = sum(phase.active_power_w for phase in phases.values())
    total_apparent = sum(phase.apparent_power_va for phase in phases.values())
    total_reactive = sum(phase.reactive_power_var for phase in phases.values())
    total_pf = total_active / total_apparent if total_apparent > 0 else scenario.power_factor

    energy_import = scenario.energy_import_kwh
    if scenario.accumulate_energy and scenario.elapsed_seconds > 0:
        energy_import += total_active * scenario.elapsed_seconds / 3_600_000.0

    return MeterElectricalValues(
        l1=phases["L1"],
        l2=phases["L2"],
        l3=phases["L3"],
        total_active_power_w=total_active,
        total_reactive_power_var=total_reactive,
        total_apparent_power_va=total_apparent,
        power_factor=min(max(total_pf, 0.0), 1.0),
        frequency_hz=scenario.frequency_hz,
        energy_import_kwh=energy_import,
        energy_export_kwh=scenario.energy_export_kwh,
    )


def map_physical_value_for_register(register: Any, meter_values: MeterElectricalValues) -> float | None:
    """Map one profile register to a physical demo value from *meter_values*."""
    variable = getattr(register, "variable", "").lower()
    description = getattr(register, "description", "").lower()
    unit = (getattr(register, "unit", "") or "").lower()
    text = " ".join((variable, description, unit))

    if any(token in text for token in ("frequency", " hz")):
        return meter_values.frequency_hz
    if any(token in text for token in ("power_factor", " pf", "factor")):
        return meter_values.power_factor
    if "voltage" in text:
        if any(token in text for token in ("ll", "l12", "l23", "l31", "uab", "ubc", "uca")):
            if any(token in text for token in ("l23", "ubc")):
                return meter_values.l2.voltage_ll
            if any(token in text for token in ("l31", "uca")):
                return meter_values.l3.voltage_ll
            return meter_values.l1.voltage_ll
        if any(token in text for token in ("l2", "ub", "phase b")):
            return meter_values.l2.voltage_ln
        if any(token in text for token in ("l3", "uc", "phase c")):
            return meter_values.l3.voltage_ln
        return meter_values.l1.voltage_ln
    if "current" in text:
        if "l2" in text or "phase b" in text:
            return meter_values.l2.current_a
        if "l3" in text or "phase c" in text:
            return meter_values.l3.current_a
        if "total" in text:
            return meter_values.l1.current_a + meter_values.l2.current_a + meter_values.l3.current_a
        return meter_values.l1.current_a
    if "reactive" in text:
        if "l2" in text or "phase b" in text:
            return meter_values.l2.reactive_power_var
        if "l3" in text or "phase c" in text:
            return meter_values.l3.reactive_power_var
        if "l1" in text or "phase a" in text:
            return meter_values.l1.reactive_power_var
        return meter_values.total_reactive_power_var
    if "apparent" in text:
        if "l2" in text or "phase b" in text:
            return meter_values.l2.apparent_power_va
        if "l3" in text or "phase c" in text:
            return meter_values.l3.apparent_power_va
        if "l1" in text or "phase a" in text:
            return meter_values.l1.apparent_power_va
        return meter_values.total_apparent_power_va
    if "power" in text:
        if "l2" in text or "phase b" in text:
            return meter_values.l2.active_power_w
        if "l3" in text or "phase c" in text:
            return meter_values.l3.active_power_w
        if "l1" in text or "phase a" in text:
            return meter_values.l1.active_power_w
        return meter_values.total_active_power_w
    if "energy" in text:
        if "export" in text or "negative" in text:
            return meter_values.energy_export_kwh
        return meter_values.energy_import_kwh
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
    scenario: MeterDemoScenario | None = None,
    variation_percent: float = 0.0,
    rng: random.Random | None = None,
) -> DemoValueBuildResult:
    """Build raw register words for a profile using an optional scenario."""
    generator = rng or random.Random()
    scenario_obj = scenario or MeterDemoScenario()
    scenario_obj.validate()
    meter_values = calculate_meter_values(scenario_obj)

    values: dict[tuple[str, int], int] = {}
    generated_count = 0
    skipped_count = 0
    warnings: list[str] = []
    function_code = int(getattr(profile, "default_function", 3) or 3)
    bank_name = bank_for_function(function_code)
    profile_word_order = getattr(profile, "word_order", "normal")

    for register in getattr(profile, "registers", []):
        try:
            physical_value = map_physical_value_for_register(register, meter_values)
            if physical_value is None:
                skipped_count += 1
                continue
            varied_value = apply_random_variation(
                physical_value,
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
            warnings.append(f"{getattr(register, 'variable', '<unknown>')}: {exc}")
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


def _phase_values(
    voltage_ln: float,
    voltage_ll: float,
    active_power_w: float,
    power_factor: float,
) -> PhaseElectricalValues:
    if active_power_w <= 0:
        return PhaseElectricalValues(
            voltage_ln=voltage_ln,
            voltage_ll=voltage_ll,
            current_a=0.0,
            active_power_w=0.0,
            reactive_power_var=0.0,
            apparent_power_va=0.0,
            power_factor=power_factor,
        )

    apparent_power_va = active_power_w / power_factor
    reactive_power_var = math.sqrt(max(apparent_power_va**2 - active_power_w**2, 0.0))
    current_a = active_power_w / (voltage_ln * power_factor) if voltage_ln > 0 else 0.0
    return PhaseElectricalValues(
        voltage_ln=voltage_ln,
        voltage_ll=voltage_ll,
        current_a=current_a,
        active_power_w=active_power_w,
        reactive_power_var=reactive_power_var,
        apparent_power_va=apparent_power_va,
        power_factor=power_factor,
    )


def _phase_powers_for_scenario(scenario: MeterDemoScenario) -> tuple[float, float, float]:
    manual_powers = (
        scenario.phase_l1_power_w,
        scenario.phase_l2_power_w,
        scenario.phase_l3_power_w,
    )
    if any(value is not None for value in manual_powers):
        return tuple(float(value or 0.0) for value in manual_powers)

    if scenario.mode == MeterScenarioMode.SINGLE_PHASE:
        return (scenario.total_active_power_w, 0.0, 0.0)
    if scenario.mode == MeterScenarioMode.THREE_PHASE_BALANCED:
        per_phase = scenario.total_active_power_w / 3.0
        return (per_phase, per_phase, per_phase)
    if scenario.mode == MeterScenarioMode.THREE_PHASE_SINGLE_PHASE_LOAD:
        phase_map = {"L1": 0, "L2": 1, "L3": 2}
        powers = [0.0, 0.0, 0.0]
        powers[phase_map[scenario.active_phase]] = scenario.total_active_power_w
        return tuple(powers)  # type: ignore[return-value]
    if scenario.mode == MeterScenarioMode.THREE_PHASE_UNBALANCED:
        base = scenario.total_active_power_w / 3.0
        spread = base * (scenario.imbalance_percent / 100.0)
        p1 = max(base + spread, 0.0)
        p2 = max(base, 0.0)
        p3 = max(scenario.total_active_power_w - p1 - p2, 0.0)
        return (p1, p2, p3)
    return (scenario.total_active_power_w, 0.0, 0.0)


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


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
