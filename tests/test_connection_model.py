"""Tests for serial connection models."""

import pytest

from modbus_diagnostic_studio.models.connection import (
    SerialConnectionSettings,
    SerialPortInfo,
)


def test_serial_connection_settings_valid() -> None:
    settings = SerialConnectionSettings(port="COM3")

    assert settings.port == "COM3"
    assert settings.baudrate == 9600
    assert settings.bytesize == 8
    assert settings.parity == "N"
    assert settings.stopbits == 1
    assert settings.timeout == 1.0


def test_serial_connection_settings_rejects_empty_port() -> None:
    with pytest.raises(ValueError, match="port"):
        SerialConnectionSettings(port="")


def test_serial_connection_settings_rejects_invalid_baudrate() -> None:
    with pytest.raises(ValueError, match="baudrate"):
        SerialConnectionSettings(port="COM3", baudrate=0)


def test_serial_connection_settings_rejects_invalid_parity() -> None:
    with pytest.raises(ValueError, match="parity"):
        SerialConnectionSettings(port="COM3", parity="X")


def test_serial_connection_settings_rejects_invalid_stopbits() -> None:
    with pytest.raises(ValueError, match="stopbits"):
        SerialConnectionSettings(port="COM3", stopbits=1.2)


def test_serial_port_info_basic() -> None:
    port = SerialPortInfo(
        device="COM3",
        name="COM3",
        description="USB Serial Port",
        hwid="USB VID:PID=1234:5678",
        manufacturer="Example",
        vid=0x1234,
        pid=0x5678,
    )

    assert port.device == "COM3"
    assert port.manufacturer == "Example"
    assert port.vid == 0x1234
    assert port.pid == 0x5678
