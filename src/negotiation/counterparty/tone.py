"""Tone guidance generation for counterparty-adaptive negotiation.

Produces prompt instructions that adjust the agent's communication style
based on whether the counterparty is a talent manager or a direct influencer.
Talent managers respond to data-backed, professional language while direct
influencers respond to relationship-driven, creative-alignment language.
"""

from __future__ import annotations

_TALENT_MANAGER_GUIDANCE = """\
COUNTERPARTY CONTEXT:
You are negotiating with a talent manager/agency representative{agency_suffix}.
Adapt your tone accordingly:
- Be professional, concise, and direct -- managers handle many negotiations simultaneously
- Lead with data: CPM benchmarks, market rates, campaign performance metrics
- Frame proposals in business terms: ROI, deliverable value, cost efficiency
- Avoid excessive flattery or creative-vision language -- focus on deal terms
- Use industry-standard terminology (SOW, usage rights, deliverables, rate card)
- Acknowledge their role: "I understand you're managing multiple campaigns..."\
"""

_DIRECT_INFLUENCER_GUIDANCE = """\
COUNTERPARTY CONTEXT:
You are negotiating directly with the influencer/creator.
Adapt your tone accordingly:
- Be warm, enthusiastic, and relationship-focused
- Lead with creative alignment: how the brand fits their content style and audience
- Emphasize partnership value: long-term relationship, creative freedom, brand alignment
- Use creator-friendly language: "your audience", "your content", "collaboration"
- Show genuine appreciation for their work and creative vision
- Frame rate discussions around fair value for their unique audience and content quality\
"""


def get_tone_guidance(
    counterparty_type: str | None = None,
    agency_name: str | None = None,
) -> str:
    """Return tone guidance instructions for the given counterparty type.

    Args:
        counterparty_type: The counterparty classification string.
            ``"talent_manager"`` yields data-backed professional tone;
            ``"direct_influencer"`` or any other value yields warm
            relationship-focused tone.
        agency_name: Optional agency name to include in talent manager
            guidance for personalisation.

    Returns:
        A multi-line instruction string suitable for injection into the
        LLM user prompt.
    """
    if counterparty_type == "talent_manager":
        agency_suffix = f" from {agency_name}" if agency_name else ""
        return _TALENT_MANAGER_GUIDANCE.format(agency_suffix=agency_suffix)

    return _DIRECT_INFLUENCER_GUIDANCE
