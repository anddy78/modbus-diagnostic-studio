"""Tests for minimal Modbus RTU frame parsing."""

import pytest

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.core.rtu_frame import (
    classify_frame,
    parse_bit_read_request,
    parse_exception_response,
    parse_read_request,
    parse_read_response,
    parse_rtu_frame,
    parse_write_multiple_coils_request,
    parse_write_multiple_registers_request,
    parse_write_single_coil_request,
    parse_write_single_register_request,
)


def test_parse_fc03_request_known_vector_a() -> None:
    frame = bytes.fromhex("01 03 00 00 00 0A C5 CD")

    request = parse_read_request(frame)

    assert request.slave_id == 1
    assert request.function_code == 3
    assert request.address == 0
    assert request.quantity == 10
    assert request.raw == frame


def test_parse_fc03_request_known_vector_b() -> None:
    frame = bytes.fromhex("11 03 00 6B 00 03 76 87")

    request = parse_read_request(frame)

    assert request.slave_id == 0x11
    assert request.function_code == 3
    assert request.address == 0x006B
    assert request.quantity == 3


def test_parse_fc04_request_created_with_crc() -> None:
    frame = append_crc(bytes.fromhex("01 04 00 10 00 02"))

    request = parse_read_request(frame)

    assert request.slave_id == 1
    assert request.function_code == 4
    assert request.address == 0x0010
    assert request.quantity == 2


def test_parse_fc03_response() -> None:
    frame = append_crc(bytes.fromhex("01 03 04 00 2A 00 64"))

    response = parse_read_response(frame)

    assert response.slave_id == 1
    assert response.function_code == 3
    assert response.byte_count == 4
    assert response.data == bytes.fromhex("00 2A 00 64")
    assert response.registers == [42, 100]


def test_parse_fc04_response() -> None:
    frame = append_crc(bytes.fromhex("01 04 04 00 2A 00 64"))

    response = parse_read_response(frame)

    assert response.function_code == 4
    assert response.registers == [42, 100]


def test_parse_exception_response() -> None:
    frame = append_crc(bytes.fromhex("01 83 02"))

    response = parse_exception_response(frame)

    assert response.slave_id == 1
    assert response.function_code == 0x83
    assert response.exception_code == 2


def test_parse_rejects_invalid_crc() -> None:
    frame = bytes.fromhex("01 03 00 00 00 0A C5 CC")

    with pytest.raises(ValueError, match="CRC"):
        parse_rtu_frame(frame)


def test_parse_rejects_incomplete_frame() -> None:
    with pytest.raises(ValueError):
        parse_rtu_frame(b"\x01\x03")


def test_parse_read_response_rejects_odd_byte_count() -> None:
    frame = append_crc(bytes.fromhex("01 03 03 00 2A 00"))

    with pytest.raises(ValueError, match="even"):
        parse_read_response(frame)


def test_classify_frame_main_cases() -> None:
    request = bytes.fromhex("01 03 00 00 00 0A C5 CD")
    response = append_crc(bytes.fromhex("01 03 04 00 2A 00 64"))
    exception = append_crc(bytes.fromhex("01 83 02"))
    # FC08 (Diagnostics) is genuinely unknown to this implementation
    unknown = append_crc(bytes([0x01, 0x08, 0x00, 0x01, 0x00, 0x00]))
    invalid_crc = bytes.fromhex("01 03 00 00 00 0A C5 CC")

    assert classify_frame(request) == "read_request"
    assert classify_frame(response) == "read_response"
    assert classify_frame(exception) == "exception_response"
    assert classify_frame(unknown) == "unknown"
    assert classify_frame(invalid_crc) == "invalid_crc"
    assert classify_frame(b"\x01\x03") == "incomplete"


# ── FC01/FC02 bit read ────────────────────────────────────────────────────────


def test_parse_fc01_read_coils() -> None:
    frame = append_crc(bytes([0x01, 0x01, 0x00, 0x13, 0x00, 0x25]))
    req = parse_bit_read_request(frame)
    assert req.slave_id == 1
    assert req.function_code == 0x01
    assert req.address == 0x0013
    assert req.quantity == 0x0025


def test_parse_fc02_read_discrete_inputs() -> None:
    frame = append_crc(bytes([0x05, 0x02, 0x00, 0x0A, 0x00, 0x0D]))
    req = parse_bit_read_request(frame)
    assert req.slave_id == 5
    assert req.function_code == 0x02
    assert req.address == 10
    assert req.quantity == 13


def test_parse_bit_read_wrong_fc_raises() -> None:
    frame = append_crc(bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01]))
    with pytest.raises(ValueError, match="FC01 or FC02"):
        parse_bit_read_request(frame)


def test_classify_fc01_as_bit_read_request() -> None:
    frame = append_crc(bytes([0x01, 0x01, 0x00, 0x00, 0x00, 0x08]))
    assert classify_frame(frame) == "bit_read_request"


def test_classify_fc02_as_bit_read_request() -> None:
    frame = append_crc(bytes([0x01, 0x02, 0x00, 0x00, 0x00, 0x08]))
    assert classify_frame(frame) == "bit_read_request"


# ── FC05 Write Single Coil ────────────────────────────────────────────────────


def test_parse_fc05_coil_on() -> None:
    frame = append_crc(bytes([0x01, 0x05, 0x00, 0xAC, 0xFF, 0x00]))
    req = parse_write_single_coil_request(frame)
    assert req.slave_id == 1
    assert req.function_code == 0x05
    assert req.address == 0x00AC
    assert req.value is True


def test_parse_fc05_coil_off() -> None:
    frame = append_crc(bytes([0x01, 0x05, 0x00, 0x05, 0x00, 0x00]))
    req = parse_write_single_coil_request(frame)
    assert req.value is False


def test_parse_fc05_invalid_value_raises() -> None:
    frame = append_crc(bytes([0x01, 0x05, 0x00, 0x00, 0x01, 0x00]))
    with pytest.raises(ValueError, match="0xFF00"):
        parse_write_single_coil_request(frame)


def test_classify_fc05_as_write_single_coil() -> None:
    frame = append_crc(bytes([0x01, 0x05, 0x00, 0xAC, 0xFF, 0x00]))
    assert classify_frame(frame) == "write_single_coil_request"


# ── FC06 Write Single Register ────────────────────────────────────────────────


def test_parse_fc06_write_single_register() -> None:
    frame = append_crc(bytes([0x01, 0x06, 0x00, 0x01, 0x00, 0x03]))
    req = parse_write_single_register_request(frame)
    assert req.slave_id == 1
    assert req.function_code == 0x06
    assert req.address == 1
    assert req.value == 3


def test_parse_fc06_max_value() -> None:
    frame = append_crc(bytes([0x02, 0x06, 0xFF, 0xFF, 0xFF, 0xFF]))
    req = parse_write_single_register_request(frame)
    assert req.address == 0xFFFF
    assert req.value == 0xFFFF


def test_classify_fc06_as_write_single_register() -> None:
    frame = append_crc(bytes([0x01, 0x06, 0x00, 0x01, 0x00, 0x03]))
    assert classify_frame(frame) == "write_single_register_request"


# ── FC15 Write Multiple Coils ─────────────────────────────────────────────────


def _make_fc15(slave_id: int, address: int, bits: list[bool]) -> bytes:
    quantity = len(bits)
    byte_count = (quantity + 7) // 8
    data = bytearray(byte_count)
    for i, b in enumerate(bits):
        if b:
            data[i // 8] |= 1 << (i % 8)
    payload = bytes([slave_id, 0x0F,
                     (address >> 8) & 0xFF, address & 0xFF,
                     (quantity >> 8) & 0xFF, quantity & 0xFF,
                     byte_count]) + bytes(data)
    return append_crc(payload)


def test_parse_fc15_8_coils() -> None:
    bits = [True, False, True, True, False, False, True, False]
    frame = _make_fc15(1, 20, bits)
    req = parse_write_multiple_coils_request(frame)
    assert req.slave_id == 1
    assert req.address == 20
    assert req.quantity == 8
    assert req.byte_count == 1
    assert req.values == bits


def test_parse_fc15_lsb_first_packing() -> None:
    # 0b00000011 → coil[0]=True, coil[1]=True, rest False
    payload = bytes([0x01, 0x0F, 0x00, 0x00, 0x00, 0x03, 0x01, 0b00000011])
    frame = append_crc(payload)
    req = parse_write_multiple_coils_request(frame)
    assert req.values == [True, True, False]


def test_parse_fc15_byte_count_mismatch_raises() -> None:
    # byte_count=2 but only 1 data byte
    payload = bytes([0x01, 0x0F, 0x00, 0x00, 0x00, 0x08, 0x02, 0xFF])
    frame = append_crc(payload)
    with pytest.raises(ValueError):
        parse_write_multiple_coils_request(frame)


def test_classify_fc15_as_write_multiple_coils() -> None:
    frame = _make_fc15(1, 0, [True, False, True, False, True, False, True, False])
    assert classify_frame(frame) == "write_multiple_coils_request"


# ── FC16 Write Multiple Registers ────────────────────────────────────────────


def _make_fc16(slave_id: int, address: int, values: list[int]) -> bytes:
    quantity = len(values)
    byte_count = quantity * 2
    data = b"".join(bytes([(v >> 8) & 0xFF, v & 0xFF]) for v in values)
    payload = bytes([slave_id, 0x10,
                     (address >> 8) & 0xFF, address & 0xFF,
                     (quantity >> 8) & 0xFF, quantity & 0xFF,
                     byte_count]) + data
    return append_crc(payload)


def test_parse_fc16_two_registers() -> None:
    frame = _make_fc16(1, 0, [0x1234, 0x5678])
    req = parse_write_multiple_registers_request(frame)
    assert req.slave_id == 1
    assert req.address == 0
    assert req.quantity == 2
    assert req.byte_count == 4
    assert req.values == [0x1234, 0x5678]


def test_parse_fc16_byte_count_mismatch_raises() -> None:
    # byte_count=3 but quantity=2 requires 4
    payload = bytes([0x01, 0x10, 0x00, 0x00, 0x00, 0x02, 0x03, 0x00, 0x01, 0x00])
    frame = append_crc(payload)
    with pytest.raises(ValueError, match="byte count"):
        parse_write_multiple_registers_request(frame)


def test_classify_fc16_as_write_multiple_registers() -> None:
    frame = _make_fc16(1, 10, [100, 200, 300])
    assert classify_frame(frame) == "write_multiple_registers_request"
