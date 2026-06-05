$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$SpecPath = Join-Path $RepoRoot "packaging\pyinstaller\modbus_diagnostic_studio.spec"
$OutputName = "ModbusDiagnosticStudioPortable"
$OutputDir = Join-Path $RepoRoot "dist\$OutputName"

if (-not (Test-Path $PythonExe)) {
    throw "Python virtual environment not found at $PythonExe"
}

if (-not (Test-Path $SpecPath)) {
    throw "PyInstaller spec not found at $SpecPath"
}

Write-Host "Building portable Windows package..."
& $PythonExe -m PyInstaller --noconfirm --clean $SpecPath

foreach ($Folder in @(
    "config",
    "logs",
    "captures",
    "exports",
    "profiles\user",
    "device_profiles\user"
)) {
    $Target = Join-Path $OutputDir $Folder
    if (-not (Test-Path $Target)) {
        New-Item -ItemType Directory -Path $Target -Force | Out-Null
    }
}

Write-Host "Portable build ready at $OutputDir"
