"""Smoke tests for GUI imports without showing windows."""

import pytest


pytest.importorskip("PySide6")


def test_gui_imports() -> None:
    from modbus_diagnostic_studio.gui.app import run_app
    from modbus_diagnostic_studio.gui.main_window import MainWindow
    from modbus_diagnostic_studio.gui.tabs import (
        ConnectionTab,
        DecoderTab,
        MasterReadTab,
        MetersTab,
        ProfilesTab,
        SnifferDiagnosticTab,
    )
    from modbus_diagnostic_studio.gui.theme import available_themes, apply_theme

    assert callable(run_app)
    assert MainWindow.__name__ == "MainWindow"
    assert ConnectionTab.__name__ == "ConnectionTab"
    assert DecoderTab.__name__ == "DecoderTab"
    assert MasterReadTab.__name__ == "MasterReadTab"
    assert MetersTab.__name__ == "MetersTab"
    assert ProfilesTab.__name__ == "ProfilesTab"
    assert SnifferDiagnosticTab.__name__ == "SnifferDiagnosticTab"
    assert available_themes() == ["system", "light", "dark"]
    assert callable(apply_theme)


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
