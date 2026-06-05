"""Tests for passive request/response matching."""

import pytest

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.sniffer.matcher import RequestResponseMatcher
from modbus_diagnostic_studio.sniffer.stream_parser import frame_event_from_bytes


def request_event(timestamp: float = 1.0):
    return frame_event_from_bytes(bytes.fromhex("01 03 00 00 00 02 C4 0B"), timestamp)


def response_event(timestamp: float = 1.1):
    return frame_event_from_bytes(
        append_crc(bytes.fromhex("01 03 04 00 2A 00 64")),
        timestamp,
    )


def test_request_then_response_matches_ok_with_latency() -> None:
    matcher = RequestResponseMatcher(timeout_ms=1000)

    assert matcher.add_event(request_event(1.0)) is None
    exchange = matcher.add_event(response_event(1.2))

    assert exchange is not None
    assert exchange.status == "ok"
    assert exchange.latency_ms == pytest.approx(200.0)
    assert matcher.pending_count() == 0


def test_request_then_exception_matches_exception() -> None:
    matcher = RequestResponseMatcher()
    exception = frame_event_from_bytes(append_crc(bytes.fromhex("01 83 02")), 1.1)

    matcher.add_event(request_event(1.0))
    exchange = matcher.add_event(exception)

    assert exchange is not None
    assert exchange.status == "exception"
    assert exchange.latency_ms == pytest.approx(100.0)


def test_request_timeout() -> None:
    matcher = RequestResponseMatcher(timeout_ms=100)

    matcher.add_event(request_event(1.0))
    expired = matcher.flush_expired(1.2)

    assert len(expired) == 1
    assert expired[0].status == "timeout"
    assert matcher.pending_count() == 0


def test_unmatched_response() -> None:
    matcher = RequestResponseMatcher()

    exchange = matcher.add_event(response_event(1.0))

    assert exchange is not None
    assert exchange.status == "unmatched_response"
    assert exchange.response is exchange.request


def test_pending_count() -> None:
    matcher = RequestResponseMatcher()

    matcher.add_event(request_event(1.0))

    assert matcher.pending_count() == 1
