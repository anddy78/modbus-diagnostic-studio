"""Tests for diagnostic session import/export helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from modbus_diagnostic_studio.models.diagnostic_session import (
    DiagnosticSessionEvent,
    add_event,
    create_new_session,
)
from modbus_diagnostic_studio.services.diagnostic_report import (
    read_session_json,
    write_session_csv,
    write_session_html,
    write_session_json,
)


def _sample_session():
    session = create_new_session(title="Report Test", customer="ACME <Plant>")
    add_event(
        session,
        DiagnosticSessionEvent(
            timestamp="2026-06-08T12:00:00+00:00",
            source="manual_note",
            event_type="note",
            severity="info",
            summary="Operator <note>",
            details={"note": "Voltage < 220 & unstable"},
        ),
    )
    return session


def test_write_and_read_session_json(tmp_path: Path) -> None:
    path = tmp_path / "exports" / "session.json"
    write_session_json(path, _sample_session())

    loaded = read_session_json(path)

    assert path.exists()
    assert loaded.metadata.title == "Report Test"
    assert loaded.events[0].details["note"] == "Voltage < 220 & unstable"


def test_write_session_csv(tmp_path: Path) -> None:
    path = tmp_path / "exports" / "session.csv"
    write_session_csv(path, _sample_session())

    text = path.read_text(encoding="utf-8")

    assert "timestamp,source,event_type,severity,summary,details_json" in text
    assert "manual_note" in text
    assert "Operator <note>" in text


def test_write_session_html_escapes_content(tmp_path: Path) -> None:
    path = tmp_path / "exports" / "session.html"
    write_session_html(path, _sample_session())

    text = path.read_text(encoding="utf-8")

    assert "&lt;Plant&gt;" in text
    assert "Voltage &lt; 220 &amp; unstable" in text
    assert "<html" in text.lower()


def test_directory_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_session_json(tmp_path, _sample_session())
    with pytest.raises(ValueError):
        read_session_json(tmp_path)
    with pytest.raises(ValueError):
        write_session_csv(tmp_path, _sample_session())
    with pytest.raises(ValueError):
        write_session_html(tmp_path, _sample_session())
