"""Minimal Modbus domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModbusRtuFrame:
    """A CRC-validated Modbus RTU frame."""

    slave_id: int
    function_code: int
    payload: bytes
    raw_without_crc: bytes
    crc: int
    raw: bytes


@dataclass(frozen=True)
class ModbusReadRequest:
    """A parsed FC03/FC04 read request."""

    slave_id: int
    function_code: int
    address: int
    quantity: int
    raw: bytes


@dataclass(frozen=True)
class ModbusReadResponse:
    """A parsed FC03/FC04 read response."""

    slave_id: int
    function_code: int
    byte_count: int
    data: bytes
    registers: list[int]
    raw: bytes


@dataclass(frozen=True)
class ModbusExceptionResponse:
    """A parsed Modbus exception response."""

    slave_id: int
    function_code: int
    exception_code: int
    raw: bytes
