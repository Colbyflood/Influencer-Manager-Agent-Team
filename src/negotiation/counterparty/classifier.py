"""Counterparty classifier for negotiation email analysis.

Analyzes an email sender's address, body text, and subject to determine
whether the counterparty is a direct influencer or a talent manager/agency
representative.  Returns a CounterpartyProfile with confidence score and
the detection signals used.
"""

from __future__ import annotations

import re

from negotiation.counterparty.models import (
    CounterpartyProfile,
    CounterpartyType,
    DetectionSignal,
)

# ---------------------------------------------------------------------------
# Domain lookup tables
# ---------------------------------------------------------------------------

KNOWN_AGENCY_DOMAINS: dict[str, str] = {
    "unitedtalent.com": "United Talent Agency",
    "wmgagent.com": "William Morris Endeavor",
    "caa.com": "Creative Artists Agency",
    "icmpartners.com": "ICM Partners",
    "paradigmagency.com": "Paradigm Talent Agency",
    "gersh.com": "The Gersh Agency",
    "apa-agency.com": "APA Agency",
    "abrams-artists.com": "Abrams Artists Agency",
    "buchwald.com": "Buchwald Agency",
    "innovative-artists.com": "Innovative Artists",
    "dfrental.com": "DFR Entertainment",
    "selectmanagement.com": "Select Management Group",
    "digitaltalentagents.com": "Digital Talent Agents",
}

PERSONAL_DOMAINS: set[str] = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "protonmail.com",
    "live.com",
    "me.com",
    "msn.com",
    "mail.com",
}

# ---------------------------------------------------------------------------
# Signature / title patterns
# ---------------------------------------------------------------------------

MANAGER_TITLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:talent\s+)?manager\b", re.IGNORECASE),
    re.compile(r"\b(?:talent\s+)?agent\b", re.IGNORECASE),
    re.compile(r"\btalent\s+director\b", re.IGNORECASE),
    re.compile(r"\bvp\s+talent\b", re.IGNORECASE),
    re.compile(r"\bbooking\b", re.IGNORECASE),
    re.compile(r"\bon\s+behalf\s+of\b", re.IGNORECASE),
    re.compile(r"\brepresenting\b", re.IGNORECASE),
]

CREATOR_TITLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bcontent\s+creator\b", re.IGNORECASE),
    re.compile(r"\binfluencer\b", re.IGNORECASE),
    re.compile(r"\bcreator\b", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Structure patterns
# ---------------------------------------------------------------------------

_FORMAL_SIGN_OFF = re.compile(
    r"\b(?:best\s+regards|warm\s+regards|kind\s+regards|sincerely|respectfully)\b",
    re.IGNORECASE,
)

_CASUAL_PATTERN = re.compile(
    r"(?:^hey[!\s]|thanks[!]|\bsuper\s+excited\b|\bsounds\s+cool\b)",
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_domain(email: str) -> str:
    """Return the domain portion of an email address."""
    _, _, domain = email.rpartition("@")
    return domain.lower().strip()


def _check_domain(from_email: str) -> DetectionSignal | None:
    """Check the email domain against known agency and personal lists."""
    domain = _extract_domain(from_email)

    if domain in KNOWN_AGENCY_DOMAINS:
        return DetectionSignal(
            signal_type="agency_domain",
            value=domain,
            strength=1.0,
            indicates=CounterpartyType.TALENT_MANAGER,
        )

    if domain in PERSONAL_DOMAINS:
        return DetectionSignal(
            signal_type="personal_domain",
            value=domain,
            strength=0.8,
            indicates=CounterpartyType.DIRECT_INFLUENCER,
        )

    return None


def _scan_signature(body: str) -> list[DetectionSignal]:
    """Scan the last 10 lines of the email body for title keywords."""
    lines = body.strip().splitlines()
    signature_block = "\n".join(lines[-10:]) if len(lines) > 10 else body

    signals: list[DetectionSignal] = []

    for pattern in MANAGER_TITLE_PATTERNS:
        match = pattern.search(signature_block)
        if match:
            signals.append(
                DetectionSignal(
                    signal_type="signature_title",
                    value=match.group(),
                    strength=0.7,
                    indicates=CounterpartyType.TALENT_MANAGER,
                )
            )

    for pattern in CREATOR_TITLE_PATTERNS:
        match = pattern.search(signature_block)
        if match:
            signals.append(
                DetectionSignal(
                    signal_type="signature_title",
                    value=match.group(),
                    strength=0.6,
                    indicates=CounterpartyType.DIRECT_INFLUENCER,
                )
            )

    return signals


def _assess_structure(body: str) -> DetectionSignal | None:
    """Assess the email structure for formality signals."""
    if _FORMAL_SIGN_OFF.search(body):
        return DetectionSignal(
            signal_type="email_structure",
            value="formal_sign_off",
            strength=0.3,
            indicates=CounterpartyType.TALENT_MANAGER,
        )

    if _CASUAL_PATTERN.search(body):
        return DetectionSignal(
            signal_type="email_structure",
            value="casual_tone",
            strength=0.3,
            indicates=CounterpartyType.DIRECT_INFLUENCER,
        )

    return None


def _extract_agency_name(signals: list[DetectionSignal]) -> str | None:
    """Extract agency name from detection signals."""
    for signal in signals:
        if signal.signal_type == "agency_domain" and signal.value in KNOWN_AGENCY_DOMAINS:
            return KNOWN_AGENCY_DOMAINS[signal.value]
    return None


def _compute_confidence(
    manager_signals: list[DetectionSignal],
    influencer_signals: list[DetectionSignal],
) -> tuple[CounterpartyType, float]:
    """Compute counterparty type and confidence from accumulated signals."""
    manager_count = len(manager_signals)
    influencer_count = len(influencer_signals)

    has_strong_manager = any(s.strength >= 0.8 for s in manager_signals)

    if manager_count >= 2:
        return CounterpartyType.TALENT_MANAGER, 0.9
    if manager_count == 1 and has_strong_manager:
        return CounterpartyType.TALENT_MANAGER, 0.8
    if manager_count == 1 and not has_strong_manager:
        return CounterpartyType.TALENT_MANAGER, 0.6

    if influencer_count >= 1 and manager_count == 0:
        return CounterpartyType.DIRECT_INFLUENCER, 0.8

    # Default: ambiguous
    return CounterpartyType.DIRECT_INFLUENCER, 0.5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_counterparty(
    from_email: str,
    email_body: str,
    subject: str = "",
) -> CounterpartyProfile:
    """Classify the counterparty type from email metadata and content.

    Analyzes the sender's email domain, signature keywords, and email
    structure to determine whether the sender is a direct influencer
    or a talent manager/agency representative.

    Args:
        from_email: The sender's email address.
        email_body: The full text body of the email.
        subject: The email subject line (optional).

    Returns:
        A CounterpartyProfile with the classification result.
    """
    all_signals: list[DetectionSignal] = []

    # 1. Domain analysis
    domain_signal = _check_domain(from_email)
    if domain_signal is not None:
        all_signals.append(domain_signal)

    # 2. Signature keyword scan
    sig_signals = _scan_signature(email_body)
    all_signals.extend(sig_signals)

    # 3. Email structure assessment
    structure_signal = _assess_structure(email_body)
    if structure_signal is not None:
        all_signals.append(structure_signal)

    # Partition signals by indicated type
    manager_signals = [s for s in all_signals if s.indicates == CounterpartyType.TALENT_MANAGER]
    influencer_signals = [
        s for s in all_signals if s.indicates == CounterpartyType.DIRECT_INFLUENCER
    ]

    counterparty_type, confidence = _compute_confidence(manager_signals, influencer_signals)

    agency_name = _extract_agency_name(all_signals)

    return CounterpartyProfile(
        counterparty_type=counterparty_type,
        confidence=confidence,
        signals=all_signals,
        agency_name=agency_name,
    )
