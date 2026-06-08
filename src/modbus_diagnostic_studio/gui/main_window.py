"""Main application window."""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from modbus_diagnostic_studio.gui.help import attach_help_menu
from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import AdvancedMasterTab
from modbus_diagnostic_studio.gui.tabs.capture_viewer_tab import CaptureViewerTab
from modbus_diagnostic_studio.gui.tabs.connection_tab import ConnectionTab
from modbus_diagnostic_studio.gui.tabs.decoder_tab import DecoderTab
from modbus_diagnostic_studio.gui.tabs.diagnostic_report_tab import DiagnosticReportTab
from modbus_diagnostic_studio.gui.tabs.master_read_tab import MasterReadTab
from modbus_diagnostic_studio.gui.tabs.meters_tab import MetersTab
from modbus_diagnostic_studio.gui.tabs.profile_manager_tab import ProfileManagerTab
from modbus_diagnostic_studio.gui.tabs.profiles_tab import ProfilesTab
from modbus_diagnostic_studio.gui.tabs.slave_simulator_tab import SlaveSimulatorTab
from modbus_diagnostic_studio.gui.tabs.sniffer_diagnostic_tab import (
    SnifferDiagnosticTab,
)
from modbus_diagnostic_studio.gui.theme import apply_theme, available_themes
from modbus_diagnostic_studio.services.application_state import ApplicationState


class MainWindow(QMainWindow):
    """Main Modbus Diagnostic Studio window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Modbus Diagnostic Studio")
        self.resize(980, 680)

        self._current_theme = "system"
        self.app_state = ApplicationState()
        self.theme_menu = self.menuBar().addMenu("Theme")
        self.theme_actions: dict[str, QAction] = {}
        self.help_menu = None
        self.help_actions: dict[str, QAction] = {}

        self.tabs = QTabWidget()
        self._legacy_profiles_tab_class = ProfilesTab
        self.tabs.addTab(ConnectionTab(), "Serial Ports")
        self.tabs.addTab(MetersTab(self.app_state), "Meter Dashboard")
        self.tabs.addTab(AdvancedMasterTab(self.app_state), "Advanced Master")
        self.tabs.addTab(SlaveSimulatorTab(self.app_state), "Slave Simulator")
        self.tabs.addTab(SnifferDiagnosticTab(self.app_state), "Sniffer Diagnostic")
        self.tabs.addTab(CaptureViewerTab(self.app_state), "Capture Viewer")
        self.tabs.addTab(DecoderTab(), "Raw Frame Decoder")
        self.tabs.addTab(MasterReadTab(self.app_state), "Basic Master")
        self.tabs.addTab(ProfileManagerTab(), "Profile Manager")
        self.tabs.addTab(DiagnosticReportTab(self.app_state), "Diagnostic Report")

        self.setCentralWidget(self.tabs)
        self._build_theme_menu()
        attach_help_menu(self)
        self._apply_theme("system")

    def _build_theme_menu(self) -> None:
        """Create a simple theme selector menu."""
        self.theme_menu.clear()
        self.theme_actions.clear()
        for theme_name in available_themes():
            action = self.theme_menu.addAction(theme_name.capitalize())
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, name=theme_name: self._apply_theme(name))
            self.theme_actions[theme_name] = action
        self._sync_theme_menu()

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
        for theme_name, action in self.theme_actions.items():
            action.setChecked(theme_name == self._current_theme)
