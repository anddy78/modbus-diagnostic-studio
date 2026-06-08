"""GUI smoke tests for the offline Capture Viewer tab."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.gui.main_window import MainWindow
from modbus_diagnostic_studio.gui.tabs.capture_viewer_tab import CaptureViewerTab
from modbus_diagnostic_studio.services.application_state import ApplicationState


def _write_sample_events_jsonl(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                json.dumps({"record_type": "metadata", "capture_id": "abc"}),
                json.dumps(
                    {
                        "record_type": "event",
                        "timestamp_iso": "2026-06-08T12:00:00+00:00",
                        "raw_hex": "01 03 00 00 00 02 C4 0B",
                        "classification": "read_request",
                        "crc_ok": True,
                        "slave_id": 1,
                        "function_code": 3,
                        "address": 0,
                        "quantity": 2,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_capture_viewer_tab_builds() -> None:
    app = QApplication.instance() or QApplication([])
    widget = CaptureViewerTab(ApplicationState())

    assert app is not None
    assert widget.records_table.columnCount() == 9
    assert "Offline capture viewer" in widget.status_label.text()


def test_capture_viewer_loads_and_decodes_events_jsonl(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    widget = CaptureViewerTab(ApplicationState())
    capture_path = tmp_path / "capture_events.jsonl"
    _write_sample_events_jsonl(capture_path)

    widget.load_capture_from_path(capture_path)
    widget.records_table.selectRow(0)
    widget.decode_selected_frame()

    assert app is not None
    assert widget.records_table.rowCount() == 1
    assert widget.selected_raw_hex_output.toPlainText() == "01 03 00 00 00 02 C4 0B"
    assert widget.decoded_labels["classification"].text() == "read_request"


def test_add_selected_frame_to_diagnostic_report_requires_session(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    state = ApplicationState()
    widget = CaptureViewerTab(state)
    capture_path = tmp_path / "capture_events.jsonl"
    _write_sample_events_jsonl(capture_path)
    widget.load_capture_from_path(capture_path)
    widget.records_table.selectRow(0)

    widget.add_selected_frame_to_report()

    assert app is not None
    assert widget.status_label.text() == "No active diagnostic session."


def test_add_selected_frame_to_diagnostic_report_appends_event(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    state = ApplicationState()
    state.new_session(title="Capture Review")
    widget = CaptureViewerTab(state)
    capture_path = tmp_path / "capture_events.jsonl"
    _write_sample_events_jsonl(capture_path)
    widget.load_capture_from_path(capture_path)
    widget.records_table.selectRow(0)

    widget.add_selected_frame_to_report()

    assert app is not None
    assert state.current_session is not None
    assert len(state.current_session.events) == 1
    assert state.current_session.events[0].source == "capture_viewer"


def test_capture_viewer_export_ai_bundle_to_path(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    widget = CaptureViewerTab(ApplicationState())
    capture_path = tmp_path / "capture_events.jsonl"
    bundle_path = tmp_path / "bundle.json"
    _write_sample_events_jsonl(capture_path)
    widget.load_capture_from_path(capture_path)

    widget.export_ai_bundle_to_path(bundle_path)

    assert app is not None
    assert bundle_path.exists()
    assert json.loads(bundle_path.read_text(encoding="utf-8"))["bundle_type"] == "modbus_capture_ai_bundle"


def test_main_window_contains_capture_viewer_tab() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    tab_names = [window.tabs.tabText(index) for index in range(window.tabs.count())]

    assert app is not None
    assert "Capture Viewer" in tab_names
