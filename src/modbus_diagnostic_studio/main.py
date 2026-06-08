from __future__ import annotations

import argparse
import sys

from modbus_diagnostic_studio.gui.app import run_app
from modbus_diagnostic_studio.version import APP_NAME


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    return argparse.ArgumentParser(
        prog="modbus-diagnostic-studio",
        description=f"Launch {APP_NAME}.",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the desktop application."""
    if argv is None:
        return 0

    parser = build_parser()
    parser.parse_args(argv)
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
