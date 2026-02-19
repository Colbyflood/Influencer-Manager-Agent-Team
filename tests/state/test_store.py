"""Tests for NegotiationStateStore save/load/delete operations.

Uses an in-memory SQLite database for isolation and speed.
"""

from __future__ import annotations

import json
import sqlite3
import time
from decimal import Decimal

import pytest

from negotiation.campaign.cpm_tracker import CampaignCPMTracker
from negotiation.campaign.models import (
    Campaign,
    CampaignCPMRange,
    CampaignInfluencer,
)
from negotiation.domain.types import Platform
from negotiation.state.schema import init_negotiation_state_table
from negotiation.state.serializers import serialize_context, serialize_cpm_tracker
from negotiation.state.store import NegotiationStateStore
from negotiation.state_machine.machine import NegotiationStateMachine


@pytest.fixture
def conn() -> sqlite3.Connection:
    """In-memory SQLite connection with state table initialized."""
    connection = sqlite3.connect(":memory:")
    init_negotiation_state_table(connection)
    return connection


@pytest.fixture
def store(conn: sqlite3.Connection) -> NegotiationStateStore:
    """NegotiationStateStore backed by the in-memory connection."""
    return NegotiationStateStore(conn)


@pytest.fixture
def sample_campaign() -> Campaign:
    """A minimal Campaign model for testing."""
    return Campaign(
        campaign_id="camp-001",
        client_name="Acme Corp",
        budget=Decimal("10000"),
        target_deliverables="2 Instagram Reels",
        influencers=[
            CampaignInfluencer(
                name="Influencer A",
                platform=Platform.INSTAGRAM,
                engagement_rate=4.5,
            ),
        ],
        cpm_range=CampaignCPMRange(min_cpm=Decimal("20"), max_cpm=Decimal("30")),
        platform=Platform.INSTAGRAM,
        timeline="Q1 2026",
        created_at="2026-01-15T12:00:00Z",
    )


@pytest.fixture
def sample_cpm_tracker() -> CampaignCPMTracker:
    """A CampaignCPMTracker with one agreement for testing."""
    tracker = CampaignCPMTracker(
        campaign_id="camp-001",
        target_min_cpm=Decimal("20"),
        target_max_cpm=Decimal("30"),
        total_influencers=5,
    )
    tracker.record_agreement(Decimal("25.50"), engagement_rate=4.2)
    return tracker


class TestSaveAndLoadActive:
    """Tests for the save/load_active round-trip."""

    def test_save_and_load_active_round_trip(
        self,
        store: NegotiationStateStore,
        sample_campaign: Campaign,
        sample_cpm_tracker: CampaignCPMTracker,
    ) -> None:
        """A saved negotiation should be fully recoverable via load_active."""
        sm = NegotiationStateMachine()
        sm.trigger("send_offer")  # -> AWAITING_REPLY

        context = {
            "influencer_name": "Test Influencer",
            "next_cpm": Decimal("25.50"),
            "tags": ["instagram", "reel"],
        }
        serialized_context = serialize_context(context)
        context_for_save = json.loads(serialized_context)

        cpm_data = serialize_cpm_tracker(sample_cpm_tracker)

        store.save(
            thread_id="thread-001",
            state_machine=sm,
            context=context_for_save,
            campaign=sample_campaign,
            cpm_tracker_data=cpm_data,
            round_count=1,
        )

        rows = store.load_active()
        assert len(rows) == 1

        row = rows[0]
        assert row["thread_id"] == "thread-001"
        assert row["state"] == "awaiting_reply"
        assert row["round_count"] == 1

        # Context round-trip
        loaded_context = json.loads(row["context_json"])
        assert loaded_context["influencer_name"] == "Test Influencer"
        assert loaded_context["next_cpm"] == "25.50"
        assert loaded_context["tags"] == ["instagram", "reel"]

        # Campaign round-trip
        loaded_campaign = Campaign.model_validate_json(row["campaign_json"])
        assert loaded_campaign.campaign_id == "camp-001"
        assert loaded_campaign.budget == Decimal("10000")

        # CPM tracker round-trip
        loaded_cpm_data = json.loads(row["cpm_tracker_json"])
        loaded_tracker = CampaignCPMTracker.from_dict(loaded_cpm_data)
        assert loaded_tracker.campaign_id == "camp-001"
        assert loaded_tracker.target_min_cpm == Decimal("20")
        assert len(loaded_tracker._agreements) == 1

        # History round-trip
        loaded_history = json.loads(row["history_json"])
        assert len(loaded_history) == 1
        assert loaded_history[0] == ["initial_offer", "send_offer", "awaiting_reply"]


class TestSaveOverwrite:
    """Tests for INSERT OR REPLACE with created_at preservation."""

    def test_save_overwrites_existing_preserves_created_at(
        self,
        store: NegotiationStateStore,
        conn: sqlite3.Connection,
        sample_campaign: Campaign,
        sample_cpm_tracker: CampaignCPMTracker,
    ) -> None:
        """Second save should update state and updated_at but keep created_at."""
        sm = NegotiationStateMachine()
        sm.trigger("send_offer")
        cpm_data = serialize_cpm_tracker(sample_cpm_tracker)

        store.save(
            thread_id="thread-002",
            state_machine=sm,
            context={"round": 1},
            campaign=sample_campaign,
            cpm_tracker_data=cpm_data,
            round_count=1,
        )

        # Read the original created_at
        conn.row_factory = sqlite3.Row
        original = dict(
            conn.execute(
                "SELECT created_at, updated_at FROM negotiation_state WHERE thread_id = ?",
                ("thread-002",),
            ).fetchone()
        )
        conn.row_factory = None

        # Small delay to ensure different updated_at
        time.sleep(0.05)

        # Update: trigger another event
        sm.trigger("receive_reply")
        store.save(
            thread_id="thread-002",
            state_machine=sm,
            context={"round": 2},
            campaign=sample_campaign,
            cpm_tracker_data=cpm_data,
            round_count=2,
        )

        conn.row_factory = sqlite3.Row
        updated = dict(
            conn.execute(
                "SELECT state, created_at, updated_at, round_count"
                " FROM negotiation_state WHERE thread_id = ?",
                ("thread-002",),
            ).fetchone()
        )
        conn.row_factory = None

        assert updated["state"] == "counter_received"
        assert updated["round_count"] == 2
        assert updated["created_at"] == original["created_at"]
        assert updated["updated_at"] >= original["updated_at"]


class TestLoadActiveFiltering:
    """Tests for terminal state exclusion."""

    def test_load_active_excludes_terminal_states(
        self,
        store: NegotiationStateStore,
        sample_campaign: Campaign,
        sample_cpm_tracker: CampaignCPMTracker,
    ) -> None:
        """load_active should only return non-terminal negotiations."""
        cpm_data = serialize_cpm_tracker(sample_cpm_tracker)

        # AWAITING_REPLY (active)
        sm_active = NegotiationStateMachine()
        sm_active.trigger("send_offer")
        store.save("t-active", sm_active, {}, sample_campaign, cpm_data, 1)

        # AGREED (terminal)
        sm_agreed = NegotiationStateMachine()
        sm_agreed.trigger("send_offer")
        sm_agreed.trigger("receive_reply")
        sm_agreed.trigger("accept")
        store.save("t-agreed", sm_agreed, {}, sample_campaign, cpm_data, 3)

        # REJECTED (terminal)
        sm_rejected = NegotiationStateMachine()
        sm_rejected.trigger("send_offer")
        sm_rejected.trigger("receive_reply")
        sm_rejected.trigger("reject")
        store.save("t-rejected", sm_rejected, {}, sample_campaign, cpm_data, 3)

        rows = store.load_active()
        thread_ids = {r["thread_id"] for r in rows}
        assert thread_ids == {"t-active"}


class TestDelete:
    """Tests for row deletion."""

    def test_delete_removes_row(
        self,
        store: NegotiationStateStore,
        sample_campaign: Campaign,
        sample_cpm_tracker: CampaignCPMTracker,
    ) -> None:
        """delete should remove the row, leaving load_active empty."""
        sm = NegotiationStateMachine()
        sm.trigger("send_offer")
        cpm_data = serialize_cpm_tracker(sample_cpm_tracker)

        store.save("t-del", sm, {}, sample_campaign, cpm_data, 1)
        assert len(store.load_active()) == 1

        store.delete("t-del")
        assert len(store.load_active()) == 0


class TestInitIdempotent:
    """Tests for schema initialization idempotency."""

    def test_init_table_is_idempotent(self) -> None:
        """Calling init_negotiation_state_table twice should not raise."""
        conn = sqlite3.connect(":memory:")
        init_negotiation_state_table(conn)
        init_negotiation_state_table(conn)  # second call -- no error
        conn.close()
