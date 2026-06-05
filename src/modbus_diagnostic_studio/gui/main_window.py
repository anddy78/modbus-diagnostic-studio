"""Main application window."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from modbus_diagnostic_studio.gui.tabs.connection_tab import ConnectionTab
from modbus_diagnostic_studio.gui.tabs.decoder_tab import DecoderTab
from modbus_diagnostic_studio.gui.tabs.profiles_tab import ProfilesTab


class MainWindow(QMainWindow):
    """Main Modbus Diagnostic Studio window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Modbus Diagnostic Studio")
        self.resize(980, 680)

        tabs = QTabWidget()
        tabs.addTab(ConnectionTab(), "Connection")
        tabs.addTab(DecoderTab(), "Decoder")
        tabs.addTab(ProfilesTab(), "Profiles")

        self.setCentralWidget(tabs)
