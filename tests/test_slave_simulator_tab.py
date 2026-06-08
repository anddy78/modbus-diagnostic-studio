"""GUI tests for Slave Simulator profile-assisted demo meter scenarios."""

import os
from pathlib import Path

import pytest


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.core.endian import registers_to_float32
from modbus_diagnostic_studio.slave.demo_values import MeterDemoScenario, MeterScenarioMode
from modbus_diagnostic_studio.slave.scenario_store import SlaveScenarioFile
from modbus_diagnostic_studio.gui.tabs.slave_simulator_tab import SlaveSimulatorTab


def _read_float32_holding(widget: SlaveSimulatorTab, address: int) -> float:
    registers = widget._datastore.read_holding_registers(address, 2)
    return registers_to_float32(registers)


def test_slave_simulator_tab_has_profile_selectors(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()

    assert app is not None
    assert widget.device_profile_combo is not None
    assert widget.register_profile_combo is not None
    assert widget.known_registers_table is not None
    assert widget.demo_mode_combo is not None


def test_slave_simulator_load_profile_registers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    index = widget.register_profile_combo.findData("chint_dtsu71")
    widget.register_profile_combo.setCurrentIndex(index)

    assert app is not None
    assert widget.known_registers_table.rowCount() > 0
    assert "chint_dtsu71" in widget.status_label.text()


def test_slave_simulator_known_register_selection_updates_editor(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    index = widget.register_profile_combo.findData("generic_meter")
    widget.register_profile_combo.setCurrentIndex(index)
    widget.known_registers_table.selectRow(0)

    selected_address = int(widget.known_registers_table.item(0, 1).text())

    assert app is not None
    assert widget.edit_address.value() == selected_address
    assert widget.view_offset.value() == selected_address


def test_single_phase_demo_generation_is_coherent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    index = widget.register_profile_combo.findData("chint_dtsu71")
    widget.register_profile_combo.setCurrentIndex(index)
    mode_index = widget.demo_mode_combo.findData("single_phase")
    widget.demo_mode_combo.setCurrentIndex(mode_index)
    widget.total_active_power_spin.setValue(2300.0)
    widget.random_variation_check.setChecked(False)
    widget.generate_demo_meter_values()

    l1 = _read_float32_holding(widget, 2128)
    l2 = _read_float32_holding(widget, 2130)
    l3 = _read_float32_holding(widget, 2132)

    assert app is not None
    assert l1 > 0.0
    assert l2 == pytest.approx(0.0)
    assert l3 == pytest.approx(0.0)


def test_three_phase_single_phase_load_uses_active_phase(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    index = widget.register_profile_combo.findData("chint_dtsu71")
    widget.register_profile_combo.setCurrentIndex(index)
    mode_index = widget.demo_mode_combo.findData("three_phase_single_phase_load")
    widget.demo_mode_combo.setCurrentIndex(mode_index)
    widget.active_phase_combo.setCurrentText("L2")
    widget.total_active_power_spin.setValue(1800.0)
    widget.random_variation_check.setChecked(False)
    widget.generate_demo_meter_values()

    l1 = _read_float32_holding(widget, 2128)
    l2 = _read_float32_holding(widget, 2130)
    l3 = _read_float32_holding(widget, 2132)

    assert app is not None
    assert l1 == pytest.approx(0.0)
    assert l2 > 0.0
    assert l3 == pytest.approx(0.0)


def test_manual_per_phase_power_uses_sum(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    index = widget.register_profile_combo.findData("chint_dtsu71")
    widget.register_profile_combo.setCurrentIndex(index)
    widget.manual_phase_power_check.setChecked(True)
    widget.phase_l1_power_spin.setValue(1000.0)
    widget.phase_l2_power_spin.setValue(500.0)
    widget.phase_l3_power_spin.setValue(250.0)
    widget.random_variation_check.setChecked(False)
    widget.generate_demo_meter_values()

    total_power = _read_float32_holding(widget, 2126)

    assert app is not None
    assert total_power == pytest.approx(1750.0, rel=1e-4)


def test_accumulate_energy_increases_on_auto_refresh(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    index = widget.register_profile_combo.findData("chint_dtsu71")
    widget.register_profile_combo.setCurrentIndex(index)
    widget.accumulate_energy_check.setChecked(True)
    widget.random_variation_check.setChecked(False)
    widget.demo_update_interval_spin.setValue(2)

    widget.generate_demo_meter_values()
    before = _read_float32_holding(widget, 2166)
    widget._auto_refresh_demo_values()
    after = _read_float32_holding(widget, 2166)

    assert app is not None
    assert after > before


def test_auto_refresh_timer_can_toggle_without_port(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    index = widget.register_profile_combo.findData("generic_meter")
    widget.register_profile_combo.setCurrentIndex(index)
    widget.auto_refresh_demo_check.setChecked(True)

    assert app is not None
    assert widget._demo_timer is not None
    assert widget._demo_timer.isActive()

    widget.auto_refresh_demo_check.setChecked(False)

    assert widget._demo_timer is not None
    assert widget._demo_timer.isActive() is False


def test_scenario_from_controls_returns_expected_model(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    widget.demo_mode_combo.setCurrentIndex(widget.demo_mode_combo.findData(MeterScenarioMode.SINGLE_PHASE))
    widget.voltage_ln_spin.setValue(220.0)
    widget.frequency_spin.setValue(60.0)
    widget.total_active_power_spin.setValue(1000.0)
    widget.power_factor_spin.setValue(0.95)

    scenario = widget._scenario_from_controls()

    assert app is not None
    assert scenario.mode == MeterScenarioMode.SINGLE_PHASE
    assert scenario.voltage_ln == pytest.approx(220.0)
    assert scenario.frequency_hz == pytest.approx(60.0)
    assert scenario.total_active_power_w == pytest.approx(1000.0)
    assert scenario.power_factor == pytest.approx(0.95)


def test_apply_scenario_to_controls_restores_values(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    scenario_file = SlaveScenarioFile(
        name="L1 load",
        description="Three-phase with load on L1",
        register_profile_id="chint_dtsu71",
        scenario=MeterDemoScenario(
            mode=MeterScenarioMode.THREE_PHASE_SINGLE_PHASE_LOAD,
            active_phase="L1",
            total_active_power_w=2000.0,
        ),
        random_variation_enabled=True,
        variation_percent=3.0,
        auto_refresh_enabled=True,
        update_interval_seconds=5.0,
    )

    widget._apply_scenario_file_to_controls(scenario_file)

    assert app is not None
    assert widget.scenario_name_edit.text() == "L1 load"
    assert widget.scenario_description_edit.text() == "Three-phase with load on L1"
    assert widget.demo_mode_combo.currentData() == MeterScenarioMode.THREE_PHASE_SINGLE_PHASE_LOAD
    assert widget.active_phase_combo.currentText() == "L1"
    assert widget.total_active_power_spin.value() == pytest.approx(2000.0)
    assert widget.random_variation_check.isChecked() is True
    assert widget.demo_update_interval_spin.value() == 5


def test_save_and_load_scenario_helpers_do_not_generate_values(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    widget.register_profile_combo.setCurrentIndex(widget.register_profile_combo.findData("generic_meter"))
    widget.scenario_name_edit.setText("Saved single phase")
    widget.demo_mode_combo.setCurrentIndex(widget.demo_mode_combo.findData(MeterScenarioMode.SINGLE_PHASE))
    widget.total_active_power_spin.setValue(1234.0)
    widget.random_variation_check.setChecked(True)
    widget.variation_percent_spin.setValue(4)
    widget.auto_refresh_demo_check.setChecked(True)

    path = tmp_path / "saved_scenario.json"
    widget.save_scenario_to_path(str(path))

    widget.total_active_power_spin.setValue(9999.0)
    widget.random_variation_check.setChecked(False)
    widget._datastore.write_holding_register(0, 123)
    widget.load_scenario_from_path(str(path))

    assert app is not None
    assert path.exists()
    assert widget.total_active_power_spin.value() == pytest.approx(1234.0)
    assert widget.random_variation_check.isChecked() is True
    assert widget.auto_refresh_demo_check.isChecked() is False
    assert widget._datastore.read_holding_registers(0, 1)[0] == 123
    assert "Scenario loaded. Press Generate Demo Meter Values to apply to datastore." in widget.status_label.text()
