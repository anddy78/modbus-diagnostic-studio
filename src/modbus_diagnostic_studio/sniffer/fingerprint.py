"""Communication profile fingerprint scoring."""

from __future__ import annotations

from modbus_diagnostic_studio.models.capture import (
    CaptureFrameEvent,
    FrameDirectionGuess,
)
from modbus_diagnostic_studio.models.communication_profile import (
    CommunicationProfile,
    FingerprintScore,
)


def score_communication_profile(
    profile: CommunicationProfile,
    events: list[CaptureFrameEvent],
) -> FingerprintScore:
    """Score one communication profile against observed capture events."""
    score = 0.0
    matched_items: list[str] = []
    missing_items: list[str] = []

    observed_slave_ids = {event.slave_id for event in events if event.slave_id is not None}
    observed_functions = {
        (event.function_code & 0x7F) if event.function_code is not None and event.function_code & 0x80 else event.function_code
        for event in events
        if event.function_code is not None
    }
    request_events = [
        event for event in events if event.direction_guess is FrameDirectionGuess.REQUEST
    ]
    response_events = [
        event
        for event in events
        if event.direction_guess
        in {FrameDirectionGuess.RESPONSE, FrameDirectionGuess.EXCEPTION_RESPONSE}
    ]

    if profile.expected_slave_ids:
        matched_slave_ids = sorted(
            slave_id for slave_id in observed_slave_ids if slave_id in profile.expected_slave_ids
        )
        if matched_slave_ids:
            score += 20.0
            matched_items.append(f"Observed expected slave ID(s): {matched_slave_ids}")
        else:
            missing_items.append(
                f"Missing expected slave ID(s): {profile.expected_slave_ids}"
            )

    if profile.expected_functions:
        matched_functions = sorted(
            function_code
            for function_code in observed_functions
            if function_code in profile.expected_functions
        )
        if matched_functions:
            score += 20.0
            matched_items.append(
                f"Observed expected function code(s): {matched_functions}"
            )
        else:
            missing_items.append(
                f"Missing expected function code(s): {profile.expected_functions}"
            )

    matched_request_count = 0
    for block in profile.expected_requests:
        block_observed = any(
            event.function_code == block.function_code
            and event.address == block.address
            and event.quantity == block.quantity
            for event in request_events
        )
        if block_observed:
            matched_request_count += 1
            score += 40.0
            matched_items.append(
                f"Observed expected request block FC{block.function_code:02d} address {block.address} quantity {block.quantity}"
            )
        else:
            missing_items.append(
                f"Missing expected request block FC{block.function_code:02d} address {block.address} quantity {block.quantity}"
            )

    if matched_request_count > 0 and response_events:
        score += 10.0
        matched_items.append("Observed responses associated with expected request traffic")
    elif matched_request_count > 0:
        missing_items.append("Expected request traffic observed without any responses")

    return FingerprintScore(
        profile_id=profile.profile_id,
        name=profile.name,
        score=min(score, 100.0),
        matched_items=matched_items,
        missing_items=missing_items,
    )


def rank_communication_profiles(
    profiles: list[CommunicationProfile],
    events: list[CaptureFrameEvent],
) -> list[FingerprintScore]:
    """Rank communication profiles by descending fingerprint score."""
    scores = [score_communication_profile(profile, events) for profile in profiles]
    return sorted(scores, key=lambda item: (-item.score, item.profile_id))
