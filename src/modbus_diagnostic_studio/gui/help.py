"""Small GUI help utilities."""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu, QMessageBox, QWidget


def set_help(widget: QWidget, title: str, text: str) -> None:
    """Attach tooltip, What's This text, and a small context help menu."""
    widget.setToolTip(text)
    widget.setWhatsThis(text)
    widget.setContextMenuPolicy(Qt.CustomContextMenu)
    widget.customContextMenuRequested.connect(
        partial(_show_help_context_menu, widget, title, text)
    )


def attach_help_menu(window: QMainWindow) -> None:
    """Add a persistent Help menu with a few practical actions."""
    help_menu = window.menuBar().addMenu("Help")
    help_actions: dict[str, QAction] = {}

    action_specs = {
        "quick_start": (
            "Quick Start",
            "Quick Start",
            "Serial Ports lists COM ports without opening them.\n\n"
            "Meter Dashboard reads known meter profiles with a friendlier view.\n\n"
            "Advanced Master performs generic Modbus reads and guarded writes.\n\n"
            "Slave Simulator responds as a local Modbus slave for safe testing.\n\n"
            "Sniffer Diagnostic listens passively and does not transmit.\n\n"
            "Diagnostic Report centralizes notes and exported evidence without opening ports.",
        ),
        "safety": (
            "Safety / Write Warning",
            "Safety / Write Warning",
            "Master Write can modify real devices.\n\n"
            "Write mode stays locked by default.\n\n"
            "Test against Slave Simulator first.\n\n"
            "Do not use write functions on real equipment without explicit authorization.",
        ),
        "about": (
            "About",
            "About Modbus Diagnostic Studio",
            "Modbus Diagnostic Studio\n"
            "Version 0.1.0-beta\n\n"
            "Industrial Modbus diagnostic tool",
        ),
    }

    for key, (label, title, text) in action_specs.items():
        action = help_menu.addAction(label)
        action.triggered.connect(
            partial(QMessageBox.information, window, title, text)
        )
        help_actions[key] = action

    window.help_menu = help_menu
    window.help_actions = help_actions


def _show_help_context_menu(
    widget: QWidget,
    title: str,
    text: str,
    position: QPoint,
) -> None:
    menu = QMenu(widget)
    help_action = menu.addAction("Que es esto?")
    selected = menu.exec(widget.mapToGlobal(position))
    if selected is help_action:
        QMessageBox.information(widget, title, text)
