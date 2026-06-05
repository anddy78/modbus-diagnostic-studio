"""Tests for reading profiles through a fake master client."""

import struct

import pytest

from modbus_diagnostic_studio.master.profile_reader import read_profile
from modbus_diagnostic_studio.models.profile import ProfileDefinition, RegisterDefinition
from modbus_diagnostic_studio.profiles.decoder import decoded_values_to_dict
from modbus_diagnostic_studio.profiles.loader import load_builtin_profile


class FakeMasterClient:
    def __init__(self, blocks: dict[tuple[int, int, int], list[int]]) -> None:
        self.blocks = blocks
        self.calls: list[tuple[str, int, int, int]] = []

    def read_holding_registers(
        self,
        slave_id: int,
        address: int,
        quantity: int,
    ) -> list[int]:
        self.calls.append(("holding", slave_id, address, quantity))
        return self.blocks[(3, address, quantity)]

    def read_input_registers(
        self,
        slave_id: int,
        address: int,
        quantity: int,
    ) -> list[int]:
        self.calls.append(("input", slave_id, address, quantity))
        return self.blocks[(4, address, quantity)]


class FailingMasterClient:
    def read_holding_registers(
        self,
        slave_id: int,
        address: int,
        quantity: int,
    ) -> list[int]:
        raise RuntimeError("serial failed")

    def read_input_registers(
        self,
        slave_id: int,
        address: int,
        quantity: int,
    ) -> list[int]:
        raise RuntimeError("serial failed")


def float32_registers(value: float) -> list[int]:
    return list(struct.unpack(">HH", struct.pack(">f", value)))


def test_read_profile_generic_meter_decodes_values_and_uses_fc03() -> None:
    profile = load_builtin_profile("generic_meter")
    registers = (
        float32_registers(230.5)
        + float32_registers(10.25)
        + float32_registers(1234.0)
        + float32_registers(50.0)
    )
    master = FakeMasterClient({(3, 0, 8): registers})

    result = read_profile(master, slave_id=7, profile=profile)
    values = decoded_values_to_dict(result.values)

    assert result.profile_id == "generic_meter"
    assert result.blocks_read == 1
    assert result.raw_blocks == {0: registers}
    assert master.calls == [("holding", 7, 0, 8)]
    assert values["voltage_l1_v"] == pytest.approx(230.5)
    assert values["current_l1_a"] == pytest.approx(10.25)
    assert values["power_total_w"] == pytest.approx(1234.0)
    assert values["frequency_hz"] == pytest.approx(50.0)


def test_read_profile_uses_fc04_for_input_register_profile() -> None:
    profile = ProfileDefinition(
        profile_id="input_profile",
        name="Input Profile",
        default_function=4,
        registers=[RegisterDefinition(variable="voltage_l1_v", address=0, type="float32")],
    )
    registers = float32_registers(231.0)
    master = FakeMasterClient({(4, 0, 2): registers})

    result = read_profile(master, slave_id=1, profile=profile)
    values = decoded_values_to_dict(result.values)

    assert master.calls == [("input", 1, 0, 2)]
    assert result.blocks_read == 1
    assert values["voltage_l1_v"] == pytest.approx(231.0)


def test_read_profile_propagates_master_exception() -> None:
    profile = load_builtin_profile("generic_meter")

    with pytest.raises(RuntimeError, match="serial failed"):
        read_profile(FailingMasterClient(), slave_id=1, profile=profile)


def test_read_profile_rejects_unsupported_function_code() -> None:
    profile = ProfileDefinition(
        profile_id="bad_function",
        name="Bad Function",
        default_function=6,
        registers=[RegisterDefinition(variable="value", address=0, type="uint16")],
    )

    with pytest.raises(ValueError, match="Unsupported function code"):
        read_profile(FakeMasterClient({}), slave_id=1, profile=profile)
