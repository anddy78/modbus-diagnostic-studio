"""Advanced Master tab — generic Modbus RTU read for technical users."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.master.client import ModbusMasterClient
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.services.mode_manager import AppMode, ModeManager
from modbus_diagnostic_studio.transports.rtu_transport import RtuTransport
from modbus_diagnostic_studio.transports.serial_ports import list_serial_ports

ADVANCED_MASTER_OWNER = "advanced_master_tab"

# TODO: add FC01 Read Coils and FC02 Read Discrete Inputs once coil/bit
#       response parsing is added to the core RTU frame parser.

DECODE_FORMATS = [
    "uint16",
    "int16",
    "uint32",
    "int32",
    "float32",
    "float32 word-swap",
    "hex",
    "binary",
]


# ── pure decode helper ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DecodeRow:
    """One row in the decoded register table."""

    offset: int
    address: int
    raw_uint16: int
    hex_str: str
    bin_str: str
    decoded: str


def decode_registers(
    registers: list[int],
    start_address: int,
    fmt: str,
) -> list[DecodeRow]:
    """Decode a list of Modbus registers into display rows.

    Single-register formats (uint16, int16, hex, binary) produce one row per
    register.  Multi-register formats (uint32, int32, float32, float32
    word-swap) consume pairs; the decoded value is shown on the first row of
    each pair while the second row shows "-".
    """
    rows: list[DecodeRow] = []

    def _base_row(offset: int) -> tuple[int, int, int, str, str]:
        raw = registers[offset]
        return (
            offset,
            start_address + offset,
            raw,
            f"0x{raw:04X}",
            f"{raw:016b}",
        )

    if fmt == "uint16":
        for i, raw in enumerate(registers):
            rows.append(DecodeRow(*_base_row(i), decoded=str(raw)))

    elif fmt == "int16":
        for i, raw in enumerate(registers):
            signed = raw - 0x10000 if raw & 0x8000 else raw
            rows.append(DecodeRow(*_base_row(i), decoded=str(signed)))

    elif fmt in ("uint32", "int32", "float32", "float32 word-swap"):
        for i in range(0, len(registers), 2):
            pair = registers[i : i + 2]
            if len(pair) == 2:
                decoded_val = _decode_pair(pair, fmt)
                rows.append(DecodeRow(*_base_row(i), decoded=decoded_val))
                rows.append(DecodeRow(*_base_row(i + 1), decoded="-"))
            else:
                rows.append(DecodeRow(*_base_row(i), decoded="(incomplete pair)"))

    elif fmt == "hex":
        for i, raw in enumerate(registers):
            rows.append(DecodeRow(*_base_row(i), decoded=f"0x{raw:04X}"))

    elif fmt == "binary":
        for i, raw in enumerate(registers):
            rows.append(DecodeRow(*_base_row(i), decoded=f"{raw:016b}"))

    else:
        for i, raw in enumerate(registers):
            rows.append(DecodeRow(*_base_row(i), decoded=str(raw)))

    return rows


def _decode_pair(pair: list[int], fmt: str) -> str:
    """Decode two registers into a string value for the given format."""
    high, low = pair
    raw32 = (high << 16) | low

    if fmt == "uint32":
        return str(raw32)

    if fmt == "int32":
        signed = raw32 - 0x100000000 if raw32 & 0x80000000 else raw32
        return str(signed)

    # float32 normal: high register = most significant word
    if fmt == "float32":
        data = struct.pack(">HH", high, low)
        value = struct.unpack(">f", data)[0]
        return f"{value:.6g}"

    # float32 word-swap: low register = most significant word
    if fmt == "float32 word-swap":
        data = struct.pack(">HH", low, high)
        value = struct.unpack(">f", data)[0]
        return f"{value:.6g}"

    return str(raw32)


# ── background worker ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AdvancedReadRequest:
    """One raw Modbus read request."""

    settings: SerialConnectionSettings
    slave_id: int
    function_code: int
    address: int
    quantity: int


class AdvancedReadWorker(QObject):
    """Worker that opens a transport, reads raw registers, then closes."""

    finished = Signal(object)   # list[int]
    failed = Signal(str)

    def __init__(self, request: AdvancedReadRequest) -> None:
        super().__init__()
        self._request = request

    @Slot()
    def run(self) -> None:
        transport = RtuTransport(self._request.settings)
        try:
            transport.open()
            client = ModbusMasterClient(transport)
            if self._request.function_code == 3:
                registers = client.read_holding_registers(
                    self._request.slave_id,
                    self._request.address,
                    self._request.quantity,
                )
            else:
                registers = client.read_input_registers(
                    self._request.slave_id,
                    self._request.address,
                    self._request.quantity,
                )
            self.finished.emit(registers)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            try:
                transport.close()
            except Exception:
                pass


# ── tab widget ────────────────────────────────────────────────────────────────


class AdvancedMasterTab(QWidget):
    """Generic Modbus RTU read tab for technical users."""

    def __init__(self) -> None:
        super().__init__()

        self._mode_manager = ModeManager()
        self._reserved_port: str | None = None
        self._thread: QThread | None = None
        self._worker: AdvancedReadWorker | None = None
        self._continuous_timer: QTimer | None = None
        self._reading_busy: bool = False
        self._cycle_count: int = 0
        self._error_count: int = 0
        self._last_error: str = ""

        # ── status ────────────────────────────────────────────────────────
        self.status_label = QLabel(
            "Active master mode. A request is sent only when Read Once or Start Continuous is pressed."
        )

        # ── connection / request form ─────────────────────────────────────
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

        self.function_combo = QComboBox()
        self.function_combo.addItem("FC03 — Read Holding Registers", 3)
        self.function_combo.addItem("FC04 — Read Input Registers", 4)

        self.start_address = QSpinBox()
        self.start_address.setRange(0, 65535)
        self.start_address.setValue(0)

        self.quantity = QSpinBox()
        self.quantity.setRange(1, 125)
        self.quantity.setValue(10)

        self.poll_interval = QSpinBox()
        self.poll_interval.setRange(1, 300)
        self.poll_interval.setValue(2)
        self.poll_interval.setSuffix(" s")

        self.decode_format = QComboBox()
        for fmt in DECODE_FORMATS:
            self.decode_format.addItem(fmt, fmt)

        # ── counters / meta labels ────────────────────────────────────────
        self.cycles_label = QLabel("Cycles: 0")
        self.errors_label = QLabel("Errors: 0")
        self.last_read_label = QLabel("Last read: —")

        # ── action buttons ────────────────────────────────────────────────
        self.read_once_button = QPushButton("Read Once")
        self.read_once_button.clicked.connect(self._read_once)

        self.start_button = QPushButton("Start Continuous Read")
        self.start_button.clicked.connect(self._start_continuous)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self._stop)
        self.stop_button.setEnabled(False)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear)

        # ── output table ──────────────────────────────────────────────────
        self.registers_table = QTableWidget(0, 6)
        self.registers_table.setHorizontalHeaderLabels(
            ["Offset", "Address", "Raw uint16", "Hex", "Binary", "Decoded value"]
        )
        self.registers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.registers_table.setSelectionBehavior(QTableWidget.SelectRows)

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
        form.addRow("Slave ID", self.slave_id)
        form.addRow("Function", self.function_combo)
        form.addRow("Start address", self.start_address)
        form.addRow("Quantity", self.quantity)
        form.addRow("Poll interval (continuous)", self.poll_interval)
        form.addRow("Decode format", self.decode_format)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.read_once_button)
        btn_row.addWidget(self.start_button)
        btn_row.addWidget(self.stop_button)
        btn_row.addWidget(self.clear_button)

        meta_row = QHBoxLayout()
        meta_row.addWidget(self.cycles_label)
        meta_row.addWidget(self.errors_label)
        meta_row.addWidget(self.last_read_label)
        meta_row.addStretch()

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addLayout(meta_row)
        layout.addWidget(QLabel("Registers"))
        layout.addWidget(self.registers_table)
        self.setLayout(layout)

    # ── port refresh ──────────────────────────────────────────────────────

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
            f"{self.port_combo.count()} port(s) detected. Active read — request sent only on demand."
        )

    # ── read once ─────────────────────────────────────────────────────────

    def _read_once(self) -> None:
        if self._reading_busy:
            return
        request = self._build_request()
        if request is None:
            return
        self._start_worker(request)

    # ── continuous read ───────────────────────────────────────────────────

    def _start_continuous(self) -> None:
        if self._reading_busy:
            return
        if self.port_combo.currentData() is None:
            self._set_status("Error: no COM port selected.")
            return

        self.start_button.setEnabled(False)
        self.read_once_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.poll_interval.setEnabled(False)

        self._continuous_timer = QTimer(self)
        self._continuous_timer.setInterval(self.poll_interval.value() * 1000)
        self._continuous_timer.timeout.connect(self._continuous_tick)
        self._set_status("Continuous read started.")
        self._continuous_tick()
        self._continuous_timer.start()

    def _continuous_tick(self) -> None:
        if self._reading_busy:
            return
        request = self._build_request()
        if request is None:
            self._stop()
            return
        self._start_worker(request)

    def _stop(self) -> None:
        if self._continuous_timer is not None:
            self._continuous_timer.stop()
            self._continuous_timer.deleteLater()
            self._continuous_timer = None

        self._release_port()
        self.start_button.setEnabled(True)
        self.read_once_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.poll_interval.setEnabled(True)
        if not self._reading_busy:
            self._set_status("Stopped.")

    def _clear(self) -> None:
        self.registers_table.setRowCount(0)
        self._cycle_count = 0
        self._error_count = 0
        self._last_error = ""
        self._update_meta_labels()
        self.last_read_label.setText("Last read: —")

    # ── worker lifecycle ──────────────────────────────────────────────────

    def _build_request(self) -> AdvancedReadRequest | None:
        port = self.port_combo.currentData()
        if not port:
            self._set_status("Error: no COM port selected.")
            return None
        try:
            settings = SerialConnectionSettings(
                port=str(port),
                baudrate=self.baudrate.value(),
                parity=self.parity.currentText(),
                stopbits=float(self.stopbits.currentText()),
                timeout=self.timeout.value(),
            )
        except ValueError as exc:
            self._set_status(f"Error: invalid settings — {exc}")
            return None
        return AdvancedReadRequest(
            settings=settings,
            slave_id=self.slave_id.value(),
            function_code=int(self.function_combo.currentData()),
            address=self.start_address.value(),
            quantity=self.quantity.value(),
        )

    def _start_worker(self, request: AdvancedReadRequest) -> None:
        port = request.settings.port
        try:
            self._mode_manager.reserve(port, AppMode.MASTER_READ, ADVANCED_MASTER_OWNER)
            self._reserved_port = port
        except RuntimeError as exc:
            self._set_status(f"Error: {exc}")
            return

        self._reading_busy = True
        self.read_once_button.setEnabled(False)
        self._set_status("Reading…")

        self._thread = QThread(self)
        self._worker = AdvancedReadWorker(request)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_success)
        self._worker.failed.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    @Slot(object)
    def _on_success(self, registers: list[int]) -> None:
        self._cycle_count += 1
        ts = datetime.now().strftime("%H:%M:%S")
        self.last_read_label.setText(f"Last read: {ts}")
        self._update_meta_labels()
        self._set_status(
            f"Read OK — {len(registers)} register(s) — cycle {self._cycle_count} — {ts}"
        )
        fmt = str(self.decode_format.currentData())
        rows = decode_registers(registers, self.start_address.value(), fmt)
        self._populate_table(rows)
        self._release_port()

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self._error_count += 1
        self._last_error = message
        self._update_meta_labels()
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
        self._mode_manager.release(self._reserved_port, ADVANCED_MASTER_OWNER)
        self._reserved_port = None

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _update_meta_labels(self) -> None:
        self.cycles_label.setText(f"Cycles: {self._cycle_count}")
        self.errors_label.setText(f"Errors: {self._error_count}")

    # ── table population ──────────────────────────────────────────────────

    def _populate_table(self, rows: list[DecodeRow]) -> None:
        self.registers_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.registers_table.setItem(i, 0, QTableWidgetItem(str(row.offset)))
            self.registers_table.setItem(i, 1, QTableWidgetItem(str(row.address)))
            self.registers_table.setItem(i, 2, QTableWidgetItem(str(row.raw_uint16)))
            self.registers_table.setItem(i, 3, QTableWidgetItem(row.hex_str))
            self.registers_table.setItem(i, 4, QTableWidgetItem(row.bin_str))
            self.registers_table.setItem(i, 5, QTableWidgetItem(row.decoded))
