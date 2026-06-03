# Skill: Python Desktop App

Use this skill for PySide6/Qt GUI work.

Rules:
- GUI must not contain protocol parsing logic.
- Long-running serial/TCP work must not block the UI thread.
- Use signals/events or service boundaries for background workers.
- Keep tabs simple and technical.
- Favor clear state indicators over visual complexity.
- Do not require terminal usage for end users.
- Use Windows-safe paths.

Target GUI tabs:
- Connection
- Master Read
- Slave Simulator
- Sniffer
- Live Dashboard
- Profiles
- Decoder
- Logs

Required indicators:
- connected/disconnected
- passive/active mode
- requests OK
- CRC errors
- timeouts
- last request
- last response
- latency
- capture status
- selected serial port
- selected slave ID
- current profile

Threading:
- Serial polling, sniffing and TCP services must run outside the GUI thread.
- GUI updates must be done through safe signals/events.
- Background workers must stop cleanly.
