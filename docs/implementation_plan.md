# Implementation Plan

## Phase 0
Create repository skeleton, AGENTS.md, agent skills and project metadata.

## Phase 1
Implement core Modbus utilities:
- CRC16
- RTU frame parser
- raw decoder
- endian helpers
- tests

## Phase 2
Implement profile system:
- register profile models
- YAML loader
- validator
- built-in register profiles
- profile-based register decoding

## Phase 3
Implement active connection and master foundations.

### Phase 3A
Implement COM discovery and serial connection settings.

### Phase 3B
Implement minimal RTU transport and MasterClient FC03/FC04 with fake-transport tests.

### Phase 3D
Implement Communication Profiles.

Scope:
- Define communication profile model and YAML schema.
- Add built-in communication profiles for common master/slave conversations:
  - Generic Master -> Generic Slave
  - Huawei SmartLogger -> Chint DTSU71
  - Huawei SmartLogger -> Janitza UMG604
  - Inverter -> Eastron SDM630
  - Inverter -> DTSU666
- Link communication profiles to register profiles where known.
- Define expected baudrate, parity, stopbits, slave IDs, function codes, request blocks, polling intervals and diagnostic thresholds.

### Phase 3E
Implement Passive Sniffer Diagnostics Core.

Scope:
- Passive RTU byte stream ingestion.
- Frame boundary handling without transmitting.
- Request/response matching.
- CRC OK/error counters.
- Missing response and timeout detection.
- Slave ID, function code, address, quantity and byte-count summaries.
- Modbus exception summaries.
- Request-response latency and polling frequency metrics.
- Incomplete frame reporting.
- Preliminary conclusions:
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
- Fingerprint matching against communication profiles.
- Safety checks ensuring sniffer code has no send/write APIs and never calls `serial.write()`.

## Phase 4
Implement PySide6 GUI in focused increments.

### Phase 4A
Implement GUI minima Connection + Decoder.

Scope:
- COM listing.
- Serial settings form.
- Raw hex decoder view.
- Clear active/passive mode labels.

### Phase 4B
Implement GUI Master Read.

Scope:
- Active master read panel for FC03/FC04.
- Clear active mode warning.
- No shared COM port with passive sniffer sessions.

### Phase 4C
Implement GUI Sniffer Diagnostic.

Scope:
- Passive mode banner/status.
- Start/stop passive capture.
- Traffic present/absent indicator.
- Request/response summaries.
- CRC and timeout rates.
- Latency and polling frequency.
- Communication profile suggestion.
- Preliminary diagnostic conclusions.
- Exportable diagnostic report.

## Phase 5
Implement Slave/Simulator.

## Phase 6
Expand GUI workflows after core diagnostic features are stable.

## Phase 7
Implement Windows packaging.
