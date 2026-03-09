"""Campaign detail and timeline API endpoints.

Provides:
- GET /campaigns/{campaign_id}/negotiations — per-influencer negotiation data
- GET /campaigns/{campaign_id}/negotiations/{thread_id}/timeline — state
  transitions and audit trail for a specific negotiation thread
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from negotiation.audit.store import query_audit_trail

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class NegotiationSummary(BaseModel):
    """Per-influencer negotiation row within a campaign."""

    thread_id: str
    influencer_name: str
    influencer_email: str
    state: str
    round_count: int
    counterparty_type: str
    agency_name: str | None
    current_rate: float | None


class CampaignDetailResponse(BaseModel):
    """Response model for the campaign detail endpoint."""

    campaign_id: str
    negotiations: list[NegotiationSummary]
    total: int


class StateTransition(BaseModel):
    """A single state machine transition record."""

    from_state: str
    event: str
    to_state: str


class TimelineEntry(BaseModel):
    """A single audit trail entry for the timeline view."""

    timestamp: str
    event_type: str
    direction: str | None
    email_body: str | None
    negotiation_state: str | None
    rates_used: str | None
    metadata: dict[str, Any] | None


class TimelineResponse(BaseModel):
    """Response model for the negotiation timeline endpoint."""

    thread_id: str
    influencer_name: str
    state_transitions: list[StateTransition]
    timeline: list[TimelineEntry]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/campaigns/{campaign_id}/negotiations",
    response_model=CampaignDetailResponse,
)
async def campaign_detail(
    campaign_id: str,
    request: Request,
) -> CampaignDetailResponse:
    """Return per-influencer negotiation data for a campaign.

    Filters the in-memory negotiation_states by campaign_id and extracts
    summary information for each matching thread.
    """
    negotiation_states: dict[str, dict[str, Any]] = getattr(
        request.app.state, "negotiation_states", {}
    )

    negotiations: list[NegotiationSummary] = []

    for thread_id, entry in negotiation_states.items():
        context = entry.get("context", {})
        if context.get("campaign_id") != campaign_id:
            continue

        # Extract current rate from CPM tracker if available
        current_rate: float | None = None
        cpm_tracker = entry.get("cpm_tracker")
        if cpm_tracker is not None:
            running_avg = getattr(cpm_tracker, "running_average_cpm", None)
            if running_avg is not None:
                current_rate = float(running_avg)

        state_machine = entry.get("state_machine")
        state_str = str(state_machine.state) if state_machine is not None else "unknown"

        negotiations.append(
            NegotiationSummary(
                thread_id=thread_id,
                influencer_name=context.get("influencer_name", "Unknown"),
                influencer_email=context.get("influencer_email", ""),
                state=state_str,
                round_count=entry.get("round_count", 0),
                counterparty_type=context.get(
                    "counterparty_type", "direct_influencer"
                ),
                agency_name=context.get("agency_name"),
                current_rate=current_rate,
            )
        )

    return CampaignDetailResponse(
        campaign_id=campaign_id,
        negotiations=negotiations,
        total=len(negotiations),
    )


@router.get(
    "/campaigns/{campaign_id}/negotiations/{thread_id}/timeline",
    response_model=TimelineResponse,
)
async def negotiation_timeline(
    campaign_id: str,
    thread_id: str,
    request: Request,
) -> TimelineResponse:
    """Return state transitions and audit trail for a negotiation thread.

    Combines the state machine history with the audit trail entries to
    produce a comprehensive timeline view.
    """
    negotiation_states: dict[str, dict[str, Any]] = getattr(
        request.app.state, "negotiation_states", {}
    )

    entry = negotiation_states.get(thread_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    context = entry.get("context", {})
    if context.get("campaign_id") != campaign_id:
        raise HTTPException(
            status_code=404,
            detail="Thread does not belong to this campaign",
        )

    # State machine history
    state_transitions: list[StateTransition] = []
    state_machine = entry.get("state_machine")
    if state_machine is not None:
        for from_state, event, to_state in state_machine.history:
            state_transitions.append(
                StateTransition(
                    from_state=str(from_state),
                    event=event,
                    to_state=str(to_state),
                )
            )

    # Audit trail entries
    timeline: list[TimelineEntry] = []
    services: dict[str, Any] = getattr(request.app.state, "services", {})
    audit_conn = services.get("audit_conn")
    if audit_conn is not None:
        influencer_name = context.get("influencer_name", "")
        rows = query_audit_trail(
            audit_conn,
            campaign_id=campaign_id,
            influencer_name=influencer_name,
            limit=200,
        )
        for row in rows:
            timeline.append(
                TimelineEntry(
                    timestamp=row.get("timestamp", ""),
                    event_type=row.get("event_type", ""),
                    direction=row.get("direction"),
                    email_body=row.get("email_body"),
                    negotiation_state=row.get("negotiation_state"),
                    rates_used=row.get("rates_used"),
                    metadata=row.get("metadata"),
                )
            )

    influencer_name = context.get("influencer_name", "Unknown")

    return TimelineResponse(
        thread_id=thread_id,
        influencer_name=influencer_name,
        state_transitions=state_transitions,
        timeline=timeline,
    )
