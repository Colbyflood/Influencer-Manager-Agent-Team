"""Integration tests for the SlackDispatcher dispatch pipeline.

Tests the full Phase 4 flow: pre-check gates (human takeover, triggers),
escalation dispatch with Block Kit messages, agreement dispatch with
deal summary, and handle_negotiation_result routing.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from negotiation.llm.models import (
    AgreementPayload,
    EscalationPayload,
    IntentClassification,
    NegotiationIntent,
)
from negotiation.slack.dispatcher import SlackDispatcher
from negotiation.slack.takeover import ThreadStateManager
from negotiation.slack.triggers import (
    EscalationTriggersConfig,
    TriggerConfig,
    TriggerResult,
    TriggerType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_notifier() -> MagicMock:
    """Mock SlackNotifier with post_escalation/post_agreement returning ts."""
    notifier = MagicMock()
    notifier.post_escalation.return_value = "esc_ts_123"
    notifier.post_agreement.return_value = "agr_ts_456"
    return notifier


@pytest.fixture()
def thread_state() -> ThreadStateManager:
    """Real ThreadStateManager instance."""
    return ThreadStateManager()


@pytest.fixture()
def triggers_config() -> EscalationTriggersConfig:
    """Default EscalationTriggersConfig."""
    return EscalationTriggersConfig()


@pytest.fixture()
def dispatcher(
    mock_notifier: MagicMock,
    thread_state: ThreadStateManager,
    triggers_config: EscalationTriggersConfig,
) -> SlackDispatcher:
    """SlackDispatcher with mock notifier and real state/config."""
    return SlackDispatcher(
        notifier=mock_notifier,
        thread_state_manager=thread_state,
        triggers_config=triggers_config,
        agent_email="agent@company.com",
    )


@pytest.fixture()
def negotiation_context() -> dict:
    """Standard negotiation context dict."""
    return {
        "influencer_name": "Jane Doe",
        "influencer_email": "jane@influencer.com",
        "client_name": "Acme Corp",
        "thread_id": "thread_abc123",
        "platform": "instagram",
        "average_views": 100000,
        "deliverables_summary": "2 Reels + 3 Stories",
        "deliverable_types": ["instagram_reel", "instagram_story"],
        "next_cpm": Decimal("15.00"),
    }


# ---------------------------------------------------------------------------
# Helper: build mock Gmail service
# ---------------------------------------------------------------------------


def _mock_gmail_service(from_headers: list[str]) -> MagicMock:
    """Create a mock Gmail service returning a thread with the given From headers."""
    messages = []
    for from_value in from_headers:
        messages.append(
            {
                "payload": {
                    "headers": [{"name": "From", "value": from_value}],
                },
            }
        )

    thread_response = {"messages": messages}

    service = MagicMock()
    (
        service.users()
        .threads()
        .get(
            userId="me",
            id="thread_abc123",
            format="metadata",
            metadataHeaders=["From"],
        )
        .execute.return_value
    ) = thread_response

    return service


# ---------------------------------------------------------------------------
# pre_check tests
# ---------------------------------------------------------------------------


class TestPreCheck:
    """Tests for SlackDispatcher.pre_check."""

    def test_returns_skip_when_thread_is_human_managed(
        self,
        dispatcher: SlackDispatcher,
        thread_state: ThreadStateManager,
    ) -> None:
        """Human-managed threads are silently skipped."""
        thread_state.claim_thread("thread_abc123", "U_HUMAN")
        gmail = _mock_gmail_service(["agent@company.com", "jane@influencer.com"])

        result = dispatcher.pre_check(
            email_body="Hi there",
            thread_id="thread_abc123",
            influencer_email="jane@influencer.com",
            proposed_cpm=10.0,
            intent_confidence=0.9,
            gmail_service=gmail,
            anthropic_client=None,
        )

        assert result is not None
        assert result["action"] == "skip"
        assert "human-managed" in result["reason"]

    def test_returns_skip_when_human_reply_detected(
        self,
        dispatcher: SlackDispatcher,
    ) -> None:
        """Human reply in Gmail thread triggers auto-claim and skip."""
        gmail = _mock_gmail_service(
            [
                "agent@company.com",
                "jane@influencer.com",
                "Manager Name <boss@company.com>",
            ]
        )

        result = dispatcher.pre_check(
            email_body="Hi there",
            thread_id="thread_abc123",
            influencer_email="jane@influencer.com",
            proposed_cpm=10.0,
            intent_confidence=0.9,
            gmail_service=gmail,
            anthropic_client=None,
        )

        assert result is not None
        assert result["action"] == "skip"
        assert "Human reply detected" in result["reason"]

    def test_auto_claims_thread_when_human_reply_detected(
        self,
        dispatcher: SlackDispatcher,
        thread_state: ThreadStateManager,
    ) -> None:
        """Detecting a human reply auto-claims the thread."""
        gmail = _mock_gmail_service(["agent@company.com", "boss@company.com"])

        dispatcher.pre_check(
            email_body="Hi",
            thread_id="thread_abc123",
            influencer_email="jane@influencer.com",
            proposed_cpm=10.0,
            intent_confidence=0.9,
            gmail_service=gmail,
            anthropic_client=None,
        )

        assert thread_state.is_human_managed("thread_abc123")

    def test_returns_escalate_when_cpm_trigger_fires(
        self,
        dispatcher: SlackDispatcher,
    ) -> None:
        """CPM over threshold triggers escalation."""
        gmail = _mock_gmail_service(["agent@company.com", "jane@influencer.com"])

        result = dispatcher.pre_check(
            email_body="I want $5000 for this",
            thread_id="thread_abc123",
            influencer_email="jane@influencer.com",
            proposed_cpm=35.0,  # Over 30.0 threshold
            intent_confidence=0.9,
            gmail_service=gmail,
            anthropic_client=None,
        )

        assert result is not None
        assert result["action"] == "escalate"
        assert len(result["triggers"]) > 0
        assert "CPM" in result["reason"]

    def test_returns_none_when_no_gates_fire(
        self,
        dispatcher: SlackDispatcher,
    ) -> None:
        """No gates fired -- returns None to proceed with negotiation."""
        gmail = _mock_gmail_service(["agent@company.com", "jane@influencer.com"])

        result = dispatcher.pre_check(
            email_body="Hi there",
            thread_id="thread_abc123",
            influencer_email="jane@influencer.com",
            proposed_cpm=10.0,
            intent_confidence=0.9,
            gmail_service=gmail,
            anthropic_client=None,
        )

        assert result is None

    def test_skips_llm_triggers_when_all_disabled(
        self,
        mock_notifier: MagicMock,
        thread_state: ThreadStateManager,
    ) -> None:
        """All 3 LLM triggers disabled -- no LLM call needed."""
        config = EscalationTriggersConfig(
            hostile_tone=TriggerConfig(enabled=False),
            legal_language=TriggerConfig(enabled=False),
            unusual_deliverables=TriggerConfig(enabled=False),
        )
        disp = SlackDispatcher(
            notifier=mock_notifier,
            thread_state_manager=thread_state,
            triggers_config=config,
            agent_email="agent@company.com",
        )
        gmail = _mock_gmail_service(["agent@company.com", "jane@influencer.com"])

        # Pass None as anthropic_client -- should not error
        result = disp.pre_check(
            email_body="Hi there",
            thread_id="thread_abc123",
            influencer_email="jane@influencer.com",
            proposed_cpm=10.0,
            intent_confidence=0.9,
            gmail_service=gmail,
            anthropic_client=None,
        )

        assert result is None


# ---------------------------------------------------------------------------
# dispatch_escalation tests
# ---------------------------------------------------------------------------


class TestDispatchEscalation:
    """Tests for SlackDispatcher.dispatch_escalation."""

    def test_posts_to_escalation_channel(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
    ) -> None:
        """Escalation payload is posted via notifier."""
        payload = EscalationPayload(
            reason="CPM too high",
            email_draft="Draft email...",
            influencer_name="Jane Doe",
            thread_id="thread_abc123",
            influencer_email="jane@influencer.com",
            client_name="Acme Corp",
            evidence_quote="I want $5000",
            proposed_rate=Decimal("5000"),
            our_rate=Decimal("2000"),
            suggested_actions=["Reply with counter", "Approve rate"],
        )

        ts = dispatcher.dispatch_escalation(payload)

        mock_notifier.post_escalation.assert_called_once()
        assert ts == "esc_ts_123"

    def test_includes_all_required_fields_in_blocks(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
    ) -> None:
        """Block Kit blocks include all required fields."""
        payload = EscalationPayload(
            reason="CPM too high",
            email_draft="",
            influencer_name="Jane Doe",
            thread_id="thread_abc123",
            influencer_email="jane@influencer.com",
            client_name="Acme Corp",
            evidence_quote="I need $5000",
            proposed_rate=Decimal("5000"),
            our_rate=Decimal("2000"),
            suggested_actions=["Counter at $3000"],
        )

        dispatcher.dispatch_escalation(payload)

        blocks = mock_notifier.post_escalation.call_args[0][0]
        blocks_str = str(blocks)

        assert "Jane Doe" in blocks_str
        assert "jane@influencer.com" in blocks_str
        assert "Acme Corp" in blocks_str
        assert "CPM too high" in blocks_str
        assert "I need $5000" in blocks_str
        assert "5000" in blocks_str
        assert "2000" in blocks_str
        assert "Counter at $3000" in blocks_str

    def test_constructs_gmail_permalink(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
    ) -> None:
        """Details link is a Gmail thread permalink."""
        payload = EscalationPayload(
            reason="Test",
            email_draft="",
            influencer_name="Jane",
            thread_id="thread_xyz",
        )

        dispatcher.dispatch_escalation(payload)

        blocks = mock_notifier.post_escalation.call_args[0][0]
        blocks_str = str(blocks)
        assert "mail.google.com/mail/u/0/#inbox/thread_xyz" in blocks_str

    def test_returns_message_timestamp(
        self,
        dispatcher: SlackDispatcher,
    ) -> None:
        """dispatch_escalation returns the Slack message ts."""
        payload = EscalationPayload(
            reason="Test",
            email_draft="",
            influencer_name="Jane",
            thread_id="thread_1",
        )

        ts = dispatcher.dispatch_escalation(payload)
        assert ts == "esc_ts_123"


# ---------------------------------------------------------------------------
# dispatch_agreement tests
# ---------------------------------------------------------------------------


class TestDispatchAgreement:
    """Tests for SlackDispatcher.dispatch_agreement."""

    def test_posts_to_agreement_channel(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
    ) -> None:
        """Agreement payload is posted via notifier."""
        payload = AgreementPayload(
            influencer_name="Jane Doe",
            influencer_email="jane@influencer.com",
            client_name="Acme Corp",
            agreed_rate=Decimal("1500"),
            platform="instagram",
            deliverables="2 Reels + 3 Stories",
            cpm_achieved=Decimal("15.00"),
            thread_id="thread_abc123",
            next_steps=["Send contract"],
        )

        ts = dispatcher.dispatch_agreement(payload)

        mock_notifier.post_agreement.assert_called_once()
        assert ts == "agr_ts_456"

    def test_includes_all_required_fields(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
    ) -> None:
        """Block Kit blocks include all required agreement fields."""
        payload = AgreementPayload(
            influencer_name="Jane Doe",
            influencer_email="jane@influencer.com",
            client_name="Acme Corp",
            agreed_rate=Decimal("1500"),
            platform="instagram",
            deliverables="2 Reels + 3 Stories",
            cpm_achieved=Decimal("15.00"),
            thread_id="thread_abc123",
            next_steps=["Send contract", "Confirm deliverables"],
        )

        dispatcher.dispatch_agreement(payload)

        blocks = mock_notifier.post_agreement.call_args[0][0]
        blocks_str = str(blocks)

        assert "Jane Doe" in blocks_str
        assert "jane@influencer.com" in blocks_str
        assert "Acme Corp" in blocks_str
        assert "1,500.00" in blocks_str
        assert "Instagram" in blocks_str
        assert "2 Reels + 3 Stories" in blocks_str
        assert "15.00" in blocks_str
        assert "Send contract" in blocks_str
        assert "Confirm deliverables" in blocks_str

    def test_includes_mentions_when_provided(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
    ) -> None:
        """Agreement blocks include @ mentions when mention_users provided."""
        payload = AgreementPayload(
            influencer_name="Jane",
            influencer_email="jane@test.com",
            client_name="Acme",
            agreed_rate=Decimal("1000"),
            platform="tiktok",
            deliverables="1 Video",
            cpm_achieved=Decimal("10.00"),
            thread_id="thread_1",
            mention_users=["U123", "U456"],
        )

        dispatcher.dispatch_agreement(payload)

        blocks = mock_notifier.post_agreement.call_args[0][0]
        blocks_str = str(blocks)
        assert "<@U123>" in blocks_str
        assert "<@U456>" in blocks_str

    def test_returns_message_timestamp(
        self,
        dispatcher: SlackDispatcher,
    ) -> None:
        """dispatch_agreement returns the Slack message ts."""
        payload = AgreementPayload(
            influencer_name="Jane",
            influencer_email="jane@test.com",
            client_name="Acme",
            agreed_rate=Decimal("1000"),
            platform="tiktok",
            deliverables="1 Video",
            cpm_achieved=Decimal("10.00"),
            thread_id="thread_1",
        )

        ts = dispatcher.dispatch_agreement(payload)
        assert ts == "agr_ts_456"


# ---------------------------------------------------------------------------
# handle_negotiation_result tests
# ---------------------------------------------------------------------------


class TestHandleNegotiationResult:
    """Tests for SlackDispatcher.handle_negotiation_result."""

    def test_escalation_dispatches_to_slack(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
        negotiation_context: dict,
    ) -> None:
        """Escalation result dispatches to Slack and adds slack_ts."""
        result = {
            "action": "escalate",
            "reason": "CPM $35.00 exceeds threshold $30.00",
            "triggers": [
                TriggerResult(
                    trigger_type=TriggerType.CPM_OVER_THRESHOLD,
                    fired=True,
                    reason="CPM $35.00 exceeds threshold $30.00",
                )
            ],
        }

        enriched = dispatcher.handle_negotiation_result(result, negotiation_context)

        mock_notifier.post_escalation.assert_called_once()
        assert "slack_ts" in enriched
        assert enriched["slack_ts"] == "esc_ts_123"

    def test_accept_dispatches_agreement_to_slack(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
        negotiation_context: dict,
    ) -> None:
        """Accept result dispatches agreement to Slack and adds slack_ts."""
        classification = IntentClassification(
            intent=NegotiationIntent.ACCEPT,
            confidence=0.95,
            proposed_rate="1500.00",
            summary="Influencer accepts the rate",
        )
        result = {
            "action": "accept",
            "classification": classification,
        }

        enriched = dispatcher.handle_negotiation_result(result, negotiation_context)

        mock_notifier.post_agreement.assert_called_once()
        assert "slack_ts" in enriched
        assert enriched["slack_ts"] == "agr_ts_456"

    def test_send_result_passes_through(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
        negotiation_context: dict,
    ) -> None:
        """Send result passes through without Slack dispatch."""
        result = {
            "action": "send",
            "email_body": "Counter offer...",
        }

        enriched = dispatcher.handle_negotiation_result(result, negotiation_context)

        mock_notifier.post_escalation.assert_not_called()
        mock_notifier.post_agreement.assert_not_called()
        assert "slack_ts" not in enriched

    def test_reject_result_passes_through(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
        negotiation_context: dict,
    ) -> None:
        """Reject result passes through without Slack dispatch."""
        result = {
            "action": "reject",
            "classification": IntentClassification(
                intent=NegotiationIntent.REJECT,
                confidence=0.9,
                summary="Influencer declines",
            ),
        }

        enriched = dispatcher.handle_negotiation_result(result, negotiation_context)

        mock_notifier.post_escalation.assert_not_called()
        mock_notifier.post_agreement.assert_not_called()
        assert "slack_ts" not in enriched

    def test_escalation_payload_includes_phase4_fields(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
        negotiation_context: dict,
    ) -> None:
        """Escalation payload includes Phase 4 fields from context."""
        result = {
            "action": "escalate",
            "reason": "CPM $35.00 exceeds threshold $30.00",
            "triggers": [
                TriggerResult(
                    trigger_type=TriggerType.CPM_OVER_THRESHOLD,
                    fired=True,
                    reason="CPM $35.00 exceeds threshold $30.00",
                )
            ],
        }

        dispatcher.handle_negotiation_result(result, negotiation_context)

        # Verify the blocks posted contain Phase 4 fields
        blocks = mock_notifier.post_escalation.call_args[0][0]
        blocks_str = str(blocks)
        assert "jane@influencer.com" in blocks_str
        assert "Acme Corp" in blocks_str
        assert "cpm_over_threshold" in blocks_str or "CPM" in blocks_str

    def test_agreement_has_default_next_steps(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
        negotiation_context: dict,
    ) -> None:
        """Agreement payload uses default next_steps if not in context."""
        classification = IntentClassification(
            intent=NegotiationIntent.ACCEPT,
            confidence=0.95,
            proposed_rate="1500.00",
            summary="Deal accepted",
        )
        result = {"action": "accept", "classification": classification}

        dispatcher.handle_negotiation_result(result, negotiation_context)

        blocks = mock_notifier.post_agreement.call_args[0][0]
        blocks_str = str(blocks)
        assert "Send contract" in blocks_str
        assert "Confirm deliverables" in blocks_str
        assert "Schedule content calendar" in blocks_str

    def test_agreement_calculates_cpm(
        self,
        dispatcher: SlackDispatcher,
        mock_notifier: MagicMock,
        negotiation_context: dict,
    ) -> None:
        """Agreement payload calculates CPM from agreed_rate / average_views."""
        classification = IntentClassification(
            intent=NegotiationIntent.ACCEPT,
            confidence=0.95,
            proposed_rate="1500.00",
            summary="Deal",
        )
        result = {"action": "accept", "classification": classification}

        dispatcher.handle_negotiation_result(result, negotiation_context)

        blocks = mock_notifier.post_agreement.call_args[0][0]
        blocks_str = str(blocks)
        # CPM = 1500 / 100000 * 1000 = 15.00
        assert "15.00" in blocks_str
