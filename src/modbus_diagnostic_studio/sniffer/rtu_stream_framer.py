"""Passive RTU stream segmentation by timing gaps.

This module must never transmit.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RtuFramerConfig:
    """Configuration for approximate passive RTU frame segmentation."""

    baudrate: int = 9600
    gap_multiplier: float = 3.5
    max_frame_size: int = 256
    stale_buffer_seconds: float = 2.0

    def char_time_seconds(self) -> float:
        """Return approximate character time using 11 bits per character."""
        return 11.0 / self.baudrate

    def frame_gap_seconds(self) -> float:
        """Return the minimum silent gap that suggests a frame boundary."""
        return self.char_time_seconds() * self.gap_multiplier


@dataclass(frozen=True)
class FramedRtuPacket:
    """One candidate RTU packet segmented from a passive byte stream."""

    timestamp_monotonic: float
    raw: bytes
    reason: str


class RtuStreamFramer:
    """Segment passive RTU bytes into candidate frames using gaps and size."""

    def __init__(self, config: RtuFramerConfig | None = None) -> None:
        self.config = config or RtuFramerConfig()
        self._buffer = bytearray()
        self._buffer_start_timestamp: float | None = None
        self._last_feed_timestamp: float | None = None

    def feed(self, data: bytes, timestamp_monotonic: float) -> list[FramedRtuPacket]:
        """Feed bytes observed at timestamp and emit completed packets when found."""
        packets: list[FramedRtuPacket] = []

        if (
            self._buffer
            and self._last_feed_timestamp is not None
            and timestamp_monotonic - self._last_feed_timestamp
            >= self.config.frame_gap_seconds()
        ):
            packets.append(self._emit_buffer("gap"))

        self._last_feed_timestamp = timestamp_monotonic
        if not data:
            return packets

        if not self._buffer:
            self._buffer_start_timestamp = timestamp_monotonic
        self._buffer.extend(data)

        if len(self._buffer) >= self.config.max_frame_size:
            packets.append(self._emit_buffer("max_frame_size"))

        return packets

    def flush(self, timestamp_monotonic: float) -> list[FramedRtuPacket]:
        """Emit any buffered bytes as one packet."""
        if self._buffer:
            self._last_feed_timestamp = timestamp_monotonic
            return [self._emit_buffer("flush")]
        return []

    def buffer_size(self) -> int:
        """Return current buffered byte count."""
        return len(self._buffer)

    def clear(self) -> None:
        """Drop buffered bytes without emission."""
        self._buffer.clear()
        self._buffer_start_timestamp = None
        self._last_feed_timestamp = None

    def _emit_buffer(self, reason: str) -> FramedRtuPacket:
        timestamp = self._buffer_start_timestamp
        if timestamp is None:
            timestamp = self._last_feed_timestamp if self._last_feed_timestamp is not None else 0.0
        packet = FramedRtuPacket(
            timestamp_monotonic=timestamp,
            raw=bytes(self._buffer),
            reason=reason,
        )
        self._buffer.clear()
        self._buffer_start_timestamp = None
        return packet
