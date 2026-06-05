"""Master operation log — records every read/write attempt with its outcome."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

MAX_LOG_ENTRIES = 1000

LOG_FIELDNAMES = [
    "timestamp",
    "operation",
    "com_port",
    "slave_id",
    "function_code",
    "address",
    "quantity",
    "values",
    "status",
    "message",
]


@dataclass
class MasterOperationLogEntry:
    """One recorded Modbus master operation."""

    timestamp: str
    operation: str    # "read" | "write"
    com_port: str
    slave_id: int
    function_code: int
    address: int
    quantity: int | None
    values: str       # brief human-readable representation of result/request data
    status: str       # "ok" | "error" | "cancelled"
    message: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "operation": self.operation,
            "com_port": self.com_port,
            "slave_id": self.slave_id,
            "function_code": self.function_code,
            "address": self.address,
            "quantity": self.quantity,
            "values": self.values,
            "status": self.status,
            "message": self.message,
        }


def write_log_csv(path: str | Path, entries: list[MasterOperationLogEntry]) -> None:
    """Write operation log entries to a CSV file."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDNAMES)
        writer.writeheader()
        for entry in entries:
            writer.writerow(entry.to_dict())


def write_log_jsonl(path: str | Path, entries: list[MasterOperationLogEntry]) -> None:
    """Write operation log entries to a JSONL file."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        for entry in entries:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=False))
            handle.write("\n")
