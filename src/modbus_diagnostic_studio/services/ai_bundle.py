"""Offline AI-ready bundle exports for capture viewer data."""

from __future__ import annotations

import json
from pathlib import Path

from modbus_diagnostic_studio.sniffer.capture_reader import CaptureReadResult


def write_capture_ai_bundle(
    path: str | Path,
    capture_result: CaptureReadResult,
    decoded_records: list[dict],
    metadata: dict | None = None,
) -> None:
    """Write one offline capture bundle as JSON."""
    output_path = Path(path)
    if output_path.exists() and output_path.is_dir():
        raise ValueError(f"AI bundle path is a directory: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "bundle_type": "modbus_capture_ai_bundle",
        "version": "1",
        "metadata": {
            "source_file": capture_result.path,
            "capture_type": capture_result.capture_type,
            "record_count": len(capture_result.records),
            **(metadata or {}),
        },
        "records": [],
        "analysis_guidance": {
            "safety": "This is offline capture data. Do not infer writes unless function codes indicate writes.",
            "tasks": [
                "Identify slave IDs and function codes",
                "Group request/response exchanges",
                "Detect CRC errors, exception responses, timeouts and repeated polling",
                "Suggest likely register map/profile if possible",
            ],
        },
    }
    for index, record in enumerate(capture_result.records):
        raw_hex = (
            record.get("raw_hex")
            or record.get("request_raw_hex")
            or record.get("response_raw_hex")
            or ""
        )
        payload["records"].append(
            {
                "index": index,
                "raw_hex": raw_hex,
                "decoded": decoded_records[index] if index < len(decoded_records) else {},
                "source_record": record,
            }
        )
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
