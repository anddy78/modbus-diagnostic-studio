# AGENTS.md — Modbus Diagnostic Studio

## Project identity

This is a NEW independent repository.

Project goal:
Build a self-contained Windows desktop application for industrial Modbus diagnostics.

Product direction:
Evolve into a complete Modbus diagnostic workbench with two clear layers:
- a friendly layer for meter-centric diagnostics and guided workflows
- an advanced layer for raw registers, protocol functions and simulation

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
- Passive Sniffer Diagnostic as a central operating mode
- PyInstaller for packaging
- pytest for tests

UI direction:
- include a theme selector with System, Light and Dark modes
- keep passive and active modes visually distinct
- make meter workflows approachable for non-expert users
- keep advanced workflows explicit for technicians

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
13. Future Modbus write features must require explicit user confirmation and remain clearly marked as active operations.

## Passive Sniffer Diagnostic

Passive Sniffer Diagnostic is a central requirement of this project.

The sniffer must be an industrial diagnostic tool, not only a frame list.
It must help determine whether a Modbus RTU conversation between devices is working correctly.

The sniffer must detect and summarize:
- whether there is traffic on the bus
- whether the master is sending requests
- whether the slave is sending responses
- CRC OK counts and CRC error counts
- timeouts or missing responses
- slave IDs observed
- function codes observed
- requested addresses
- requested quantities
- response byte counts
- Modbus exception responses
- request-response latency
- polling frequency
- incomplete frames
- possible baudrate, parity or stopbits mismatch inferred from noise, CRC rate or framing error patterns

The sniffer must be able to produce preliminary conclusions such as:
- Communication OK.
- Master queries but slave does not respond.
- Responses have invalid CRC.
- Unexpected slave ID.
- Unexpected function code.
- Unexpected register block.
- Polling too slow or too fast.
- Possible serial configuration mismatch.
- Possible A/B line inversion.
- Possible powered-off device.
- Possible sniffer adapter is seeing only one side of the bus.

The sniffer must support fingerprint-based suggestions by comparing:
- slave ID
- function code
- address
- quantity
- polling interval
- response pattern
- linked register profile

Example:
If the sniffer observes FC03 address 2102 quantity 42 every 180-200 ms and FC03 address 2158 quantity 66 around every 10 s, it may suggest the communication profile Huawei SmartLogger -> Chint DTSU71.

Sniffer safety requirements are absolute:
- Sniffer mode must never transmit.
- Sniffer code must not call `serial.write()`.
- Sniffer code must not expose send/write APIs.
- The UI must clearly show passive mode status.
- The same COM port must not be shared between sniffer and active master/slave modes.
- Software passivity does not guarantee electrical passivity; hardware notes must be documented separately when relevant.

Product layering:
- Friendly layer: meter selection, guided reads, summary values and quick diagnostics.
- Advanced layer: raw frames, Modbus function access, register-level inspection and simulation tools.
- The friendly layer should stay approachable while the advanced layer remains explicit for experts.

## Communication profiles

Communication profiles are distinct from register profiles.

Register profiles describe how to decode register values for a device.
Communication profiles describe an expected Modbus RTU conversation between a master role and a slave role.

Example communication profiles:
- Generic Master -> Generic Slave
- Inverter -> Meter
- Meter as slave -> Inverter as master
- Inverter as slave -> Energy Manager as master
- Inverter as slave -> SmartLogger as master
- Huawei SmartLogger -> Chint DTSU71
- Huawei SmartLogger -> Janitza UMG604
- Inverter -> Eastron SDM630
- Inverter -> DTSU666

Communication profiles should be able to define:
- `profile_id`
- `name`
- `master_role`
- `slave_role`
- `expected_baudrate`
- `expected_parity`
- `expected_stopbits`
- `expected_slave_ids`
- `expected_functions`
- expected request blocks:
  - address
  - quantity
  - expected polling interval min/max
  - description
- linked register profile
- diagnostic thresholds:
  - max CRC error rate percent
  - max timeout rate percent
  - max response latency ms

## Theme and UX

The application should support at least these theme choices:
- System
- Light
- Dark

Theme selection is a product-level setting, not a protocol concern.
Keep the first-screen experience simple and clearly divided between friendly and advanced diagnostics.

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
  Passive RTU stream parser, request/response matcher, diagnostic engine, capture writer and stats.
  This layer must never transmit and must not expose write/send APIs.

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
- Add communication-profile-driven sniffer diagnostics.
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
- Passive Sniffer Diagnostic planning and safety rules
- Communication profile planning for diagnostic fingerprinting
- Friendly meter workflows and advanced Modbus workflows as separate UI layers

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
