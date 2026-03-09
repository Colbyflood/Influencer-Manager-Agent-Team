"""Campaign list API endpoint with per-campaign status aggregation.

Provides GET /campaigns returning structured campaign summary data
derived from the in-memory negotiation_states dict and CampaignCPMTracker
instances.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from negotiation.domain.types import NegotiationState

router = APIRouter()

# States considered "active" (in-progress negotiations)
_ACTIVE_STATES = frozenset(
    {
        NegotiationState.INITIAL_OFFER,
        NegotiationState.AWAITING_REPLY,
        NegotiationState.COUNTER_RECEIVED,
        NegotiationState.COUNTER_SENT,
    }
)


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class CampaignStatusCounts(BaseModel):
    """Per-campaign negotiation status counts."""

    active_negotiations: int
    agreed: int
    escalated: int
    rejected: int
    total_influencers: int


class CampaignMetrics(BaseModel):
    """Per-campaign computed metrics."""

    avg_cpm_achieved: float | None
    pct_closed: float
    budget_utilization: float | None


class CampaignSummary(BaseModel):
    """Summary of a single campaign including status counts and metrics."""

    campaign_id: str
    client_name: str
    platform: str
    budget: float
    status_counts: CampaignStatusCounts
    metrics: CampaignMetrics


class CampaignListResponse(BaseModel):
    """Response model for the campaign list endpoint."""

    campaigns: list[CampaignSummary]
    total: int


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/campaigns", response_model=CampaignListResponse)
async def list_campaigns(request: Request) -> CampaignListResponse:
    """Return all campaigns with per-campaign status counts and metrics.

    Aggregates data from the in-memory negotiation_states dict, grouping
    negotiations by campaign_id and computing status counts, average CPM,
    percent closed, and budget utilization for each campaign.
    """
    negotiation_states: dict[str, dict[str, Any]] = getattr(
        request.app.state, "negotiation_states", {}
    )

    if not negotiation_states:
        return CampaignListResponse(campaigns=[], total=0)

    # Group negotiations by campaign_id
    by_campaign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _thread_id, entry in negotiation_states.items():
        context = entry.get("context", {})
        campaign_id = context.get("campaign_id", "unknown")
        by_campaign[campaign_id].append(entry)

    summaries: list[CampaignSummary] = []

    for campaign_id, entries in by_campaign.items():
        # Count states
        active = 0
        agreed = 0
        escalated = 0
        rejected = 0

        for entry in entries:
            state_machine = entry.get("state_machine")
            if state_machine is None:
                continue
            current_state = state_machine.state
            if current_state in _ACTIVE_STATES:
                active += 1
            elif current_state == NegotiationState.AGREED:
                agreed += 1
            elif current_state == NegotiationState.ESCALATED:
                escalated += 1
            elif current_state == NegotiationState.REJECTED:
                rejected += 1

        total_influencers = len(entries)
        status_counts = CampaignStatusCounts(
            active_negotiations=active,
            agreed=agreed,
            escalated=escalated,
            rejected=rejected,
            total_influencers=total_influencers,
        )

        # Compute pct_closed
        pct_closed = 0.0
        if total_influencers > 0:
            pct_closed = (agreed + rejected) / total_influencers * 100

        # Extract avg_cpm from CampaignCPMTracker
        avg_cpm: float | None = None
        first_entry = entries[0]
        cpm_tracker = first_entry.get("cpm_tracker")
        if cpm_tracker is not None:
            running_avg = cpm_tracker.running_average_cpm
            if running_avg is not None:
                avg_cpm = float(running_avg)

        # Budget utilization from tracker agreements vs campaign budget
        budget_utilization: float | None = None
        campaign_obj = first_entry.get("campaign")
        if cpm_tracker is not None and campaign_obj is not None:
            campaign_budget = campaign_obj.budget
            if campaign_budget > Decimal("0"):
                sum_agreed = sum(
                    (cpm for cpm, _ in cpm_tracker._agreements),
                    Decimal("0"),
                )
                budget_utilization = float(sum_agreed / campaign_budget * 100)

        metrics = CampaignMetrics(
            avg_cpm_achieved=avg_cpm,
            pct_closed=pct_closed,
            budget_utilization=budget_utilization,
        )

        # Campaign info from the Campaign model
        client_name = "Unknown"
        platform = "unknown"
        budget = 0.0
        if campaign_obj is not None:
            client_name = campaign_obj.client_name
            platform = str(campaign_obj.platform)
            budget = float(campaign_obj.budget)

        summaries.append(
            CampaignSummary(
                campaign_id=campaign_id,
                client_name=client_name,
                platform=platform,
                budget=budget,
                status_counts=status_counts,
                metrics=metrics,
            )
        )

    return CampaignListResponse(campaigns=summaries, total=len(summaries))
