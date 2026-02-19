"""Integration tests for Phase 6 runtime orchestration wiring.

Tests verify the two E2E flows that were broken before Phase 6:
1. Inbound Email -> Negotiation Loop (MISSING-01, MISSING-02)
2. Campaign Ingestion -> Negotiation Start (MISSING-04)

Plus SlackDispatcher wiring (MISSING-03) and audit trail activation.

All external services (Gmail, Slack, Anthropic) are mocked.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import MagicMock, patch

from negotiation.app import (
    build_negotiation_context,
    process_inbound_email,
    start_negotiations_for_campaign,
)
from negotiation.campaign.cpm_tracker import CPMFlexibility
from negotiation.email.models import InboundEmail

# ---------------------------------------------------------------------------
# Helpers to build mock objects matching expected shapes
# ---------------------------------------------------------------------------


def _make_mock_influencer_row(
    *,
    platform: str = "YouTube",
    average_views: int = 50000,
    email: str = "influencer@example.com",
    engagement_rate: float = 4.5,
) -> MagicMock:
    """Build a mock InfluencerRow with the fields used by orchestration code."""
    row = MagicMock()
    row.platform = platform
    row.average_views = average_views
    row.email = email
    row.engagement_rate = engagement_rate
    return row


def _make_mock_campaign(
    *,
    campaign_id: str = "CAMP-001",
    client_name: str = "TestBrand",
    target_deliverables: str = "1 YouTube video",
    platform: str = "YouTube",
    min_cpm: Decimal = Decimal("15"),
    max_cpm: Decimal = Decimal("30"),
) -> MagicMock:
    """Build a mock Campaign with cpm_range sub-object."""
    campaign = MagicMock()
    campaign.campaign_id = campaign_id
    campaign.client_name = client_name
    campaign.target_deliverables = target_deliverables
    campaign.platform = platform
    campaign.cpm_range = MagicMock()
    campaign.cpm_range.min_cpm = min_cpm
    campaign.cpm_range.max_cpm = max_cpm
    return campaign


def _make_inbound_email(
    *,
    thread_id: str = "thread_abc",
    from_email: str = "influencer@example.com",
    body_text: str = "I can do it for $500.",
) -> InboundEmail:
    """Build a real InboundEmail instance for test use."""
    return InboundEmail(
        gmail_message_id="msg_123",
        thread_id=thread_id,
        message_id_header="<msg123@mail.gmail.com>",
        from_email=from_email,
        subject="Re: Collaboration",
        body_text=body_text,
        received_at="2026-02-19T10:00:00Z",
    )


def _base_services(
    *,
    gmail_client: MagicMock | None = None,
    slack_dispatcher: MagicMock | None = None,
    anthropic_client: MagicMock | None = None,
    audited_process_reply: MagicMock | None = None,
    negotiation_states: dict | None = None,
    audit_logger: MagicMock | None = None,
) -> dict:
    """Build a services dict with sensible defaults."""
    return {
        "gmail_client": gmail_client,
        "slack_dispatcher": slack_dispatcher,
        "anthropic_client": anthropic_client,
        "audited_process_reply": audited_process_reply,
        "negotiation_states": negotiation_states if negotiation_states is not None else {},
        "audit_logger": audit_logger or MagicMock(),
        "history_lock": asyncio.Lock(),
        "history_id": "",
        "background_tasks": set(),
    }


# ===========================================================================
# Tests for build_negotiation_context
# ===========================================================================


class TestBuildNegotiationContext:
    """Tests for context dict assembly used by process_influencer_reply."""

    def test_assembles_correct_keys(self) -> None:
        """Context dict has all required keys for negotiation loop."""
        sheet_data = _make_mock_influencer_row()
        campaign = _make_mock_campaign()

        context = build_negotiation_context(
            influencer_name="Jane",
            influencer_email="jane@example.com",
            sheet_data=sheet_data,
            campaign=campaign,
            thread_id="thread_xyz",
        )

        expected_keys = {
            "influencer_name",
            "influencer_email",
            "thread_id",
            "platform",
            "average_views",
            "deliverables_summary",
            "deliverable_types",
            "next_cpm",
            "client_name",
            "campaign_id",
            "history",
        }
        assert set(context.keys()) == expected_keys
        assert context["influencer_name"] == "Jane"
        assert context["influencer_email"] == "jane@example.com"
        assert context["thread_id"] == "thread_xyz"
        assert context["average_views"] == 50000
        assert context["client_name"] == "TestBrand"
        assert context["campaign_id"] == "CAMP-001"
        assert context["history"] == ""

    def test_uses_cpm_tracker_flexibility(self) -> None:
        """When a CPMTracker is provided, next_cpm comes from flexibility."""
        sheet_data = _make_mock_influencer_row()
        campaign = _make_mock_campaign()

        mock_tracker = MagicMock()
        mock_tracker.get_flexibility.return_value = CPMFlexibility(
            target_cpm=Decimal("25"),
            max_allowed_cpm=Decimal("30"),
            reason="test",
        )

        context = build_negotiation_context(
            influencer_name="Jane",
            influencer_email="jane@example.com",
            sheet_data=sheet_data,
            campaign=campaign,
            thread_id="thread_xyz",
            cpm_tracker=mock_tracker,
        )

        assert context["next_cpm"] == Decimal("25")
        mock_tracker.get_flexibility.assert_called_once_with(
            influencer_engagement_rate=4.5,
        )

    def test_defaults_to_campaign_min_cpm_without_tracker(self) -> None:
        """Without a CPMTracker, next_cpm falls back to campaign cpm_range.min_cpm."""
        sheet_data = _make_mock_influencer_row()
        campaign = _make_mock_campaign(min_cpm=Decimal("12"))

        context = build_negotiation_context(
            influencer_name="Jane",
            influencer_email="jane@example.com",
            sheet_data=sheet_data,
            campaign=campaign,
            thread_id="thread_xyz",
        )

        assert context["next_cpm"] == Decimal("12")


# ===========================================================================
# Tests for process_inbound_email
# ===========================================================================


class TestProcessInboundEmail:
    """Tests for the full inbound email processing pipeline."""

    def test_full_pipeline(self) -> None:
        """Full pipeline: get_message -> pre_check -> process_reply -> send_reply."""
        inbound = _make_inbound_email()

        mock_gmail = MagicMock()
        mock_gmail.get_message.return_value = inbound
        mock_gmail.send_reply.return_value = {"id": "reply_1"}
        mock_gmail._service = MagicMock()

        mock_dispatcher = MagicMock()
        mock_dispatcher.pre_check.return_value = None  # proceed
        mock_dispatcher.handle_negotiation_result.side_effect = lambda r, c: r

        mock_process = MagicMock(return_value={
            "action": "send",
            "email_body": "Here is our counter offer.",
        })

        mock_anthropic = MagicMock()

        state_machine = MagicMock()
        negotiation_states = {
            "thread_abc": {
                "state_machine": state_machine,
                "context": {"influencer_name": "Jane"},
                "round_count": 0,
            }
        }

        services = _base_services(
            gmail_client=mock_gmail,
            slack_dispatcher=mock_dispatcher,
            anthropic_client=mock_anthropic,
            audited_process_reply=mock_process,
            negotiation_states=negotiation_states,
        )

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("negotiation.app.asyncio.to_thread", side_effect=mock_to_thread):
            asyncio.run(process_inbound_email("msg_123", services))

        mock_gmail.get_message.assert_called_once_with("msg_123")
        mock_dispatcher.pre_check.assert_called_once()
        mock_process.assert_called_once()
        mock_gmail.send_reply.assert_called_once_with(
            "thread_abc", "Here is our counter offer."
        )
        assert negotiation_states["thread_abc"]["round_count"] == 1

    def test_skips_unknown_thread(self) -> None:
        """Unknown thread_id: get_message called but pipeline stops."""
        inbound = _make_inbound_email(thread_id="thread_unknown")

        mock_gmail = MagicMock()
        mock_gmail.get_message.return_value = inbound
        mock_gmail._service = MagicMock()

        mock_process = MagicMock()

        services = _base_services(
            gmail_client=mock_gmail,
            anthropic_client=MagicMock(),
            audited_process_reply=mock_process,
            negotiation_states={},
        )

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("negotiation.app.asyncio.to_thread", side_effect=mock_to_thread):
            asyncio.run(process_inbound_email("msg_123", services))

        mock_gmail.get_message.assert_called_once_with("msg_123")
        mock_process.assert_not_called()

    def test_stops_on_precheck_gate(self) -> None:
        """Pre-check gate fires: process_reply is NOT called."""
        inbound = _make_inbound_email()

        mock_gmail = MagicMock()
        mock_gmail.get_message.return_value = inbound
        mock_gmail._service = MagicMock()

        mock_dispatcher = MagicMock()
        mock_dispatcher.pre_check.return_value = {
            "action": "skip",
            "reason": "human-managed",
        }

        mock_process = MagicMock()
        mock_anthropic = MagicMock()

        state_machine = MagicMock()
        negotiation_states = {
            "thread_abc": {
                "state_machine": state_machine,
                "context": {"influencer_name": "Jane"},
                "round_count": 0,
            }
        }

        services = _base_services(
            gmail_client=mock_gmail,
            slack_dispatcher=mock_dispatcher,
            anthropic_client=mock_anthropic,
            audited_process_reply=mock_process,
            negotiation_states=negotiation_states,
        )

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("negotiation.app.asyncio.to_thread", side_effect=mock_to_thread):
            asyncio.run(process_inbound_email("msg_123", services))

        mock_dispatcher.pre_check.assert_called_once()
        mock_process.assert_not_called()
        mock_gmail.send_reply.assert_not_called()

    def test_process_inbound_email_passes_real_cpm_to_pre_check(self) -> None:
        """pre_check receives proposed_cpm from context.next_cpm, not hardcoded 0.0."""
        inbound = _make_inbound_email()

        mock_gmail = MagicMock()
        mock_gmail.get_message.return_value = inbound
        mock_gmail._service = MagicMock()

        mock_dispatcher = MagicMock()
        mock_dispatcher.pre_check.return_value = None  # proceed
        mock_dispatcher.handle_negotiation_result.side_effect = lambda r, c: r

        mock_process = MagicMock(return_value={
            "action": "send",
            "email_body": "Counter offer.",
        })

        mock_anthropic = MagicMock()

        state_machine = MagicMock()
        negotiation_states = {
            "thread_abc": {
                "state_machine": state_machine,
                "context": {
                    "influencer_name": "Jane",
                    "next_cpm": Decimal("25.50"),
                    "campaign_id": "CAMP-001",
                },
                "round_count": 0,
            }
        }

        services = _base_services(
            gmail_client=mock_gmail,
            slack_dispatcher=mock_dispatcher,
            anthropic_client=mock_anthropic,
            audited_process_reply=mock_process,
            negotiation_states=negotiation_states,
        )

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("negotiation.app.asyncio.to_thread", side_effect=mock_to_thread):
            asyncio.run(process_inbound_email("msg_123", services))

        mock_dispatcher.pre_check.assert_called_once()
        call_kwargs = mock_dispatcher.pre_check.call_args[1]
        assert call_kwargs["proposed_cpm"] == 25.5
        assert isinstance(call_kwargs["proposed_cpm"], float)

    def test_process_inbound_email_logs_received_email_to_audit(self) -> None:
        """Inbound emails are logged via audit_logger.log_email_received."""
        inbound = _make_inbound_email()

        mock_gmail = MagicMock()
        mock_gmail.get_message.return_value = inbound
        mock_gmail._service = MagicMock()

        mock_dispatcher = MagicMock()
        mock_dispatcher.pre_check.return_value = None
        mock_dispatcher.handle_negotiation_result.side_effect = lambda r, c: r

        mock_process = MagicMock(return_value={
            "action": "send",
            "email_body": "Counter offer.",
        })

        mock_anthropic = MagicMock()
        mock_audit = MagicMock()

        state_machine = MagicMock()
        negotiation_states = {
            "thread_abc": {
                "state_machine": state_machine,
                "context": {
                    "influencer_name": "Jane",
                    "campaign_id": "CAMP-001",
                    "negotiation_state": "counter_received",
                    "next_cpm": Decimal("20"),
                },
                "round_count": 1,
            }
        }

        services = _base_services(
            gmail_client=mock_gmail,
            slack_dispatcher=mock_dispatcher,
            anthropic_client=mock_anthropic,
            audited_process_reply=mock_process,
            negotiation_states=negotiation_states,
            audit_logger=mock_audit,
        )

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("negotiation.app.asyncio.to_thread", side_effect=mock_to_thread):
            asyncio.run(process_inbound_email("msg_123", services))

        mock_audit.log_email_received.assert_called_once_with(
            campaign_id="CAMP-001",
            influencer_name="Jane",
            thread_id="thread_abc",
            email_body="I can do it for $500.",
            negotiation_state="counter_received",
            intent_classification=None,
        )

    def test_process_inbound_email_no_audit_logger_no_crash(self) -> None:
        """When audit_logger is not in services, processing continues without error."""
        inbound = _make_inbound_email()

        mock_gmail = MagicMock()
        mock_gmail.get_message.return_value = inbound
        mock_gmail._service = MagicMock()

        mock_dispatcher = MagicMock()
        mock_dispatcher.pre_check.return_value = None
        mock_dispatcher.handle_negotiation_result.side_effect = lambda r, c: r

        mock_process = MagicMock(return_value={
            "action": "send",
            "email_body": "Counter offer.",
        })

        mock_anthropic = MagicMock()

        state_machine = MagicMock()
        negotiation_states = {
            "thread_abc": {
                "state_machine": state_machine,
                "context": {
                    "influencer_name": "Jane",
                    "next_cpm": Decimal("20"),
                },
                "round_count": 0,
            }
        }

        services = _base_services(
            gmail_client=mock_gmail,
            slack_dispatcher=mock_dispatcher,
            anthropic_client=mock_anthropic,
            audited_process_reply=mock_process,
            negotiation_states=negotiation_states,
        )
        # Remove audit_logger from services entirely
        services.pop("audit_logger", None)

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("negotiation.app.asyncio.to_thread", side_effect=mock_to_thread):
            asyncio.run(process_inbound_email("msg_123", services))

        # No crash -- function completed normally and sent the reply
        mock_gmail.send_reply.assert_called_once()

    def test_handles_escalation(self) -> None:
        """Escalation result: send_reply NOT called, handle_result IS called."""
        inbound = _make_inbound_email()

        mock_gmail = MagicMock()
        mock_gmail.get_message.return_value = inbound
        mock_gmail._service = MagicMock()

        mock_dispatcher = MagicMock()
        mock_dispatcher.pre_check.return_value = None
        mock_dispatcher.handle_negotiation_result.side_effect = lambda r, c: r

        mock_process = MagicMock(return_value={
            "action": "escalate",
            "reason": "high CPM",
        })

        mock_anthropic = MagicMock()

        state_machine = MagicMock()
        negotiation_states = {
            "thread_abc": {
                "state_machine": state_machine,
                "context": {"influencer_name": "Jane"},
                "round_count": 0,
            }
        }

        services = _base_services(
            gmail_client=mock_gmail,
            slack_dispatcher=mock_dispatcher,
            anthropic_client=mock_anthropic,
            audited_process_reply=mock_process,
            negotiation_states=negotiation_states,
        )

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("negotiation.app.asyncio.to_thread", side_effect=mock_to_thread):
            asyncio.run(process_inbound_email("msg_123", services))

        mock_gmail.send_reply.assert_not_called()
        mock_dispatcher.handle_negotiation_result.assert_called_once()
        # Round count unchanged for escalation
        assert negotiation_states["thread_abc"]["round_count"] == 0


# ===========================================================================
# Tests for start_negotiations_for_campaign
# ===========================================================================


class TestStartNegotiationsForCampaign:
    """Tests for campaign -> negotiation initiation flow."""

    def test_creates_state_entries(self) -> None:
        """Successful initiation: state entry created, email sent, audit logged."""
        mock_gmail = MagicMock()
        mock_gmail.send.return_value = {"threadId": "thread_123"}

        mock_anthropic = MagicMock()
        mock_audit = MagicMock()

        negotiation_states: dict = {}

        services = _base_services(
            gmail_client=mock_gmail,
            anthropic_client=mock_anthropic,
            audit_logger=mock_audit,
            negotiation_states=negotiation_states,
        )

        sheet_data = _make_mock_influencer_row()
        campaign = _make_mock_campaign()

        found_influencers = [
            {"name": "Jane Creator", "sheet_data": sheet_data},
        ]

        mock_composed = MagicMock()
        mock_composed.email_body = "Hello Jane, we'd love to work with you."

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with (
            patch("negotiation.app.asyncio.to_thread", side_effect=mock_to_thread),
            patch("negotiation.llm.composer.compose_counter_email", return_value=mock_composed),
            patch("negotiation.llm.knowledge_base.load_knowledge_base", return_value="kb content"),
            patch(
                "negotiation.pricing.calculate_initial_offer",
                return_value=Decimal("250"),
            ),
            patch("negotiation.app.NegotiationStateMachine") as mock_sm_cls,
        ):
            mock_sm_instance = MagicMock()
            mock_sm_cls.return_value = mock_sm_instance

            asyncio.run(start_negotiations_for_campaign(
                found_influencers=found_influencers,
                campaign=campaign,
                services=services,
            ))

        # State entry created with the thread_id from Gmail
        assert "thread_123" in negotiation_states
        state_entry = negotiation_states["thread_123"]
        assert state_entry["state_machine"] is mock_sm_instance
        assert state_entry["round_count"] == 0
        assert state_entry["context"]["influencer_name"] == "Jane Creator"

        # Gmail send was called
        mock_gmail.send.assert_called_once()

        # State machine triggered send_offer
        mock_sm_instance.trigger.assert_called_once_with("send_offer")

        # Audit logged
        mock_audit.log_email_sent.assert_called_once()

    def test_skips_without_gmail(self) -> None:
        """No GmailClient: negotiation_states stays empty."""
        negotiation_states: dict = {}

        services = _base_services(
            gmail_client=None,
            anthropic_client=MagicMock(),
            negotiation_states=negotiation_states,
        )

        campaign = _make_mock_campaign()

        asyncio.run(start_negotiations_for_campaign(
            found_influencers=[
                {"name": "Jane", "sheet_data": _make_mock_influencer_row()},
            ],
            campaign=campaign,
            services=services,
        ))

        assert negotiation_states == {}

    def test_skips_without_anthropic(self) -> None:
        """No Anthropic client: cannot compose emails, negotiation_states stays empty."""
        negotiation_states: dict = {}

        services = _base_services(
            gmail_client=MagicMock(),
            anthropic_client=None,
            negotiation_states=negotiation_states,
        )

        campaign = _make_mock_campaign()

        asyncio.run(start_negotiations_for_campaign(
            found_influencers=[
                {"name": "Jane", "sheet_data": _make_mock_influencer_row()},
            ],
            campaign=campaign,
            services=services,
        ))

        assert negotiation_states == {}

    def test_instantiates_cpm_tracker(self) -> None:
        """CampaignCPMTracker is created with campaign CPM range."""
        mock_gmail = MagicMock()
        mock_gmail.send.return_value = {"threadId": "thread_456"}

        mock_anthropic = MagicMock()
        negotiation_states: dict = {}

        services = _base_services(
            gmail_client=mock_gmail,
            anthropic_client=mock_anthropic,
            negotiation_states=negotiation_states,
        )

        sheet_data = _make_mock_influencer_row()
        campaign = _make_mock_campaign(
            min_cpm=Decimal("10"),
            max_cpm=Decimal("20"),
        )

        found_influencers = [
            {"name": "Jane", "sheet_data": sheet_data},
        ]

        mock_composed = MagicMock()
        mock_composed.email_body = "Hello"

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with (
            patch("negotiation.app.asyncio.to_thread", side_effect=mock_to_thread),
            patch("negotiation.llm.composer.compose_counter_email", return_value=mock_composed),
            patch("negotiation.llm.knowledge_base.load_knowledge_base", return_value="kb"),
            patch(
                "negotiation.pricing.calculate_initial_offer",
                return_value=Decimal("100"),
            ),
            patch("negotiation.state_machine.NegotiationStateMachine"),
            patch("negotiation.campaign.cpm_tracker.CampaignCPMTracker") as mock_tracker_cls,
        ):
            mock_tracker_instance = MagicMock()
            mock_tracker_cls.return_value = mock_tracker_instance

            asyncio.run(start_negotiations_for_campaign(
                found_influencers=found_influencers,
                campaign=campaign,
                services=services,
            ))

        mock_tracker_cls.assert_called_once_with(
            campaign_id="CAMP-001",
            target_min_cpm=Decimal("10"),
            target_max_cpm=Decimal("20"),
            total_influencers=1,
        )

        # Tracker is stored in the negotiation state entry
        state_entry = negotiation_states["thread_456"]
        assert state_entry["cpm_tracker"] is mock_tracker_instance
