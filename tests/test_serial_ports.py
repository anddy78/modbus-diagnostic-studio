"""Tests for serial port discovery."""

from dataclasses import dataclass

from modbus_diagnostic_studio.transports import serial_ports


@dataclass
class FakePort:
    device: str
    name: str
    description: str
    hwid: str
    manufacturer: str | None = None
    vid: int | None = None
    pid: int | None = None


def test_list_serial_ports_maps_and_sorts(monkeypatch) -> None:
    monkeypatch.setattr(
        serial_ports.list_ports,
        "comports",
        lambda: [
            FakePort(
                device="COM10",
                name="COM10",
                description="Second",
                hwid="B",
                manufacturer="Beta",
                vid=2,
                pid=20,
            ),
            FakePort(
                device="COM3",
                name="COM3",
                description="First",
                hwid="A",
                manufacturer="Alpha",
                vid=1,
                pid=10,
            ),
        ],
    )

    ports = serial_ports.list_serial_ports()

    assert [port.device for port in ports] == ["COM3", "COM10"]
    assert ports[0].description == "First"
    assert ports[0].hwid == "A"
    assert ports[0].manufacturer == "Alpha"
    assert ports[0].vid == 1
    assert ports[0].pid == 10


def test_list_serial_ports_returns_empty_list(monkeypatch) -> None:
    monkeypatch.setattr(serial_ports.list_ports, "comports", lambda: [])

    assert serial_ports.list_serial_ports() == []
