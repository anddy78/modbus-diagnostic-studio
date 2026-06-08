"""GUI smoke tests for the Diagnostic Report tab."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.gui.main_window import MainWindow
from modbus_diagnostic_studio.gui.tabs.diagnostic_report_tab import DiagnosticReportTab
from modbus_diagnostic_studio.services.application_state import ApplicationState


def test_diagnostic_report_tab_builds_with_active_session(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    state = ApplicationState()

    widget = DiagnosticReportTab(state)

    assert app is not None
    assert state.current_session is not None
    assert widget.events_table.columnCount() == 5
    assert widget.summary_labels["total_events"].text() == "0"


def test_diagnostic_report_new_session_replaces_current_session(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    state = ApplicationState()
    widget = DiagnosticReportTab(state)
    original_id = state.current_session.metadata.session_id

    widget.title_edit.setText("Job B")
    widget.technician_edit.setText("Alex")
    widget.new_session()

    assert app is not None
    assert state.current_session is not None
    assert state.current_session.metadata.session_id != original_id
    assert state.current_session.metadata.title == "Job B"
    assert state.current_session.metadata.technician == "Alex"


def test_add_manual_note_updates_event_table_and_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    state = ApplicationState()
    widget = DiagnosticReportTab(state)

    widget.manual_note_input.setPlainText("Observed timeout on inverter poll")
    widget.add_manual_note()

    assert app is not None
    assert state.current_session is not None
    assert widget.events_table.rowCount() == 1
    assert widget.summary_labels["total_events"].text() == "1"
    assert widget.events_table.item(0, 1).text() == "manual_note"
    assert "timeout" in widget.event_details_output.toPlainText().lower()


def test_diagnostic_report_direct_exports_work(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    state = ApplicationState()
    widget = DiagnosticReportTab(state)
    widget.manual_note_input.setPlainText("Manual export check")
    widget.add_manual_note()

    json_path = tmp_path / "exports" / "session.json"
    csv_path = tmp_path / "exports" / "session.csv"
    html_path = tmp_path / "exports" / "session.html"

    widget.save_session_to_path(json_path)
    widget.export_csv_to_path(csv_path)
    widget.export_html_to_path(html_path)

    assert app is not None
    assert json_path.exists()
    assert csv_path.exists()
    assert html_path.exists()

    state.current_session = None
    widget.load_session_from_path(json_path)

    assert state.current_session is not None
    assert widget.events_table.rowCount() == 1


def test_main_window_contains_diagnostic_report_tab() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    tab_names = [window.tabs.tabText(index) for index in range(window.tabs.count())]

    assert app is not None
    assert "Diagnostic Report" in tab_names
