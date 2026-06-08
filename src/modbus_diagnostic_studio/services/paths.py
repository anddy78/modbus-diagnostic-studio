"""Runtime path helpers for development and portable builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_base_dir() -> Path:
    """Return the writable runtime base directory."""
    override = os.environ.get("MDS_BASE_DIR")
    if override:
        return Path(override).resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[3]


def config_dir() -> Path:
    return app_base_dir() / "config"


def logs_dir() -> Path:
    return app_base_dir() / "logs"


def captures_dir() -> Path:
    return app_base_dir() / "captures"


def exports_dir() -> Path:
    return app_base_dir() / "exports"


def user_profiles_dir() -> Path:
    return app_base_dir() / "profiles" / "user"


def user_device_profiles_dir() -> Path:
    return app_base_dir() / "device_profiles" / "user"


def slave_scenarios_dir() -> Path:
    return app_base_dir() / "scenarios" / "slave"


def ensure_runtime_dirs() -> None:
    """Create the writable runtime directories if needed."""
    for path in (
        config_dir(),
        logs_dir(),
        captures_dir(),
        exports_dir(),
        user_profiles_dir(),
        user_device_profiles_dir(),
        slave_scenarios_dir(),
    ):
        path.mkdir(parents=True, exist_ok=True)
