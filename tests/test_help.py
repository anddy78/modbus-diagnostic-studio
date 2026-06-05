"""Tests for small GUI help helpers."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from modbus_diagnostic_studio.gui.help import attach_help_menu, set_help


def test_set_help_assigns_tooltip_and_whats_this() -> None:
    app = QApplication.instance() or QApplication([])
    label = QLabel("test")

    set_help(label, "Example", "Helpful text")

    assert label.toolTip() == "Helpful text"
    assert label.whatsThis() == "Helpful text"
    assert label.contextMenuPolicy() == Qt.CustomContextMenu


def test_attach_help_menu_creates_actions() -> None:
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()

    attach_help_menu(window)

    assert window.help_menu is not None
    assert {"quick_start", "safety", "about"} <= set(window.help_actions)
