"""Negotiation state persistence package.

Provides SQLite-backed storage for negotiation state snapshots and
serialization helpers for domain objects.
"""

from negotiation.state.schema import init_negotiation_state_table
from negotiation.state.serializers import (
    deserialize_context,
    deserialize_cpm_tracker,
    serialize_context,
    serialize_cpm_tracker,
)
from negotiation.state.store import NegotiationStateStore

__all__ = [
    "NegotiationStateStore",
    "deserialize_context",
    "deserialize_cpm_tracker",
    "init_negotiation_state_table",
    "serialize_context",
    "serialize_cpm_tracker",
]
