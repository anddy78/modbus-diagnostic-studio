"""GUI tab widgets."""

from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import AdvancedMasterTab
from modbus_diagnostic_studio.gui.tabs.connection_tab import ConnectionTab
from modbus_diagnostic_studio.gui.tabs.decoder_tab import DecoderTab
from modbus_diagnostic_studio.gui.tabs.master_read_tab import MasterReadTab
from modbus_diagnostic_studio.gui.tabs.meters_tab import MetersTab
from modbus_diagnostic_studio.gui.tabs.profiles_tab import ProfilesTab
from modbus_diagnostic_studio.gui.tabs.slave_simulator_tab import SlaveSimulatorTab
from modbus_diagnostic_studio.gui.tabs.sniffer_diagnostic_tab import (
    SnifferDiagnosticTab,
)

__all__ = [
    "AdvancedMasterTab",
    "ConnectionTab",
    "DecoderTab",
    "MasterReadTab",
    "MetersTab",
    "ProfilesTab",
    "SlaveSimulatorTab",
    "SnifferDiagnosticTab",
]
