"""Tests for Block Kit message builders.

These are pure function tests -- no mocks needed. The block builders
return plain dicts that we can inspect directly.
"""

from decimal import Decimal

from negotiation.slack.blocks import build_agreement_blocks, build_escalation_blocks

# ---------- Escalation block tests ----------


def _build_full_escalation_blocks():
    """Helper to build escalation blocks with all fields populated."""
    return build_escalation_blocks(
        influencer_name="Jane Creator",
        influencer_email="jane@example.com",
        client_name="Acme Brand",
        escalation_reason="CPM over threshold ($35 vs $30 limit)",
        evidence_quote="I typically charge $3,500 for this kind of content",
        proposed_rate="3500",
        our_rate="2500",
        suggested_actions=["Reply with counter at $3,000", "Approve $3,500 rate"],
        details_link="https://mail.google.com/mail/u/0/#inbox/abc123",
    )


def test_escalation_blocks_contain_required_fields():
    """Escalation blocks include influencer name, email, client, and reason."""
    blocks = _build_full_escalation_blocks()
    full_text = str(blocks)

    assert "Jane Creator" in full_text
    assert "jane@example.com" in full_text
    assert "Acme Brand" in full_text
    assert "CPM over threshold" in full_text


def test_escalation_blocks_header():
    """Escalation header includes influencer name."""
    blocks = _build_full_escalation_blocks()

    assert blocks[0]["type"] == "header"
    assert "Jane Creator" in blocks[0]["text"]["text"]
    assert blocks[0]["text"]["text"].startswith("Escalation:")


def test_escalation_blocks_include_rate_comparison():
    """Rate comparison section appears when rates are provided."""
    blocks = _build_full_escalation_blocks()
    full_text = str(blocks)

    assert "Their Rate" in full_text
    assert "Our Rate" in full_text
    assert "3500" in full_text
    assert "2500" in full_text


def test_escalation_blocks_omit_rate_section_when_no_rates():
    """Rate comparison section is omitted when both rates are None."""
    blocks = build_escalation_blocks(
        influencer_name="Jane Creator",
        influencer_email="jane@example.com",
        client_name="Acme Brand",
        escalation_reason="Hostile tone detected",
        evidence_quote="Some quote",
        proposed_rate=None,
        our_rate=None,
        suggested_actions=[],
        details_link="https://mail.google.com/mail/u/0/#inbox/abc123",
    )
    full_text = str(blocks)

    assert "Their Rate" not in full_text
    assert "Our Rate" not in full_text


def test_escalation_blocks_include_evidence_quote():
    """Evidence section uses mrkdwn blockquote format."""
    blocks = _build_full_escalation_blocks()
    full_text = str(blocks)

    assert "Evidence" in full_text
    assert ">I typically charge $3,500" in full_text


def test_escalation_blocks_omit_evidence_when_empty():
    """Evidence section is omitted when evidence_quote is empty."""
    blocks = build_escalation_blocks(
        influencer_name="Jane Creator",
        influencer_email="jane@example.com",
        client_name="Acme Brand",
        escalation_reason="Ambiguous intent",
        evidence_quote="",
        proposed_rate=None,
        our_rate=None,
        suggested_actions=[],
        details_link="https://mail.google.com/mail/u/0/#inbox/abc123",
    )
    full_text = str(blocks)

    assert "Evidence" not in full_text


def test_escalation_blocks_include_suggested_actions():
    """Suggested actions appear as bullet list."""
    blocks = _build_full_escalation_blocks()
    full_text = str(blocks)

    assert "Suggested Actions" in full_text
    assert "Reply with counter at $3,000" in full_text
    assert "Approve $3,500 rate" in full_text


def test_escalation_blocks_omit_actions_when_empty():
    """Suggested actions section is omitted when list is empty."""
    blocks = build_escalation_blocks(
        influencer_name="Jane Creator",
        influencer_email="jane@example.com",
        client_name="Acme Brand",
        escalation_reason="Test",
        evidence_quote="",
        proposed_rate=None,
        our_rate=None,
        suggested_actions=[],
        details_link="https://mail.google.com/mail/u/0/#inbox/abc123",
    )
    full_text = str(blocks)

    assert "Suggested Actions" not in full_text


def test_escalation_blocks_include_details_link():
    """Details link appears in context block with mrkdwn link format."""
    blocks = _build_full_escalation_blocks()

    # Last block should be context with link
    last_block = blocks[-1]
    assert last_block["type"] == "context"
    link_text = last_block["elements"][0]["text"]
    assert "https://mail.google.com/mail/u/0/#inbox/abc123" in link_text
    assert "View full conversation details" in link_text


# ---------- Agreement block tests ----------


def _build_full_agreement_blocks():
    """Helper to build agreement blocks with all fields populated."""
    return build_agreement_blocks(
        influencer_name="Jane Creator",
        influencer_email="jane@example.com",
        client_name="Acme Brand",
        agreed_rate=Decimal("2500.00"),
        platform="instagram",
        deliverables="2x Reels + 1x Story",
        cpm_achieved=Decimal("22.50"),
        next_steps=["Send contract", "Confirm deliverables"],
        mention_users=["U024BE7LH", "U0G9QF9C6"],
    )


def test_agreement_blocks_contain_required_fields():
    """Agreement blocks include all required fields."""
    blocks = _build_full_agreement_blocks()
    full_text = str(blocks)

    assert "Jane Creator" in full_text
    assert "jane@example.com" in full_text
    assert "Acme Brand" in full_text
    assert "$2,500.00" in full_text
    assert "Instagram" in full_text  # platform.title()
    assert "2x Reels + 1x Story" in full_text
    assert "$22.50" in full_text


def test_agreement_blocks_header():
    """Agreement header includes influencer name."""
    blocks = _build_full_agreement_blocks()

    assert blocks[0]["type"] == "header"
    assert "Jane Creator" in blocks[0]["text"]["text"]
    assert blocks[0]["text"]["text"].startswith("Deal Agreed:")


def test_agreement_blocks_rate_formatting():
    """Agreed rate and CPM are formatted as $X,XXX.XX."""
    blocks = _build_full_agreement_blocks()
    full_text = str(blocks)

    assert "$2,500.00" in full_text
    assert "$22.50" in full_text


def test_agreement_blocks_include_next_steps():
    """Next steps appear as bullet list."""
    blocks = _build_full_agreement_blocks()
    full_text = str(blocks)

    assert "Next Steps" in full_text
    assert "Send contract" in full_text
    assert "Confirm deliverables" in full_text


def test_agreement_blocks_omit_next_steps_when_empty():
    """Next steps section is omitted when list is empty."""
    blocks = build_agreement_blocks(
        influencer_name="Jane Creator",
        influencer_email="jane@example.com",
        client_name="Acme Brand",
        agreed_rate=Decimal("2500.00"),
        platform="instagram",
        deliverables="2x Reels",
        cpm_achieved=Decimal("22.50"),
        next_steps=[],
        mention_users=None,
    )
    full_text = str(blocks)

    assert "Next Steps" not in full_text


def test_agreement_blocks_include_mentions():
    """Mentions use <@USER_ID> syntax."""
    blocks = _build_full_agreement_blocks()
    full_text = str(blocks)

    assert "<@U024BE7LH>" in full_text
    assert "<@U0G9QF9C6>" in full_text


def test_agreement_blocks_omit_mentions_when_empty():
    """Mention section is omitted when mention_users is None or empty."""
    blocks = build_agreement_blocks(
        influencer_name="Jane Creator",
        influencer_email="jane@example.com",
        client_name="Acme Brand",
        agreed_rate=Decimal("2500.00"),
        platform="instagram",
        deliverables="2x Reels",
        cpm_achieved=Decimal("22.50"),
        next_steps=[],
        mention_users=None,
    )

    # Should have exactly 3 blocks: header, details, financials (no mentions, no next steps)
    assert len(blocks) == 3


def test_agreement_blocks_omit_mentions_when_list_empty():
    """Mention section is omitted when mention_users is an empty list."""
    blocks = build_agreement_blocks(
        influencer_name="Jane Creator",
        influencer_email="jane@example.com",
        client_name="Acme Brand",
        agreed_rate=Decimal("2500.00"),
        platform="instagram",
        deliverables="2x Reels",
        cpm_achieved=Decimal("22.50"),
        next_steps=[],
        mention_users=[],
    )

    # Should have exactly 3 blocks: header, details, financials
    assert len(blocks) == 3
