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

    app.setStyleSheet("")
    if normalized == "system":
        app.setPalette(app.style().standardPalette())
        return

    app.setPalette(_build_palette(normalized))
    app.setStyleSheet(_build_stylesheet(normalized))


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
        palette.setColor(QPalette.PlaceholderText, QColor("#6a6a6a"))
        palette.setColor(QPalette.Button, QColor("#ededed"))
        palette.setColor(QPalette.ButtonText, QColor("#1f1f1f"))
        palette.setColor(QPalette.Highlight, QColor("#d7eaff"))
        palette.setColor(QPalette.HighlightedText, QColor("#000000"))
        palette.setColor(QPalette.BrightText, QColor("#000000"))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#737373"))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#737373"))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#737373"))
        return palette

    palette.setColor(QPalette.Window, QColor("#202124"))
    palette.setColor(QPalette.WindowText, QColor("#f1f3f4"))
    palette.setColor(QPalette.Base, QColor("#14161a"))
    palette.setColor(QPalette.AlternateBase, QColor("#1d1f23"))
    palette.setColor(QPalette.ToolTipBase, QColor("#f1f3f4"))
    palette.setColor(QPalette.ToolTipText, QColor("#f1f3f4"))
    palette.setColor(QPalette.Text, QColor("#f1f3f4"))
    palette.setColor(QPalette.PlaceholderText, QColor("#9aa0a6"))
    palette.setColor(QPalette.Button, QColor("#2b2f36"))
    palette.setColor(QPalette.ButtonText, QColor("#f1f3f4"))
    palette.setColor(QPalette.Highlight, QColor("#2d7dd2"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#8a8d91"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#8a8d91"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#8a8d91"))
    return palette


def _build_stylesheet(theme_name: str) -> str:
    if theme_name == "light":
        return """
QWidget { color: #1f1f1f; }
QMenuBar, QMenu, QTabBar::tab, QLabel, QGroupBox {
    color: #1f1f1f;
}
QMenuBar { background: #f3f3f3; }
QMenu {
    background: #ffffff;
    border: 1px solid #cfcfcf;
}
QTabWidget::pane {
    border: 1px solid #cfcfcf;
    background: #f7f7f7;
}
QTabBar::tab {
    background: #e9e9e9;
    border: 1px solid #cfcfcf;
    padding: 6px 10px;
}
QTabBar::tab:selected {
    background: #ffffff;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit, QTableWidget {
    background: #ffffff;
    color: #1f1f1f;
    border: 1px solid #b8b8b8;
    selection-background-color: #d7eaff;
    selection-color: #000000;
}
QPushButton {
    background: #ededed;
    color: #1f1f1f;
    border: 1px solid #b8b8b8;
    padding: 4px 10px;
}
QPushButton:disabled, QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
    color: #737373;
}
QHeaderView::section {
    background: #ececec;
    color: #1f1f1f;
    border: 1px solid #cfcfcf;
    padding: 4px;
}
"""

    return """
QWidget { color: #f1f3f4; }
QMenuBar, QMenu, QTabBar::tab, QLabel, QGroupBox {
    color: #f1f3f4;
}
QMenuBar { background: #25282d; }
QMenu {
    background: #2b2f36;
    border: 1px solid #3a3f47;
}
QTabWidget::pane {
    border: 1px solid #3a3f47;
    background: #202124;
}
QTabBar::tab {
    background: #2b2f36;
    border: 1px solid #3a3f47;
    padding: 6px 10px;
}
QTabBar::tab:selected {
    background: #1f2329;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit, QTableWidget {
    background: #14161a;
    color: #f1f3f4;
    border: 1px solid #49505a;
    selection-background-color: #2d7dd2;
    selection-color: #ffffff;
}
QPushButton {
    background: #2b2f36;
    color: #f1f3f4;
    border: 1px solid #49505a;
    padding: 4px 10px;
}
QPushButton:disabled, QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
    color: #8a8d91;
}
QHeaderView::section {
    background: #25282d;
    color: #f1f3f4;
    border: 1px solid #3a3f47;
    padding: 4px;
}
"""
