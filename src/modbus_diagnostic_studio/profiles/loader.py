"""YAML profile loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from modbus_diagnostic_studio.models.profile import (
    ProfileDefinition,
    RegisterDefinition,
)
from modbus_diagnostic_studio.profiles.validator import assert_valid_profile

BUILTINS_DIR = Path(__file__).resolve().parent / "builtins"


def _require_mapping(data: Any, context: str) -> dict:
    if not isinstance(data, dict):
        raise ValueError(f"{context} must be a mapping")
    return data


def _require_field(data: dict, field_name: str) -> Any:
    if field_name not in data:
        raise ValueError(f"Profile is missing required field: {field_name}")
    return data[field_name]


def _load_register(data: Any, index: int) -> RegisterDefinition:
    register = _require_mapping(data, f"Register #{index}")
    for field_name in ("variable", "address", "type"):
        if field_name not in register:
            raise ValueError(f"Register #{index} is missing required field: {field_name}")

    return RegisterDefinition(
        variable=register["variable"],
        address=register["address"],
        type=register["type"],
        unit=register.get("unit"),
        scale=register.get("scale", 1.0),
        description=register.get("description", ""),
    )


def load_profile(path: str | Path) -> ProfileDefinition:
    """Load and validate a profile from a YAML file."""
    profile_path = Path(path)
    with profile_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return load_profile_from_dict(data)


def load_profile_from_dict(data: dict) -> ProfileDefinition:
    """Build and validate a profile from a dictionary."""
    profile_data = _require_mapping(data, "Profile")
    registers_data = _require_field(profile_data, "registers")
    if not isinstance(registers_data, list):
        raise ValueError("Profile field 'registers' must be a list")

    profile = ProfileDefinition(
        profile_id=_require_field(profile_data, "profile_id"),
        name=_require_field(profile_data, "name"),
        description=profile_data.get("description", ""),
        status=profile_data.get("status", "unknown"),
        default_function=profile_data.get("default_function", 3),
        byte_order=profile_data.get("byte_order", "big"),
        word_order=profile_data.get("word_order", "normal"),
        base_addressing=profile_data.get("base_addressing", "zero_based"),
        registers_per_value=profile_data.get("registers_per_value", 2),
        max_registers_per_request=profile_data.get("max_registers_per_request", 64),
        registers=[
            _load_register(register_data, index)
            for index, register_data in enumerate(registers_data)
        ],
    )
    assert_valid_profile(profile)
    return profile


def load_builtin_profile(profile_id: str) -> ProfileDefinition:
    """Load a bundled profile by id."""
    profile_path = BUILTINS_DIR / f"{profile_id}.yaml"
    if not profile_path.exists():
        raise ValueError(f"Built-in profile not found: {profile_id}")
    return load_profile(profile_path)


def list_builtin_profiles() -> list[str]:
    """Return available built-in profile ids."""
    return sorted(path.stem for path in BUILTINS_DIR.glob("*.yaml"))
