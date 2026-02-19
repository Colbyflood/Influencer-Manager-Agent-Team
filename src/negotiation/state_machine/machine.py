"""NegotiationStateMachine class with trigger, history, and valid_events."""

from __future__ import annotations

from negotiation.domain.errors import InvalidTransitionError
from negotiation.domain.types import NegotiationState
from negotiation.state_machine.transitions import TERMINAL_STATES, TRANSITIONS


class NegotiationStateMachine:
    """Finite state machine governing the negotiation lifecycle.

    Tracks the current negotiation state, validates transitions against the
    transition map, and records a full audit history of all state changes.

    Usage::

        sm = NegotiationStateMachine()
        sm.trigger("send_offer")      # -> AWAITING_REPLY
        sm.trigger("receive_reply")   # -> COUNTER_RECEIVED
        sm.trigger("accept")          # -> AGREED (terminal)
    """

    def __init__(
        self,
        initial_state: NegotiationState = NegotiationState.INITIAL_OFFER,
    ) -> None:
        self._state: NegotiationState = initial_state
        self._history: list[tuple[NegotiationState, str, NegotiationState]] = []

    @classmethod
    def from_snapshot(
        cls,
        state: NegotiationState,
        history: list[tuple[NegotiationState, str, NegotiationState]],
    ) -> NegotiationStateMachine:
        """Reconstruct a state machine from a persisted snapshot.

        Creates an instance at the given *state* with the provided *history*
        without replaying events.  This makes the persistence contract
        explicit rather than requiring external code to poke at ``_history``.

        Args:
            state: The negotiation state to restore.
            history: The full transition history as ``(from, event, to)``
                     tuples in chronological order.

        Returns:
            A ``NegotiationStateMachine`` positioned at *state* with the
            given history already recorded.
        """
        instance = cls(initial_state=state)
        instance._history = list(history)  # defensive copy
        return instance

    @property
    def state(self) -> NegotiationState:
        """Return the current negotiation state."""
        return self._state

    @property
    def is_terminal(self) -> bool:
        """Return True if the machine is in a terminal state (AGREED or REJECTED)."""
        return self._state in TERMINAL_STATES

    @property
    def history(self) -> list[tuple[NegotiationState, str, NegotiationState]]:
        """Return a copy of the transition history.

        Each entry is a ``(from_state, event, to_state)`` tuple recorded in
        chronological order.
        """
        return list(self._history)

    def trigger(self, event: str) -> NegotiationState:
        """Apply an event to the current state and transition.

        Args:
            event: The event string (e.g. ``"send_offer"``).

        Returns:
            The new state after the transition.

        Raises:
            InvalidTransitionError: If the transition is not allowed from
                the current state, or if the machine is in a terminal state.
        """
        if self.is_terminal:
            raise InvalidTransitionError(self._state, event)

        key = (self._state, event)
        if key not in TRANSITIONS:
            raise InvalidTransitionError(self._state, event)

        old_state = self._state
        new_state = TRANSITIONS[key]
        self._history.append((old_state, event, new_state))
        self._state = new_state
        return new_state

    def get_valid_events(self) -> list[str]:
        """Return a sorted list of events valid from the current state.

        Returns an empty list if the machine is in a terminal state.
        """
        if self.is_terminal:
            return []
        return sorted(event for state, event in TRANSITIONS if state == self._state)
