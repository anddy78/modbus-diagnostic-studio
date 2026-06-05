"""Modbus RTU frame parsing helpers for FC01-FC06, FC15 and FC16."""

from __future__ import annotations

from modbus_diagnostic_studio.core.crc import strip_crc, verify_crc
from modbus_diagnostic_studio.models.modbus import (
    ModbusBitReadRequest,
    ModbusExceptionResponse,
    ModbusReadRequest,
    ModbusReadResponse,
    ModbusRtuFrame,
    ModbusWriteMultipleCoilsRequest,
    ModbusWriteMultipleRegistersRequest,
    ModbusWriteSingleCoilRequest,
    ModbusWriteSingleRegisterRequest,
)

READ_FUNCTION_CODES = {0x03, 0x04}
BIT_READ_FUNCTION_CODES = {0x01, 0x02}

# Coil value constants per Modbus specification
_COIL_ON = 0xFF00
_COIL_OFF = 0x0000


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


# ── Read request parsers ──────────────────────────────────────────────────────


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


def parse_bit_read_request(frame: bytes) -> ModbusBitReadRequest:
    """Parse a CRC-validated FC01/FC02 bit read request."""
    parsed = parse_rtu_frame(frame)
    if len(frame) != 8:
        raise ValueError("Bit read request RTU frame must be exactly 8 bytes")
    if parsed.function_code not in BIT_READ_FUNCTION_CODES:
        raise ValueError("Bit read request function code must be FC01 or FC02")

    return ModbusBitReadRequest(
        slave_id=parsed.slave_id,
        function_code=parsed.function_code,
        address=_read_u16(parsed.payload[0], parsed.payload[1]),
        quantity=_read_u16(parsed.payload[2], parsed.payload[3]),
        raw=frame,
    )


# ── Write request parsers ─────────────────────────────────────────────────────


def parse_write_single_coil_request(frame: bytes) -> ModbusWriteSingleCoilRequest:
    """Parse a CRC-validated FC05 Write Single Coil request.

    Valid coil values per Modbus specification: 0xFF00 (ON) and 0x0000 (OFF).
    Any other value raises ValueError.
    """
    parsed = parse_rtu_frame(frame)
    if len(frame) != 8:
        raise ValueError("FC05 Write Single Coil frame must be exactly 8 bytes")
    if parsed.function_code != 0x05:
        raise ValueError("FC05 expected, got function code 0x{:02X}".format(parsed.function_code))

    address = _read_u16(parsed.payload[0], parsed.payload[1])
    coil_raw = _read_u16(parsed.payload[2], parsed.payload[3])

    if coil_raw == _COIL_ON:
        value = True
    elif coil_raw == _COIL_OFF:
        value = False
    else:
        raise ValueError(
            f"Invalid FC05 coil value 0x{coil_raw:04X}; "
            "must be 0xFF00 (ON) or 0x0000 (OFF)"
        )

    return ModbusWriteSingleCoilRequest(
        slave_id=parsed.slave_id,
        function_code=parsed.function_code,
        address=address,
        value=value,
        raw=frame,
    )


def parse_write_single_register_request(frame: bytes) -> ModbusWriteSingleRegisterRequest:
    """Parse a CRC-validated FC06 Write Single Register request."""
    parsed = parse_rtu_frame(frame)
    if len(frame) != 8:
        raise ValueError("FC06 Write Single Register frame must be exactly 8 bytes")
    if parsed.function_code != 0x06:
        raise ValueError("FC06 expected, got function code 0x{:02X}".format(parsed.function_code))

    return ModbusWriteSingleRegisterRequest(
        slave_id=parsed.slave_id,
        function_code=parsed.function_code,
        address=_read_u16(parsed.payload[0], parsed.payload[1]),
        value=_read_u16(parsed.payload[2], parsed.payload[3]),
        raw=frame,
    )


def parse_write_multiple_coils_request(frame: bytes) -> ModbusWriteMultipleCoilsRequest:
    """Parse a CRC-validated FC15 (0x0F) Write Multiple Coils request.

    Bits are unpacked LSB-first from each data byte.
    Raises ValueError when byte_count does not match quantity.
    """
    parsed = parse_rtu_frame(frame)
    if parsed.function_code != 0x0F:
        raise ValueError(
            "FC15 (0x0F) expected, got function code 0x{:02X}".format(parsed.function_code)
        )
    if len(parsed.payload) < 5:
        raise ValueError("FC15 frame payload too short (minimum 5 bytes)")

    address = _read_u16(parsed.payload[0], parsed.payload[1])
    quantity = _read_u16(parsed.payload[2], parsed.payload[3])
    byte_count = parsed.payload[4]
    data = parsed.payload[5:]

    if len(data) != byte_count:
        raise ValueError(
            f"FC15 byte count {byte_count} does not match data length {len(data)}"
        )
    expected_byte_count = (quantity + 7) // 8
    if byte_count != expected_byte_count:
        raise ValueError(
            f"FC15 byte count {byte_count} invalid for quantity {quantity} "
            f"(expected {expected_byte_count})"
        )

    values = [bool(data[i // 8] & (1 << (i % 8))) for i in range(quantity)]

    return ModbusWriteMultipleCoilsRequest(
        slave_id=parsed.slave_id,
        function_code=parsed.function_code,
        address=address,
        quantity=quantity,
        byte_count=byte_count,
        values=values,
        raw=frame,
    )


def parse_write_multiple_registers_request(frame: bytes) -> ModbusWriteMultipleRegistersRequest:
    """Parse a CRC-validated FC16 (0x10) Write Multiple Registers request.

    Register values are big-endian uint16.
    Raises ValueError when byte_count does not equal quantity * 2.
    """
    parsed = parse_rtu_frame(frame)
    if parsed.function_code != 0x10:
        raise ValueError(
            "FC16 (0x10) expected, got function code 0x{:02X}".format(parsed.function_code)
        )
    if len(parsed.payload) < 5:
        raise ValueError("FC16 frame payload too short (minimum 5 bytes)")

    address = _read_u16(parsed.payload[0], parsed.payload[1])
    quantity = _read_u16(parsed.payload[2], parsed.payload[3])
    byte_count = parsed.payload[4]
    data = parsed.payload[5:]

    if len(data) != byte_count:
        raise ValueError(
            f"FC16 byte count {byte_count} does not match data length {len(data)}"
        )
    if byte_count != quantity * 2:
        raise ValueError(
            f"FC16 byte count {byte_count} must equal quantity*2={quantity * 2}"
        )

    values = [_read_u16(data[i * 2], data[i * 2 + 1]) for i in range(quantity)]

    return ModbusWriteMultipleRegistersRequest(
        slave_id=parsed.slave_id,
        function_code=parsed.function_code,
        address=address,
        quantity=quantity,
        byte_count=byte_count,
        values=values,
        raw=frame,
    )


# ── Response parsers ──────────────────────────────────────────────────────────


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


# ── Frame classifier ──────────────────────────────────────────────────────────


def classify_frame(frame: bytes) -> str:
    """Classify an RTU frame without raising for CRC or length failures.

    Return values
    -------------
    read_request                  — FC03/FC04 8-byte request
    read_response                 — FC03/FC04 variable-length response
    bit_read_request              — FC01/FC02 8-byte request
    write_single_coil_request     — FC05 8-byte request
    write_single_register_request — FC06 8-byte request
    write_multiple_coils_request  — FC15 variable-length request
    write_multiple_registers_request — FC16 variable-length request
    exception_response            — any exception (fc|0x80) response
    invalid_crc                   — CRC check failed
    incomplete                    — frame too short to classify
    unknown                       — valid CRC but unrecognised structure
    """
    if len(frame) < 3:
        return "incomplete"
    if not verify_crc(frame):
        return "invalid_crc"

    try:
        parsed = parse_rtu_frame(frame)
    except ValueError:
        return "unknown"

    fc = parsed.function_code

    # Exception responses (any FC with high bit set)
    if fc & 0x80:
        return "exception_response" if len(parsed.payload) == 1 else "unknown"

    # FC03/FC04 register read
    if fc in READ_FUNCTION_CODES:
        if len(frame) == 8:
            return "read_request"
        if len(parsed.payload) >= 1 and parsed.payload[0] == len(parsed.payload[1:]):
            return "read_response"
        return "unknown"

    # FC01/FC02 bit read
    if fc in BIT_READ_FUNCTION_CODES:
        return "bit_read_request" if len(frame) == 8 else "unknown"

    # FC05 Write Single Coil (fixed 8 bytes)
    if fc == 0x05:
        return "write_single_coil_request" if len(frame) == 8 else "unknown"

    # FC06 Write Single Register (fixed 8 bytes)
    if fc == 0x06:
        return "write_single_register_request" if len(frame) == 8 else "unknown"

    # FC15 Write Multiple Coils (variable: 7 header + byte_count data + 2 CRC)
    if fc == 0x0F:
        if len(parsed.payload) >= 5:
            bc = parsed.payload[4]
            if len(parsed.payload) == 5 + bc:
                return "write_multiple_coils_request"
        return "unknown"

    # FC16 Write Multiple Registers (variable: 7 header + byte_count data + 2 CRC)
    if fc == 0x10:
        if len(parsed.payload) >= 5:
            bc = parsed.payload[4]
            if len(parsed.payload) == 5 + bc:
                return "write_multiple_registers_request"
        return "unknown"

    return "unknown"
