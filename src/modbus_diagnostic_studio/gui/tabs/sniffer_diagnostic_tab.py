"""Passive sniffer diagnostic tab."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.models.communication_profile import CommunicationProfile
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.services.mode_manager import AppMode, ModeManager
from modbus_diagnostic_studio.sniffer.capture_writer import (
    write_events_csv,
    write_events_jsonl,
    write_exchanges_csv,
    write_exchanges_jsonl,
)
from modbus_diagnostic_studio.sniffer.communication_profiles import (
    list_builtin_communication_profiles,
    load_all_builtin_communication_profiles,
    load_builtin_communication_profile,
)
from modbus_diagnostic_studio.sniffer.passive_serial_sniffer import (
    PassiveSerialSniffer,
    PassiveSerialSnifferConfig,
    PassiveSnifferSnapshot,
)
from modbus_diagnostic_studio.sniffer.rtu_stream_framer import RtuFramerConfig
from modbus_diagnostic_studio.transports.serial_ports import list_serial_ports

SNIFFER_OWNER = "sniffer_diagnostic_tab"


@dataclass(frozen=True)
class SnifferStartRequest:
    """Settings for one passive sniffer session."""

    settings: SerialConnectionSettings
    communication_profiles: list[CommunicationProfile]


class SnifferWorker(QObject):
    """Background worker that polls a passive serial sniffer."""

    snapshot_ready = Signal(object)
    failed = Signal(str)
    stopped = Signal()

    def __init__(self, request: SnifferStartRequest) -> None:
        super().__init__()
        self.request = request
        self._timer: QTimer | None = None
        self._sniffer: PassiveSerialSniffer | None = None

    @Slot()
    def start(self) -> None:
        """Open sniffer and start periodic polling."""
        try:
            self._sniffer = PassiveSerialSniffer(
                PassiveSerialSnifferConfig(
                    connection=self.request.settings,
                    framer=RtuFramerConfig(baudrate=self.request.settings.baudrate),
                    matcher_timeout_ms=max(self.request.settings.timeout * 1000.0, 100.0),
                    read_size=256,
                ),
                communication_profiles=self.request.communication_profiles,
            )
            self._sniffer.open()
        except Exception as exc:
            self.failed.emit(str(exc))
            self.stopped.emit()
            return

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.poll_once)
        self._timer.start()

    @Slot()
    def poll_once(self) -> None:
        """Poll one passive serial chunk and publish the snapshot."""
        if self._sniffer is None:
            return
        try:
            snapshot = self._sniffer.poll_once()
        except Exception as exc:
            self._close_sniffer()
            self.failed.emit(str(exc))
            self.stopped.emit()
            return
        self.snapshot_ready.emit(snapshot)

    @Slot()
    def stop(self) -> None:
        """Stop polling and close the sniffer."""
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        self._close_sniffer()
        self.stopped.emit()

    def _close_sniffer(self) -> None:
        if self._sniffer is None:
            return
        try:
            self._sniffer.close()
        except Exception:
            pass
        self._sniffer = None


class SnifferDiagnosticTab(QWidget):
    """Passive serial sniffer UI."""

    stop_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: SnifferWorker | None = None
        self._running = False
        self._reserved_port: str | None = None
        self._last_snapshot: PassiveSnifferSnapshot | None = None
        # TODO: inject an application-wide ModeManager from ApplicationState.
        self._mode_manager = ModeManager()

        self.banner_label = QLabel("PASSIVE SNIFFER - DOES NOT TRANSMIT")
        banner_font = self.banner_label.font()
        banner_font.setPointSize(max(banner_font.pointSize() + 4, 14))
        banner_font.setBold(True)
        self.banner_label.setFont(banner_font)

        self.status_label = QLabel("Stopped. Passive mode reads only and never transmits.")

        self.port_combo = QComboBox()
        self.refresh_button = QPushButton("Refresh Ports")
        self.refresh_button.clicked.connect(self.refresh_ports)

        self.baudrate = QComboBox()
        self.baudrate.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate.setCurrentText("9600")

        self.parity = QComboBox()
        self.parity.addItems(["N", "E", "O"])

        self.stopbits = QComboBox()
        self.stopbits.addItems(["1", "2"])

        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(0.05, 5.0)
        self.timeout.setSingleStep(0.05)
        self.timeout.setValue(0.1)

        self.profile_combo = QComboBox()
        self.profile_combo.addItem("Auto / All built-ins", "__all__")
        for profile_id in list_builtin_communication_profiles():
            self.profile_combo.addItem(profile_id, profile_id)

        self.start_button = QPushButton("Start Passive Sniffer")
        self.start_button.clicked.connect(self.start_sniffer)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_sniffer)
        self.stop_button.setEnabled(False)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_view)

        self.export_events_csv_button = QPushButton("Export Events CSV")
        self.export_events_csv_button.clicked.connect(self.export_events_csv)
        self.export_events_jsonl_button = QPushButton("Export Events JSONL")
        self.export_events_jsonl_button.clicked.connect(self.export_events_jsonl)
        self.export_exchanges_csv_button = QPushButton("Export Exchanges CSV")
        self.export_exchanges_csv_button.clicked.connect(self.export_exchanges_csv)
        self.export_exchanges_jsonl_button = QPushButton("Export Exchanges JSONL")
        self.export_exchanges_jsonl_button.clicked.connect(self.export_exchanges_jsonl)

        self.frames_count_label = QLabel("0")
        self.crc_ok_label = QLabel("0")
        self.crc_errors_label = QLabel("0")
        self.requests_label = QLabel("0")
        self.responses_label = QLabel("0")
        self.exceptions_label = QLabel("0")
        self.timeouts_label = QLabel("0")
        self.unmatched_label = QLabel("0")
        self.slave_ids_label = QLabel("-")
        self.function_codes_label = QLabel("-")
        self.latency_min_label = QLabel("-")
        self.latency_max_label = QLabel("-")
        self.latency_avg_label = QLabel("-")

        self.frames_table = QTableWidget(0, 8)
        self.frames_table.setHorizontalHeaderLabels(
            [
                "Timestamp",
                "Classification",
                "Slave ID",
                "Function",
                "Address",
                "Quantity",
                "CRC OK",
                "Raw Hex",
            ]
        )
        self.frames_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.diagnosis_text = QTextEdit()
        self.diagnosis_text.setReadOnly(True)

        self.fingerprint_table = QTableWidget(0, 4)
        self.fingerprint_table.setHorizontalHeaderLabels(
            ["Profile ID", "Score", "Matched Items", "Missing Items"]
        )
        self.fingerprint_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._build_layout()
        self.refresh_ports()

    def _build_layout(self) -> None:
        form = QFormLayout()
        port_row = QHBoxLayout()
        port_row.addWidget(self.port_combo)
        port_row.addWidget(self.refresh_button)
        form.addRow("COM port", port_row)
        form.addRow("Baudrate", self.baudrate)
        form.addRow("Parity", self.parity)
        form.addRow("Stopbits", self.stopbits)
        form.addRow("Timeout seconds", self.timeout)
        form.addRow("Communication profile", self.profile_combo)

        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.clear_button)

        export_row = QHBoxLayout()
        export_row.addWidget(self.export_events_csv_button)
        export_row.addWidget(self.export_events_jsonl_button)
        export_row.addWidget(self.export_exchanges_csv_button)
        export_row.addWidget(self.export_exchanges_jsonl_button)

        stats = QGridLayout()
        stats.addWidget(QLabel("Frames"), 0, 0)
        stats.addWidget(self.frames_count_label, 0, 1)
        stats.addWidget(QLabel("CRC OK"), 0, 2)
        stats.addWidget(self.crc_ok_label, 0, 3)
        stats.addWidget(QLabel("CRC errors"), 0, 4)
        stats.addWidget(self.crc_errors_label, 0, 5)
        stats.addWidget(QLabel("Requests"), 1, 0)
        stats.addWidget(self.requests_label, 1, 1)
        stats.addWidget(QLabel("Responses"), 1, 2)
        stats.addWidget(self.responses_label, 1, 3)
        stats.addWidget(QLabel("Exceptions"), 1, 4)
        stats.addWidget(self.exceptions_label, 1, 5)
        stats.addWidget(QLabel("Timeouts"), 2, 0)
        stats.addWidget(self.timeouts_label, 2, 1)
        stats.addWidget(QLabel("Unmatched"), 2, 2)
        stats.addWidget(self.unmatched_label, 2, 3)
        stats.addWidget(QLabel("Slave IDs"), 2, 4)
        stats.addWidget(self.slave_ids_label, 2, 5)
        stats.addWidget(QLabel("Function codes"), 3, 0)
        stats.addWidget(self.function_codes_label, 3, 1)
        stats.addWidget(QLabel("Latency min"), 3, 2)
        stats.addWidget(self.latency_min_label, 3, 3)
        stats.addWidget(QLabel("Latency max"), 3, 4)
        stats.addWidget(self.latency_max_label, 3, 5)
        stats.addWidget(QLabel("Latency avg"), 4, 0)
        stats.addWidget(self.latency_avg_label, 4, 1)

        layout = QVBoxLayout()
        layout.addWidget(self.banner_label)
        layout.addWidget(self.status_label)
        layout.addLayout(form)
        layout.addLayout(button_row)
        layout.addLayout(export_row)
        layout.addLayout(stats)
        layout.addWidget(QLabel("Recent frames"))
        layout.addWidget(self.frames_table)
        layout.addWidget(QLabel("Preliminary diagnosis"))
        layout.addWidget(self.diagnosis_text)
        layout.addWidget(QLabel("Profile fingerprint ranking"))
        layout.addWidget(self.fingerprint_table)
        self.setLayout(layout)

    def refresh_ports(self) -> None:
        """Refresh available COM ports without opening them."""
        current = self.port_combo.currentData()
        self.port_combo.clear()
        for port in list_serial_ports():
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)
        if current is not None:
            index = self.port_combo.findData(current)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        self.status_label.setText(
            f"{self.port_combo.count()} port(s) detected. Passive sniffer does not transmit."
        )

    def start_sniffer(self) -> None:
        """Reserve port and start passive polling in a background thread."""
        if self._running:
            self._set_error("Passive sniffer is already running.")
            return

        port = self.port_combo.currentData()
        if not port:
            self._set_error("No COM selected.")
            return
        port = str(port)

        try:
            self._mode_manager.reserve(port, AppMode.SNIFFER_PASSIVE, SNIFFER_OWNER)
            self._reserved_port = port
        except RuntimeError as exc:
            self._set_error(str(exc))
            return

        try:
            settings = SerialConnectionSettings(
                port=port,
                baudrate=int(self.baudrate.currentText()),
                parity=self.parity.currentText(),
                stopbits=float(self.stopbits.currentText()),
                timeout=self.timeout.value(),
            )
        except ValueError as exc:
            self._release_reserved_port()
            self._set_error(f"Invalid settings: {exc}")
            return

        self.clear_view()
        self.status_label.setText("Starting passive sniffer...")
        self._set_running_state(True)

        request = SnifferStartRequest(
            settings=settings,
            communication_profiles=self._selected_profiles(),
        )

        self._thread = QThread(self)
        self._worker = SnifferWorker(request)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self.stop_requested.connect(self._worker.stop, Qt.QueuedConnection)
        self._worker.snapshot_ready.connect(self._handle_snapshot)
        self._worker.failed.connect(self._handle_error)
        self._worker.stopped.connect(self._handle_worker_stopped)
        self._worker.stopped.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    def stop_sniffer(self) -> None:
        """Stop passive capture and release the port."""
        if self._worker is None:
            self._finish_stop("Stopped.")
            return
        self.status_label.setText("Stopping passive sniffer...")
        self.stop_requested.emit()

    def clear_view(self) -> None:
        """Clear visible diagnostic data without starting any serial action."""
        self.frames_table.setRowCount(0)
        self.diagnosis_text.clear()
        self.fingerprint_table.setRowCount(0)
        self.frames_count_label.setText("0")
        self.crc_ok_label.setText("0")
        self.crc_errors_label.setText("0")
        self.requests_label.setText("0")
        self.responses_label.setText("0")
        self.exceptions_label.setText("0")
        self.timeouts_label.setText("0")
        self.unmatched_label.setText("0")
        self.slave_ids_label.setText("-")
        self.function_codes_label.setText("-")
        self.latency_min_label.setText("-")
        self.latency_max_label.setText("-")
        self.latency_avg_label.setText("-")

    @Slot(object)
    def _handle_snapshot(self, snapshot: PassiveSnifferSnapshot) -> None:
        self._last_snapshot = snapshot
        self.status_label.setText("Passive sniffer running. Read-only serial capture.")
        self._populate_stats(snapshot)
        self._populate_frames(snapshot)
        self._populate_diagnosis(snapshot)
        self._populate_fingerprint(snapshot)

    @Slot(str)
    def _handle_error(self, message: str) -> None:
        self._finish_stop(f"Error: {message}")

    @Slot()
    def _handle_worker_stopped(self) -> None:
        self._finish_stop("Stopped. Passive sniffer closed.")

    @Slot()
    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None

    def _finish_stop(self, status: str) -> None:
        self._set_running_state(False)
        self._release_reserved_port()
        self.status_label.setText(status)

    def _set_running_state(self, running: bool) -> None:
        self._running = running
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    def _set_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")

    def _release_reserved_port(self) -> None:
        if self._reserved_port is None:
            return
        self._mode_manager.release(self._reserved_port, SNIFFER_OWNER)
        self._reserved_port = None

    def _selected_profiles(self) -> list[CommunicationProfile]:
        profile_id = self.profile_combo.currentData()
        if profile_id == "__all__":
            return load_all_builtin_communication_profiles()
        return [load_builtin_communication_profile(str(profile_id))]

    # ── export ────────────────────────────────────────────────────────────

    def export_events_csv(self) -> None:
        """Export captured frame events to a CSV file."""
        events = self._last_snapshot.events if self._last_snapshot is not None else []
        if not events:
            self.status_label.setText("No events to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Events CSV", "sniffer_events.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            write_events_csv(path, events)
            self.status_label.setText(f"Events exported to: {path}")
        except Exception as exc:
            self.status_label.setText(f"Export error: {exc}")

    def export_events_jsonl(self) -> None:
        """Export captured frame events to a JSONL file."""
        events = self._last_snapshot.events if self._last_snapshot is not None else []
        if not events:
            self.status_label.setText("No events to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Events JSONL", "sniffer_events.jsonl", "JSONL files (*.jsonl)"
        )
        if not path:
            return
        try:
            write_events_jsonl(path, events)
            self.status_label.setText(f"Events exported to: {path}")
        except Exception as exc:
            self.status_label.setText(f"Export error: {exc}")

    def export_exchanges_csv(self) -> None:
        """Export matched exchanges to a CSV file."""
        exchanges = self._last_snapshot.exchanges if self._last_snapshot is not None else []
        if not exchanges:
            self.status_label.setText("No exchanges to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Exchanges CSV", "sniffer_exchanges.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            write_exchanges_csv(path, exchanges)
            self.status_label.setText(f"Exchanges exported to: {path}")
        except Exception as exc:
            self.status_label.setText(f"Export error: {exc}")

    def export_exchanges_jsonl(self) -> None:
        """Export matched exchanges to a JSONL file."""
        exchanges = self._last_snapshot.exchanges if self._last_snapshot is not None else []
        if not exchanges:
            self.status_label.setText("No exchanges to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Exchanges JSONL", "sniffer_exchanges.jsonl", "JSONL files (*.jsonl)"
        )
        if not path:
            return
        try:
            write_exchanges_jsonl(path, exchanges)
            self.status_label.setText(f"Exchanges exported to: {path}")
        except Exception as exc:
            self.status_label.setText(f"Export error: {exc}")

    def _populate_stats(self, snapshot: PassiveSnifferSnapshot) -> None:
        stats = snapshot.stats
        self.frames_count_label.setText(str(stats.total_frames))
        self.crc_ok_label.setText(str(stats.valid_crc_frames))
        self.crc_errors_label.setText(str(stats.invalid_crc_frames))
        self.requests_label.setText(str(stats.requests))
        self.responses_label.setText(str(stats.responses))
        self.exceptions_label.setText(str(stats.exceptions))
        self.timeouts_label.setText(str(stats.timeouts))
        self.unmatched_label.setText(str(stats.unmatched_responses))
        self.slave_ids_label.setText(
            ", ".join(str(item) for item in sorted(stats.slave_ids_seen)) or "-"
        )
        self.function_codes_label.setText(
            ", ".join(str(item) for item in sorted(stats.function_codes_seen)) or "-"
        )
        self.latency_min_label.setText(self._format_latency(stats.min_latency_ms))
        self.latency_max_label.setText(self._format_latency(stats.max_latency_ms))
        self.latency_avg_label.setText(self._format_latency(stats.avg_latency_ms))

    def _populate_frames(self, snapshot: PassiveSnifferSnapshot) -> None:
        events = snapshot.events[-100:]
        self.frames_table.setRowCount(len(events))
        for row, event in enumerate(events):
            self.frames_table.setItem(
                row, 0, QTableWidgetItem(f"{event.timestamp_monotonic:.3f}")
            )
            self.frames_table.setItem(row, 1, QTableWidgetItem(event.classification))
            self.frames_table.setItem(
                row, 2, QTableWidgetItem("" if event.slave_id is None else str(event.slave_id))
            )
            self.frames_table.setItem(
                row,
                3,
                QTableWidgetItem(
                    "" if event.function_code is None else str(event.function_code)
                ),
            )
            self.frames_table.setItem(
                row, 4, QTableWidgetItem("" if event.address is None else str(event.address))
            )
            self.frames_table.setItem(
                row, 5, QTableWidgetItem("" if event.quantity is None else str(event.quantity))
            )
            self.frames_table.setItem(row, 6, QTableWidgetItem("Yes" if event.crc_ok else "No"))
            self.frames_table.setItem(row, 7, QTableWidgetItem(event.raw_hex))

    def _populate_diagnosis(self, snapshot: PassiveSnifferSnapshot) -> None:
        if snapshot.diagnosis:
            self.diagnosis_text.setPlainText("\n".join(snapshot.diagnosis))
        else:
            self.diagnosis_text.setPlainText("No diagnosis yet.")

    def _populate_fingerprint(self, snapshot: PassiveSnifferSnapshot) -> None:
        scores = snapshot.fingerprint_scores[:10]
        self.fingerprint_table.setRowCount(len(scores))
        for row, score in enumerate(scores):
            self.fingerprint_table.setItem(row, 0, QTableWidgetItem(score.profile_id))
            self.fingerprint_table.setItem(row, 1, QTableWidgetItem(f"{score.score:.1f}"))
            self.fingerprint_table.setItem(
                row, 2, QTableWidgetItem("; ".join(score.matched_items))
            )
            self.fingerprint_table.setItem(
                row, 3, QTableWidgetItem("; ".join(score.missing_items))
            )

    @staticmethod
    def _format_latency(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value:.1f} ms"
