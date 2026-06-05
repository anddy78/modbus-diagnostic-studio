"""Passive RTU frame event parser.

Safety rule:
This module must never transmit.
"""

from __future__ import annotations

from modbus_diagnostic_studio.core.crc import verify_crc
from modbus_diagnostic_studio.core.decoder import bytes_to_hex
from modbus_diagnostic_studio.core.rtu_frame import (
    classify_frame,
    parse_exception_response,
    parse_read_request,
    parse_read_response,
)
from modbus_diagnostic_studio.models.capture import (
    CaptureFrameEvent,
    FrameDirectionGuess,
)


def frame_event_from_bytes(
    raw: bytes,
    timestamp_monotonic: float,
) -> CaptureFrameEvent:
    """Convert one received RTU frame to a passive capture event."""
    raw_hex = bytes_to_hex(raw)
    classification = classify_frame(raw)
    crc_ok = verify_crc(raw)

    try:
        if classification == "read_request":
            request = parse_read_request(raw)
            return CaptureFrameEvent(
                timestamp_monotonic=timestamp_monotonic,
                raw=raw,
                raw_hex=raw_hex,
                crc_ok=crc_ok,
                classification=classification,
                direction_guess=FrameDirectionGuess.REQUEST,
                slave_id=request.slave_id,
                function_code=request.function_code,
                address=request.address,
                quantity=request.quantity,
            )
        if classification == "read_response":
            response = parse_read_response(raw)
            return CaptureFrameEvent(
                timestamp_monotonic=timestamp_monotonic,
                raw=raw,
                raw_hex=raw_hex,
                crc_ok=crc_ok,
                classification=classification,
                direction_guess=FrameDirectionGuess.RESPONSE,
                slave_id=response.slave_id,
                function_code=response.function_code,
                byte_count=response.byte_count,
                registers=response.registers,
            )
        if classification == "exception_response":
            exception = parse_exception_response(raw)
            return CaptureFrameEvent(
                timestamp_monotonic=timestamp_monotonic,
                raw=raw,
                raw_hex=raw_hex,
                crc_ok=crc_ok,
                classification=classification,
                direction_guess=FrameDirectionGuess.EXCEPTION_RESPONSE,
                slave_id=exception.slave_id,
                function_code=exception.function_code,
                exception_code=exception.exception_code,
            )
    except ValueError as exc:
        return CaptureFrameEvent(
            timestamp_monotonic=timestamp_monotonic,
            raw=raw,
            raw_hex=raw_hex,
            crc_ok=crc_ok,
            classification=classification,
            direction_guess=FrameDirectionGuess.UNKNOWN,
            error=str(exc),
        )

    error = None
    if classification == "invalid_crc":
        error = "Invalid Modbus RTU CRC"
    elif classification == "incomplete":
        error = "Incomplete Modbus RTU frame"
    elif classification == "unknown":
        error = "Unknown Modbus RTU frame"

    return CaptureFrameEvent(
        timestamp_monotonic=timestamp_monotonic,
        raw=raw,
        raw_hex=raw_hex,
        crc_ok=crc_ok,
        classification=classification,
        direction_guess=FrameDirectionGuess.UNKNOWN,
        error=error,
    )
