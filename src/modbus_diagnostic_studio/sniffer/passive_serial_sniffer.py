"""Passive serial sniffer service.

Safety rule:
This module must never transmit.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from modbus_diagnostic_studio.models.capture import CaptureFrameEvent, MatchedExchange
from modbus_diagnostic_studio.models.communication_profile import FingerprintScore
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.sniffer.communication_profiles import (
    load_all_builtin_communication_profiles,
)
from modbus_diagnostic_studio.sniffer.diagnostics import build_preliminary_diagnosis
from modbus_diagnostic_studio.sniffer.fingerprint import rank_communication_profiles
from modbus_diagnostic_studio.sniffer.matcher import RequestResponseMatcher
from modbus_diagnostic_studio.sniffer.rtu_stream_framer import (
    RtuFramerConfig,
    RtuStreamFramer,
)
from modbus_diagnostic_studio.sniffer.stats import SnifferStats, SnifferStatsCollector
from modbus_diagnostic_studio.sniffer.stream_parser import frame_event_from_bytes


@dataclass(frozen=True)
class PassiveSnifferSnapshot:
    """Current passive sniffer snapshot."""

    events: list[CaptureFrameEvent]
    exchanges: list[MatchedExchange]
    stats: SnifferStats
    diagnosis: list[str]
    fingerprint_scores: list[FingerprintScore]


@dataclass(frozen=True)
class PassiveSerialSnifferConfig:
    """Passive serial sniffer configuration."""

    connection: SerialConnectionSettings
    framer: RtuFramerConfig
    matcher_timeout_ms: float = 1000.0
    read_size: int = 256

    def __post_init__(self) -> None:
        if self.matcher_timeout_ms <= 0:
            raise ValueError("Matcher timeout must be > 0")
        if self.read_size <= 0:
            raise ValueError("Read size must be > 0")


class PassiveSerialSniffer:
    """Passively read serial bytes and build diagnostic snapshots."""

    def __init__(
        self,
        config: PassiveSerialSnifferConfig,
        serial_factory: Callable[..., Any] | None = None,
        communication_profiles: list[Any] | None = None,
    ) -> None:
        self.config = config
        self._serial_factory = serial_factory
        self._communication_profiles = (
            communication_profiles
            if communication_profiles is not None
            else load_all_builtin_communication_profiles()
        )
        self._serial: Any | None = None
        self._framer = RtuStreamFramer(config.framer)
        self._matcher = RequestResponseMatcher(timeout_ms=config.matcher_timeout_ms)
        self._stats = SnifferStatsCollector()
        self._events: list[CaptureFrameEvent] = []
        self._exchanges: list[MatchedExchange] = []

    @property
    def is_open(self) -> bool:
        """Return True when the underlying serial object is open."""
        if self._serial is None:
            return False
        is_open = getattr(self._serial, "is_open", None)
        if is_open is None:
            return True
        return bool(is_open)

    def open(self) -> None:
        """Open the configured serial port for passive reads."""
        if self.is_open:
            return

        settings = self.config.connection
        try:
            if self._serial_factory is None:
                import serial

                self._serial = serial.Serial(
                    port=settings.port,
                    baudrate=settings.baudrate,
                    bytesize=settings.bytesize,
                    parity=settings.parity,
                    stopbits=settings.stopbits,
                    timeout=settings.timeout,
                )
            else:
                self._serial = self._serial_factory(settings)
                if hasattr(self._serial, "open") and not getattr(
                    self._serial, "is_open", False
                ):
                    self._serial.open()
        except Exception as exc:
            self._serial = None
            raise RuntimeError(
                f"Unable to open passive serial sniffer on {settings.port}: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the configured serial port if it is open."""
        if self._serial is None:
            return

        serial_obj = self._serial
        self._serial = None
        try:
            serial_obj.close()
        except Exception as exc:
            raise RuntimeError(f"Unable to close passive serial sniffer: {exc}") from exc

    def poll_once(
        self,
        timestamp_monotonic: float | None = None,
    ) -> PassiveSnifferSnapshot:
        """Read one serial chunk, process frames, and return a snapshot."""
        if not self.is_open or self._serial is None:
            raise RuntimeError("Passive serial sniffer is not open")

        now = time.monotonic() if timestamp_monotonic is None else timestamp_monotonic
        data = self._read_chunk()
        packets = self._framer.feed(data, now)
        new_exchanges = self._process_packets(packets)
        new_exchanges.extend(self._matcher.flush_expired(now))

        for exchange in new_exchanges:
            self._exchanges.append(exchange)
            self._stats.add_exchange(exchange)

        return self.snapshot()

    def snapshot(self) -> PassiveSnifferSnapshot:
        """Return the current accumulated sniffer view."""
        stats = self._stats.snapshot()
        diagnosis = build_preliminary_diagnosis(stats)
        fingerprint_scores = (
            rank_communication_profiles(self._communication_profiles, self._events)
            if self._communication_profiles
            else []
        )
        return PassiveSnifferSnapshot(
            events=list(self._events),
            exchanges=list(self._exchanges),
            stats=stats,
            diagnosis=diagnosis,
            fingerprint_scores=fingerprint_scores,
        )

    def _read_chunk(self) -> bytes:
        try:
            data = self._serial.read(self.config.read_size)
        except Exception as exc:
            raise RuntimeError(f"Passive serial read failed: {exc}") from exc
        if not data:
            return b""
        if isinstance(data, bytes):
            return data
        return bytes(data)

    def _process_packets(self, packets: list[Any]) -> list[MatchedExchange]:
        exchanges: list[MatchedExchange] = []
        for packet in packets:
            event = frame_event_from_bytes(packet.raw, packet.timestamp_monotonic)
            self._events.append(event)
            self._stats.add_event(event)
            exchange = self._matcher.add_event(event)
            if exchange is not None:
                exchanges.append(exchange)
        return exchanges
