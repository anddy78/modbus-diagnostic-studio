"""Tests for MasterOperationLogEntry and export helpers — no GUI, no hardware."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import pytest

from modbus_diagnostic_studio.master.operation_log import (
    MAX_LOG_ENTRIES,
    MasterOperationLogEntry,
    write_log_csv,
    write_log_jsonl,
)


def _entry(**kwargs) -> MasterOperationLogEntry:
    defaults = {
        "timestamp": "2024-01-01 12:00:00",
        "operation": "read",
        "com_port": "COM1",
        "slave_id": 1,
        "function_code": 3,
        "address": 0,
        "quantity": 10,
        "values": "10 register(s)",
        "status": "ok",
        "message": "Read OK",
    }
    defaults.update(kwargs)
    return MasterOperationLogEntry(**defaults)


class TestMasterOperationLogEntry:
    def test_to_dict_contains_all_fields(self) -> None:
        e = _entry()
        d = e.to_dict()
        assert d["timestamp"] == "2024-01-01 12:00:00"
        assert d["operation"] == "read"
        assert d["com_port"] == "COM1"
        assert d["slave_id"] == 1
        assert d["function_code"] == 3
        assert d["address"] == 0
        assert d["quantity"] == 10
        assert d["values"] == "10 register(s)"
        assert d["status"] == "ok"
        assert d["message"] == "Read OK"

    def test_to_dict_quantity_none(self) -> None:
        e = _entry(quantity=None)
        assert e.to_dict()["quantity"] is None

    def test_write_status_roundtrip(self) -> None:
        e = _entry(operation="write", status="error", message="CRC error")
        d = e.to_dict()
        assert d["operation"] == "write"
        assert d["status"] == "error"

    def test_cancelled_status(self) -> None:
        e = _entry(status="cancelled", message="User cancelled")
        assert e.to_dict()["status"] == "cancelled"


class TestWriteLogCsv:
    def test_writes_header_and_rows(self) -> None:
        entries = [_entry(address=0), _entry(address=100)]
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        write_log_csv(path, entries)
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["address"] == "0"
        assert rows[1]["address"] == "100"

    def test_empty_list_writes_header_only(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        write_log_csv(path, [])
        with open(path, encoding="utf-8", newline="") as f:
            content = f.read()
        assert "timestamp" in content
        # only header, no data rows
        lines = [ln for ln in content.splitlines() if ln.strip()]
        assert len(lines) == 1

    def test_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "log.csv"
            write_log_csv(path, [_entry()])
            assert path.exists()

    def test_rejects_directory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            with pytest.raises(ValueError, match="directory"):
                write_log_csv(path, [_entry()])

    def test_all_fieldnames_present(self) -> None:
        from modbus_diagnostic_studio.master.operation_log import LOG_FIELDNAMES
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        write_log_csv(path, [_entry()])
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        for field in LOG_FIELDNAMES:
            assert field in row


class TestWriteLogJsonl:
    def test_one_line_per_entry(self) -> None:
        entries = [_entry(address=i) for i in range(5)]
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        write_log_jsonl(path, entries)
        with open(path, encoding="utf-8") as f:
            lines = [ln for ln in f.readlines() if ln.strip()]
        assert len(lines) == 5

    def test_each_line_is_valid_json(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        write_log_jsonl(path, [_entry(address=42)])
        with open(path, encoding="utf-8") as f:
            obj = json.loads(f.readline())
        assert obj["address"] == 42

    def test_empty_list_produces_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        write_log_jsonl(path, [])
        assert Path(path).stat().st_size == 0

    def test_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "log.jsonl"
            write_log_jsonl(path, [_entry()])
            assert path.exists()

    def test_rejects_directory_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            with pytest.raises(ValueError, match="directory"):
                write_log_jsonl(path, [_entry()])


def test_max_log_entries_constant() -> None:
    assert MAX_LOG_ENTRIES == 1000
