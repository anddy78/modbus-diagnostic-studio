"""Tests for offline capture readers."""

from __future__ import annotations

import json

import pytest

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.models.capture import MatchedExchange
from modbus_diagnostic_studio.sniffer.capture_reader import (
    detect_capture_file,
    read_capture_file,
    read_events_csv,
    read_events_jsonl,
    read_exchanges_csv,
    read_exchanges_jsonl,
)
from modbus_diagnostic_studio.sniffer.capture_writer import write_events_csv, write_exchanges_csv
from modbus_diagnostic_studio.sniffer.stream_parser import frame_event_from_bytes


def request_event():
    return frame_event_from_bytes(append_crc(bytes.fromhex("01 03 00 00 00 02")), 1.0)


def response_event():
    return frame_event_from_bytes(append_crc(bytes.fromhex("01 03 04 00 2A 00 64")), 1.2)


def sample_exchange() -> MatchedExchange:
    return MatchedExchange(
        request=request_event(),
        response=response_event(),
        latency_ms=200.0,
        status="ok",
        note="",
    )


def test_read_events_jsonl(tmp_path) -> None:
    path = tmp_path / "capture_events.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"record_type": "metadata", "capture_id": "abc"}),
                json.dumps({"record_type": "event", "raw_hex": "01 03 00 00 00 02 C4 0B"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = read_events_jsonl(path)

    assert result.capture_type == "events_jsonl"
    assert len(result.records) == 1


def test_read_exchanges_jsonl(tmp_path) -> None:
    path = tmp_path / "capture_exchanges.jsonl"
    path.write_text(
        json.dumps(
            {
                "record_type": "exchange",
                "request_raw_hex": "01 03 00 00 00 02 C4 0B",
                "response_raw_hex": "01 03 04 00 2A 00 64 DA 3E",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = read_exchanges_jsonl(path)

    assert result.capture_type == "exchanges_jsonl"
    assert len(result.records) == 1


def test_read_events_csv_from_capture_writer(tmp_path) -> None:
    path = tmp_path / "events.csv"
    write_events_csv(path, [request_event()])

    result = read_events_csv(path)

    assert result.capture_type == "events_csv"
    assert result.records[0]["raw_hex"] == "01 03 00 00 00 02 C4 0B"


def test_read_exchanges_csv_from_capture_writer(tmp_path) -> None:
    path = tmp_path / "exchanges.csv"
    write_exchanges_csv(path, [sample_exchange()])

    result = read_exchanges_csv(path)

    assert result.capture_type == "exchanges_csv"
    assert result.records[0]["status"] == "ok"


def test_detect_capture_file_types(tmp_path) -> None:
    event_path = tmp_path / "sniffer_events.jsonl"
    event_path.write_text(json.dumps({"record_type": "event", "raw_hex": "AA"}) + "\n", encoding="utf-8")
    exchange_path = tmp_path / "sniffer_exchanges.csv"
    exchange_path.write_text("request_raw_hex,response_raw_hex\nAA,BB\n", encoding="utf-8")

    assert detect_capture_file(event_path) == "events_jsonl"
    assert detect_capture_file(exchange_path) == "exchanges_csv"


def test_directory_path_fails(tmp_path) -> None:
    with pytest.raises(ValueError, match="is a directory"):
        read_capture_file(tmp_path)


def test_invalid_jsonl_line_adds_warning(tmp_path) -> None:
    path = tmp_path / "bad_events.jsonl"
    path.write_text("{bad json}\n" + json.dumps({"record_type": "event", "raw_hex": "AA"}) + "\n", encoding="utf-8")

    result = read_capture_file(path)

    assert len(result.records) == 1
    assert result.warnings
