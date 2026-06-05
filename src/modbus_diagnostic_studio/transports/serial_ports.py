"""Serial port discovery."""

from __future__ import annotations

from serial.tools import list_ports

from modbus_diagnostic_studio.models.connection import SerialPortInfo


def _device_sort_key(device: str) -> tuple[str, int, str]:
    prefix = device.rstrip("0123456789")
    suffix = device[len(prefix) :]
    if suffix:
        return (prefix, int(suffix), device)
    return (device, -1, device)


def list_serial_ports() -> list[SerialPortInfo]:
    """List available serial ports without opening them."""
    ports = [
        SerialPortInfo(
            device=port.device,
            name=getattr(port, "name", "") or "",
            description=getattr(port, "description", "") or "",
            hwid=getattr(port, "hwid", "") or "",
            manufacturer=getattr(port, "manufacturer", None),
            vid=getattr(port, "vid", None),
            pid=getattr(port, "pid", None),
        )
        for port in list_ports.comports()
    ]
    return sorted(ports, key=lambda port: _device_sort_key(port.device))
