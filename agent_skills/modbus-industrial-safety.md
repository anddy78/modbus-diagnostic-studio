# Skill: Modbus Industrial Safety

Use this skill for Modbus RTU/TCP, RS485, sniffing, master/slave and simulators.

Hard rules:
- Sniffer mode must never transmit.
- Passive capture must not call serial.write().
- Sniffer code must not expose write/send APIs.
- Master and Slave modes are active modes and must be visually distinct.
- Never assume a profile is correct without evidence.
- Decode CRC and exceptions explicitly.
- Handle incomplete frames and timeouts.
- Do not hide stale data as valid data.
- Avoid unbounded memory growth.

Required concepts:
- RTU CRC16 validation
- inter-frame timing awareness
- request/response matching
- FC03 and FC04 first
- Modbus exception frames
- slave id
- function code
- address
- quantity
- byte count
- serial disconnection handling
- bounded buffers
- log rotation

For RS485:
- Sniffing in software does not guarantee electrical passivity by itself.
- The UI must clearly state that sniffer mode is software-passive.
- Any hardware notes must be documented separately.
