"""Domain-specific exception classes for the negotiation agent."""

from negotiation.domain.types import DeliverableType, NegotiationState, Platform


class NegotiationError(Exception):
    """Base class for all domain errors in the negotiation agent."""


class InvalidTransitionError(NegotiationError):
    """Raised when an invalid state transition is attempted.

    Attributes:
        current_state: The state the machine was in when the transition was attempted.
        event: The event that was rejected.
    """

    def __init__(self, current_state: NegotiationState, event: str) -> None:
        self.current_state = current_state
        self.event = event
        super().__init__(
            f"Cannot apply event '{event}' in state '{current_state}'"
        )


class InvalidDeliverableError(NegotiationError):
    """Raised when a deliverable type is invalid for a given platform.

    Attributes:
        platform: The platform the deliverable was assigned to.
        deliverable_type: The invalid deliverable type.
    """

    def __init__(self, platform: Platform, deliverable_type: DeliverableType) -> None:
        self.platform = platform
        self.deliverable_type = deliverable_type
        super().__init__(
            f"{deliverable_type} is not a valid deliverable type for {platform}"
        )


class PricingError(NegotiationError):
    """Raised when a pricing calculation fails."""
