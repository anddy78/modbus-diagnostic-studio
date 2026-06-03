"""Profile validation helpers."""

from __future__ import annotations

from numbers import Real

from modbus_diagnostic_studio.models.profile import ProfileDefinition

VALID_DEFAULT_FUNCTIONS = {3, 4}
VALID_BYTE_ORDERS = {"big"}
VALID_WORD_ORDERS = {"normal", "swap"}
VALID_BASE_ADDRESSING = {"zero_based", "one_based"}
VALID_REGISTER_TYPES = {"uint16", "int16", "uint32", "int32", "float32"}


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def validate_profile(profile: ProfileDefinition) -> list[str]:
    """Return validation errors for a profile, or an empty list when valid."""
    errors: list[str] = []

    if not profile.profile_id:
        errors.append("profile_id must not be empty")
    if not profile.name:
        errors.append("name must not be empty")
    if profile.default_function not in VALID_DEFAULT_FUNCTIONS:
        errors.append("default_function must be 3 or 4")
    if profile.byte_order not in VALID_BYTE_ORDERS:
        errors.append("byte_order must be 'big'")
    if profile.word_order not in VALID_WORD_ORDERS:
        errors.append("word_order must be 'normal' or 'swap'")
    if profile.base_addressing not in VALID_BASE_ADDRESSING:
        errors.append("base_addressing must be 'zero_based' or 'one_based'")
    if profile.registers_per_value < 1:
        errors.append("registers_per_value must be >= 1")
    if profile.max_registers_per_request < 1:
        errors.append("max_registers_per_request must be >= 1")

    seen_variables: set[str] = set()
    seen_addresses: set[int] = set()
    for index, register in enumerate(profile.registers):
        prefix = f"register #{index}"
        if not register.variable:
            errors.append(f"{prefix} variable must not be empty")
        elif register.variable in seen_variables:
            errors.append(f"duplicate variable: {register.variable}")
        else:
            seen_variables.add(register.variable)

        if register.address < 0:
            errors.append(f"{prefix} address must be >= 0")
        elif register.address in seen_addresses:
            errors.append(f"duplicate address: {register.address}")
        else:
            seen_addresses.add(register.address)

        if register.type not in VALID_REGISTER_TYPES:
            errors.append(f"{prefix} type must be one of {sorted(VALID_REGISTER_TYPES)}")
        if not _is_number(register.scale):
            errors.append(f"{prefix} scale must be numeric")

    return errors


def assert_valid_profile(profile: ProfileDefinition) -> None:
    """Raise ValueError if profile validation fails."""
    errors = validate_profile(profile)
    if errors:
        raise ValueError("; ".join(errors))
