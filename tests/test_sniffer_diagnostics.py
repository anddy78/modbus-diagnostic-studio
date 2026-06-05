"""Tests for preliminary passive sniffer diagnosis."""

from modbus_diagnostic_studio.sniffer.diagnostics import build_preliminary_diagnosis
from modbus_diagnostic_studio.sniffer.stats import SnifferStats


def test_no_traffic_message() -> None:
    assert build_preliminary_diagnosis(SnifferStats()) == [
        "No Modbus RTU traffic detected."
    ]


def test_high_crc_message() -> None:
    messages = build_preliminary_diagnosis(
        SnifferStats(total_frames=3, valid_crc_frames=1, invalid_crc_frames=2)
    )

    assert any("High CRC error rate" in message for message in messages)


def test_requests_no_responses_message() -> None:
    messages = build_preliminary_diagnosis(
        SnifferStats(total_frames=1, valid_crc_frames=1, requests=1, responses=0)
    )

    assert any("Requests detected but no responses" in message for message in messages)


def test_healthy_communication_message() -> None:
    messages = build_preliminary_diagnosis(
        SnifferStats(
            total_frames=2,
            valid_crc_frames=2,
            requests=1,
            responses=1,
            invalid_crc_frames=0,
            timeouts=0,
        )
    )

    assert "Communication appears healthy at RTU frame level." in messages


def test_exceptions_message() -> None:
    messages = build_preliminary_diagnosis(
        SnifferStats(total_frames=2, valid_crc_frames=2, requests=1, exceptions=1)
    )

    assert "Modbus exception responses detected." in messages
