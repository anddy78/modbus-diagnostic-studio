"""Tests for continuous passive capture recorder."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from modbus_diagnostic_studio.core.crc import append_crc
from modbus_diagnostic_studio.sniffer.capture_recorder import (
    ContinuousCaptureRecorder,
    ContinuousCaptureRecorderConfig,
)
from modbus_diagnostic_studio.sniffer.stream_parser import frame_event_from_bytes


def sample_event(timestamp: float = 1.0):
    return frame_event_from_bytes(append_crc(bytes.fromhex("01 03 00 00 00 02")), timestamp)


def sample_exchange():
    request = sample_event(1.0)
    response = frame_event_from_bytes(
        append_crc(bytes.fromhex("01 03 04 00 2A 00 64")),
        1.2,
    )
    return SimpleNamespace(
        request=request,
        response=response,
        latency_ms=200.0,
        status="ok",
        note="",
    )


def test_start_creates_capture_files_and_manifest(tmp_path) -> None:
    recorder = ContinuousCaptureRecorder(
        ContinuousCaptureRecorderConfig(output_dir=tmp_path / "captures", base_name="modbus_capture")
    )

    recorder.start({"port": "COM7", "baudrate": 9600, "parity": "N", "stopbits": 1.0, "bytesize": 8})

    assert recorder.events_path is not None and recorder.events_path.exists()
    assert recorder.exchanges_path is not None and recorder.exchanges_path.exists()
    assert recorder.manifest_path is not None and recorder.manifest_path.exists()


def test_write_snapshot_delta_writes_events_and_avoids_duplicates(tmp_path) -> None:
    recorder = ContinuousCaptureRecorder(
        ContinuousCaptureRecorderConfig(output_dir=tmp_path / "captures", base_name="capture")
    )
    recorder.start({"port": "COM7", "baudrate": 9600, "parity": "N", "stopbits": 1.0, "bytesize": 8})
    snapshot = SimpleNamespace(events=[sample_event()], exchanges=[sample_exchange()])

    recorder.write_snapshot_delta(snapshot)
    recorder.write_snapshot_delta(snapshot)
    recorder.close()

    event_lines = recorder.events_path.read_text(encoding="utf-8").splitlines()
    exchange_lines = recorder.exchanges_path.read_text(encoding="utf-8").splitlines()
    assert len(event_lines) == 2
    assert len(exchange_lines) == 2
    assert json.loads(event_lines[1])["record_type"] == "event"
    assert json.loads(exchange_lines[1])["record_type"] == "exchange"


def test_stop_closes_handles(tmp_path) -> None:
    recorder = ContinuousCaptureRecorder(
        ContinuousCaptureRecorderConfig(output_dir=tmp_path / "captures", base_name="capture")
    )
    recorder.start({"port": "COM7", "baudrate": 9600, "parity": "N", "stopbits": 1.0, "bytesize": 8})

    recorder.stop()

    assert recorder.is_open is False


def test_output_dir_file_is_rejected(tmp_path) -> None:
    bad_output = tmp_path / "capture.txt"
    bad_output.write_text("x", encoding="utf-8")
    recorder = ContinuousCaptureRecorder(
        ContinuousCaptureRecorderConfig(output_dir=bad_output, base_name="capture")
    )

    with pytest.raises(ValueError, match="output_dir is a file"):
        recorder.start()


def test_metadata_line_is_written(tmp_path) -> None:
    recorder = ContinuousCaptureRecorder(
        ContinuousCaptureRecorderConfig(output_dir=tmp_path / "captures", base_name="capture")
    )
    recorder.start(
        {
            "port": "COM7",
            "baudrate": 9600,
            "parity": "N",
            "stopbits": 1.0,
            "bytesize": 8,
            "profile_id": "smartlogger_chint_dtsu71",
        }
    )
    recorder.close()

    first_line = recorder.events_path.read_text(encoding="utf-8").splitlines()[0]
    assert json.loads(first_line)["record_type"] == "metadata"


def test_rotation_creates_part002(tmp_path) -> None:
    recorder = ContinuousCaptureRecorder(
        ContinuousCaptureRecorderConfig(
            output_dir=tmp_path / "captures",
            base_name="capture",
            rotate_max_bytes=1,
        )
    )
    recorder.start({"port": "COM7", "baudrate": 9600, "parity": "N", "stopbits": 1.0, "bytesize": 8})

    recorder.write_events([sample_event(), sample_event(2.0)])
    recorder.close()

    assert (tmp_path / "captures" / "capture_events_part002.jsonl").exists()
