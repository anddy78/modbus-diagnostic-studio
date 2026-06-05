"""GUI theme helpers."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

_THEMES = ("system", "light", "dark")


def available_themes() -> list[str]:
    """Return the supported theme names."""
    return list(_THEMES)


def apply_theme(app: QApplication, theme_name: str) -> None:
    """Apply one of the supported GUI themes."""
    normalized = theme_name.strip().lower()
    if normalized not in _THEMES:
        raise ValueError(f"Unsupported theme: {theme_name}")

    if normalized == "system":
        app.setStyleSheet("")
        app.setPalette(app.style().standardPalette())
        return

    app.setStyleSheet("")
    app.setPalette(_build_palette(normalized))


def _build_palette(theme_name: str) -> QPalette:
    palette = QPalette()
    if theme_name == "light":
        palette.setColor(QPalette.Window, QColor("#f7f7f7"))
        palette.setColor(QPalette.WindowText, QColor("#1f1f1f"))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f0f0f0"))
        palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipText, QColor("#1f1f1f"))
        palette.setColor(QPalette.Text, QColor("#1f1f1f"))
        palette.setColor(QPalette.Button, QColor("#ededed"))
        palette.setColor(QPalette.ButtonText, QColor("#1f1f1f"))
        palette.setColor(QPalette.Highlight, QColor("#d7eaff"))
        palette.setColor(QPalette.HighlightedText, QColor("#000000"))
        return palette

    palette.setColor(QPalette.Window, QColor("#202124"))
    palette.setColor(QPalette.WindowText, QColor("#f1f3f4"))
    palette.setColor(QPalette.Base, QColor("#14161a"))
    palette.setColor(QPalette.AlternateBase, QColor("#1d1f23"))
    palette.setColor(QPalette.ToolTipBase, QColor("#f1f3f4"))
    palette.setColor(QPalette.ToolTipText, QColor("#f1f3f4"))
    palette.setColor(QPalette.Text, QColor("#f1f3f4"))
    palette.setColor(QPalette.Button, QColor("#2b2f36"))
    palette.setColor(QPalette.ButtonText, QColor("#f1f3f4"))
    palette.setColor(QPalette.Highlight, QColor("#2d7dd2"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    return palette
