"""Tests for device profile YAML loading."""

from pathlib import Path

from modbus_diagnostic_studio.device_profiles.loader import (
    find_device_profile,
    list_builtin_device_profile_ids,
    load_all_device_profiles,
    load_builtin_device_profile,
    load_user_device_profiles,
)


def test_list_builtin_device_profile_ids_includes_expected_ids() -> None:
    profile_ids = set(list_builtin_device_profile_ids())

    assert {"generic_modbus_meter", "chint_dtsu71", "generic_inverter_demo"} <= profile_ids


def test_load_builtin_device_profile_works() -> None:
    profile = load_builtin_device_profile("chint_dtsu71")

    assert profile.device_id == "chint_dtsu71"
    assert profile.roles[0].profile_id == "chint_dtsu71"


def test_load_all_device_profiles_loads_builtins() -> None:
    profiles, errors = load_all_device_profiles()

    assert errors == []
    assert find_device_profile(profiles, "generic_modbus_meter") is not None
    assert find_device_profile(profiles, "chint_dtsu71") is not None


def test_load_user_device_profiles_from_tmp_path(tmp_path: Path) -> None:
    profile_path = tmp_path / "sample_meter.yaml"
    profile_path.write_text(
        "\n".join(
            [
                "device_id: sample_meter",
                "name: Sample Meter",
                "device_type: meter",
                "roles:",
                "  - role: slave",
                "    profile_type: register_profile",
                "    profile_id: generic_meter",
            ]
        ),
        encoding="utf-8",
    )

    profiles, errors = load_user_device_profiles(tmp_path)

    assert errors == []
    assert len(profiles) == 1
    assert profiles[0].device_id == "sample_meter"


def test_invalid_yaml_does_not_break_user_load(tmp_path: Path) -> None:
    valid_path = tmp_path / "ok.yaml"
    valid_path.write_text(
        "\n".join(
            [
                "device_id: sample_ok",
                "name: Sample OK",
                "roles: []",
            ]
        ),
        encoding="utf-8",
    )
    invalid_path = tmp_path / "broken.yaml"
    invalid_path.write_text("device_id: [", encoding="utf-8")

    profiles, errors = load_user_device_profiles(tmp_path)

    assert any(profile.device_id == "sample_ok" for profile in profiles)
    assert len(errors) == 1
    assert "broken.yaml" in errors[0]


def test_disabled_placeholder_with_empty_profile_id_does_not_break() -> None:
    profile = load_builtin_device_profile("generic_inverter_demo")

    disabled_links = [role_link for role_link in profile.roles if not role_link.enabled]
    assert len(disabled_links) == 1
    assert disabled_links[0].profile_id == ""
