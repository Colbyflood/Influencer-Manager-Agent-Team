"""Tests for the NegotiationStateMachine class."""

import pytest

from negotiation.domain.errors import InvalidTransitionError
from negotiation.domain.types import NegotiationState
from negotiation.state_machine.machine import NegotiationStateMachine
from negotiation.state_machine.transitions import NegotiationEvent

# ---------------------------------------------------------------------------
# All 13 valid transitions
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: list[tuple[NegotiationState, str, NegotiationState]] = [
    (NegotiationState.INITIAL_OFFER, "send_offer", NegotiationState.AWAITING_REPLY),
    (NegotiationState.AWAITING_REPLY, "receive_reply", NegotiationState.COUNTER_RECEIVED),
    (NegotiationState.AWAITING_REPLY, "timeout", NegotiationState.STALE),
    (NegotiationState.COUNTER_RECEIVED, "send_counter", NegotiationState.COUNTER_SENT),
    (NegotiationState.COUNTER_RECEIVED, "accept", NegotiationState.AGREED),
    (NegotiationState.COUNTER_RECEIVED, "reject", NegotiationState.REJECTED),
    (NegotiationState.COUNTER_RECEIVED, "escalate", NegotiationState.ESCALATED),
    (NegotiationState.COUNTER_SENT, "receive_reply", NegotiationState.COUNTER_RECEIVED),
    (NegotiationState.COUNTER_SENT, "timeout", NegotiationState.STALE),
    (NegotiationState.ESCALATED, "resume_counter", NegotiationState.COUNTER_SENT),
    (NegotiationState.ESCALATED, "reject", NegotiationState.REJECTED),
    (NegotiationState.STALE, "receive_reply", NegotiationState.COUNTER_RECEIVED),
    (NegotiationState.STALE, "reject", NegotiationState.REJECTED),
]

# ---------------------------------------------------------------------------
# All 8 event string values
# ---------------------------------------------------------------------------
ALL_EVENTS: list[str] = [e.value for e in NegotiationEvent]

# ---------------------------------------------------------------------------
# Invalid transitions for non-terminal states
# Build the set of valid (state, event) pairs, then for each non-terminal
# state compute which events are NOT valid.
# ---------------------------------------------------------------------------
_VALID_PAIRS: set[tuple[NegotiationState, str]] = {(s, e) for s, e, _ in VALID_TRANSITIONS}

TERMINAL_STATES = {NegotiationState.AGREED, NegotiationState.REJECTED}

INVALID_NON_TERMINAL_TRANSITIONS: list[tuple[NegotiationState, str]] = [
    (state, event)
    for state in NegotiationState
    if state not in TERMINAL_STATES
    for event in ALL_EVENTS
    if (state, event) not in _VALID_PAIRS
]


# ===================================================================
# Parameterized valid transitions
# ===================================================================
class TestValidTransitions:
    """Parameterized test for all 13 valid transitions."""

    @pytest.mark.parametrize(
        ("from_state", "event", "to_state"),
        VALID_TRANSITIONS,
        ids=[f"{s.value}+{e}->{t.value}" for s, e, t in VALID_TRANSITIONS],
    )
    def test_valid_transition(
        self,
        from_state: NegotiationState,
        event: str,
        to_state: NegotiationState,
    ) -> None:
        sm = NegotiationStateMachine(initial_state=from_state)
        result = sm.trigger(event)
        assert result == to_state
        assert sm.state == to_state


# ===================================================================
# Terminal states reject ALL events
# ===================================================================
class TestTerminalStates:
    """Terminal states (AGREED, REJECTED) must reject every event."""

    @pytest.mark.parametrize("terminal", list(TERMINAL_STATES), ids=lambda s: s.value)
    @pytest.mark.parametrize("event", ALL_EVENTS, ids=lambda e: e)
    def test_terminal_rejects_event(self, terminal: NegotiationState, event: str) -> None:
        sm = NegotiationStateMachine(initial_state=terminal)
        with pytest.raises(InvalidTransitionError) as exc_info:
            sm.trigger(event)
        assert exc_info.value.current_state == terminal
        assert exc_info.value.event == event


# ===================================================================
# Invalid non-terminal transitions
# ===================================================================
class TestInvalidNonTerminalTransitions:
    """Non-terminal states must reject events that are not in the transition map."""

    @pytest.mark.parametrize(
        ("state", "event"),
        INVALID_NON_TERMINAL_TRANSITIONS,
        ids=[f"{s.value}+{e}" for s, e in INVALID_NON_TERMINAL_TRANSITIONS],
    )
    def test_invalid_transition_raises(self, state: NegotiationState, event: str) -> None:
        sm = NegotiationStateMachine(initial_state=state)
        with pytest.raises(InvalidTransitionError):
            sm.trigger(event)


# ===================================================================
# Path integration tests
# ===================================================================
class TestHappyPath:
    """End-to-end happy path: INITIAL_OFFER -> ... -> AGREED."""

    def test_full_negotiation_to_agreement(self) -> None:
        sm = NegotiationStateMachine()
        sm.trigger("send_offer")
        assert sm.state == NegotiationState.AWAITING_REPLY
        sm.trigger("receive_reply")
        assert sm.state == NegotiationState.COUNTER_RECEIVED
        sm.trigger("send_counter")
        assert sm.state == NegotiationState.COUNTER_SENT
        sm.trigger("receive_reply")
        assert sm.state == NegotiationState.COUNTER_RECEIVED
        sm.trigger("accept")
        assert sm.state == NegotiationState.AGREED
        assert sm.is_terminal


class TestEscalationPath:
    """Escalation path: COUNTER_RECEIVED -> escalate -> resume_counter -> COUNTER_SENT."""

    def test_escalation_and_resume(self) -> None:
        sm = NegotiationStateMachine(initial_state=NegotiationState.COUNTER_RECEIVED)
        sm.trigger("escalate")
        assert sm.state == NegotiationState.ESCALATED
        sm.trigger("resume_counter")
        assert sm.state == NegotiationState.COUNTER_SENT


class TestStaleRevival:
    """Stale thread revival: AWAITING_REPLY -> timeout -> STALE -> receive_reply."""

    def test_stale_then_revive(self) -> None:
        sm = NegotiationStateMachine(initial_state=NegotiationState.AWAITING_REPLY)
        sm.trigger("timeout")
        assert sm.state == NegotiationState.STALE
        sm.trigger("receive_reply")
        assert sm.state == NegotiationState.COUNTER_RECEIVED


# ===================================================================
# History tracking
# ===================================================================
class TestHistory:
    """History should record every transition as (from_state, event, to_state) tuples."""

    def test_history_records_all_transitions(self) -> None:
        sm = NegotiationStateMachine()
        sm.trigger("send_offer")
        sm.trigger("receive_reply")
        sm.trigger("accept")
        assert len(sm.history) == 3
        assert sm.history[0] == (
            NegotiationState.INITIAL_OFFER,
            "send_offer",
            NegotiationState.AWAITING_REPLY,
        )
        assert sm.history[1] == (
            NegotiationState.AWAITING_REPLY,
            "receive_reply",
            NegotiationState.COUNTER_RECEIVED,
        )
        assert sm.history[2] == (
            NegotiationState.COUNTER_RECEIVED,
            "accept",
            NegotiationState.AGREED,
        )

    def test_history_empty_at_start(self) -> None:
        sm = NegotiationStateMachine()
        assert sm.history == []

    def test_history_is_a_copy(self) -> None:
        """Modifying the returned history list should not affect the machine."""
        sm = NegotiationStateMachine()
        sm.trigger("send_offer")
        history = sm.history
        history.clear()
        assert len(sm.history) == 1


# ===================================================================
# get_valid_events
# ===================================================================
class TestGetValidEvents:
    """get_valid_events returns sorted list of valid events from current state."""

    def test_initial_offer_only_send_offer(self) -> None:
        sm = NegotiationStateMachine()
        assert sm.get_valid_events() == ["send_offer"]

    def test_agreed_has_no_valid_events(self) -> None:
        sm = NegotiationStateMachine(initial_state=NegotiationState.AGREED)
        assert sm.get_valid_events() == []

    def test_counter_received_has_four_events(self) -> None:
        sm = NegotiationStateMachine(initial_state=NegotiationState.COUNTER_RECEIVED)
        valid = sm.get_valid_events()
        assert valid == sorted(["send_counter", "accept", "reject", "escalate"])


# ===================================================================
# is_terminal property
# ===================================================================
class TestIsTerminal:
    """is_terminal property checks AGREED and REJECTED."""

    @pytest.mark.parametrize(
        "state",
        [NegotiationState.AGREED, NegotiationState.REJECTED],
        ids=["agreed", "rejected"],
    )
    def test_terminal_states_return_true(self, state: NegotiationState) -> None:
        sm = NegotiationStateMachine(initial_state=state)
        assert sm.is_terminal is True

    @pytest.mark.parametrize(
        "state",
        [
            s
            for s in NegotiationState
            if s not in {NegotiationState.AGREED, NegotiationState.REJECTED}
        ],
        ids=[
            s.value
            for s in NegotiationState
            if s not in {NegotiationState.AGREED, NegotiationState.REJECTED}
        ],
    )
    def test_non_terminal_states_return_false(self, state: NegotiationState) -> None:
        sm = NegotiationStateMachine(initial_state=state)
        assert sm.is_terminal is False


# ===================================================================
# Default and custom initial state
# ===================================================================
class TestInitialState:
    """Machine initialization tests."""

    def test_default_initial_state(self) -> None:
        sm = NegotiationStateMachine()
        assert sm.state == NegotiationState.INITIAL_OFFER

    def test_custom_initial_state(self) -> None:
        sm = NegotiationStateMachine(initial_state=NegotiationState.COUNTER_RECEIVED)
        assert sm.state == NegotiationState.COUNTER_RECEIVED
