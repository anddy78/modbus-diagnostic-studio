"""GUI tests for Advanced Master known register selection."""

import os

import pytest


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import AdvancedMasterTab


def test_advanced_master_profile_selection_loads_known_registers() -> None:
    app = QApplication.instance() or QApplication([])

    widget = AdvancedMasterTab()
    index = widget.profile_combo.findData("chint_dtsu71")
    widget.profile_combo.setCurrentIndex(index)

    assert app is not None
    assert widget.known_registers_table.rowCount() > 0


def test_advanced_master_known_register_updates_read_fields() -> None:
    app = QApplication.instance() or QApplication([])

    widget = AdvancedMasterTab()
    index = widget.profile_combo.findData("generic_meter")
    widget.profile_combo.setCurrentIndex(index)
    widget.known_registers_table.selectRow(0)

    assert app is not None
    assert widget.function_combo.currentData() == 3
    assert widget.start_address.value() == int(widget.known_registers_table.item(0, 1).text())
    assert widget.quantity.value() >= 1
    assert widget.decode_format.currentData() is not None
    assert widget.write_enable_check.isChecked() is False
