"""Unit tests for slave register datastore."""

from __future__ import annotations

import pytest

from modbus_diagnostic_studio.slave.datastore import RegisterBank, SlaveDatastore


# ── RegisterBank ──────────────────────────────────────────────────────────────


class TestRegisterBankDefaults:
    def test_read_default_zeros(self) -> None:
        bank = RegisterBank(size=10)
        assert bank.read(0, 10) == [0] * 10

    def test_default_value_applied(self) -> None:
        bank = RegisterBank(size=4, default_value=0xFFFF)
        assert bank.read(0, 4) == [0xFFFF] * 4

    def test_size_property(self) -> None:
        bank = RegisterBank(size=100)
        assert bank.size == 100


class TestRegisterBankRead:
    def test_read_single(self) -> None:
        bank = RegisterBank(size=5)
        bank.write_register(2, 42)
        assert bank.read(2, 1) == [42]

    def test_read_range(self) -> None:
        bank = RegisterBank(size=10)
        bank.write_range(3, [10, 20, 30])
        assert bank.read(3, 3) == [10, 20, 30]

    def test_read_at_boundary(self) -> None:
        bank = RegisterBank(size=5)
        bank.write_register(4, 99)
        assert bank.read(4, 1) == [99]

    def test_read_returns_copy(self) -> None:
        bank = RegisterBank(size=5)
        result = bank.read(0, 3)
        result[0] = 999
        assert bank.read(0, 1) == [0]


class TestRegisterBankWrite:
    def test_write_and_read_back(self) -> None:
        bank = RegisterBank(size=10)
        bank.write_register(5, 1234)
        assert bank.read(5, 1) == [1234]

    def test_write_range_and_read_back(self) -> None:
        bank = RegisterBank(size=10)
        bank.write_range(0, [100, 200, 300])
        assert bank.read(0, 3) == [100, 200, 300]

    def test_write_range_partial_overlap(self) -> None:
        bank = RegisterBank(size=10)
        bank.write_range(0, [1, 2, 3, 4, 5])
        bank.write_range(2, [99, 99])
        assert bank.read(0, 5) == [1, 2, 99, 99, 5]

    def test_write_max_value(self) -> None:
        bank = RegisterBank(size=5)
        bank.write_register(0, 0xFFFF)
        assert bank.read(0, 1) == [0xFFFF]

    def test_write_zero(self) -> None:
        bank = RegisterBank(size=5, default_value=0xFFFF)
        bank.write_register(0, 0)
        assert bank.read(0, 1) == [0]


class TestRegisterBankClear:
    def test_clear_resets_to_zero(self) -> None:
        bank = RegisterBank(size=5)
        bank.write_range(0, [1, 2, 3, 4, 5])
        bank.clear()
        assert bank.read(0, 5) == [0] * 5

    def test_clear_with_nonzero_value(self) -> None:
        bank = RegisterBank(size=4)
        bank.clear(value=7)
        assert bank.read(0, 4) == [7, 7, 7, 7]


class TestRegisterBankInvalidInputs:
    def test_invalid_address_negative(self) -> None:
        bank = RegisterBank(size=10)
        with pytest.raises(ValueError, match="address"):
            bank.read(-1, 1)

    def test_invalid_address_too_high(self) -> None:
        bank = RegisterBank(size=10)
        with pytest.raises(ValueError, match="address"):
            bank.write_register(10, 0)

    def test_invalid_address_exceeds_65535(self) -> None:
        bank = RegisterBank(size=65536)
        with pytest.raises(ValueError, match="address"):
            bank.write_register(65536, 0)

    def test_invalid_value_too_high(self) -> None:
        bank = RegisterBank(size=5)
        with pytest.raises(ValueError, match="value"):
            bank.write_register(0, 0x10000)

    def test_invalid_value_negative(self) -> None:
        bank = RegisterBank(size=5)
        with pytest.raises(ValueError, match="value"):
            bank.write_register(0, -1)

    def test_read_out_of_range(self) -> None:
        bank = RegisterBank(size=5)
        with pytest.raises(ValueError, match="exceeds"):
            bank.read(3, 3)

    def test_write_range_out_of_range(self) -> None:
        bank = RegisterBank(size=5)
        with pytest.raises(ValueError, match="exceeds"):
            bank.write_range(4, [1, 2])

    def test_read_quantity_zero(self) -> None:
        bank = RegisterBank(size=5)
        with pytest.raises(ValueError, match="quantity"):
            bank.read(0, 0)

    def test_invalid_size(self) -> None:
        with pytest.raises(ValueError):
            RegisterBank(size=0)

    def test_invalid_default_value(self) -> None:
        with pytest.raises(ValueError):
            RegisterBank(size=10, default_value=0x10000)


# ── SlaveDatastore ────────────────────────────────────────────────────────────


class TestSlaveDatastore:
    def test_default_zeros_holding(self) -> None:
        ds = SlaveDatastore()
        assert ds.read_holding_registers(0, 4) == [0, 0, 0, 0]

    def test_default_zeros_input(self) -> None:
        ds = SlaveDatastore()
        assert ds.read_input_registers(0, 4) == [0, 0, 0, 0]

    def test_write_and_read_holding(self) -> None:
        ds = SlaveDatastore()
        ds.write_holding_register(10, 0xABCD)
        assert ds.read_holding_registers(10, 1) == [0xABCD]

    def test_write_range_holding(self) -> None:
        ds = SlaveDatastore()
        ds.write_holding_range(5, [11, 22, 33])
        assert ds.read_holding_registers(5, 3) == [11, 22, 33]

    def test_write_and_read_input(self) -> None:
        ds = SlaveDatastore()
        ds.write_input_register(20, 0x1234)
        assert ds.read_input_registers(20, 1) == [0x1234]

    def test_write_range_input(self) -> None:
        ds = SlaveDatastore()
        ds.write_input_range(0, [100, 200])
        assert ds.read_input_registers(0, 2) == [100, 200]

    def test_holding_and_input_are_independent(self) -> None:
        ds = SlaveDatastore()
        ds.write_holding_register(0, 111)
        ds.write_input_register(0, 222)
        assert ds.read_holding_registers(0, 1) == [111]
        assert ds.read_input_registers(0, 1) == [222]

    def test_invalid_address_propagated(self) -> None:
        ds = SlaveDatastore()
        with pytest.raises(ValueError):
            ds.write_holding_register(65536, 0)

    def test_out_of_range_propagated(self) -> None:
        ds = SlaveDatastore(holding_size=10)
        with pytest.raises(ValueError):
            ds.read_holding_registers(8, 5)
