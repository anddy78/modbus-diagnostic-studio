"""Tests for communication profile fingerprint scoring."""

from modbus_diagnostic_studio.models.capture import CaptureFrameEvent, FrameDirectionGuess
from modbus_diagnostic_studio.sniffer.communication_profiles import (
    load_all_builtin_communication_profiles,
    load_builtin_communication_profile,
)
from modbus_diagnostic_studio.sniffer.fingerprint import (
    rank_communication_profiles,
    score_communication_profile,
)


def fake_event(
    *,
    direction_guess: FrameDirectionGuess,
    slave_id: int | None = None,
    function_code: int | None = None,
    address: int | None = None,
    quantity: int | None = None,
) -> CaptureFrameEvent:
    return CaptureFrameEvent(
        timestamp_monotonic=1.0,
        raw=b"",
        raw_hex="",
        crc_ok=True,
        classification="read_request"
        if direction_guess is FrameDirectionGuess.REQUEST
        else "read_response",
        direction_guess=direction_guess,
        slave_id=slave_id,
        function_code=function_code,
        address=address,
        quantity=quantity,
    )


def test_dtsu71_events_score_high_for_smartlogger_chint_dtsu71() -> None:
    profile = load_builtin_communication_profile("smartlogger_chint_dtsu71")
    events = [
        fake_event(
            direction_guess=FrameDirectionGuess.REQUEST,
            slave_id=11,
            function_code=3,
            address=2102,
            quantity=42,
        ),
        fake_event(
            direction_guess=FrameDirectionGuess.REQUEST,
            slave_id=11,
            function_code=3,
            address=2158,
            quantity=66,
        ),
        fake_event(
            direction_guess=FrameDirectionGuess.RESPONSE,
            slave_id=11,
            function_code=3,
        ),
    ]

    score = score_communication_profile(profile, events)

    assert score.score == 100.0
    assert any("2102" in item for item in score.matched_items)
    assert any("2158" in item for item in score.matched_items)


def test_generic_fc03_event_scores_low_but_nonzero_for_generic_profile() -> None:
    profile = load_builtin_communication_profile("generic_modbus_rtu")
    events = [
        fake_event(
            direction_guess=FrameDirectionGuess.REQUEST,
            slave_id=1,
            function_code=3,
            address=0,
            quantity=2,
        )
    ]

    score = score_communication_profile(profile, events)

    assert score.score == 20.0
    assert score.matched_items


def test_rank_orders_highest_score_first() -> None:
    profiles = load_all_builtin_communication_profiles()
    events = [
        fake_event(
            direction_guess=FrameDirectionGuess.REQUEST,
            slave_id=11,
            function_code=3,
            address=2102,
            quantity=42,
        ),
        fake_event(
            direction_guess=FrameDirectionGuess.REQUEST,
            slave_id=11,
            function_code=3,
            address=2158,
            quantity=66,
        ),
        fake_event(
            direction_guess=FrameDirectionGuess.RESPONSE,
            slave_id=11,
            function_code=3,
        ),
    ]

    ranked = rank_communication_profiles(profiles, events)

    assert ranked[0].profile_id == "smartlogger_chint_dtsu71"


def test_missing_items_contains_missing_block() -> None:
    profile = load_builtin_communication_profile("smartlogger_chint_dtsu71")
    events = [
        fake_event(
            direction_guess=FrameDirectionGuess.REQUEST,
            slave_id=11,
            function_code=3,
            address=2102,
            quantity=42,
        )
    ]

    score = score_communication_profile(profile, events)

    assert any("2158" in item for item in score.missing_items)


def test_response_associated_with_expected_request_adds_score() -> None:
    profile = load_builtin_communication_profile("smartlogger_janitza_umg604")
    request_only = [
        fake_event(
            direction_guess=FrameDirectionGuess.REQUEST,
            slave_id=11,
            function_code=3,
            address=19000,
            quantity=110,
        )
    ]
    with_response = request_only + [
        fake_event(
            direction_guess=FrameDirectionGuess.RESPONSE,
            slave_id=11,
            function_code=3,
        )
    ]

    score_without_response = score_communication_profile(profile, request_only)
    score_with_response = score_communication_profile(profile, with_response)

    assert score_with_response.score > score_without_response.score
