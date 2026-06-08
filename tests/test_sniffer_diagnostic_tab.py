"""GUI smoke tests for the Sniffer Diagnostic tab."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.gui.tabs.sniffer_diagnostic_tab import (
    VISIBLE_FRAME_LIMIT,
    SnifferDiagnosticTab,
)
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.services.application_state import ApplicationState


def test_sniffer_diagnostic_tab_builds_with_performance_controls() -> None:
    app = QApplication.instance() or QApplication([])
    widget = SnifferDiagnosticTab(ApplicationState())

    assert app is not None
    assert widget.poll_interval_spin.value() == 100
    assert widget.ui_update_interval_spin.value() == 500
    assert widget.fingerprint_interval_spin.value() == pytest.approx(1.0)
    assert widget.pause_display_button.text() == "Pause Display"
    assert widget.resume_display_button.text() == "Resume Display"
    assert widget.record_to_file_checkbox.text() == "Record to file"
    assert widget.base_name_edit.text() == "modbus_capture"


def test_pause_and_resume_display_toggle_state_without_port_access() -> None:
    app = QApplication.instance() or QApplication([])
    widget = SnifferDiagnosticTab(ApplicationState())

    widget._running = True
    widget.pause_display()
    assert app is not None
    assert widget._display_paused is True
    assert widget.display_paused_label.text() == "Yes"
    assert "Display paused; capture still running." in widget.status_label.text()

    widget.resume_display()
    assert widget._display_paused is False
    assert widget.display_paused_label.text() == "No"
    assert "Passive sniffer running. Capture active." in widget.status_label.text()


def test_record_toggle_is_blocked_while_running_without_port_access() -> None:
    app = QApplication.instance() or QApplication([])
    widget = SnifferDiagnosticTab(ApplicationState())

    widget._running = True
    widget.record_to_file_checkbox.setChecked(True)

    assert app is not None
    assert widget.status_label.text() == "Change recording before starting capture."


def test_snapshot_write_updates_recorder_labels_without_threads(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    widget = SnifferDiagnosticTab(ApplicationState())
    fake_snapshot = SimpleNamespace(events=[object(), object()], exchanges=[object()])

    class FakeRecorder:
        def __init__(self) -> None:
            self.records_written = 3
            self.events_path = tmp_path / "events.jsonl"
            self.exchanges_path = tmp_path / "exchanges.jsonl"
            self.calls = 0

        def write_snapshot_delta(self, snapshot: object) -> None:
            assert snapshot is fake_snapshot
            self.calls += 1

        def close(self) -> None:
            return None

    recorder = FakeRecorder()
    widget._recorder = recorder

    widget._write_snapshot_to_recorder(fake_snapshot)

    assert app is not None
    assert recorder.calls == 1
    assert widget.recording_label.text() == "Yes"
    assert widget.records_written_label.text() == "3"
    assert "events.jsonl" in widget.capture_files_label.text()


def test_close_recorder_keeps_last_files_and_total_until_clear(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    widget = SnifferDiagnosticTab(ApplicationState())

    class FakeRecorder:
        def __init__(self) -> None:
            self.records_written = 7
            self.events_path = tmp_path / "capture_events.jsonl"
            self.exchanges_path = tmp_path / "capture_exchanges.jsonl"

        def close(self) -> None:
            return None

    widget._recorder = FakeRecorder()
    widget._sync_recorder_labels()
    widget._close_recorder()

    assert app is not None
    assert widget.recording_label.text() == "No"
    assert widget.records_written_label.text() == "7"
    assert "capture_events.jsonl" in widget.capture_files_label.text()

    widget.clear_view()

    assert widget.records_written_label.text() == "0"
    assert widget.capture_files_label.text() == "-"


def test_recorder_metadata_uses_central_version() -> None:
    widget = SnifferDiagnosticTab(ApplicationState())
    metadata = widget._build_recorder_metadata(SerialConnectionSettings(port="COM9"))

    assert metadata["app_version"] == "0.1.0-rc1"


def test_visible_frame_limit_constant_is_100() -> None:
    assert VISIBLE_FRAME_LIMIT == 100
