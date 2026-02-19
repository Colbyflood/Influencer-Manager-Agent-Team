"""Negotiation state machine with transition validation."""

from negotiation.state_machine.machine import NegotiationStateMachine
from negotiation.state_machine.transitions import (
    TERMINAL_STATES,
    TRANSITIONS,
    NegotiationEvent,
)

__all__ = [
    "TERMINAL_STATES",
    "TRANSITIONS",
    "NegotiationEvent",
    "NegotiationStateMachine",
]
