"""Communication profile models for passive diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExpectedRequestBlock:
    """One expected Modbus request pattern."""

    address: int
    quantity: int
    function_code: int = 3
    interval_min_ms: float | None = None
    interval_max_ms: float | None = None
    description: str = ""


@dataclass(frozen=True)
class DiagnosticThresholds:
    """Thresholds used by passive diagnostics."""

    max_crc_error_rate_percent: float = 1.0
    max_timeout_rate_percent: float = 5.0
    max_response_latency_ms: float = 500.0


@dataclass(frozen=True)
class CommunicationProfile:
    """Expected master/slave communication behavior."""

    profile_id: str
    name: str
    description: str = ""
    master_role: str = "generic_master"
    slave_role: str = "generic_slave"
    expected_baudrate: int | None = None
    expected_parity: str | None = None
    expected_stopbits: float | None = None
    expected_slave_ids: list[int] = field(default_factory=list)
    expected_functions: list[int] = field(default_factory=list)
    expected_requests: list[ExpectedRequestBlock] = field(default_factory=list)
    linked_register_profile: str | None = None
    thresholds: DiagnosticThresholds = field(default_factory=DiagnosticThresholds)


@dataclass(frozen=True)
class FingerprintScore:
    """Score for one communication profile against observed events."""

    profile_id: str
    name: str
    score: float
    matched_items: list[str]
    missing_items: list[str]
