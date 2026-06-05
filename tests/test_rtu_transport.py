"""Tests for minimal RTU transport using fake serial objects."""

import pytest

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.transports.rtu_transport import RtuTransport


class FakeSerial:
    def __init__(self, read_data: bytes = b"", fail_write: bool = False) -> None:
        self.is_open = False
        self.read_data = bytearray(read_data)
        self.written = bytearray()
        self.fail_write = fail_write

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def write(self, data: bytes) -> int:
        if self.fail_write:
            raise OSError("disconnected")
        self.written.extend(data)
        return len(data)

    def read(self, size: int) -> bytes:
        chunk = self.read_data[:size]
        del self.read_data[:size]
        return bytes(chunk)


def settings() -> SerialConnectionSettings:
    return SerialConnectionSettings(port="COM3", timeout=0.01)


def test_rtu_transport_open_close_with_fake_serial() -> None:
    fake = FakeSerial()
    transport = RtuTransport(settings(), serial_factory=lambda _: fake)

    transport.open()
    assert transport.is_open is True

    transport.close()
    assert transport.is_open is False


def test_write_frame_without_open_raises() -> None:
    transport = RtuTransport(settings(), serial_factory=lambda _: FakeSerial())

    with pytest.raises(RuntimeError, match="not open"):
        transport.write_frame(b"\x01")


def test_write_frame_open_writes_bytes() -> None:
    fake = FakeSerial()
    transport = RtuTransport(settings(), serial_factory=lambda _: fake)
    transport.open()

    transport.write_frame(b"\x01\x03")

    assert bytes(fake.written) == b"\x01\x03"


def test_read_exact_returns_expected_bytes() -> None:
    fake = FakeSerial(read_data=b"\x01\x02\x03")
    transport = RtuTransport(settings(), serial_factory=lambda _: fake)
    transport.open()

    assert transport.read_exact(3) == b"\x01\x02\x03"


def test_transact_normal_fc03_response() -> None:
    request = append_crc(bytes.fromhex("01 03 00 00 00 02"))
    response = append_crc(bytes.fromhex("01 03 04 00 2A 00 64"))
    fake = FakeSerial(read_data=response)
    transport = RtuTransport(settings(), serial_factory=lambda _: fake)
    transport.open()

    assert transport.transact(request) == response
    assert bytes(fake.written) == request


def test_transact_exception_response() -> None:
    request = append_crc(bytes.fromhex("01 03 00 00 00 02"))
    response = append_crc(bytes.fromhex("01 83 02"))
    fake = FakeSerial(read_data=response)
    transport = RtuTransport(settings(), serial_factory=lambda _: fake)
    transport.open()

    assert transport.transact(request) == response


def test_serial_error_is_runtime_error() -> None:
    fake = FakeSerial(fail_write=True)
    transport = RtuTransport(settings(), serial_factory=lambda _: fake)
    transport.open()

    with pytest.raises(RuntimeError, match="write failed"):
        transport.write_frame(b"\x01")
