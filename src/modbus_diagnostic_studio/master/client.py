"""Active Modbus master client."""

from __future__ import annotations

from typing import Protocol

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.core.rtu_frame import (
    classify_frame,
    parse_exception_response,
    parse_read_response,
)


class RtuTransportLike(Protocol):
    """Transport protocol used by the master client."""

    def transact(self, request: bytes, expected_min_response_size: int = 5) -> bytes:
        """Send request and return response frame."""


class ModbusMasterClient:
    """Minimal active Modbus master for FC03 and FC04."""

    def __init__(self, transport: RtuTransportLike) -> None:
        self.transport = transport

    def read_holding_registers(
        self,
        slave_id: int,
        address: int,
        quantity: int,
    ) -> list[int]:
        """Read holding registers using FC03."""
        return self._read_registers(slave_id, 0x03, address, quantity)

    def read_input_registers(
        self,
        slave_id: int,
        address: int,
        quantity: int,
    ) -> list[int]:
        """Read input registers using FC04."""
        return self._read_registers(slave_id, 0x04, address, quantity)

    def _read_registers(
        self,
        slave_id: int,
        function_code: int,
        address: int,
        quantity: int,
    ) -> list[int]:
        self._validate_read_arguments(slave_id, address, quantity)
        payload = bytes(
            (
                slave_id,
                function_code,
                (address >> 8) & 0xFF,
                address & 0xFF,
                (quantity >> 8) & 0xFF,
                quantity & 0xFF,
            )
        )
        request = append_crc(payload)

        try:
            response = self.transport.transact(request, expected_min_response_size=5)
        except Exception as exc:
            raise RuntimeError(f"Modbus transaction failed: {exc}") from exc

        classification = classify_frame(response)
        if classification == "invalid_crc":
            raise RuntimeError("Modbus response has invalid CRC")
        if classification == "exception_response":
            exception = parse_exception_response(response)
            raise RuntimeError(
                f"Modbus exception response: code {exception.exception_code}"
            )
        if classification != "read_response":
            raise RuntimeError(f"Unexpected Modbus response frame: {classification}")

        try:
            parsed = parse_read_response(response)
        except ValueError as exc:
            raise RuntimeError(f"Invalid Modbus read response: {exc}") from exc

        if parsed.slave_id != slave_id:
            raise RuntimeError("Modbus response slave id does not match request")
        if parsed.function_code != function_code:
            raise RuntimeError("Modbus response function code does not match request")

        return parsed.registers

    @staticmethod
    def _validate_read_arguments(slave_id: int, address: int, quantity: int) -> None:
        if not 1 <= slave_id <= 247:
            raise ValueError("slave_id must be in range 1..247")
        if not 0 <= address <= 0xFFFF:
            raise ValueError("address must be in range 0..65535")
        if not 1 <= quantity <= 125:
            raise ValueError("quantity must be in range 1..125")
