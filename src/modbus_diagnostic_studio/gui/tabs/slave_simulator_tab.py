"""Slave Simulator tab — active mode, responds to Modbus RTU master requests."""

from __future__ import annotations

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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.services.mode_manager import AppMode, ModeManager
from modbus_diagnostic_studio.slave.datastore import SlaveDatastore
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

    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: SlaveServerWorker | None = None
        self._running = False
        self._reserved_port: str | None = None
        self._mode_manager = ModeManager()
        self._datastore = SlaveDatastore()

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
        form.addRow("Timeout (s)", self.timeout)
        form.addRow("Slave ID", self.slave_id_spin)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.start_button)
        btn_row.addWidget(self.stop_button)
        btn_row.addWidget(self.clear_button)

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

        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("Offset"))
        view_row.addWidget(self.view_offset)
        view_row.addWidget(QLabel("Count"))
        view_row.addWidget(self.view_count)
        view_row.addWidget(self.refresh_table_button)

        layout = QVBoxLayout()
        layout.addWidget(self.banner_label)
        layout.addWidget(self.status_label)
        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addLayout(stats)
        layout.addWidget(QLabel("Datastore editor"))
        layout.addLayout(editor_form)
        layout.addWidget(QLabel("Register view"))
        layout.addLayout(view_row)
        layout.addWidget(self.register_table)
        self.setLayout(layout)

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
