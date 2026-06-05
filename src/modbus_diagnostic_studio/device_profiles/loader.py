"""YAML loader for role-oriented device profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from modbus_diagnostic_studio.models.device_profile import (
    DeviceProfileDefinition,
    DeviceProfileRoleLink,
)

BUILTINS_DIR = Path(__file__).resolve().parent / "builtins"


def _require_mapping(data: Any, context: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{context} must be a mapping")
    return data


def _load_role_link(data: Any, index: int) -> DeviceProfileRoleLink:
    link = _require_mapping(data, f"Role link #{index}")
    enabled = bool(link.get("enabled", True))
    required_fields = ("role", "profile_type")
    for field_name in required_fields:
        if field_name not in link:
            raise ValueError(f"Role link #{index} is missing required field: {field_name}")
    if enabled and "profile_id" not in link:
        raise ValueError("Enabled role link is missing required field: profile_id")
    if not enabled and "profile_id" not in link:
        profile_id = ""
    else:
        profile_id = str(link.get("profile_id", ""))

    return DeviceProfileRoleLink(
        role=str(link["role"]),
        profile_id=profile_id,
        profile_type=str(link["profile_type"]),
        description=str(link.get("description", "")),
        enabled=enabled,
    )


def _load_device_profile_from_dict(data: Any, source: str) -> DeviceProfileDefinition:
    profile_data = _require_mapping(data, "Device profile")
    if "device_id" not in profile_data:
        raise ValueError("Device profile is missing required field: device_id")
    if "name" not in profile_data:
        raise ValueError("Device profile is missing required field: name")

    roles_data = profile_data.get("roles", [])
    if not isinstance(roles_data, list):
        raise ValueError("Device profile field 'roles' must be a list")
    tags_data = profile_data.get("tags", [])
    if not isinstance(tags_data, list):
        raise ValueError("Device profile field 'tags' must be a list")

    return DeviceProfileDefinition(
        device_id=str(profile_data["device_id"]),
        name=str(profile_data["name"]),
        manufacturer=str(profile_data.get("manufacturer", "")),
        model=str(profile_data.get("model", "")),
        device_type=str(profile_data.get("device_type", "generic")),
        description=str(profile_data.get("description", "")),
        tags=[str(tag) for tag in tags_data],
        roles=[_load_role_link(role_data, index) for index, role_data in enumerate(roles_data)],
        source=str(profile_data.get("source", source)),
        status=str(profile_data.get("status", "draft")),
        notes=str(profile_data.get("notes", "")),
    )


def builtin_device_profiles_dir() -> Path:
    """Return the built-in device profile directory."""
    return BUILTINS_DIR


def list_builtin_device_profile_ids() -> list[str]:
    """Return available built-in device profile ids."""
    return sorted(path.stem for path in BUILTINS_DIR.glob("*.yaml"))


def load_device_profile_file(
    path: Path,
    source: str = "user",
) -> DeviceProfileDefinition:
    """Load one device profile from YAML."""
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return _load_device_profile_from_dict(data, source=source)


def load_builtin_device_profile(device_id: str) -> DeviceProfileDefinition:
    """Load a bundled device profile by id."""
    path = BUILTINS_DIR / f"{device_id}.yaml"
    if not path.exists():
        raise ValueError(f"Built-in device profile not found: {device_id}")
    return load_device_profile_file(path, source="built-in")


def load_user_device_profiles(user_dir: Path) -> tuple[list[DeviceProfileDefinition], list[str]]:
    """Load all user device profiles recursively."""
    profiles: list[DeviceProfileDefinition] = []
    errors: list[str] = []
    base_dir = Path(user_dir)
    if not base_dir.exists():
        return profiles, errors

    paths = sorted(
        path
        for pattern in ("*.yaml", "*.yml")
        for path in base_dir.rglob(pattern)
        if path.is_file()
    )
    for path in paths:
        try:
            profiles.append(load_device_profile_file(path, source="user"))
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    return profiles, errors


def load_all_device_profiles(
    user_dir: Path | None = None,
) -> tuple[list[DeviceProfileDefinition], list[str]]:
    """Load built-in and optional user device profiles."""
    profiles = [
        load_builtin_device_profile(device_id)
        for device_id in list_builtin_device_profile_ids()
    ]
    errors: list[str] = []
    if user_dir is None:
        return profiles, errors

    user_profiles, user_errors = load_user_device_profiles(user_dir)
    profiles.extend(user_profiles)
    errors.extend(user_errors)
    return profiles, errors


def find_device_profile(
    profiles: list[DeviceProfileDefinition],
    device_id: str,
) -> DeviceProfileDefinition | None:
    """Return one device profile by id, if present."""
    for profile in profiles:
        if profile.device_id == device_id:
            return profile
    return None


def filter_device_profiles(
    profiles: list[DeviceProfileDefinition],
    device_type: str | None = None,
    manufacturer: str | None = None,
) -> list[DeviceProfileDefinition]:
    """Filter profiles by simple metadata."""
    filtered = profiles
    if device_type:
        filtered = [profile for profile in filtered if profile.device_type == device_type]
    if manufacturer:
        filtered = [
            profile for profile in filtered if profile.manufacturer == manufacturer
        ]
    return filtered
