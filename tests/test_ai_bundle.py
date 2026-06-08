"""Tests for offline AI bundle exports."""

from __future__ import annotations

import json

import pytest

from modbus_diagnostic_studio.services.ai_bundle import write_capture_ai_bundle
from modbus_diagnostic_studio.sniffer.capture_reader import CaptureReadResult


def test_write_capture_ai_bundle_exports_json(tmp_path) -> None:
    path = tmp_path / "exports" / "capture_bundle.json"
    result = CaptureReadResult(
        path="captures\\events.jsonl",
        capture_type="events_jsonl",
        records=[{"raw_hex": "01 03 00 00 00 02 C4 0B"}],
        warnings=[],
    )

    write_capture_ai_bundle(path, result, [{"classification": "read_request", "slave_id": 1}])

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["bundle_type"] == "modbus_capture_ai_bundle"
    assert payload["records"][0]["raw_hex"] == "01 03 00 00 00 02 C4 0B"
    assert payload["records"][0]["decoded"]["slave_id"] == 1


def test_write_capture_ai_bundle_rejects_directory(tmp_path) -> None:
    result = CaptureReadResult(path="capture.jsonl", capture_type="events_jsonl", records=[], warnings=[])

    with pytest.raises(ValueError, match="is a directory"):
        write_capture_ai_bundle(tmp_path, result, [])
