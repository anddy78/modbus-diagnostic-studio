"""Slave register datastore — in-memory holding and input register banks."""

from __future__ import annotations

_MAX_ADDRESS = 65535
_MAX_VALUE = 65535


class RegisterBank:
    """A flat array of 16-bit Modbus registers.

    Default size covers the full Modbus address space (65536 registers).
    All values are initialised to *default_value*.
    """

    def __init__(self, size: int = 65536, default_value: int = 0) -> None:
        if size < 1:
            raise ValueError("RegisterBank size must be >= 1")
        if not 0 <= default_value <= _MAX_VALUE:
            raise ValueError("RegisterBank default_value must be in range 0..65535")
        self._size = size
        self._registers: list[int] = [default_value] * size

    # ── read ──────────────────────────────────────────────────────────────

    def read(self, address: int, quantity: int) -> list[int]:
        """Return *quantity* registers starting at *address*.

        Raises ValueError if address or the requested range are out of bounds.
        """
        self._validate_address(address)
        if quantity < 1:
            raise ValueError("quantity must be >= 1")
        end = address + quantity
        if end > self._size:
            raise ValueError(
                f"Read range {address}..{end - 1} exceeds bank size {self._size}"
            )
        return list(self._registers[address:end])

    # ── write ─────────────────────────────────────────────────────────────

    def write_register(self, address: int, value: int) -> None:
        """Write one register value."""
        self._validate_address(address)
        self._validate_value(value)
        self._registers[address] = value

    def write_range(self, address: int, values: list[int]) -> None:
        """Write a contiguous block of register values."""
        self._validate_address(address)
        end = address + len(values)
        if end > self._size:
            raise ValueError(
                f"Write range {address}..{end - 1} exceeds bank size {self._size}"
            )
        for i, v in enumerate(values):
            self._validate_value(v)
            self._registers[address + i] = v

    def clear(self, value: int = 0) -> None:
        """Reset all registers to *value*."""
        self._validate_value(value)
        for i in range(self._size):
            self._registers[i] = value

    # ── helpers ───────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return self._size

    def _validate_address(self, address: int) -> None:
        if not 0 <= address <= _MAX_ADDRESS:
            raise ValueError(f"address must be in range 0..65535, got {address}")
        if address >= self._size:
            raise ValueError(
                f"address {address} is out of range for bank size {self._size}"
            )

    @staticmethod
    def _validate_value(value: int) -> None:
        if not 0 <= value <= _MAX_VALUE:
            raise ValueError(f"value must be in range 0..65535, got {value}")


class SlaveDatastore:
    """Dual-bank Modbus slave register store.

    Holds separate *holding registers* (FC03) and *input registers* (FC04).
    Both banks are full-size (65536 registers) by default.
    """

    def __init__(
        self,
        holding_size: int = 65536,
        input_size: int = 65536,
        default_value: int = 0,
    ) -> None:
        self.holding_registers = RegisterBank(size=holding_size, default_value=default_value)
        self.input_registers = RegisterBank(size=input_size, default_value=default_value)

    # ── read ──────────────────────────────────────────────────────────────

    def read_holding_registers(self, address: int, quantity: int) -> list[int]:
        return self.holding_registers.read(address, quantity)

    def read_input_registers(self, address: int, quantity: int) -> list[int]:
        return self.input_registers.read(address, quantity)

    # ── write holding ─────────────────────────────────────────────────────

    def write_holding_register(self, address: int, value: int) -> None:
        self.holding_registers.write_register(address, value)

    def write_holding_range(self, address: int, values: list[int]) -> None:
        self.holding_registers.write_range(address, values)

    # ── write input ───────────────────────────────────────────────────────

    def write_input_register(self, address: int, value: int) -> None:
        self.input_registers.write_register(address, value)

    def write_input_range(self, address: int, values: list[int]) -> None:
        self.input_registers.write_range(address, values)
