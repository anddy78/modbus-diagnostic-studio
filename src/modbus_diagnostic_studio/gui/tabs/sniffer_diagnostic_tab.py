"""Passive sniffer diagnostic tab."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.gui.help import set_help
from modbus_diagnostic_studio.models.communication_profile import CommunicationProfile
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.services.application_state import ApplicationState
from modbus_diagnostic_studio.services.mode_manager import AppMode
from modbus_diagnostic_studio.services.paths import captures_dir, ensure_runtime_dirs
from modbus_diagnostic_studio.sniffer.capture_recorder import (
    ContinuousCaptureRecorder,
    ContinuousCaptureRecorderConfig,
)
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
VISIBLE_FRAME_LIMIT = 100


@dataclass(frozen=True)
class SnifferStartRequest:
    """Settings for one passive sniffer session."""

    settings: SerialConnectionSettings
    communication_profiles: list[CommunicationProfile]
    poll_interval_ms: int = 100
    ui_update_interval_ms: int = 500
    fingerprint_interval_seconds: float = 1.0


@dataclass(frozen=True)
class SnifferWorkerMetrics:
    """Worker-side performance counters for passive sniffing."""

    polls_count: int
    snapshots_emitted: int
    serial_errors_count: int


class SnifferWorker(QObject):
    """Background worker that polls a passive serial sniffer."""

    snapshot_ready = Signal(object, object)
    failed = Signal(str)
    stopped = Signal()

    def __init__(self, request: SnifferStartRequest) -> None:
        super().__init__()
        self.request = request
        self._timer: QTimer | None = None
        self._sniffer: PassiveSerialSniffer | None = None
        self.polls_count = 0
        self.snapshots_emitted = 0
        self.serial_errors_count = 0
        self.last_publish_monotonic = 0.0

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
                    fingerprint_interval_seconds=self.request.fingerprint_interval_seconds,
                    diagnosis_interval_seconds=self.request.fingerprint_interval_seconds,
                ),
                communication_profiles=self.request.communication_profiles,
            )
            self._sniffer.open()
        except Exception as exc:
            self.failed.emit(str(exc))
            self.stopped.emit()
            return

        self.last_publish_monotonic = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(self.request.poll_interval_ms)
        self._timer.timeout.connect(self.poll_once)
        self._timer.start()

    @Slot()
    def poll_once(self) -> None:
        """Poll one passive serial chunk and publish only on the configured cadence."""
        if self._sniffer is None:
            return
        self.polls_count += 1
        now = time.monotonic()
        try:
            self._sniffer.poll_once(timestamp_monotonic=now)
        except Exception as exc:
            self.serial_errors_count += 1
            self._emit_snapshot_if_available(force_recompute=True)
            self._close_sniffer()
            self.failed.emit(str(exc))
            self.stopped.emit()
            return

        if (
            self.snapshots_emitted == 0
            or (now - self.last_publish_monotonic) * 1000.0 >= self.request.ui_update_interval_ms
        ):
            self._emit_snapshot_if_available(force_recompute=False)
            self.last_publish_monotonic = now

    @Slot()
    def stop(self) -> None:
        """Stop polling and close the sniffer."""
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        self._emit_snapshot_if_available(force_recompute=True)
        self._close_sniffer()
        self.stopped.emit()

    def _emit_snapshot_if_available(self, *, force_recompute: bool) -> None:
        if self._sniffer is None:
            return
        snapshot = self._sniffer.snapshot(force_recompute=force_recompute)
        self.snapshots_emitted += 1
        self.snapshot_ready.emit(snapshot, self._metrics())

    def _metrics(self) -> SnifferWorkerMetrics:
        return SnifferWorkerMetrics(
            polls_count=self.polls_count,
            snapshots_emitted=self.snapshots_emitted,
            serial_errors_count=self.serial_errors_count,
        )

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

    def __init__(self, app_state: ApplicationState | None = None) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: SnifferWorker | None = None
        self._running = False
        self._display_paused = False
        self._reserved_port: str | None = None
        self._last_snapshot: PassiveSnifferSnapshot | None = None
        self._last_metrics = SnifferWorkerMetrics(0, 0, 0)
        self._app_state = app_state or ApplicationState()
        self._mode_manager = self._app_state.mode_manager
        self._recorder: ContinuousCaptureRecorder | None = None

        self.banner_label = QLabel("PASSIVE SNIFFER - DOES NOT TRANSMIT")
        banner_font = self.banner_label.font()
        banner_font.setPointSize(max(banner_font.pointSize() + 4, 14))
        banner_font.setBold(True)
        self.banner_label.setFont(banner_font)

        self.status_label = QLabel("Stopped. Passive sniffer closed.")

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

        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(20, 1000)
        self.poll_interval_spin.setValue(100)
        self.poll_interval_spin.setSuffix(" ms")

        self.ui_update_interval_spin = QSpinBox()
        self.ui_update_interval_spin.setRange(100, 5000)
        self.ui_update_interval_spin.setValue(500)
        self.ui_update_interval_spin.setSuffix(" ms")

        self.fingerprint_interval_spin = QDoubleSpinBox()
        self.fingerprint_interval_spin.setRange(0.5, 10.0)
        self.fingerprint_interval_spin.setSingleStep(0.5)
        self.fingerprint_interval_spin.setValue(1.0)
        self.fingerprint_interval_spin.setSuffix(" s")

        self.profile_combo = QComboBox()
        self.profile_combo.addItem("Auto / All built-ins", "__all__")
        for profile_id in list_builtin_communication_profiles():
            self.profile_combo.addItem(profile_id, profile_id)

        ensure_runtime_dirs()
        self.record_to_file_checkbox = QCheckBox("Record to file")
        self.record_to_file_checkbox.stateChanged.connect(self._handle_record_toggle_changed)
        self.output_folder_edit = QLineEdit(str(captures_dir()))
        self.browse_output_folder_button = QPushButton("Browse")
        self.browse_output_folder_button.clicked.connect(self.browse_output_folder)
        self.open_captures_folder_button = QPushButton("Open Captures Folder")
        self.open_captures_folder_button.clicked.connect(self.open_captures_folder)
        self.base_name_edit = QLineEdit("modbus_capture")
        self.recording_label = QLabel("No")
        self.records_written_label = QLabel("0")
        self.capture_files_label = QLabel("-")

        self.start_button = QPushButton("Start Passive Sniffer")
        self.start_button.clicked.connect(self.start_sniffer)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_sniffer)
        self.stop_button.setEnabled(False)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_view)
        self.pause_display_button = QPushButton("Pause Display")
        self.pause_display_button.clicked.connect(self.pause_display)
        self.pause_display_button.setEnabled(False)
        self.resume_display_button = QPushButton("Resume Display")
        self.resume_display_button.clicked.connect(self.resume_display)
        self.resume_display_button.setEnabled(False)
        self.refresh_snapshot_button = QPushButton("Refresh Snapshot Now")
        self.refresh_snapshot_button.clicked.connect(self.refresh_snapshot_now)
        self.refresh_snapshot_button.setEnabled(False)

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
        self.polls_label = QLabel("0")
        self.ui_updates_label = QLabel("0")
        self.display_paused_label = QLabel("No")
        self.serial_errors_label = QLabel("0")

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
        self.frames_table.setMinimumHeight(240)

        self.diagnosis_text = QTextEdit()
        self.diagnosis_text.setReadOnly(True)
        self.diagnosis_text.setMinimumHeight(160)

        self.fingerprint_table = QTableWidget(0, 4)
        self.fingerprint_table.setHorizontalHeaderLabels(
            ["Profile ID", "Score", "Matched Items", "Missing Items"]
        )
        self.fingerprint_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.fingerprint_table.setMinimumHeight(180)

        self._build_layout()
        self._attach_help()
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
        form.addRow("Poll interval", self.poll_interval_spin)
        form.addRow("UI update interval", self.ui_update_interval_spin)
        form.addRow("Fingerprint interval", self.fingerprint_interval_spin)
        form.addRow("Communication profile", self.profile_combo)
        form.addRow("Record to file", self.record_to_file_checkbox)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_folder_edit)
        output_row.addWidget(self.browse_output_folder_button)
        output_row.addWidget(self.open_captures_folder_button)
        form.addRow("Output folder", output_row)
        form.addRow("Base name", self.base_name_edit)

        button_row = QHBoxLayout()
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.clear_button)
        button_row.addWidget(self.pause_display_button)
        button_row.addWidget(self.resume_display_button)
        button_row.addWidget(self.refresh_snapshot_button)

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
        stats.addWidget(QLabel("Polls"), 4, 2)
        stats.addWidget(self.polls_label, 4, 3)
        stats.addWidget(QLabel("UI updates"), 4, 4)
        stats.addWidget(self.ui_updates_label, 4, 5)
        stats.addWidget(QLabel("Display paused"), 5, 0)
        stats.addWidget(self.display_paused_label, 5, 1)
        stats.addWidget(QLabel("Serial errors"), 5, 2)
        stats.addWidget(self.serial_errors_label, 5, 3)
        stats.addWidget(QLabel("Recording"), 6, 0)
        stats.addWidget(self.recording_label, 6, 1)
        stats.addWidget(QLabel("Records written"), 6, 2)
        stats.addWidget(self.records_written_label, 6, 3)
        stats.addWidget(QLabel("Capture files"), 7, 0)
        stats.addWidget(self.capture_files_label, 7, 1, 1, 5)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.addWidget(self.banner_label)
        content_layout.addWidget(self.status_label)
        content_layout.addLayout(form)
        content_layout.addLayout(button_row)
        content_layout.addLayout(export_row)
        content_layout.addLayout(stats)
        content_layout.addWidget(QLabel("Recent frames"))
        content_layout.addWidget(self.frames_table)
        content_layout.addWidget(QLabel("Preliminary diagnosis"))
        content_layout.addWidget(self.diagnosis_text)
        content_layout.addWidget(QLabel("Profile fingerprint ranking"))
        content_layout.addWidget(self.fingerprint_table)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        layout = QVBoxLayout()
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _attach_help(self) -> None:
        set_help(
            self.banner_label,
            "Passive Sniffer",
            "Passive Sniffer reads serial traffic only. It does not send Modbus requests and must never transmit.",
        )
        set_help(
            self.profile_combo,
            "Communication profile",
            "Use Auto to compare against all built-in fingerprints, or select one profile to narrow the ranking.",
        )
        set_help(
            self.start_button,
            "Start Passive Sniffer",
            "Reserve the selected COM port in passive mode and begin read-only capture.",
        )
        set_help(
            self.poll_interval_spin,
            "Poll interval",
            "How often the passive worker polls the serial adapter for new bytes.",
        )
        set_help(
            self.ui_update_interval_spin,
            "UI update interval",
            "How often the worker publishes snapshots to the GUI while capture continues.",
        )
        set_help(
            self.fingerprint_interval_spin,
            "Fingerprint interval",
            "Minimum interval between fingerprint and diagnosis recomputation inside the sniffer snapshot cache.",
        )
        set_help(
            self.pause_display_button,
            "Pause Display",
            "Pause GUI table and diagnosis refresh while passive capture continues in the background.",
        )
        set_help(
            self.record_to_file_checkbox,
            "Record to file",
            "Continuously write new passive capture events and exchanges to JSONL files while the sniffer runs.",
        )
        set_help(
            self.output_folder_edit,
            "Output folder",
            "Writable folder for continuous capture files. Loading or viewing capture files never opens ports or transmits.",
        )
        set_help(
            self.base_name_edit,
            "Base name",
            "Safe base name prefix used for capture files such as modbus_capture_events.jsonl.",
        )

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
        self._display_paused = False
        self._update_display_paused_label()
        self._set_running_state(True)
        self._close_recorder()
        if self.record_to_file_checkbox.isChecked():
            try:
                self._start_recorder(settings)
            except Exception as exc:
                self._set_running_state(False)
                self._release_reserved_port()
                self._set_error(f"Recorder error: {exc}")
                return
        self.status_label.setText(
            f"Starting passive sniffer... Read-only mode. UI updates every {self.ui_update_interval_spin.value()} ms."
        )

        request = SnifferStartRequest(
            settings=settings,
            communication_profiles=self._selected_profiles(),
            poll_interval_ms=self.poll_interval_spin.value(),
            ui_update_interval_ms=self.ui_update_interval_spin.value(),
            fingerprint_interval_seconds=self.fingerprint_interval_spin.value(),
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
            self._finish_stop(self._stopped_status())
            return
        self.status_label.setText("Stopping passive sniffer...")
        self.stop_requested.emit()

    def pause_display(self) -> None:
        """Pause visual updates while capture continues."""
        if not self._running:
            return
        self._display_paused = True
        self._update_display_paused_label()
        status = "Display paused; capture still running."
        if self._recorder is not None:
            status += " Recording continues."
        else:
            status += " Export uses latest captured snapshot."
        self.status_label.setText(status)

    def resume_display(self) -> None:
        """Resume visual updates using the latest captured snapshot."""
        if not self._running:
            return
        self._display_paused = False
        self._update_display_paused_label()
        if self._last_snapshot is not None:
            self._apply_snapshot_to_view(self._last_snapshot)
        self.status_label.setText(
            f"Passive sniffer running. Capture active. UI updates every {self.ui_update_interval_spin.value()} ms."
        )

    def refresh_snapshot_now(self) -> None:
        """Apply the latest cached snapshot to the visible view immediately."""
        if self._last_snapshot is None:
            return
        self._populate_stats(self._last_snapshot)
        self._populate_frames(self._last_snapshot)
        self._populate_diagnosis(self._last_snapshot)
        self._populate_fingerprint(self._last_snapshot)
        self.status_label.setText(
            f"Passive sniffer running. Capture active. UI updates every {self.ui_update_interval_spin.value()} ms."
        )

    def clear_view(self) -> None:
        """Clear visible diagnostic data without starting any serial action."""
        self._last_snapshot = None
        self._last_metrics = SnifferWorkerMetrics(0, 0, 0)
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
        self.polls_label.setText("0")
        self.ui_updates_label.setText("0")
        self.serial_errors_label.setText("0")
        self.display_paused_label.setText("No")
        self.records_written_label.setText("0")
        self.recording_label.setText("No" if self._recorder is None else "Yes")
        self.capture_files_label.setText("-")

    @Slot(object, object)
    def _handle_snapshot(
        self,
        snapshot: PassiveSnifferSnapshot,
        metrics: SnifferWorkerMetrics,
    ) -> None:
        self._last_snapshot = snapshot
        self._last_metrics = metrics
        self._update_metrics(metrics)
        self._write_snapshot_to_recorder(snapshot)
        if self._display_paused:
            status = "Display paused; capture still running."
            if self._recorder is not None:
                status += " Recording continues."
            else:
                status += " Export uses latest captured snapshot."
            self.status_label.setText(status)
            return
        self._apply_snapshot_to_view(snapshot)
        self.status_label.setText(
            f"Passive sniffer running. Capture active. UI updates every {self.ui_update_interval_spin.value()} ms."
        )

    @Slot(str)
    def _handle_error(self, message: str) -> None:
        self._finish_stop(f"Error: {message}")

    @Slot()
    def _handle_worker_stopped(self) -> None:
        if self._last_snapshot is not None and not self._display_paused:
            self._apply_snapshot_to_view(self._last_snapshot)
        self._finish_stop(self._stopped_status())

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
        self._display_paused = False
        self._update_display_paused_label()
        self._release_reserved_port()
        self._close_recorder()
        self.status_label.setText(status)

    def _set_running_state(self, running: bool) -> None:
        self._running = running
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.pause_display_button.setEnabled(running and not self._display_paused)
        self.resume_display_button.setEnabled(running and self._display_paused)
        self.refresh_snapshot_button.setEnabled(running)

    def _update_display_paused_label(self) -> None:
        self.display_paused_label.setText("Yes" if self._display_paused else "No")
        self.pause_display_button.setEnabled(self._running and not self._display_paused)
        self.resume_display_button.setEnabled(self._running and self._display_paused)

    def _update_metrics(self, metrics: SnifferWorkerMetrics) -> None:
        self.polls_label.setText(str(metrics.polls_count))
        self.ui_updates_label.setText(str(metrics.snapshots_emitted))
        self.serial_errors_label.setText(str(metrics.serial_errors_count))
        self._update_display_paused_label()

    def _set_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")

    def browse_output_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Capture Output Folder",
            self.output_folder_edit.text().strip() or str(captures_dir()),
        )
        if path:
            self.output_folder_edit.setText(path)

    def open_captures_folder(self) -> None:
        ensure_runtime_dirs()
        folder = Path(self.output_folder_edit.text().strip() or str(captures_dir()))
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(folder))
            self.status_label.setText(f"Opened captures folder: {folder}")
        except OSError as exc:
            self.status_label.setText(f"Unable to open captures folder: {exc}")

    def _handle_record_toggle_changed(self) -> None:
        if self._running:
            self.record_to_file_checkbox.blockSignals(True)
            self.record_to_file_checkbox.setChecked(self._recorder is not None)
            self.record_to_file_checkbox.blockSignals(False)
            self.status_label.setText("Change recording before starting capture.")
            return
        self.recording_label.setText("Yes" if self.record_to_file_checkbox.isChecked() else "No")

    def _start_recorder(self, settings: SerialConnectionSettings) -> None:
        self._recorder = self._create_recorder(settings)
        self._recorder.start(self._build_recorder_metadata(settings))
        self._sync_recorder_labels()

    def _create_recorder(self, settings: SerialConnectionSettings) -> ContinuousCaptureRecorder:
        del settings
        return ContinuousCaptureRecorder(
            ContinuousCaptureRecorderConfig(
                output_dir=Path(self.output_folder_edit.text().strip() or str(captures_dir())),
                base_name=self.base_name_edit.text().strip() or "modbus_capture",
            )
        )

    def _build_recorder_metadata(self, settings: SerialConnectionSettings) -> dict[str, object]:
        profile_id = self.profile_combo.currentData()
        return {
            "app_version": "0.1.0-beta",
            "port": settings.port,
            "baudrate": settings.baudrate,
            "parity": settings.parity,
            "stopbits": settings.stopbits,
            "bytesize": settings.bytesize,
            "profile_id": "" if profile_id == "__all__" else str(profile_id or ""),
        }

    def _write_snapshot_to_recorder(self, snapshot: PassiveSnifferSnapshot) -> None:
        if self._recorder is None:
            return
        try:
            self._recorder.write_snapshot_delta(snapshot)
            self._sync_recorder_labels()
        except Exception as exc:
            self._close_recorder()
            self.status_label.setText(f"Recorder error: {exc}")

    def _sync_recorder_labels(self) -> None:
        if self._recorder is None:
            self.recording_label.setText("No")
            self.records_written_label.setText("0")
            self.capture_files_label.setText("-")
            return
        self.recording_label.setText("Yes")
        self.records_written_label.setText(str(self._recorder.records_written))
        files = []
        if self._recorder.events_path is not None:
            files.append(self._recorder.events_path.name)
        if self._recorder.exchanges_path is not None:
            files.append(self._recorder.exchanges_path.name)
        self.capture_files_label.setText(", ".join(files) or "-")

    def _close_recorder(self) -> None:
        if self._recorder is None:
            self._sync_recorder_labels()
            return
        try:
            self._recorder.close()
        finally:
            self._recorder = None
            self._sync_recorder_labels()

    def _stopped_status(self) -> str:
        if self._recorder is not None:
            paths = []
            if self._recorder.events_path is not None:
                paths.append(str(self._recorder.events_path))
            if self._recorder.exchanges_path is not None:
                paths.append(str(self._recorder.exchanges_path))
            if paths:
                return f"Stopped. Capture saved to: {' | '.join(paths)}"
        return "Stopped. Passive sniffer closed."

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

    def _apply_snapshot_to_view(self, snapshot: PassiveSnifferSnapshot) -> None:
        self._populate_stats(snapshot)
        self._populate_frames(snapshot)
        self._populate_diagnosis(snapshot)
        self._populate_fingerprint(snapshot)

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
        events = snapshot.events[-VISIBLE_FRAME_LIMIT:]
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
