"""Preliminary passive sniffer diagnostics."""

from __future__ import annotations

from modbus_diagnostic_studio.sniffer.stats import SnifferStats


def build_preliminary_diagnosis(stats: SnifferStats) -> list[str]:
    """Build generic diagnostic messages from sniffer statistics."""
    messages: list[str] = []

    if stats.total_frames == 0:
        messages.append("No Modbus RTU traffic detected.")
        return messages
    if stats.invalid_crc_frames > stats.valid_crc_frames:
        messages.append(
            "High CRC error rate. Possible serial settings mismatch, noise, or wiring issue."
        )
    if stats.requests > 0 and stats.responses == 0:
        messages.append(
            "Requests detected but no responses. Possible wrong slave ID, disconnected slave, A/B reversed, or sniffer sees only master side."
        )
    if stats.timeouts > 0:
        messages.append("Timeouts detected between requests and responses.")
    if stats.exceptions > 0:
        messages.append("Modbus exception responses detected.")
    if (
        stats.requests > 0
        and stats.responses > 0
        and stats.invalid_crc_frames == 0
        and stats.timeouts == 0
    ):
        messages.append("Communication appears healthy at RTU frame level.")

    return messages
