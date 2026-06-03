from modbus_diagnostic_studio.main import APP_NAME, main


def test_app_name():
    assert APP_NAME == "Modbus Diagnostic Studio"


def test_main_returns_zero():
    assert main() == 0
