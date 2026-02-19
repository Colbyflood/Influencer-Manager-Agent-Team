"""Tests for the negotiation state machine transition map."""

import pytest

from negotiation.domain.types import NegotiationState
from negotiation.state_machine.transitions import (
    TERMINAL_STATES,
    TRANSITIONS,
    NegotiationEvent,
)


class TestNegotiationEvent:
    """Tests for the NegotiationEvent enum."""

    EXPECTED_MEMBERS = {
        "SEND_OFFER": "send_offer",
        "RECEIVE_REPLY": "receive_reply",
        "TIMEOUT": "timeout",
        "SEND_COUNTER": "send_counter",
        "ACCEPT": "accept",
        "REJECT": "reject",
        "ESCALATE": "escalate",
        "RESUME_COUNTER": "resume_counter",
    }

    def test_has_exactly_8_members(self) -> None:
        assert len(NegotiationEvent) == 8

    @pytest.mark.parametrize(
        ("name", "value"),
        list(EXPECTED_MEMBERS.items()),
        ids=list(EXPECTED_MEMBERS.keys()),
    )
    def test_member_name_and_value(self, name: str, value: str) -> None:
        member = NegotiationEvent[name]
        assert member.value == value

    def test_is_str_enum(self) -> None:
        """NegotiationEvent members should be usable as strings."""
        assert str(NegotiationEvent.SEND_OFFER) == "send_offer"


class TestTransitionsMap:
    """Tests for the TRANSITIONS dict completeness."""

    def test_has_exactly_13_entries(self) -> None:
        assert len(TRANSITIONS) == 13

    def test_all_non_terminal_states_appear_as_source(self) -> None:
        """Every non-terminal state must be a source in at least one transition."""
        source_states = {state for state, _event in TRANSITIONS}
        non_terminal = {s for s in NegotiationState if s not in TERMINAL_STATES}
        assert non_terminal == source_states

    def test_terminal_states_never_appear_as_source(self) -> None:
        """AGREED and REJECTED must never appear as source states."""
        source_states = {state for state, _event in TRANSITIONS}
        for terminal in TERMINAL_STATES:
            assert terminal not in source_states, f"{terminal} should not be a source state"

    def test_all_transition_values_are_negotiation_states(self) -> None:
        """Every target state in the map must be a valid NegotiationState."""
        for target in TRANSITIONS.values():
            assert isinstance(target, NegotiationState)


class TestTerminalStates:
    """Tests for the TERMINAL_STATES frozenset."""

    def test_contains_agreed(self) -> None:
        assert NegotiationState.AGREED in TERMINAL_STATES

    def test_contains_rejected(self) -> None:
        assert NegotiationState.REJECTED in TERMINAL_STATES

    def test_has_exactly_2_members(self) -> None:
        assert len(TERMINAL_STATES) == 2

    def test_is_frozenset(self) -> None:
        assert isinstance(TERMINAL_STATES, frozenset)
