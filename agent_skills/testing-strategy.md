# Skill: Testing Strategy

Use this skill for tests and validation.

Priorities:
1. Core protocol correctness.
2. Profile decoding correctness.
3. Safety behavior.
4. Simulator math.
5. GUI smoke tests only after core is stable.

Required early tests:
- CRC16 known vectors
- FC03 request parse
- FC04 request parse
- FC03 response parse
- exception response parse
- incomplete RTU frame handling
- invalid CRC handling
- float32 endian decoding
- profile YAML load
- profile schema validation
- energy accumulator import/export behavior

Rules:
- Tests must be deterministic.
- Do not require hardware for unit tests.
- Hardware tests must be optional/manual.
- Prefer small fixtures with raw hex frames.
- Avoid fragile timing tests.
- Use explicit raw frame examples.

Validation commands must be PowerShell-compatible:
- python -m compileall src tests
- pytest -q
