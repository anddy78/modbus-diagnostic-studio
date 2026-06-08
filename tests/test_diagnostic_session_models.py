"""Tests for pure diagnostic session models."""

from __future__ import annotations

from modbus_diagnostic_studio.models.diagnostic_session import (
    DiagnosticSessionEvent,
    add_event,
    create_new_session,
    session_from_dict,
    session_summary,
    session_to_dict,
)


def test_create_new_session_returns_empty_session() -> None:
    session = create_new_session(title="Site A", technician="Ana")

    assert session.metadata.session_id != ""
    assert session.metadata.title == "Site A"
    assert session.metadata.technician == "Ana"
    assert session.events == []


def test_add_event_updates_session_and_summary() -> None:
    session = create_new_session()
    add_event(
        session,
        DiagnosticSessionEvent(
            timestamp="2026-06-08T12:00:00+00:00",
            source="advanced_master",
            event_type="read",
            severity="info",
            summary="Read OK",
            details={"slave_id": 1},
        ),
    )
    add_event(
        session,
        DiagnosticSessionEvent(
            timestamp="2026-06-08T12:01:00+00:00",
            source="sniffer",
            event_type="timeout",
            severity="warning",
            summary="No response",
            details={},
        ),
    )

    summary = session_summary(session)

    assert len(session.events) == 2
    assert session.metadata.updated_at == "2026-06-08T12:01:00+00:00"
    assert summary == {
        "total_events": 2,
        "errors": 0,
        "warnings": 1,
        "reads": 1,
        "writes": 0,
        "crc_errors": 0,
        "timeouts": 1,
    }


def test_session_to_dict_and_from_dict_round_trip() -> None:
    original = create_new_session(
        title="Line 1",
        customer="Acme",
        site="Plant 7",
        equipment="Meter A",
        technician="Kim",
        notes="Check wiring",
    )
    add_event(
        original,
        DiagnosticSessionEvent(
            timestamp="2026-06-08T13:00:00+00:00",
            source="manual_note",
            event_type="note",
            severity="info",
            summary="Operator report",
            details={"note": "Observed intermittent resets", "count": 2},
        ),
    )

    restored = session_from_dict(session_to_dict(original))

    assert restored.metadata.title == "Line 1"
    assert restored.metadata.customer == "Acme"
    assert restored.metadata.site == "Plant 7"
    assert restored.metadata.equipment == "Meter A"
    assert restored.metadata.technician == "Kim"
    assert restored.metadata.notes == "Check wiring"
    assert len(restored.events) == 1
    assert restored.events[0].details["count"] == 2


def test_session_from_dict_tolerates_missing_details() -> None:
    session = session_from_dict(
        {
            "metadata": {
                "session_id": "abc",
                "created_at": "2026-06-08T10:00:00+00:00",
                "updated_at": "2026-06-08T10:00:00+00:00",
            },
            "events": [
                {
                    "timestamp": "2026-06-08T10:01:00+00:00",
                    "source": "system",
                    "event_type": "note",
                    "severity": "info",
                    "summary": "No details event",
                }
            ],
        }
    )

    assert session.events[0].details == {}
