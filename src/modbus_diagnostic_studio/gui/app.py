"""PySide6 application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.gui.main_window import MainWindow


def run_app() -> int:
    """Create and run the Qt application."""
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    if owns_app:
        return app.exec()
    return 0
