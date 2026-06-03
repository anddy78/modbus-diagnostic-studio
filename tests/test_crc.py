"""Tests for Modbus RTU CRC helpers."""

import pytest

from modbus_diagnostic_studio.core.crc import (
    append_crc,
    compute_crc,
    crc_to_bytes,
    strip_crc,
    verify_crc,
)


def test_compute_crc_known_request_vector_a() -> None:
    payload = bytes.fromhex("01 03 00 00 00 0A")

    assert compute_crc(payload) == 0xCDC5
    assert crc_to_bytes(compute_crc(payload)) == bytes.fromhex("C5 CD")
    assert append_crc(payload) == bytes.fromhex("01 03 00 00 00 0A C5 CD")


def test_compute_crc_known_request_vector_b() -> None:
    payload = bytes.fromhex("11 03 00 6B 00 03")

    assert compute_crc(payload) == 0x8776
    assert crc_to_bytes(compute_crc(payload)) == bytes.fromhex("76 87")
    assert append_crc(payload) == bytes.fromhex("11 03 00 6B 00 03 76 87")


def test_verify_crc_accepts_valid_frame() -> None:
    frame = bytes.fromhex("01 03 00 00 00 0A C5 CD")

    assert verify_crc(frame) is True


def test_verify_crc_rejects_altered_last_byte() -> None:
    frame = bytes.fromhex("01 03 00 00 00 0A C5 CC")

    assert verify_crc(frame) is False


def test_verify_crc_rejects_too_short_frames() -> None:
    assert verify_crc(b"") is False
    assert verify_crc(b"\x01\x03") is False


def test_strip_crc_returns_payload_for_valid_frame() -> None:
    frame = bytes.fromhex("11 03 00 6B 00 03 76 87")

    assert strip_crc(frame) == bytes.fromhex("11 03 00 6B 00 03")


@pytest.mark.parametrize(
    "frame",
    [
        b"",
        b"\x01\x03",
        bytes.fromhex("01 03 00 00 00 0A C5 CC"),
    ],
)
def test_strip_crc_raises_for_invalid_frame(frame: bytes) -> None:
    with pytest.raises(ValueError):
        strip_crc(frame)
