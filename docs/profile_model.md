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

The `Profile Manager` register preview now shows known register details including function, bank, quantity, scale, and description.

The `Slave Simulator`, `Master Read`, and `Advanced Master` tabs can also use built-in profiles as guidance:
- they list known registers from the selected profile
- selecting a known register prefills address, function, quantity, and decode-related fields where applicable
- selecting a known register does not automatically read, write, or start communication

The `Slave Simulator` can also use a selected register profile to generate reasonable demo meter values in its local `SlaveDatastore`.
This generation is local to the simulator, can use optional smooth random variation, and does not transmit Modbus requests to external equipment.

Typical simulator examples:
- `SDM230` or `generic_meter` with `Single phase`
- `SDM630`, `DTSU666`, or similar three-phase profile with `Three phase balanced`
- `SDM630` or `DTSU666` with `Three phase meter / single-phase load` to simulate a three-phase meter where only one phase carries load

These scenarios only assist the local simulator datastore. They do not automatically start the slave server or trigger any external Modbus traffic.
