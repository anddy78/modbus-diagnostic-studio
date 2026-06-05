# Profile Model

Modbus Diagnostic Studio uses three complementary profile layers.

## Register Profile

A register profile describes the register map exposed by a device acting as a Modbus slave.

Typical contents:
- `profile_id`
- human-readable name
- default function
- byte and word order
- register definitions with address, type, scale, unit, and description

Example:
- a meter register map used by the Meters tab or Advanced Master read workflows

## Communication Profile

A communication profile describes an observed or expected Modbus RTU conversation between a master role and a slave role.

Typical contents:
- `profile_id`
- master role and slave role
- expected serial settings
- expected slave ids and function codes
- expected request blocks
- polling intervals
- linked register profile when known

Example:
- `Huawei SmartLogger -> Chint DTSU71`

## Device Profile

A device profile represents the physical or logical equipment identity and groups one or more roles.

Typical contents:
- `device_id`
- manufacturer and model
- device type
- role links
- source and status metadata

Each role link points to a specific profile type, such as:
- `register_profile`
- `communication_profile`
- future dashboard or diagnostic profile types

## Examples

Inverter example:
- role `slave`: exposes its own register map to a PC, SCADA, logger, or EMS.
- role `master`: polls an external meter or BMS.

Meter example:
- role `slave`: exposes measurement registers.
- role `master_target`: represents the communication fingerprint seen when an inverter or SmartLogger polls the meter.

## User Profiles

Writable runtime folders:
- `profiles\user\`
- `device_profiles\user\`

The `Profile Manager` tab loads built-in device profiles, lists bundled register profiles, validates selected entries, and imports YAML files into `device_profiles\user\`.
