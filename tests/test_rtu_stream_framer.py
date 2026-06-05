"""Tests for passive RTU stream framing."""

from modbus_diagnostic_studio.sniffer.rtu_stream_framer import (
    FramedRtuPacket,
    RtuFramerConfig,
    RtuStreamFramer,
)


def test_char_time_seconds_is_positive() -> None:
    config = RtuFramerConfig(baudrate=9600)

    assert config.char_time_seconds() > 0


def test_frame_gap_seconds_is_greater_than_char_time() -> None:
    config = RtuFramerConfig(baudrate=9600)

    assert config.frame_gap_seconds() > config.char_time_seconds()


def test_feed_without_gap_emits_nothing() -> None:
    framer = RtuStreamFramer()

    packets = framer.feed(b"\x01\x03", 1.0)
    packets += framer.feed(b"\x00\x00", 1.0001)

    assert packets == []
    assert framer.buffer_size() == 4


def test_feed_with_gap_emits_previous_buffer() -> None:
    framer = RtuStreamFramer()
    framer.feed(b"\x01\x03", 1.0)

    packets = framer.feed(b"\x02", 1.01)

    assert packets == [FramedRtuPacket(timestamp_monotonic=1.0, raw=b"\x01\x03", reason="gap")]
    assert framer.buffer_size() == 1


def test_flush_emits_pending_buffer() -> None:
    framer = RtuStreamFramer()
    framer.feed(b"\x01\x03\x00", 1.0)

    packets = framer.flush(2.0)

    assert packets == [FramedRtuPacket(timestamp_monotonic=1.0, raw=b"\x01\x03\x00", reason="flush")]
    assert framer.buffer_size() == 0


def test_clear_empties_buffer() -> None:
    framer = RtuStreamFramer()
    framer.feed(b"\x01\x03\x00", 1.0)

    framer.clear()

    assert framer.buffer_size() == 0


def test_buffer_size_reports_current_size() -> None:
    framer = RtuStreamFramer()
    framer.feed(b"\x01\x03\x00\x00", 1.0)

    assert framer.buffer_size() == 4


def test_max_frame_size_emits_controlled_packet() -> None:
    framer = RtuStreamFramer(RtuFramerConfig(max_frame_size=4))

    packets = framer.feed(b"\x01\x03\x00\x00", 1.0)

    assert packets == [
        FramedRtuPacket(timestamp_monotonic=1.0, raw=b"\x01\x03\x00\x00", reason="max_frame_size")
    ]
    assert framer.buffer_size() == 0


def test_feed_with_empty_data_does_not_break() -> None:
    framer = RtuStreamFramer()

    packets = framer.feed(b"", 1.0)

    assert packets == []
    assert framer.buffer_size() == 0


def test_multiple_frames_consecutive_by_gaps() -> None:
    framer = RtuStreamFramer()
    packets = []
    packets += framer.feed(b"\x01\x03", 1.0)
    packets += framer.feed(b"\x00\x00", 1.0001)
    packets += framer.feed(b"\x02", 1.01)
    packets += framer.feed(b"\x11\x04", 1.0101)
    packets += framer.feed(b"\x00\x10", 1.0102)
    packets += framer.flush(2.0)

    assert packets == [
        FramedRtuPacket(timestamp_monotonic=1.0, raw=b"\x01\x03\x00\x00", reason="gap"),
        FramedRtuPacket(timestamp_monotonic=1.01, raw=b"\x02\x11\x04\x00\x10", reason="flush"),
    ]
