from modbus_diagnostic_studio.main import APP_NAME, main
from modbus_diagnostic_studio.version import BUILD_CHANNEL, version


def test_app_name():
    assert APP_NAME == "Modbus Diagnostic Studio"


def test_main_returns_zero():
    assert main() == 0


def test_version_metadata():
    assert version == "0.1.0-rc1"
    assert BUILD_CHANNEL == "rc1"
