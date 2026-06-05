"""Master read plan builder."""

from __future__ import annotations

from dataclasses import dataclass

from modbus_diagnostic_studio.models.profile import ProfileDefinition, RegisterDefinition

_TYPE_REGISTER_COUNTS = {
    "uint16": 1,
    "int16": 1,
    "uint32": 2,
    "int32": 2,
    "float32": 2,
}
_MAX_INCLUDED_GAP_REGISTERS = 2


@dataclass(frozen=True)
class ReadBlock:
    """One active Modbus read operation for a profile."""

    function_code: int
    start_address: int
    quantity: int
    variables: list[str]


def _register_count(register: RegisterDefinition) -> int:
    try:
        return _TYPE_REGISTER_COUNTS[register.type]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported register type for {register.variable}: {register.type}"
        ) from exc


def build_read_plan(profile: ProfileDefinition) -> list[ReadBlock]:
    """Build grouped FC03/FC04 read blocks for a register profile."""
    if not profile.registers:
        return []

    blocks: list[ReadBlock] = []
    seen_variables: set[str] = set()
    current_start: int | None = None
    current_end: int | None = None
    current_variables: list[str] = []

    for register in sorted(profile.registers, key=lambda item: item.address):
        if register.variable in seen_variables:
            continue
        seen_variables.add(register.variable)

        size = _register_count(register)
        register_start = register.address
        register_end = register.address + size

        if current_start is None or current_end is None:
            current_start = register_start
            current_end = register_end
            current_variables = [register.variable]
            continue

        gap = register_start - current_end
        candidate_quantity = register_end - current_start
        can_extend = (
            gap <= _MAX_INCLUDED_GAP_REGISTERS
            and candidate_quantity <= profile.max_registers_per_request
        )

        if can_extend:
            current_end = max(current_end, register_end)
            current_variables.append(register.variable)
            continue

        blocks.append(
            ReadBlock(
                function_code=profile.default_function,
                start_address=current_start,
                quantity=current_end - current_start,
                variables=current_variables,
            )
        )
        current_start = register_start
        current_end = register_end
        current_variables = [register.variable]

    if current_start is not None and current_end is not None:
        blocks.append(
            ReadBlock(
                function_code=profile.default_function,
                start_address=current_start,
                quantity=current_end - current_start,
                variables=current_variables,
            )
        )

    return blocks
