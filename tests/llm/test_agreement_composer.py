"""Tests for agreement email composition using mocked Anthropic client.

Verifies that compose_agreement_email correctly builds prompts with knowledge base
content, passes all agreement parameters (terms, payment, next steps) to the LLM,
and returns a ComposedEmail with token usage tracking.
"""

from unittest.mock import MagicMock

from negotiation.llm.composer import compose_agreement_email
from negotiation.llm.models import ComposedEmail
from negotiation.llm.prompts import AGREEMENT_CONFIRMATION_SYSTEM_PROMPT


def _make_mock_client(
    response_text: str = "Dear Sarah,\n\nWe're thrilled to confirm our partnership!",
) -> MagicMock:
    """Create a mock Anthropic client with a canned response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_content_block = MagicMock()
    mock_content_block.text = response_text
    mock_response.content = [mock_content_block]
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 600
    mock_response.usage.output_tokens = 250
    mock_client.messages.create.return_value = mock_response
    return mock_client


class TestComposeAgreementEmail:
    """Tests for compose_agreement_email function."""

    def test_compose_agreement_email_returns_composed_email(self):
        """compose_agreement_email returns a ComposedEmail with correct fields."""
        mock_client = _make_mock_client("Dear Sarah,\n\nWe're excited to confirm the deal!")
        result = compose_agreement_email(
            influencer_name="Sarah",
            agreed_rate="1500.00",
            deliverables_summary="2x Instagram Reels, 1x Story",
            usage_rights_summary="12 months paid amplification",
            platform="instagram",
            payment_terms="within 30 days of content going live",
            knowledge_base_content="Be professional and celebratory.",
            negotiation_history="Agreed after 2 rounds.",
            client=mock_client,
        )
        assert isinstance(result, ComposedEmail)
        assert result.email_body == "Dear Sarah,\n\nWe're excited to confirm the deal!"
        assert result.input_tokens == 600
        assert result.output_tokens == 250

    def test_agreement_system_prompt_includes_knowledge_base(self):
        """System prompt injected to the LLM includes knowledge base content."""
        mock_client = _make_mock_client()
        compose_agreement_email(
            influencer_name="Sarah",
            agreed_rate="1500.00",
            deliverables_summary="2x Instagram Reels",
            usage_rights_summary=None,
            platform="instagram",
            payment_terms="within 30 days",
            knowledge_base_content="Always celebrate the partnership.",
            negotiation_history="No prior messages.",
            client=mock_client,
        )
        call_kwargs = mock_client.messages.create.call_args
        system_blocks = call_kwargs.kwargs["system"]
        system_text = system_blocks[0]["text"]
        assert "Always celebrate the partnership." in system_text

    def test_agreement_user_prompt_includes_agreed_terms(self):
        """User message includes deliverables, rate, and usage rights."""
        mock_client = _make_mock_client()
        compose_agreement_email(
            influencer_name="Jake",
            agreed_rate="2500.00",
            deliverables_summary="1x YouTube Video, 2x Shorts",
            usage_rights_summary="6 months organic only",
            platform="youtube",
            payment_terms="net 30",
            knowledge_base_content="KB content here.",
            negotiation_history="Round 1: agreed.",
            client=mock_client,
        )
        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[0]["content"]
        assert "1x YouTube Video" in user_content
        assert "2500.00" in user_content
        assert "6 months organic only" in user_content

    def test_agreement_user_prompt_includes_payment_terms(self):
        """User message includes payment terms."""
        mock_client = _make_mock_client()
        compose_agreement_email(
            influencer_name="Sarah",
            agreed_rate="1500.00",
            deliverables_summary="2x Instagram Reels",
            usage_rights_summary=None,
            platform="instagram",
            payment_terms="net 45 from invoice date",
            knowledge_base_content="KB content.",
            negotiation_history="No prior.",
            client=mock_client,
        )
        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[0]["content"]
        assert "net 45 from invoice date" in user_content

    def test_agreement_user_prompt_includes_next_steps_instruction(self):
        """System prompt mentions next steps for agreement emails."""
        # The AGREEMENT_CONFIRMATION_SYSTEM_PROMPT should contain next steps guidance
        assert "next steps" in AGREEMENT_CONFIRMATION_SYSTEM_PROMPT.lower()
        assert "SOW" in AGREEMENT_CONFIRMATION_SYSTEM_PROMPT

    def test_agreement_default_payment_terms(self):
        """Empty payment_terms string defaults to 30-day terms."""
        mock_client = _make_mock_client()
        compose_agreement_email(
            influencer_name="Sarah",
            agreed_rate="1500.00",
            deliverables_summary="2x Instagram Reels",
            usage_rights_summary=None,
            platform="instagram",
            payment_terms="",
            knowledge_base_content="KB content.",
            negotiation_history="No prior.",
            client=mock_client,
        )
        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[0]["content"]
        assert "within 30 days of content going live" in user_content

    def test_agreement_counterparty_context_included(self):
        """Counterparty context tone guidance is passed through to user prompt."""
        mock_client = _make_mock_client()
        compose_agreement_email(
            influencer_name="Sarah",
            agreed_rate="1500.00",
            deliverables_summary="2x Instagram Reels",
            usage_rights_summary=None,
            platform="instagram",
            payment_terms="net 30",
            knowledge_base_content="KB content.",
            negotiation_history="No prior.",
            client=mock_client,
            counterparty_context="COUNTERPARTY CONTEXT: talent manager at WME",
        )
        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[0]["content"]
        assert "COUNTERPARTY CONTEXT: talent manager at WME" in user_content
