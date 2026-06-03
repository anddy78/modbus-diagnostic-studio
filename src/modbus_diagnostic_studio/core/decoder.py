"""Raw Modbus RTU frame decoding helpers."""

from __future__ import annotations

from modbus_diagnostic_studio.core.crc import verify_crc
from modbus_diagnostic_studio.core.rtu_frame import (
    classify_frame,
    parse_exception_response,
    parse_read_request,
    parse_read_response,
)


def hex_to_bytes(text: str) -> bytes:
    """Convert hex text with spaces, hyphens, or no separators to bytes."""
    normalized = "".join(text.replace("-", " ").split())
    if len(normalized) % 2 != 0:
        raise ValueError("Hex text must contain an even number of digits")

    try:
        return bytes.fromhex(normalized)
    except ValueError as exc:
        raise ValueError("Hex text contains invalid characters") from exc


def bytes_to_hex(data: bytes) -> str:
    """Return uppercase hex bytes separated by spaces."""
    return data.hex(" ").upper()


def decode_raw_rtu_frame(text: str) -> dict:
    """Decode raw hex text into a small, UI-friendly dictionary."""
    try:
        frame = hex_to_bytes(text)
    except ValueError as exc:
        return {
            "error": str(exc),
            "crc_ok": False,
            "classification": "invalid_hex",
            "raw_hex": "",
        }

    classification = classify_frame(frame)
    result = {
        "classification": classification,
        "crc_ok": verify_crc(frame),
        "raw_hex": bytes_to_hex(frame),
    }

    try:
        if classification == "read_request":
            request = parse_read_request(frame)
            result.update(
                {
                    "slave_id": request.slave_id,
                    "function_code": request.function_code,
                    "address": request.address,
                    "quantity": request.quantity,
                }
            )
        elif classification == "read_response":
            response = parse_read_response(frame)
            result.update(
                {
                    "slave_id": response.slave_id,
                    "function_code": response.function_code,
                    "byte_count": response.byte_count,
                    "registers": response.registers,
                }
            )
        elif classification == "exception_response":
            exception = parse_exception_response(frame)
            result.update(
                {
                    "slave_id": exception.slave_id,
                    "function_code": exception.function_code,
                    "exception_code": exception.exception_code,
                }
            )
    except ValueError as exc:
        result["error"] = str(exc)

    return result
