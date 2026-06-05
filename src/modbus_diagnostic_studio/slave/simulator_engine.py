"""Modbus RTU slave simulator engine — pure in-memory, no serial I/O.

Response policies
-----------------
handle_request() returns:
- b""     — frame is too corrupt (CRC invalid) or not addressed to this slave.
             A real RS-485 slave would simply stay silent in both cases.
- bytes   — a complete RTU response frame (normal or exception), always with a
             valid CRC appended.

Exception codes used
--------------------
- 0x01  Illegal Function   — function code not supported (not FC03 or FC04).
- 0x02  Illegal Data Address — quantity out of 1..125, address+quantity > 65536,
                               or datastore read raises ValueError.
"""

from __future__ import annotations

from modbus_diagnostic_studio.core.crc import append_crc, verify_crc
from modbus_diagnostic_studio.core.rtu_frame import parse_read_request, parse_rtu_frame
from modbus_diagnostic_studio.slave.datastore import SlaveDatastore

_FC_HOLDING = 0x03
_FC_INPUT = 0x04
_SUPPORTED_FC = {_FC_HOLDING, _FC_INPUT}

_EX_ILLEGAL_FUNCTION = 0x01
_EX_ILLEGAL_DATA_ADDRESS = 0x02

_MAX_QUANTITY = 125
_MAX_ADDRESS_SPACE = 65536


# ── frame builder helpers ─────────────────────────────────────────────────────


def build_read_response(slave_id: int, function_code: int, registers: list[int]) -> bytes:
    """Build a valid FC03/FC04 read response frame with CRC appended."""
    byte_count = len(registers) * 2
    payload = bytes([slave_id, function_code, byte_count])
    for reg in registers:
        payload += bytes([(reg >> 8) & 0xFF, reg & 0xFF])
    return append_crc(payload)


def build_exception_response(slave_id: int, function_code: int, exception_code: int) -> bytes:
    """Build a valid Modbus exception response frame with CRC appended."""
    payload = bytes([slave_id, function_code | 0x80, exception_code])
    return append_crc(payload)


# ── simulator ─────────────────────────────────────────────────────────────────


class ModbusSlaveSimulator:
    """Pure in-memory Modbus RTU slave that handles FC03 and FC04 requests.

    Instantiate with a *slave_id* and an optional *datastore*.  Call
    ``handle_request`` with a raw RTU frame (bytes) to get the raw RTU
    response (bytes).

    No serial port or transport is involved.
    """

    def __init__(
        self,
        slave_id: int,
        datastore: SlaveDatastore | None = None,
    ) -> None:
        if not 1 <= slave_id <= 247:
            raise ValueError("slave_id must be in range 1..247")
        self.slave_id = slave_id
        self.datastore = datastore if datastore is not None else SlaveDatastore()

    def handle_request(self, frame: bytes) -> bytes:
        """Process one raw RTU request frame and return the response frame.

        Returns b"" when the frame has an invalid CRC or is addressed to a
        different slave (the simulator stays silent, matching RS-485 behaviour).
        """
        # ── 1. CRC guard ────────────────────────────────────────────────────
        if not verify_crc(frame):
            return b""

        # ── 2. Parse common RTU fields ──────────────────────────────────────
        try:
            rtu = parse_rtu_frame(frame)
        except ValueError:
            return b""

        # ── 3. Slave-ID filter ──────────────────────────────────────────────
        if rtu.slave_id != self.slave_id:
            return b""

        # ── 4. Function code check ──────────────────────────────────────────
        if rtu.function_code not in _SUPPORTED_FC:
            return build_exception_response(
                rtu.slave_id, rtu.function_code, _EX_ILLEGAL_FUNCTION
            )

        # ── 5. Parse as read request (validates 8-byte length) ───────────────
        try:
            req = parse_read_request(frame)
        except ValueError:
            return build_exception_response(
                rtu.slave_id, rtu.function_code, _EX_ILLEGAL_FUNCTION
            )

        # ── 6. Validate address / quantity ──────────────────────────────────
        if not 1 <= req.quantity <= _MAX_QUANTITY:
            return build_exception_response(
                req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS
            )
        if req.address + req.quantity > _MAX_ADDRESS_SPACE:
            return build_exception_response(
                req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS
            )

        # ── 7. Read from datastore ────────────────────────────────────────────
        try:
            if req.function_code == _FC_HOLDING:
                registers = self.datastore.read_holding_registers(req.address, req.quantity)
            else:
                registers = self.datastore.read_input_registers(req.address, req.quantity)
        except ValueError:
            return build_exception_response(
                req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS
            )

        return build_read_response(req.slave_id, req.function_code, registers)
