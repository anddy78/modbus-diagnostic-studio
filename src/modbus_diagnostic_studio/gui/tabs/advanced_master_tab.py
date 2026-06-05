"""Advanced Master tab — generic Modbus RTU read and guarded write."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
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

_WRITE_CONFIRM_TOKEN = "WRITE"

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


# ── pure value-parsing helpers (no GUI dependency) ────────────────────────────


def parse_coil_values(text: str) -> list[bool]:
    """Parse comma- or space-separated coil values from *text*.

    Accepts: 1, 0, true, false (case-insensitive).
    Rejects all other tokens to avoid ambiguity.

    Examples
    --------
    "1,0,1"         → [True, False, True]
    "true false"    → [True, False]
    """
    tokens = text.replace(",", " ").split()
    if not tokens:
        raise ValueError("No coil values provided")
    result: list[bool] = []
    for tok in tokens:
        low = tok.lower()
        if low in ("1", "true"):
            result.append(True)
        elif low in ("0", "false"):
            result.append(False)
        else:
            raise ValueError(
                f"Invalid coil token {tok!r}; accepted values are 0/1 or true/false"
            )
    return result


def parse_register_values(text: str) -> list[int]:
    """Parse comma- or space-separated register values from *text*.

    Accepts decimal or 0x-prefixed hex.  All values must be 0..65535.

    Examples
    --------
    "100 200 300"       → [100, 200, 300]
    "0x0001, 0xFF00"    → [1, 65280]
    """
    tokens = text.replace(",", " ").split()
    if not tokens:
        raise ValueError("No register values provided")
    result: list[int] = []
    for tok in tokens:
        try:
            value = int(tok, 0)
        except ValueError:
            raise ValueError(f"Invalid register value {tok!r}; use decimal or 0x-prefixed hex")
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"Register value {value} (0x{value:X}) is out of range 0..65535")
        result.append(value)
    return result


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
    """Decode a list of Modbus registers into display rows."""
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
    high, low = pair
    raw32 = (high << 16) | low
    if fmt == "uint32":
        return str(raw32)
    if fmt == "int32":
        signed = raw32 - 0x100000000 if raw32 & 0x80000000 else raw32
        return str(signed)
    if fmt == "float32":
        data = struct.pack(">HH", high, low)
        return f"{struct.unpack('>f', data)[0]:.6g}"
    if fmt == "float32 word-swap":
        data = struct.pack(">HH", low, high)
        return f"{struct.unpack('>f', data)[0]:.6g}"
    return str(raw32)


# ── read worker ───────────────────────────────────────────────────────────────


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


# ── write worker ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WriteRequest:
    """One Modbus write request."""

    settings: SerialConnectionSettings
    slave_id: int
    function_code: int
    address: int
    coil_values: list[bool] | None = None
    register_values: list[int] | None = None


class AdvancedWriteWorker(QObject):
    """Worker that opens a transport, executes one write, then closes."""

    finished = Signal(str)   # human-readable success message
    failed = Signal(str)

    def __init__(self, request: WriteRequest) -> None:
        super().__init__()
        self._request = request

    @Slot()
    def run(self) -> None:
        transport = RtuTransport(self._request.settings)
        try:
            transport.open()
            client = ModbusMasterClient(transport)
            r = self._request
            if r.function_code == 5:
                v = r.coil_values[0]  # type: ignore[index]
                confirmed = client.write_single_coil(r.slave_id, r.address, v)
                self.finished.emit(
                    f"FC05 OK — address {r.address} = {confirmed}"
                )
            elif r.function_code == 6:
                v = r.register_values[0]  # type: ignore[index]
                confirmed = client.write_single_register(r.slave_id, r.address, v)
                self.finished.emit(
                    f"FC06 OK — address {r.address} = {confirmed} (0x{confirmed:04X})"
                )
            elif r.function_code == 15:
                qty = client.write_multiple_coils(
                    r.slave_id, r.address, r.coil_values  # type: ignore[arg-type]
                )
                self.finished.emit(
                    f"FC15 OK — address {r.address}, {qty} coil(s) written"
                )
            elif r.function_code == 16:
                qty = client.write_multiple_registers(
                    r.slave_id, r.address, r.register_values  # type: ignore[arg-type]
                )
                self.finished.emit(
                    f"FC16 OK — address {r.address}, {qty} register(s) written"
                )
            else:
                self.failed.emit(f"Unsupported write function code: {r.function_code}")
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            try:
                transport.close()
            except Exception:
                pass


# ── tab widget ────────────────────────────────────────────────────────────────


class AdvancedMasterTab(QWidget):
    """Generic Modbus RTU read and guarded write tab for technical users."""

    def __init__(self) -> None:
        super().__init__()

        self._mode_manager = ModeManager()
        self._reserved_port: str | None = None

        # read state
        self._thread: QThread | None = None
        self._worker: AdvancedReadWorker | None = None
        self._continuous_timer: QTimer | None = None
        self._reading_busy: bool = False
        self._cycle_count: int = 0
        self._error_count: int = 0
        self._last_error: str = ""

        # write state
        self._write_thread: QThread | None = None
        self._write_worker: AdvancedWriteWorker | None = None
        self._write_busy: bool = False

        # ── status ────────────────────────────────────────────────────────
        self.status_label = QLabel(
            "Active master mode. A request is sent only when Read Once or "
            "Start Continuous is pressed."
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

        # ── read action buttons ───────────────────────────────────────────
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

        # ── write section ─────────────────────────────────────────────────
        self._build_write_section()

        self._build_layout()
        self.refresh_ports()

    def _build_write_section(self) -> None:
        """Create all write-mode widgets (locked by default)."""
        # Warning banner
        self.write_warning_label = QLabel(
            "⚠  ACTIVE WRITE MODE — CAN MODIFY REAL DEVICES\n"
            "Writes are disabled by default.\n"
            "Only use on equipment you are authorized to test."
        )
        warn_font = self.write_warning_label.font()
        warn_font.setBold(True)
        self.write_warning_label.setFont(warn_font)

        # Unlock controls
        self.write_enable_check = QCheckBox("Enable Modbus Write Mode")
        self.write_enable_check.setChecked(False)
        self.write_enable_check.stateChanged.connect(self._update_write_unlock_state)

        self.write_risk_check = QCheckBox(
            "I understand this can modify a real device"
        )
        self.write_risk_check.setChecked(False)
        self.write_risk_check.setEnabled(False)
        self.write_risk_check.stateChanged.connect(self._update_write_unlock_state)

        self.write_confirm_edit = QLineEdit()
        self.write_confirm_edit.setPlaceholderText('Type "WRITE" to unlock')
        self.write_confirm_edit.setEnabled(False)
        self.write_confirm_edit.textChanged.connect(self._update_write_unlock_state)

        # Write function selector
        self.write_function_combo = QComboBox()
        self.write_function_combo.addItem("FC05 — Write Single Coil", 5)
        self.write_function_combo.addItem("FC06 — Write Single Register", 6)
        self.write_function_combo.addItem("FC15 — Write Multiple Coils", 15)
        self.write_function_combo.addItem("FC16 — Write Multiple Registers", 16)
        self.write_function_combo.setEnabled(False)
        self.write_function_combo.currentIndexChanged.connect(self._update_write_value_hint)

        # Write address
        self.write_address = QSpinBox()
        self.write_address.setRange(0, 65535)
        self.write_address.setEnabled(False)

        # Value input and hint label
        self.write_value_hint = QLabel("Value (0/1 or true/false):")
        self.write_value_edit = QLineEdit()
        self.write_value_edit.setPlaceholderText("e.g. 1")
        self.write_value_edit.setEnabled(False)

        # Send Write button
        self.send_write_button = QPushButton("Send Write")
        self.send_write_button.setEnabled(False)
        self.send_write_button.clicked.connect(self._send_write)

        # Write status
        self.write_status_label = QLabel("Write status: —")

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

        # ── write section group box ───────────────────────────────────────
        write_group = QGroupBox("Write Mode — Locked by default")
        wform = QFormLayout()
        wform.addRow(self.write_warning_label)
        wform.addRow(self.write_enable_check)
        wform.addRow(self.write_risk_check)
        wform.addRow("Confirmation:", self.write_confirm_edit)
        wform.addRow("Write function:", self.write_function_combo)
        wform.addRow("Write address:", self.write_address)
        wform.addRow(self.write_value_hint, self.write_value_edit)
        wform.addRow(self.send_write_button)
        wform.addRow(self.write_status_label)
        write_group.setLayout(wform)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addLayout(form)
        layout.addLayout(btn_row)
        layout.addLayout(meta_row)
        layout.addWidget(QLabel("Registers"))
        layout.addWidget(self.registers_table)
        layout.addWidget(write_group)
        self.setLayout(layout)

    # ── port refresh ──────────────────────────────────────────────────────

    def refresh_ports(self) -> None:
        current = self.port_combo.currentData()
        self.port_combo.clear()
        for port in list_serial_ports():
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)
        if current is not None:
            index = self.port_combo.findData(current)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        self.status_label.setText(
            f"{self.port_combo.count()} port(s) detected. "
            "Active read — request sent only on demand."
        )

    # ── read once ─────────────────────────────────────────────────────────

    def _read_once(self) -> None:
        if self._write_busy:
            self._set_status("Write in progress — wait for it to finish.")
            return
        if self._reading_busy:
            return
        request = self._build_read_request()
        if request is None:
            return
        self._start_read_worker(request)

    # ── continuous read ───────────────────────────────────────────────────

    def _start_continuous(self) -> None:
        if self._write_busy:
            self._set_status("Write in progress — wait for it to finish.")
            return
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
        request = self._build_read_request()
        if request is None:
            self._stop()
            return
        self._start_read_worker(request)

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

    # ── read worker lifecycle ─────────────────────────────────────────────

    def _build_read_request(self) -> AdvancedReadRequest | None:
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

    def _start_read_worker(self, request: AdvancedReadRequest) -> None:
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
        self._worker.finished.connect(self._on_read_success)
        self._worker.failed.connect(self._on_read_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_read_worker)
        self._thread.start()

    @Slot(object)
    def _on_read_success(self, registers: list[int]) -> None:
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
    def _on_read_error(self, message: str) -> None:
        self._error_count += 1
        self._last_error = message
        self._update_meta_labels()
        self._set_status(f"Error: {message}")
        self._release_port()

    @Slot()
    def _cleanup_read_worker(self) -> None:
        self._reading_busy = False
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        if self._continuous_timer is None:
            self.read_once_button.setEnabled(True)

    # ── write mode unlock ─────────────────────────────────────────────────

    def _update_write_unlock_state(self) -> None:
        """Enable/disable write controls based on the three unlock conditions."""
        enabled = self.write_enable_check.isChecked()
        self.write_risk_check.setEnabled(enabled)
        self.write_confirm_edit.setEnabled(enabled)
        self.write_function_combo.setEnabled(enabled)
        self.write_address.setEnabled(enabled)
        self.write_value_edit.setEnabled(enabled)

        unlocked = self._is_write_unlocked()
        self.send_write_button.setEnabled(unlocked and not self._write_busy)

    def _is_write_unlocked(self) -> bool:
        return (
            self.write_enable_check.isChecked()
            and self.write_risk_check.isChecked()
            and self.write_confirm_edit.text().strip() == _WRITE_CONFIRM_TOKEN
        )

    def _update_write_value_hint(self) -> None:
        fc = int(self.write_function_combo.currentData())
        if fc == 5:
            self.write_value_hint.setText("Value (true/false or 1/0):")
            self.write_value_edit.setPlaceholderText("e.g. true")
        elif fc == 6:
            self.write_value_hint.setText("Value (0..65535):")
            self.write_value_edit.setPlaceholderText("e.g. 100 or 0x0064")
        elif fc == 15:
            self.write_value_hint.setText("Coil values (e.g. 1,0,1,0):")
            self.write_value_edit.setPlaceholderText("e.g. true false true")
        elif fc == 16:
            self.write_value_hint.setText("Register values (e.g. 100,200):")
            self.write_value_edit.setPlaceholderText("e.g. 100 200 or 0x0064 0x00C8")

    # ── write execution ───────────────────────────────────────────────────

    def _send_write(self) -> None:
        if not self._is_write_unlocked():
            return
        if self._write_busy or self._reading_busy:
            self.write_status_label.setText("Busy — wait for current operation to finish.")
            return

        port = self.port_combo.currentData()
        if not port:
            self.write_status_label.setText("Error: no COM port selected.")
            return

        fc = int(self.write_function_combo.currentData())
        addr = self.write_address.value()
        value_text = self.write_value_edit.text().strip()

        # Parse values
        try:
            coil_values: list[bool] | None = None
            register_values: list[int] | None = None

            if fc == 5:
                coils = parse_coil_values(value_text)
                if len(coils) != 1:
                    raise ValueError("FC05 requires exactly one value (0/1 or true/false)")
                coil_values = coils
            elif fc == 6:
                regs = parse_register_values(value_text)
                if len(regs) != 1:
                    raise ValueError("FC06 requires exactly one register value")
                register_values = regs
            elif fc == 15:
                coil_values = parse_coil_values(value_text)
            elif fc == 16:
                register_values = parse_register_values(value_text)
        except ValueError as exc:
            self.write_status_label.setText(f"Parse error: {exc}")
            return

        # Build settings
        try:
            settings = SerialConnectionSettings(
                port=str(port),
                baudrate=self.baudrate.value(),
                parity=self.parity.currentText(),
                stopbits=float(self.stopbits.currentText()),
                timeout=self.timeout.value(),
            )
        except ValueError as exc:
            self.write_status_label.setText(f"Settings error: {exc}")
            return

        # Final confirmation dialog
        fc_names = {5: "FC05 Write Single Coil", 6: "FC06 Write Single Register",
                    15: "FC15 Write Multiple Coils", 16: "FC16 Write Multiple Registers"}
        values_summary = (
            str(coil_values) if coil_values is not None else str(register_values)
        )
        confirm_text = (
            f"⚠  WRITE OPERATION CONFIRMATION\n\n"
            f"COM:        {settings.port}\n"
            f"Baudrate:   {settings.baudrate}  Parity: {settings.parity}  "
            f"Stopbits: {settings.stopbits}\n"
            f"Slave ID:   {self.slave_id.value()}\n"
            f"Function:   {fc_names.get(fc, str(fc))}\n"
            f"Address:    {addr}\n"
            f"Values:     {values_summary}\n\n"
            "This will transmit a write request to the device.\n"
            "Make sure you are authorized to modify this equipment.\n\n"
            "Confirm write?"
        )
        reply = QMessageBox.question(
            self,
            "Confirm Modbus Write",
            confirm_text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            self.write_status_label.setText("Write cancelled.")
            return

        write_request = WriteRequest(
            settings=settings,
            slave_id=self.slave_id.value(),
            function_code=fc,
            address=addr,
            coil_values=coil_values,
            register_values=register_values,
        )
        self._start_write_worker(write_request)

    def _start_write_worker(self, request: WriteRequest) -> None:
        port = request.settings.port
        try:
            self._mode_manager.reserve(port, AppMode.MASTER_READ, ADVANCED_MASTER_OWNER)
            self._reserved_port = port
        except RuntimeError as exc:
            self.write_status_label.setText(f"Port reservation error: {exc}")
            return

        self._write_busy = True
        self.send_write_button.setEnabled(False)
        self.write_status_label.setText("Writing…")

        self._write_thread = QThread(self)
        self._write_worker = AdvancedWriteWorker(request)
        self._write_worker.moveToThread(self._write_thread)
        self._write_thread.started.connect(self._write_worker.run)
        self._write_worker.finished.connect(self._on_write_success)
        self._write_worker.failed.connect(self._on_write_error)
        self._write_worker.finished.connect(self._write_thread.quit)
        self._write_worker.failed.connect(self._write_thread.quit)
        self._write_thread.finished.connect(self._cleanup_write_worker)
        self._write_thread.start()

    @Slot(str)
    def _on_write_success(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.write_status_label.setText(f"Write OK [{ts}]: {message}")
        self._release_port()

    @Slot(str)
    def _on_write_error(self, message: str) -> None:
        self.write_status_label.setText(f"Write error: {message}")
        self._release_port()

    @Slot()
    def _cleanup_write_worker(self) -> None:
        self._write_busy = False
        if self._write_worker is not None:
            self._write_worker.deleteLater()
            self._write_worker = None
        if self._write_thread is not None:
            self._write_thread.deleteLater()
            self._write_thread = None
        self._update_write_unlock_state()

    # ── shared helpers ────────────────────────────────────────────────────

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

    def _populate_table(self, rows: list[DecodeRow]) -> None:
        self.registers_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.registers_table.setItem(i, 0, QTableWidgetItem(str(row.offset)))
            self.registers_table.setItem(i, 1, QTableWidgetItem(str(row.address)))
            self.registers_table.setItem(i, 2, QTableWidgetItem(str(row.raw_uint16)))
            self.registers_table.setItem(i, 3, QTableWidgetItem(row.hex_str))
            self.registers_table.setItem(i, 4, QTableWidgetItem(row.bin_str))
            self.registers_table.setItem(i, 5, QTableWidgetItem(row.decoded))
