"""Persistence helpers for reusable slave simulator scenarios."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modbus_diagnostic_studio.services.paths import ensure_runtime_dirs, slave_scenarios_dir
from modbus_diagnostic_studio.slave.demo_values import (
    MeterDemoScenario,
    MeterScenarioMode,
    scenario_from_dict,
    scenario_to_dict,
)


@dataclass(frozen=True)
class SlaveScenarioFile:
    """Persisted slave simulator scenario preset."""

    name: str
    description: str = ""
    register_profile_id: str = ""
    device_profile_id: str = ""
    scenario: MeterDemoScenario = MeterDemoScenario()
    random_variation_enabled: bool = False
    variation_percent: float = 0.0
    auto_refresh_enabled: bool = False
    update_interval_seconds: float = 2.0


def scenario_file_to_dict(scenario_file: SlaveScenarioFile) -> dict[str, Any]:
    """Convert a SlaveScenarioFile into JSON-compatible data."""
    scenario_file.scenario.validate()
    if scenario_file.update_interval_seconds <= 0:
        raise ValueError("update_interval_seconds must be > 0")
    if scenario_file.variation_percent < 0:
        raise ValueError("variation_percent must be >= 0")
    return {
        "name": scenario_file.name,
        "description": scenario_file.description,
        "register_profile_id": scenario_file.register_profile_id,
        "device_profile_id": scenario_file.device_profile_id,
        "scenario": scenario_to_dict(scenario_file.scenario),
        "random_variation_enabled": scenario_file.random_variation_enabled,
        "variation_percent": scenario_file.variation_percent,
        "auto_refresh_enabled": scenario_file.auto_refresh_enabled,
        "update_interval_seconds": scenario_file.update_interval_seconds,
    }


def scenario_file_from_dict(data: dict[str, Any]) -> SlaveScenarioFile:
    """Build a validated SlaveScenarioFile from JSON-compatible data."""
    scenario_data = data.get("scenario")
    if not isinstance(scenario_data, dict):
        raise ValueError("scenario must be an object")
    scenario_file = SlaveScenarioFile(
        name=str(data.get("name", "")).strip(),
        description=str(data.get("description", "")),
        register_profile_id=str(data.get("register_profile_id", "")),
        device_profile_id=str(data.get("device_profile_id", "")),
        scenario=scenario_from_dict(scenario_data),
        random_variation_enabled=bool(data.get("random_variation_enabled", False)),
        variation_percent=float(data.get("variation_percent", 0.0)),
        auto_refresh_enabled=bool(data.get("auto_refresh_enabled", False)),
        update_interval_seconds=float(data.get("update_interval_seconds", 2.0)),
    )
    if not scenario_file.name:
        raise ValueError("name must not be empty")
    if scenario_file.variation_percent < 0:
        raise ValueError("variation_percent must be >= 0")
    if scenario_file.update_interval_seconds <= 0:
        raise ValueError("update_interval_seconds must be > 0")
    return scenario_file


def write_slave_scenario(path: str | Path, scenario_file: SlaveScenarioFile) -> None:
    """Write a scenario preset JSON file."""
    output_path = _prepare_output_path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        json.dump(
            scenario_file_to_dict(scenario_file),
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")


def read_slave_scenario(path: str | Path) -> SlaveScenarioFile:
    """Read one scenario preset JSON file."""
    input_path = Path(path)
    if input_path.exists() and input_path.is_dir():
        raise ValueError(f"Slave scenario path is a directory: {input_path}")
    with input_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Slave scenario file must contain a JSON object")
    return scenario_file_from_dict(data)


def list_slave_scenarios(directory: str | Path | None = None) -> list[Path]:
    """List available JSON scenario files in the given directory."""
    target_dir = Path(directory) if directory is not None else ensure_slave_scenario_dir()
    if not target_dir.exists():
        return []
    return sorted(path for path in target_dir.glob("*.json") if path.is_file())


def ensure_slave_scenario_dir() -> Path:
    """Ensure the writable scenario directory exists."""
    ensure_runtime_dirs()
    path = slave_scenarios_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_builtin_like_default_scenarios(directory: str | Path | None = None) -> list[Path]:
    """Create a small set of example scenario files if none exist yet."""
    target_dir = Path(directory) if directory is not None else ensure_slave_scenario_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    existing = list_slave_scenarios(target_dir)
    if existing:
        return existing

    scenarios = {
        "sdm230_single_phase_1kw.json": SlaveScenarioFile(
            name="SDM230 Single Phase 1kW",
            description="Single-phase meter demo around 1 kW.",
            register_profile_id="generic_meter",
            scenario=MeterDemoScenario(
                mode=MeterScenarioMode.SINGLE_PHASE,
                total_active_power_w=1000.0,
                power_factor=0.98,
                elapsed_seconds=0.0,
            ),
        ),
        "sdm630_three_phase_balanced_5kw.json": SlaveScenarioFile(
            name="SDM630 Three Phase Balanced 5kW",
            description="Balanced three-phase scenario around 5 kW total.",
            register_profile_id="chint_dtsu71",
            scenario=MeterDemoScenario(
                mode=MeterScenarioMode.THREE_PHASE_BALANCED,
                total_active_power_w=5000.0,
                power_factor=0.99,
                elapsed_seconds=0.0,
            ),
        ),
        "sdm630_single_phase_load_l1_2kw.json": SlaveScenarioFile(
            name="SDM630 Single Phase Load L1 2kW",
            description="Three-phase meter with load only on L1.",
            register_profile_id="chint_dtsu71",
            scenario=MeterDemoScenario(
                mode=MeterScenarioMode.THREE_PHASE_SINGLE_PHASE_LOAD,
                active_phase="L1",
                total_active_power_w=2000.0,
                elapsed_seconds=0.0,
            ),
        ),
        "low_voltage_pf_low.json": SlaveScenarioFile(
            name="Low Voltage Low PF",
            description="Low voltage and low power factor diagnostic preset.",
            register_profile_id="generic_meter",
            scenario=MeterDemoScenario(
                mode=MeterScenarioMode.THREE_PHASE_UNBALANCED,
                voltage_ln=205.0,
                total_active_power_w=1800.0,
                power_factor=0.72,
                imbalance_percent=15.0,
                elapsed_seconds=0.0,
            ),
            random_variation_enabled=True,
            variation_percent=3.0,
        ),
    }

    written: list[Path] = []
    for filename, scenario_file in scenarios.items():
        path = target_dir / filename
        write_slave_scenario(path, scenario_file)
        written.append(path)
    return written


def _prepare_output_path(path: str | Path) -> Path:
    output_path = Path(path)
    if output_path.exists() and output_path.is_dir():
        raise ValueError(f"Slave scenario path is a directory: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path
