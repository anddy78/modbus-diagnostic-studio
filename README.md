# Modbus Diagnostic Studio

Self-contained Windows desktop application for industrial Modbus diagnostics.

## Product Direction

Modbus Diagnostic Studio is evolving into a two-layer workbench:

1. Friendly layer
   - guided meter selection
   - single and continuous reads
   - summary electrical values
   - quick diagnostics for common devices
2. Advanced layer
   - raw registers
   - manual Modbus function access
   - simulation
   - expert-focused troubleshooting

The theme selector will support `System`, `Light` and `Dark` modes.

## Goals

- Friendly meter diagnostics
- Advanced Modbus master tools
- Passive RTU sniffer diagnostics
- Raw frame decoder
- Profile-based decoding
- Role-oriented Device Profile Manager
- Meter simulation
- Windows portable/installer packaging

## Main Tabs

- `Serial Ports`: lists detected COM ports without opening them
- `Meter Dashboard`: friendly profile-based meter reading
- `Advanced Master`: advanced reads, decoding, logging, and guarded writes
- `Slave Simulator`: local Modbus slave simulation for safe testing
- `Sniffer Diagnostic`: passive bus diagnostics that never transmit
- `Raw Frame Decoder`: offline decoder for pasted RTU frames
- `Basic Master`: simple one-shot Modbus reads
- `Profile Manager`: manage device/register profile metadata

## Initial Supported Profiles

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

Future Modbus write features will require explicit user confirmation and will remain clearly marked as active operations.

## Development on Windows

Create virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run validation:

```powershell
.\.venv\Scripts\python.exe -m compileall src tests
.\.venv\Scripts\python.exe -m pytest -q
```

Run application entry point:

```powershell
.\.venv\Scripts\python.exe -m modbus_diagnostic_studio.main
```

## Packaging Target

The final application must run as:

- `ModbusDiagnosticStudio.exe`
- or as a portable Windows folder containing the executable, profiles, config, logs and captures

## Quick Start Beta

### From the portable ZIP

1. Download and extract `ModbusDiagnosticStudio_0.1.0-beta_portable.zip`.
2. Open `dist\ModbusDiagnosticStudioPortable\`.
3. Run `ModbusDiagnosticStudioPortable.exe`.

### From the virtual environment

```powershell
.\.venv\Scripts\python.exe -m modbus_diagnostic_studio.main
```

### Safe write testing workflow

For Master Write testing in this beta, use the built-in Slave Simulator first. Do not write to real equipment unless you have explicit authorization.

### Profile model layers

- Register Profiles describe the register map exposed by a device acting as a slave.
- Communication Profiles describe the expected polling pattern between a master and a slave.
- Device Profiles group those roles under one equipment identity and are managed from the `Profile Manager` tab.
- The legacy `Profiles` widget remains in the codebase for compatibility, but the main GUI now uses only `Profile Manager`.

### Where files go

- Captures: `captures\`
- Logs: `logs\`
- Operation log exports: `exports\`
- Local config: `config\`
- User register profiles: `profiles\user\`
- User device profiles: `device_profiles\user\`
