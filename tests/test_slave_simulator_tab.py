"""GUI tests for Slave Simulator profile-assisted register selection."""

import os
from pathlib import Path

import pytest


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.gui.tabs.slave_simulator_tab import SlaveSimulatorTab


def test_slave_simulator_tab_has_profile_selectors(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()

    assert app is not None
    assert widget.device_profile_combo is not None
    assert widget.register_profile_combo is not None
    assert widget.known_registers_table is not None


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


def test_slave_simulator_generate_demo_values_updates_datastore(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    index = widget.register_profile_combo.findData("generic_meter")
    widget.register_profile_combo.setCurrentIndex(index)
    widget.random_variation_combo.setCurrentIndex(0)
    widget.generate_demo_meter_values()

    values = widget._datastore.read_holding_registers(0, 8)

    assert app is not None
    assert any(value != 0 for value in values)
    assert "Generated" in widget.status_label.text()


def test_slave_simulator_generate_demo_values_without_variation_is_stable(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    index = widget.register_profile_combo.findData("generic_meter")
    widget.register_profile_combo.setCurrentIndex(index)
    widget.random_variation_combo.setCurrentIndex(0)

    widget.generate_demo_meter_values()
    first = widget._datastore.read_holding_registers(0, 8)
    widget.generate_demo_meter_values()
    second = widget._datastore.read_holding_registers(0, 8)

    assert app is not None
    assert first == second


def test_slave_simulator_auto_refresh_toggle_without_port(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = SlaveSimulatorTab()
    index = widget.register_profile_combo.findData("generic_meter")
    widget.register_profile_combo.setCurrentIndex(index)
    widget.auto_refresh_demo_combo.setCurrentIndex(1)

    assert app is not None
    assert widget._demo_timer is not None
    assert widget._demo_timer.isActive()

    widget.auto_refresh_demo_combo.setCurrentIndex(0)

    assert widget._demo_timer is not None
    assert widget._demo_timer.isActive() is False
