"""Pure diagnostic session models and helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

SessionDetailValue = str | int | float | bool | None


@dataclass
class DiagnosticSessionMetadata:
    """Descriptive metadata for one diagnostic session."""

    session_id: str
    created_at: str
    updated_at: str
    title: str = ""
    customer: str = ""
    site: str = ""
    equipment: str = ""
    technician: str = ""
    notes: str = ""


@dataclass
class DiagnosticSessionEvent:
    """One session event recorded from a GUI workflow or manual note."""

    timestamp: str
    source: str
    event_type: str
    severity: str
    summary: str
    details: dict[str, SessionDetailValue] = field(default_factory=dict)


@dataclass
class DiagnosticSession:
    """Full diagnostic session with metadata and a chronological event list."""

    metadata: DiagnosticSessionMetadata
    events: list[DiagnosticSessionEvent] = field(default_factory=list)


def create_new_session(
    *,
    title: str = "",
    customer: str = "",
    site: str = "",
    equipment: str = "",
    technician: str = "",
    notes: str = "",
) -> DiagnosticSession:
    """Create a new empty session with generated id and timestamps."""
    timestamp = _utc_now_iso()
    metadata = DiagnosticSessionMetadata(
        session_id=uuid4().hex,
        created_at=timestamp,
        updated_at=timestamp,
        title=title,
        customer=customer,
        site=site,
        equipment=equipment,
        technician=technician,
        notes=notes,
    )
    return DiagnosticSession(metadata=metadata)


def add_event(
    session: DiagnosticSession,
    event: DiagnosticSessionEvent,
) -> DiagnosticSession:
    """Append one event and refresh the session updated timestamp."""
    session.events.append(event)
    session.metadata.updated_at = event.timestamp or _utc_now_iso()
    return session


def session_to_dict(session: DiagnosticSession) -> dict:
    """Convert a session into JSON-compatible data."""
    return asdict(session)


def session_from_dict(data: dict) -> DiagnosticSession:
    """Build a session from JSON-compatible data."""
    metadata_data = data.get("metadata", {})
    metadata = DiagnosticSessionMetadata(
        session_id=_coerce_string(metadata_data.get("session_id", "")),
        created_at=_coerce_string(metadata_data.get("created_at", "")),
        updated_at=_coerce_string(
            metadata_data.get("updated_at", metadata_data.get("created_at", ""))
        ),
        title=_coerce_string(metadata_data.get("title", "")),
        customer=_coerce_string(metadata_data.get("customer", "")),
        site=_coerce_string(metadata_data.get("site", "")),
        equipment=_coerce_string(metadata_data.get("equipment", "")),
        technician=_coerce_string(metadata_data.get("technician", "")),
        notes=_coerce_string(metadata_data.get("notes", "")),
    )
    events: list[DiagnosticSessionEvent] = []
    for event_data in data.get("events", []):
        raw_details = event_data.get("details") or {}
        details = {
            str(key): _coerce_detail_value(value)
            for key, value in dict(raw_details).items()
        }
        events.append(
            DiagnosticSessionEvent(
                timestamp=str(event_data.get("timestamp", "")),
                source=str(event_data.get("source", "")),
                event_type=str(event_data.get("event_type", "")),
                severity=str(event_data.get("severity", "info")),
                summary=str(event_data.get("summary", "")),
                details=details,
            )
        )
    return DiagnosticSession(metadata=metadata, events=events)


def session_summary(session: DiagnosticSession) -> dict[str, int]:
    """Return a small counter summary for the session."""
    counters = {
        "total_events": len(session.events),
        "errors": 0,
        "warnings": 0,
        "reads": 0,
        "writes": 0,
        "crc_errors": 0,
        "timeouts": 0,
    }
    for event in session.events:
        if event.severity == "error":
            counters["errors"] += 1
        if event.severity == "warning":
            counters["warnings"] += 1
        if event.event_type == "read":
            counters["reads"] += 1
        if event.event_type == "write":
            counters["writes"] += 1
        if event.event_type == "crc_error":
            counters["crc_errors"] += 1
        if event.event_type == "timeout":
            counters["timeouts"] += 1
    return counters


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _coerce_detail_value(value: object) -> SessionDetailValue:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _coerce_string(value: object) -> str:
    if value is None:
        return ""
    return str(value)
