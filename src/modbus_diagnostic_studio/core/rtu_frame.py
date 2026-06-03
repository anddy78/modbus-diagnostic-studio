"""Modbus RTU frame parsing helpers for FC03 and FC04."""

from __future__ import annotations

from modbus_diagnostic_studio.core.crc import strip_crc, verify_crc
from modbus_diagnostic_studio.models.modbus import (
    ModbusExceptionResponse,
    ModbusReadRequest,
    ModbusReadResponse,
    ModbusRtuFrame,
)

READ_FUNCTION_CODES = {0x03, 0x04}


def _read_u16(high: int, low: int) -> int:
    return (high << 8) | low


def parse_rtu_frame(frame: bytes) -> ModbusRtuFrame:
    """Parse a CRC-validated RTU frame into its common fields."""
    raw_without_crc = strip_crc(frame)
    if len(raw_without_crc) < 2:
        raise ValueError("RTU frame must include slave id and function code")

    crc = frame[-2] | (frame[-1] << 8)
    return ModbusRtuFrame(
        slave_id=raw_without_crc[0],
        function_code=raw_without_crc[1],
        payload=raw_without_crc[2:],
        raw_without_crc=raw_without_crc,
        crc=crc,
        raw=frame,
    )


def parse_read_request(frame: bytes) -> ModbusReadRequest:
    """Parse a CRC-validated FC03/FC04 read request."""
    parsed = parse_rtu_frame(frame)
    if len(frame) != 8:
        raise ValueError("Read request RTU frame must be exactly 8 bytes")
    if parsed.function_code not in READ_FUNCTION_CODES:
        raise ValueError("Read request function code must be FC03 or FC04")

    return ModbusReadRequest(
        slave_id=parsed.slave_id,
        function_code=parsed.function_code,
        address=_read_u16(parsed.payload[0], parsed.payload[1]),
        quantity=_read_u16(parsed.payload[2], parsed.payload[3]),
        raw=frame,
    )


def parse_read_response(frame: bytes) -> ModbusReadResponse:
    """Parse a CRC-validated FC03/FC04 read response."""
    parsed = parse_rtu_frame(frame)
    if parsed.function_code not in READ_FUNCTION_CODES:
        raise ValueError("Read response function code must be FC03 or FC04")
    if len(parsed.payload) < 1:
        raise ValueError("Read response must include byte count")

    byte_count = parsed.payload[0]
    data = parsed.payload[1:]
    if byte_count != len(data):
        raise ValueError("Read response byte count does not match data length")
    if byte_count % 2 != 0:
        raise ValueError("Read response byte count must be even")

    registers = [
        _read_u16(data[index], data[index + 1])
        for index in range(0, len(data), 2)
    ]
    return ModbusReadResponse(
        slave_id=parsed.slave_id,
        function_code=parsed.function_code,
        byte_count=byte_count,
        data=data,
        registers=registers,
        raw=frame,
    )


def parse_exception_response(frame: bytes) -> ModbusExceptionResponse:
    """Parse a CRC-validated Modbus exception response."""
    parsed = parse_rtu_frame(frame)
    if not parsed.function_code & 0x80:
        raise ValueError("Exception response function code must have bit 0x80 set")
    if len(parsed.payload) != 1:
        raise ValueError("Exception response must contain one exception code")

    return ModbusExceptionResponse(
        slave_id=parsed.slave_id,
        function_code=parsed.function_code,
        exception_code=parsed.payload[0],
        raw=frame,
    )


def classify_frame(frame: bytes) -> str:
    """Classify an RTU frame without raising for CRC or length failures."""
    if len(frame) < 3:
        return "incomplete"
    if not verify_crc(frame):
        return "invalid_crc"

    try:
        parsed = parse_rtu_frame(frame)
    except ValueError:
        return "unknown"

    if parsed.function_code & 0x80:
        return "exception_response" if len(parsed.payload) == 1 else "unknown"
    if parsed.function_code not in READ_FUNCTION_CODES:
        return "unknown"
    if len(frame) == 8:
        return "read_request"
    if len(parsed.payload) >= 1 and parsed.payload[0] == len(parsed.payload[1:]):
        return "read_response"

    return "unknown"
