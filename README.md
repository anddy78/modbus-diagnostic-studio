# Modbus Diagnostic Studio

Self-contained Windows desktop application for industrial Modbus diagnostics.

## 0.1.0-rc1 Highlights

- guarded active master writes
- passive sniffer
- continuous capture recorder
- capture viewer
- diagnostic report
- slave simulator scenarios
- portable Windows ZIP

`0.1.0-rc1` is a release candidate. Validate it in a controlled environment before using it in field-critical workflows.

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
  - reusable scenario presets can be saved and loaded from `scenarios\slave`
- `Sniffer Diagnostic`: passive bus diagnostics that never transmit
  - separate poll interval, UI update interval, and fingerprint interval controls
  - display pause/resume without stopping capture
  - optional continuous capture recorder to `captures\` for longer passive sessions
- `Capture Viewer`: open offline JSONL/CSV captures, decode selected frames, export AI-ready bundles, and add evidence to Diagnostic Report
- `Raw Frame Decoder`: offline decoder for pasted RTU frames
- `Basic Master`: simple one-shot Modbus reads
- `Profile Manager`: manage device/register profile metadata
- `Diagnostic Report`: centralize notes and export diagnostic evidence as JSON, CSV, or HTML

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

## Quick Start RC1

### From the portable ZIP

1. Download and extract `ModbusDiagnosticStudio_0.1.0-rc1_portable.zip`.
2. Open `dist\ModbusDiagnosticStudioPortable\`.
3. Run `ModbusDiagnosticStudioPortable.exe`.

### From the virtual environment

```powershell
.\.venv\Scripts\python.exe -m modbus_diagnostic_studio.main
```

### Safe write testing workflow

For Master Write testing in this RC1 build, use the built-in Slave Simulator first. Do not write to real equipment unless you have explicit authorization.

### Reusable slave scenarios

The `Slave Simulator` can save and load reusable JSON presets for electrical demo scenarios such as:
- `SDM230` single-phase 1 kW
- `SDM630` balanced three-phase 5 kW
- `SDM630` with single-phase load on `L1`

Scenario loading only restores controls and selected profiles. It does not open ports, does not transmit, and does not apply values to the datastore until `Generate Demo Meter Values` is pressed.

### Profile model layers

- Register Profiles describe the register map exposed by a device acting as a slave.
- Communication Profiles describe the expected polling pattern between a master and a slave.
- Device Profiles group those roles under one equipment identity and are managed from the `Profile Manager` tab.
- The legacy `Profiles` widget remains in the codebase for compatibility, but the main GUI now uses only `Profile Manager`.

### Diagnostic Report

- `Diagnostic Report` centralizes session metadata, manual notes, and exported evidence.
- It can save/load session JSON and export CSV/HTML reports.
- This tab does not open serial ports and does not transmit.
- Automatic cross-tab evidence capture is incremental; v1 already accepts manual notes and can receive lightweight entries from `Advanced Master`.

### Continuous sniffer capture and offline review

- `Sniffer Diagnostic` still supports manual in-memory export, but `Record to file` is intended for 30-second or multi-minute passive captures without losing older events from bounded GUI buffers.
- Continuous recorder output is written locally under `captures\` as JSONL files plus a small manifest.
- `Capture Viewer` opens those offline JSONL files, or the existing CSV exports, without opening ports or transmitting.
- From `Capture Viewer` you can decode one selected frame, copy raw hex, add a decoded finding to an active `Diagnostic Report` session, or export an offline `AI Bundle` JSON.
- `AI Bundle` export only writes a local file; review sensitive capture contents before sharing it externally.
- The portable build script also writes a companion `.sha256` file next to the ZIP release.

### Where files go

- Captures: `captures\`
- Logs: `logs\`
- Operation log exports: `exports\`
- Local config: `config\`
- User register profiles: `profiles\user\`
- User device profiles: `device_profiles\user\`
