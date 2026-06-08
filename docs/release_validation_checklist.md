# Release Validation Checklist

Use this checklist to validate `0.1.0-rc1` before publishing the portable release.

## Environment

- [ ] Windows 10
- [ ] Windows 11
- [ ] Fresh folder extraction
- [ ] Antivirus / SmartScreen notes

## Portable Package

- [ ] ZIP extracts cleanly
- [ ] EXE starts
- [ ] App closes without hanging

## Main Tabs

- [ ] Serial Ports
- [ ] Meter Dashboard
- [ ] Advanced Master
- [ ] Slave Simulator
- [ ] Sniffer Diagnostic
- [ ] Capture Viewer
- [ ] Raw Frame Decoder
- [ ] Basic Master
- [ ] Profile Manager
- [ ] Diagnostic Report

## Serial Safety

- [ ] Serial Ports refresh does not open ports
- [ ] Capture Viewer does not open ports
- [ ] Raw Frame Decoder is offline

## Active Master

- [ ] Read FC03/FC04 with simulator
- [ ] Write guards require all confirmations

## Slave Simulator

- [ ] Start / stop with virtual COM
- [ ] Generate demo meter values
- [ ] Save / load scenario

## Passive Sniffer

- [ ] Start / stop
- [ ] Record to file
- [ ] Pause Display does not stop recorder
- [ ] Files generated

## Capture Viewer

- [ ] Open JSONL
- [ ] Decode selected frame
- [ ] Export AI bundle
- [ ] Add to Diagnostic Report

## Diagnostic Report

- [ ] New session
- [ ] Manual note
- [ ] Export JSON / CSV / HTML

## Release Artifacts

- [ ] ZIP filename
- [ ] SHA256 generated
- [ ] Version visible in About
