# AGENTS.md — Modbus Diagnostic Studio

## Project identity

This is a NEW independent repository.

Project goal:
Build a self-contained Windows desktop application for industrial Modbus diagnostics.

The existing repository `anddy78/modbus_meter_bridge` is only a technical reference.
Do not extend it.
Do not blindly copy code from it.
Extract concepts, profiles, maps, lessons, safety rules and tests where useful.

Primary target:
- Windows 10/11
- Installable or portable desktop application
- No loose scripts required from the user
- No manual terminal workflow for end users
- The final user should launch the app from an `.exe` or shortcut

Preferred stack:
- Python
- PySide6 / Qt for native desktop GUI
- pyserial for RTU serial access
- pymodbus for Master/Slave where appropriate
- Custom parser for passive RTU sniffing
- PyInstaller for packaging
- pytest for tests

Acceptable secondary architecture:
A local web GUI is acceptable only if explicitly approved.
If used, it must be started by a single executable that launches the local backend and opens the browser automatically.
Do not design loose scripts plus manual browser steps.

## User environment

The user works on Windows.

All commands provided to the user must be PowerShell commands.

Do not use:
- Bash syntax
- `mkdir -p`
- `touch`
- `cat <<EOF`
- `source`
- `chmod`
- Linux paths such as `/home/...`

Use:
- PowerShell
- Windows paths
- `.\.venv\Scripts\Activate.ps1`
- `New-Item`
- PowerShell here-strings when creating files

## Non-negotiable safety rules

1. Sniffer mode must NEVER transmit.
2. Sniffer code must not expose write/send APIs.
3. Passive capture must not call `serial.write()`.
4. The GUI must clearly show passive vs active modes.
5. Do not allow the same serial adapter to be used simultaneously for sniffer and slave/master.
6. Handle USB-RS485 disconnection without crashing.
7. Use bounded buffers and log rotation.
8. Do not hide stale data as valid data.
9. Do not create cloud, telemetry, remote-control or internet-exposed features unless explicitly requested.
10. Do not expose network services beyond localhost unless explicitly requested.
11. Do not commit secrets, API keys, private captures, client data or personal data.
12. Do not implement large unrelated features.

## Development workflow

Default mode:
- Plan first.
- Make small changes.
- Keep code boring, explicit and testable.
- Add or update tests with every core behavior.
- Prefer pure core modules before GUI integration.
- Stop after the requested scope.

Before modifying code:
1. Read this AGENTS.md.
2. Read the relevant file under `agent_skills/`.
3. State the planned files to change.
4. Keep the change minimal.

After modifying code:
1. Run relevant tests.
2. Show concise diff summary.
3. List validation commands and results.
4. Mention known limitations.

## Repository architecture

Core must be GUI-independent.

Expected layers:

- `core/`
  Protocol-level logic: CRC, RTU frame parsing, endian decoding, raw decoding.

- `models/`
  Dataclasses or Pydantic models for Modbus frames, decoded values, profiles, captures and electrical snapshots.

- `profiles/`
  Profile loading, validation, built-in profiles and fingerprinting.

- `transports/`
  Serial and TCP communication wrappers.

- `master/`
  Active Modbus master operations.

- `slave/`
  Slave/simulator logic and dynamic datastore.

- `sniffer/`
  Passive RTU stream parser, request/response matcher, capture writer and stats.

- `decoder/`
  Raw frame decoder and helper tools.

- `services/`
  Application state, event bus, capture sessions and report builders.

- `gui/`
  PySide6 application only.
  GUI must call services/core modules.
  GUI must not implement protocol logic directly.

## Testing expectations

Core modules must be covered first.

Initial required tests:
- CRC16 Modbus
- RTU request parsing
- RTU response parsing
- Modbus exceptions
- float32 endian/word-order decoding
- profile loader
- profile validator
- energy accumulator
- sniffer frame boundary handling

Do not build the full GUI before core tests exist.

## Packaging expectations

The final app must support:

- portable `.exe` or folder release
- later installer option
- bundled built-in profiles
- local writable config directory
- local writable logs directory
- local writable captures directory
- local writable exports directory

Do not hardcode Linux paths.
Use Windows-safe path handling.

Expected writable folders:
- config/
- logs/
- captures/
- exports/

## Reference repo lessons

From `modbus_meter_bridge`, preserve these concepts:

- Separate physical polling from external slave responses.
- Use normalized electrical models.
- Use profile-driven register decoding.
- Treat observed/non-official profiles explicitly.
- Keep request history and status counters.
- Add safety checks for stale data.
- Test register maps and energy accumulator behavior.
- Keep active and passive modes visually distinct.

Avoid copying:

- Raspberry Pi systemd assumptions
- Linux-only serial paths
- Web UI architecture unless explicitly approved
- Bridge-specific runtime state
- SmartLogger-only assumptions as global rules

## Modbus initial scope

Initial supported features:
- FC03 Read Holding Registers
- FC04 Read Input Registers
- Modbus RTU CRC validation
- Modbus exception frames
- Slave ID, function code, address, quantity, byte count decoding
- Raw hex decoder
- Profile-based register decoding

Initial profiles:
- Chint DTSU71
- Eastron SDM630
- Janitza UMG604
- Generic configurable profile

## Stop conditions

Stop and ask/report if:
- A task requires changing project scope.
- A task risks making sniffer mode transmit.
- A task requires undocumented protocol assumptions.
- Hardware behavior cannot be validated from available data.
- Packaging requires OS-specific testing not available in the current environment.
