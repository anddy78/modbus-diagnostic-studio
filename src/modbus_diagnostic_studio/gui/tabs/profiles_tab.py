"""Built-in profiles tab."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.profiles.loader import (
    list_builtin_profiles,
    load_builtin_profile,
)


class ProfilesTab(QWidget):
    """List bundled register profiles."""

    def __init__(self) -> None:
        super().__init__()

        self.status_label = QLabel("Built-in register profiles bundled with the app.")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Profile ID", "Name", "Status", "Registers"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.refresh_profiles()

    def refresh_profiles(self) -> None:
        """Load built-in profiles and show a compact summary."""
        profile_ids = list_builtin_profiles()
        self.table.setRowCount(len(profile_ids))
        for row, profile_id in enumerate(profile_ids):
            profile = load_builtin_profile(profile_id)
            self.table.setItem(row, 0, QTableWidgetItem(profile.profile_id))
            self.table.setItem(row, 1, QTableWidgetItem(profile.name))
            self.table.setItem(row, 2, QTableWidgetItem(profile.status))
            self.table.setItem(row, 3, QTableWidgetItem(str(len(profile.registers))))
        self.status_label.setText(f"{len(profile_ids)} built-in profile(s) available.")
