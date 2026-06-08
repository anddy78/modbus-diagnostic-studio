"""Tests for shared register profile view helpers."""

import os

import pytest

from modbus_diagnostic_studio.gui.profile_views import (
    bank_for_function,
    decode_format_for_register_type,
    populate_register_preview_table,
    register_quantity_for_type,
    register_tooltip,
    selected_register_from_table,
)
from modbus_diagnostic_studio.models.profile import ProfileDefinition, RegisterDefinition


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget


def _sample_profile() -> ProfileDefinition:
    return ProfileDefinition(
        profile_id="sample_profile",
        name="Sample Profile",
        default_function=4,
        registers=[
            RegisterDefinition(
                variable="voltage_l1",
                address=10,
                type="float32",
                unit="V",
                scale=1.0,
                description="Phase voltage",
            )
        ],
    )


def test_register_quantity_for_type() -> None:
    assert register_quantity_for_type("uint16") == 1
    assert register_quantity_for_type("int16") == 1
    assert register_quantity_for_type("uint32") == 2
    assert register_quantity_for_type("int32") == 2
    assert register_quantity_for_type("float32") == 2
    assert register_quantity_for_type("unknown") == 1


def test_decode_format_for_register_type() -> None:
    assert decode_format_for_register_type("uint16") == "uint16"
    assert decode_format_for_register_type("float32") == "float32"
    assert decode_format_for_register_type("other") == "uint16"


def test_bank_for_function() -> None:
    assert bank_for_function(3) == "Holding Registers"
    assert bank_for_function(4) == "Input Registers"
    assert bank_for_function(1) == "Coils"
    assert bank_for_function(2) == "Discrete Inputs"


def test_register_tooltip_contains_description() -> None:
    tooltip = register_tooltip("sample_profile", _sample_profile().registers[0])

    assert "sample_profile" in tooltip
    assert "Phase voltage" in tooltip


def test_populate_register_preview_table_and_select_row() -> None:
    app = QApplication.instance() or QApplication([])
    table = QTableWidget()

    populate_register_preview_table(table, _sample_profile())
    table.selectRow(0)
    selected = selected_register_from_table(table)

    assert app is not None
    assert table.rowCount() == 1
    assert table.columnCount() == 9
    assert table.horizontalHeaderItem(2).text() == "Function"
    assert selected is not None
    assert selected["address"] == 10
    assert selected["function_code"] == 4
    assert selected["quantity"] == 2
