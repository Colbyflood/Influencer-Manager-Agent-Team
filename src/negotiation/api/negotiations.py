"""Campaign detail, timeline, and negotiation control API endpoints.

Provides:
- GET /campaigns/{campaign_id}/negotiations — per-influencer negotiation data
- GET /campaigns/{campaign_id}/negotiations/{thread_id}/timeline — state
  transitions and audit trail for a specific negotiation thread
- POST /campaigns/{campaign_id}/negotiations/{thread_id}/pause — pause a negotiation
- POST /campaigns/{campaign_id}/negotiations/{thread_id}/resume — resume a paused negotiation
- POST /campaigns/{campaign_id}/negotiations/{thread_id}/stop — permanently stop a negotiation
- POST /negotiations/stop-by-agency — bulk stop all negotiations for an agency
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from negotiation.audit.store import query_audit_trail
from negotiation.domain.types import NegotiationState
from negotiation.state_machine.transitions import TERMINAL_STATES

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


class ControlResponse(BaseModel):
    """Response model for negotiation control actions (pause/resume/stop)."""

    thread_id: str
    action: str
    previous_state: str
    new_state: str


class BulkStopRequest(BaseModel):
    """Request body for bulk stop-by-agency."""

    agency_name: str


class BulkStopResponse(BaseModel):
    """Response model for bulk stop-by-agency."""

    agency_name: str
    stopped_count: int
    thread_ids: list[str]


# ---------------------------------------------------------------------------
# Helper: look up thread and verify campaign membership
# ---------------------------------------------------------------------------


def _get_thread_entry(
    request: Request,
    campaign_id: str,
    thread_id: str,
) -> dict[str, Any]:
    """Retrieve a negotiation thread entry, raising 404 on missing/mismatch."""
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
    return entry


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


# ---------------------------------------------------------------------------
# Control endpoints: pause / resume / stop / stop-by-agency
# ---------------------------------------------------------------------------


@router.post(
    "/campaigns/{campaign_id}/negotiations/{thread_id}/pause",
    response_model=ControlResponse,
)
async def pause_negotiation(
    campaign_id: str,
    thread_id: str,
    request: Request,
) -> ControlResponse:
    """Pause an active negotiation thread."""
    entry = _get_thread_entry(request, campaign_id, thread_id)
    state_machine = entry["state_machine"]

    if state_machine.is_terminal or state_machine.state == NegotiationState.PAUSED:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot pause negotiation in state '{state_machine.state.value}'",
        )

    previous = state_machine.state.value
    state_machine.pause()
    return ControlResponse(
        thread_id=thread_id,
        action="paused",
        previous_state=previous,
        new_state=state_machine.state.value,
    )


@router.post(
    "/campaigns/{campaign_id}/negotiations/{thread_id}/resume",
    response_model=ControlResponse,
)
async def resume_negotiation(
    campaign_id: str,
    thread_id: str,
    request: Request,
) -> ControlResponse:
    """Resume a previously paused negotiation thread."""
    entry = _get_thread_entry(request, campaign_id, thread_id)
    state_machine = entry["state_machine"]

    if state_machine.state != NegotiationState.PAUSED:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot resume negotiation in state '{state_machine.state.value}' (must be paused)",
        )

    previous = state_machine.state.value
    state_machine.resume()
    return ControlResponse(
        thread_id=thread_id,
        action="resumed",
        previous_state=previous,
        new_state=state_machine.state.value,
    )


@router.post(
    "/campaigns/{campaign_id}/negotiations/{thread_id}/stop",
    response_model=ControlResponse,
)
async def stop_negotiation(
    campaign_id: str,
    thread_id: str,
    request: Request,
) -> ControlResponse:
    """Permanently stop a negotiation thread."""
    entry = _get_thread_entry(request, campaign_id, thread_id)
    state_machine = entry["state_machine"]

    if state_machine.is_terminal:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot stop negotiation in terminal state '{state_machine.state.value}'",
        )

    previous = state_machine.state.value
    state_machine.stop()
    return ControlResponse(
        thread_id=thread_id,
        action="stopped",
        previous_state=previous,
        new_state=state_machine.state.value,
    )


@router.post(
    "/negotiations/stop-by-agency",
    response_model=BulkStopResponse,
)
async def stop_by_agency(
    body: BulkStopRequest,
    request: Request,
) -> BulkStopResponse:
    """Bulk stop all non-terminal negotiations belonging to an agency."""
    negotiation_states: dict[str, dict[str, Any]] = getattr(
        request.app.state, "negotiation_states", {}
    )

    stopped_ids: list[str] = []
    for tid, entry in negotiation_states.items():
        context = entry.get("context", {})
        if context.get("agency_name") != body.agency_name:
            continue
        sm = entry.get("state_machine")
        if sm is None or sm.is_terminal:
            continue
        sm.stop()
        stopped_ids.append(tid)

    return BulkStopResponse(
        agency_name=body.agency_name,
        stopped_count=len(stopped_ids),
        thread_ids=stopped_ids,
    )
