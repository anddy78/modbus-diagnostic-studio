"""Tests for reusable slave simulator scenario persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from modbus_diagnostic_studio.slave.demo_values import MeterDemoScenario, MeterScenarioMode
from modbus_diagnostic_studio.slave.scenario_store import (
    SlaveScenarioFile,
    create_builtin_like_default_scenarios,
    list_slave_scenarios,
    read_slave_scenario,
    write_slave_scenario,
)


def _sample_scenario_file() -> SlaveScenarioFile:
    return SlaveScenarioFile(
        name="SDM230 Single Phase 1kW",
        description="Reusable single-phase preset",
        register_profile_id="generic_meter",
        device_profile_id="",
        scenario=MeterDemoScenario(
            mode=MeterScenarioMode.SINGLE_PHASE,
            total_active_power_w=1000.0,
            power_factor=0.97,
        ),
        random_variation_enabled=True,
        variation_percent=2.0,
        auto_refresh_enabled=False,
        update_interval_seconds=2.0,
    )


def test_write_and_read_slave_scenario_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "scenarios" / "slave" / "single_phase.json"
    write_slave_scenario(path, _sample_scenario_file())

    restored = read_slave_scenario(path)

    assert restored == _sample_scenario_file()


def test_directory_path_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_slave_scenario(tmp_path, _sample_scenario_file())
    with pytest.raises(ValueError):
        read_slave_scenario(tmp_path)


def test_list_slave_scenarios_returns_sorted_json_files(tmp_path: Path) -> None:
    write_slave_scenario(tmp_path / "b.json", _sample_scenario_file())
    write_slave_scenario(tmp_path / "a.json", _sample_scenario_file())

    listed = list_slave_scenarios(tmp_path)

    assert [path.name for path in listed] == ["a.json", "b.json"]


def test_default_scenarios_can_be_created(tmp_path: Path) -> None:
    created = create_builtin_like_default_scenarios(tmp_path)

    assert len(created) >= 4
    assert any(path.name == "sdm230_single_phase_1kw.json" for path in created)


def test_invalid_json_or_data_fails_clearly(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.json"
    bad_json.write_text('{"name": "", "scenario": {"mode": "bad"}}', encoding="utf-8")

    with pytest.raises(ValueError):
        read_slave_scenario(bad_json)
