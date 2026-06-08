"""Tests for ApplicationState — no GUI, no hardware."""

from __future__ import annotations

import inspect

from modbus_diagnostic_studio.models.diagnostic_session import DiagnosticSessionEvent
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


def test_application_state_starts_without_current_session() -> None:
    state = ApplicationState()
    assert state.current_session is None


def test_application_state_new_session_creates_current_session() -> None:
    state = ApplicationState()

    session = state.new_session(title="Test Session", technician="Pat")

    assert state.current_session is session
    assert session.metadata.title == "Test Session"
    assert session.metadata.technician == "Pat"


def test_application_state_add_session_event_appends_to_active_session() -> None:
    state = ApplicationState()
    state.new_session()

    state.add_session_event(
        DiagnosticSessionEvent(
            timestamp="2026-06-08T12:00:00+00:00",
            source="system",
            event_type="note",
            severity="info",
            summary="Created manually",
            details={},
        )
    )

    assert state.current_session is not None
    assert len(state.current_session.events) == 1
    assert state.current_session.events[0].summary == "Created manually"


def test_application_state_add_session_event_without_session_is_safe() -> None:
    state = ApplicationState()
    result = state.add_session_event(
        DiagnosticSessionEvent(
            timestamp="2026-06-08T12:00:00+00:00",
            source="system",
            event_type="note",
            severity="info",
            summary="Ignored",
            details={},
        )
    )
    assert result is None


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


def test_shared_app_state_mode_manager_sees_all_reservations() -> None:
    """All components using the same ApplicationState observe the same reservations."""
    from modbus_diagnostic_studio.services.mode_manager import AppMode

    state = ApplicationState()
    mm = state.mode_manager

    mm.reserve("COM1", AppMode.MASTER_READ, "component_a")

    # Accessing via the same ApplicationState reference sees the reservation
    assert state.mode_manager.is_reserved("COM1") is True

    mm.release("COM1", "component_a")
    assert state.mode_manager.is_reserved("COM1") is False


def test_two_app_states_have_isolated_reservations() -> None:
    """Two separate ApplicationState instances have completely independent reservations."""
    from modbus_diagnostic_studio.services.mode_manager import AppMode

    state_a = ApplicationState()
    state_b = ApplicationState()

    state_a.mode_manager.reserve("COM1", AppMode.MASTER_READ, "owner_a")

    assert state_a.mode_manager.is_reserved("COM1") is True
    assert state_b.mode_manager.is_reserved("COM1") is False


def test_main_window_has_app_state_attribute() -> None:
    import inspect
    from modbus_diagnostic_studio.gui.main_window import MainWindow
    # Verify the attribute exists at class level via __init__ source inspection
    # without instantiating (which requires QApplication)
    src = inspect.getsource(MainWindow.__init__)
    assert "self.app_state = ApplicationState()" in src
