"""Tests for GUI theme helpers."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from modbus_diagnostic_studio.gui.theme import available_themes, apply_theme


def test_available_themes_lists_supported_names() -> None:
    assert available_themes() == ["system", "light", "dark"]


def test_apply_theme_rejects_invalid_name() -> None:
    app = QApplication.instance() or QApplication([])

    with pytest.raises(ValueError, match="Unsupported theme"):
        apply_theme(app, "purple")


def test_apply_theme_light_and_dark_change_palette() -> None:
    app = QApplication.instance() or QApplication([])

    apply_theme(app, "light")
    light_window = app.palette().color(QPalette.Window)

    apply_theme(app, "dark")
    dark_window = app.palette().color(QPalette.Window)

    assert isinstance(light_window, QColor)
    assert isinstance(dark_window, QColor)
    assert light_window != dark_window
