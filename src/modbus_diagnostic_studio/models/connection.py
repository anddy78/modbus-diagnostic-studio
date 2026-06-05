"""Connection models for serial Modbus RTU access."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SerialConnectionSettings:
    """Validated serial connection settings."""

    port: str
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 1.0

    def __post_init__(self) -> None:
        if not self.port:
            raise ValueError("Serial port must not be empty")
        if self.baudrate <= 0:
            raise ValueError("Serial baudrate must be > 0")
        if self.bytesize not in {5, 6, 7, 8}:
            raise ValueError("Serial bytesize must be one of 5, 6, 7, 8")
        if self.parity not in {"N", "E", "O", "M", "S"}:
            raise ValueError("Serial parity must be one of N, E, O, M, S")
        if self.stopbits not in {1, 1.5, 2}:
            raise ValueError("Serial stopbits must be one of 1, 1.5, 2")
        if self.timeout <= 0:
            raise ValueError("Serial timeout must be > 0")


@dataclass(frozen=True)
class SerialPortInfo:
    """Discovered serial port metadata."""

    device: str
    name: str
    description: str
    hwid: str
    manufacturer: str | None = None
    vid: int | None = None
    pid: int | None = None
