"""Email composition module for counter-offer generation.

Uses the Anthropic Claude API to compose contextually appropriate negotiation
emails, with knowledge base content injected via cached system prompts for
cost efficiency.
"""

from __future__ import annotations

from anthropic import Anthropic

from negotiation.llm.client import COMPOSE_MODEL
from negotiation.llm.models import ComposedEmail
from negotiation.llm.prompts import (
    AGREEMENT_CONFIRMATION_SYSTEM_PROMPT,
    AGREEMENT_CONFIRMATION_USER_PROMPT,
    EMAIL_COMPOSITION_SYSTEM_PROMPT,
    EMAIL_COMPOSITION_USER_PROMPT,
)
from negotiation.llm.sow_formatter import format_rate_adjustment, format_sow_block


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
    lever_instructions: str = "",
    counterparty_context: str = "",
    original_rate: str = "",
    usage_rights_summary: str | None = None,
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
        lever_instructions: Specific negotiation lever tactic to use.
        counterparty_context: Counterparty-specific context for tone adjustment.
        original_rate: The influencer's original rate for strikethrough comparison.
            If empty, their_rate is used as the original for comparison.
        usage_rights_summary: Usage rights text for SOW block, or None for defaults.

    Returns:
        ComposedEmail with email body, model used, and token counts.
    """
    # Build SOW block with rate adjustment formatting
    rate_display = format_rate_adjustment(original_rate or their_rate, our_rate)
    sow_block = format_sow_block(
        deliverables_summary=deliverables_summary,
        usage_rights_summary=usage_rights_summary,
        rate_display=rate_display,
        platform=platform,
    )

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
        sow_block=sow_block,
        lever_instructions=lever_instructions
        or "No specific lever -- respond naturally to their proposal.",
        counterparty_context=counterparty_context or "No specific counterparty context.",
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


def compose_agreement_email(
    influencer_name: str,
    agreed_rate: str,
    deliverables_summary: str,
    usage_rights_summary: str | None,
    platform: str,
    payment_terms: str,
    knowledge_base_content: str,
    negotiation_history: str,
    client: Anthropic,
    model: str = COMPOSE_MODEL,
    counterparty_context: str = "",
) -> ComposedEmail:
    """Compose a deal confirmation email using the Claude API.

    Builds a system prompt with knowledge base content (cached for cost savings)
    and a user prompt with all agreed terms, payment terms, and next steps
    instructions. Returns a ComposedEmail with the generated body and token
    usage metrics.

    Args:
        influencer_name: Name of the influencer to address.
        agreed_rate: The agreed-upon rate as a string (e.g., "1500.00").
        deliverables_summary: Human-readable summary of agreed deliverables.
        usage_rights_summary: Usage rights text, or None for default terms.
        platform: Social media platform (e.g., "instagram", "tiktok").
        payment_terms: Payment terms description. If empty, defaults to
            "within 30 days of content going live".
        knowledge_base_content: Loaded knowledge base Markdown for system prompt.
        negotiation_history: Summary of prior negotiation exchanges.
        client: Configured Anthropic client instance.
        model: Model ID to use. Defaults to COMPOSE_MODEL (Sonnet).
        counterparty_context: Counterparty-specific context for tone adjustment.

    Returns:
        ComposedEmail with email body, model used, and token counts.
    """
    # Build agreed terms block using SOW formatter (no strikethrough -- agreed rate directly)
    rate_display = format_sow_block(
        deliverables_summary=deliverables_summary,
        usage_rights_summary=usage_rights_summary,
        rate_display=agreed_rate,
        platform=platform,
    )

    # Default payment terms if empty
    effective_payment_terms = payment_terms or "within 30 days of content going live"

    system_text = AGREEMENT_CONFIRMATION_SYSTEM_PROMPT.format(
        knowledge_base_content=knowledge_base_content,
    )

    user_text = AGREEMENT_CONFIRMATION_USER_PROMPT.format(
        influencer_name=influencer_name,
        platform=platform,
        agreed_terms_block=rate_display,
        payment_terms=effective_payment_terms,
        counterparty_context=counterparty_context or "No specific counterparty context.",
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
