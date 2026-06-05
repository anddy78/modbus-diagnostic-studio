"""Lightweight passive sniffer capture export helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from modbus_diagnostic_studio.core.decoder import bytes_to_hex
from modbus_diagnostic_studio.models.capture import CaptureFrameEvent, MatchedExchange

EVENT_FIELDNAMES = [
    "timestamp_monotonic",
    "raw_hex",
    "crc_ok",
    "classification",
    "direction_guess",
    "slave_id",
    "function_code",
    "address",
    "quantity",
    "byte_count",
    "exception_code",
    "registers",
    "error",
]

EXCHANGE_FIELDNAMES = [
    "status",
    "latency_ms",
    "note",
    "request_raw_hex",
    "response_raw_hex",
    "request_slave_id",
    "request_function_code",
    "request_address",
    "request_quantity",
    "response_classification",
    "response_exception_code",
]


def event_to_dict(event: CaptureFrameEvent) -> dict:
    """Convert one capture event to a JSON/CSV-safe dictionary."""
    return {
        "timestamp_monotonic": event.timestamp_monotonic,
        "raw_hex": event.raw_hex or bytes_to_hex(event.raw),
        "crc_ok": event.crc_ok,
        "classification": event.classification,
        "direction_guess": event.direction_guess.value,
        "slave_id": event.slave_id,
        "function_code": event.function_code,
        "address": event.address,
        "quantity": event.quantity,
        "byte_count": event.byte_count,
        "exception_code": event.exception_code,
        "registers": list(event.registers) if event.registers is not None else None,
        "error": event.error,
    }


def exchange_to_dict(exchange: MatchedExchange) -> dict:
    """Convert one matched exchange to a JSON/CSV-safe dictionary."""
    request = exchange.request
    response = exchange.response
    return {
        "status": exchange.status,
        "latency_ms": exchange.latency_ms,
        "note": exchange.note,
        "request_raw_hex": request.raw_hex or bytes_to_hex(request.raw),
        "response_raw_hex": None
        if response is None
        else (response.raw_hex or bytes_to_hex(response.raw)),
        "request_slave_id": request.slave_id,
        "request_function_code": request.function_code,
        "request_address": request.address,
        "request_quantity": request.quantity,
        "response_classification": None if response is None else response.classification,
        "response_exception_code": None if response is None else response.exception_code,
    }


def write_events_jsonl(path: str | Path, events: list[CaptureFrameEvent]) -> None:
    """Write capture events as JSONL."""
    output_path = _prepare_output_path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        for event in events:
            handle.write(json.dumps(event_to_dict(event), ensure_ascii=False))
            handle.write("\n")


def write_events_csv(path: str | Path, events: list[CaptureFrameEvent]) -> None:
    """Write capture events as CSV with header."""
    output_path = _prepare_output_path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVENT_FIELDNAMES)
        writer.writeheader()
        for event in events:
            writer.writerow(_csv_safe_dict(event_to_dict(event), EVENT_FIELDNAMES))


def write_exchanges_jsonl(path: str | Path, exchanges: list[MatchedExchange]) -> None:
    """Write matched exchanges as JSONL."""
    output_path = _prepare_output_path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        for exchange in exchanges:
            handle.write(json.dumps(exchange_to_dict(exchange), ensure_ascii=False))
            handle.write("\n")


def write_exchanges_csv(path: str | Path, exchanges: list[MatchedExchange]) -> None:
    """Write matched exchanges as CSV with header."""
    output_path = _prepare_output_path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXCHANGE_FIELDNAMES)
        writer.writeheader()
        for exchange in exchanges:
            writer.writerow(_csv_safe_dict(exchange_to_dict(exchange), EXCHANGE_FIELDNAMES))


def _prepare_output_path(path: str | Path) -> Path:
    output_path = Path(path)
    if output_path.exists() and output_path.is_dir():
        raise ValueError(f"Capture export path is a directory: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _csv_safe_dict(data: dict, fieldnames: list[str]) -> dict[str, str | int | float | bool | None]:
    result: dict[str, str | int | float | bool | None] = {}
    for fieldname in fieldnames:
        value = data.get(fieldname)
        if isinstance(value, list):
            result[fieldname] = json.dumps(value, ensure_ascii=False)
        else:
            result[fieldname] = value
    return result
