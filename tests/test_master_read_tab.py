"""GUI tests for Master Read profile-assisted register selection."""

import os

import pytest


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.gui.tabs.master_read_tab import MasterReadTab


def test_master_read_profile_selection_loads_known_registers() -> None:
    app = QApplication.instance() or QApplication([])

    widget = MasterReadTab()
    index = widget.profile_combo.findData("chint_dtsu71")
    widget.profile_combo.setCurrentIndex(index)

    assert app is not None
    assert widget.known_registers_table.rowCount() > 0


def test_master_read_known_register_updates_function_address_quantity() -> None:
    app = QApplication.instance() or QApplication([])

    widget = MasterReadTab()
    index = widget.profile_combo.findData("generic_meter")
    widget.profile_combo.setCurrentIndex(index)
    widget.known_registers_table.selectRow(0)

    assert app is not None
    assert widget.function.currentData() == 3
    assert widget.address.value() == int(widget.known_registers_table.item(0, 1).text())
    assert widget.quantity.value() >= 1
