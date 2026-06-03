"""Profile models for register-based Modbus decoding."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegisterDefinition:
    """A single register value definition from a profile."""

    variable: str
    address: int
    type: str
    unit: str | None = None
    scale: float = 1.0
    description: str = ""


@dataclass(frozen=True)
class ProfileDefinition:
    """A complete Modbus device profile definition."""

    profile_id: str
    name: str
    description: str = ""
    status: str = "unknown"
    default_function: int = 3
    byte_order: str = "big"
    word_order: str = "normal"
    base_addressing: str = "zero_based"
    registers_per_value: int = 2
    max_registers_per_request: int = 64
    registers: list[RegisterDefinition] = field(default_factory=list)
