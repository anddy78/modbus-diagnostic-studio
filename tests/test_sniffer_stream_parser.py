"""Tests for passive sniffer frame event parsing."""

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.models.capture import FrameDirectionGuess
from modbus_diagnostic_studio.sniffer.stream_parser import frame_event_from_bytes


def test_event_from_valid_fc03_request() -> None:
    event = frame_event_from_bytes(bytes.fromhex("01 03 00 00 00 0A C5 CD"), 1.0)

    assert event.classification == "read_request"
    assert event.direction_guess is FrameDirectionGuess.REQUEST
    assert event.crc_ok is True
    assert event.slave_id == 1
    assert event.function_code == 3
    assert event.address == 0
    assert event.quantity == 10


def test_event_from_valid_fc03_response() -> None:
    frame = append_crc(bytes.fromhex("01 03 04 00 2A 00 64"))

    event = frame_event_from_bytes(frame, 2.0)

    assert event.classification == "read_response"
    assert event.direction_guess is FrameDirectionGuess.RESPONSE
    assert event.byte_count == 4
    assert event.registers == [42, 100]


def test_event_from_exception_response() -> None:
    frame = append_crc(bytes.fromhex("01 83 02"))

    event = frame_event_from_bytes(frame, 3.0)

    assert event.classification == "exception_response"
    assert event.direction_guess is FrameDirectionGuess.EXCEPTION_RESPONSE
    assert event.function_code == 0x83
    assert event.exception_code == 2


def test_event_from_invalid_crc() -> None:
    event = frame_event_from_bytes(bytes.fromhex("01 03 00 00 00 0A C5 CC"), 4.0)

    assert event.classification == "invalid_crc"
    assert event.crc_ok is False
    assert event.direction_guess is FrameDirectionGuess.UNKNOWN
    assert event.error is not None


def test_event_from_incomplete_frame() -> None:
    event = frame_event_from_bytes(b"\x01\x03", 5.0)

    assert event.classification == "incomplete"
    assert event.crc_ok is False
    assert event.error is not None


def test_event_from_garbage_does_not_raise() -> None:
    event = frame_event_from_bytes(b"\x99\x88\x77\x66\x55", 6.0)

    assert event.classification in {"invalid_crc", "unknown"}
    assert event.raw_hex == "99 88 77 66 55"
