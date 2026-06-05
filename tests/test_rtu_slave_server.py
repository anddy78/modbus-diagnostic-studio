"""Unit tests for RtuSlaveServer using a fake serial — no real COM port is opened."""

from __future__ import annotations

import pytest

from modbus_diagnostic_studio.core.crc import append_crc, verify_crc
from modbus_diagnostic_studio.core.rtu_frame import parse_exception_response, parse_read_response
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.slave.datastore import SlaveDatastore
from modbus_diagnostic_studio.slave.rtu_server import (
    RtuSlaveServer,
    RtuSlaveServerConfig,
    _try_extract_frame,
)
from modbus_diagnostic_studio.slave.simulator_engine import ModbusSlaveSimulator


# ── Fake serial helpers ───────────────────────────────────────────────────────


class _FakeSerial:
    """Minimal serial-like object for tests."""

    def __init__(self, rx_data: bytes = b"") -> None:
        self._rx = bytearray(rx_data)
        self.written = bytearray()
        self.is_open = False
        self.raise_on_read: Exception | None = None
        self.raise_on_write: Exception | None = None

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def read(self, size: int) -> bytes:
        if self.raise_on_read is not None:
            raise self.raise_on_read
        chunk = bytes(self._rx[:size])
        del self._rx[:size]
        return chunk

    def write(self, data: bytes) -> int:
        if self.raise_on_write is not None:
            raise self.raise_on_write
        self.written.extend(data)
        return len(data)

    def feed(self, data: bytes) -> None:
        self._rx.extend(data)


def _make_factory(fake: _FakeSerial):
    def factory(settings: SerialConnectionSettings) -> _FakeSerial:
        fake.is_open = True
        return fake
    return factory


def _make_config(slave_id: int = 1) -> RtuSlaveServerConfig:
    return RtuSlaveServerConfig(
        connection=SerialConnectionSettings(
            port="COM_FAKE", baudrate=9600, parity="N", stopbits=1, timeout=0.05
        ),
        slave_id=slave_id,
    )


def _make_read_request(slave_id: int, fc: int, address: int, quantity: int) -> bytes:
    payload = bytes([slave_id, fc,
                     (address >> 8) & 0xFF, address & 0xFF,
                     (quantity >> 8) & 0xFF, quantity & 0xFF])
    return append_crc(payload)


def _make_fc06(slave_id: int, address: int, value: int) -> bytes:
    payload = bytes([slave_id, 0x06,
                     (address >> 8) & 0xFF, address & 0xFF,
                     (value >> 8) & 0xFF, value & 0xFF])
    return append_crc(payload)


# ── _try_extract_frame unit tests ─────────────────────────────────────────────


class TestTryExtractFrame:
    def test_empty_buffer_returns_wait(self) -> None:
        assert _try_extract_frame(bytearray()) == (None, 0)

    def test_one_byte_returns_wait(self) -> None:
        assert _try_extract_frame(bytearray([0x01])) == (None, 0)

    def test_partial_fixed_frame_returns_wait(self) -> None:
        buf = bytearray(append_crc(bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01]))[:5])
        frame, consumed = _try_extract_frame(buf)
        assert consumed == 0  # wait for more

    def test_complete_fc03_frame_extracted(self) -> None:
        req = append_crc(bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01]))
        buf = bytearray(req)
        frame, consumed = _try_extract_frame(buf)
        assert consumed == 8
        assert frame == req

    def test_bad_crc_skips_one_byte(self) -> None:
        req = bytearray(append_crc(bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])))
        req[-1] ^= 0xFF  # corrupt CRC
        frame, consumed = _try_extract_frame(req)
        assert frame is None
        assert consumed == 1

    def test_unknown_fc_skips_one_byte(self) -> None:
        buf = bytearray([0x01, 0x0B, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        frame, consumed = _try_extract_frame(buf)
        assert frame is None
        assert consumed == 1

    def test_fc16_variable_frame_extracted(self) -> None:
        qty = 2
        bc = qty * 2
        data = b"\x00\x01\x00\x02"
        payload = bytes([0x01, 0x10, 0x00, 0x00, 0x00, qty, bc]) + data
        req = append_crc(payload)
        buf = bytearray(req)
        frame, consumed = _try_extract_frame(buf)
        assert consumed == len(req)
        assert frame == req

    def test_fc16_partial_variable_frame_returns_wait(self) -> None:
        qty = 2
        bc = qty * 2
        payload = bytes([0x01, 0x10, 0x00, 0x00, 0x00, qty, bc, 0x00])  # 1 data byte only
        buf = bytearray(payload)
        frame, consumed = _try_extract_frame(buf)
        assert consumed == 0


# ── RtuSlaveServer open/close ────────────────────────────────────────────────


class TestRtuSlaveServerLifecycle:
    def _server(self, fake: _FakeSerial | None = None) -> tuple[RtuSlaveServer, _FakeSerial]:
        if fake is None:
            fake = _FakeSerial()
        sim = ModbusSlaveSimulator(slave_id=1)
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        return server, fake

    def test_open_sets_is_open(self) -> None:
        server, _ = self._server()
        assert not server.is_open
        server.open()
        assert server.is_open

    def test_close_clears_is_open(self) -> None:
        server, _ = self._server()
        server.open()
        server.close()
        assert not server.is_open

    def test_open_idempotent(self) -> None:
        server, _ = self._server()
        server.open()
        server.open()  # should not raise
        assert server.is_open

    def test_poll_without_open_raises(self) -> None:
        server, _ = self._server()
        with pytest.raises(RuntimeError, match="not open"):
            server.poll_once()


# ── RtuSlaveServer FC03 poll cycle ───────────────────────────────────────────


class TestRtuSlaveServerFC03:
    def test_fc03_produces_read_response(self) -> None:
        ds = SlaveDatastore()
        ds.write_holding_range(0, [0x1234, 0x5678])
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        fake = _FakeSerial()
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        fake.feed(_make_read_request(1, 0x03, 0, 2))

        stats = server.poll_once()
        assert stats.requests_seen == 1
        assert stats.responses_sent == 1
        assert stats.ignored_frames == 0

        parsed = parse_read_response(bytes(fake.written))
        assert parsed.registers == [0x1234, 0x5678]
        server.close()

    def test_response_crc_valid(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        fake = _FakeSerial()
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        fake.feed(_make_read_request(1, 0x03, 0, 1))
        server.poll_once()
        assert verify_crc(bytes(fake.written))
        server.close()

    def test_multiple_requests_in_one_poll(self) -> None:
        ds = SlaveDatastore()
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        fake = _FakeSerial()
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        for _ in range(3):
            fake.feed(_make_read_request(1, 0x03, 0, 1))
        stats = server.poll_once()
        assert stats.requests_seen == 3
        assert stats.responses_sent == 3
        server.close()


# ── RtuSlaveServer FC06 write cycle ──────────────────────────────────────────


class TestRtuSlaveServerFC06:
    def test_fc06_updates_datastore(self) -> None:
        ds = SlaveDatastore()
        sim = ModbusSlaveSimulator(slave_id=1, datastore=ds)
        fake = _FakeSerial()
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        fake.feed(_make_fc06(1, 5, 0xABCD))
        stats = server.poll_once()
        assert stats.responses_sent == 1
        assert ds.read_holding_registers(5, 1) == [0xABCD]
        server.close()

    def test_fc06_echo_crc_valid(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        fake = _FakeSerial()
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        fake.feed(_make_fc06(1, 0, 99))
        server.poll_once()
        assert verify_crc(bytes(fake.written))
        server.close()


# ── Ignored / error cases ─────────────────────────────────────────────────────


class TestRtuSlaveServerIgnored:
    def test_invalid_crc_counted_as_crc_error(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        fake = _FakeSerial()
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        bad = bytearray(_make_read_request(1, 0x03, 0, 1))
        bad[-1] ^= 0xFF
        fake.feed(bytes(bad))
        stats = server.poll_once()
        assert stats.crc_errors >= 1
        assert stats.responses_sent == 0
        assert len(fake.written) == 0
        server.close()

    def test_slave_id_mismatch_ignored(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        fake = _FakeSerial()
        server = RtuSlaveServer(_make_config(slave_id=1), sim, serial_factory=_make_factory(fake))
        server.open()
        # Request to slave_id=2
        fake.feed(_make_read_request(2, 0x03, 0, 1))
        stats = server.poll_once()
        assert stats.responses_sent == 0
        assert stats.ignored_frames == 1
        server.close()

    def test_exception_response_counted(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        fake = _FakeSerial()
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        # FC05 with coil value 0x0100 is invalid (must be 0xFF00 or 0x0000)
        # _try_extract_frame recognises FC05 (fixed 8-byte) → simulator returns exception 0x03
        invalid_coil = append_crc(bytes([0x01, 0x05, 0x00, 0x00, 0x01, 0x00]))
        fake.feed(invalid_coil)
        stats = server.poll_once()
        assert stats.exception_responses == 1
        exc = parse_exception_response(bytes(fake.written))
        assert exc.exception_code == 0x03
        server.close()

    def test_serial_read_error_raises_runtime_error(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        fake = _FakeSerial()
        fake.raise_on_read = OSError("port gone")
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        with pytest.raises(RuntimeError, match="Serial read failed"):
            server.poll_once()
        server.close()

    def test_serial_write_error_raises_runtime_error(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        fake = _FakeSerial()
        fake.raise_on_write = OSError("tx buffer full")
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        fake.feed(_make_read_request(1, 0x03, 0, 1))
        with pytest.raises(RuntimeError, match="Serial write failed"):
            server.poll_once()
        server.close()


# ── Stats ─────────────────────────────────────────────────────────────────────


class TestRtuSlaveServerStats:
    def test_stats_snapshot_is_copy(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        fake = _FakeSerial()
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        s1 = server.stats()
        fake.feed(_make_read_request(1, 0x03, 0, 1))
        server.poll_once()
        s2 = server.stats()
        assert s1.responses_sent == 0
        assert s2.responses_sent == 1
        server.close()

    def test_last_request_hex_updated(self) -> None:
        sim = ModbusSlaveSimulator(slave_id=1)
        fake = _FakeSerial()
        server = RtuSlaveServer(_make_config(), sim, serial_factory=_make_factory(fake))
        server.open()
        req = _make_read_request(1, 0x03, 0, 1)
        fake.feed(req)
        stats = server.poll_once()
        assert stats.last_request_hex == req.hex()
        server.close()
