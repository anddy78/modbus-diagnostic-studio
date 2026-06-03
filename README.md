# Modbus Diagnostic Studio

Self-contained Windows desktop application for industrial Modbus diagnostics.

## Goals

- Modbus Master RTU
- Modbus Master TCP
- Modbus Slave RTU
- Modbus Slave TCP
- Passive RTU sniffer
- Raw frame decoder
- Live dashboard
- Profile-based decoding
- Meter simulation
- Windows portable/installer packaging

## Initial supported profiles

- Chint DTSU71
- Eastron SDM630
- Janitza UMG604
- Generic configurable profile

## Status

Initial architecture phase.

This is a new independent repository.

The previous `modbus_meter_bridge` repository is used only as a technical reference.

## Safety

Sniffer mode must never transmit.

Passive sniffing must be visually distinct from active Master/Slave modes.

## Development on Windows

Create virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

Run validation:

python -m compileall src tests
pytest -q

Run application entry point:

python -m modbus_diagnostic_studio.main
Packaging target

The final application must run as:

ModbusDiagnosticStudio.exe

or as a portable Windows folder containing the executable, profiles, config, logs and captures.
