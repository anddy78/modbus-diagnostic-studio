# Manual Test Checklist

Use this checklist to validate the beta GUI on Windows.

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
- [ ] Passive Sniffer exports captures to CSV and JSONL.

## Slave Simulator

- [ ] Slave Simulator starts and stops.
- [ ] Slave Simulator profile selector shows known registers.
- [ ] Selecting a known register updates bank and address without writing data.
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

## Safety Notes

- [ ] Do not use real equipment for write operations in this beta unless you have explicit authorization.
