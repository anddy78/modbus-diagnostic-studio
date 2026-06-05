"""Request/response matcher for passive captures."""

from __future__ import annotations

from modbus_diagnostic_studio.models.capture import (
    CaptureFrameEvent,
    FrameDirectionGuess,
    MatchedExchange,
)


class RequestResponseMatcher:
    """Match passive Modbus RTU requests to responses."""

    def __init__(self, timeout_ms: float = 1000.0) -> None:
        self.timeout_ms = timeout_ms
        self._pending: list[CaptureFrameEvent] = []

    def add_event(self, event: CaptureFrameEvent) -> MatchedExchange | None:
        """Add an event and return a completed exchange when one is available."""
        if event.direction_guess is FrameDirectionGuess.REQUEST:
            self._pending.append(event)
            return None

        if event.direction_guess in {
            FrameDirectionGuess.RESPONSE,
            FrameDirectionGuess.EXCEPTION_RESPONSE,
        }:
            request = self._pop_matching_request(event)
            if request is None:
                return MatchedExchange(
                    request=event,
                    response=event,
                    latency_ms=None,
                    status="unmatched_response",
                    note="Response observed without a compatible pending request.",
                )

            latency_ms = (
                event.timestamp_monotonic - request.timestamp_monotonic
            ) * 1000.0
            status = (
                "exception"
                if event.direction_guess is FrameDirectionGuess.EXCEPTION_RESPONSE
                else "ok"
            )
            return MatchedExchange(
                request=request,
                response=event,
                latency_ms=latency_ms,
                status=status,
            )

        return None

    def flush_expired(self, now_monotonic: float) -> list[MatchedExchange]:
        """Return timeout exchanges for expired pending requests."""
        expired: list[MatchedExchange] = []
        active: list[CaptureFrameEvent] = []
        for request in self._pending:
            age_ms = (now_monotonic - request.timestamp_monotonic) * 1000.0
            if age_ms >= self.timeout_ms:
                expired.append(
                    MatchedExchange(
                        request=request,
                        response=None,
                        latency_ms=None,
                        status="timeout",
                        note="No compatible response before timeout.",
                    )
                )
            else:
                active.append(request)
        self._pending = active
        return expired

    def pending_count(self) -> int:
        """Return pending request count."""
        return len(self._pending)

    def _pop_matching_request(
        self,
        response: CaptureFrameEvent,
    ) -> CaptureFrameEvent | None:
        response_function = response.function_code
        if response_function is not None and response_function & 0x80:
            response_function &= 0x7F

        for index, request in enumerate(self._pending):
            if (
                request.slave_id == response.slave_id
                and request.function_code == response_function
            ):
                return self._pending.pop(index)
        return None
