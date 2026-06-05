"""Connection tab for passive port discovery."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.transports.serial_ports import list_serial_ports


class ConnectionTab(QWidget):
    """List serial ports without opening them."""

    def __init__(self) -> None:
        super().__init__()

        self.status_label = QLabel("Ports are listed only; no serial port is opened.")
        self.refresh_button = QPushButton("Refresh Ports")
        self.refresh_button.clicked.connect(self.refresh_ports)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Device", "Description", "HWID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.refresh_ports()

    def refresh_ports(self) -> None:
        """Refresh the serial port table without opening ports."""
        ports = list_serial_ports()
        self.table.setRowCount(len(ports))
        for row, port in enumerate(ports):
            self.table.setItem(row, 0, QTableWidgetItem(port.device))
            self.table.setItem(row, 1, QTableWidgetItem(port.description))
            self.table.setItem(row, 2, QTableWidgetItem(port.hwid))
        self.status_label.setText(f"{len(ports)} port(s) detected. No port opened.")
