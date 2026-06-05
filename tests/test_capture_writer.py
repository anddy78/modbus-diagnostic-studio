"""Tests for passive sniffer capture export helpers."""

from __future__ import annotations

import csv
import json

import pytest

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.models.capture import MatchedExchange
from modbus_diagnostic_studio.sniffer.capture_writer import (
    event_to_dict,
    exchange_to_dict,
    write_events_csv,
    write_events_jsonl,
    write_exchanges_csv,
    write_exchanges_jsonl,
)
from modbus_diagnostic_studio.sniffer.stream_parser import frame_event_from_bytes


def request_event() -> object:
    return frame_event_from_bytes(append_crc(bytes.fromhex("01 03 00 00 00 02")), 1.0)


def response_event() -> object:
    return frame_event_from_bytes(
        append_crc(bytes.fromhex("01 03 04 00 2A 00 64")),
        1.2,
    )


def sample_exchange() -> MatchedExchange:
    return MatchedExchange(
        request=request_event(),
        response=response_event(),
        latency_ms=200.0,
        status="ok",
        note="",
    )


def test_event_to_dict_converts_enum_and_bytes() -> None:
    data = event_to_dict(request_event())

    assert data["direction_guess"] == "request"
    assert data["raw_hex"] == "01 03 00 00 00 02 C4 0B"
    assert data["registers"] is None


def test_write_events_jsonl_creates_valid_file(tmp_path) -> None:
    path = tmp_path / "captures" / "events.jsonl"

    write_events_jsonl(path, [request_event(), response_event()])

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["classification"] == "read_request"
    assert first["direction_guess"] == "request"


def test_write_events_csv_creates_header_and_rows(tmp_path) -> None:
    path = tmp_path / "captures" / "events.csv"

    write_events_csv(path, [request_event(), response_event()])

    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[0]["raw_hex"] == "01 03 00 00 00 02 C4 0B"
    assert rows[1]["registers"] == "[42, 100]"


def test_write_exchanges_jsonl_creates_valid_file(tmp_path) -> None:
    path = tmp_path / "captures" / "exchanges.jsonl"

    write_exchanges_jsonl(path, [sample_exchange()])

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["status"] == "ok"
    assert data["request_raw_hex"] == "01 03 00 00 00 02 C4 0B"
    assert data["response_classification"] == "read_response"


def test_write_exchanges_csv_creates_header_and_rows(tmp_path) -> None:
    path = tmp_path / "captures" / "exchanges.csv"

    write_exchanges_csv(path, [sample_exchange()])

    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["request_function_code"] == "3"


def test_parent_directory_is_created(tmp_path) -> None:
    path = tmp_path / "nested" / "captures" / "events.jsonl"

    write_events_jsonl(path, [request_event()])

    assert path.exists()


def test_directory_path_raises_value_error(tmp_path) -> None:
    with pytest.raises(ValueError, match="is a directory"):
        write_events_csv(tmp_path, [request_event()])


def test_exchange_to_dict_handles_response_fields() -> None:
    data = exchange_to_dict(sample_exchange())

    assert data["latency_ms"] == 200.0
    assert data["response_exception_code"] is None
    assert data["request_address"] == 0
