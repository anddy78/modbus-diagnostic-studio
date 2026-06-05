"""Slave register and bit datastore — in-memory banks for all four Modbus data types."""

from __future__ import annotations

_MAX_ADDRESS = 65535
_MAX_VALUE = 65535


# ── RegisterBank ──────────────────────────────────────────────────────────────


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


# ── BitBank ───────────────────────────────────────────────────────────────────


class BitBank:
    """A flat array of single-bit (boolean) Modbus data points.

    Covers coils and discrete inputs.  Values must be strictly bool, 0, or 1.
    Any other value (including integers != 0/1) is rejected to avoid ambiguity.
    """

    def __init__(self, size: int = 65536, default_value: bool = False) -> None:
        if size < 1:
            raise ValueError("BitBank size must be >= 1")
        self._size = size
        self._bits: list[bool] = [bool(default_value)] * size

    # ── read ──────────────────────────────────────────────────────────────

    def read(self, address: int, quantity: int) -> list[bool]:
        """Return *quantity* bits starting at *address*.

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
        return list(self._bits[address:end])

    # ── write ─────────────────────────────────────────────────────────────

    def write_bit(self, address: int, value: bool | int) -> None:
        """Write one bit value.

        Accepts bool or integers 0/1 only.  All other values raise ValueError.
        """
        self._validate_address(address)
        self._bits[address] = self._validate_bit_value(value)

    def write_range(self, address: int, values: list[bool | int]) -> None:
        """Write a contiguous block of bit values."""
        self._validate_address(address)
        end = address + len(values)
        if end > self._size:
            raise ValueError(
                f"Write range {address}..{end - 1} exceeds bank size {self._size}"
            )
        validated = [self._validate_bit_value(v) for v in values]
        for i, b in enumerate(validated):
            self._bits[address + i] = b

    def clear(self, value: bool | int = False) -> None:
        """Reset all bits to *value*."""
        fill = self._validate_bit_value(value)
        for i in range(self._size):
            self._bits[i] = fill

    # ── helpers ───────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return self._size

    def _validate_address(self, address: int) -> None:
        if not 0 <= address <= 65535:
            raise ValueError(f"address must be in range 0..65535, got {address}")
        if address >= self._size:
            raise ValueError(
                f"address {address} is out of range for bank size {self._size}"
            )

    @staticmethod
    def _validate_bit_value(value: bool | int) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        raise ValueError(
            f"Bit value must be bool or 0/1, got {value!r} ({type(value).__name__})"
        )


# ── SlaveDatastore ─────────────────────────────────────────────────────────────


class SlaveDatastore:
    """Four-bank Modbus slave data store: coils, discrete inputs, holding and input registers.

    All banks default to 65536 data points, initialised to zero/False.
    """

    def __init__(
        self,
        holding_size: int = 65536,
        input_size: int = 65536,
        coil_size: int = 65536,
        discrete_size: int = 65536,
        default_value: int = 0,
    ) -> None:
        self.holding_registers = RegisterBank(size=holding_size, default_value=default_value)
        self.input_registers = RegisterBank(size=input_size, default_value=default_value)
        self.coils = BitBank(size=coil_size)
        self.discrete_inputs = BitBank(size=discrete_size)

    # ── register reads ────────────────────────────────────────────────────

    def read_holding_registers(self, address: int, quantity: int) -> list[int]:
        return self.holding_registers.read(address, quantity)

    def read_input_registers(self, address: int, quantity: int) -> list[int]:
        return self.input_registers.read(address, quantity)

    # ── bit reads ─────────────────────────────────────────────────────────

    def read_coils(self, address: int, quantity: int) -> list[bool]:
        return self.coils.read(address, quantity)

    def read_discrete_inputs(self, address: int, quantity: int) -> list[bool]:
        return self.discrete_inputs.read(address, quantity)

    # ── holding register writes ───────────────────────────────────────────

    def write_holding_register(self, address: int, value: int) -> None:
        self.holding_registers.write_register(address, value)

    def write_holding_range(self, address: int, values: list[int]) -> None:
        self.holding_registers.write_range(address, values)

    # ── input register writes ─────────────────────────────────────────────

    def write_input_register(self, address: int, value: int) -> None:
        self.input_registers.write_register(address, value)

    def write_input_range(self, address: int, values: list[int]) -> None:
        self.input_registers.write_range(address, values)

    # ── coil writes ───────────────────────────────────────────────────────

    def write_coil(self, address: int, value: bool | int) -> None:
        self.coils.write_bit(address, value)

    def write_coil_range(self, address: int, values: list[bool | int]) -> None:
        self.coils.write_range(address, values)

    # ── discrete input writes ─────────────────────────────────────────────

    def write_discrete_input(self, address: int, value: bool | int) -> None:
        self.discrete_inputs.write_bit(address, value)

    def write_discrete_input_range(self, address: int, values: list[bool | int]) -> None:
        self.discrete_inputs.write_range(address, values)

    # ── reset ─────────────────────────────────────────────────────────────

    def clear_all(self) -> None:
        """Reset all four banks to zero / False."""
        self.holding_registers.clear()
        self.input_registers.clear()
        self.coils.clear()
        self.discrete_inputs.clear()
