"""Deterministic validation gate for composed emails.

Validates LLM-generated emails using regex and string matching only -- no LLM
calls. Catches monetary mismatches, hallucinated commitments, off-brand
language, and basic sanity issues before any email is sent.
"""

import re
from decimal import Decimal

from negotiation.llm.models import ValidationFailure, ValidationResult

# Regex for dollar amounts like $1,500.00, $1500, $200.50
_DOLLAR_PATTERN = re.compile(r"\$[\d,]+(?:\.\d{2})?")

# Hallucinated commitment patterns the LLM must never promise
_HALLUCINATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bexclusi(?:ve|vity)\b", re.IGNORECASE),
    re.compile(r"\busage\s+rights?\b", re.IGNORECASE),
    re.compile(r"\brights?\s+extension\b", re.IGNORECASE),
    re.compile(r"\bfuture\s+(?:deal|campaign|partnership)s?\b", re.IGNORECASE),
    re.compile(r"\bguarantee\b", re.IGNORECASE),
]

_MIN_EMAIL_LENGTH = 50


def _normalize_dollar(value: str) -> str:
    """Normalize a dollar string by stripping $ and commas.

    Examples:
        "$1,500.00" -> "1500.00"
        "$1500" -> "1500"
    """
    return value.replace("$", "").replace(",", "")


def _decimal_to_dollar_normalized(rate: Decimal) -> str:
    """Convert a Decimal rate to a normalized dollar string for comparison.

    Examples:
        Decimal("1500.00") -> "1500.00"
        Decimal("1250") -> "1250"
    """
    return str(rate)


def validate_composed_email(
    email_body: str,
    expected_rate: Decimal,
    expected_deliverables: list[str],
    influencer_name: str,
    forbidden_phrases: list[str] | None = None,
) -> ValidationResult:
    """Validate a composed email using deterministic checks (no LLM).

    Runs five validation checks:
    1. Monetary values -- all dollar amounts must match the expected rate
    2. Deliverable coverage -- expected deliverables should be mentioned (warning only)
    3. Hallucinated commitments -- no exclusivity, usage rights, future deals, guarantees
    4. Off-brand language -- no forbidden phrases present
    5. Basic sanity -- email must be at least 50 characters

    Args:
        email_body: The composed email text to validate.
        expected_rate: The intended counter-offer rate (Decimal).
        expected_deliverables: List of expected deliverable type strings
            (e.g., ["instagram_reel", "story"]).
        influencer_name: Name of the influencer (for context).
        forbidden_phrases: Optional list of phrases that should not appear
            in the email. Case-insensitive matching.

    Returns:
        ValidationResult with passed=True only if no error-severity failures.
    """
    failures: list[ValidationFailure] = []

    # Check 1: Monetary values
    dollar_amounts = _DOLLAR_PATTERN.findall(email_body)
    expected_normalized = _decimal_to_dollar_normalized(expected_rate)
    for amount in dollar_amounts:
        normalized = _normalize_dollar(amount)
        if normalized != expected_normalized:
            failures.append(
                ValidationFailure(
                    check="monetary_value",
                    reason=(
                        f"Found dollar amount {amount} in email but expected "
                        f"rate is ${expected_normalized}"
                    ),
                    severity="error",
                )
            )

    # Check 2: Deliverable coverage (warning only)
    email_lower = email_body.lower()
    for deliverable in expected_deliverables:
        # Check full name and short name (last segment after underscore)
        short_name = deliverable.split("_")[-1]
        if deliverable.lower() not in email_lower and short_name.lower() not in email_lower:
            failures.append(
                ValidationFailure(
                    check="deliverable_coverage",
                    reason=f"Expected deliverable '{deliverable}' not mentioned in email",
                    severity="warning",
                )
            )

    # Check 3: Hallucinated commitments
    for pattern in _HALLUCINATION_PATTERNS:
        match = pattern.search(email_body)
        if match:
            failures.append(
                ValidationFailure(
                    check="hallucinated_commitment",
                    reason=(f"Email contains unauthorized commitment: '{match.group()}'"),
                    severity="error",
                )
            )

    # Check 4: Off-brand language
    if forbidden_phrases:
        for phrase in forbidden_phrases:
            if phrase.lower() in email_lower:
                failures.append(
                    ValidationFailure(
                        check="off_brand_language",
                        reason=f"Email contains forbidden phrase: '{phrase}'",
                        severity="error",
                    )
                )

    # Check 5: Basic sanity
    if len(email_body.strip()) < _MIN_EMAIL_LENGTH:
        failures.append(
            ValidationFailure(
                check="too_short",
                reason=(
                    f"Email body is {len(email_body.strip())} characters, "
                    f"minimum is {_MIN_EMAIL_LENGTH}"
                ),
                severity="error",
            )
        )

    # passed = True only if zero error-severity failures
    has_errors = any(f.severity == "error" for f in failures)

    return ValidationResult(
        passed=not has_errors,
        failures=failures,
        email_body=email_body,
    )
