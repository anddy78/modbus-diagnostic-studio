"""Modbus RTU slave server — reads requests from serial and writes responses.

This module is an *active* component: it calls ``serial.write()`` to respond
to master requests.  It must only be used under AppMode.SLAVE_SIMULATOR via
ModeManager, and must never be used in the same session as the passive sniffer
on the same COM port.

Frame extraction strategy
-------------------------
A simple size-based approach is used instead of timing gaps:
- For FC01-FC06: requests are always exactly 8 bytes.
- For FC15/FC16: total size is determined from the byte_count field at offset 6.
- If CRC of the expected frame is invalid, one byte is skipped and the search
  restarts.  This is the standard "re-sync after noise" strategy for Modbus RTU.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from modbus_diagnostic_studio.core.crc import verify_crc
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.slave.simulator_engine import ModbusSlaveSimulator

# FC codes whose requests are always 8 bytes
_FIXED_8_FC = frozenset({0x01, 0x02, 0x03, 0x04, 0x05, 0x06})
# FC codes with a variable payload (byte_count at offset 6)
_VARIABLE_FC = frozenset({0x0F, 0x10})


@dataclass(frozen=True)
class RtuSlaveServerConfig:
    """Configuration for the RTU slave server."""

    connection: SerialConnectionSettings
    slave_id: int
    read_size: int = 256
    poll_interval_seconds: float = 0.02


@dataclass
class RtuSlaveServerStats:
    """Cumulative statistics for one server session."""

    requests_seen: int = 0
    requests_for_this_slave: int = 0
    responses_sent: int = 0
    ignored_frames: int = 0
    exception_responses: int = 0
    crc_errors: int = 0
    last_request_hex: str = ""
    last_response_hex: str = ""
    last_error: str = ""


def _try_extract_frame(buf: bytearray) -> tuple[bytes | None, int]:
    """Try to extract one complete RTU request frame from *buf*.

    Returns
    -------
    (frame, n)
        *frame* is the validated bytes object; *n* bytes are consumed from buf.
    (None, 0)
        Buffer too short — caller should wait for more data.
    (None, n>0)
        No valid frame found; skip *n* bytes and retry.
    """
    if len(buf) < 2:
        return None, 0

    fc = buf[1]

    if fc in _FIXED_8_FC:
        if len(buf) < 8:
            return None, 0
        frame = bytes(buf[:8])
        return (frame, 8) if verify_crc(frame) else (None, 1)

    if fc in _VARIABLE_FC:
        if len(buf) < 7:
            return None, 0
        byte_count = buf[6]
        expected = 7 + byte_count + 2
        if len(buf) < expected:
            return None, 0
        frame = bytes(buf[:expected])
        return (frame, expected) if verify_crc(frame) else (None, 1)

    # Unknown function code — skip first byte to resync
    return None, 1


class RtuSlaveServer:
    """Serial-backed Modbus RTU slave server.

    Opens a serial port and polls for incoming request frames.  Each valid
    frame is forwarded to the *simulator* engine.  If the engine returns a
    non-empty response, it is written back to the serial port.

    Instantiate with an optional *serial_factory* (callable receiving
    SerialConnectionSettings, returning a serial-like object) for testing
    without real hardware.
    """

    def __init__(
        self,
        config: RtuSlaveServerConfig,
        simulator: ModbusSlaveSimulator,
        serial_factory: Callable[[SerialConnectionSettings], Any] | None = None,
    ) -> None:
        self._config = config
        self._simulator = simulator
        self._serial_factory = serial_factory
        self._serial: Any | None = None
        self._buffer: bytearray = bytearray()
        self._stats: RtuSlaveServerStats = RtuSlaveServerStats()

    # ── lifecycle ─────────────────────────────────────────────────────────

    def open(self) -> None:
        """Open the configured serial port."""
        if self.is_open:
            return
        try:
            if self._serial_factory is not None:
                self._serial = self._serial_factory(self._config.connection)
                if hasattr(self._serial, "open") and not getattr(self._serial, "is_open", False):
                    self._serial.open()
            else:
                import serial
                self._serial = serial.Serial(
                    port=self._config.connection.port,
                    baudrate=self._config.connection.baudrate,
                    bytesize=self._config.connection.bytesize,
                    parity=self._config.connection.parity,
                    stopbits=self._config.connection.stopbits,
                    timeout=self._config.connection.timeout,
                )
        except Exception as exc:
            raise RuntimeError(
                f"Unable to open slave server on {self._config.connection.port}: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the serial port and clear the receive buffer."""
        self._buffer.clear()
        if self._serial is None:
            return
        try:
            self._serial.close()
        except Exception:
            pass
        self._serial = None

    @property
    def is_open(self) -> bool:
        return self._serial is not None and bool(getattr(self._serial, "is_open", False))

    # ── polling ───────────────────────────────────────────────────────────

    def poll_once(self, timestamp_monotonic: float | None = None) -> RtuSlaveServerStats:
        """Read available bytes, process complete frames, write responses.

        Safe to call repeatedly from a background thread or QTimer slot.
        Raises RuntimeError only for unrecoverable serial errors.
        """
        if not self.is_open or self._serial is None:
            raise RuntimeError("RtuSlaveServer is not open")

        _ = timestamp_monotonic  # reserved for future timing diagnostics

        # Read available bytes
        try:
            chunk = self._serial.read(self._config.read_size)
        except Exception as exc:
            self._stats.last_error = str(exc)
            raise RuntimeError(f"Serial read failed: {exc}") from exc

        if chunk:
            self._buffer.extend(chunk)

        # Process complete frames
        while True:
            frame, consumed = _try_extract_frame(self._buffer)

            if consumed == 0:
                break  # incomplete — wait for more bytes

            del self._buffer[:consumed]

            if frame is None:
                # Skipped one byte due to bad CRC or unknown FC
                self._stats.crc_errors += 1
                continue

            self._stats.requests_seen += 1
            self._stats.last_request_hex = frame.hex()

            response = self._simulator.handle_request(frame)

            if not response:
                self._stats.ignored_frames += 1
                continue

            self._stats.requests_for_this_slave += 1
            try:
                self._serial.write(response)
            except Exception as exc:
                self._stats.last_error = str(exc)
                raise RuntimeError(f"Serial write failed: {exc}") from exc

            self._stats.responses_sent += 1
            self._stats.last_response_hex = response.hex()
            if len(response) >= 2 and response[1] & 0x80:
                self._stats.exception_responses += 1

        return self.stats()

    def stats(self) -> RtuSlaveServerStats:
        """Return a snapshot of current statistics."""
        return RtuSlaveServerStats(
            requests_seen=self._stats.requests_seen,
            requests_for_this_slave=self._stats.requests_for_this_slave,
            responses_sent=self._stats.responses_sent,
            ignored_frames=self._stats.ignored_frames,
            exception_responses=self._stats.exception_responses,
            crc_errors=self._stats.crc_errors,
            last_request_hex=self._stats.last_request_hex,
            last_response_hex=self._stats.last_response_hex,
            last_error=self._stats.last_error,
        )
