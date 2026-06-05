"""Main application window."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from modbus_diagnostic_studio.gui.tabs.connection_tab import ConnectionTab
from modbus_diagnostic_studio.gui.tabs.decoder_tab import DecoderTab
from modbus_diagnostic_studio.gui.tabs.master_read_tab import MasterReadTab
from modbus_diagnostic_studio.gui.tabs.profiles_tab import ProfilesTab
from modbus_diagnostic_studio.gui.tabs.sniffer_diagnostic_tab import (
    SnifferDiagnosticTab,
)
from modbus_diagnostic_studio.gui.theme import apply_theme, available_themes


class MainWindow(QMainWindow):
    """Main Modbus Diagnostic Studio window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Modbus Diagnostic Studio")
        self.resize(980, 680)

        self._current_theme = "system"

        tabs = QTabWidget()
        tabs.addTab(ConnectionTab(), "Connection")
        tabs.addTab(DecoderTab(), "Decoder")
        tabs.addTab(MasterReadTab(), "Master Read")
        tabs.addTab(SnifferDiagnosticTab(), "Sniffer Diagnostic")
        tabs.addTab(ProfilesTab(), "Profiles")

        self.setCentralWidget(tabs)
        self._build_theme_menu()
        self._apply_theme("system")

    def _build_theme_menu(self) -> None:
        """Create a simple theme selector menu."""
        theme_menu = self.menuBar().addMenu("Theme")
        for theme_name in available_themes():
            action = theme_menu.addAction(theme_name.capitalize())
            action.setCheckable(True)
            action.setChecked(theme_name == self._current_theme)
            action.triggered.connect(lambda checked=False, name=theme_name: self._apply_theme(name))

    def _apply_theme(self, theme_name: str) -> None:
        """Apply the selected theme to the running QApplication."""
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication is not running")
        apply_theme(app, theme_name)
        self._current_theme = theme_name
        self._sync_theme_menu()

    def _sync_theme_menu(self) -> None:
        """Update check marks in the theme menu."""
        theme_menu = self.menuBar().actions()[0].menu()
        if theme_menu is None:
            return
        for action in theme_menu.actions():
            action.setChecked(action.text().lower() == self._current_theme)
