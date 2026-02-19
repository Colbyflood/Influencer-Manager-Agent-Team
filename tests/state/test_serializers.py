"""Tests for serialization round-trips on context, CPM tracker, and state machine."""

from __future__ import annotations

from decimal import Decimal

from negotiation.campaign.cpm_tracker import CampaignCPMTracker
from negotiation.domain.types import NegotiationState
from negotiation.state.serializers import (
    deserialize_context,
    deserialize_cpm_tracker,
    serialize_context,
    serialize_cpm_tracker,
)
from negotiation.state_machine.machine import NegotiationStateMachine


class TestSerializeContext:
    """Tests for context dict serialization."""

    def test_serialize_context_handles_decimal(self) -> None:
        """Decimal values should survive round-trip as strings."""
        context = {
            "influencer_name": "Jane",
            "next_cpm": Decimal("25.50"),
            "counter_cpm": Decimal("30.00"),
        }
        json_str = serialize_context(context)
        loaded = deserialize_context(json_str)

        assert loaded["influencer_name"] == "Jane"
        assert loaded["next_cpm"] == "25.50"
        assert loaded["counter_cpm"] == "30.00"

        # Verify Decimal can be reconstructed from the string
        assert Decimal(str(loaded["next_cpm"])) == Decimal("25.50")

    def test_serialize_context_handles_plain_types(self) -> None:
        """Context with str, int, and list fields should round-trip correctly."""
        context = {
            "round": 3,
            "influencer_name": "Test",
            "tags": ["instagram", "beauty"],
            "active": True,
        }
        json_str = serialize_context(context)
        loaded = deserialize_context(json_str)

        assert loaded["round"] == 3
        assert loaded["influencer_name"] == "Test"
        assert loaded["tags"] == ["instagram", "beauty"]
        assert loaded["active"] is True


class TestCPMTrackerRoundTrip:
    """Tests for CampaignCPMTracker serialization."""

    def test_cpm_tracker_round_trip(self) -> None:
        """Tracker with agreements should survive to_dict/from_dict round-trip."""
        tracker = CampaignCPMTracker(
            campaign_id="camp-rt",
            target_min_cpm=Decimal("15.00"),
            target_max_cpm=Decimal("25.00"),
            total_influencers=10,
        )
        tracker.record_agreement(Decimal("20.00"), engagement_rate=5.5)
        tracker.record_agreement(Decimal("22.50"), engagement_rate=3.2)

        data = serialize_cpm_tracker(tracker)
        restored = deserialize_cpm_tracker(data)

        assert restored.campaign_id == "camp-rt"
        assert restored.target_min_cpm == Decimal("15.00")
        assert restored.target_max_cpm == Decimal("25.00")
        assert restored.total_influencers == 10
        assert len(restored._agreements) == 2
        assert restored._agreements[0] == (Decimal("20.00"), 5.5)
        assert restored._agreements[1] == (Decimal("22.50"), 3.2)

    def test_cpm_tracker_empty_agreements(self) -> None:
        """Tracker with no agreements should round-trip cleanly."""
        tracker = CampaignCPMTracker(
            campaign_id="camp-empty",
            target_min_cpm=Decimal("10"),
            target_max_cpm=Decimal("20"),
            total_influencers=3,
        )
        data = serialize_cpm_tracker(tracker)
        restored = deserialize_cpm_tracker(data)

        assert restored.campaign_id == "camp-empty"
        assert restored.target_min_cpm == Decimal("10")
        assert restored.target_max_cpm == Decimal("20")
        assert restored.total_influencers == 3
        assert len(restored._agreements) == 0


class TestStateMachineFromSnapshot:
    """Tests for NegotiationStateMachine.from_snapshot round-trip."""

    def test_state_machine_from_snapshot_round_trip(self) -> None:
        """State machine should be reconstructable from state + history."""
        sm = NegotiationStateMachine()
        sm.trigger("send_offer")       # INITIAL_OFFER -> AWAITING_REPLY
        sm.trigger("receive_reply")    # AWAITING_REPLY -> COUNTER_RECEIVED
        sm.trigger("send_counter")     # COUNTER_RECEIVED -> COUNTER_SENT

        original_state = sm.state
        original_history = sm.history

        restored = NegotiationStateMachine.from_snapshot(
            state=original_state,
            history=original_history,
        )

        assert restored.state == NegotiationState.COUNTER_SENT
        assert restored.history == original_history
        assert restored.is_terminal is False

        # Verify valid events match -- COUNTER_SENT can receive_reply or timeout
        valid = restored.get_valid_events()
        assert "receive_reply" in valid
        assert "timeout" in valid

    def test_from_snapshot_with_empty_history(self) -> None:
        """from_snapshot with empty history should produce a usable machine."""
        restored = NegotiationStateMachine.from_snapshot(
            state=NegotiationState.INITIAL_OFFER,
            history=[],
        )
        assert restored.state == NegotiationState.INITIAL_OFFER
        assert restored.history == []
        assert "send_offer" in restored.get_valid_events()

    def test_from_snapshot_terminal_state(self) -> None:
        """from_snapshot at a terminal state should report is_terminal."""
        history = [
            (NegotiationState.INITIAL_OFFER, "send_offer", NegotiationState.AWAITING_REPLY),
            (NegotiationState.AWAITING_REPLY, "receive_reply", NegotiationState.COUNTER_RECEIVED),
            (NegotiationState.COUNTER_RECEIVED, "accept", NegotiationState.AGREED),
        ]
        restored = NegotiationStateMachine.from_snapshot(
            state=NegotiationState.AGREED,
            history=history,
        )
        assert restored.is_terminal is True
        assert restored.get_valid_events() == []
