# Windows Packaging

## Goal

Produce a self-contained Windows portable build for `modbus-diagnostic-studio`.

The first packaging target is a PyInstaller one-folder build that launches the GUI without requiring the user to run Python manually.

## Portable Build Inputs

- Entry point: `src\modbus_diagnostic_studio\main.py`
- PyInstaller spec: `packaging\pyinstaller\modbus_diagnostic_studio.spec`
- Build script: `scripts\build_portable.ps1`

## Included Application Data

The portable build bundles built-in YAML data required at runtime:

- `src\modbus_diagnostic_studio\profiles\builtins\`
- `src\modbus_diagnostic_studio\sniffer\builtins\`

## Expected Portable Output

The build script targets:

- `dist\ModbusDiagnosticStudioPortable\`

After packaging, the script ensures these writable runtime folders exist inside the portable output:

- `config\`
- `logs\`
- `captures\`
- `exports\`

## Build Command

Run from PowerShell:

```powershell
.\scripts\build_portable.ps1
```

## Beta ZIP

To create the versioned beta ZIP after the portable build succeeds, run:

```powershell
.\scripts\build_beta_zip.ps1
```

Expected archive:

- `dist\ModbusDiagnosticStudio_0.1.0-beta_portable.zip`

The archive contains the full `dist\ModbusDiagnosticStudioPortable\` folder.

## Validation

Recommended validation before packaging:

```powershell
.\.venv\Scripts\python.exe -m compileall src tests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m modbus_diagnostic_studio.main --help
```

## Notes

- Portable build is one-folder, not one-file.
- Sniffer mode remains passive only and must never transmit.
- Installer packaging can be added later once the portable layout is stable.
