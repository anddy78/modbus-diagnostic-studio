"""Profile Manager tab for device and register profile inspection."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modbus_diagnostic_studio.device_profiles.loader import load_all_device_profiles
from modbus_diagnostic_studio.device_profiles.validator import validate_device_profile, validate_role_links
from modbus_diagnostic_studio.gui.help import set_help
from modbus_diagnostic_studio.profiles.loader import list_builtin_profiles, load_builtin_profile
from modbus_diagnostic_studio.services.paths import (
    ensure_runtime_dirs,
    user_device_profiles_dir,
)
from modbus_diagnostic_studio.sniffer.communication_profiles import (
    list_builtin_communication_profiles,
)


class ProfileManagerTab(QWidget):
    """Inspect role-oriented device profiles and existing register profiles."""

    def __init__(self) -> None:
        super().__init__()
        self._device_profiles = []
        self._device_profile_errors: list[str] = []

        self.status_label = QLabel("Profile Manager loads built-in and user profile metadata only.")

        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(self.reload_profiles)
        self.open_user_folder_button = QPushButton("Open User Device Profiles Folder")
        self.open_user_folder_button.clicked.connect(self.open_user_device_profiles_folder)
        self.import_button = QPushButton("Import Device Profile YAML")
        self.import_button.clicked.connect(self.import_device_profile_yaml)
        self.validate_button = QPushButton("Validate Selected")
        self.validate_button.clicked.connect(self.validate_selected_profile)

        self.device_profiles_table = QTableWidget(0, 8)
        self.device_profiles_table.setHorizontalHeaderLabels(
            [
                "Device ID",
                "Name",
                "Manufacturer",
                "Model",
                "Device Type",
                "Status",
                "Source",
                "Roles",
            ]
        )
        self.device_profiles_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.device_profiles_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.device_profiles_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_profiles_table.itemSelectionChanged.connect(self._update_device_profile_preview)

        self.roles_table = QTableWidget(0, 5)
        self.roles_table.setHorizontalHeaderLabels(
            ["Role", "Profile Type", "Profile ID", "Enabled", "Description"]
        )
        self.roles_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.roles_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.roles_table.setSelectionBehavior(QTableWidget.SelectRows)

        self.validation_output = QTextEdit()
        self.validation_output.setReadOnly(True)
        self.validation_output.setMinimumHeight(120)

        self.register_profiles_table = QTableWidget(0, 5)
        self.register_profiles_table.setHorizontalHeaderLabels(
            ["Profile ID", "Name", "Status", "Registers", "Source"]
        )
        self.register_profiles_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.register_profiles_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.register_profiles_table.setSelectionBehavior(QTableWidget.SelectRows)

        self._build_layout()
        self._attach_help()
        self.reload_profiles()

    def _build_layout(self) -> None:
        button_row = QHBoxLayout()
        button_row.addWidget(self.reload_button)
        button_row.addWidget(self.open_user_folder_button)
        button_row.addWidget(self.import_button)
        button_row.addWidget(self.validate_button)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.addWidget(self.status_label)
        content_layout.addLayout(button_row)
        content_layout.addWidget(QLabel("Device Profiles"))
        content_layout.addWidget(self.device_profiles_table)

        preview_grid = QGridLayout()
        preview_grid.addWidget(QLabel("Role Links"), 0, 0)
        preview_grid.addWidget(self.roles_table, 1, 0)
        preview_grid.addWidget(QLabel("Validation"), 2, 0)
        preview_grid.addWidget(self.validation_output, 3, 0)
        content_layout.addLayout(preview_grid)

        content_layout.addWidget(QLabel("Register Profiles"))
        content_layout.addWidget(self.register_profiles_table)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        layout = QVBoxLayout()
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _attach_help(self) -> None:
        set_help(
            self.open_user_folder_button,
            "User Device Profiles Folder",
            "Open the writable folder where custom device profile YAML files are stored.",
        )
        set_help(
            self.import_button,
            "Import Device Profile YAML",
            "Copy a YAML file into the local user device profile folder. This does not open serial ports or run Modbus operations.",
        )
        set_help(
            self.validate_button,
            "Validate Selected",
            "Validate the selected device profile structure and linked profile ids.",
        )

    def reload_profiles(self) -> None:
        """Reload built-in and user profile summaries."""
        ensure_runtime_dirs()
        self._device_profiles, self._device_profile_errors = load_all_device_profiles(
            user_device_profiles_dir()
        )
        self._populate_device_profiles_table()
        self._populate_register_profiles_table()
        self._update_device_profile_preview()

        profile_count = len(self._device_profiles)
        error_count = len(self._device_profile_errors)
        if error_count:
            self.status_label.setText(
                f"Loaded {profile_count} device profile(s) with {error_count} user file issue(s)."
            )
        else:
            self.status_label.setText(f"Loaded {profile_count} device profile(s).")

    def open_user_device_profiles_folder(self) -> None:
        """Open the user device profile folder in the shell."""
        ensure_runtime_dirs()
        folder = user_device_profiles_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        self.status_label.setText(f"Opened: {folder}")

    def import_device_profile_yaml(self) -> None:
        """Open a file picker and import one YAML file into the user folder."""
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Import Device Profile YAML",
            str(Path.cwd()),
            "YAML files (*.yaml *.yml)",
        )
        if not path_str:
            return
        destination = self.import_device_profile_file(Path(path_str))
        if destination is None:
            return
        self.reload_profiles()
        self._select_device_profile_by_filename(destination)

    def import_device_profile_file(self, source_path: Path) -> Path | None:
        """Copy one YAML file into the user device profile directory."""
        ensure_runtime_dirs()
        if source_path.suffix.lower() not in {".yaml", ".yml"}:
            QMessageBox.warning(self, "Import Device Profile", "Select a .yaml or .yml file.")
            return None

        target_dir = user_device_profiles_dir()
        target_path = self._unique_destination(target_dir / source_path.name)
        shutil.copy2(source_path, target_path)

        messages = self._validate_profile_file(target_path)
        message_text = "\n".join(messages) if messages else "Imported without validation messages."
        QMessageBox.information(self, "Import Device Profile", message_text)
        return target_path

    def validate_selected_profile(self) -> None:
        """Validate the currently selected device profile and show the results."""
        profile = self._selected_device_profile()
        if profile is None:
            self.status_label.setText("Select a device profile first.")
            return

        messages = self._validation_messages_for_profile(profile)
        if not messages:
            messages = ["OK: no validation issues found"]
        self.validation_output.setPlainText("\n".join(messages))
        QMessageBox.information(self, "Validate Device Profile", "\n".join(messages))

    def _populate_device_profiles_table(self) -> None:
        self.device_profiles_table.setRowCount(len(self._device_profiles))
        for row, profile in enumerate(self._device_profiles):
            self.device_profiles_table.setItem(row, 0, QTableWidgetItem(profile.device_id))
            self.device_profiles_table.setItem(row, 1, QTableWidgetItem(profile.name))
            self.device_profiles_table.setItem(row, 2, QTableWidgetItem(profile.manufacturer))
            self.device_profiles_table.setItem(row, 3, QTableWidgetItem(profile.model))
            self.device_profiles_table.setItem(row, 4, QTableWidgetItem(profile.device_type))
            self.device_profiles_table.setItem(row, 5, QTableWidgetItem(profile.status))
            self.device_profiles_table.setItem(row, 6, QTableWidgetItem(profile.source))
            self.device_profiles_table.setItem(row, 7, QTableWidgetItem(str(len(profile.roles))))

    def _populate_register_profiles_table(self) -> None:
        profile_ids = list_builtin_profiles()
        self.register_profiles_table.setRowCount(len(profile_ids))
        for row, profile_id in enumerate(profile_ids):
            profile = load_builtin_profile(profile_id)
            self.register_profiles_table.setItem(row, 0, QTableWidgetItem(profile.profile_id))
            self.register_profiles_table.setItem(row, 1, QTableWidgetItem(profile.name))
            self.register_profiles_table.setItem(row, 2, QTableWidgetItem(profile.status))
            self.register_profiles_table.setItem(
                row, 3, QTableWidgetItem(str(len(profile.registers)))
            )
            self.register_profiles_table.setItem(row, 4, QTableWidgetItem("built-in"))

    def _update_device_profile_preview(self) -> None:
        profile = self._selected_device_profile()
        if profile is None:
            self.roles_table.setRowCount(0)
            if self._device_profile_errors:
                self.validation_output.setPlainText("\n".join(self._device_profile_errors))
            else:
                self.validation_output.setPlainText("Select a device profile to preview roles.")
            return

        self.roles_table.setRowCount(len(profile.roles))
        for row, role_link in enumerate(profile.roles):
            self.roles_table.setItem(row, 0, QTableWidgetItem(role_link.role))
            self.roles_table.setItem(row, 1, QTableWidgetItem(role_link.profile_type))
            self.roles_table.setItem(row, 2, QTableWidgetItem(role_link.profile_id))
            self.roles_table.setItem(row, 3, QTableWidgetItem("Yes" if role_link.enabled else "No"))
            self.roles_table.setItem(row, 4, QTableWidgetItem(role_link.description))

        messages = self._validation_messages_for_profile(profile)
        if not messages:
            messages = ["OK: no validation issues found"]
        self.validation_output.setPlainText("\n".join(messages))

    def _validation_messages_for_profile(self, profile) -> list[str]:
        register_ids = set(list_builtin_profiles())
        communication_ids = set(list_builtin_communication_profiles())
        messages = validate_device_profile(profile)
        messages.extend(
            validate_role_links(
                profile,
                available_register_profile_ids=register_ids,
                available_communication_profile_ids=communication_ids,
            )
        )
        return _deduplicate_messages(messages)

    def _selected_device_profile(self):
        row = self.device_profiles_table.currentRow()
        if row < 0 or row >= len(self._device_profiles):
            return None
        return self._device_profiles[row]

    def _validate_profile_file(self, path: Path) -> list[str]:
        from modbus_diagnostic_studio.device_profiles.loader import load_device_profile_file

        try:
            profile = load_device_profile_file(path, source="user")
        except Exception as exc:
            return [f"ERROR: imported file could not be loaded: {exc}"]
        return self._validation_messages_for_profile(profile) or [
            "OK: imported file loaded successfully"
        ]

    def _select_device_profile_by_filename(self, path: Path) -> None:
        device_id = path.stem
        for row, profile in enumerate(self._device_profiles):
            if profile.device_id == device_id:
                self.device_profiles_table.selectRow(row)
                return

    @staticmethod
    def _unique_destination(path: Path) -> Path:
        if not path.exists():
            return path
        for index in range(1, 1000):
            candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
            if not candidate.exists():
                return candidate
        raise RuntimeError(f"Could not find a unique destination for {path.name}")


def _deduplicate_messages(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_messages: list[str] = []
    for message in messages:
        if message in seen:
            continue
        seen.add(message)
        unique_messages.append(message)
    return unique_messages
