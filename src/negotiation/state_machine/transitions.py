"""Transition map defining all valid (state, event) -> state mappings."""

from enum import StrEnum

from negotiation.domain.types import NegotiationState


class NegotiationEvent(StrEnum):
    """Events that can trigger state transitions in a negotiation."""

    SEND_OFFER = "send_offer"
    RECEIVE_REPLY = "receive_reply"
    TIMEOUT = "timeout"
    SEND_COUNTER = "send_counter"
    ACCEPT = "accept"
    REJECT = "reject"
    ESCALATE = "escalate"
    RESUME_COUNTER = "resume_counter"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


# All valid (current_state, event_string) -> next_state mappings.
# Any pair not in this dict is an invalid transition.
TRANSITIONS: dict[tuple[NegotiationState, str], NegotiationState] = {
    # From INITIAL_OFFER
    (NegotiationState.INITIAL_OFFER, NegotiationEvent.SEND_OFFER): NegotiationState.AWAITING_REPLY,
    # From AWAITING_REPLY
    (NegotiationState.AWAITING_REPLY, NegotiationEvent.RECEIVE_REPLY): (
        NegotiationState.COUNTER_RECEIVED
    ),
    (NegotiationState.AWAITING_REPLY, NegotiationEvent.TIMEOUT): NegotiationState.STALE,
    # From COUNTER_RECEIVED
    (NegotiationState.COUNTER_RECEIVED, NegotiationEvent.SEND_COUNTER): (
        NegotiationState.COUNTER_SENT
    ),
    (NegotiationState.COUNTER_RECEIVED, NegotiationEvent.ACCEPT): NegotiationState.AGREED,
    (NegotiationState.COUNTER_RECEIVED, NegotiationEvent.REJECT): NegotiationState.REJECTED,
    (NegotiationState.COUNTER_RECEIVED, NegotiationEvent.ESCALATE): NegotiationState.ESCALATED,
    # From COUNTER_SENT
    (NegotiationState.COUNTER_SENT, NegotiationEvent.RECEIVE_REPLY): (
        NegotiationState.COUNTER_RECEIVED
    ),
    (NegotiationState.COUNTER_SENT, NegotiationEvent.TIMEOUT): NegotiationState.STALE,
    # From ESCALATED
    (NegotiationState.ESCALATED, NegotiationEvent.RESUME_COUNTER): NegotiationState.COUNTER_SENT,
    (NegotiationState.ESCALATED, NegotiationEvent.REJECT): NegotiationState.REJECTED,
    # From STALE
    (NegotiationState.STALE, NegotiationEvent.RECEIVE_REPLY): NegotiationState.COUNTER_RECEIVED,
    (NegotiationState.STALE, NegotiationEvent.REJECT): NegotiationState.REJECTED,
    # Pause transitions (all non-terminal states -> PAUSED)
    (NegotiationState.INITIAL_OFFER, NegotiationEvent.PAUSE): NegotiationState.PAUSED,
    (NegotiationState.AWAITING_REPLY, NegotiationEvent.PAUSE): NegotiationState.PAUSED,
    (NegotiationState.COUNTER_RECEIVED, NegotiationEvent.PAUSE): NegotiationState.PAUSED,
    (NegotiationState.COUNTER_SENT, NegotiationEvent.PAUSE): NegotiationState.PAUSED,
    (NegotiationState.ESCALATED, NegotiationEvent.PAUSE): NegotiationState.PAUSED,
    (NegotiationState.STALE, NegotiationEvent.PAUSE): NegotiationState.PAUSED,
    # Stop transitions (all non-terminal states + PAUSED -> STOPPED)
    (NegotiationState.INITIAL_OFFER, NegotiationEvent.STOP): NegotiationState.STOPPED,
    (NegotiationState.AWAITING_REPLY, NegotiationEvent.STOP): NegotiationState.STOPPED,
    (NegotiationState.COUNTER_RECEIVED, NegotiationEvent.STOP): NegotiationState.STOPPED,
    (NegotiationState.COUNTER_SENT, NegotiationEvent.STOP): NegotiationState.STOPPED,
    (NegotiationState.ESCALATED, NegotiationEvent.STOP): NegotiationState.STOPPED,
    (NegotiationState.STALE, NegotiationEvent.STOP): NegotiationState.STOPPED,
    (NegotiationState.PAUSED, NegotiationEvent.STOP): NegotiationState.STOPPED,
}

# States that reject all events -- no outgoing transitions allowed.
TERMINAL_STATES: frozenset[NegotiationState] = frozenset(
    {NegotiationState.AGREED, NegotiationState.REJECTED, NegotiationState.STOPPED}
)
