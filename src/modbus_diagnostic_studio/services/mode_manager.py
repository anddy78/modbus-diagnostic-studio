"""Application mode and COM port reservation manager."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AppMode(Enum):
    """Top-level runtime modes that may reserve a COM port."""

    IDLE = "idle"
    MASTER_READ = "master_read"
    SNIFFER_PASSIVE = "sniffer_passive"
    SLAVE_SIMULATOR = "slave_simulator"


@dataclass(frozen=True)
class PortReservation:
    """A COM port reservation by one owner and mode."""

    mode: AppMode
    port: str
    owner: str


class ModeManager:
    """Track active COM port reservations across runtime modes."""

    _shared_reservations: dict[str, PortReservation] = {}

    def __init__(self) -> None:
        self._reservations = self._shared_reservations
        self._owned_reservation_keys: set[tuple[str, str]] = set()

    def __del__(self) -> None:
        for port, owner in list(self._owned_reservation_keys):
            existing = self._reservations.get(port)
            if existing is not None and existing.owner == owner:
                del self._reservations[port]

    def current_reservations(self) -> dict[str, PortReservation]:
        """Return a copy of current reservations by normalized port."""
        return dict(self._reservations)

    def can_reserve(self, port: str, mode: AppMode) -> bool:
        """Return True if port is free for the requested mode."""
        del mode
        return self._normalize_port(port) not in self._reservations

    def reserve(self, port: str, mode: AppMode, owner: str) -> None:
        """Reserve a port for one owner."""
        normalized_port = self._normalize_port(port)
        existing = self._reservations.get(normalized_port)
        if existing is not None:
            raise RuntimeError(
                f"Port {normalized_port} is already reserved by {existing.owner} "
                f"for {existing.mode.value}"
            )
        self._reservations[normalized_port] = PortReservation(
            mode=mode,
            port=normalized_port,
            owner=owner,
        )
        self._owned_reservation_keys.add((normalized_port, owner))

    def release(self, port: str, owner: str | None = None) -> None:
        """Release a port reservation. Missing ports are ignored."""
        normalized_port = self._normalize_port(port)
        existing = self._reservations.get(normalized_port)
        if existing is None:
            return
        if owner is not None and existing.owner != owner:
            raise RuntimeError(
                f"Port {normalized_port} is reserved by {existing.owner}, not {owner}"
            )
        del self._reservations[normalized_port]
        self._owned_reservation_keys.discard((normalized_port, existing.owner))

    def release_owner(self, owner: str) -> None:
        """Release all reservations held by owner."""
        for port, reservation in list(self._reservations.items()):
            if reservation.owner == owner:
                del self._reservations[port]
                self._owned_reservation_keys.discard((port, owner))

    def is_reserved(self, port: str) -> bool:
        """Return True if the port is currently reserved."""
        return self._normalize_port(port) in self._reservations

    def get_reservation(self, port: str) -> PortReservation | None:
        """Return the reservation for port, if any."""
        return self._reservations.get(self._normalize_port(port))

    @staticmethod
    def _normalize_port(port: str) -> str:
        normalized = port.strip().upper()
        if not normalized:
            raise ValueError("Port must not be empty")
        return normalized
