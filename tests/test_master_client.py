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


# ── write_single_coil (FC05) ──────────────────────────────────────────────────


def test_write_single_coil_on_builds_correct_request() -> None:
    response = append_crc(bytes([0x01, 0x05, 0x00, 0x00, 0xFF, 0x00]))
    transport = FakeTransport(response)
    client = ModbusMasterClient(transport)

    result = client.write_single_coil(slave_id=1, address=0, value=True)

    assert result is True
    expected = append_crc(bytes([0x01, 0x05, 0x00, 0x00, 0xFF, 0x00]))
    assert transport.requests[0] == expected


def test_write_single_coil_off_builds_correct_request() -> None:
    response = append_crc(bytes([0x01, 0x05, 0x00, 0x05, 0x00, 0x00]))
    transport = FakeTransport(response)
    client = ModbusMasterClient(transport)

    result = client.write_single_coil(slave_id=1, address=5, value=False)

    assert result is False
    expected = append_crc(bytes([0x01, 0x05, 0x00, 0x05, 0x00, 0x00]))
    assert transport.requests[0] == expected


def test_write_single_coil_echo_address_mismatch_raises() -> None:
    # Echo returns address=1, but we wrote to address=0
    response = append_crc(bytes([0x01, 0x05, 0x00, 0x01, 0xFF, 0x00]))
    client = ModbusMasterClient(FakeTransport(response))

    with pytest.raises(RuntimeError, match="mismatch"):
        client.write_single_coil(slave_id=1, address=0, value=True)


def test_write_single_coil_invalid_crc_raises() -> None:
    valid = append_crc(bytes([0x01, 0x05, 0x00, 0x00, 0xFF, 0x00]))
    bad_crc = valid[:-1] + bytes([valid[-1] ^ 0xFF])
    client = ModbusMasterClient(FakeTransport(bad_crc))

    with pytest.raises(RuntimeError, match="invalid CRC"):
        client.write_single_coil(slave_id=1, address=0, value=True)


def test_write_single_coil_exception_raises() -> None:
    response = append_crc(bytes([0x01, 0x85, 0x02]))  # exception FC05|0x80 = 0x85, code=2
    client = ModbusMasterClient(FakeTransport(response))

    with pytest.raises(RuntimeError, match="exception response: code 2"):
        client.write_single_coil(slave_id=1, address=0, value=True)


def test_write_single_coil_invalid_slave_id_raises() -> None:
    client = ModbusMasterClient(FakeTransport(b""))

    with pytest.raises(ValueError, match="slave_id"):
        client.write_single_coil(slave_id=0, address=0, value=True)


def test_write_single_coil_invalid_address_raises() -> None:
    client = ModbusMasterClient(FakeTransport(b""))

    with pytest.raises(ValueError, match="address"):
        client.write_single_coil(slave_id=1, address=65536, value=True)


# ── write_single_register (FC06) ──────────────────────────────────────────────


def test_write_single_register_builds_correct_request() -> None:
    response = append_crc(bytes([0x01, 0x06, 0x00, 0x01, 0x00, 0x03]))
    transport = FakeTransport(response)
    client = ModbusMasterClient(transport)

    result = client.write_single_register(slave_id=1, address=1, value=3)

    assert result == 3
    expected = append_crc(bytes([0x01, 0x06, 0x00, 0x01, 0x00, 0x03]))
    assert transport.requests[0] == expected


def test_write_single_register_echo_value_mismatch_raises() -> None:
    # Echo returns value=4, but we wrote value=3
    response = append_crc(bytes([0x01, 0x06, 0x00, 0x01, 0x00, 0x04]))
    client = ModbusMasterClient(FakeTransport(response))

    with pytest.raises(RuntimeError, match="mismatch"):
        client.write_single_register(slave_id=1, address=1, value=3)


def test_write_single_register_value_out_of_range_raises() -> None:
    client = ModbusMasterClient(FakeTransport(b""))

    with pytest.raises(ValueError, match="value"):
        client.write_single_register(slave_id=1, address=0, value=0x10000)


def test_write_single_register_exception_raises() -> None:
    response = append_crc(bytes([0x01, 0x86, 0x02]))
    client = ModbusMasterClient(FakeTransport(response))

    with pytest.raises(RuntimeError, match="exception response: code 2"):
        client.write_single_register(slave_id=1, address=0, value=1)


# ── write_multiple_coils (FC15) ───────────────────────────────────────────────


def test_write_multiple_coils_packs_bits_lsb_first() -> None:
    # [True, False, True] → bit0=1, bit1=0, bit2=1 → 0b00000101 = 0x05
    response = append_crc(bytes([0x01, 0x0F, 0x00, 0x00, 0x00, 0x03]))
    transport = FakeTransport(response)
    client = ModbusMasterClient(transport)

    result = client.write_multiple_coils(slave_id=1, address=0, values=[True, False, True])

    assert result == 3
    req = transport.requests[0]
    assert req[1] == 0x0F              # FC15
    assert req[6] == 1                 # byte_count = 1
    assert req[7] == 0x05              # bits LSB first: 101 → 0x05


def test_write_multiple_coils_8_bits_two_bytes_boundary() -> None:
    # 9 bits → byte_count = 2
    response = append_crc(bytes([0x01, 0x0F, 0x00, 0x00, 0x00, 0x09]))
    transport = FakeTransport(response)
    client = ModbusMasterClient(transport)

    client.write_multiple_coils(slave_id=1, address=0, values=[True] * 9)

    req = transport.requests[0]
    assert req[6] == 2   # ceil(9/8) = 2


def test_write_multiple_coils_echo_mismatch_raises() -> None:
    # Echo quantity=2, but we sent 3
    response = append_crc(bytes([0x01, 0x0F, 0x00, 0x00, 0x00, 0x02]))
    client = ModbusMasterClient(FakeTransport(response))

    with pytest.raises(RuntimeError, match="mismatch"):
        client.write_multiple_coils(slave_id=1, address=0, values=[True, False, True])


def test_write_multiple_coils_quantity_over_limit_raises() -> None:
    client = ModbusMasterClient(FakeTransport(b""))

    with pytest.raises(ValueError, match="quantity"):
        client.write_multiple_coils(slave_id=1, address=0, values=[True] * 1969)


# ── write_multiple_registers (FC16) ──────────────────────────────────────────


def test_write_multiple_registers_builds_correct_request() -> None:
    response = append_crc(bytes([0x01, 0x10, 0x00, 0x01, 0x00, 0x02]))
    transport = FakeTransport(response)
    client = ModbusMasterClient(transport)

    result = client.write_multiple_registers(slave_id=1, address=1, values=[0x000A, 0x0102])

    assert result == 2
    req = transport.requests[0]
    assert req[1] == 0x10              # FC16
    assert req[6] == 4                 # byte_count = 2 * 2
    assert req[7] == 0x00 and req[8] == 0x0A    # first value big-endian
    assert req[9] == 0x01 and req[10] == 0x02   # second value big-endian


def test_write_multiple_registers_echo_mismatch_raises() -> None:
    # Echo quantity=1, but we sent 2
    response = append_crc(bytes([0x01, 0x10, 0x00, 0x01, 0x00, 0x01]))
    client = ModbusMasterClient(FakeTransport(response))

    with pytest.raises(RuntimeError, match="mismatch"):
        client.write_multiple_registers(slave_id=1, address=1, values=[10, 20])


def test_write_multiple_registers_quantity_over_limit_raises() -> None:
    client = ModbusMasterClient(FakeTransport(b""))

    with pytest.raises(ValueError, match="quantity"):
        client.write_multiple_registers(slave_id=1, address=0, values=[0] * 124)


def test_write_multiple_registers_value_out_of_range_raises() -> None:
    client = ModbusMasterClient(FakeTransport(b""))

    with pytest.raises(ValueError, match="0..65535"):
        client.write_multiple_registers(slave_id=1, address=0, values=[0x10000])


def test_write_multiple_registers_exception_raises() -> None:
    response = append_crc(bytes([0x01, 0x90, 0x02]))
    client = ModbusMasterClient(FakeTransport(response))

    with pytest.raises(RuntimeError, match="exception response: code 2"):
        client.write_multiple_registers(slave_id=1, address=0, values=[1])


# ── common write validations ──────────────────────────────────────────────────


def test_slave_id_zero_rejected_for_write_single_coil() -> None:
    client = ModbusMasterClient(FakeTransport(b""))
    with pytest.raises(ValueError, match="slave_id"):
        client.write_single_coil(slave_id=0, address=0, value=True)


def test_slave_id_zero_rejected_for_write_single_register() -> None:
    client = ModbusMasterClient(FakeTransport(b""))
    with pytest.raises(ValueError, match="slave_id"):
        client.write_single_register(slave_id=0, address=0, value=1)


def test_slave_id_zero_rejected_for_write_multiple_coils() -> None:
    client = ModbusMasterClient(FakeTransport(b""))
    with pytest.raises(ValueError, match="slave_id"):
        client.write_multiple_coils(slave_id=0, address=0, values=[True])


def test_slave_id_zero_rejected_for_write_multiple_registers() -> None:
    client = ModbusMasterClient(FakeTransport(b""))
    with pytest.raises(ValueError, match="slave_id"):
        client.write_multiple_registers(slave_id=0, address=0, values=[1])
