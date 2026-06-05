# Architecture

Status: draft.

Primary decision:
Build a self-contained Windows desktop app using Python + PySide6.

Product direction:
The app should grow into a complete Modbus diagnostic workbench with two deliberate layers:
- friendly diagnostics for meter users and quick checks
- advanced diagnostics for technicians who need raw registers, protocol functions and simulation

Core principles:
- GUI-independent Modbus core.
- Passive sniffer must never transmit.
- Profiles drive decoding and simulation.
- Built-in profiles are bundled with the app.
- Windows packaging is a first-class requirement.

## Layers

- `core/`: CRC, RTU frame parsing, endian helpers and raw frame decoding.
- `models/`: dataclasses for Modbus frames, profile definitions, connection settings and future capture models.
- `profiles/`: register profile loading, validation and profile-based value decoding.
- `transports/`: active serial/TCP wrappers. These are used by active master/slave workflows, not by passive sniffer diagnostics.
- `master/`: active Modbus master operations.
- `slave/`: active simulator/slave operations.
- `sniffer/`: passive RTU capture, frame reconstruction, request/response matching, diagnostics and capture output.
- `services/`: application state, event bus, sessions and reports.
- `gui/`: PySide6 user interface only. GUI must call services/core modules and must not implement protocol logic directly.

The GUI should also provide a theme selector with System, Light and Dark modes.

## Passive Sniffer Diagnostic

Passive Sniffer Diagnostic is a central operating mode.

Its purpose is to answer whether a real Modbus RTU conversation between devices is healthy, not only to display raw frames. It must remain software-passive at all times.

The sniffer diagnostic core should detect:
- bus traffic present or absent
- requests from the master
- responses from the slave
- CRC OK frames and CRC errors
- timeouts or missing responses
- slave IDs seen
- function codes seen
- requested addresses and quantities
- response byte counts
- Modbus exception responses
- request-response latency
- polling frequency
- incomplete frames
- possible serial configuration mismatch inferred from noise, CRC rate or framing error patterns

The diagnostic engine should produce preliminary conclusions:
- Communication OK.
- Master queries but slave does not respond.
- Responses have invalid CRC.
- Unexpected slave ID.
- Unexpected function code.
- Unexpected register block.
- Polling too slow or too fast.
- Possible baudrate/parity/stopbits mismatch.
- Possible A/B line inversion.
- Possible powered-off device.
- Possible sniffer adapter is seeing only one side of the bus.

## Sniffer Safety Boundary

The passive sniffer is separate from active master/slave transports.

Hard rules:
- Sniffer mode must never transmit.
- Sniffer code must not call `serial.write()`.
- Sniffer code must not expose send/write APIs.
- The UI must clearly show passive mode status.
- The same COM port must not be shared between passive sniffer and active master/slave modes.
- Software passivity does not prove electrical passivity; wiring and adapter notes belong in hardware documentation.

## Friendly And Advanced Layers

The user experience should be split into two explicit layers rather than one flat control surface.

Friendly layer:
- meter selection
- serial connection settings
- guided single reads and continuous reads
- summary electrical values
- fast diagnostics for common devices

Advanced layer:
- raw register views
- manual FC01, FC02, FC03 and FC04 operations
- simulator workflows
- register editing and range editing
- protocol-level inspection

The friendly layer should favor quick, low-friction workflows.
The advanced layer should keep every active operation explicit.

Future write operations must be clearly marked as active actions and require explicit user confirmation.

## Register Profiles

Register profiles define how values are decoded from Modbus registers.

They include:
- profile id and human-readable name
- default function code
- byte/word order
- base addressing
- register definitions with variable, address, type, unit, scale and description

Examples:
- `generic_meter`
- `chint_dtsu71`
- `dtsu666`
- `eastron_sdm230`
- `eastron_sdm630`
- `janitza_umg604`

## Communication Profiles

Communication profiles are separate from register profiles.

They define the expected conversation between a master role and a slave role. They are used by Passive Sniffer Diagnostic for validation, fingerprinting and preliminary diagnosis.

Examples:
- Generic Master -> Generic Slave
- Inverter -> Meter
- Meter as slave -> Inverter as master
- Inverter as slave -> Energy Manager as master
- Inverter as slave -> SmartLogger as master
- Huawei SmartLogger -> Chint DTSU71
- Huawei SmartLogger -> Janitza UMG604
- Inverter -> Eastron SDM630
- Inverter -> DTSU666

Communication profiles should support:
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

## Meter Workflows

Meter-oriented workflows should reuse the existing register profiles and present friendly electrical names and units.

These workflows should emphasize:
- selected meter model
- selected COM settings
- slave ID
- single read
- continuous read
- summary values such as voltage, current, power and frequency

This layer is for quick diagnosis and should stay approachable for non-expert users.

## Fingerprint-Based Profile Suggestions

The sniffer should be able to suggest a likely communication profile by comparing observed traffic against known fingerprints:
- slave ID
- function code
- address
- quantity
- polling interval
- response pattern
- linked register profile

Example:
If FC03 address 2102 quantity 42 appears every 180-200 ms and FC03 address 2158 quantity 66 appears around every 10 s, the diagnostic engine may suggest Huawei SmartLogger -> Chint DTSU71.

## Advanced Master And Slave Simulation

The advanced side of the app should eventually include:
- a manual master panel for FC01, FC02, FC03 and FC04
- a simulator-oriented slave panel
- raw register editing
- range editing
- support for holding registers and input registers first
- coils and discrete inputs in later phases
- profile-backed simulator presets for known meters
