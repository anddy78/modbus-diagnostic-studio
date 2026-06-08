"""Shared GUI helpers for register-profile-driven views."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


def register_quantity_for_type(register_type: str) -> int:
    """Return how many 16-bit registers are needed for *register_type*."""
    if register_type in {"uint32", "int32", "float32"}:
        return 2
    return 1


def decode_format_for_register_type(register_type: str) -> str:
    """Return the closest decode format label for *register_type*."""
    if register_type in {"uint16", "int16", "uint32", "int32", "float32"}:
        return register_type
    return "uint16"


def function_for_profile(profile: Any) -> int:
    """Return the default read function for a register profile-like object."""
    return int(getattr(profile, "default_function", 3) or 3)


def bank_for_function(function_code: int) -> str:
    """Return the logical register bank label for a Modbus function code."""
    if function_code == 4:
        return "Input Registers"
    if function_code == 1:
        return "Coils"
    if function_code == 2:
        return "Discrete Inputs"
    return "Holding Registers"


def register_tooltip(profile_id: str, register: Any) -> str:
    """Build a rich tooltip for one known register entry."""
    return (
        f"Profile: {profile_id}\n"
        f"Variable: {register.variable}\n"
        f"Address: {register.address}\n"
        f"Type: {register.type}\n"
        f"Unit: {register.unit or '-'}\n"
        f"Scale: {register.scale}\n"
        f"Description: {register.description or '-'}"
    )


def populate_register_preview_table(
    table: QTableWidget,
    profile: Any,
    include_function: bool = True,
    include_bank: bool = True,
) -> None:
    """Populate *table* with known-register rows from *profile*."""
    function_code = function_for_profile(profile)
    bank = bank_for_function(function_code)
    registers = list(getattr(profile, "registers", []))

    columns = ["Variable", "Address"]
    if include_function:
        columns.append("Function")
    if include_bank:
        columns.append("Bank")
    columns.extend(["Type", "Quantity", "Unit", "Scale", "Description"])
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setRowCount(len(registers))

    for row, register in enumerate(registers):
        metadata = {
            "profile_id": getattr(profile, "profile_id", ""),
            "variable": register.variable,
            "address": register.address,
            "function_code": function_code,
            "bank": bank,
            "type": register.type,
            "quantity": register_quantity_for_type(register.type),
            "unit": register.unit or "",
            "scale": register.scale,
            "description": register.description or "",
        }
        tooltip = register_tooltip(metadata["profile_id"], register)
        values: list[str] = [register.variable, str(register.address)]
        if include_function:
            values.append(f"FC{function_code:02d}")
        if include_bank:
            values.append(bank)
        values.extend(
            [
                register.type,
                str(metadata["quantity"]),
                register.unit or "",
                str(register.scale),
                register.description or "",
            ]
        )
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(tooltip)
            item.setData(Qt.UserRole, metadata)
            table.setItem(row, column, item)


def selected_register_from_table(table: QTableWidget) -> dict[str, Any] | None:
    """Return metadata for the selected known register row, if any."""
    row = table.currentRow()
    if row < 0 or table.columnCount() == 0:
        return None
    item = table.item(row, 0)
    if item is None:
        return None
    metadata = item.data(Qt.UserRole)
    if not isinstance(metadata, dict):
        return None
    return metadata
