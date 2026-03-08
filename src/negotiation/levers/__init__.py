"""Negotiation lever engine -- selects tactics based on campaign data and state."""

from negotiation.levers.models import LeverAction, LeverResult, NegotiationLeverContext

__all__ = [
    "LeverAction",
    "LeverResult",
    "NegotiationLeverContext",
    "select_lever",
]


def select_lever(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Placeholder -- replaced by engine import in Task 2."""
    raise NotImplementedError("Engine not yet implemented")
