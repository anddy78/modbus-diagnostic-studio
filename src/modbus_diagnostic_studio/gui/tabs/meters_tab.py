"""Meters tab — friendly meter-centric active Modbus read."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.gui.help import set_help
from modbus_diagnostic_studio.master.client import ModbusMasterClient
from modbus_diagnostic_studio.master.profile_reader import (
    ProfileReadResult,
    read_profile,
)
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.profiles.decoder import DecodedProfileValue
from modbus_diagnostic_studio.profiles.loader import (
    list_builtin_profiles,
    load_builtin_profile,
)
from modbus_diagnostic_studio.services.application_state import ApplicationState
from modbus_diagnostic_studio.services.mode_manager import AppMode, ModeManager
from modbus_diagnostic_studio.transports.rtu_transport import RtuTransport
from modbus_diagnostic_studio.transports.serial_ports import list_serial_ports

METERS_TAB_OWNER = "meters_tab"

_CONTINUOUS_INTERVAL_MS = 2000


def _classify_variable(variable: str) -> str:
    """Return the electrical group name for a variable by keyword matching."""
    name = variable.lower()
    if "voltage" in name:
        return "Voltage"
    if "current" in name:
        return "Current"
    if any(k in name for k in ("power", "reactive", "apparent", "pf", "factor")):
        return "Power"
    if any(k in name for k in ("energy", "kwh", "kvarh")):
        return "Energy"
    return "Other"


class MeterReadWorker(QObject):
    """Worker that opens a transport, reads a full profile, then closes."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        settings: SerialConnectionSettings,
        slave_id: int,
        profile_id: str,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._slave_id = slave_id
        self._profile_id = profile_id

    @Slot()
    def run(self) -> None:
        transport = RtuTransport(self._settings)
        try:
            transport.open()
            profile = load_builtin_profile(self._profile_id)
            client = ModbusMasterClient(transport)
            result = read_profile(client, self._slave_id, profile)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(_friendly_serial_error(str(exc)))
        finally:
            try:
                transport.close()
            except Exception:
                pass


class MetersTab(QWidget):
    """Friendly meter read tab — select meter model, read electrical values."""

    def __init__(self, app_state: ApplicationState | None = None) -> None:
        super().__init__()

        self._app_state = app_state or ApplicationState()
        self._mode_manager = self._app_state.mode_manager
        self._reserved_port: str | None = None
        self._thread: QThread | None = None
        self._worker: MeterReadWorker | None = None
        self._continuous_timer: QTimer | None = None
        self._cycle_count: int = 0
        self._reading_busy: bool = False

        # ── status ──────────────────────────────────────────────────────
        self.status_label = QLabel("Select a meter model and press Read Once or Start Continuous Read.")

        # ── connection form ──────────────────────────────────────────────
        self.port_combo = QComboBox()
        self.refresh_button = QPushButton("Refresh Ports")
        self.refresh_button.clicked.connect(self.refresh_ports)

        self.baudrate = QSpinBox()
        self.baudrate.setRange(1, 1_000_000)
        self.baudrate.setValue(9600)

        self.parity = QComboBox()
        self.parity.addItems(["N", "E", "O"])

        self.stopbits = QComboBox()
        self.stopbits.addItems(["1", "2"])

        self.timeout = QDoubleSpinBox()
        self.timeout.setRange(0.1, 60.0)
        self.timeout.setSingleStep(0.1)
        self.timeout.setValue(1.0)

        self.slave_id = QSpinBox()
        self.slave_id.setRange(1, 247)
        self.slave_id.setValue(1)

        self.profile_combo = QComboBox()
        for pid in list_builtin_profiles():
            self.profile_combo.addItem(pid, pid)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 300)
        self.interval_spin.setValue(2)
        self.interval_spin.setSuffix(" s")

        # ── action buttons ───────────────────────────────────────────────
        self.read_once_button = QPushButton("Read Once")
        self.read_once_button.clicked.connect(self._read_once)

        self.start_button = QPushButton("Start Continuous Read")
        self.start_button.clicked.connect(self._start_continuous)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self._stop)
        self.stop_button.setEnabled(False)

        # ── values table ─────────────────────────────────────────────────
        self.values_table = QTableWidget(0, 6)
        self.values_table.setHorizontalHeaderLabels(
            ["Group", "Variable", "Value", "Unit", "Address", "Description"]
        )
        self.values_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.values_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.values_table.setMinimumHeight(260)

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
        form.addRow("Timeout (s)", self.timeout)
        form.addRow("Slave ID", self.slave_id)
        form.addRow("Meter profile", self.profile_combo)
        form.addRow("Interval (continuous)", self.interval_spin)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.read_once_button)
        btn_row.addWidget(self.start_button)
        btn_row.addWidget(self.stop_button)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.addWidget(self.status_label)
        content_layout.addLayout(form)
        content_layout.addLayout(btn_row)
        content_layout.addWidget(QLabel("Electrical values"))
        content_layout.addWidget(self.values_table)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        layout = QVBoxLayout()
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _attach_help(self) -> None:
        set_help(
            self.profile_combo,
            "Meter profile",
            "Select the built-in meter profile that describes the register map to read.",
        )
        set_help(
            self.read_once_button,
            "Read Once",
            "Perform one active Modbus read cycle using the selected meter profile.",
        )
        set_help(
            self.start_button,
            "Continuous Read",
            "Start repeated active reads at the selected interval. The COM port is reserved while running.",
        )

    # ── port management ──────────────────────────────────────────────────

    def refresh_ports(self) -> None:
        """Refresh available serial ports without opening them."""
        current = self.port_combo.currentData()
        self.port_combo.clear()
        for port in list_serial_ports():
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)
        if current is not None:
            index = self.port_combo.findData(current)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        self.status_label.setText(
            f"{self.port_combo.count()} port(s) detected."
        )

    # ── read once ────────────────────────────────────────────────────────

    def _read_once(self) -> None:
        """Perform one full profile read then release the port."""
        if self._reading_busy:
            return
        settings = self._build_settings()
        if settings is None:
            return
        self._start_worker(settings)

    # ── continuous read ──────────────────────────────────────────────────

    def _start_continuous(self) -> None:
        """Start periodic profile reads using a QTimer."""
        if self._reading_busy:
            return
        if self.port_combo.currentData() is None:
            self._set_status("Error: no COM port selected.")
            return

        self._cycle_count = 0
        self.start_button.setEnabled(False)
        self.read_once_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.interval_spin.setEnabled(False)

        self._continuous_timer = QTimer(self)
        self._continuous_timer.setInterval(self.interval_spin.value() * 1000)
        self._continuous_timer.timeout.connect(self._continuous_tick)
        self._set_status("Continuous read started.")
        self._continuous_tick()
        self._continuous_timer.start()

    def _continuous_tick(self) -> None:
        """Fire one read cycle if not already busy."""
        if self._reading_busy:
            return
        settings = self._build_settings()
        if settings is None:
            self._stop()
            return
        self._start_worker(settings)

    def _stop(self) -> None:
        """Stop continuous read and release any reserved port."""
        if self._continuous_timer is not None:
            self._continuous_timer.stop()
            self._continuous_timer.deleteLater()
            self._continuous_timer = None

        self._release_port()
        self.start_button.setEnabled(True)
        self.read_once_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.interval_spin.setEnabled(True)
        if not self._reading_busy:
            self._set_status("Stopped.")

    # ── worker lifecycle ─────────────────────────────────────────────────

    def _build_settings(self) -> SerialConnectionSettings | None:
        port = self.port_combo.currentData()
        if not port:
            self._set_status("Error: no COM port selected.")
            return None
        if not self.profile_combo.currentData():
            self._set_status("Error: no meter profile selected.")
            return None
        try:
            return SerialConnectionSettings(
                port=str(port),
                baudrate=self.baudrate.value(),
                parity=self.parity.currentText(),
                stopbits=float(self.stopbits.currentText()),
                timeout=self.timeout.value(),
            )
        except ValueError as exc:
            self._set_status(f"Error: invalid settings — {exc}")
            return None

    def _start_worker(self, settings: SerialConnectionSettings) -> None:
        port = settings.port
        profile_id = str(self.profile_combo.currentData())

        try:
            self._mode_manager.reserve(port, AppMode.MASTER_READ, METERS_TAB_OWNER)
            self._reserved_port = port
        except RuntimeError as exc:
            self._set_status(f"Error: {exc}")
            return

        self._reading_busy = True
        self.read_once_button.setEnabled(False)
        self._set_status("Reading…")

        self._thread = QThread(self)
        self._worker = MeterReadWorker(settings, self.slave_id.value(), profile_id)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_success)
        self._worker.failed.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    @Slot(object)
    def _on_success(self, result: ProfileReadResult) -> None:
        self._cycle_count += 1
        ts = datetime.now().strftime("%H:%M:%S")
        self._set_status(
            f"Read OK — {len(result.values)} value(s) — "
            f"cycle {self._cycle_count} — {ts}"
        )
        self._populate_table(result.values)
        self._release_port()

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self._set_status(f"Error: {message}")
        self._release_port()

    @Slot()
    def _cleanup_worker(self) -> None:
        self._reading_busy = False
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        if self._continuous_timer is None:
            self.read_once_button.setEnabled(True)

    def _release_port(self) -> None:
        if self._reserved_port is None:
            return
        self._mode_manager.release(self._reserved_port, METERS_TAB_OWNER)
        self._reserved_port = None

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    # ── table population ─────────────────────────────────────────────────

    def _populate_table(self, values: list[DecodedProfileValue]) -> None:
        self.values_table.setRowCount(len(values))
        for row, val in enumerate(values):
            group = _classify_variable(val.variable)
            self.values_table.setItem(row, 0, QTableWidgetItem(group))
            self.values_table.setItem(row, 1, QTableWidgetItem(val.variable))
            self.values_table.setItem(row, 2, QTableWidgetItem(str(val.value)))
            self.values_table.setItem(row, 3, QTableWidgetItem(val.unit or ""))
            self.values_table.setItem(row, 4, QTableWidgetItem(str(val.address)))
            self.values_table.setItem(row, 5, QTableWidgetItem(val.description))


def _friendly_serial_error(message: str) -> str:
    lower = message.lower()
    if "timed out" in lower or "no response" in lower:
        return (
            "No response received from device. Check COM port, wiring, slave ID, "
            f"baudrate, parity and stop bits. Details: {message}"
        )
    return message
