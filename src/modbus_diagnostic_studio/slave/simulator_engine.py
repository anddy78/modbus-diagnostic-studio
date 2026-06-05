"""Modbus RTU slave simulator engine — pure in-memory, no serial I/O.

Response policies
-----------------
handle_request() returns:
- b""     — silent discard: CRC invalid, frame too short, or addressed to a
             different slave.  A real RS-485 bus slave stays silent in these
             cases.
- b""     — broadcast (slave_id 0): not supported in v1.  Documented here so
             future implementations can add it explicitly.
- bytes   — a complete RTU response frame (normal or exception), always with a
             valid CRC appended.

Exception codes
---------------
0x01  Illegal Function       — function code not recognised by this slave.
0x02  Illegal Data Address   — address or address+quantity out of range.
0x03  Illegal Data Value     — value in request data field is not allowed
                               (FC05 coil value, FC15/FC16 byte count mismatch).

Supported function codes
------------------------
FC01  Read Coils
FC02  Read Discrete Inputs
FC03  Read Holding Registers
FC04  Read Input Registers
FC05  Write Single Coil
FC06  Write Single Register
FC15  Write Multiple Coils   (0x0F)
FC16  Write Multiple Registers (0x10)
"""

from __future__ import annotations

from modbus_diagnostic_studio.core.crc import append_crc, verify_crc
from modbus_diagnostic_studio.core.rtu_frame import (
    parse_bit_read_request,
    parse_read_request,
    parse_rtu_frame,
    parse_write_multiple_coils_request,
    parse_write_multiple_registers_request,
    parse_write_single_coil_request,
    parse_write_single_register_request,
)
from modbus_diagnostic_studio.slave.datastore import SlaveDatastore

# ── constants ─────────────────────────────────────────────────────────────────

_FC_COILS = 0x01
_FC_DISCRETE = 0x02
_FC_HOLDING = 0x03
_FC_INPUT = 0x04
_FC_WRITE_COIL = 0x05
_FC_WRITE_REGISTER = 0x06
_FC_WRITE_MULTIPLE_COILS = 0x0F
_FC_WRITE_MULTIPLE_REGISTERS = 0x10

_SUPPORTED_FC = {
    _FC_COILS,
    _FC_DISCRETE,
    _FC_HOLDING,
    _FC_INPUT,
    _FC_WRITE_COIL,
    _FC_WRITE_REGISTER,
    _FC_WRITE_MULTIPLE_COILS,
    _FC_WRITE_MULTIPLE_REGISTERS,
}

_EX_ILLEGAL_FUNCTION = 0x01
_EX_ILLEGAL_DATA_ADDRESS = 0x02
_EX_ILLEGAL_DATA_VALUE = 0x03

_MAX_BIT_QUANTITY = 2000         # FC01/FC02 per Modbus spec
_MAX_REGISTER_QUANTITY = 125     # FC03/FC04 per Modbus spec
_MAX_WRITE_COIL_QUANTITY = 1968  # FC15 per Modbus spec
_MAX_WRITE_REGISTER_QUANTITY = 123  # FC16 per Modbus spec
_MAX_ADDRESS_SPACE = 65536


# ── frame builder helpers (public) ────────────────────────────────────────────


def build_bit_read_response(slave_id: int, function_code: int, bits: list[bool]) -> bytes:
    """Build a FC01/FC02 response: byte_count + bits packed LSB-first."""
    if not bits:
        packed, byte_count = b"\x00", 1
    else:
        byte_count = (len(bits) + 7) // 8
        data = bytearray(byte_count)
        for i, bit in enumerate(bits):
            if bit:
                data[i // 8] |= 1 << (i % 8)
        packed = bytes(data)
    payload = bytes([slave_id, function_code, byte_count]) + packed
    return append_crc(payload)


def build_read_response(slave_id: int, function_code: int, registers: list[int]) -> bytes:
    """Build a FC03/FC04 response: byte_count + register values big-endian."""
    byte_count = len(registers) * 2
    payload = bytes([slave_id, function_code, byte_count])
    for reg in registers:
        payload += bytes([(reg >> 8) & 0xFF, reg & 0xFF])
    return append_crc(payload)


def build_write_single_coil_response(slave_id: int, address: int, value: bool) -> bytes:
    """Build a FC05 echo response."""
    coil_raw = 0xFF00 if value else 0x0000
    payload = bytes([
        slave_id, 0x05,
        (address >> 8) & 0xFF, address & 0xFF,
        (coil_raw >> 8) & 0xFF, coil_raw & 0xFF,
    ])
    return append_crc(payload)


def build_write_single_register_response(slave_id: int, address: int, value: int) -> bytes:
    """Build a FC06 echo response."""
    payload = bytes([
        slave_id, 0x06,
        (address >> 8) & 0xFF, address & 0xFF,
        (value >> 8) & 0xFF, value & 0xFF,
    ])
    return append_crc(payload)


def build_write_multiple_coils_response(slave_id: int, address: int, quantity: int) -> bytes:
    """Build a FC15 response: slave_id, fc, address, quantity."""
    payload = bytes([
        slave_id, 0x0F,
        (address >> 8) & 0xFF, address & 0xFF,
        (quantity >> 8) & 0xFF, quantity & 0xFF,
    ])
    return append_crc(payload)


def build_write_multiple_registers_response(slave_id: int, address: int, quantity: int) -> bytes:
    """Build a FC16 response: slave_id, fc, address, quantity."""
    payload = bytes([
        slave_id, 0x10,
        (address >> 8) & 0xFF, address & 0xFF,
        (quantity >> 8) & 0xFF, quantity & 0xFF,
    ])
    return append_crc(payload)


def build_exception_response(slave_id: int, function_code: int, exception_code: int) -> bytes:
    """Build an exception response: slave_id, fc|0x80, exception_code + CRC."""
    payload = bytes([slave_id, function_code | 0x80, exception_code])
    return append_crc(payload)


# ── simulator ─────────────────────────────────────────────────────────────────


class ModbusSlaveSimulator:
    """Pure in-memory Modbus RTU slave simulator.

    Instantiate with a *slave_id* and optional *datastore*.  Call
    ``handle_request`` with a raw RTU request frame to receive the raw RTU
    response frame.  No serial port or transport is involved.
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

        Returns b"" (silent) for: invalid CRC, addressing another slave, or
        broadcast (slave_id=0, not supported in v1).
        """
        # 1. CRC guard — corrupt frames are ignored silently
        if not verify_crc(frame):
            return b""

        # 2. Parse common RTU fields
        try:
            rtu = parse_rtu_frame(frame)
        except ValueError:
            return b""

        # 3. Slave-ID filter
        #    slave_id==0 (broadcast) is also silently ignored in v1.
        if rtu.slave_id != self.slave_id:
            return b""

        fc = rtu.function_code

        # 4. Function code check
        if fc not in _SUPPORTED_FC:
            return build_exception_response(rtu.slave_id, fc, _EX_ILLEGAL_FUNCTION)

        # 5. Route by FC
        if fc == _FC_COILS:
            return self._handle_read_bits(rtu, frame, self.datastore.read_coils)
        if fc == _FC_DISCRETE:
            return self._handle_read_bits(rtu, frame, self.datastore.read_discrete_inputs)
        if fc == _FC_HOLDING:
            return self._handle_read_registers(rtu, frame, self.datastore.read_holding_registers)
        if fc == _FC_INPUT:
            return self._handle_read_registers(rtu, frame, self.datastore.read_input_registers)
        if fc == _FC_WRITE_COIL:
            return self._handle_write_single_coil(rtu, frame)
        if fc == _FC_WRITE_REGISTER:
            return self._handle_write_single_register(rtu, frame)
        if fc == _FC_WRITE_MULTIPLE_COILS:
            return self._handle_write_multiple_coils(rtu, frame)
        if fc == _FC_WRITE_MULTIPLE_REGISTERS:
            return self._handle_write_multiple_registers(rtu, frame)

        return build_exception_response(rtu.slave_id, fc, _EX_ILLEGAL_FUNCTION)

    # ── read handlers ─────────────────────────────────────────────────────

    def _handle_read_bits(self, rtu, frame, reader):
        try:
            req = parse_bit_read_request(frame)
        except ValueError:
            return build_exception_response(rtu.slave_id, rtu.function_code, _EX_ILLEGAL_FUNCTION)
        if not 1 <= req.quantity <= _MAX_BIT_QUANTITY:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        if req.address + req.quantity > _MAX_ADDRESS_SPACE:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        try:
            bits = reader(req.address, req.quantity)
        except ValueError:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        return build_bit_read_response(req.slave_id, req.function_code, bits)

    def _handle_read_registers(self, rtu, frame, reader):
        try:
            req = parse_read_request(frame)
        except ValueError:
            return build_exception_response(rtu.slave_id, rtu.function_code, _EX_ILLEGAL_FUNCTION)
        if not 1 <= req.quantity <= _MAX_REGISTER_QUANTITY:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        if req.address + req.quantity > _MAX_ADDRESS_SPACE:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        try:
            registers = reader(req.address, req.quantity)
        except ValueError:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        return build_read_response(req.slave_id, req.function_code, registers)

    # ── write handlers ────────────────────────────────────────────────────

    def _handle_write_single_coil(self, rtu, frame):
        try:
            req = parse_write_single_coil_request(frame)
        except ValueError:
            return build_exception_response(rtu.slave_id, 0x05, _EX_ILLEGAL_DATA_VALUE)
        try:
            self.datastore.write_coil(req.address, req.value)
        except ValueError:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        return build_write_single_coil_response(req.slave_id, req.address, req.value)

    def _handle_write_single_register(self, rtu, frame):
        try:
            req = parse_write_single_register_request(frame)
        except ValueError:
            return build_exception_response(rtu.slave_id, 0x06, _EX_ILLEGAL_FUNCTION)
        try:
            self.datastore.write_holding_register(req.address, req.value)
        except ValueError:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        return build_write_single_register_response(req.slave_id, req.address, req.value)

    def _handle_write_multiple_coils(self, rtu, frame):
        try:
            req = parse_write_multiple_coils_request(frame)
        except ValueError:
            return build_exception_response(rtu.slave_id, 0x0F, _EX_ILLEGAL_DATA_VALUE)
        if not 1 <= req.quantity <= _MAX_WRITE_COIL_QUANTITY:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        if req.address + req.quantity > _MAX_ADDRESS_SPACE:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        try:
            self.datastore.write_coil_range(req.address, req.values)
        except ValueError:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        return build_write_multiple_coils_response(req.slave_id, req.address, req.quantity)

    def _handle_write_multiple_registers(self, rtu, frame):
        try:
            req = parse_write_multiple_registers_request(frame)
        except ValueError:
            return build_exception_response(rtu.slave_id, 0x10, _EX_ILLEGAL_DATA_VALUE)
        if not 1 <= req.quantity <= _MAX_WRITE_REGISTER_QUANTITY:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        if req.address + req.quantity > _MAX_ADDRESS_SPACE:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        try:
            self.datastore.write_holding_range(req.address, req.values)
        except ValueError:
            return build_exception_response(req.slave_id, req.function_code, _EX_ILLEGAL_DATA_ADDRESS)
        return build_write_multiple_registers_response(req.slave_id, req.address, req.quantity)
