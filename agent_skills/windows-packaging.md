# Skill: Windows Packaging

Use this skill for Windows distribution.

Goal:
The application must be self-contained and easy to launch.

Preferred:
- PyInstaller portable build first
- installer later if needed

Rules:
- No Linux paths.
- No manual script execution for end users.
- Use app-local or user-local folders for config, logs and captures.
- Built-in profiles must be bundled.
- App must run from a shortcut or executable.
- If a local web GUI is ever used, main.exe must start backend and open browser automatically.
- Do not require users to activate venv manually.

Expected folders:
- config/
- profiles/
- logs/
- captures/
- exports/

Validation:
- app launches without console dependency
- profiles load from packaged build
- logs are writable
- captures are writable
- USB serial errors do not crash the app
- app can be closed cleanly

PowerShell only:
- All commands must be PowerShell-compatible.
- Do not use Bash commands.
