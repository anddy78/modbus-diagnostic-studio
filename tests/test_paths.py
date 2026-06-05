"""Tests for runtime path helpers."""

from pathlib import Path

from modbus_diagnostic_studio.services.paths import (
    app_base_dir,
    ensure_runtime_dirs,
    user_device_profiles_dir,
)


def test_ensure_runtime_dirs_creates_expected_folders(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))

    ensure_runtime_dirs()

    assert app_base_dir() == tmp_path.resolve()
    assert (tmp_path / "config").is_dir()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "captures").is_dir()
    assert (tmp_path / "exports").is_dir()
    assert (tmp_path / "profiles" / "user").is_dir()
    assert (tmp_path / "device_profiles" / "user").is_dir()


def test_user_device_profiles_dir_exists_after_ensure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MDS_BASE_DIR", str(tmp_path))

    ensure_runtime_dirs()

    assert user_device_profiles_dir().is_dir()
