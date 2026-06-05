"""Validation helpers for role-oriented device profiles."""

from __future__ import annotations

from modbus_diagnostic_studio.models.device_profile import DeviceProfileDefinition


def validate_role_links(
    profile: DeviceProfileDefinition,
    available_register_profile_ids: set[str] | None = None,
    available_communication_profile_ids: set[str] | None = None,
) -> list[str]:
    """Validate role links and optional linked profile references."""
    messages: list[str] = []

    register_ids = available_register_profile_ids or set()
    communication_ids = available_communication_profile_ids or set()

    for index, role_link in enumerate(profile.roles):
        prefix = f"role link #{index}"
        if not role_link.role:
            messages.append(f"ERROR: {prefix} role must not be empty")
        if not role_link.profile_type:
            messages.append(f"ERROR: {prefix} profile_type must not be empty")
        if role_link.enabled and not role_link.profile_id:
            messages.append(f"ERROR: {prefix} enabled role must define profile_id")
        if not role_link.enabled and not role_link.profile_id:
            messages.append(
                f"WARNING: {prefix} is disabled and has no profile_id yet"
            )

        if not role_link.enabled or not role_link.profile_id:
            continue

        if (
            role_link.profile_type == "register_profile"
            and register_ids
            and role_link.profile_id not in register_ids
        ):
            messages.append(
                f"WARNING: {prefix} references unknown register profile '{role_link.profile_id}'"
            )
        if (
            role_link.profile_type == "communication_profile"
            and communication_ids
            and role_link.profile_id not in communication_ids
        ):
            messages.append(
                "WARNING: "
                f"{prefix} references unknown communication profile '{role_link.profile_id}'"
            )

    return messages


def validate_device_profile(profile: DeviceProfileDefinition) -> list[str]:
    """Return human-readable validation messages for one device profile."""
    messages: list[str] = []

    if not profile.device_id:
        messages.append("ERROR: device_id must not be empty")
    if not profile.name:
        messages.append("ERROR: name must not be empty")
    if not profile.device_type:
        messages.append("ERROR: device_type must not be empty")
    if not profile.roles:
        messages.append("WARNING: device profile has no role links")

    messages.extend(validate_role_links(profile))
    return messages
