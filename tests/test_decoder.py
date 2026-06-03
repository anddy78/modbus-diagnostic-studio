"""Tests for raw Modbus RTU decoder helpers."""

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.core.decoder import (
    bytes_to_hex,
    decode_raw_rtu_frame,
    hex_to_bytes,
)


def test_hex_to_bytes_with_spaces() -> None:
    assert hex_to_bytes("01 03 00 00 00 0A C5 CD") == bytes.fromhex(
        "01 03 00 00 00 0A C5 CD"
    )


def test_hex_to_bytes_without_spaces() -> None:
    assert hex_to_bytes("01030000000AC5CD") == bytes.fromhex("01 03 00 00 00 0A C5 CD")


def test_hex_to_bytes_with_hyphens() -> None:
    assert hex_to_bytes("01-03-00-00-00-0A-C5-CD") == bytes.fromhex(
        "01 03 00 00 00 0A C5 CD"
    )


def test_bytes_to_hex() -> None:
    assert bytes_to_hex(bytes.fromhex("01 03 00 00")) == "01 03 00 00"


def test_decode_raw_rtu_frame_valid_request() -> None:
    decoded = decode_raw_rtu_frame("01 03 00 00 00 0A C5 CD")

    assert decoded["classification"] == "read_request"
    assert decoded["crc_ok"] is True
    assert decoded["slave_id"] == 1
    assert decoded["function_code"] == 3
    assert decoded["address"] == 0
    assert decoded["quantity"] == 10
    assert decoded["raw_hex"] == "01 03 00 00 00 0A C5 CD"


def test_decode_raw_rtu_frame_valid_response() -> None:
    frame = append_crc(bytes.fromhex("01 03 04 00 2A 00 64"))

    decoded = decode_raw_rtu_frame(bytes_to_hex(frame))

    assert decoded["classification"] == "read_response"
    assert decoded["crc_ok"] is True
    assert decoded["byte_count"] == 4
    assert decoded["registers"] == [42, 100]


def test_decode_raw_rtu_frame_valid_exception() -> None:
    frame = append_crc(bytes.fromhex("01 83 02"))

    decoded = decode_raw_rtu_frame(bytes_to_hex(frame))

    assert decoded["classification"] == "exception_response"
    assert decoded["crc_ok"] is True
    assert decoded["slave_id"] == 1
    assert decoded["function_code"] == 0x83
    assert decoded["exception_code"] == 2


def test_decode_raw_rtu_frame_invalid_crc() -> None:
    decoded = decode_raw_rtu_frame("01 03 00 00 00 0A C5 CC")

    assert decoded["classification"] == "invalid_crc"
    assert decoded["crc_ok"] is False
    assert decoded["raw_hex"] == "01 03 00 00 00 0A C5 CC"


def test_decode_raw_rtu_frame_invalid_hex() -> None:
    decoded = decode_raw_rtu_frame("01 03 ZZ")

    assert decoded["classification"] == "invalid_hex"
    assert decoded["crc_ok"] is False
    assert "error" in decoded
