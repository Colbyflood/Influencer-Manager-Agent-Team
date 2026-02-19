"""Serialization helpers for negotiation domain objects.

Handles the tricky Decimal <-> JSON round-trip by converting Decimal values to
strings so no precision is lost.  The negotiation loop already does
``Decimal(str(context["next_cpm"]))`` on the way back in, so string
representation is the correct contract.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from negotiation.campaign.cpm_tracker import CampaignCPMTracker


class _DecimalEncoder(json.JSONEncoder):
    """JSON encoder that converts Decimal values to strings."""

    def default(self, o: object) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


def serialize_context(context: dict[str, Any]) -> str:
    """JSON-encode a negotiation context dict, converting Decimals to strings.

    Args:
        context: The negotiation context dictionary.  May contain
                 ``Decimal`` values (e.g. ``next_cpm``).

    Returns:
        A JSON string with Decimal values represented as strings.
    """
    return json.dumps(context, cls=_DecimalEncoder)


def deserialize_context(json_str: str) -> dict[str, Any]:
    """Decode a JSON context string back to a dict.

    Note: Decimal fields come back as strings (e.g. ``"25.50"``).  The
    negotiation loop converts them back via ``Decimal(str(value))``.

    Args:
        json_str: JSON string produced by ``serialize_context``.

    Returns:
        The reconstructed context dictionary.
    """
    result: dict[str, Any] = json.loads(json_str)
    return result


def serialize_cpm_tracker(tracker: CampaignCPMTracker) -> dict[str, Any]:
    """Serialize a CampaignCPMTracker to a plain dict.

    Delegates to ``tracker.to_dict()`` which handles Decimal -> str
    conversion internally.

    Args:
        tracker: The CPM tracker instance.

    Returns:
        A JSON-safe dict representing the tracker's full state.
    """
    return tracker.to_dict()


def deserialize_cpm_tracker(data: dict[str, Any]) -> CampaignCPMTracker:
    """Reconstruct a CampaignCPMTracker from a serialized dict.

    Args:
        data: A dict produced by ``serialize_cpm_tracker`` / ``to_dict()``.

    Returns:
        A fully reconstructed ``CampaignCPMTracker`` instance.
    """
    from negotiation.campaign.cpm_tracker import CampaignCPMTracker

    return CampaignCPMTracker.from_dict(data)
