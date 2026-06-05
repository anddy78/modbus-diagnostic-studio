# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH).resolve().parents[1]
src_root = project_root / "src"
app_name = "ModbusDiagnosticStudioPortable"

datas = [
    (
        str(src_root / "modbus_diagnostic_studio" / "profiles" / "builtins"),
        "modbus_diagnostic_studio/profiles/builtins",
    ),
    (
        str(src_root / "modbus_diagnostic_studio" / "sniffer" / "builtins"),
        "modbus_diagnostic_studio/sniffer/builtins",
    ),
]


a = Analysis(
    [str(src_root / "modbus_diagnostic_studio" / "main.py")],
    pathex=[str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name,
)
