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


@dataclass(frozen=True)
class ModbusBitReadRequest:
    """A parsed FC01/FC02 bit read request."""

    slave_id: int
    function_code: int
    address: int
    quantity: int
    raw: bytes


@dataclass(frozen=True)
class ModbusWriteSingleCoilRequest:
    """A parsed FC05 Write Single Coil request."""

    slave_id: int
    function_code: int
    address: int
    value: bool
    raw: bytes


@dataclass(frozen=True)
class ModbusWriteSingleRegisterRequest:
    """A parsed FC06 Write Single Register request."""

    slave_id: int
    function_code: int
    address: int
    value: int
    raw: bytes


@dataclass(frozen=True)
class ModbusWriteMultipleCoilsRequest:
    """A parsed FC15 (0x0F) Write Multiple Coils request."""

    slave_id: int
    function_code: int
    address: int
    quantity: int
    byte_count: int
    values: list[bool]
    raw: bytes


@dataclass(frozen=True)
class ModbusWriteMultipleRegistersRequest:
    """A parsed FC16 (0x10) Write Multiple Registers request."""

    slave_id: int
    function_code: int
    address: int
    quantity: int
    byte_count: int
    values: list[int]
    raw: bytes
