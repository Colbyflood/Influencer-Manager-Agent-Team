"""Deterministic SOW block builder for counter-offer emails.

Produces structured Scope of Work text blocks with deliverable lists,
usage rights terms, and rate formatting including strikethrough
adjustments (e.g., ~~$2,000.00~~ $1,500.00).
"""

from __future__ import annotations


def _format_currency(value: str) -> str:
    """Format a numeric string as currency with commas and cents.

    Args:
        value: Numeric rate string (e.g., "1500", "1500.00", "2000.50").
            Non-numeric values are returned as-is.

    Returns:
        Formatted currency string (e.g., "$1,500.00"), or the original
        value if it cannot be parsed as a number.
    """
    cleaned = value.replace(",", "").replace("$", "").strip()
    try:
        amount = float(cleaned)
    except ValueError:
        return value
    return f"${amount:,.2f}"


def format_rate_adjustment(original_rate: str, adjusted_rate: str) -> str:
    """Format a rate adjustment with optional strikethrough.

    When the original and adjusted rates differ, returns a strikethrough
    formatted string showing both values. When they match, returns just
    the formatted rate.

    Args:
        original_rate: The original/previous rate as a numeric string.
        adjusted_rate: The new counter-offer rate as a numeric string.

    Returns:
        Formatted rate string, e.g., "~~$2,000.00~~ $1,500.00" or "$1,500.00".
    """
    original_formatted = _format_currency(original_rate)
    adjusted_formatted = _format_currency(adjusted_rate)

    if original_formatted == adjusted_formatted:
        return adjusted_formatted

    return f"~~{original_formatted}~~ {adjusted_formatted}"


def _parse_deliverables(deliverables_summary: str) -> list[str]:
    """Parse a deliverables summary into individual items.

    Handles both comma-separated and multi-line formats.

    Args:
        deliverables_summary: Deliverables as comma-separated or newline-separated text.

    Returns:
        List of individual deliverable strings, stripped of whitespace.
    """
    if "\n" in deliverables_summary:
        items = deliverables_summary.strip().split("\n")
    else:
        items = deliverables_summary.split(",")

    return [item.strip().lstrip("- ") for item in items if item.strip()]


def format_sow_block(
    deliverables_summary: str,
    usage_rights_summary: str | None,
    rate_display: str,
    platform: str,
) -> str:
    """Build a structured SOW text block for embedding in negotiation emails.

    Produces a formatted Scope of Work section with deliverable bullets,
    usage rights, and rate display matching AGM email format.

    Args:
        deliverables_summary: Deliverables as comma-separated or newline-separated text.
        usage_rights_summary: Usage rights description, or None for default terms.
        rate_display: Pre-formatted rate string (from format_rate_adjustment).
        platform: Social media platform for terminology reference.

    Returns:
        Formatted SOW block string ready for email embedding.
    """
    deliverables = _parse_deliverables(deliverables_summary)

    lines: list[str] = ["Scope of Work:"]
    for item in deliverables:
        lines.append(f"- {item}")

    usage_text = usage_rights_summary or "per standard terms"
    lines.append(f"- Usage Rights: {usage_text}")
    lines.append(f"- Rate: {rate_display}")

    return "\n".join(lines)
