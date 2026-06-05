"""Active Master Read tab."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal, Slot
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
from modbus_diagnostic_studio.profiles.decoder import (
    DecodedProfileValue,
    decode_profile_registers,
)
from modbus_diagnostic_studio.profiles.loader import (
    list_builtin_profiles,
    load_builtin_profile,
)
from modbus_diagnostic_studio.services.application_state import ApplicationState
from modbus_diagnostic_studio.services.mode_manager import AppMode, ModeManager
from modbus_diagnostic_studio.transports.rtu_transport import RtuTransport
from modbus_diagnostic_studio.transports.serial_ports import list_serial_ports

MASTER_READ_OWNER = "master_read_tab"


@dataclass(frozen=True)
class MasterReadRequest:
    """Settings for one explicit active master read."""

    settings: SerialConnectionSettings
    slave_id: int
    function_code: int
    address: int
    quantity: int


@dataclass(frozen=True)
class MasterReadResult:
    """Registers returned by one active master read."""

    start_address: int
    registers: list[int]


class MasterReadWorker(QObject):
    """Worker that performs one active Modbus master read."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, request: MasterReadRequest) -> None:
        super().__init__()
        self.request = request

    @Slot()
    def run(self) -> None:
        """Open transport, read once, and close transport."""
        transport = RtuTransport(self.request.settings)
        try:
            transport.open()
            client = ModbusMasterClient(transport)
            if self.request.function_code == 3:
                registers = client.read_holding_registers(
                    self.request.slave_id,
                    self.request.address,
                    self.request.quantity,
                )
            else:
                registers = client.read_input_registers(
                    self.request.slave_id,
                    self.request.address,
                    self.request.quantity,
                )
            self.finished.emit(
                MasterReadResult(
                    start_address=self.request.address,
                    registers=registers,
                )
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            try:
                transport.close()
            except Exception:
                pass


class MasterReadTab(QWidget):
    """Manual active RTU read UI."""

    def __init__(self, app_state: ApplicationState | None = None) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: MasterReadWorker | None = None
        self._app_state = app_state or ApplicationState()
        self._mode_manager = self._app_state.mode_manager
        self._reserved_port: str | None = None

        self.status_label = QLabel("Active master mode. A request is sent only when Read is pressed.")

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

        self.function = QComboBox()
        self.function.addItem("FC03 Holding Registers", 3)
        self.function.addItem("FC04 Input Registers", 4)

        self.address = QSpinBox()
        self.address.setRange(0, 65535)
        self.address.setValue(0)

        self.quantity = QSpinBox()
        self.quantity.setRange(1, 125)
        self.quantity.setValue(2)

        self.profile_combo = QComboBox()
        self.profile_combo.addItem("None / Raw only", None)
        for profile_id in list_builtin_profiles():
            self.profile_combo.addItem(profile_id, profile_id)

        self.read_button = QPushButton("Read")
        self.read_button.clicked.connect(self.read_once)

        self.raw_table = QTableWidget(0, 4)
        self.raw_table.setHorizontalHeaderLabels(["Offset", "Address", "uint16", "Hex"])
        self.raw_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.decoded_table = QTableWidget(0, 5)
        self.decoded_table.setHorizontalHeaderLabels(
            ["Variable", "Value", "Unit", "Address", "Description"]
        )
        self.decoded_table.setEditTriggers(QTableWidget.NoEditTriggers)

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
        form.addRow("Slave ID", self.slave_id)
        form.addRow("Function", self.function)
        form.addRow("Address", self.address)
        form.addRow("Quantity", self.quantity)
        form.addRow("Profile", self.profile_combo)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addLayout(form)
        layout.addWidget(self.read_button)
        layout.addWidget(QLabel("Raw registers"))
        layout.addWidget(self.raw_table)
        layout.addWidget(QLabel("Profile decoded values"))
        layout.addWidget(self.decoded_table)
        self.setLayout(layout)

    def refresh_ports(self) -> None:
        """Refresh available ports without opening them."""
        current = self.port_combo.currentData()
        self.port_combo.clear()
        for port in list_serial_ports():
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)
        if current is not None:
            index = self.port_combo.findData(current)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        self.status_label.setText(f"{self.port_combo.count()} port(s) detected. Active read sends one request.")

    def read_once(self) -> None:
        """Start one active master read."""
        port = self.port_combo.currentData()
        if not port:
            self._set_error("No COM selected.")
            return
        port = str(port)

        try:
            self._mode_manager.reserve(port, AppMode.MASTER_READ, MASTER_READ_OWNER)
            self._reserved_port = port
        except RuntimeError as exc:
            self._set_error(str(exc))
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
            self._release_reserved_port()
            self._set_error(f"Invalid settings: {exc}")
            return

        request = MasterReadRequest(
            settings=settings,
            slave_id=self.slave_id.value(),
            function_code=int(self.function.currentData()),
            address=self.address.value(),
            quantity=self.quantity.value(),
        )
        self.read_button.setEnabled(False)
        self.status_label.setText("Reading... active request in progress.")

        self._thread = QThread(self)
        self._worker = MasterReadWorker(request)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._handle_success)
        self._worker.failed.connect(self._handle_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    @Slot(object)
    def _handle_success(self, result: MasterReadResult) -> None:
        self._populate_raw_table(result.start_address, result.registers)
        self._populate_decoded_table(result.start_address, result.registers)
        self.status_label.setText(f"Read OK: {len(result.registers)} register(s). Port closed.")
        self._release_reserved_port()

    @Slot(str)
    def _handle_error(self, message: str) -> None:
        self._set_error(message)
        self._release_reserved_port()

    @Slot()
    def _cleanup_worker(self) -> None:
        self.read_button.setEnabled(True)
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None

    def _set_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")

    def _release_reserved_port(self) -> None:
        if self._reserved_port is None:
            return
        self._mode_manager.release(self._reserved_port, MASTER_READ_OWNER)
        self._reserved_port = None

    def _populate_raw_table(self, start_address: int, registers: list[int]) -> None:
        self.raw_table.setRowCount(len(registers))
        for offset, value in enumerate(registers):
            self.raw_table.setItem(offset, 0, QTableWidgetItem(str(offset)))
            self.raw_table.setItem(offset, 1, QTableWidgetItem(str(start_address + offset)))
            self.raw_table.setItem(offset, 2, QTableWidgetItem(str(value)))
            self.raw_table.setItem(offset, 3, QTableWidgetItem(f"0x{value:04X}"))

    def _populate_decoded_table(self, start_address: int, registers: list[int]) -> None:
        profile_id = self.profile_combo.currentData()
        if profile_id is None:
            self.decoded_table.setRowCount(0)
            return

        profile = load_builtin_profile(str(profile_id))
        decoded = decode_profile_registers(profile, start_address, registers)
        self.decoded_table.setRowCount(len(decoded))
        for row, value in enumerate(decoded):
            self._set_decoded_row(row, value)
        if not decoded:
            self.status_label.setText(
                "Read OK, but selected profile has no registers applicable to this block."
            )

    def _set_decoded_row(self, row: int, value: DecodedProfileValue) -> None:
        self.decoded_table.setItem(row, 0, QTableWidgetItem(value.variable))
        self.decoded_table.setItem(row, 1, QTableWidgetItem(str(value.value)))
        self.decoded_table.setItem(row, 2, QTableWidgetItem(value.unit or ""))
        self.decoded_table.setItem(row, 3, QTableWidgetItem(str(value.address)))
        self.decoded_table.setItem(row, 4, QTableWidgetItem(value.description))
