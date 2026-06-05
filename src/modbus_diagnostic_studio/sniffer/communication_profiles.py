"""Communication profile loading for passive sniffer diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from modbus_diagnostic_studio.models.communication_profile import (
    CommunicationProfile,
    DiagnosticThresholds,
    ExpectedRequestBlock,
)

BUILTINS_DIR = Path(__file__).resolve().parent / "builtins"


def _require_mapping(data: Any, context: str) -> dict:
    if not isinstance(data, dict):
        raise ValueError(f"{context} must be a mapping")
    return data


def _require_field(data: dict, field_name: str) -> Any:
    if field_name not in data:
        raise ValueError(f"Communication profile is missing required field: {field_name}")
    return data[field_name]


def _load_expected_request_block(data: Any, index: int) -> ExpectedRequestBlock:
    block = _require_mapping(data, f"Expected request block #{index}")
    if "address" not in block or "quantity" not in block:
        raise ValueError(
            f"Expected request block #{index} must include address and quantity"
        )
    return ExpectedRequestBlock(
        address=block["address"],
        quantity=block["quantity"],
        function_code=block.get("function_code", 3),
        interval_min_ms=block.get("interval_min_ms"),
        interval_max_ms=block.get("interval_max_ms"),
        description=block.get("description", ""),
    )


def _load_thresholds(data: Any) -> DiagnosticThresholds:
    if data is None:
        return DiagnosticThresholds()
    mapping = _require_mapping(data, "thresholds")
    return DiagnosticThresholds(
        max_crc_error_rate_percent=mapping.get("max_crc_error_rate_percent", 1.0),
        max_timeout_rate_percent=mapping.get("max_timeout_rate_percent", 5.0),
        max_response_latency_ms=mapping.get("max_response_latency_ms", 500.0),
    )


def load_communication_profile(path: str | Path) -> CommunicationProfile:
    """Load one communication profile from YAML."""
    profile_path = Path(path)
    with profile_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return load_communication_profile_from_dict(data)


def load_communication_profile_from_dict(data: dict) -> CommunicationProfile:
    """Build one communication profile from a dictionary."""
    profile_data = _require_mapping(data, "Communication profile")
    expected_requests_data = profile_data.get("expected_requests", [])
    if not isinstance(expected_requests_data, list):
        raise ValueError("Communication profile field 'expected_requests' must be a list")

    expected_slave_ids = profile_data.get("expected_slave_ids", [])
    if not isinstance(expected_slave_ids, list):
        raise ValueError("Communication profile field 'expected_slave_ids' must be a list")

    expected_functions = profile_data.get("expected_functions", [])
    if not isinstance(expected_functions, list):
        raise ValueError("Communication profile field 'expected_functions' must be a list")

    return CommunicationProfile(
        profile_id=_require_field(profile_data, "profile_id"),
        name=_require_field(profile_data, "name"),
        description=profile_data.get("description", ""),
        master_role=profile_data.get("master_role", "generic_master"),
        slave_role=profile_data.get("slave_role", "generic_slave"),
        expected_baudrate=profile_data.get("expected_baudrate"),
        expected_parity=profile_data.get("expected_parity"),
        expected_stopbits=profile_data.get("expected_stopbits"),
        expected_slave_ids=list(expected_slave_ids),
        expected_functions=list(expected_functions),
        expected_requests=[
            _load_expected_request_block(block_data, index)
            for index, block_data in enumerate(expected_requests_data)
        ],
        linked_register_profile=profile_data.get("linked_register_profile"),
        thresholds=_load_thresholds(profile_data.get("thresholds")),
    )


def list_builtin_communication_profiles() -> list[str]:
    """Return available built-in communication profile ids."""
    return sorted(path.stem for path in BUILTINS_DIR.glob("*.yaml"))


def load_builtin_communication_profile(profile_id: str) -> CommunicationProfile:
    """Load one built-in communication profile by id."""
    path = BUILTINS_DIR / f"{profile_id}.yaml"
    if not path.exists():
        raise ValueError(f"Built-in communication profile not found: {profile_id}")
    return load_communication_profile(path)


def load_all_builtin_communication_profiles() -> list[CommunicationProfile]:
    """Load all built-in communication profiles."""
    return [
        load_builtin_communication_profile(profile_id)
        for profile_id in list_builtin_communication_profiles()
    ]
