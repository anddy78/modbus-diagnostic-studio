"""Capture event models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FrameDirectionGuess(Enum):
    """Best-effort passive frame direction classification."""

    UNKNOWN = "unknown"
    REQUEST = "request"
    RESPONSE = "response"
    EXCEPTION_RESPONSE = "exception_response"


@dataclass(frozen=True)
class CaptureFrameEvent:
    """One RTU frame observed by a passive sniffer."""

    timestamp_monotonic: float
    raw: bytes
    raw_hex: str
    crc_ok: bool
    classification: str
    direction_guess: FrameDirectionGuess
    slave_id: int | None = None
    function_code: int | None = None
    address: int | None = None
    quantity: int | None = None
    byte_count: int | None = None
    exception_code: int | None = None
    registers: list[int] | None = None
    error: str | None = None


@dataclass(frozen=True)
class MatchedExchange:
    """A matched or timed-out request/response exchange."""

    request: CaptureFrameEvent
    response: CaptureFrameEvent | None
    latency_ms: float | None
    status: str
    note: str = ""


@dataclass(frozen=True)
class CaptureFileMetadata:
    """Small metadata block stored alongside offline capture files."""

    capture_id: str
    started_at: str
    app_version: str
    port: str
    baudrate: int
    parity: str
    stopbits: float
    bytesize: int
    profile_id: str = ""
    stopped_at: str | None = None
    notes: str = ""
