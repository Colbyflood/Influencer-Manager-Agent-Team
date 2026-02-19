"""Email composition module for counter-offer generation.

Uses the Anthropic Claude API to compose contextually appropriate negotiation
emails, with knowledge base content injected via cached system prompts for
cost efficiency.
"""

from anthropic import Anthropic

from negotiation.llm.client import COMPOSE_MODEL
from negotiation.llm.models import ComposedEmail
from negotiation.llm.prompts import EMAIL_COMPOSITION_SYSTEM_PROMPT, EMAIL_COMPOSITION_USER_PROMPT


def compose_counter_email(
    influencer_name: str,
    their_rate: str,
    our_rate: str,
    deliverables_summary: str,
    platform: str,
    negotiation_stage: str,
    knowledge_base_content: str,
    negotiation_history: str,
    client: Anthropic,
    model: str = COMPOSE_MODEL,
) -> ComposedEmail:
    """Compose a counter-offer email using the Claude API.

    Builds a system prompt with knowledge base content (cached for cost savings)
    and a user prompt with all negotiation parameters. Returns a ComposedEmail
    with the generated body and token usage metrics.

    Args:
        influencer_name: Name of the influencer to address.
        their_rate: The influencer's proposed rate as a string (e.g., "2000.00").
        our_rate: Our counter-offer rate as a string (e.g., "1500.00").
        deliverables_summary: Human-readable summary of deliverables.
        platform: Social media platform (e.g., "instagram", "tiktok").
        negotiation_stage: Current stage of negotiation (e.g., "initial_counter").
        knowledge_base_content: Loaded knowledge base Markdown for system prompt.
        negotiation_history: Summary of prior negotiation exchanges.
        client: Configured Anthropic client instance.
        model: Model ID to use. Defaults to COMPOSE_MODEL (Sonnet).

    Returns:
        ComposedEmail with email body, model used, and token counts.
    """
    system_text = EMAIL_COMPOSITION_SYSTEM_PROMPT.format(
        knowledge_base_content=knowledge_base_content,
    )

    user_text = EMAIL_COMPOSITION_USER_PROMPT.format(
        influencer_name=influencer_name,
        platform=platform,
        negotiation_stage=negotiation_stage,
        their_rate=their_rate,
        our_rate=our_rate,
        deliverables_summary=deliverables_summary,
        negotiation_history=negotiation_history,
    )

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": user_text,
            }
        ],
    )

    email_body: str = response.content[0].text  # type: ignore[union-attr]
    input_tokens: int = response.usage.input_tokens
    output_tokens: int = response.usage.output_tokens

    return ComposedEmail(
        email_body=email_body,
        model_used=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
