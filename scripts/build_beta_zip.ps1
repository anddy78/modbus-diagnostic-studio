$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PortableBuildScript = Join-Path $RepoRoot "scripts\build_portable.ps1"
$PortableDir = Join-Path $RepoRoot "dist\ModbusDiagnosticStudioPortable"
$ZipPath = Join-Path $RepoRoot "dist\ModbusDiagnosticStudio_0.1.0-beta_portable.zip"

if (-not (Test-Path $PythonExe)) {
    throw "Python virtual environment not found at $PythonExe"
}

Write-Host "Running test suite..."
& $PythonExe -m pytest -q

Write-Host "Building portable application..."
& $PortableBuildScript

if (-not (Test-Path $PortableDir)) {
    throw "Portable build directory not found at $PortableDir"
}

$ExePath = Join-Path $PortableDir "ModbusDiagnosticStudioPortable.exe"
if (-not (Test-Path $ExePath)) {
    throw "Portable executable not found at $ExePath"
}

if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}

Write-Host "Creating beta ZIP..."
Compress-Archive -Path $PortableDir -DestinationPath $ZipPath

Write-Host "Beta ZIP ready at $ZipPath"
