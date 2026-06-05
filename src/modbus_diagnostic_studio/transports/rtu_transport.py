"""Minimal active Modbus RTU transport."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from modbus_diagnostic_studio.models.connection import SerialConnectionSettings


class RtuTransport:
    """Small pyserial-backed RTU transport for active master operations."""

    def __init__(
        self,
        settings: SerialConnectionSettings,
        serial_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.settings = settings
        self._serial_factory = serial_factory
        self._serial: Any | None = None

    @property
    def is_open(self) -> bool:
        """Return True when the underlying serial object is open."""
        return bool(self._serial is not None and getattr(self._serial, "is_open", False))

    def open(self) -> None:
        """Open the configured serial port."""
        if self.is_open:
            return

        try:
            if self._serial_factory is None:
                import serial

                self._serial = serial.Serial(
                    port=self.settings.port,
                    baudrate=self.settings.baudrate,
                    bytesize=self.settings.bytesize,
                    parity=self.settings.parity,
                    stopbits=self.settings.stopbits,
                    timeout=self.settings.timeout,
                )
            else:
                self._serial = self._serial_factory(self.settings)
                if hasattr(self._serial, "open") and not getattr(
                    self._serial, "is_open", False
                ):
                    self._serial.open()
        except Exception as exc:
            raise RuntimeError(f"Unable to open serial port {self.settings.port}: {exc}") from exc

    def close(self) -> None:
        """Close the serial port if it is open."""
        if self._serial is None:
            return
        try:
            self._serial.close()
        except Exception as exc:
            raise RuntimeError(f"Unable to close serial port: {exc}") from exc

    def write_frame(self, frame: bytes) -> None:
        """Write one complete RTU frame."""
        if not self.is_open or self._serial is None:
            raise RuntimeError("RTU transport is not open")
        try:
            self._serial.write(frame)
        except Exception as exc:
            raise RuntimeError(f"Serial write failed: {exc}") from exc

    def read_exact(self, size: int) -> bytes:
        """Read exactly size bytes or raise RuntimeError on timeout/error."""
        if not self.is_open or self._serial is None:
            raise RuntimeError("RTU transport is not open")
        if size < 0:
            raise ValueError("Read size must be >= 0")

        deadline = time.monotonic() + self.settings.timeout
        chunks = bytearray()
        try:
            while len(chunks) < size:
                chunk = self._serial.read(size - len(chunks))
                if chunk:
                    chunks.extend(chunk)
                    continue
                if time.monotonic() >= deadline:
                    break
            if len(chunks) != size:
                raise RuntimeError(f"Serial read timed out after {len(chunks)} of {size} bytes")
            return bytes(chunks)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Serial read failed: {exc}") from exc

    def transact(self, request: bytes, expected_min_response_size: int = 5) -> bytes:
        """Write a request and read one normal or exception RTU response."""
        if expected_min_response_size < 5:
            raise ValueError("Expected minimum response size must be at least 5 bytes")

        self.write_frame(request)
        header = self.read_exact(3)
        function_code = header[1]

        if function_code & 0x80:
            return header + self.read_exact(2)

        if function_code in {0x03, 0x04}:
            byte_count = header[2]
            return header + self.read_exact(byte_count + 2)

        remaining = expected_min_response_size - len(header)
        if remaining <= 0:
            return header
        return header + self.read_exact(remaining)
