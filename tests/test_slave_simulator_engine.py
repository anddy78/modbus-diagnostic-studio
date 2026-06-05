"""Unit tests for ModbusSlaveSimulator and frame builder helpers.

All tests are pure in-memory — no serial ports are opened.
RTU request frames are built with append_crc so they carry valid CRCs.
Responses are validated with parse_read_response / parse_exception_response.
"""

from __future__ import annotations

import pytest

from modbus_diagnostic_studio.core.crc import append_crc, verify_crc
from modbus_diagnostic_studio.core.rtu_frame import (
    parse_exception_response,
    parse_read_response,
    parse_write_single_coil_request,
    parse_write_single_register_request,
)
from modbus_diagnostic_studio.slave.datastore import SlaveDatastore
from modbus_diagnostic_studio.slave.simulator_engine import (
    ModbusSlaveSimulator,
    build_bit_read_response,
    build_exception_response,
    build_read_response,
    build_write_multiple_coils_response,
    build_write_multiple_registers_response,
    build_write_single_coil_response,
    build_write_single_register_response,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def make_read_request(slave_id: int, function_code: int, address: int, quantity: int) -> bytes:
    """Build a valid FC03/FC04 read request with CRC."""
    payload = bytes([
        slave_id,
        function_code,
        (address >> 8) & 0xFF,
        address & 0xFF,
        (quantity >> 8) & 0xFF,
        quantity & 0xFF,
    ])
    return append_crc(payload)


def make_bad_crc_request(slave_id: int, function_code: int, address: int, quantity: int) -> bytes:
    """Build a read request with the last CRC byte corrupted."""
    frame = make_read_request(slave_id, function_code, address, quantity)
    return frame[:-1] + bytes([(frame[-1] ^ 0xFF)])


# ── build_read_response ───────────────────────────────────────────────────────


class TestBuildReadResponse:
    def test_structure(self) -> None:
        frame = build_read_response(1, 0x03, [0x1234, 0x5678])
        parsed = parse_read_response(frame)
        assert parsed.slave_id == 1
        assert parsed.function_code == 0x03
        assert parsed.registers == [0x1234, 0x5678]

    def test_crc_valid(self) -> None:
        frame = build_read_response(2, 0x04, [0xABCD])
        assert verify_crc(frame)

    def test_byte_count_correct(self) -> None:
        frame = build_read_response(1, 0x03, [1, 2, 3])
        parsed = parse_read_response(frame)
        assert parsed.byte_count == 6

    def test_empty_registers(self) -> None:
        frame = build_read_response(1, 0x03, [])
        assert verify_crc(frame)
        parsed = parse_read_response(frame)
        assert parsed.registers == []


# ── build_exception_response ──────────────────────────────────────────────────


class TestBuildExceptionResponse:
    def test_structure(self) -> None:
        frame = build_exception_response(3, 0x03, 0x02)
        parsed = parse_exception_response(frame)
        assert parsed.slave_id == 3
        assert parsed.function_code == 0x83
        assert parsed.exception_code == 0x02

    def test_crc_valid(self) -> None:
        frame = build_exception_response(1, 0x04, 0x01)
        assert verify_crc(frame)

    def test_function_code_high_bit_set(self) -> None:
        frame = build_exception_response(1, 0x03, 0x01)
        # byte 1 must be 0x83
        assert frame[1] == 0x83


# ── ModbusSlaveSimulator ──────────────────────────────────────────────────────


class TestModbusSlaveSimulatorFC03:
    def test_fc03_returns_holding_registers(self) -> None:
        ds = SlaveDatastore()
        ds.write_holding_range(0, [10, 20, 30])
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        req = make_read_request(1, 0x03, 0, 3)
        resp = sim.handle_request(req)
        parsed = parse_read_response(resp)
        assert parsed.registers == [10, 20, 30]
        assert parsed.slave_id == 1
        assert parsed.function_code == 0x03

    def test_fc03_non_zero_start_address(self) -> None:
        ds = SlaveDatastore()
        ds.write_holding_range(100, [0xABCD, 0x1234])
        sim = ModbusSlaveSimulator(slave_id=5, datastore=ds)
        req = make_read_request(5, 0x03, 100, 2)
        resp = sim.handle_request(req)
        parsed = parse_read_response(resp)
        assert parsed.registers == [0xABCD, 0x1234]

    def test_fc03_default_zeros(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = make_read_request(1, 0x03, 0, 5)
        resp = sim.handle_request(req)
        parsed = parse_read_response(resp)
        assert parsed.registers == [0, 0, 0, 0, 0]


class TestModbusSlaveSimulatorFC04:
    def test_fc04_returns_input_registers(self) -> None:
        ds = SlaveDatastore()
        ds.write_input_range(10, [500, 600])
        sim = ModbusSlaveSimulator(slave_id=2, datastore=ds)
        req = make_read_request(2, 0x04, 10, 2)
        resp = sim.handle_request(req)
        parsed = parse_read_response(resp)
        assert parsed.registers == [500, 600]
        assert parsed.function_code == 0x04

    def test_fc03_and_fc04_independent(self) -> None:
        ds = SlaveDatastore()
        ds.write_holding_register(0, 111)
        ds.write_input_register(0, 222)
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)

        r03 = parse_read_response(sim.handle_request(make_read_request(1, 0x03, 0, 1)))
        r04 = parse_read_response(sim.handle_request(make_read_request(1, 0x04, 0, 1)))
        assert r03.registers == [111]
        assert r04.registers == [222]


class TestModbusSlaveSimulatorSilentCases:
    def test_slave_id_mismatch_returns_empty(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = make_read_request(slave_id=2, function_code=0x03, address=0, quantity=1)
        assert sim.handle_request(req) == b""

    def test_invalid_crc_returns_empty(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = make_bad_crc_request(1, 0x03, 0, 1)
        assert sim.handle_request(req) == b""

    def test_too_short_frame_returns_empty(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        assert sim.handle_request(b"\x01\x03") == b""

    def test_empty_frame_returns_empty(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        assert sim.handle_request(b"") == b""


class TestModbusSlaveSimulatorExceptions:
    def test_unsupported_function_returns_exception_01(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        # FC11 (0x0B) Get Comm Event Counter — not supported in this simulator
        req = append_crc(bytes([0x01, 0x0B, 0x00, 0x00, 0x00, 0x00]))
        resp = sim.handle_request(req)
        parsed = parse_exception_response(resp)
        assert parsed.slave_id == 1
        assert parsed.exception_code == 0x01

    def test_invalid_address_range_returns_exception_02(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        # address=65535 + quantity=2 exceeds 65536
        req = make_read_request(1, 0x03, 65535, 2)
        resp = sim.handle_request(req)
        parsed = parse_exception_response(resp)
        assert parsed.exception_code == 0x02

    def test_quantity_zero_is_rejected(self) -> None:
        # quantity=0 is invalid per Modbus spec
        sim = ModbusSlaveSimulator(slave_id=1)
        req = make_read_request(1, 0x03, 0, 0)
        resp = sim.handle_request(req)
        # parse_read_request raises ValueError for qty=0 → exception 0x01
        parsed = parse_exception_response(resp)
        assert parsed.exception_code in (0x01, 0x02)

    def test_quantity_over_125_returns_exception_02(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = make_read_request(1, 0x03, 0, 126)
        resp = sim.handle_request(req)
        # ModbusMasterClient._validate_read_arguments rejects >125 but here we
        # build the frame manually; the simulator enforces it on its own.
        parsed = parse_exception_response(resp)
        assert parsed.exception_code == 0x02

    def test_exception_response_crc_valid(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = append_crc(bytes([0x01, 0x0B, 0x00, 0x00, 0x00, 0x00]))
        resp = sim.handle_request(req)
        assert verify_crc(resp)


class TestModbusSlaveSimulatorCrcCorrectness:
    def test_normal_response_crc_valid(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = make_read_request(1, 0x03, 0, 2)
        resp = sim.handle_request(req)
        assert verify_crc(resp)

    def test_response_parseable_by_client_side_parser(self) -> None:
        ds = SlaveDatastore()
        ds.write_holding_range(0, [0x0102, 0x0304])
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        req = make_read_request(1, 0x03, 0, 2)
        resp = sim.handle_request(req)
        parsed = parse_read_response(resp)
        assert parsed.registers == [0x0102, 0x0304]


class TestModbusSlaveSimulatorInit:
    def test_invalid_slave_id_zero(self) -> None:
        with pytest.raises(ValueError, match="slave_id"):
            ModbusSlaveSimulator(slave_id=0)

    def test_invalid_slave_id_248(self) -> None:
        with pytest.raises(ValueError, match="slave_id"):
            ModbusSlaveSimulator(slave_id=248)

    def test_default_datastore_created(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        assert sim.datastore is not None

    def test_custom_datastore_used(self) -> None:
        ds = SlaveDatastore()
        ds.write_holding_register(0, 42)
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        req = make_read_request(1, 0x03, 0, 1)
        resp = sim.handle_request(req)
        parsed = parse_read_response(resp)
        assert parsed.registers == [42]


# ── build_bit_read_response ───────────────────────────────────────────────────


class TestBuildBitReadResponse:
    def test_8_bits_packed_lsb_first(self) -> None:
        bits = [True, False, True, True, False, False, True, False]
        # LSB first: bit0=1 bit1=0 bit2=1 bit3=1 bit4=0 bit5=0 bit6=1 bit7=0 → 0b01001101 = 0x4D
        frame = build_bit_read_response(1, 0x01, bits)
        assert verify_crc(frame)
        assert frame[2] == 1   # byte_count
        assert frame[3] == 0x4D

    def test_byte_count_rounds_up(self) -> None:
        bits = [True] * 9  # 9 bits → 2 bytes
        frame = build_bit_read_response(1, 0x02, bits)
        assert frame[2] == 2


# ── FC01 Read Coils via simulator ─────────────────────────────────────────────


class TestSimulatorFC01FC02:
    def _make_bit_req(self, slave: int, fc: int, addr: int, qty: int) -> bytes:
        payload = bytes([slave, fc,
                         (addr >> 8) & 0xFF, addr & 0xFF,
                         (qty >> 8) & 0xFF, qty & 0xFF])
        return append_crc(payload)

    def test_fc01_read_coils(self) -> None:
        ds = SlaveDatastore()
        ds.write_coil_range(0, [True, False, True])
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        req = self._make_bit_req(1, 0x01, 0, 3)
        resp = sim.handle_request(req)
        assert verify_crc(resp)
        assert resp[1] == 0x01  # FC01 response
        assert resp[2] == 1     # byte_count = 1 for 3 bits

    def test_fc01_coil_values_correct(self) -> None:
        ds = SlaveDatastore()
        ds.write_coil_range(0, [True, False, True, True, False, False, True, False])
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        req = self._make_bit_req(1, 0x01, 0, 8)
        resp = sim.handle_request(req)
        # 0b01001101 = True,False,True,True,False,False,True,False LSB first
        assert resp[3] == 0x4D

    def test_fc02_read_discrete_inputs(self) -> None:
        ds = SlaveDatastore()
        ds.write_discrete_input(5, True)
        sim = ModbusSlaveSimulator(slave_id=2, datastore=ds)
        req = self._make_bit_req(2, 0x02, 5, 1)
        resp = sim.handle_request(req)
        assert verify_crc(resp)
        assert resp[1] == 0x02
        assert resp[3] & 0x01 == 1  # bit 0 of first byte = True

    def test_fc01_fc02_datastore_independence(self) -> None:
        ds = SlaveDatastore()
        ds.write_coil(0, True)
        ds.write_discrete_input(0, False)
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        r01 = sim.handle_request(self._make_bit_req(1, 0x01, 0, 1))
        r02 = sim.handle_request(self._make_bit_req(1, 0x02, 0, 1))
        assert r01[3] & 0x01 == 1
        assert r02[3] & 0x01 == 0

    def test_fc01_quantity_over_limit_returns_exception_02(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = self._make_bit_req(1, 0x01, 0, 2001)
        resp = sim.handle_request(req)
        parsed = parse_exception_response(resp)
        assert parsed.exception_code == 0x02


# ── FC05 Write Single Coil via simulator ──────────────────────────────────────


class TestSimulatorFC05:
    def _make_fc05(self, slave: int, addr: int, value: bool) -> bytes:
        v = 0xFF00 if value else 0x0000
        payload = bytes([slave, 0x05,
                         (addr >> 8) & 0xFF, addr & 0xFF,
                         (v >> 8) & 0xFF, v & 0xFF])
        return append_crc(payload)

    def test_fc05_write_coil_on(self) -> None:
        ds = SlaveDatastore()
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        req = self._make_fc05(1, 10, True)
        resp = sim.handle_request(req)
        assert verify_crc(resp)
        assert ds.read_coils(10, 1) == [True]

    def test_fc05_write_coil_off(self) -> None:
        ds = SlaveDatastore()
        ds.write_coil(0, True)
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        req = self._make_fc05(1, 0, False)
        sim.handle_request(req)
        assert ds.read_coils(0, 1) == [False]

    def test_fc05_echo_response_structure(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=3)
        req = self._make_fc05(3, 5, True)
        resp = sim.handle_request(req)
        req_parsed = parse_write_single_coil_request(resp)
        assert req_parsed.slave_id == 3
        assert req_parsed.address == 5
        assert req_parsed.value is True

    def test_fc05_invalid_coil_value_returns_exception_03(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = append_crc(bytes([0x01, 0x05, 0x00, 0x00, 0x01, 0x00]))  # 0x0100 invalid
        resp = sim.handle_request(req)
        parsed = parse_exception_response(resp)
        assert parsed.exception_code == 0x03


# ── FC06 Write Single Register via simulator ──────────────────────────────────


class TestSimulatorFC06:
    def _make_fc06(self, slave: int, addr: int, value: int) -> bytes:
        payload = bytes([slave, 0x06,
                         (addr >> 8) & 0xFF, addr & 0xFF,
                         (value >> 8) & 0xFF, value & 0xFF])
        return append_crc(payload)

    def test_fc06_write_register(self) -> None:
        ds = SlaveDatastore()
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        req = self._make_fc06(1, 100, 0xABCD)
        resp = sim.handle_request(req)
        assert verify_crc(resp)
        assert ds.read_holding_registers(100, 1) == [0xABCD]

    def test_fc06_echo_response(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=2)
        req = self._make_fc06(2, 50, 999)
        resp = sim.handle_request(req)
        parsed = parse_write_single_register_request(resp)
        assert parsed.address == 50
        assert parsed.value == 999

    def test_fc06_response_crc_valid(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = self._make_fc06(1, 0, 0)
        assert verify_crc(sim.handle_request(req))


# ── FC15 Write Multiple Coils via simulator ───────────────────────────────────


class TestSimulatorFC15:
    def _make_fc15(self, slave: int, addr: int, bits: list[bool]) -> bytes:
        qty = len(bits)
        bc = (qty + 7) // 8
        data = bytearray(bc)
        for i, b in enumerate(bits):
            if b:
                data[i // 8] |= 1 << (i % 8)
        payload = bytes([slave, 0x0F,
                         (addr >> 8) & 0xFF, addr & 0xFF,
                         (qty >> 8) & 0xFF, qty & 0xFF,
                         bc]) + bytes(data)
        return append_crc(payload)

    def test_fc15_writes_coils(self) -> None:
        ds = SlaveDatastore()
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        bits = [True, False, True, True, False, False, True, False]
        req = self._make_fc15(1, 0, bits)
        resp = sim.handle_request(req)
        assert verify_crc(resp)
        assert ds.read_coils(0, 8) == bits

    def test_fc15_response_format(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = self._make_fc15(1, 5, [True, False, True])
        resp = sim.handle_request(req)
        # response: slave_id, 0x0F, addr_hi, addr_lo, qty_hi, qty_lo, crc_lo, crc_hi
        assert resp[0] == 1
        assert resp[1] == 0x0F
        assert (resp[2] << 8 | resp[3]) == 5   # address
        assert (resp[4] << 8 | resp[5]) == 3   # quantity

    def test_fc15_response_crc_valid(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = self._make_fc15(1, 0, [True])
        assert verify_crc(sim.handle_request(req))


# ── FC16 Write Multiple Registers via simulator ───────────────────────────────


class TestSimulatorFC16:
    def _make_fc16(self, slave: int, addr: int, values: list[int]) -> bytes:
        qty = len(values)
        bc = qty * 2
        data = b"".join(bytes([(v >> 8) & 0xFF, v & 0xFF]) for v in values)
        payload = bytes([slave, 0x10,
                         (addr >> 8) & 0xFF, addr & 0xFF,
                         (qty >> 8) & 0xFF, qty & 0xFF,
                         bc]) + data
        return append_crc(payload)

    def test_fc16_writes_registers(self) -> None:
        ds = SlaveDatastore()
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        req = self._make_fc16(1, 10, [0x1111, 0x2222, 0x3333])
        resp = sim.handle_request(req)
        assert verify_crc(resp)
        assert ds.read_holding_registers(10, 3) == [0x1111, 0x2222, 0x3333]

    def test_fc16_response_format(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = self._make_fc16(1, 20, [1, 2])
        resp = sim.handle_request(req)
        assert resp[0] == 1
        assert resp[1] == 0x10
        assert (resp[2] << 8 | resp[3]) == 20  # address
        assert (resp[4] << 8 | resp[5]) == 2   # quantity

    def test_fc16_quantity_over_limit_returns_exception_02(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = self._make_fc16(1, 0, [0] * 124)  # 124 > 123 max
        resp = sim.handle_request(req)
        parsed = parse_exception_response(resp)
        assert parsed.exception_code == 0x02

    def test_fc16_response_crc_valid(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        req = self._make_fc16(1, 0, [42])
        assert verify_crc(sim.handle_request(req))


# ── build_write helpers ───────────────────────────────────────────────────────


class TestBuildWriteHelpers:
    def test_build_write_single_coil_on(self) -> None:
        frame = build_write_single_coil_response(1, 0xAC, True)
        assert verify_crc(frame)
        assert frame[1] == 0x05
        assert frame[4] == 0xFF and frame[5] == 0x00

    def test_build_write_single_coil_off(self) -> None:
        frame = build_write_single_coil_response(1, 0, False)
        assert frame[4] == 0x00 and frame[5] == 0x00

    def test_build_write_single_register(self) -> None:
        frame = build_write_single_register_response(2, 10, 0x1234)
        assert verify_crc(frame)
        assert frame[1] == 0x06
        assert (frame[4] << 8 | frame[5]) == 0x1234

    def test_build_write_multiple_coils(self) -> None:
        frame = build_write_multiple_coils_response(1, 5, 16)
        assert verify_crc(frame)
        assert frame[1] == 0x0F
        assert (frame[4] << 8 | frame[5]) == 16

    def test_build_write_multiple_registers(self) -> None:
        frame = build_write_multiple_registers_response(1, 0, 3)
        assert verify_crc(frame)
        assert frame[1] == 0x10
        assert (frame[4] << 8 | frame[5]) == 3
