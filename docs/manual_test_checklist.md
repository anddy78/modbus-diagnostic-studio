# Manual Test Checklist

Use this checklist to validate the RC1 GUI on Windows.

## App Startup

- [ ] App opens from the virtual environment.
- [ ] App opens from the portable EXE.

## Core GUI

- [ ] Serial Ports tab lists COM ports.
- [ ] Raw Frame Decoder tab decodes raw hex.
- [ ] Profile Manager tab loads built-in device profiles.
- [ ] Profile Manager lists built-in register profiles.
- [ ] Profile Manager shows register preview with descriptions.
- [ ] Profile Manager validates a selected device profile.
- [ ] Profile Manager opens `device_profiles\user`.
- [ ] Meter Dashboard tab opens.
- [ ] Main window does not show a separate `Profiles` tab.
- [ ] Diagnostic Report tab opens.
- [ ] About dialog shows `0.1.0-rc1`.
- [ ] Theme selector works.

## Advanced Master

- [ ] Advanced Master reads FC03 and FC04.
- [ ] Advanced Master reads FC01 and FC02 against Slave Simulator.
- [ ] Advanced Master known register selector prefills read fields without auto-reading.
- [ ] Protected write FC06 works against Slave Simulator after confirmation.
- [ ] Protected write FC05 works against Slave Simulator after confirmation.
- [ ] Protected write FC15 works against Slave Simulator after confirmation.
- [ ] Protected write FC16 works against Slave Simulator after confirmation.
- [ ] Master operation log exports to CSV and JSONL.

## Passive Sniffer

- [ ] Passive Sniffer Diagnostic starts and stops.
- [ ] Passive Sniffer does not transmit.
- [ ] Passive Sniffer exposes Poll interval, UI update interval, and Fingerprint interval controls.
- [ ] Passive Sniffer exposes `Record to file`, output folder, and base name controls.
- [ ] `Record to file` defaults to `captures\`.
- [ ] Pause Display pauses visual refresh while capture keeps running.
- [ ] Pause Display does not stop the recorder when `Record to file` is enabled.
- [ ] Resume Display restores visual refresh without reopening the port.
- [ ] Passive Sniffer exports captures to CSV and JSONL.
- [ ] Stop closes the recorder and leaves capture files on disk.
- [ ] Capture files stay visible after Stop.
- [ ] Records written keeps the final total after Stop.

## Capture Viewer

- [ ] Capture Viewer tab opens.
- [ ] Capture Viewer loads events JSONL from `captures\`.
- [ ] Capture Viewer loads CSV exports.
- [ ] Selecting a row updates Selected Raw Hex.
- [ ] Decode Selected Frame decodes offline without opening ports.
- [ ] Copy Raw Hex works.
- [ ] Export AI Bundle JSON creates a local JSON file.
- [ ] Add Selected Frame To Diagnostic Report works when a session is active.
- [ ] Capture Viewer shows `No active diagnostic session.` when no session exists.
- [ ] Capture Viewer never opens ports and never transmits.

## Slave Simulator

- [ ] Slave Simulator starts and stops.
- [ ] Slave Simulator profile selector shows known registers.
- [ ] Selecting a known register updates bank and address without writing data.
- [ ] Slave Simulator can save a scenario JSON preset.
- [ ] Slave Simulator can load a scenario JSON preset back into controls.
- [ ] Loading a scenario does not apply values to the datastore until `Generate Demo Meter Values`.
- [ ] Open Scenarios Folder opens `scenarios\slave`.
- [ ] Generate Demo Meter Values fills the local datastore with non-zero meter-like values.
- [ ] Random variation slightly changes demo values when enabled.
- [ ] Auto refresh demo values updates the local datastore without opening a port.
- [ ] `SDM230` or `generic_meter` works in `Single phase` mode.
- [ ] `SDM630`/`DTSU666` works in `Three phase balanced` mode.
- [ ] `SDM630`/`DTSU666` works in `Three phase meter / single-phase load` mode with load on the selected phase.

## Basic Master

- [ ] Basic Master profile selector shows known registers.
- [ ] Selecting a known register updates function, address, and quantity without auto-reading.

## End-To-End Local Simulation

- [ ] Advanced Master or Basic Master can read changing demo values from Slave Simulator when the simulator server is started locally.

## Diagnostic Report

- [ ] Diagnostic Report creates a new session.
- [ ] Diagnostic Report adds a manual note event.
- [ ] Diagnostic Report saves session JSON.
- [ ] Diagnostic Report loads session JSON.
- [ ] Diagnostic Report exports CSV.
- [ ] Diagnostic Report exports HTML.
- [ ] Diagnostic Report does not open ports or transmit.

## Release Artifacts

- [ ] ZIP tested from a fresh extraction folder with timestamp in the path.
- [ ] SHA256 file generated next to the portable ZIP.

## Safety Notes

- [ ] Do not use real equipment for write operations in this RC1 build unless you have explicit authorization.
