# Manual Test Checklist

Use this checklist to validate the beta GUI on Windows.

## App Startup

- [ ] App opens from the virtual environment.
- [ ] App opens from the portable EXE.

## Core GUI

- [ ] Connection tab lists COM ports.
- [ ] Decoder tab decodes raw hex.
- [ ] Profiles tab loads built-in profiles.
- [ ] Profile Manager tab loads built-in device profiles.
- [ ] Profile Manager lists built-in register profiles.
- [ ] Profile Manager validates a selected device profile.
- [ ] Profile Manager opens `device_profiles\user`.
- [ ] Meters tab opens.
- [ ] Theme selector works.

## Advanced Master

- [ ] Advanced Master reads FC03 and FC04.
- [ ] Advanced Master reads FC01 and FC02 against Slave Simulator.
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

## Safety Notes

- [ ] Do not use real equipment for write operations in this beta unless you have explicit authorization.
