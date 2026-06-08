"""Diagnostic session import/export helpers."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from modbus_diagnostic_studio.models.diagnostic_session import (
    DiagnosticSession,
    session_from_dict,
    session_summary,
    session_to_dict,
)


def write_session_json(path: str | Path, session: DiagnosticSession) -> None:
    """Write one session as readable JSON."""
    output_path = _prepare_output_path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        json.dump(session_to_dict(session), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_session_json(path: str | Path) -> DiagnosticSession:
    """Read one session from JSON."""
    input_path = Path(path)
    if input_path.exists() and input_path.is_dir():
        raise ValueError(f"Diagnostic session path is a directory: {input_path}")
    with input_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return session_from_dict(data)


def write_session_csv(path: str | Path, session: DiagnosticSession) -> None:
    """Write one session event list as CSV."""
    output_path = _prepare_output_path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "source",
                "event_type",
                "severity",
                "summary",
                "details_json",
            ],
        )
        writer.writeheader()
        for event in session.events:
            writer.writerow(
                {
                    "timestamp": event.timestamp,
                    "source": event.source,
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "summary": event.summary,
                    "details_json": json.dumps(event.details, ensure_ascii=False, sort_keys=True),
                }
            )


def write_session_html(path: str | Path, session: DiagnosticSession) -> None:
    """Write one simple standalone HTML session report."""
    output_path = _prepare_output_path(path)
    metadata = session.metadata
    summary = session_summary(session)
    title = metadata.title or "Diagnostic Session Report"

    rows: list[str] = []
    for event in session.events:
        rows.append(
            "<tr>"
            f"<td>{html.escape(event.timestamp)}</td>"
            f"<td>{html.escape(event.source)}</td>"
            f"<td>{html.escape(event.event_type)}</td>"
            f"<td>{html.escape(event.severity)}</td>"
            f"<td>{html.escape(event.summary)}</td>"
            f"<td><pre>{html.escape(json.dumps(event.details, ensure_ascii=False, indent=2, sort_keys=True))}</pre></td>"
            "</tr>"
        )

    metadata_rows = [
        ("Session ID", metadata.session_id),
        ("Created At", metadata.created_at),
        ("Updated At", metadata.updated_at),
        ("Title", metadata.title),
        ("Customer", metadata.customer),
        ("Site", metadata.site),
        ("Equipment", metadata.equipment),
        ("Technician", metadata.technician),
        ("Notes", metadata.notes),
    ]

    summary_rows = [
        ("Total events", summary["total_events"]),
        ("Warnings", summary["warnings"]),
        ("Errors", summary["errors"]),
        ("Reads", summary["reads"]),
        ("Writes", summary["writes"]),
        ("Timeouts", summary["timeouts"]),
        ("CRC errors", summary["crc_errors"]),
    ]

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #222; }}
    h1, h2 {{ margin-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
    th, td {{ border: 1px solid #bbb; padding: 6px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f0f0f0; }}
    pre {{ margin: 0; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <h2>Metadata</h2>
  <table>
    <tbody>
      {"".join(f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>" for label, value in metadata_rows)}
    </tbody>
  </table>
  <h2>Summary</h2>
  <table>
    <tbody>
      {"".join(f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>" for label, value in summary_rows)}
    </tbody>
  </table>
  <h2>Events</h2>
  <table>
    <thead>
      <tr>
        <th>Timestamp</th>
        <th>Source</th>
        <th>Type</th>
        <th>Severity</th>
        <th>Summary</th>
        <th>Details</th>
      </tr>
    </thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
</body>
</html>
"""
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(document)


def _prepare_output_path(path: str | Path) -> Path:
    output_path = Path(path)
    if output_path.exists() and output_path.is_dir():
        raise ValueError(f"Diagnostic session path is a directory: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path
