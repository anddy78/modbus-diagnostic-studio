"""Tests for application mode manager."""

import pytest

from modbus_diagnostic_studio.services.mode_manager import (
    AppMode,
    ModeManager,
    PortReservation,
)


def test_reserve_and_query_port() -> None:
    manager = ModeManager()

    manager.reserve("COM3", AppMode.MASTER_READ, "reader")

    assert manager.is_reserved("COM3") is True
    assert manager.can_reserve("COM3", AppMode.SNIFFER_PASSIVE) is False
    reservation = manager.get_reservation("COM3")
    assert reservation == PortReservation(
        mode=AppMode.MASTER_READ,
        port="COM3",
        owner="reader",
    )


def test_port_is_normalized_to_uppercase() -> None:
    manager = ModeManager()

    manager.reserve("com4", AppMode.SNIFFER_PASSIVE, "sniffer")

    assert manager.is_reserved("COM4") is True
    assert "COM4" in manager.current_reservations()


def test_cannot_reserve_same_port_twice() -> None:
    manager = ModeManager()
    manager.reserve("COM3", AppMode.MASTER_READ, "reader")

    with pytest.raises(RuntimeError, match="already reserved"):
        manager.reserve("com3", AppMode.SNIFFER_PASSIVE, "sniffer")


def test_release_correct_owner() -> None:
    manager = ModeManager()
    manager.reserve("COM3", AppMode.MASTER_READ, "reader")

    manager.release("COM3", owner="reader")

    assert manager.is_reserved("COM3") is False


def test_release_wrong_owner_raises() -> None:
    manager = ModeManager()
    manager.reserve("COM3", AppMode.MASTER_READ, "reader")

    with pytest.raises(RuntimeError, match="reserved by reader"):
        manager.release("COM3", owner="other")


def test_release_owner_releases_multiple_ports() -> None:
    manager = ModeManager()
    manager.reserve("COM3", AppMode.MASTER_READ, "reader")
    manager.reserve("COM4", AppMode.SLAVE_SIMULATOR, "reader")
    manager.reserve("COM5", AppMode.SNIFFER_PASSIVE, "sniffer")

    manager.release_owner("reader")

    assert manager.is_reserved("COM3") is False
    assert manager.is_reserved("COM4") is False
    assert manager.is_reserved("COM5") is True


def test_release_missing_port_is_noop() -> None:
    manager = ModeManager()

    manager.release("COM9")

    assert manager.current_reservations() == {}


def test_two_instances_do_not_share_reservations() -> None:
    """Instance-level storage: a reservation on mm1 is invisible to mm2."""
    mm1 = ModeManager()
    mm2 = ModeManager()

    mm1.reserve("COM3", AppMode.MASTER_READ, "owner_a")

    assert mm1.is_reserved("COM3") is True
    assert mm2.is_reserved("COM3") is False
