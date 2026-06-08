"""Tests for passive serial sniffer service."""

from __future__ import annotations

from unittest.mock import patch

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
        fingerprint_interval_seconds=1.0,
        diagnosis_interval_seconds=1.0,
    )


def make_small_config(
    *,
    max_events: int = 2,
    max_exchanges: int = 1,
) -> PassiveSerialSnifferConfig:
    return PassiveSerialSnifferConfig(
        connection=SerialConnectionSettings(port="COM9", timeout=0.1),
        framer=RtuFramerConfig(baudrate=9600),
        matcher_timeout_ms=200.0,
        read_size=256,
        max_events=max_events,
        max_exchanges=max_exchanges,
        fingerprint_interval_seconds=1.0,
        diagnosis_interval_seconds=1.0,
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
    sniffer.poll_once(1.02)
    result = sniffer.snapshot(force_recompute=True, timestamp_monotonic=2.5)

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


def test_snapshot_limits_events_to_max_events() -> None:
    fake_serial = FakeSerial([dtsu71_fast_request(), simple_response(), dtsu71_slow_request(), b""])
    sniffer = PassiveSerialSniffer(
        make_small_config(max_events=2),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()

    sniffer.poll_once(1.0)
    sniffer.poll_once(1.01)
    sniffer.poll_once(1.02)
    result = sniffer.poll_once(1.03)

    assert len(result.events) == 2
    assert result.events[0].classification == "read_response"
    assert result.events[1].address == 2158


def test_snapshot_limits_exchanges_to_max_exchanges() -> None:
    fake_serial = FakeSerial(
        [
            dtsu71_fast_request(),
            simple_response(),
            dtsu71_slow_request(),
            simple_response(),
            b"",
        ]
    )
    sniffer = PassiveSerialSniffer(
        make_small_config(max_exchanges=1),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()

    sniffer.poll_once(1.0)
    sniffer.poll_once(1.01)
    sniffer.poll_once(1.02)
    sniffer.poll_once(1.03)
    result = sniffer.poll_once(1.04)

    assert len(result.exchanges) == 1
    assert result.exchanges[0].request.address == 2158


def test_snapshot_caches_fingerprint_until_interval() -> None:
    fake_serial = FakeSerial([dtsu71_fast_request(), dtsu71_slow_request(), b""])
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()
    sniffer.poll_once(1.0)
    sniffer.poll_once(1.01)
    sniffer.poll_once(1.02)

    with patch(
        "modbus_diagnostic_studio.sniffer.passive_serial_sniffer.rank_communication_profiles",
        wraps=__import__(
            "modbus_diagnostic_studio.sniffer.passive_serial_sniffer",
            fromlist=["rank_communication_profiles"],
        ).rank_communication_profiles,
    ) as rank_mock:
        first = sniffer.snapshot(timestamp_monotonic=2.0)
        second = sniffer.snapshot(timestamp_monotonic=2.5)

    assert first.fingerprint_scores
    assert second.fingerprint_scores
    assert rank_mock.call_count == 1


def test_snapshot_force_recompute_recalculates_fingerprint() -> None:
    fake_serial = FakeSerial([dtsu71_fast_request(), dtsu71_slow_request(), b""])
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()
    sniffer.poll_once(1.0)
    sniffer.poll_once(1.01)
    sniffer.poll_once(1.02)

    with patch(
        "modbus_diagnostic_studio.sniffer.passive_serial_sniffer.rank_communication_profiles",
        wraps=__import__(
            "modbus_diagnostic_studio.sniffer.passive_serial_sniffer",
            fromlist=["rank_communication_profiles"],
        ).rank_communication_profiles,
    ) as rank_mock:
        sniffer.snapshot(timestamp_monotonic=2.0)
        sniffer.snapshot(force_recompute=True, timestamp_monotonic=2.1)

    assert rank_mock.call_count == 2


def test_snapshot_caches_diagnosis_until_interval_without_changing_stats() -> None:
    fake_serial = FakeSerial([invalid_frame := dtsu71_fast_request()[:-1] + b"\x00", b""])
    sniffer = PassiveSerialSniffer(
        make_config(),
        serial_factory=lambda settings: fake_serial,
    )
    sniffer.open()
    sniffer.poll_once(1.0)
    base = sniffer.poll_once(1.01)

    with patch(
        "modbus_diagnostic_studio.sniffer.passive_serial_sniffer.build_preliminary_diagnosis",
        wraps=__import__(
            "modbus_diagnostic_studio.sniffer.passive_serial_sniffer",
            fromlist=["build_preliminary_diagnosis"],
        ).build_preliminary_diagnosis,
    ) as diagnosis_mock:
        first = sniffer.snapshot(timestamp_monotonic=2.0)
        second = sniffer.snapshot(timestamp_monotonic=2.5)
        third = sniffer.snapshot(timestamp_monotonic=3.1)

    assert base.stats.invalid_crc_frames == 1
    assert first.stats.invalid_crc_frames == 1
    assert second.stats.invalid_crc_frames == 1
    assert third.stats.invalid_crc_frames == 1
    assert len(first.events) == len(second.events) == len(third.events) == 1
    assert diagnosis_mock.call_count == 2
