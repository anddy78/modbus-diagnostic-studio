"""Global application state — owns the single shared ModeManager."""

from __future__ import annotations

from modbus_diagnostic_studio.services.mode_manager import ModeManager


class ApplicationState:
    """Single shared application state created by MainWindow.

    All tabs that reserve COM ports must receive the same ApplicationState
    instance so that the ModeManager sees every active reservation.
    """

    def __init__(self) -> None:
        self.mode_manager: ModeManager = ModeManager()
