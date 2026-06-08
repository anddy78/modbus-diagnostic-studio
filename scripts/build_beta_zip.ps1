$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PortableBuildScript = Join-Path $RepoRoot "scripts\build_portable.ps1"
$PortableDir = Join-Path $RepoRoot "dist\ModbusDiagnosticStudioPortable"
$Version = & $PythonExe -c "from modbus_diagnostic_studio.version import version; print(version)"
$ZipPath = Join-Path $RepoRoot "dist\ModbusDiagnosticStudio_$Version`_portable.zip"
$HashPath = "$ZipPath.sha256"

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
if (Test-Path $HashPath) {
    Remove-Item $HashPath -Force
}

Write-Host "Creating release ZIP..."
Compress-Archive -Path $PortableDir -DestinationPath $ZipPath

$ZipFile = Get-Item $ZipPath
$Hash = (Get-FileHash -Path $ZipFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  $($ZipFile.Name)" | Set-Content -Path $HashPath -Encoding ascii

Write-Host "Release ZIP ready at $ZipPath"
Write-Host "SHA256 written to $HashPath"
