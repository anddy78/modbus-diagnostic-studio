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
from modbus_diagnostic_studio.device_profiles.validator import (
    validate_device_profile,
    validate_role_links,
)
from modbus_diagnostic_studio.gui.help import set_help
from modbus_diagnostic_studio.gui.profile_views import populate_register_preview_table
from modbus_diagnostic_studio.profiles.loader import list_builtin_profiles, load_builtin_profile
from modbus_diagnostic_studio.services.paths import (
    ensure_runtime_dirs,
    user_device_profiles_dir,
)
from modbus_diagnostic_studio.sniffer.communication_profiles import (
    list_builtin_communication_profiles,
)

_DEVICE_PROFILES_TABLE_MIN_HEIGHT = 170
_ROLE_LINKS_TABLE_MIN_HEIGHT = 130
_REGISTER_PROFILES_TABLE_MIN_HEIGHT = 170
_REGISTER_PREVIEW_TABLE_MIN_HEIGHT = 260


class ProfileManagerTab(QWidget):
    """Inspect role-oriented device profiles and existing register profiles."""

    def __init__(self) -> None:
        super().__init__()
        self._device_profiles = []
        self._device_profile_errors: list[str] = []
        self._register_profiles: dict[str, object] = {}

        self.status_label = QLabel("Manage device/register profile metadata.")

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
        self.device_profiles_table.setMinimumHeight(_DEVICE_PROFILES_TABLE_MIN_HEIGHT)
        self.device_profiles_table.itemSelectionChanged.connect(self._update_device_profile_preview)

        self.roles_table = QTableWidget(0, 5)
        self.roles_table.setHorizontalHeaderLabels(
            ["Role", "Profile Type", "Profile ID", "Enabled", "Description"]
        )
        self.roles_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.roles_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.roles_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.roles_table.setMinimumHeight(_ROLE_LINKS_TABLE_MIN_HEIGHT)
        self.roles_table.itemSelectionChanged.connect(self._handle_role_selection_changed)

        self.validation_output = QTextEdit()
        self.validation_output.setReadOnly(True)
        self.validation_output.setMinimumHeight(120)

        self.register_profiles_table = QTableWidget(0, 5)
        self.register_profiles_table.setHorizontalHeaderLabels(
            ["Profile ID", "Name", "Status", "Registers", "Description"]
        )
        self.register_profiles_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.register_profiles_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.register_profiles_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.register_profiles_table.setMinimumHeight(_REGISTER_PROFILES_TABLE_MIN_HEIGHT)
        self.register_profiles_table.itemSelectionChanged.connect(
            self._handle_register_profile_selection_changed
        )

        self.register_preview_status_label = QLabel(
            "Select a register profile to preview its registers."
        )
        self.register_preview_table = QTableWidget(0, 9)
        self.register_preview_table.setHorizontalHeaderLabels(
            ["Variable", "Address", "Function", "Bank", "Type", "Quantity", "Unit", "Scale", "Description"]
        )
        self.register_preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.register_preview_table.horizontalHeader().setStretchLastSection(True)
        self.register_preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.register_preview_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.register_preview_table.setMinimumHeight(_REGISTER_PREVIEW_TABLE_MIN_HEIGHT)

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
        content_layout.setStretch(content_layout.count() - 1, 3)

        preview_grid = QGridLayout()
        preview_grid.addWidget(QLabel("Role Links"), 0, 0)
        preview_grid.addWidget(self.roles_table, 1, 0)
        preview_grid.addWidget(QLabel("Validation"), 2, 0)
        preview_grid.addWidget(self.validation_output, 3, 0)
        preview_grid.setRowStretch(1, 2)
        preview_grid.setRowStretch(3, 1)
        content_layout.addLayout(preview_grid)

        content_layout.addWidget(QLabel("Register Profiles"))
        content_layout.addWidget(self.register_profiles_table)
        content_layout.setStretch(content_layout.count() - 1, 3)
        content_layout.addWidget(QLabel("Register Preview"))
        content_layout.addWidget(self.register_preview_status_label)
        content_layout.addWidget(self.register_preview_table)
        content_layout.setStretch(content_layout.count() - 1, 5)

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
        set_help(
            self.register_profiles_table,
            "Register Profiles",
            "Built-in register profiles used by meter and raw register workflows.",
        )
        set_help(
            self.register_preview_table,
            "Register Preview",
            "Preview the decoded register map fields for the selected register profile.",
        )

    def reload_profiles(self) -> None:
        """Reload built-in and user profile summaries."""
        ensure_runtime_dirs()
        self._device_profiles, self._device_profile_errors = load_all_device_profiles(
            user_device_profiles_dir()
        )
        self._register_profiles = {
            profile_id: load_builtin_profile(profile_id)
            for profile_id in list_builtin_profiles()
        }
        self._populate_device_profiles_table()
        self._populate_register_profiles_table()
        self._update_device_profile_preview()
        self._clear_register_preview()

        device_profile_count = len(self._device_profiles)
        register_profile_count = len(self._register_profiles)
        error_count = len(self._device_profile_errors)
        if error_count:
            self.status_label.setText(
                "Manage device/register profile metadata. Loaded "
                f"{device_profile_count} device profiles and {register_profile_count} register profiles "
                f"with {error_count} user file issue(s)."
            )
        else:
            self.status_label.setText(
                "Manage device/register profile metadata. "
                f"Loaded {device_profile_count} device profiles and {register_profile_count} register profiles."
            )

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
            tooltip = (
                f"Device ID: {profile.device_id}\n"
                f"Name: {profile.name}\n"
                f"Manufacturer: {profile.manufacturer or '-'}\n"
                f"Model: {profile.model or '-'}\n"
                f"Device Type: {profile.device_type}\n"
                f"Status: {profile.status}\n"
                f"Description: {profile.description or '-'}\n"
                f"Roles: {len(profile.roles)}"
            )
            self._set_table_item(self.device_profiles_table, row, 0, profile.device_id, tooltip)
            self._set_table_item(self.device_profiles_table, row, 1, profile.name, tooltip)
            self._set_table_item(self.device_profiles_table, row, 2, profile.manufacturer, tooltip)
            self._set_table_item(self.device_profiles_table, row, 3, profile.model, tooltip)
            self._set_table_item(self.device_profiles_table, row, 4, profile.device_type, tooltip)
            self._set_table_item(self.device_profiles_table, row, 5, profile.status, tooltip)
            self._set_table_item(self.device_profiles_table, row, 6, profile.source, tooltip)
            self._set_table_item(
                self.device_profiles_table, row, 7, str(len(profile.roles)), tooltip
            )

    def _populate_register_profiles_table(self) -> None:
        profile_ids = sorted(self._register_profiles)
        self.register_profiles_table.setRowCount(len(profile_ids))
        for row, profile_id in enumerate(profile_ids):
            profile = self._register_profiles[profile_id]
            description = profile.description or ""
            tooltip = (
                f"Profile ID: {profile.profile_id}\n"
                f"Name: {profile.name}\n"
                f"Status: {profile.status}\n"
                f"Registers: {len(profile.registers)}\n"
                f"Description: {description or '-'}"
            )
            self._set_table_item(self.register_profiles_table, row, 0, profile.profile_id, tooltip)
            self._set_table_item(self.register_profiles_table, row, 1, profile.name, tooltip)
            self._set_table_item(self.register_profiles_table, row, 2, profile.status, tooltip)
            self._set_table_item(
                self.register_profiles_table, row, 3, str(len(profile.registers)), tooltip
            )
            self._set_table_item(self.register_profiles_table, row, 4, description, tooltip)

    def _update_device_profile_preview(self) -> None:
        profile = self._selected_device_profile()
        if profile is None:
            self.roles_table.setRowCount(0)
            if self._device_profile_errors:
                self.validation_output.setPlainText("\n".join(self._device_profile_errors))
            else:
                self.validation_output.setPlainText("Select a device profile to preview roles.")
            self.status_label.setText("Select a device profile to preview its roles.")
            return

        self.roles_table.setRowCount(len(profile.roles))
        for row, role_link in enumerate(profile.roles):
            tooltip = (
                f"Role: {role_link.role}\n"
                f"Profile Type: {role_link.profile_type}\n"
                f"Profile ID: {role_link.profile_id or '-'}\n"
                f"Enabled: {'Yes' if role_link.enabled else 'No'}\n"
                f"Description: {role_link.description or '-'}"
            )
            self._set_table_item(self.roles_table, row, 0, role_link.role, tooltip)
            self._set_table_item(self.roles_table, row, 1, role_link.profile_type, tooltip)
            self._set_table_item(self.roles_table, row, 2, role_link.profile_id, tooltip)
            self._set_table_item(
                self.roles_table, row, 3, "Yes" if role_link.enabled else "No", tooltip
            )
            self._set_table_item(self.roles_table, row, 4, role_link.description, tooltip)

        messages = self._validation_messages_for_profile(profile)
        if not messages:
            messages = ["OK: no validation issues found"]
        self.validation_output.setPlainText("\n".join(messages))
        self.status_label.setText(
            f"Selected device profile {profile.device_id}: {len(profile.roles)} role link(s)."
        )

    def _handle_register_profile_selection_changed(self) -> None:
        profile = self._selected_register_profile()
        if profile is None:
            self._clear_register_preview()
            return
        self._load_register_profile_preview(profile.profile_id)

    def _handle_role_selection_changed(self) -> None:
        role_link = self._selected_role_link()
        if role_link is None:
            return

        if not role_link.enabled:
            self._clear_register_preview("Role is disabled.")
            self.status_label.setText("Role is disabled.")
            return

        if not role_link.profile_id:
            self._clear_register_preview("Role has no linked profile.")
            self.status_label.setText("Role has no linked profile.")
            return

        if role_link.profile_type == "register_profile":
            if role_link.profile_id not in self._register_profiles:
                self._clear_register_preview(
                    f"Linked register profile {role_link.profile_id} is not available."
                )
                self.status_label.setText(
                    f"Linked register profile {role_link.profile_id} is not available."
                )
                return
            self._select_register_profile_by_id(role_link.profile_id)
            self._load_register_profile_preview(role_link.profile_id)
            return

        if role_link.profile_type == "communication_profile":
            self._clear_register_preview(
                "Communication profiles are used for Sniffer diagnostics and do not expose a register map preview."
            )
            self.status_label.setText(
                f"Role points to communication profile {role_link.profile_id}."
            )
            return

        self._clear_register_preview(
            f"Role points to unsupported profile type {role_link.profile_type}."
        )
        self.status_label.setText(
            f"Role points to unsupported profile type {role_link.profile_type}."
        )

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

    def _selected_register_profile(self):
        row = self.register_profiles_table.currentRow()
        if row < 0:
            return None
        item = self.register_profiles_table.item(row, 0)
        if item is None:
            return None
        return self._register_profiles.get(item.text())

    def _selected_role_link(self):
        profile = self._selected_device_profile()
        row = self.roles_table.currentRow()
        if profile is None or row < 0 or row >= len(profile.roles):
            return None
        return profile.roles[row]

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

    def _select_register_profile_by_id(self, profile_id: str) -> None:
        for row in range(self.register_profiles_table.rowCount()):
            item = self.register_profiles_table.item(row, 0)
            if item is not None and item.text() == profile_id:
                self.register_profiles_table.selectRow(row)
                return

    def _load_register_profile_preview(self, profile_id: str) -> None:
        profile = self._register_profiles.get(profile_id)
        if profile is None:
            self._clear_register_preview(
                f"Register profile {profile_id} is not available."
            )
            return

        populate_register_preview_table(self.register_preview_table, profile)
        count = len(profile.registers)
        if count == 0:
            message = f"Selected register profile {profile.profile_id}: 0 registers."
        else:
            message = f"Selected register profile {profile.profile_id}: {count} registers."
        self.register_preview_status_label.setText(message)
        self.status_label.setText(message)

    def _clear_register_preview(
        self,
        message: str = "Select a register profile to preview its registers.",
    ) -> None:
        self.register_preview_table.setRowCount(0)
        self.register_preview_status_label.setText(message)

    @staticmethod
    def _unique_destination(path: Path) -> Path:
        if not path.exists():
            return path
        for index in range(1, 1000):
            candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
            if not candidate.exists():
                return candidate
        raise RuntimeError(f"Could not find a unique destination for {path.name}")

    @staticmethod
    def _set_table_item(
        table: QTableWidget,
        row: int,
        column: int,
        text: str,
        tooltip: str,
    ) -> None:
        item = QTableWidgetItem(text)
        item.setToolTip(tooltip)
        table.setItem(row, column, item)


def _deduplicate_messages(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_messages: list[str] = []
    for message in messages:
        if message in seen:
            continue
        seen.add(message)
        unique_messages.append(message)
    return unique_messages
