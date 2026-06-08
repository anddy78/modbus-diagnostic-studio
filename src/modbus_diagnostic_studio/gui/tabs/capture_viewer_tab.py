"""Offline capture viewer for passive sniffer exports."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.core.decoder import decode_raw_rtu_frame
from modbus_diagnostic_studio.gui.help import set_help
from modbus_diagnostic_studio.models.diagnostic_session import DiagnosticSessionEvent
from modbus_diagnostic_studio.services.ai_bundle import write_capture_ai_bundle
from modbus_diagnostic_studio.services.application_state import ApplicationState
from modbus_diagnostic_studio.services.paths import ensure_runtime_dirs, exports_dir
from modbus_diagnostic_studio.sniffer.capture_reader import CaptureReadResult, read_capture_file


class CaptureViewerTab(QWidget):
    """Open offline capture exports, decode selected frames, and reuse them in reports."""

    DISPLAY_FIELDS = [
        "raw_hex",
        "classification",
        "crc_ok",
        "slave_id",
        "function_code",
        "address",
        "quantity",
        "byte_count",
        "registers",
        "exception_code",
        "error",
    ]

    def __init__(self, app_state: ApplicationState | None = None) -> None:
        super().__init__()
        self._app_state = app_state or ApplicationState()
        self._capture_result = CaptureReadResult("", "unknown", [], [])
        self._decoded_cache: list[dict] = []
        self._loaded_path: Path | None = None

        self.status_label = QLabel(
            "Offline capture viewer for JSONL/CSV sniffer exports. No ports are opened."
        )
        self.file_path_label = QLabel("-")
        self.capture_type_label = QLabel("unknown")
        self.record_count_label = QLabel("0")
        self.warning_count_label = QLabel("0")

        self.open_button = QPushButton("Open Capture File")
        self.open_button.clicked.connect(self.open_capture_file)
        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(self.reload_capture)
        self.copy_raw_hex_button = QPushButton("Copy Raw Hex")
        self.copy_raw_hex_button.clicked.connect(self.copy_raw_hex)
        self.decode_button = QPushButton("Decode Selected Frame")
        self.decode_button.clicked.connect(self.decode_selected_frame)
        self.add_to_report_button = QPushButton("Add Selected Frame To Diagnostic Report")
        self.add_to_report_button.clicked.connect(self.add_selected_frame_to_report)
        self.export_ai_bundle_button = QPushButton("Export AI Bundle JSON")
        self.export_ai_bundle_button.clicked.connect(self.export_ai_bundle)

        self.frame_side_combo = QComboBox()
        self.frame_side_combo.addItems(["Auto", "Request", "Response"])

        self.records_table = QTableWidget(0, 9)
        self.records_table.setHorizontalHeaderLabels(
            [
                "#",
                "Type",
                "Timestamp",
                "Status",
                "Slave ID",
                "Function",
                "Address",
                "Quantity",
                "Raw Hex",
            ]
        )
        self.records_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.records_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.records_table.setMinimumHeight(240)
        self.records_table.itemSelectionChanged.connect(self._handle_selection_changed)

        self.selected_raw_hex_output = QTextEdit()
        self.selected_raw_hex_output.setReadOnly(True)
        self.selected_raw_hex_output.setMinimumHeight(90)

        self.decoded_labels: dict[str, QLabel] = {field: QLabel("") for field in self.DISPLAY_FIELDS}
        self.warnings_output = QTextEdit()
        self.warnings_output.setReadOnly(True)
        self.warnings_output.setMinimumHeight(110)

        self._build_layout()
        self._attach_help()

    def _build_layout(self) -> None:
        button_row = QHBoxLayout()
        button_row.addWidget(self.open_button)
        button_row.addWidget(self.reload_button)
        button_row.addWidget(self.copy_raw_hex_button)
        button_row.addWidget(self.decode_button)
        button_row.addWidget(self.add_to_report_button)
        button_row.addWidget(self.export_ai_bundle_button)

        info_form = QFormLayout()
        info_form.addRow("Loaded file", self.file_path_label)
        info_form.addRow("Capture type", self.capture_type_label)
        info_form.addRow("Frame side", self.frame_side_combo)
        info_form.addRow("Record count", self.record_count_label)
        info_form.addRow("Warnings", self.warning_count_label)

        decoded_form = QFormLayout()
        for field, label in self.decoded_labels.items():
            decoded_form.addRow(field, label)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.addWidget(self.status_label)
        content_layout.addLayout(button_row)
        content_layout.addLayout(info_form)
        content_layout.addWidget(QLabel("Capture records"))
        content_layout.addWidget(self.records_table)
        content_layout.addWidget(QLabel("Selected raw hex"))
        content_layout.addWidget(self.selected_raw_hex_output)
        content_layout.addWidget(QLabel("Decoded fields"))
        content_layout.addLayout(decoded_form)
        content_layout.addWidget(QLabel("Warnings"))
        content_layout.addWidget(self.warnings_output)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        layout = QVBoxLayout()
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _attach_help(self) -> None:
        set_help(
            self.open_button,
            "Open Capture File",
            "Open an offline JSONL or CSV passive capture export. This tab never opens serial ports.",
        )
        set_help(
            self.decode_button,
            "Decode Selected Frame",
            "Decode the selected raw RTU frame using the same offline decoder as the Raw Frame Decoder tab.",
        )
        set_help(
            self.export_ai_bundle_button,
            "Export AI Bundle JSON",
            "Create a local offline JSON bundle for later analysis. Review sensitive data before sharing.",
        )

    def open_capture_file(self) -> None:
        ensure_runtime_dirs()
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Capture File",
            str(Path.cwd()),
            "Capture files (*.jsonl *.csv);;All files (*.*)",
        )
        if not path_str:
            return
        self.load_capture_from_path(path_str)

    def load_capture_from_path(self, path: str | Path) -> None:
        self._loaded_path = Path(path)
        self._capture_result = read_capture_file(self._loaded_path)
        self._decoded_cache = [{} for _ in self._capture_result.records]
        self._refresh_view()
        self.status_label.setText(f"Loaded capture file: {self._loaded_path}")

    def reload_capture(self) -> None:
        if self._loaded_path is None:
            self.status_label.setText("Open a capture file first.")
            return
        self.load_capture_from_path(self._loaded_path)

    def copy_raw_hex(self) -> None:
        raw_hex = self._selected_raw_hex()
        if not raw_hex:
            self.status_label.setText("Select a capture record first.")
            return
        QApplication.clipboard().setText(raw_hex)
        self.status_label.setText("Selected raw hex copied to clipboard.")

    def decode_selected_frame(self) -> None:
        row = self.records_table.currentRow()
        raw_hex = self._selected_raw_hex()
        if row < 0 or not raw_hex:
            self.status_label.setText("Select a capture record with raw hex first.")
            return
        decoded = decode_raw_rtu_frame(raw_hex)
        self._decoded_cache[row] = decoded
        self._apply_decoded_fields(decoded)
        self.status_label.setText("Selected frame decoded offline.")

    def add_selected_frame_to_report(self) -> None:
        row = self.records_table.currentRow()
        if row < 0:
            self.status_label.setText("Select a capture record first.")
            return
        if self._app_state.current_session is None:
            self.status_label.setText("No active diagnostic session.")
            return
        decoded = self._decoded_cache[row] or decode_raw_rtu_frame(self._selected_raw_hex())
        self._decoded_cache[row] = decoded
        severity = "warning" if (not decoded.get("crc_ok", False) or decoded.get("error")) else "info"
        summary = (
            f"Decoded frame slave={decoded.get('slave_id')} "
            f"fc={decoded.get('function_code')} addr={decoded.get('address')}"
        )
        event = DiagnosticSessionEvent(
            timestamp=_now_iso(),
            source="capture_viewer",
            event_type="frame_decoded",
            severity=severity,
            summary=summary,
            details={
                "capture_path": str(self._loaded_path or ""),
                "raw_hex": self._selected_raw_hex(),
                "decoded_json": json.dumps(decoded, ensure_ascii=False, sort_keys=True),
            },
        )
        self._app_state.add_session_event(event)
        self.status_label.setText("Selected frame added to Diagnostic Report.")

    def export_ai_bundle(self) -> None:
        if not self._capture_result.records:
            self.status_label.setText("Open a capture file first.")
            return
        ensure_runtime_dirs()
        default_path = exports_dir() / "capture_ai_bundle.json"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export AI Bundle JSON",
            str(default_path),
            "JSON files (*.json)",
        )
        if not path_str:
            return
        self.export_ai_bundle_to_path(path_str)

    def export_ai_bundle_to_path(self, path: str | Path) -> None:
        decoded_records = [decoded or decode_raw_rtu_frame(self._raw_hex_for_record(record)) for decoded, record in zip(self._decoded_cache, self._capture_result.records)]
        self._decoded_cache = decoded_records
        write_capture_ai_bundle(path, self._capture_result, decoded_records)
        self.status_label.setText(f"AI bundle exported to: {path}")

    def _refresh_view(self) -> None:
        self.file_path_label.setText(str(self._loaded_path or "-"))
        self.capture_type_label.setText(self._capture_result.capture_type)
        self.record_count_label.setText(str(len(self._capture_result.records)))
        self.warning_count_label.setText(str(len(self._capture_result.warnings)))
        self.warnings_output.setPlainText(
            "\n".join(self._capture_result.warnings) or "No warnings."
        )
        self.records_table.setRowCount(len(self._capture_result.records))
        for row, record in enumerate(self._capture_result.records):
            raw_hex = self._raw_hex_for_record(record)
            self.records_table.setItem(row, 0, QTableWidgetItem(str(row)))
            self.records_table.setItem(
                row,
                1,
                QTableWidgetItem(str(record.get("record_type") or record.get("status") or "record")),
            )
            self.records_table.setItem(
                row,
                2,
                QTableWidgetItem(str(record.get("timestamp_iso") or record.get("timestamp_monotonic") or "")),
            )
            self.records_table.setItem(
                row,
                3,
                QTableWidgetItem(str(record.get("classification") or record.get("status") or "")),
            )
            self.records_table.setItem(
                row,
                4,
                QTableWidgetItem(_display_value(record, "slave_id", "request_slave_id")),
            )
            self.records_table.setItem(
                row,
                5,
                QTableWidgetItem(_display_value(record, "function_code", "request_function_code")),
            )
            self.records_table.setItem(
                row,
                6,
                QTableWidgetItem(_display_value(record, "address", "request_address")),
            )
            self.records_table.setItem(
                row,
                7,
                QTableWidgetItem(_display_value(record, "quantity", "request_quantity")),
            )
            self.records_table.setItem(row, 8, QTableWidgetItem(raw_hex[:48]))
        if self._capture_result.records:
            self.records_table.selectRow(0)
        else:
            self.selected_raw_hex_output.clear()
            self._apply_decoded_fields({})

    def _handle_selection_changed(self) -> None:
        self.selected_raw_hex_output.setPlainText(self._selected_raw_hex())

    def _selected_raw_hex(self) -> str:
        row = self.records_table.currentRow()
        if row < 0 or row >= len(self._capture_result.records):
            return ""
        return self._raw_hex_for_record(self._capture_result.records[row])

    def _raw_hex_for_record(self, record: dict) -> str:
        side = self.frame_side_combo.currentText()
        if side == "Request" and record.get("request_raw_hex"):
            return str(record.get("request_raw_hex"))
        if side == "Response" and record.get("response_raw_hex"):
            return str(record.get("response_raw_hex"))
        return str(
            record.get("raw_hex")
            or record.get("request_raw_hex")
            or record.get("response_raw_hex")
            or ""
        )

    def _apply_decoded_fields(self, decoded: dict) -> None:
        for field, label in self.decoded_labels.items():
            value = decoded.get(field, "")
            if isinstance(value, list):
                label.setText(", ".join(str(item) for item in value))
            else:
                label.setText(str(value))


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _display_value(record: dict, *keys: str) -> str:
    for key in keys:
        if key in record and record.get(key) is not None:
            return str(record.get(key))
    return ""
