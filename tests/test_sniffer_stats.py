"""Tests for passive sniffer statistics."""

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.models.capture import MatchedExchange
from modbus_diagnostic_studio.sniffer.stats import SnifferStatsCollector
from modbus_diagnostic_studio.sniffer.stream_parser import frame_event_from_bytes


def test_counts_frames_crc_and_directions() -> None:
    collector = SnifferStatsCollector()
    request = frame_event_from_bytes(bytes.fromhex("01 03 00 00 00 02 C4 0B"), 1.0)
    response = frame_event_from_bytes(
        append_crc(bytes.fromhex("01 03 04 00 2A 00 64")), 1.1
    )
    exception = frame_event_from_bytes(append_crc(bytes.fromhex("01 83 02")), 1.2)
    invalid = frame_event_from_bytes(bytes.fromhex("01 03 00 00 00 0A C5 CC"), 1.3)
    incomplete = frame_event_from_bytes(b"\x01\x03", 1.4)

    for event in [request, response, exception, invalid, incomplete]:
        collector.add_event(event)
    stats = collector.snapshot()

    assert stats.total_frames == 5
    assert stats.valid_crc_frames == 3
    assert stats.invalid_crc_frames == 2
    assert stats.incomplete_frames == 1
    assert stats.requests == 1
    assert stats.responses == 1
    assert stats.exceptions == 1
    assert stats.slave_ids_seen == {1}
    assert stats.function_codes_seen == {3, 0x83}


def test_counts_timeout_unmatched_and_latency() -> None:
    collector = SnifferStatsCollector()
    request = frame_event_from_bytes(bytes.fromhex("01 03 00 00 00 02 C4 0B"), 1.0)
    response = frame_event_from_bytes(
        append_crc(bytes.fromhex("01 03 04 00 2A 00 64")), 1.1
    )

    collector.add_exchange(
        MatchedExchange(
            request=request,
            response=response,
            latency_ms=100.0,
            status="ok",
        )
    )
    collector.add_exchange(
        MatchedExchange(
            request=request,
            response=response,
            latency_ms=300.0,
            status="exception",
        )
    )
    collector.add_exchange(
        MatchedExchange(
            request=request,
            response=None,
            latency_ms=None,
            status="timeout",
        )
    )
    collector.add_exchange(
        MatchedExchange(
            request=response,
            response=response,
            latency_ms=None,
            status="unmatched_response",
        )
    )
    stats = collector.snapshot()

    assert stats.timeouts == 1
    assert stats.unmatched_responses == 1
    assert stats.min_latency_ms == 100.0
    assert stats.max_latency_ms == 300.0
    assert stats.avg_latency_ms == 200.0


def test_snapshot_returns_copied_sets() -> None:
    collector = SnifferStatsCollector()
    event = frame_event_from_bytes(bytes.fromhex("01 03 00 00 00 02 C4 0B"), 1.0)
    collector.add_event(event)

    stats = collector.snapshot()
    stats.slave_ids_seen.add(99)

    assert collector.snapshot().slave_ids_seen == {1}
