"""GUI smoke tests for the Profile Manager tab."""

import os
from pathlib import Path

import pytest


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.gui.tabs.profile_manager_tab import ProfileManagerTab


def test_profile_manager_tab_builds_and_lists_builtins(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = ProfileManagerTab()
    widget.reload_profiles()

    assert app is not None
    assert widget.device_profiles_table.rowCount() >= 3
    assert widget.register_profiles_table.rowCount() >= 1
    assert widget.register_profiles_table.horizontalHeaderItem(4).text() == "Description"
    assert widget.register_preview_table.horizontalHeaderItem(5).text() == "Description"


def test_profile_manager_import_device_profile_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    source_path = tmp_path / "import_me.yaml"
    source_path.write_text(
        "\n".join(
            [
                "device_id: imported_sample",
                "name: Imported Sample",
                "device_type: meter",
                "roles:",
                "  - role: slave",
                "    profile_type: register_profile",
                "    profile_id: generic_meter",
            ]
        ),
        encoding="utf-8",
    )

    widget = ProfileManagerTab()
    imported_messages: list[tuple[str, str]] = []

    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args: imported_messages.append((args[1], args[2])),
    )

    destination = widget.import_device_profile_file(source_path)
    widget.reload_profiles()

    assert app is not None
    assert destination is not None
    assert destination.exists()
    assert any("Import Device Profile" == title for title, _ in imported_messages)
    assert any(
        widget.device_profiles_table.item(row, 0).text() == "imported_sample"
        for row in range(widget.device_profiles_table.rowCount())
    )


def test_select_register_profile_loads_register_preview(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = ProfileManagerTab()
    widget.reload_profiles()
    widget._select_register_profile_by_id("chint_dtsu71")

    assert app is not None
    assert widget.register_preview_table.rowCount() > 0
    assert "chint_dtsu71" in widget.register_preview_status_label.text()
    assert widget.register_profiles_table.currentRow() >= 0


def test_role_linked_to_register_profile_can_load_preview(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = ProfileManagerTab()
    widget.reload_profiles()

    for row in range(widget.device_profiles_table.rowCount()):
        item = widget.device_profiles_table.item(row, 0)
        if item is not None and item.text() == "chint_dtsu71":
            widget.device_profiles_table.selectRow(row)
            break

    widget.roles_table.selectRow(0)

    assert app is not None
    assert widget.register_preview_table.rowCount() > 0
    assert "Selected register profile chint_dtsu71" in widget.status_label.text()
    assert widget.roles_table.item(0, 0).toolTip() != ""


def test_role_linked_to_communication_profile_shows_clear_status(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = ProfileManagerTab()
    widget.reload_profiles()

    for row in range(widget.device_profiles_table.rowCount()):
        item = widget.device_profiles_table.item(row, 0)
        if item is not None and item.text() == "chint_dtsu71":
            widget.device_profiles_table.selectRow(row)
            break

    widget.roles_table.selectRow(1)

    assert app is not None
    assert widget.register_preview_table.rowCount() == 0
    assert "communication profile smartlogger_chint_dtsu71" in widget.status_label.text()


def test_register_preview_cells_have_tooltips(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])

    widget = ProfileManagerTab()
    widget.reload_profiles()
    widget._select_register_profile_by_id("generic_meter")

    first_item = widget.register_preview_table.item(0, 0)

    assert app is not None
    assert first_item is not None
    assert "Variable:" in first_item.toolTip()
