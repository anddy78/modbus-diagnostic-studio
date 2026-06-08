from modbus_diagnostic_studio.version import APP_NAME, BUILD_CHANNEL, version


def test_version_module_exports_release_metadata() -> None:
    assert APP_NAME == "Modbus Diagnostic Studio"
    assert version == "0.1.0-rc1"
    assert BUILD_CHANNEL == "rc1"
