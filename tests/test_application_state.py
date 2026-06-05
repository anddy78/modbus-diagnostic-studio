"""Tests for ApplicationState — no GUI, no hardware."""

from __future__ import annotations

import inspect

from modbus_diagnostic_studio.services.application_state import ApplicationState
from modbus_diagnostic_studio.services.mode_manager import ModeManager


def test_application_state_has_mode_manager() -> None:
    state = ApplicationState()
    assert isinstance(state.mode_manager, ModeManager)


def test_two_accessors_on_same_state_return_same_instance() -> None:
    state = ApplicationState()
    assert state.mode_manager is state.mode_manager


def test_two_states_have_independent_mode_managers() -> None:
    state_a = ApplicationState()
    state_b = ApplicationState()
    assert state_a.mode_manager is not state_b.mode_manager


def test_tab_constructors_accept_app_state_parameter() -> None:
    pytest_importorskip = None  # just a note — no QApplication needed for inspect
    from modbus_diagnostic_studio.gui.tabs.advanced_master_tab import AdvancedMasterTab
    from modbus_diagnostic_studio.gui.tabs.master_read_tab import MasterReadTab
    from modbus_diagnostic_studio.gui.tabs.meters_tab import MetersTab
    from modbus_diagnostic_studio.gui.tabs.slave_simulator_tab import SlaveSimulatorTab
    from modbus_diagnostic_studio.gui.tabs.sniffer_diagnostic_tab import SnifferDiagnosticTab

    for tab_class in (
        AdvancedMasterTab,
        MasterReadTab,
        MetersTab,
        SlaveSimulatorTab,
        SnifferDiagnosticTab,
    ):
        sig = inspect.signature(tab_class.__init__)
        params = sig.parameters
        assert "app_state" in params, f"{tab_class.__name__} missing app_state parameter"
        assert params["app_state"].default is None, (
            f"{tab_class.__name__}.app_state default is not None"
        )


def test_main_window_has_app_state_attribute() -> None:
    import inspect
    from modbus_diagnostic_studio.gui.main_window import MainWindow
    # Verify the attribute exists at class level via __init__ source inspection
    # without instantiating (which requires QApplication)
    src = inspect.getsource(MainWindow.__init__)
    assert "self.app_state = ApplicationState()" in src
