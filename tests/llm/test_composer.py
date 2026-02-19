"""Tests for email composition using mocked Anthropic client.

Verifies that compose_counter_email correctly builds prompts with knowledge base
content, passes all parameters to the LLM, and returns a ComposedEmail with
token usage tracking.
"""

from unittest.mock import MagicMock

from negotiation.llm.client import COMPOSE_MODEL
from negotiation.llm.composer import compose_counter_email
from negotiation.llm.models import ComposedEmail


def _make_mock_client(
    response_text: str = "Dear Sarah,\n\nThank you for your proposal.",
) -> MagicMock:
    """Create a mock Anthropic client with a canned response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_content_block = MagicMock()
    mock_content_block.text = response_text
    mock_response.content = [mock_content_block]
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 512
    mock_response.usage.output_tokens = 200
    mock_client.messages.create.return_value = mock_response
    return mock_client


class TestComposeCounterEmail:
    """Tests for compose_counter_email function."""

    def test_returns_composed_email(self):
        """compose_counter_email returns a ComposedEmail with correct fields."""
        mock_client = _make_mock_client("Dear Sarah,\n\nHere is our counter-offer.")
        result = compose_counter_email(
            influencer_name="Sarah",
            their_rate="2000.00",
            our_rate="1500.00",
            deliverables_summary="2x Instagram Reels, 1x Story",
            platform="instagram",
            negotiation_stage="initial_counter",
            knowledge_base_content="Be professional and friendly.",
            negotiation_history="No prior messages.",
            client=mock_client,
        )
        assert isinstance(result, ComposedEmail)
        assert result.email_body == "Dear Sarah,\n\nHere is our counter-offer."
        assert result.model_used == COMPOSE_MODEL
        assert result.input_tokens == 512
        assert result.output_tokens == 200

    def test_system_prompt_includes_knowledge_base(self):
        """System prompt injected to the LLM includes knowledge base content."""
        mock_client = _make_mock_client()
        compose_counter_email(
            influencer_name="Sarah",
            their_rate="2000.00",
            our_rate="1500.00",
            deliverables_summary="2x Instagram Reels",
            platform="instagram",
            negotiation_stage="initial_counter",
            knowledge_base_content="Always be warm and collaborative.",
            negotiation_history="No prior messages.",
            client=mock_client,
        )
        call_kwargs = mock_client.messages.create.call_args
        system_blocks = call_kwargs.kwargs["system"]
        system_text = system_blocks[0]["text"]
        assert "Always be warm and collaborative." in system_text

    def test_user_prompt_includes_all_parameters(self):
        """User message includes all negotiation parameters."""
        mock_client = _make_mock_client()
        compose_counter_email(
            influencer_name="Jake",
            their_rate="3000.00",
            our_rate="2500.00",
            deliverables_summary="1x YouTube Video",
            platform="youtube",
            negotiation_stage="second_counter",
            knowledge_base_content="KB content here.",
            negotiation_history="Round 1: They asked for $3000.",
            client=mock_client,
        )
        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[0]["content"]
        assert "Jake" in user_content
        assert "3000.00" in user_content
        assert "2500.00" in user_content
        assert "1x YouTube Video" in user_content
        assert "youtube" in user_content
        assert "second_counter" in user_content
        assert "Round 1: They asked for $3000." in user_content

    def test_model_defaults_to_compose_model(self):
        """Default model parameter uses COMPOSE_MODEL constant."""
        mock_client = _make_mock_client()
        compose_counter_email(
            influencer_name="Sarah",
            their_rate="2000.00",
            our_rate="1500.00",
            deliverables_summary="2x Instagram Reels",
            platform="instagram",
            negotiation_stage="initial_counter",
            knowledge_base_content="KB content.",
            negotiation_history="No prior.",
            client=mock_client,
        )
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == COMPOSE_MODEL

    def test_custom_model_parameter(self):
        """Custom model parameter is passed through to API call."""
        mock_client = _make_mock_client()
        compose_counter_email(
            influencer_name="Sarah",
            their_rate="2000.00",
            our_rate="1500.00",
            deliverables_summary="2x Instagram Reels",
            platform="instagram",
            negotiation_stage="initial_counter",
            knowledge_base_content="KB content.",
            negotiation_history="No prior.",
            client=mock_client,
            model="claude-haiku-4-5-20250929",
        )
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-haiku-4-5-20250929"

    def test_cache_control_set_on_system_content(self):
        """System content block includes cache_control for prompt caching."""
        mock_client = _make_mock_client()
        compose_counter_email(
            influencer_name="Sarah",
            their_rate="2000.00",
            our_rate="1500.00",
            deliverables_summary="2x Instagram Reels",
            platform="instagram",
            negotiation_stage="initial_counter",
            knowledge_base_content="KB content for caching.",
            negotiation_history="No prior.",
            client=mock_client,
        )
        call_kwargs = mock_client.messages.create.call_args
        system_blocks = call_kwargs.kwargs["system"]
        assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}
