"""Tests for active Modbus master client with fake transport."""

import pytest

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.master.client import ModbusMasterClient


class FakeTransport:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.requests: list[bytes] = []

    def transact(self, request: bytes, expected_min_response_size: int = 5) -> bytes:
        self.requests.append(request)
        return self.response


def test_read_holding_registers_builds_fc03_request_and_returns_registers() -> None:
    response = append_crc(bytes.fromhex("01 03 04 00 2A 00 64"))
    transport = FakeTransport(response)
    client = ModbusMasterClient(transport)

    registers = client.read_holding_registers(slave_id=1, address=0, quantity=2)

    assert registers == [42, 100]
    assert transport.requests == [bytes.fromhex("01 03 00 00 00 02 C4 0B")]


def test_read_input_registers_builds_fc04_request_and_returns_registers() -> None:
    response = append_crc(bytes.fromhex("11 04 04 00 2A 00 64"))
    transport = FakeTransport(response)
    client = ModbusMasterClient(transport)

    registers = client.read_input_registers(slave_id=0x11, address=0x0010, quantity=2)

    assert registers == [42, 100]
    assert transport.requests == [append_crc(bytes.fromhex("11 04 00 10 00 02"))]


def test_read_rejects_invalid_slave_id() -> None:
    client = ModbusMasterClient(FakeTransport(b""))

    with pytest.raises(ValueError, match="slave_id"):
        client.read_holding_registers(slave_id=0, address=0, quantity=1)


def test_read_rejects_invalid_quantity() -> None:
    client = ModbusMasterClient(FakeTransport(b""))

    with pytest.raises(ValueError, match="quantity"):
        client.read_holding_registers(slave_id=1, address=0, quantity=0)


def test_exception_response_raises_runtime_error() -> None:
    response = append_crc(bytes.fromhex("01 83 02"))
    client = ModbusMasterClient(FakeTransport(response))

    with pytest.raises(RuntimeError, match="exception response: code 2"):
        client.read_holding_registers(slave_id=1, address=0, quantity=2)


def test_invalid_crc_response_raises_runtime_error() -> None:
    response = bytes.fromhex("01 03 04 00 2A 00 64 00 00")
    client = ModbusMasterClient(FakeTransport(response))

    with pytest.raises(RuntimeError, match="invalid CRC"):
        client.read_holding_registers(slave_id=1, address=0, quantity=2)
