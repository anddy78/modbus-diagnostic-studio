"""Global application state owns shared mode reservations and diagnostic session state."""

from __future__ import annotations

from modbus_diagnostic_studio.models.diagnostic_session import (
    DiagnosticSession,
    DiagnosticSessionEvent,
    add_event,
    create_new_session,
)
from modbus_diagnostic_studio.services.mode_manager import ModeManager


class ApplicationState:
    """Single shared application state created by MainWindow."""

    def __init__(self) -> None:
        self.mode_manager: ModeManager = ModeManager()
        self.current_session: DiagnosticSession | None = None

    def new_session(
        self,
        *,
        title: str = "",
        customer: str = "",
        site: str = "",
        equipment: str = "",
        technician: str = "",
        notes: str = "",
    ) -> DiagnosticSession:
        """Create and store a new active diagnostic session."""
        self.current_session = create_new_session(
            title=title,
            customer=customer,
            site=site,
            equipment=equipment,
            technician=technician,
            notes=notes,
        )
        return self.current_session

    def add_session_event(
        self,
        event: DiagnosticSessionEvent,
    ) -> DiagnosticSession | None:
        """Append one event to the active session if a session exists."""
        if self.current_session is None:
            return None
        return add_event(self.current_session, event)
