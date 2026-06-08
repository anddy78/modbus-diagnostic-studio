"""Slave Simulator tab — active mode, responds to Modbus RTU master requests."""

from __future__ import annotations

import random

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
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
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.device_profiles.loader import load_all_device_profiles
from modbus_diagnostic_studio.gui.help import set_help
from modbus_diagnostic_studio.gui.profile_views import (
    populate_register_preview_table,
    selected_register_from_table,
)
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.profiles.loader import list_builtin_profiles, load_builtin_profile
from modbus_diagnostic_studio.services.application_state import ApplicationState
from modbus_diagnostic_studio.services.mode_manager import AppMode, ModeManager
from modbus_diagnostic_studio.services.paths import ensure_runtime_dirs, user_device_profiles_dir
from modbus_diagnostic_studio.slave.datastore import SlaveDatastore
from modbus_diagnostic_studio.slave.demo_values import build_demo_register_values
from modbus_diagnostic_studio.slave.rtu_server import RtuSlaveServer, RtuSlaveServerConfig, RtuSlaveServerStats
from modbus_diagnostic_studio.slave.simulator_engine import ModbusSlaveSimulator
from modbus_diagnostic_studio.transports.serial_ports import list_serial_ports

SLAVE_OWNER = "slave_simulator_tab"

_BANKS = ["Holding Registers", "Input Registers", "Coils", "Discrete Inputs"]
_VIEW_COUNT_DEFAULT = 32


class SlaveServerWorker(QObject):
    """Background worker that drives RtuSlaveServer.poll_once() via QTimer."""

    stats_ready = Signal(object)   # RtuSlaveServerStats
    failed = Signal(str)
    stopped = Signal()

    def __init__(self, config: RtuSlaveServerConfig, simulator: ModbusSlaveSimulator) -> None:
        super().__init__()
        self._config = config
        self._simulator = simulator
        self._server: RtuSlaveServer | None = None
        self._timer: QTimer | None = None

    @Slot()
    def start(self) -> None:
        """Open the server and start polling."""
        try:
            self._server = RtuSlaveServer(self._config, self._simulator)
            self._server.open()
        except Exception as exc:
            self.failed.emit(str(exc))
            self.stopped.emit()
            return

        self._timer = QTimer(self)
        self._timer.setInterval(int(self._config.poll_interval_seconds * 1000))
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    @Slot()
    def _poll(self) -> None:
        if self._server is None:
            return
        try:
            stats = self._server.poll_once()
            self.stats_ready.emit(stats)
        except Exception as exc:
            self._close_server()
            self.failed.emit(str(exc))
            self.stopped.emit()

    @Slot()
    def stop(self) -> None:
        """Stop polling and close the server."""
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        self._close_server()
        self.stopped.emit()

    def _close_server(self) -> None:
        if self._server is None:
            return
        try:
            self._server.close()
        except Exception:
            pass
        self._server = None


class SlaveSimulatorTab(QWidget):
    """Active Slave Simulator GUI — responds to incoming Modbus RTU requests."""

    stop_requested = Signal()

    def __init__(self, app_state: ApplicationState | None = None) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: SlaveServerWorker | None = None
        self._running = False
        self._reserved_port: str | None = None
        self._app_state = app_state or ApplicationState()
        self._mode_manager = self._app_state.mode_manager
        self._datastore = SlaveDatastore()
        self._device_profiles: list[object] = []
        self._register_profiles: dict[str, object] = {}
        self._demo_timer: QTimer | None = None
        self._demo_rng = random.Random()

        # ── active mode banner ────────────────────────────────────────────
        self.banner_label = QLabel("ACTIVE SLAVE SIMULATOR — RESPONDS TO MASTER REQUESTS")
        banner_font = self.banner_label.font()
        banner_font.setPointSize(max(banner_font.pointSize() + 2, 12))
        banner_font.setBold(True)
        self.banner_label.setFont(banner_font)

        self.status_label = QLabel("Stopped. Configure settings and press Start.")

        # ── connection form ───────────────────────────────────────────────
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
        self.timeout.setRange(0.05, 10.0)
        self.timeout.setSingleStep(0.05)
        self.timeout.setValue(0.05)

        self.slave_id_spin = QSpinBox()
        self.slave_id_spin.setRange(1, 247)
        self.slave_id_spin.setValue(1)

        self.device_profile_combo = QComboBox()
        self.device_profile_combo.addItem("None / Generic raw datastore", None)
        self.device_profile_combo.currentIndexChanged.connect(self._on_device_profile_changed)

        self.register_profile_combo = QComboBox()
        self.register_profile_combo.addItem("None / Raw datastore", None)
        self.register_profile_combo.currentIndexChanged.connect(self._on_register_profile_changed)

        self.load_profile_registers_button = QPushButton("Load Profile Registers")
        self.load_profile_registers_button.clicked.connect(self._load_selected_known_registers)

        self.generate_demo_values_button = QPushButton("Generate Demo Meter Values")
        self.generate_demo_values_button.clicked.connect(self.generate_demo_meter_values)
        self.random_variation_combo = QComboBox()
        self.random_variation_combo.addItem("Off", False)
        self.random_variation_combo.addItem("On", True)
        self.variation_percent_spin = QSpinBox()
        self.variation_percent_spin.setRange(0, 20)
        self.variation_percent_spin.setValue(2)
        self.auto_refresh_demo_combo = QComboBox()
        self.auto_refresh_demo_combo.addItem("Off", False)
        self.auto_refresh_demo_combo.addItem("On", True)
        self.auto_refresh_demo_combo.currentIndexChanged.connect(self._update_demo_timer_state)
        self.demo_update_interval_spin = QSpinBox()
        self.demo_update_interval_spin.setRange(1, 60)
        self.demo_update_interval_spin.setValue(2)
        self.demo_update_interval_spin.setSuffix(" s")
        self.demo_update_interval_spin.valueChanged.connect(self._update_demo_timer_interval)

        # ── action buttons ────────────────────────────────────────────────
        self.start_button = QPushButton("Start Slave Simulator")
        self.start_button.clicked.connect(self.start_simulator)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_simulator)
        self.stop_button.setEnabled(False)
        self.clear_button = QPushButton("Clear Datastore")
        self.clear_button.clicked.connect(self.clear_datastore)

        # ── stats labels ──────────────────────────────────────────────────
        self.req_seen_label = QLabel("0")
        self.req_slave_label = QLabel("0")
        self.resp_sent_label = QLabel("0")
        self.exc_label = QLabel("0")
        self.crc_label = QLabel("0")
        self.last_req_label = QLabel("-")
        self.last_resp_label = QLabel("-")
        self.last_error_label = QLabel("-")

        # ── datastore editor ──────────────────────────────────────────────
        self.bank_combo = QComboBox()
        for b in _BANKS:
            self.bank_combo.addItem(b, b)

        self.edit_address = QSpinBox()
        self.edit_address.setRange(0, 65535)

        self.edit_value = QSpinBox()
        self.edit_value.setRange(0, 65535)

        self.write_single_button = QPushButton("Write Single")
        self.write_single_button.clicked.connect(self._write_single)

        self.range_input = QLineEdit()
        self.range_input.setPlaceholderText("e.g. 100,200,300 or 1 0 1 0")

        self.write_range_button = QPushButton("Write Range")
        self.write_range_button.clicked.connect(self._write_range)

        # ── register view ─────────────────────────────────────────────────
        self.view_offset = QSpinBox()
        self.view_offset.setRange(0, 65535)
        self.view_offset.setValue(0)

        self.view_count = QSpinBox()
        self.view_count.setRange(1, 256)
        self.view_count.setValue(_VIEW_COUNT_DEFAULT)

        self.refresh_table_button = QPushButton("Refresh Table")
        self.refresh_table_button.clicked.connect(self._refresh_table)

        self.register_table = QTableWidget(0, 4)
        self.register_table.setHorizontalHeaderLabels(["Address", "Decimal", "Hex", "Bool"])
        self.register_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.register_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.register_table.setMinimumHeight(260)

        self.known_registers_table = QTableWidget(0, 9)
        self.known_registers_table.setHorizontalHeaderLabels(
            ["Variable", "Address", "Function", "Bank", "Type", "Quantity", "Unit", "Scale", "Description"]
        )
        self.known_registers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.known_registers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.known_registers_table.setMinimumHeight(220)
        self.known_registers_table.itemSelectionChanged.connect(
            self._apply_selected_known_register
        )

        self._build_layout()
        self._attach_help()
        self.refresh_ports()
        self._reload_profile_selectors()

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
        form.addRow("Slave ID", self.slave_id_spin)
        form.addRow("Device profile", self.device_profile_combo)
        form.addRow("Register profile", self.register_profile_combo)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.start_button)
        btn_row.addWidget(self.stop_button)
        btn_row.addWidget(self.clear_button)
        btn_row.addWidget(self.load_profile_registers_button)

        stats = QGridLayout()
        stats.addWidget(QLabel("Requests seen"), 0, 0)
        stats.addWidget(self.req_seen_label, 0, 1)
        stats.addWidget(QLabel("For this slave"), 0, 2)
        stats.addWidget(self.req_slave_label, 0, 3)
        stats.addWidget(QLabel("Responses sent"), 1, 0)
        stats.addWidget(self.resp_sent_label, 1, 1)
        stats.addWidget(QLabel("Exceptions"), 1, 2)
        stats.addWidget(self.exc_label, 1, 3)
        stats.addWidget(QLabel("CRC errors"), 2, 0)
        stats.addWidget(self.crc_label, 2, 1)
        stats.addWidget(QLabel("Last request"), 3, 0)
        stats.addWidget(self.last_req_label, 3, 1, 1, 3)
        stats.addWidget(QLabel("Last response"), 4, 0)
        stats.addWidget(self.last_resp_label, 4, 1, 1, 3)
        stats.addWidget(QLabel("Last error"), 5, 0)
        stats.addWidget(self.last_error_label, 5, 1, 1, 3)

        editor_form = QFormLayout()
        editor_form.addRow("Bank", self.bank_combo)
        edit_row = QHBoxLayout()
        edit_row.addWidget(QLabel("Address"))
        edit_row.addWidget(self.edit_address)
        edit_row.addWidget(QLabel("Value"))
        edit_row.addWidget(self.edit_value)
        edit_row.addWidget(self.write_single_button)
        editor_form.addRow("Single write", edit_row)
        range_row = QHBoxLayout()
        range_row.addWidget(self.range_input)
        range_row.addWidget(self.write_range_button)
        editor_form.addRow("Range write", range_row)

        demo_form = QFormLayout()
        demo_form.addRow(self.generate_demo_values_button)
        demo_form.addRow("Random variation", self.random_variation_combo)
        demo_form.addRow("Variation %", self.variation_percent_spin)
        demo_form.addRow("Auto refresh demo values", self.auto_refresh_demo_combo)
        demo_form.addRow("Update interval", self.demo_update_interval_spin)

        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("Offset"))
        view_row.addWidget(self.view_offset)
        view_row.addWidget(QLabel("Count"))
        view_row.addWidget(self.view_count)
        view_row.addWidget(self.refresh_table_button)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.addWidget(self.banner_label)
        content_layout.addWidget(self.status_label)
        content_layout.addLayout(form)
        content_layout.addLayout(btn_row)
        content_layout.addLayout(stats)
        content_layout.addWidget(QLabel("Datastore editor"))
        content_layout.addLayout(editor_form)
        content_layout.addWidget(QLabel("Demo meter values"))
        content_layout.addLayout(demo_form)
        content_layout.addWidget(QLabel("Known registers for simulated slave"))
        content_layout.addWidget(self.known_registers_table)
        content_layout.addWidget(QLabel("Register view"))
        content_layout.addLayout(view_row)
        content_layout.addWidget(self.register_table)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        layout = QVBoxLayout()
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _attach_help(self) -> None:
        set_help(
            self.slave_id_spin,
            "Slave ID",
            "Address used by the simulator when replying to incoming Modbus RTU requests.",
        )
        set_help(
            self.start_button,
            "Start Slave Simulator",
            "Open the selected COM port in active slave mode and begin responding to master requests.",
        )
        set_help(
            self.register_table,
            "Datastore editor",
            "This table shows the simulated datastore values for the selected bank and range.",
        )
        set_help(
            self.known_registers_table,
            "Known registers",
            "Profile-guided known registers for the simulated slave. Selecting one updates the editor fields but does not write values.",
        )
        set_help(
            self.generate_demo_values_button,
            "Generate Demo Meter Values",
            "Populate the local slave datastore with reasonable demo values for the selected profile. This only changes the local simulator datastore.",
        )

    # ── port refresh ──────────────────────────────────────────────────────

    def refresh_ports(self) -> None:
        current = self.port_combo.currentData()
        self.port_combo.clear()
        for port in list_serial_ports():
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)
        if current is not None:
            idx = self.port_combo.findData(current)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
        self.status_label.setText(
            f"{self.port_combo.count()} port(s) detected. "
            "ACTIVE MODE — slave responds to requests."
        )

    # ── start / stop ──────────────────────────────────────────────────────

    def start_simulator(self) -> None:
        if self._running:
            return

        port = self.port_combo.currentData()
        if not port:
            self._set_status("Error: no COM port selected.")
            return
        port = str(port)

        try:
            self._mode_manager.reserve(port, AppMode.SLAVE_SIMULATOR, SLAVE_OWNER)
            self._reserved_port = port
        except RuntimeError as exc:
            self._set_status(f"Error: {exc}")
            return

        try:
            settings = SerialConnectionSettings(
                port=port,
                baudrate=self.baudrate.value(),
                parity=self.parity.currentText(),
                stopbits=float(self.stopbits.currentText()),
                timeout=self.timeout.value(),
            )
        except ValueError as exc:
            self._release_port()
            self._set_status(f"Error: invalid settings — {exc}")
            return

        slave_id = self.slave_id_spin.value()
        config = RtuSlaveServerConfig(
            connection=settings,
            slave_id=slave_id,
        )
        simulator = ModbusSlaveSimulator(slave_id=slave_id, datastore=self._datastore)

        self._set_running_state(True)
        self._set_status(f"Starting slave simulator on {port}, slave ID {slave_id}…")

        self._thread = QThread(self)
        self._worker = SlaveServerWorker(config, simulator)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self.stop_requested.connect(self._worker.stop, Qt.QueuedConnection)
        self._worker.stats_ready.connect(self._handle_stats)
        self._worker.failed.connect(self._handle_error)
        self._worker.stopped.connect(self._handle_stopped)
        self._worker.stopped.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    def stop_simulator(self) -> None:
        if self._worker is None:
            self._finish_stop("Stopped.")
            return
        self._set_status("Stopping…")
        self.stop_requested.emit()

    def clear_datastore(self) -> None:
        self._datastore.clear_all()
        self._set_status("Datastore cleared.")
        self._refresh_table()

    def generate_demo_meter_values(self) -> None:
        profile_id = self.register_profile_combo.currentData()
        if profile_id is None:
            self._set_status("Select a register profile before generating demo values.")
            return
        profile = self._register_profiles.get(str(profile_id))
        if profile is None:
            self._set_status(f"Register profile {profile_id} is not available.")
            return

        variation_percent = (
            float(self.variation_percent_spin.value())
            if bool(self.random_variation_combo.currentData())
            else 0.0
        )
        result = build_demo_register_values(
            profile,
            variation_percent=variation_percent,
            rng=self._demo_rng,
        )
        if result.generated_count == 0:
            self._set_status("No known meter-like registers generated.")
            return

        for (bank_name, address), raw_value in result.values.items():
            if bank_name == "Holding Registers":
                self._datastore.write_holding_register(address, raw_value)
            elif bank_name == "Input Registers":
                self._datastore.write_input_register(address, raw_value)
            else:
                self._set_status(f"Unsupported demo bank {bank_name}.")
                return

        self._refresh_table()
        self._set_status(
            f"Generated {result.generated_count} demo meter registers for {profile.profile_id} with {variation_percent:.0f}% variation."
        )

    def _update_demo_timer_state(self) -> None:
        enabled = bool(self.auto_refresh_demo_combo.currentData())
        if not enabled:
            self._stop_demo_timer()
            return
        if self._demo_timer is None:
            self._demo_timer = QTimer(self)
            self._demo_timer.timeout.connect(self.generate_demo_meter_values)
        self._demo_timer.setInterval(self.demo_update_interval_spin.value() * 1000)
        self._demo_timer.start()
        self._set_status("Auto refresh demo values enabled.")

    def _update_demo_timer_interval(self) -> None:
        if self._demo_timer is not None:
            self._demo_timer.setInterval(self.demo_update_interval_spin.value() * 1000)

    def _stop_demo_timer(self) -> None:
        if self._demo_timer is None:
            return
        self._demo_timer.stop()

    def _reload_profile_selectors(self) -> None:
        ensure_runtime_dirs()
        self._device_profiles, _ = load_all_device_profiles(user_device_profiles_dir())
        self._register_profiles = {
            profile_id: load_builtin_profile(profile_id)
            for profile_id in list_builtin_profiles()
        }

        self.device_profile_combo.blockSignals(True)
        current_device = self.device_profile_combo.currentData()
        self.device_profile_combo.clear()
        self.device_profile_combo.addItem("None / Generic raw datastore", None)
        for profile in self._device_profiles:
            register_profile_id = self._device_profile_register_profile_id(profile)
            if not register_profile_id:
                continue
            self.device_profile_combo.addItem(
                f"{profile.name} ({profile.device_type})",
                profile.device_id,
            )
        if current_device is not None:
            idx = self.device_profile_combo.findData(current_device)
            if idx >= 0:
                self.device_profile_combo.setCurrentIndex(idx)
        self.device_profile_combo.blockSignals(False)

        self.register_profile_combo.blockSignals(True)
        current_register = self.register_profile_combo.currentData()
        self.register_profile_combo.clear()
        self.register_profile_combo.addItem("None / Raw datastore", None)
        for profile_id, profile in sorted(self._register_profiles.items()):
            self.register_profile_combo.addItem(profile.name, profile_id)
        if current_register is not None:
            idx = self.register_profile_combo.findData(current_register)
            if idx >= 0:
                self.register_profile_combo.setCurrentIndex(idx)
        self.register_profile_combo.blockSignals(False)

    def _on_device_profile_changed(self) -> None:
        device_id = self.device_profile_combo.currentData()
        if device_id is None:
            return
        profile = self._find_device_profile(str(device_id))
        if profile is None:
            return
        register_profile_id = self._device_profile_register_profile_id(profile)
        if register_profile_id is None:
            self._set_status(f"Device profile {profile.device_id} has no linked slave register profile.")
            return
        index = self.register_profile_combo.findData(register_profile_id)
        if index >= 0:
            self.register_profile_combo.setCurrentIndex(index)
        self._load_known_registers(register_profile_id)

    def _on_register_profile_changed(self) -> None:
        profile_id = self.register_profile_combo.currentData()
        if profile_id is None:
            self.known_registers_table.setRowCount(0)
            return
        self._load_known_registers(str(profile_id))

    def _load_selected_known_registers(self) -> None:
        profile_id = self.register_profile_combo.currentData()
        if profile_id is None:
            self.known_registers_table.setRowCount(0)
            self._set_status("Using generic raw datastore without a reference profile.")
            return
        self._load_known_registers(str(profile_id))

    def _load_known_registers(self, profile_id: str) -> None:
        profile = self._register_profiles.get(profile_id)
        if profile is None:
            self.known_registers_table.setRowCount(0)
            self._set_status(f"Register profile {profile_id} is not available.")
            return
        populate_register_preview_table(self.known_registers_table, profile)
        self._set_status(f"Simulating with register profile {profile.profile_id}.")

    def _apply_selected_known_register(self) -> None:
        selected = selected_register_from_table(self.known_registers_table)
        if selected is None:
            return
        bank_index = self.bank_combo.findData(selected["bank"])
        if bank_index >= 0:
            self.bank_combo.setCurrentIndex(bank_index)
        self.edit_address.setValue(int(selected["address"]))
        self.view_offset.setValue(int(selected["address"]))
        self.view_count.setValue(max(int(selected["quantity"]), 1))
        self._refresh_table()
        self._set_status(
            f"Selected known register {selected['variable']} at address {selected['address']}."
        )

    def _find_device_profile(self, device_id: str):
        for profile in self._device_profiles:
            if profile.device_id == device_id:
                return profile
        return None

    @staticmethod
    def _device_profile_register_profile_id(profile) -> str | None:
        for role_link in profile.roles:
            if (
                role_link.enabled
                and role_link.role == "slave"
                and role_link.profile_type == "register_profile"
                and role_link.profile_id
            ):
                return role_link.profile_id
        return None

    # ── worker signals ────────────────────────────────────────────────────

    @Slot(object)
    def _handle_stats(self, stats: RtuSlaveServerStats) -> None:
        self.req_seen_label.setText(str(stats.requests_seen))
        self.req_slave_label.setText(str(stats.requests_for_this_slave))
        self.resp_sent_label.setText(str(stats.responses_sent))
        self.exc_label.setText(str(stats.exception_responses))
        self.crc_label.setText(str(stats.crc_errors))
        self.last_req_label.setText(stats.last_request_hex or "-")
        self.last_resp_label.setText(stats.last_response_hex or "-")
        if stats.last_error:
            self.last_error_label.setText(stats.last_error)
        self.status_label.setText(
            f"Running — {stats.responses_sent} response(s) sent, "
            f"{stats.exception_responses} exception(s)."
        )

    @Slot(str)
    def _handle_error(self, message: str) -> None:
        self._finish_stop(f"Error: {message}")

    @Slot()
    def _handle_stopped(self) -> None:
        self._finish_stop("Stopped.")

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
        self._release_port()
        self._set_status(status)

    def _set_running_state(self, running: bool) -> None:
        self._running = running
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.slave_id_spin.setEnabled(not running)

    def _release_port(self) -> None:
        if self._reserved_port is None:
            return
        self._mode_manager.release(self._reserved_port, SLAVE_OWNER)
        self._reserved_port = None

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def closeEvent(self, event) -> None:
        self._stop_demo_timer()
        super().closeEvent(event)

    # ── datastore editor ──────────────────────────────────────────────────

    def _current_bank_name(self) -> str:
        return str(self.bank_combo.currentData())

    def _write_single(self) -> None:
        bank = self._current_bank_name()
        addr = self.edit_address.value()
        val = self.edit_value.value()
        try:
            if bank == "Holding Registers":
                self._datastore.write_holding_register(addr, val)
            elif bank == "Input Registers":
                self._datastore.write_input_register(addr, val)
            elif bank == "Coils":
                self._datastore.write_coil(addr, 1 if val else 0)
            elif bank == "Discrete Inputs":
                self._datastore.write_discrete_input(addr, 1 if val else 0)
            self._set_status(f"Written {bank}[{addr}] = {val}.")
        except ValueError as exc:
            self._set_status(f"Write error: {exc}")

    def _write_range(self) -> None:
        bank = self._current_bank_name()
        addr = self.edit_address.value()
        raw = self.range_input.text().replace(",", " ").split()
        if not raw:
            self._set_status("Range write error: no values provided.")
            return
        try:
            int_values = [int(v) for v in raw]
        except ValueError:
            self._set_status("Range write error: values must be integers.")
            return
        try:
            if bank == "Holding Registers":
                self._datastore.write_holding_range(addr, int_values)
            elif bank == "Input Registers":
                self._datastore.write_input_range(addr, int_values)
            elif bank == "Coils":
                self._datastore.write_coil_range(addr, [1 if v else 0 for v in int_values])
            elif bank == "Discrete Inputs":
                self._datastore.write_discrete_input_range(addr, [1 if v else 0 for v in int_values])
            self._set_status(f"Written {len(int_values)} value(s) to {bank} starting at {addr}.")
        except ValueError as exc:
            self._set_status(f"Write error: {exc}")

    # ── register view ─────────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        bank = self._current_bank_name()
        offset = self.view_offset.value()
        count = self.view_count.value()
        is_bit_bank = bank in ("Coils", "Discrete Inputs")

        try:
            if bank == "Holding Registers":
                values = self._datastore.read_holding_registers(offset, count)
            elif bank == "Input Registers":
                values = self._datastore.read_input_registers(offset, count)
            elif bank == "Coils":
                bits = self._datastore.read_coils(offset, count)
                values = [int(b) for b in bits]
            else:
                bits = self._datastore.read_discrete_inputs(offset, count)
                values = [int(b) for b in bits]
        except ValueError as exc:
            self._set_status(f"View error: {exc}")
            return

        self.register_table.setRowCount(len(values))
        for i, v in enumerate(values):
            addr = offset + i
            self.register_table.setItem(i, 0, QTableWidgetItem(str(addr)))
            self.register_table.setItem(i, 1, QTableWidgetItem(str(v)))
            self.register_table.setItem(i, 2, QTableWidgetItem(f"0x{v:04X}"))
            self.register_table.setItem(
                i, 3, QTableWidgetItem("True" if v else "False") if is_bit_bank else QTableWidgetItem("")
            )
