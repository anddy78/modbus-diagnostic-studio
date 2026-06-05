"""Tests for passive serial sniffer service."""

from __future__ import annotations

import pytest

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.sniffer.passive_serial_sniffer import (
    PassiveSerialSniffer,
    PassiveSerialSnifferConfig,
)
from modbus_diagnostic_studio.sniffer.rtu_stream_framer import RtuFramerConfig


class FakeSerial:
    """Minimal fake serial port for passive sniffer tests."""

    def __init__(self, reads: list[bytes]) -> None:
        self._reads = list(reads)
        self.is_open = False
        self.write_calls = 0

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def read(self, size: int) -> bytes:
        if not self._reads:
            return b""
        return self._reads.pop(0)

    def write(self, data: bytes) -> int:
        self.write_calls += 1
        return len(data)


def make_config() -> PassiveSerialSnifferConfig:
    return PassiveSerialSnifferConfig(
        connection=SerialConnectionSettings(port="COM9", timeout=0.1),
        framer=RtuFramerConfig(baudrate=9600),
        matcher_timeout_ms=200.0,
        read_size=256,
    )


def dtsu71_fast_request() -> bytes:
    return append_crc(bytes.fromhex("0B 03 08 36 00 2A"))


def dtsu71_slow_request() -> bytes:
    return append_crc(bytes.fromhex("0B 03 08 6E 00 42"))


def simple_response() -> bytes:
    return append_crc(bytes.fromhex("0B 03 04 00 64 00 C8"))


def test_open_and_close_with_fake_serial() -> None:
    fake_serial = FakeSerial([])
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: fake_serial,
    )

    sniffer.open()

    assert sniffer.is_open is True

    sniffer.close()

    assert sniffer.is_open is False
    assert fake_serial.write_calls == 0


def test_poll_once_with_valid_request_generates_event() -> None:
    fake_serial = FakeSerial([dtsu71_fast_request(), b""])
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()

    first = sniffer.poll_once(1.0)
    second = sniffer.poll_once(1.01)

    assert first.events == []
    assert len(second.events) == 1
    assert second.events[0].classification == "read_request"
    assert second.events[0].slave_id == 11
    assert second.events[0].address == 2102
    assert second.events[0].quantity == 42
    assert fake_serial.write_calls == 0


def test_poll_once_request_then_response_generates_exchange() -> None:
    fake_serial = FakeSerial([dtsu71_fast_request(), simple_response(), b""])
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()

    sniffer.poll_once(1.0)
    mid = sniffer.poll_once(1.01)
    final = sniffer.poll_once(1.02)

    assert len(mid.events) == 1
    assert len(final.events) == 2
    assert len(final.exchanges) == 1
    assert final.exchanges[0].status == "ok"
    assert final.exchanges[0].latency_ms == pytest.approx(10.0)
    assert final.stats.requests == 1
    assert final.stats.responses == 1
    assert fake_serial.write_calls == 0


def test_poll_once_without_bytes_does_not_break() -> None:
    fake_serial = FakeSerial([b""])
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()

    result = sniffer.poll_once(1.0)

    assert result.events == []
    assert result.exchanges == []
    assert result.stats.total_frames == 0
    assert fake_serial.write_calls == 0


def test_poll_once_with_invalid_crc_updates_stats() -> None:
    invalid_frame = dtsu71_fast_request()[:-1] + b"\x00"
    fake_serial = FakeSerial([invalid_frame, b""])
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()

    sniffer.poll_once(1.0)
    result = sniffer.poll_once(1.01)

    assert len(result.events) == 1
    assert result.events[0].crc_ok is False
    assert result.stats.invalid_crc_frames == 1
    assert fake_serial.write_calls == 0


def test_fingerprint_scores_include_smartlogger_chint_dtsu71() -> None:
    fake_serial = FakeSerial([dtsu71_fast_request(), dtsu71_slow_request(), b""])
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()

    sniffer.poll_once(1.0)
    sniffer.poll_once(1.01)
    result = sniffer.poll_once(1.02)

    assert result.fingerprint_scores
    assert result.fingerprint_scores[0].profile_id == "smartlogger_chint_dtsu71"
    assert fake_serial.write_calls == 0


def test_passive_serial_sniffer_exposes_no_write_send_api() -> None:
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: FakeSerial([]),
    )

    assert hasattr(sniffer, "write") is False
    assert hasattr(sniffer, "send") is False
    assert hasattr(sniffer, "write_frame") is False


def test_fake_serial_write_is_never_called() -> None:
    fake_serial = FakeSerial([dtsu71_fast_request(), b""])
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()

    sniffer.poll_once(1.0)
    sniffer.poll_once(1.01)

    assert fake_serial.write_calls == 0
