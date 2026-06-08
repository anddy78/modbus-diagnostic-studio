"""Continuous passive capture recorder.

Safety rule:
This module writes offline files only. It never opens ports and never transmits.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from modbus_diagnostic_studio.models.capture import CaptureFileMetadata
from modbus_diagnostic_studio.sniffer.capture_writer import event_to_dict, exchange_to_dict


@dataclass(frozen=True)
class ContinuousCaptureRecorderConfig:
    """Settings for a rolling offline capture writer."""

    output_dir: Path
    base_name: str
    write_events: bool = True
    write_exchanges: bool = True
    flush_every_records: int = 10
    rotate_max_bytes: int = 10_000_000
    include_metadata: bool = True
    serial_metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.flush_every_records <= 0:
            raise ValueError("flush_every_records must be > 0")
        if self.rotate_max_bytes <= 0:
            raise ValueError("rotate_max_bytes must be > 0")


class ContinuousCaptureRecorder:
    """Append passive sniffer snapshot deltas to JSONL files."""

    def __init__(self, config: ContinuousCaptureRecorderConfig) -> None:
        self.config = config
        self._output_dir = Path(config.output_dir)
        self._base_name = _slugify_base_name(config.base_name)
        self._events_handle = None
        self._exchanges_handle = None
        self._current_events_path: Path | None = None
        self._current_exchanges_path: Path | None = None
        self._manifest_path: Path | None = None
        self._last_event_count_written = 0
        self._last_exchange_count_written = 0
        self._last_event_signatures: list[str] = []
        self._last_exchange_signatures: list[str] = []
        self._events_part = 1
        self._exchanges_part = 1
        self._metadata_line = ""
        self.records_written = 0
        self.event_records_written = 0
        self.exchange_records_written = 0
        self.rotations = 0
        self.bytes_written = 0

    @property
    def is_open(self) -> bool:
        return self._events_handle is not None or self._exchanges_handle is not None

    @property
    def manifest_path(self) -> Path | None:
        return self._manifest_path

    @property
    def events_path(self) -> Path | None:
        return self._current_events_path

    @property
    def exchanges_path(self) -> Path | None:
        return self._current_exchanges_path

    def start(self, metadata: dict[str, object] | None = None) -> None:
        """Create output files and optionally write metadata headers."""
        if self.is_open:
            return
        if self._output_dir.exists() and self._output_dir.is_file():
            raise ValueError(f"Capture output_dir is a file: {self._output_dir}")
        self._output_dir.mkdir(parents=True, exist_ok=True)

        merged_metadata = dict(self.config.serial_metadata)
        if metadata:
            merged_metadata.update(metadata)
        capture_metadata = CaptureFileMetadata(
            capture_id=str(merged_metadata.get("capture_id") or uuid4().hex),
            started_at=_now_iso(),
            app_version=str(merged_metadata.get("app_version", "")),
            port=str(merged_metadata.get("port", "")),
            baudrate=int(merged_metadata.get("baudrate", 0) or 0),
            parity=str(merged_metadata.get("parity", "")),
            stopbits=float(merged_metadata.get("stopbits", 0.0) or 0.0),
            bytesize=int(merged_metadata.get("bytesize", 0) or 0),
            profile_id=str(merged_metadata.get("profile_id", "")),
            notes=str(merged_metadata.get("notes", "")),
        )
        self._metadata_line = json.dumps(
            {"record_type": "metadata", **asdict(capture_metadata)},
            ensure_ascii=False,
        )
        self._manifest_path = self._output_dir / f"{self._base_name}_manifest.json"
        self._write_manifest(capture_metadata)

        if self.config.write_events:
            self._open_events_file(part=1)
            self._write_metadata_if_needed(self._events_handle)
        if self.config.write_exchanges:
            self._open_exchanges_file(part=1)
            self._write_metadata_if_needed(self._exchanges_handle)

    def write_snapshot_delta(self, snapshot: object) -> None:
        """Write only the newly appended events/exchanges from one accumulated snapshot."""
        events = list(getattr(snapshot, "events", []))
        exchanges = list(getattr(snapshot, "exchanges", []))
        if self.config.write_events:
            event_signatures = [
                json.dumps(event_to_dict(event), ensure_ascii=False, sort_keys=True)
                for event in events
            ]
            new_event_index = _overlap_index(self._last_event_signatures, event_signatures)
            self.write_events(events[new_event_index:])
            self._last_event_count_written = len(events)
            self._last_event_signatures = event_signatures
        if self.config.write_exchanges:
            exchange_signatures = [
                json.dumps(exchange_to_dict(exchange), ensure_ascii=False, sort_keys=True)
                for exchange in exchanges
            ]
            new_exchange_index = _overlap_index(
                self._last_exchange_signatures,
                exchange_signatures,
            )
            self.write_exchanges(exchanges[new_exchange_index:])
            self._last_exchange_count_written = len(exchanges)
            self._last_exchange_signatures = exchange_signatures

    def write_events(self, events: list[object]) -> None:
        """Append event records to the current JSONL file."""
        if not self.config.write_events or self._events_handle is None:
            return
        for event in events:
            self._rotate_events_if_needed()
            line = json.dumps(
                {
                    "record_type": "event",
                    "timestamp_iso": _now_iso(),
                    **event_to_dict(event),
                },
                ensure_ascii=False,
            )
            self._write_line(self._events_handle, line)
            self.records_written += 1
            self.event_records_written += 1

    def write_exchanges(self, exchanges: list[object]) -> None:
        """Append exchange records to the current JSONL file."""
        if not self.config.write_exchanges or self._exchanges_handle is None:
            return
        for exchange in exchanges:
            self._rotate_exchanges_if_needed()
            line = json.dumps(
                {
                    "record_type": "exchange",
                    "timestamp_iso": _now_iso(),
                    **exchange_to_dict(exchange),
                },
                ensure_ascii=False,
            )
            self._write_line(self._exchanges_handle, line)
            self.records_written += 1
            self.exchange_records_written += 1

    def stop(self) -> None:
        """Close open files and stamp stopped_at in the manifest."""
        self.close()

    def close(self) -> None:
        stopped_at = _now_iso()
        self._close_handle("_events_handle")
        self._close_handle("_exchanges_handle")
        if self._manifest_path is not None and self._manifest_path.exists():
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            payload["stopped_at"] = stopped_at
            payload["stats"] = {
                "records_written": self.records_written,
                "event_records_written": self.event_records_written,
                "exchange_records_written": self.exchange_records_written,
                "rotations": self.rotations,
                "bytes_written": self.bytes_written,
            }
            self._manifest_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def _write_manifest(self, metadata: CaptureFileMetadata) -> None:
        assert self._manifest_path is not None
        self._manifest_path.write_text(
            json.dumps(
                {
                    "bundle_type": "modbus_capture_manifest",
                    "version": 1,
                    "metadata": asdict(metadata),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _open_events_file(self, *, part: int) -> None:
        self._current_events_path = self._path_for_kind("events", part)
        self._events_handle = self._current_events_path.open("w", encoding="utf-8", newline="")

    def _open_exchanges_file(self, *, part: int) -> None:
        self._current_exchanges_path = self._path_for_kind("exchanges", part)
        self._exchanges_handle = self._current_exchanges_path.open(
            "w", encoding="utf-8", newline=""
        )

    def _path_for_kind(self, kind: str, part: int) -> Path:
        suffix = "" if part <= 1 else f"_part{part:03d}"
        return self._output_dir / f"{self._base_name}_{kind}{suffix}.jsonl"

    def _write_metadata_if_needed(self, handle: object | None) -> None:
        if not self.config.include_metadata or handle is None:
            return
        self._write_line(handle, self._metadata_line)

    def _rotate_events_if_needed(self) -> None:
        if self._events_handle is None or self._current_events_path is None:
            return
        if self._current_events_path.stat().st_size < self.config.rotate_max_bytes:
            return
        self.rotations += 1
        self._close_handle("_events_handle")
        self._events_part += 1
        self._open_events_file(part=self._events_part)
        self._write_metadata_if_needed(self._events_handle)

    def _rotate_exchanges_if_needed(self) -> None:
        if self._exchanges_handle is None or self._current_exchanges_path is None:
            return
        if self._current_exchanges_path.stat().st_size < self.config.rotate_max_bytes:
            return
        self.rotations += 1
        self._close_handle("_exchanges_handle")
        self._exchanges_part += 1
        self._open_exchanges_file(part=self._exchanges_part)
        self._write_metadata_if_needed(self._exchanges_handle)

    def _write_line(self, handle: object, line: str) -> None:
        handle.write(line)
        handle.write("\n")
        self.bytes_written += len((line + "\n").encode("utf-8"))
        if self.records_written % self.config.flush_every_records == 0:
            handle.flush()

    def _close_handle(self, attribute_name: str) -> None:
        handle = getattr(self, attribute_name)
        if handle is None:
            return
        try:
            handle.flush()
            handle.close()
        finally:
            setattr(self, attribute_name, None)


def _slugify_base_name(base_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name.strip())
    normalized = normalized.strip("._-")
    return normalized or "modbus_capture"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _overlap_index(previous_signatures: list[str], current_signatures: list[str]) -> int:
    max_overlap = min(len(previous_signatures), len(current_signatures))
    for overlap in range(max_overlap, 0, -1):
        if previous_signatures[-overlap:] == current_signatures[:overlap]:
            return overlap
    return 0
