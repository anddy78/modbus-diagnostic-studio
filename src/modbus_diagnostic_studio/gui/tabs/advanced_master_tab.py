"""Advanced Master tab — generic Modbus RTU read (FC01-FC04) and guarded write."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.gui.help import set_help
from modbus_diagnostic_studio.gui.profile_views import (
    decode_format_for_register_type,
    populate_register_preview_table,
    selected_register_from_table,
)
from modbus_diagnostic_studio.master.client import ModbusMasterClient
from modbus_diagnostic_studio.master.operation_log import (
    MAX_LOG_ENTRIES,
    MasterOperationLogEntry,
    write_log_csv,
    write_log_jsonl,
)
from modbus_diagnostic_studio.models.diagnostic_session import DiagnosticSessionEvent
from modbus_diagnostic_studio.models.connection import SerialConnectionSettings
from modbus_diagnostic_studio.profiles.loader import list_builtin_profiles, load_builtin_profile
from modbus_diagnostic_studio.services.application_state import ApplicationState
from modbus_diagnostic_studio.services.mode_manager import AppMode, ModeManager
from modbus_diagnostic_studio.transports.rtu_transport import RtuTransport
from modbus_diagnostic_studio.transports.serial_ports import list_serial_ports

ADVANCED_MASTER_OWNER = "advanced_master_tab"

_WRITE_CONFIRM_TOKEN = "WRITE"

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

_BIT_FC = frozenset({1, 2})
_REG_FC = frozenset({3, 4})


# ── pure value-parsing helpers ────────────────────────────────────────────────


def parse_coil_values(text: str) -> list[bool]:
    """Parse comma- or space-separated coil values from *text*.

    Accepts: 1, 0, true, false (case-insensitive).
    Rejects all other tokens.
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

    Accepts decimal or 0x-prefixed hex. All values must be 0..65535.
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


# ── pure decode helpers ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class DecodeRow:
    """One row in the decoded register/bit table."""

    offset: int
    address: int
    raw_uint16: int
    hex_str: str
    bin_str: str
    decoded: str


def decode_bits(bits: list[bool], start_address: int) -> list[DecodeRow]:
    """Produce one DecodeRow per bit with ON/OFF decoded value."""
    rows: list[DecodeRow] = []
    for i, bit in enumerate(bits):
        raw = int(bit)
        rows.append(DecodeRow(
            offset=i,
            address=start_address + i,
            raw_uint16=raw,
            hex_str=f"0x{raw:04X}",
            bin_str=f"{raw:016b}",
            decoded="ON" if bit else "OFF",
        ))
    return rows


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
                rows.append(DecodeRow(*_base_row(i), decoded=_decode_pair(pair, fmt)))
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
        return str(raw32 - 0x100000000 if raw32 & 0x80000000 else raw32)
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
    """One raw Modbus read request (bits or registers)."""

    settings: SerialConnectionSettings
    slave_id: int
    function_code: int
    address: int
    quantity: int


class AdvancedReadWorker(QObject):
    """Worker that opens a transport, reads raw data (bits or registers), then closes."""

    finished = Signal(object)   # list[bool] for FC01/02, list[int] for FC03/04
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
            fc = self._request.function_code
            sid = self._request.slave_id
            addr = self._request.address
            qty = self._request.quantity

            if fc == 1:
                data = client.read_coils(sid, addr, qty)
            elif fc == 2:
                data = client.read_discrete_inputs(sid, addr, qty)
            elif fc == 3:
                data = client.read_holding_registers(sid, addr, qty)
            else:
                data = client.read_input_registers(sid, addr, qty)

            self.finished.emit(data)
        except Exception as exc:
            self.failed.emit(_friendly_serial_error(str(exc)))
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

    finished = Signal(str)
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
                self.finished.emit(f"FC05 OK — address {r.address} = {confirmed}")
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
            self.failed.emit(_friendly_serial_error(str(exc)))
        finally:
            try:
                transport.close()
            except Exception:
                pass


# ── tab widget ────────────────────────────────────────────────────────────────


class AdvancedMasterTab(QWidget):
    """Generic Modbus RTU read (FC01-FC04) and guarded write tab for technical users."""

    def __init__(self, app_state: ApplicationState | None = None) -> None:
        super().__init__()

        self._app_state = app_state or ApplicationState()
        self._mode_manager = self._app_state.mode_manager
        self._reserved_port: str | None = None

        # read state
        self._thread: QThread | None = None
        self._worker: AdvancedReadWorker | None = None
        self._continuous_timer: QTimer | None = None
        self._reading_busy: bool = False
        self._cycle_count: int = 0
        self._error_count: int = 0
        self._last_error: str = ""
        self._last_read_fc: int = 3
        self._last_read_request: AdvancedReadRequest | None = None

        # write state
        self._write_thread: QThread | None = None
        self._write_worker: AdvancedWriteWorker | None = None
        self._write_busy: bool = False
        self._last_write_request: WriteRequest | None = None

        # log
        self._operation_log: list[MasterOperationLogEntry] = []

        # ── status ────────────────────────────────────────────────────────
        self.status_label = QLabel(
            "Advanced reads, decoding, logging, and guarded writes."
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
        self.function_combo.addItem("FC01 — Read Coils", 1)
        self.function_combo.addItem("FC02 — Read Discrete Inputs", 2)
        self.function_combo.addItem("FC03 — Read Holding Registers", 3)
        self.function_combo.addItem("FC04 — Read Input Registers", 4)
        self.function_combo.setCurrentIndex(2)  # default FC03
        self.function_combo.currentIndexChanged.connect(self._on_read_function_changed)

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

        self.profile_combo = QComboBox()
        self.profile_combo.addItem("None / Raw only", None)
        for profile_id in list_builtin_profiles():
            self.profile_combo.addItem(profile_id, profile_id)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)

        self.known_registers_table = QTableWidget(0, 7)
        self.known_registers_table.setHorizontalHeaderLabels(
            ["Variable", "Address", "Function", "Type", "Quantity", "Unit", "Description"]
        )
        self.known_registers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.known_registers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.known_registers_table.setMinimumHeight(220)
        self.known_registers_table.itemSelectionChanged.connect(
            self._apply_selected_known_register
        )

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
            ["Offset", "Address", "Raw", "Hex", "Binary", "Decoded value"]
        )
        self.registers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.registers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.registers_table.setMinimumHeight(260)

        # ── write section ─────────────────────────────────────────────────
        self._build_write_section()

        # ── log section ───────────────────────────────────────────────────
        self._build_log_section()

        self._build_layout()
        self._attach_help()
        self.refresh_ports()

    # ── write section builder ─────────────────────────────────────────────

    def _build_write_section(self) -> None:
        self.write_warning_label = QLabel(
            "⚠  ACTIVE WRITE MODE — CAN MODIFY REAL DEVICES\n"
            "Writes are disabled by default.\n"
            "Only use on equipment you are authorized to test."
        )
        warn_font = self.write_warning_label.font()
        warn_font.setBold(True)
        self.write_warning_label.setFont(warn_font)

        self.write_enable_check = QCheckBox("Enable Modbus Write Mode")
        self.write_enable_check.setChecked(False)
        self.write_enable_check.stateChanged.connect(self._update_write_unlock_state)

        self.write_risk_check = QCheckBox("I understand this can modify a real device")
        self.write_risk_check.setChecked(False)
        self.write_risk_check.setEnabled(False)
        self.write_risk_check.stateChanged.connect(self._update_write_unlock_state)

        self.write_confirm_edit = QLineEdit()
        self.write_confirm_edit.setPlaceholderText('Type "WRITE" to unlock')
        self.write_confirm_edit.setEnabled(False)
        self.write_confirm_edit.textChanged.connect(self._update_write_unlock_state)

        self.write_function_combo = QComboBox()
        self.write_function_combo.addItem("FC05 — Write Single Coil", 5)
        self.write_function_combo.addItem("FC06 — Write Single Register", 6)
        self.write_function_combo.addItem("FC15 — Write Multiple Coils", 15)
        self.write_function_combo.addItem("FC16 — Write Multiple Registers", 16)
        self.write_function_combo.setEnabled(False)
        self.write_function_combo.currentIndexChanged.connect(self._update_write_value_hint)

        self.write_address = QSpinBox()
        self.write_address.setRange(0, 65535)
        self.write_address.setEnabled(False)

        self.write_value_hint = QLabel("Value (0/1 or true/false):")
        self.write_value_edit = QLineEdit()
        self.write_value_edit.setPlaceholderText("e.g. 1")
        self.write_value_edit.setEnabled(False)

        self.send_write_button = QPushButton("Send Write")
        self.send_write_button.setEnabled(False)
        self.send_write_button.clicked.connect(self._send_write)

        self.write_status_label = QLabel("Write status: —")

    # ── log section builder ───────────────────────────────────────────────

    def _build_log_section(self) -> None:
        self.log_table = QTableWidget(0, 9)
        self.log_table.setHorizontalHeaderLabels(
            ["Timestamp", "Op", "COM", "Slave", "FC", "Address", "Qty/Values", "Status", "Message"]
        )
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setMinimumHeight(220)

        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self._clear_log)

        self.export_log_csv_button = QPushButton("Export Log CSV")
        self.export_log_csv_button.clicked.connect(self._export_log_csv)

        self.export_log_jsonl_button = QPushButton("Export Log JSONL")
        self.export_log_jsonl_button.clicked.connect(self._export_log_jsonl)

    # ── layout ────────────────────────────────────────────────────────────

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
        form.addRow("Register profile", self.profile_combo)

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

        # write group
        write_group = QGroupBox("Write Mode - Locked by default")
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
        write_group.setMinimumHeight(260)
        self.write_group = write_group

        # log group
        log_group = QGroupBox("Master Operation Log")
        log_btn_row = QHBoxLayout()
        log_btn_row.addWidget(self.clear_log_button)
        log_btn_row.addWidget(self.export_log_csv_button)
        log_btn_row.addWidget(self.export_log_jsonl_button)
        log_btn_row.addStretch()
        log_vbox = QVBoxLayout()
        log_vbox.addLayout(log_btn_row)
        log_vbox.addWidget(self.log_table)
        log_group.setLayout(log_vbox)
        log_group.setMinimumHeight(320)
        self.log_group = log_group

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.addWidget(self.status_label)
        content_layout.addLayout(form)
        content_layout.addLayout(btn_row)
        content_layout.addLayout(meta_row)
        content_layout.addWidget(QLabel("Known registers"))
        content_layout.addWidget(self.known_registers_table)
        content_layout.addWidget(QLabel("Registers / Bits"))
        content_layout.addWidget(self.registers_table)
        content_layout.addWidget(write_group)
        content_layout.addWidget(log_group)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        layout = QVBoxLayout()
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _attach_help(self) -> None:
        set_help(
            self.function_combo,
            "Function",
            "Choose the Modbus read function. FC01/FC02 read bits, FC03/FC04 read registers.",
        )
        set_help(
            self.start_address,
            "Address",
            "Start address of the Modbus block for the next active read request.",
        )
        set_help(
            self.quantity,
            "Quantity",
            "Number of bits or registers to read from the selected start address.",
        )
        set_help(
            self.decode_format,
            "Decode format",
            "Display raw registers as integer, float, hex, binary, or float32 word-swap.",
        )
        set_help(
            self.known_registers_table,
            "Known registers",
            "Profile-guided known registers. Selecting one updates read function, address, quantity, and decode format, but does not send a request.",
        )
        set_help(
            self.write_enable_check,
            "Write Mode unlock",
            "Write mode stays locked until you explicitly enable it, acknowledge the risk, and type WRITE.",
        )
        set_help(
            self.send_write_button,
            "Send Write",
            "Transmit a Modbus write request only after the protection steps are satisfied and the confirmation dialog is accepted.",
        )

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
            "Advanced reads, decoding, logging, and guarded writes. "
            f"{self.port_combo.count()} port(s) detected."
        )

    # ── function selector adapts quantity + decode ────────────────────────

    def _on_read_function_changed(self) -> None:
        fc = int(self.function_combo.currentData())
        if fc in _BIT_FC:
            self.quantity.setRange(1, 2000)
            if self.quantity.value() > 2000:
                self.quantity.setValue(2000)
            self.decode_format.setEnabled(False)
        else:
            self.quantity.setRange(1, 125)
            if self.quantity.value() > 125:
                self.quantity.setValue(125)
            self.decode_format.setEnabled(True)

    def _on_profile_changed(self) -> None:
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            self.known_registers_table.setRowCount(0)
            return
        profile = load_builtin_profile(str(profile_id))
        populate_register_preview_table(
            self.known_registers_table,
            profile,
            include_function=True,
            include_bank=False,
        )
        self.status_label.setText(
            f"Selected profile {profile.profile_id}. Choose a known register to prefill the read fields."
        )

    def _apply_selected_known_register(self) -> None:
        selected = selected_register_from_table(self.known_registers_table)
        if selected is None:
            return
        function_index = self.function_combo.findData(int(selected["function_code"]))
        if function_index >= 0:
            self.function_combo.setCurrentIndex(function_index)
        self.start_address.setValue(int(selected["address"]))
        self.quantity.setValue(int(selected["quantity"]))

        profile_id = self.profile_combo.currentData()
        note = ""
        if profile_id is not None:
            profile = load_builtin_profile(str(profile_id))
            decode_value = decode_format_for_register_type(str(selected["type"]))
            if selected["type"] == "float32" and getattr(profile, "word_order", "normal") == "swap":
                decode_index = self.decode_format.findData("float32 word-swap")
                if decode_index >= 0:
                    self.decode_format.setCurrentIndex(decode_index)
                else:
                    decode_index = self.decode_format.findData(decode_value)
                    if decode_index >= 0:
                        self.decode_format.setCurrentIndex(decode_index)
                    note = " Word-swap hint was not available, using float32."
            else:
                decode_index = self.decode_format.findData(decode_value)
                if decode_index >= 0:
                    self.decode_format.setCurrentIndex(decode_index)

        self.status_label.setText(
            f"Selected known register {selected['variable']}. Press Read Once to query.{note}"
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
        self._last_read_fc = request.function_code
        self._last_read_request = request
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
    def _on_read_success(self, data: object) -> None:
        self._cycle_count += 1
        ts = datetime.now().strftime("%H:%M:%S")
        self.last_read_label.setText(f"Last read: {ts}")
        self._update_meta_labels()

        req = self._last_read_request
        fc = self._last_read_fc

        if fc in _BIT_FC and isinstance(data, list):
            rows = decode_bits(data, self.start_address.value())  # type: ignore[arg-type]
            values_str = f"{len(data)} bit(s)"
        else:
            fmt = str(self.decode_format.currentData())
            rows = decode_registers(data, self.start_address.value(), fmt)  # type: ignore[arg-type]
            values_str = f"{len(data)} register(s)"  # type: ignore[arg-type]

        self._set_status(
            f"Read OK — {values_str} — cycle {self._cycle_count} — {ts}"
        )
        self._populate_table(rows)
        self._release_port()

        if req is not None:
            self._log_operation(
                operation="read",
                com_port=req.settings.port,
                slave_id=req.slave_id,
                function_code=req.function_code,
                address=req.address,
                quantity=req.quantity,
                values=values_str,
                status="ok",
                message=f"Read OK at {ts}",
            )

    @Slot(str)
    def _on_read_error(self, message: str) -> None:
        self._error_count += 1
        self._last_error = message
        self._update_meta_labels()
        self._set_status(f"Error: {message}")
        self._release_port()

        req = self._last_read_request
        if req is not None:
            self._log_operation(
                operation="read",
                com_port=req.settings.port,
                slave_id=req.slave_id,
                function_code=req.function_code,
                address=req.address,
                quantity=req.quantity,
                values="-",
                status="error",
                message=message,
            )

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

        fc_names = {
            5: "FC05 Write Single Coil", 6: "FC06 Write Single Register",
            15: "FC15 Write Multiple Coils", 16: "FC16 Write Multiple Registers",
        }
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
            qty = len(coil_values or register_values or [])
            self._log_operation(
                operation="write",
                com_port=settings.port,
                slave_id=self.slave_id.value(),
                function_code=fc,
                address=addr,
                quantity=qty,
                values=values_summary,
                status="cancelled",
                message="User cancelled confirmation dialog",
            )
            return

        write_request = WriteRequest(
            settings=settings,
            slave_id=self.slave_id.value(),
            function_code=fc,
            address=addr,
            coil_values=coil_values,
            register_values=register_values,
        )
        self._last_write_request = write_request
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

        req = self._last_write_request
        if req is not None:
            qty = len(req.coil_values or req.register_values or [])
            vals = str(req.coil_values) if req.coil_values is not None else str(req.register_values)
            self._log_operation(
                operation="write",
                com_port=req.settings.port,
                slave_id=req.slave_id,
                function_code=req.function_code,
                address=req.address,
                quantity=qty,
                values=vals,
                status="ok",
                message=message,
            )

    @Slot(str)
    def _on_write_error(self, message: str) -> None:
        self.write_status_label.setText(f"Write error: {message}")
        self._release_port()

        req = self._last_write_request
        if req is not None:
            qty = len(req.coil_values or req.register_values or [])
            vals = str(req.coil_values) if req.coil_values is not None else str(req.register_values)
            self._log_operation(
                operation="write",
                com_port=req.settings.port,
                slave_id=req.slave_id,
                function_code=req.function_code,
                address=req.address,
                quantity=qty,
                values=vals,
                status="error",
                message=message,
            )

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

    # ── log management ────────────────────────────────────────────────────

    def _log_operation(
        self,
        operation: str,
        com_port: str,
        slave_id: int,
        function_code: int,
        address: int,
        quantity: int | None,
        values: str,
        status: str,
        message: str,
    ) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = MasterOperationLogEntry(
            timestamp=ts,
            operation=operation,
            com_port=com_port,
            slave_id=slave_id,
            function_code=function_code,
            address=address,
            quantity=quantity,
            values=values,
            status=status,
            message=message,
        )
        if len(self._operation_log) >= MAX_LOG_ENTRIES:
            self._operation_log.pop(0)
            if self.log_table.rowCount() > 0:
                self.log_table.removeRow(0)
        self._operation_log.append(entry)
        self._append_log_row(entry)
        self._record_session_event(entry)

    def _append_log_row(self, entry: MasterOperationLogEntry) -> None:
        row = self.log_table.rowCount()
        self.log_table.insertRow(row)
        for col, val in enumerate([
            entry.timestamp,
            entry.operation,
            entry.com_port,
            str(entry.slave_id),
            f"FC{entry.function_code:02d}",
            str(entry.address),
            str(entry.quantity) if entry.quantity is not None else entry.values,
            entry.status,
            entry.message,
        ]):
            self.log_table.setItem(row, col, QTableWidgetItem(val))
        self.log_table.scrollToBottom()

    def _record_session_event(self, entry: MasterOperationLogEntry) -> None:
        """Mirror an operation log entry into the active diagnostic session if one exists."""
        severity = "info"
        event_type = entry.operation
        if entry.status == "cancelled":
            severity = "warning"
        elif entry.status == "error":
            severity = "error"
            if "timed out" in entry.message.lower() or "no response" in entry.message.lower():
                event_type = "timeout"
        try:
            self._app_state.add_session_event(
                DiagnosticSessionEvent(
                    timestamp=entry.timestamp,
                    source="advanced_master",
                    event_type=event_type,
                    severity=severity,
                    summary=entry.message,
                    details={
                        "operation": entry.operation,
                        "com_port": entry.com_port,
                        "slave_id": entry.slave_id,
                        "function_code": entry.function_code,
                        "address": entry.address,
                        "quantity": entry.quantity,
                        "values": entry.values,
                        "status": entry.status,
                    },
                )
            )
        except Exception:
            return

    def _clear_log(self) -> None:
        self._operation_log.clear()
        self.log_table.setRowCount(0)

    def _export_log_csv(self) -> None:
        if not self._operation_log:
            self.status_label.setText("No log entries to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Log CSV", "master_log.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            write_log_csv(path, self._operation_log)
            self.status_label.setText(f"Log exported to: {path}")
        except Exception as exc:
            self.status_label.setText(f"Export error: {exc}")

    def _export_log_jsonl(self) -> None:
        if not self._operation_log:
            self.status_label.setText("No log entries to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Log JSONL", "master_log.jsonl", "JSONL files (*.jsonl)"
        )
        if not path:
            return
        try:
            write_log_jsonl(path, self._operation_log)
            self.status_label.setText(f"Log exported to: {path}")
        except Exception as exc:
            self.status_label.setText(f"Export error: {exc}")

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


def _friendly_serial_error(message: str) -> str:
    lower = message.lower()
    if "timed out" in lower or "no response" in lower:
        return (
            "No response received from device. Check COM port, wiring, slave ID, "
            f"baudrate, parity and stop bits. Details: {message}"
        )
    return message
