"""Profile-based master reader."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from modbus_diagnostic_studio.master.read_plan import build_read_plan
from modbus_diagnostic_studio.models.profile import ProfileDefinition
from modbus_diagnostic_studio.profiles.decoder import (
    DecodedProfileValue,
    decode_profile_registers,
)


class ProfileMasterClientLike(Protocol):
    """Subset of ModbusMasterClient used by the profile reader."""

    def read_holding_registers(
        self,
        slave_id: int,
        address: int,
        quantity: int,
    ) -> list[int]:
        """Read holding registers."""

    def read_input_registers(
        self,
        slave_id: int,
        address: int,
        quantity: int,
    ) -> list[int]:
        """Read input registers."""


@dataclass(frozen=True)
class ProfileReadResult:
    """Result of reading and decoding a profile."""

    profile_id: str
    blocks_read: int
    values: list[DecodedProfileValue]
    raw_blocks: dict[int, list[int]]


def read_profile(
    master_client: ProfileMasterClientLike,
    slave_id: int,
    profile: ProfileDefinition,
) -> ProfileReadResult:
    """Read all profile blocks with an active master client and decode values."""
    values: list[DecodedProfileValue] = []
    raw_blocks: dict[int, list[int]] = {}

    for block in build_read_plan(profile):
        if block.function_code == 3:
            registers = master_client.read_holding_registers(
                slave_id,
                block.start_address,
                block.quantity,
            )
        elif block.function_code == 4:
            registers = master_client.read_input_registers(
                slave_id,
                block.start_address,
                block.quantity,
            )
        else:
            raise ValueError(f"Unsupported function code: {block.function_code}")

        raw_blocks[block.start_address] = registers
        values.extend(
            decode_profile_registers(
                profile,
                start_address=block.start_address,
                registers=registers,
            )
        )

    return ProfileReadResult(
        profile_id=profile.profile_id,
        blocks_read=len(raw_blocks),
        values=values,
        raw_blocks=raw_blocks,
    )
