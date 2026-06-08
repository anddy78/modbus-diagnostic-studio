"""Diagnostic Report tab for manual diagnostic session evidence management."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.gui.help import set_help
from modbus_diagnostic_studio.models.diagnostic_session import (
    DiagnosticSession,
    DiagnosticSessionEvent,
    session_summary,
)
from modbus_diagnostic_studio.services.application_state import ApplicationState
from modbus_diagnostic_studio.services.diagnostic_report import (
    read_session_json,
    write_session_csv,
    write_session_html,
    write_session_json,
)
from modbus_diagnostic_studio.services.paths import ensure_runtime_dirs, exports_dir


class DiagnosticReportTab(QWidget):
    """Manage one active diagnostic session and export evidence reports."""

    def __init__(self, app_state: ApplicationState | None = None) -> None:
        super().__init__()
        self._app_state = app_state or ApplicationState()
        self._syncing_fields = False

        self.status_label = QLabel(
            "Diagnostic Report centralizes notes and evidence without opening ports."
        )

        self.title_edit = QLineEdit()
        self.customer_edit = QLineEdit()
        self.site_edit = QLineEdit()
        self.equipment_edit = QLineEdit()
        self.technician_edit = QLineEdit()
        self.notes_edit = QTextEdit()
        self.notes_edit.setMinimumHeight(90)
        self.manual_note_input = QTextEdit()
        self.manual_note_input.setMinimumHeight(70)

        self.new_session_button = QPushButton("New Session")
        self.new_session_button.clicked.connect(self.new_session)
        self.save_json_button = QPushButton("Save Session JSON")
        self.save_json_button.clicked.connect(self.save_session_json)
        self.load_json_button = QPushButton("Load Session JSON")
        self.load_json_button.clicked.connect(self.load_session_json)
        self.export_csv_button = QPushButton("Export CSV")
        self.export_csv_button.clicked.connect(self.export_csv)
        self.export_html_button = QPushButton("Export HTML")
        self.export_html_button.clicked.connect(self.export_html)
        self.add_manual_note_button = QPushButton("Add Manual Note")
        self.add_manual_note_button.clicked.connect(self.add_manual_note)
        self.clear_events_button = QPushButton("Clear Events")
        self.clear_events_button.clicked.connect(self.clear_events)

        self.summary_labels = {
            "total_events": QLabel("0"),
            "warnings": QLabel("0"),
            "errors": QLabel("0"),
            "reads": QLabel("0"),
            "writes": QLabel("0"),
            "timeouts": QLabel("0"),
            "crc_errors": QLabel("0"),
        }

        self.events_table = QTableWidget(0, 5)
        self.events_table.setHorizontalHeaderLabels(
            ["Timestamp", "Source", "Type", "Severity", "Summary"]
        )
        self.events_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.events_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.events_table.setMinimumHeight(220)
        self.events_table.itemSelectionChanged.connect(self._update_selected_event_details)

        self.event_details_output = QTextEdit()
        self.event_details_output.setReadOnly(True)
        self.event_details_output.setMinimumHeight(140)

        self._build_layout()
        self._attach_help()
        self._connect_metadata_fields()
        self._ensure_session()
        self._load_session_into_fields()
        self._refresh_session_view()

    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("Title", self.title_edit)
        form.addRow("Customer", self.customer_edit)
        form.addRow("Site", self.site_edit)
        form.addRow("Equipment", self.equipment_edit)
        form.addRow("Technician", self.technician_edit)
        form.addRow("Notes", self.notes_edit)

        summary_grid = QGridLayout()
        labels = [
            ("Total events", "total_events"),
            ("Warnings", "warnings"),
            ("Errors", "errors"),
            ("Reads", "reads"),
            ("Writes", "writes"),
            ("Timeouts", "timeouts"),
            ("CRC errors", "crc_errors"),
        ]
        for index, (label, key) in enumerate(labels):
            row = index // 2
            col = (index % 2) * 2
            summary_grid.addWidget(QLabel(label), row, col)
            summary_grid.addWidget(self.summary_labels[key], row, col + 1)

        button_row = QHBoxLayout()
        button_row.addWidget(self.new_session_button)
        button_row.addWidget(self.save_json_button)
        button_row.addWidget(self.load_json_button)
        button_row.addWidget(self.export_csv_button)
        button_row.addWidget(self.export_html_button)
        button_row.addWidget(self.add_manual_note_button)
        button_row.addWidget(self.clear_events_button)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.addWidget(self.status_label)
        content_layout.addLayout(form)
        content_layout.addWidget(QLabel("Session Summary"))
        content_layout.addLayout(summary_grid)
        content_layout.addLayout(button_row)
        content_layout.addWidget(QLabel("Manual Note Input"))
        content_layout.addWidget(self.manual_note_input)
        content_layout.addWidget(QLabel("Session Events"))
        content_layout.addWidget(self.events_table)
        content_layout.addWidget(QLabel("Selected Event Details"))
        content_layout.addWidget(self.event_details_output)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        layout = QVBoxLayout()
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _attach_help(self) -> None:
        set_help(
            self.new_session_button,
            "New Session",
            "Create a fresh diagnostic session for the current job without opening ports.",
        )
        set_help(
            self.add_manual_note_button,
            "Add Manual Note",
            "Append a manual note event to the current session using the note input or Notes field.",
        )
        set_help(
            self.export_html_button,
            "Export HTML",
            "Export the current diagnostic session as a standalone HTML report.",
        )
        set_help(
            self.events_table,
            "Session Events",
            "Chronological event list for the current diagnostic session. Selecting a row shows its details.",
        )

    def _connect_metadata_fields(self) -> None:
        for edit in (
            self.title_edit,
            self.customer_edit,
            self.site_edit,
            self.equipment_edit,
            self.technician_edit,
        ):
            edit.editingFinished.connect(self._update_session_metadata_from_fields)
        self.notes_edit.textChanged.connect(self._update_session_metadata_from_fields)

    def _ensure_session(self) -> DiagnosticSession:
        if self._app_state.current_session is None:
            self._app_state.new_session()
        return self._app_state.current_session

    def new_session(self) -> None:
        """Create a fresh active session using the current metadata fields as seed values."""
        self._app_state.new_session(
            title=self.title_edit.text().strip(),
            customer=self.customer_edit.text().strip(),
            site=self.site_edit.text().strip(),
            equipment=self.equipment_edit.text().strip(),
            technician=self.technician_edit.text().strip(),
            notes=self.notes_edit.toPlainText().strip(),
        )
        self.manual_note_input.clear()
        self._load_session_into_fields()
        self._refresh_session_view()
        self.status_label.setText("Created a new diagnostic session.")

    def add_manual_note(self) -> None:
        """Append one manual note event to the active session."""
        session = self._ensure_session()
        self._update_session_metadata_from_fields()
        note_text = self.manual_note_input.toPlainText().strip() or self.notes_edit.toPlainText().strip()
        if not note_text:
            self.status_label.setText("Enter a manual note before adding it to the session.")
            return

        event = DiagnosticSessionEvent(
            timestamp=_now_iso(),
            source="manual_note",
            event_type="note",
            severity="info",
            summary=_truncate_summary(note_text),
            details={"note": note_text},
        )
        self._app_state.add_session_event(event)
        self.manual_note_input.clear()
        self._refresh_session_view()
        self.status_label.setText("Manual note added to the diagnostic session.")

    def clear_events(self) -> None:
        """Remove all current session events."""
        session = self._ensure_session()
        session.events.clear()
        session.metadata.updated_at = _now_iso()
        self._refresh_session_view()
        self.status_label.setText("Cleared all diagnostic session events.")

    def save_session_json(self) -> None:
        """Save the current session to JSON using a file dialog."""
        ensure_runtime_dirs()
        default_path = exports_dir() / "diagnostic_session.json"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save Diagnostic Session JSON",
            str(default_path),
            "JSON files (*.json)",
        )
        if not path_str:
            return
        self.save_session_to_path(path_str)

    def load_session_json(self) -> None:
        """Load a diagnostic session from JSON using a file dialog."""
        ensure_runtime_dirs()
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Load Diagnostic Session JSON",
            str(exports_dir()),
            "JSON files (*.json)",
        )
        if not path_str:
            return
        self.load_session_from_path(path_str)

    def export_csv(self) -> None:
        """Export current session events to CSV using a file dialog."""
        ensure_runtime_dirs()
        default_path = exports_dir() / "diagnostic_session.csv"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Diagnostic Session CSV",
            str(default_path),
            "CSV files (*.csv)",
        )
        if not path_str:
            return
        self.export_csv_to_path(path_str)

    def export_html(self) -> None:
        """Export the current session as HTML using a file dialog."""
        ensure_runtime_dirs()
        default_path = exports_dir() / "diagnostic_session.html"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Diagnostic Session HTML",
            str(default_path),
            "HTML files (*.html)",
        )
        if not path_str:
            return
        self.export_html_to_path(path_str)

    def save_session_to_path(self, path: str | Path) -> None:
        """Save the current session JSON to a concrete path."""
        session = self._ensure_session()
        self._update_session_metadata_from_fields()
        write_session_json(path, session)
        self.status_label.setText(f"Session JSON saved to: {path}")

    def load_session_from_path(self, path: str | Path) -> None:
        """Load a session JSON from a concrete path."""
        session = read_session_json(path)
        self._app_state.current_session = session
        self._load_session_into_fields()
        self._refresh_session_view()
        self.status_label.setText(f"Session JSON loaded from: {path}")

    def export_csv_to_path(self, path: str | Path) -> None:
        """Export the current session to CSV at a concrete path."""
        session = self._ensure_session()
        self._update_session_metadata_from_fields()
        write_session_csv(path, session)
        self.status_label.setText(f"Session CSV exported to: {path}")

    def export_html_to_path(self, path: str | Path) -> None:
        """Export the current session to HTML at a concrete path."""
        session = self._ensure_session()
        self._update_session_metadata_from_fields()
        write_session_html(path, session)
        self.status_label.setText(f"Session HTML exported to: {path}")

    def _load_session_into_fields(self) -> None:
        session = self._ensure_session()
        metadata = session.metadata
        self._syncing_fields = True
        self.title_edit.setText(metadata.title)
        self.customer_edit.setText(metadata.customer)
        self.site_edit.setText(metadata.site)
        self.equipment_edit.setText(metadata.equipment)
        self.technician_edit.setText(metadata.technician)
        self.notes_edit.setPlainText(metadata.notes)
        self._syncing_fields = False

    def _update_session_metadata_from_fields(self) -> None:
        if self._syncing_fields:
            return
        session = self._ensure_session()
        metadata = session.metadata
        metadata.title = self.title_edit.text().strip()
        metadata.customer = self.customer_edit.text().strip()
        metadata.site = self.site_edit.text().strip()
        metadata.equipment = self.equipment_edit.text().strip()
        metadata.technician = self.technician_edit.text().strip()
        metadata.notes = self.notes_edit.toPlainText().strip()
        metadata.updated_at = _now_iso()
        self._refresh_summary_labels()

    def _refresh_session_view(self) -> None:
        self._refresh_summary_labels()
        self._populate_events_table()
        self._update_selected_event_details()

    def _refresh_summary_labels(self) -> None:
        summary = session_summary(self._ensure_session())
        for key, label in self.summary_labels.items():
            label.setText(str(summary[key]))

    def _populate_events_table(self) -> None:
        session = self._ensure_session()
        self.events_table.setRowCount(len(session.events))
        for row, event in enumerate(session.events):
            self.events_table.setItem(row, 0, QTableWidgetItem(event.timestamp))
            self.events_table.setItem(row, 1, QTableWidgetItem(event.source))
            self.events_table.setItem(row, 2, QTableWidgetItem(event.event_type))
            self.events_table.setItem(row, 3, QTableWidgetItem(event.severity))
            self.events_table.setItem(row, 4, QTableWidgetItem(event.summary))
        if session.events:
            self.events_table.selectRow(len(session.events) - 1)

    def _update_selected_event_details(self) -> None:
        event = self._selected_event()
        if event is None:
            self.event_details_output.setPlainText("Select a session event to inspect its details.")
            return
        detail_text = json.dumps(event.details, ensure_ascii=False, indent=2, sort_keys=True)
        if not detail_text or detail_text == "{}":
            detail_text = "{}"
        self.event_details_output.setPlainText(detail_text)

    def _selected_event(self) -> DiagnosticSessionEvent | None:
        session = self._app_state.current_session
        row = self.events_table.currentRow()
        if session is None or row < 0 or row >= len(session.events):
            return None
        return session.events[row]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _truncate_summary(text: str, limit: int = 80) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."
