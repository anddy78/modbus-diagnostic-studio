"""Smoke tests for GUI imports without showing windows."""

import pytest


pytest.importorskip("PySide6")


def test_gui_imports() -> None:
    from modbus_diagnostic_studio.gui.app import run_app
    from modbus_diagnostic_studio.gui.help import attach_help_menu, set_help
    from modbus_diagnostic_studio.gui.main_window import MainWindow
    from modbus_diagnostic_studio.gui.tabs import (
        AdvancedMasterTab,
        ConnectionTab,
        DecoderTab,
        MasterReadTab,
        MetersTab,
        ProfilesTab,
        SlaveSimulatorTab,
        SnifferDiagnosticTab,
    )
    from modbus_diagnostic_studio.gui.theme import available_themes, apply_theme

    assert callable(run_app)
    assert MainWindow.__name__ == "MainWindow"
    assert AdvancedMasterTab.__name__ == "AdvancedMasterTab"
    assert ConnectionTab.__name__ == "ConnectionTab"
    assert DecoderTab.__name__ == "DecoderTab"
    assert MasterReadTab.__name__ == "MasterReadTab"
    assert MetersTab.__name__ == "MetersTab"
    assert ProfilesTab.__name__ == "ProfilesTab"
    assert SlaveSimulatorTab.__name__ == "SlaveSimulatorTab"
    assert SnifferDiagnosticTab.__name__ == "SnifferDiagnosticTab"
    assert available_themes() == ["system", "light", "dark"]
    assert callable(apply_theme)
    assert callable(set_help)
    assert callable(attach_help_menu)


def test_main_window_theme_references_exist() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from modbus_diagnostic_studio.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.theme_menu is not None
    assert window.help_menu is not None
    assert set(window.theme_actions) == {"system", "light", "dark"}
    assert {"quick_start", "safety", "about"} <= set(window.help_actions)


def test_sniffer_tab_export_methods_exist() -> None:
    from modbus_diagnostic_studio.gui.tabs.sniffer_diagnostic_tab import SnifferDiagnosticTab

    assert callable(SnifferDiagnosticTab.export_events_csv)
    assert callable(SnifferDiagnosticTab.export_events_jsonl)
    assert callable(SnifferDiagnosticTab.export_exchanges_csv)
    assert callable(SnifferDiagnosticTab.export_exchanges_jsonl)


def test_decode_registers_uint16() -> None:
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import decode_registers

    rows = decode_registers([0x0001, 0x8000, 0xFFFF], start_address=100, fmt="uint16")
    assert len(rows) == 3
    assert rows[0].offset == 0
    assert rows[0].address == 100
    assert rows[0].raw_uint16 == 1
    assert rows[0].hex_str == "0x0001"
    assert rows[0].bin_str == "0000000000000001"
    assert rows[0].decoded == "1"
    assert rows[2].decoded == "65535"


def test_decode_registers_int16() -> None:
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import decode_registers

    rows = decode_registers([0x0001, 0x8000, 0xFFFF], start_address=0, fmt="int16")
    assert rows[0].decoded == "1"
    assert rows[1].decoded == "-32768"
    assert rows[2].decoded == "-1"


def test_decode_registers_uint32() -> None:
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import decode_registers

    # 0x0001_0002 = 65538
    rows = decode_registers([0x0001, 0x0002], start_address=0, fmt="uint32")
    assert len(rows) == 2
    assert rows[0].decoded == "65538"
    assert rows[1].decoded == "-"


def test_decode_registers_int32_negative() -> None:
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import decode_registers

    # 0xFFFF_FFFF = -1 as int32
    rows = decode_registers([0xFFFF, 0xFFFF], start_address=0, fmt="int32")
    assert rows[0].decoded == "-1"
    assert rows[1].decoded == "-"


def test_decode_registers_float32() -> None:
    import struct
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import decode_registers

    raw = struct.pack(">f", 1.5)
    high = int.from_bytes(raw[:2], "big")
    low = int.from_bytes(raw[2:], "big")
    rows = decode_registers([high, low], start_address=0, fmt="float32")
    assert float(rows[0].decoded) == pytest.approx(1.5, rel=1e-5)
    assert rows[1].decoded == "-"


def test_decode_registers_float32_word_swap() -> None:
    import struct
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import decode_registers

    # word-swap: low word first in the register list
    raw = struct.pack(">f", 2.5)
    high = int.from_bytes(raw[:2], "big")
    low = int.from_bytes(raw[2:], "big")
    # pass as [low, high] so that word-swap reorders to [high, low]
    rows = decode_registers([low, high], start_address=0, fmt="float32 word-swap")
    assert float(rows[0].decoded) == pytest.approx(2.5, rel=1e-5)


def test_decode_registers_hex_and_binary() -> None:
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import decode_registers

    rows_hex = decode_registers([0xABCD], start_address=5, fmt="hex")
    assert rows_hex[0].decoded == "0xABCD"
    assert rows_hex[0].address == 5

    rows_bin = decode_registers([0b1010101010101010], start_address=0, fmt="binary")
    assert rows_bin[0].decoded == "1010101010101010"


def test_decode_registers_incomplete_pair() -> None:
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import decode_registers

    rows = decode_registers([0x0001], start_address=0, fmt="uint32")
    assert len(rows) == 1
    assert "incomplete" in rows[0].decoded


def test_tab_constructors_accept_optional_app_state() -> None:
    """Tabs expose optional app_state and can build with a QApplication."""
    import inspect
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import AdvancedMasterTab
    from modbus_diagnostic_studio.gui.tabs.master_read_tab import MasterReadTab
    from modbus_diagnostic_studio.gui.tabs.meters_tab import MetersTab
    from modbus_diagnostic_studio.gui.tabs.slave_simulator_tab import SlaveSimulatorTab
    from modbus_diagnostic_studio.gui.tabs.sniffer_diagnostic_tab import SnifferDiagnosticTab

    app = QApplication.instance() or QApplication([])

    for cls in (AdvancedMasterTab, MasterReadTab, MetersTab, SlaveSimulatorTab, SnifferDiagnosticTab):
        params = inspect.signature(cls.__init__).parameters
        assert "app_state" in params, f"{cls.__name__} missing app_state"
        assert params["app_state"].default is None
        widget = cls()
        assert widget is not None


def test_decode_bits() -> None:
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import decode_bits

    rows = decode_bits([True, False, True], start_address=10)
    assert len(rows) == 3
    assert rows[0].offset == 0
    assert rows[0].address == 10
    assert rows[0].raw_uint16 == 1
    assert rows[0].decoded == "ON"
    assert rows[1].raw_uint16 == 0
    assert rows[1].decoded == "OFF"
    assert rows[2].decoded == "ON"


def test_meters_tab_grouping() -> None:
    from modbus_diagnostic_studio.gui.tabs.meters_tab import _classify_variable

    assert _classify_variable("voltage_l1") == "Voltage"
    assert _classify_variable("current_l2") == "Current"
    assert _classify_variable("active_power") == "Power"
    assert _classify_variable("reactive_power") == "Power"
    assert _classify_variable("apparent_power") == "Power"
    assert _classify_variable("power_factor") == "Power"
    assert _classify_variable("pf_total") == "Power"
    assert _classify_variable("total_energy_kwh") == "Energy"
    assert _classify_variable("import_kvarh") == "Energy"
    assert _classify_variable("frequency") == "Other"
    assert _classify_variable("total_energy") == "Energy"
