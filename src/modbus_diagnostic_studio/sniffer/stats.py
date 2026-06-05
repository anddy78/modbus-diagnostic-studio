"""Sniffer statistics."""

from __future__ import annotations

from dataclasses import dataclass, field

from modbus_diagnostic_studio.models.capture import (
    CaptureFrameEvent,
    FrameDirectionGuess,
    MatchedExchange,
)


@dataclass(frozen=True)
class SnifferStats:
    """Snapshot of passive sniffer health statistics."""

    total_frames: int = 0
    valid_crc_frames: int = 0
    invalid_crc_frames: int = 0
    incomplete_frames: int = 0
    requests: int = 0
    responses: int = 0
    exceptions: int = 0
    timeouts: int = 0
    unmatched_responses: int = 0
    slave_ids_seen: set[int] = field(default_factory=set)
    function_codes_seen: set[int] = field(default_factory=set)
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    avg_latency_ms: float | None = None


class SnifferStatsCollector:
    """Collect passive sniffer frame and exchange statistics."""

    def __init__(self) -> None:
        self._total_frames = 0
        self._valid_crc_frames = 0
        self._invalid_crc_frames = 0
        self._incomplete_frames = 0
        self._requests = 0
        self._responses = 0
        self._exceptions = 0
        self._timeouts = 0
        self._unmatched_responses = 0
        self._slave_ids_seen: set[int] = set()
        self._function_codes_seen: set[int] = set()
        self._latencies_ms: list[float] = []

    def add_event(self, event: CaptureFrameEvent) -> None:
        """Add one observed frame event."""
        self._total_frames += 1
        if event.crc_ok:
            self._valid_crc_frames += 1
        else:
            self._invalid_crc_frames += 1

        if event.classification == "incomplete":
            self._incomplete_frames += 1
        if event.direction_guess is FrameDirectionGuess.REQUEST:
            self._requests += 1
        elif event.direction_guess is FrameDirectionGuess.RESPONSE:
            self._responses += 1
        elif event.direction_guess is FrameDirectionGuess.EXCEPTION_RESPONSE:
            self._exceptions += 1

        if event.slave_id is not None:
            self._slave_ids_seen.add(event.slave_id)
        if event.function_code is not None:
            self._function_codes_seen.add(event.function_code)

    def add_exchange(self, exchange: MatchedExchange) -> None:
        """Add one matched, timed-out, or unmatched exchange."""
        if exchange.status == "timeout":
            self._timeouts += 1
        elif exchange.status == "unmatched_response":
            self._unmatched_responses += 1

        if exchange.status in {"ok", "exception"} and exchange.latency_ms is not None:
            self._latencies_ms.append(exchange.latency_ms)

    def snapshot(self) -> SnifferStats:
        """Return an immutable-style stats snapshot with copied sets."""
        min_latency = min(self._latencies_ms) if self._latencies_ms else None
        max_latency = max(self._latencies_ms) if self._latencies_ms else None
        avg_latency = (
            sum(self._latencies_ms) / len(self._latencies_ms)
            if self._latencies_ms
            else None
        )
        return SnifferStats(
            total_frames=self._total_frames,
            valid_crc_frames=self._valid_crc_frames,
            invalid_crc_frames=self._invalid_crc_frames,
            incomplete_frames=self._incomplete_frames,
            requests=self._requests,
            responses=self._responses,
            exceptions=self._exceptions,
            timeouts=self._timeouts,
            unmatched_responses=self._unmatched_responses,
            slave_ids_seen=set(self._slave_ids_seen),
            function_codes_seen=set(self._function_codes_seen),
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            avg_latency_ms=avg_latency,
        )
