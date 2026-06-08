"""Offline capture readers for JSONL and CSV sniffer exports."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaptureReadResult:
    """Normalized offline capture file read result."""

    path: str
    capture_type: str
    records: list[dict]
    warnings: list[str]


def read_jsonl_records(path: str | Path) -> tuple[list[dict], list[str]]:
    input_path = _validate_input_path(path)
    records: list[dict] = []
    warnings: list[str] = []
    with input_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                warnings.append(f"Invalid JSON on line {line_number}: {exc.msg}")
                continue
            if not isinstance(parsed, dict):
                warnings.append(f"Unsupported record on line {line_number}: expected object")
                continue
            records.append(parsed)
    return records, warnings


def read_events_jsonl(path: str | Path) -> CaptureReadResult:
    records, warnings = read_jsonl_records(path)
    event_records = [record for record in records if record.get("record_type") != "metadata"]
    for index, record in enumerate(event_records, start=1):
        if not record.get("raw_hex"):
            warnings.append(f"Event record {index} missing raw_hex")
    return CaptureReadResult(str(Path(path)), "events_jsonl", event_records, warnings)


def read_exchanges_jsonl(path: str | Path) -> CaptureReadResult:
    records, warnings = read_jsonl_records(path)
    exchange_records = [record for record in records if record.get("record_type") != "metadata"]
    for index, record in enumerate(exchange_records, start=1):
        if not record.get("request_raw_hex") and not record.get("response_raw_hex"):
            warnings.append(f"Exchange record {index} missing request_raw_hex/response_raw_hex")
    return CaptureReadResult(str(Path(path)), "exchanges_jsonl", exchange_records, warnings)


def read_events_csv(path: str | Path) -> CaptureReadResult:
    rows = _read_csv_rows(path)
    warnings: list[str] = []
    for index, row in enumerate(rows, start=1):
        if not row.get("raw_hex"):
            warnings.append(f"Event record {index} missing raw_hex")
    return CaptureReadResult(str(Path(path)), "events_csv", rows, warnings)


def read_exchanges_csv(path: str | Path) -> CaptureReadResult:
    rows = _read_csv_rows(path)
    warnings: list[str] = []
    for index, row in enumerate(rows, start=1):
        if not row.get("request_raw_hex") and not row.get("response_raw_hex"):
            warnings.append(f"Exchange record {index} missing request_raw_hex/response_raw_hex")
    return CaptureReadResult(str(Path(path)), "exchanges_csv", rows, warnings)


def detect_capture_file(path: str | Path) -> str:
    input_path = _validate_input_path(path)
    suffix = input_path.suffix.lower()
    name = input_path.name.lower()
    if suffix == ".jsonl":
        if "exchange" in name:
            return "exchanges_jsonl"
        if "event" in name:
            return "events_jsonl"
        records, _warnings = read_jsonl_records(input_path)
        for record in records:
            record_type = record.get("record_type")
            if record_type == "exchange" or "request_raw_hex" in record:
                return "exchanges_jsonl"
            if record_type == "event" or "raw_hex" in record:
                return "events_jsonl"
        return "unknown"
    if suffix == ".csv":
        with input_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
        if "request_raw_hex" in fieldnames or "response_raw_hex" in fieldnames:
            return "exchanges_csv"
        if "raw_hex" in fieldnames:
            return "events_csv"
    return "unknown"


def read_capture_file(path: str | Path) -> CaptureReadResult:
    capture_type = detect_capture_file(path)
    if capture_type == "events_jsonl":
        return read_events_jsonl(path)
    if capture_type == "exchanges_jsonl":
        return read_exchanges_jsonl(path)
    if capture_type == "events_csv":
        return read_events_csv(path)
    if capture_type == "exchanges_csv":
        return read_exchanges_csv(path)
    return CaptureReadResult(str(Path(path)), "unknown", [], ["Unsupported capture file type"])


def _read_csv_rows(path: str | Path) -> list[dict]:
    input_path = _validate_input_path(path)
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _validate_input_path(path: str | Path) -> Path:
    input_path = Path(path)
    if input_path.exists() and input_path.is_dir():
        raise ValueError(f"Capture path is a directory: {input_path}")
    return input_path
