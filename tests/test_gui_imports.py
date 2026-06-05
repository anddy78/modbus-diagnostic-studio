"""Smoke tests for GUI imports without showing windows."""

import pytest


pytest.importorskip("PySide6")


def test_gui_imports() -> None:
    from modbus_diagnostic_studio.gui.app import run_app
    from modbus_diagnostic_studio.gui.main_window import MainWindow
    from modbus_diagnostic_studio.gui.tabs import (
        ConnectionTab,
        DecoderTab,
        ProfilesTab,
    )

    assert callable(run_app)
    assert MainWindow.__name__ == "MainWindow"
    assert ConnectionTab.__name__ == "ConnectionTab"
    assert DecoderTab.__name__ == "DecoderTab"
    assert ProfilesTab.__name__ == "ProfilesTab"
