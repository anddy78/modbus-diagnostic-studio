# Architecture

Status: draft.

Primary decision:
Build a self-contained Windows desktop app using Python + PySide6.

Core principles:
- GUI-independent Modbus core.
- Passive sniffer must never transmit.
- Profiles drive decoding and simulation.
- Built-in profiles are bundled with the app.
- Windows packaging is a first-class requirement.
