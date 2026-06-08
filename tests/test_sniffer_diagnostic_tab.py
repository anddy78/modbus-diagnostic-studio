"""GUI smoke tests for the Sniffer Diagnostic tab."""

from __future__ import annotations

import os

import pytest


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.gui.tabs.sniffer_diagnostic_tab import (
    VISIBLE_FRAME_LIMIT,
    SnifferDiagnosticTab,
)
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


def test_visible_frame_limit_constant_is_100() -> None:
    assert VISIBLE_FRAME_LIMIT == 100
