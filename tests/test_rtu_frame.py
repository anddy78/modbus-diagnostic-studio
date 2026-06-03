"""Tests for minimal Modbus RTU frame parsing."""

import pytest

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.core.rtu_frame import (
    classify_frame,
    parse_exception_response,
    parse_read_request,
    parse_read_response,
    parse_rtu_frame,
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
    unknown = append_crc(bytes.fromhex("01 06 00 01 00 02"))
    invalid_crc = bytes.fromhex("01 03 00 00 00 0A C5 CC")

    assert classify_frame(request) == "read_request"
    assert classify_frame(response) == "read_response"
    assert classify_frame(exception) == "exception_response"
    assert classify_frame(unknown) == "unknown"
    assert classify_frame(invalid_crc) == "invalid_crc"
    assert classify_frame(b"\x01\x03") == "incomplete"
