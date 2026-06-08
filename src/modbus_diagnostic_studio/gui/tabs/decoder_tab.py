"""Raw RTU decoder tab."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.core.decoder import decode_raw_rtu_frame


class DecoderTab(QWidget):
    """Decode pasted raw Modbus RTU hex frames."""

    DISPLAY_FIELDS = [
        "raw_hex",
        "classification",
        "crc_ok",
        "slave_id",
        "function_code",
        "address",
        "quantity",
        "byte_count",
        "registers",
        "exception_code",
        "error",
    ]

    def __init__(self) -> None:
        super().__init__()

        self.status_label = QLabel("Offline decoder for pasted RTU frames.")
        self.input = QTextEdit()
        self.input.setPlaceholderText("01 03 00 00 00 0A C5 CD")
        self.input.setAcceptRichText(False)

        self.decode_button = QPushButton("Decode")
        self.decode_button.clicked.connect(self.decode)

        self.value_labels: dict[str, QLabel] = {
            field: QLabel("") for field in self.DISPLAY_FIELDS
        }

        form = QFormLayout()
        for field, label in self.value_labels.items():
            label.setTextInteractionFlags(label.textInteractionFlags())
            form.addRow(field, label)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(QLabel("Raw hex frame"))
        layout.addWidget(self.input)
        layout.addWidget(self.decode_button)
        layout.addLayout(form)
        self.setLayout(layout)

    def decode(self) -> None:
        """Decode the current raw hex input."""
        decoded = decode_raw_rtu_frame(self.input.toPlainText())
        for field, label in self.value_labels.items():
            value = decoded.get(field, "")
            if isinstance(value, list):
                label.setText(", ".join(str(item) for item in value))
            else:
                label.setText(str(value))
