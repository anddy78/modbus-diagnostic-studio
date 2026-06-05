"""Active Modbus master client — FC03, FC04, FC05, FC06, FC15, FC16."""

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
    """Active Modbus master for FC03, FC04 reads and FC05/FC06/FC15/FC16 writes.

    Write operations
    ----------------
    Writes are one-shot only.  No automatic retry.  No broadcast (slave_id 0).

    The caller is responsible for ensuring that writes are authorised on the
    target equipment before calling any write method.
    """

    def __init__(self, transport: RtuTransportLike) -> None:
        self.transport = transport

    # ── read operations ────────────────────────────────────────────────────

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

    # ── write operations ───────────────────────────────────────────────────

    def write_single_coil(self, slave_id: int, address: int, value: bool) -> bool:
        """Write a single coil using FC05.  Returns the confirmed coil value.

        value=True  → 0xFF00 (coil ON)
        value=False → 0x0000 (coil OFF)
        """
        self._validate_slave_and_address(slave_id, address)
        coil_raw = 0xFF00 if value else 0x0000
        payload = bytes([
            slave_id, 0x05,
            (address >> 8) & 0xFF, address & 0xFF,
            (coil_raw >> 8) & 0xFF, coil_raw & 0xFF,
        ])
        response = self._transact_write(append_crc(payload))
        echo_addr = (response[2] << 8) | response[3]
        echo_val = (response[4] << 8) | response[5]
        if echo_addr != address:
            raise RuntimeError(
                f"Write single coil echo address mismatch: got {echo_addr}, expected {address}"
            )
        if echo_val not in (0xFF00, 0x0000):
            raise RuntimeError(f"Write single coil echo value invalid: 0x{echo_val:04X}")
        if echo_val != coil_raw:
            raise RuntimeError(
                f"Write single coil echo value mismatch: got 0x{echo_val:04X}, "
                f"expected 0x{coil_raw:04X}"
            )
        return echo_val == 0xFF00

    def write_single_register(self, slave_id: int, address: int, value: int) -> int:
        """Write a single holding register using FC06.  Returns confirmed value."""
        self._validate_slave_and_address(slave_id, address)
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"value must be in range 0..65535, got {value}")
        payload = bytes([
            slave_id, 0x06,
            (address >> 8) & 0xFF, address & 0xFF,
            (value >> 8) & 0xFF, value & 0xFF,
        ])
        response = self._transact_write(append_crc(payload))
        echo_addr = (response[2] << 8) | response[3]
        echo_val = (response[4] << 8) | response[5]
        if echo_addr != address:
            raise RuntimeError(
                f"Write single register echo address mismatch: got {echo_addr}, expected {address}"
            )
        if echo_val != value:
            raise RuntimeError(
                f"Write single register echo value mismatch: got {echo_val}, expected {value}"
            )
        return echo_val

    def write_multiple_coils(
        self,
        slave_id: int,
        address: int,
        values: list[bool],
    ) -> int:
        """Write multiple coils using FC15.  Returns confirmed quantity.

        Bits are packed LSB-first per byte per Modbus specification.
        quantity must be 1..1968.
        """
        self._validate_slave_and_address(slave_id, address)
        for i, v in enumerate(values):
            if not isinstance(v, bool):
                raise ValueError(
                    f"values[{i}] must be bool, got {type(v).__name__} {v!r}"
                )
        quantity = len(values)
        if not 1 <= quantity <= 1968:
            raise ValueError(f"quantity must be in range 1..1968, got {quantity}")
        if address + quantity > 65536:
            raise ValueError("address + quantity exceeds 65536")

        byte_count = (quantity + 7) // 8
        data = bytearray(byte_count)
        for i, bit in enumerate(values):
            if bit:
                data[i // 8] |= 1 << (i % 8)

        payload = bytes([
            slave_id, 0x0F,
            (address >> 8) & 0xFF, address & 0xFF,
            (quantity >> 8) & 0xFF, quantity & 0xFF,
            byte_count,
        ]) + bytes(data)
        response = self._transact_write(append_crc(payload))
        echo_addr = (response[2] << 8) | response[3]
        echo_qty = (response[4] << 8) | response[5]
        if echo_addr != address:
            raise RuntimeError(
                f"Write multiple coils echo address mismatch: got {echo_addr}, expected {address}"
            )
        if echo_qty != quantity:
            raise RuntimeError(
                f"Write multiple coils echo quantity mismatch: got {echo_qty}, expected {quantity}"
            )
        return echo_qty

    def write_multiple_registers(
        self,
        slave_id: int,
        address: int,
        values: list[int],
    ) -> int:
        """Write multiple holding registers using FC16.  Returns confirmed quantity.

        quantity must be 1..123.
        All values must be in range 0..65535.
        """
        self._validate_slave_and_address(slave_id, address)
        quantity = len(values)
        if not 1 <= quantity <= 123:
            raise ValueError(f"quantity must be in range 1..123, got {quantity}")
        if address + quantity > 65536:
            raise ValueError("address + quantity exceeds 65536")
        for i, v in enumerate(values):
            if not 0 <= v <= 0xFFFF:
                raise ValueError(f"values[{i}] = {v} must be in range 0..65535")

        byte_count = quantity * 2
        data = b"".join(bytes([(v >> 8) & 0xFF, v & 0xFF]) for v in values)
        payload = bytes([
            slave_id, 0x10,
            (address >> 8) & 0xFF, address & 0xFF,
            (quantity >> 8) & 0xFF, quantity & 0xFF,
            byte_count,
        ]) + data
        response = self._transact_write(append_crc(payload))
        echo_addr = (response[2] << 8) | response[3]
        echo_qty = (response[4] << 8) | response[5]
        if echo_addr != address:
            raise RuntimeError(
                f"Write multiple registers echo address mismatch: got {echo_addr}, expected {address}"
            )
        if echo_qty != quantity:
            raise RuntimeError(
                f"Write multiple registers echo quantity mismatch: got {echo_qty}, expected {quantity}"
            )
        return echo_qty

    # ── private helpers ────────────────────────────────────────────────────

    def _transact_write(self, request: bytes) -> bytes:
        """Send a write request and validate the 8-byte echo response."""
        try:
            response = self.transport.transact(request, expected_min_response_size=8)
        except Exception as exc:
            raise RuntimeError(f"Modbus write transaction failed: {exc}") from exc

        classification = classify_frame(response)
        if classification == "invalid_crc":
            raise RuntimeError("Modbus write response has invalid CRC")
        if classification == "exception_response":
            exception = parse_exception_response(response)
            raise RuntimeError(
                f"Modbus exception response: code {exception.exception_code}"
            )
        if len(response) < 8:
            raise RuntimeError(
                f"Modbus write response too short: {len(response)} bytes (expected 8)"
            )
        if response[0] != request[0]:
            raise RuntimeError("Modbus write response slave id mismatch")
        if response[1] != request[1]:
            raise RuntimeError("Modbus write response function code mismatch")
        return response

    @staticmethod
    def _validate_slave_and_address(slave_id: int, address: int) -> None:
        if not 1 <= slave_id <= 247:
            raise ValueError(f"slave_id must be in range 1..247, got {slave_id}")
        if not 0 <= address <= 0xFFFF:
            raise ValueError(f"address must be in range 0..65535, got {address}")

    @staticmethod
    def _validate_read_arguments(slave_id: int, address: int, quantity: int) -> None:
        if not 1 <= slave_id <= 247:
            raise ValueError("slave_id must be in range 1..247")
        if not 0 <= address <= 0xFFFF:
            raise ValueError("address must be in range 0..65535")
        if not 1 <= quantity <= 125:
            raise ValueError("quantity must be in range 1..125")
