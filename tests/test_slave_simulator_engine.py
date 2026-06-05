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
)
from modbus_diagnostic_studio.slave.datastore import SlaveDatastore
from modbus_diagnostic_studio.slave.simulator_engine import (
    ModbusSlaveSimulator,
    build_exception_response,
    build_read_response,
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
        # FC05 — Write Single Coil — not supported
        req = append_crc(bytes([0x01, 0x05, 0x00, 0x00, 0xFF, 0x00]))
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
        req = append_crc(bytes([0x01, 0x05, 0x00, 0x00, 0xFF, 0x00]))
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
