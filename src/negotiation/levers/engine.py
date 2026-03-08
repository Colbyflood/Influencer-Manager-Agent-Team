"""Deterministic lever selection engine for influencer negotiations.

Selects the appropriate negotiation tactic based on campaign data, current
negotiation state, and pricing context. No LLM calls -- pure business logic.

Lever priority order (from Phase 14 KB decision [14-01]):
  1. Cost floor enforcement (NEG-12)
  2. Cost ceiling escalation (NEG-12)
  3. Trade deliverables (NEG-09)
  4. Trade usage rights (NEG-10)
  5. Offer product (NEG-11)
  6. Propose syndication (NEG-14)
  7. Share CPM target (NEG-13)
  8. Graceful exit (NEG-15)

Opening high (NEG-08) is handled by build_opening_context(), called by the
orchestrator before the first negotiation round.
"""

from decimal import Decimal

from negotiation.campaign.models import Campaign
from negotiation.levers.models import LeverAction, LeverResult, NegotiationLeverContext
from negotiation.pricing.engine import calculate_rate, derive_cpm_bounds


def select_lever(ctx: NegotiationLeverContext) -> LeverResult:
    """Select the best negotiation lever for the current context.

    Evaluates levers in strict priority order and returns the first applicable
    action. Every code path returns a LeverResult -- there is no fall-through.

    Args:
        ctx: Current negotiation state including rates, campaign data, and
            which levers have already been used.

    Returns:
        LeverResult with the selected action, adjusted rate (if applicable),
        and natural language instructions for the email composer.
    """
    bc = ctx.budget_constraints

    # --- 1. Cost floor check (NEG-12) ---
    if bc and bc.min_cost_per_influencer is not None:
        if ctx.our_current_rate < bc.min_cost_per_influencer:
            return LeverResult(
                action=LeverAction.enforce_floor,
                adjusted_rate=bc.min_cost_per_influencer,
                lever_instructions=(
                    "We are at our absolute minimum for this campaign. "
                    "Frame this as the best we can offer given the campaign parameters."
                ),
            )

    # --- 2. Cost ceiling check (NEG-12) ---
    if bc and bc.max_cost_without_approval is not None:
        if ctx.their_rate > bc.max_cost_without_approval:
            return LeverResult(
                action=LeverAction.escalate_ceiling,
                should_escalate=True,
                lever_instructions=(
                    "This rate exceeds our approval threshold. "
                    "Escalate to campaign manager for approval."
                ),
            )

    # --- 3. Trade deliverables (NEG-09) ---
    ds = ctx.deliverable_scenarios
    if ctx.current_scenario < 3 and ds is not None:
        next_scenario = ctx.current_scenario + 1
        next_text = getattr(ds, f"scenario_{next_scenario}", None)
        if next_text is not None:
            # Recalculate rate at current CPM for the reduced deliverables
            adjusted_rate = _recalculate_rate_for_scenario(ctx)
            return LeverResult(
                action=LeverAction.trade_deliverables,
                adjusted_rate=adjusted_rate,
                deliverables_summary=next_text,
                lever_instructions=(
                    f"We're adjusting the deliverable package to {next_text}. "
                    "Frame this as streamlining the content scope while "
                    "maintaining quality."
                ),
            )

    # --- 4. Trade usage rights (NEG-10) ---
    ur = ctx.usage_rights
    if ctx.current_usage_tier == "target" and ur is not None:
        if _usage_rights_differ(ur):
            min_summary = _format_usage_rights_minimum(ur)
            return LeverResult(
                action=LeverAction.trade_usage_rights,
                adjusted_rate=ctx.our_current_rate,
                usage_rights_summary=min_summary,
                lever_instructions=(
                    f"We're reducing usage rights duration to {min_summary}. "
                    "Position this as a cost-saving adjustment while keeping "
                    "the content partnership intact."
                ),
            )

    # --- 5. Offer product (NEG-11) ---
    pl = ctx.product_leverage
    if pl is not None and pl.product_available and not ctx.product_offered:
        desc = pl.product_description or "product"
        value = pl.product_monetary_value or Decimal("0")
        return LeverResult(
            action=LeverAction.offer_product,
            adjusted_rate=ctx.our_current_rate,
            lever_instructions=(
                f"In addition to the rate, mention that we can provide "
                f"{desc} valued at ${value}. "
                "Frame this as added value, not a rate replacement."
            ),
        )

    # --- 6. Propose syndication (NEG-14) ---
    if ds is not None and ds.content_syndication and not ctx.syndication_proposed:
        return LeverResult(
            action=LeverAction.propose_syndication,
            adjusted_rate=ctx.our_current_rate,
            lever_instructions=(
                "Propose cross-posting content (e.g., IG to TikTok) rather "
                "than unique content per platform. Frame this as maximizing "
                "content reach with less production effort."
            ),
        )

    # --- 7. Share CPM target (NEG-13) ---
    if bc is not None and bc.cpm_target is not None and not ctx.cpm_shared:
        return LeverResult(
            action=LeverAction.share_cpm_target,
            adjusted_rate=ctx.our_current_rate,
            lever_instructions=(
                f"Share that our CPM target is ${bc.cpm_target} to justify "
                "the budget constraint. Use this selectively -- only with "
                "motivated influencers who seem engaged but stuck on rate."
            ),
        )

    # --- 8. Graceful exit (NEG-15) ---
    return LeverResult(
        action=LeverAction.graceful_exit,
        should_exit=True,
        lever_instructions=(
            "The deal economics don't work for this campaign. Send a warm, "
            "relationship-preserving exit. Express genuine appreciation, "
            "leave the door open for future campaigns, and wish them well."
        ),
    )


def build_opening_context(
    campaign: Campaign,
    average_views: int,
) -> tuple[Decimal, str]:
    """Build the opening negotiation position (NEG-08).

    Returns the opening rate (at CPM floor) and scenario_1 deliverables text
    for the first outreach email.

    Args:
        campaign: The campaign with deliverable scenarios and budget constraints.
        average_views: Average view count for the influencer.

    Returns:
        Tuple of (opening_rate, deliverables_text).
    """
    # Determine CPM floor
    cpm_floor = _get_cpm_floor(campaign)

    # Calculate rate at CPM floor
    opening_rate = calculate_rate(average_views, cpm_floor)

    # Get scenario_1 deliverables text, fall back to target_deliverables
    if campaign.deliverables is not None and campaign.deliverables.scenario_1 is not None:
        deliverables_text = campaign.deliverables.scenario_1
    else:
        deliverables_text = campaign.target_deliverables

    return (opening_rate, deliverables_text)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_cpm_floor(campaign: Campaign) -> Decimal:
    """Extract CPM floor from campaign data.

    Priority: budget_constraints.cpm_target > cpm_range.min_cpm > default.
    """
    if campaign.budget_constraints and campaign.budget_constraints.cpm_target is not None:
        cpm_floor, _ = derive_cpm_bounds(
            campaign.budget_constraints.cpm_target,
            campaign.budget_constraints.cpm_leniency_pct,
        )
        return cpm_floor
    return campaign.cpm_range.min_cpm


def _recalculate_rate_for_scenario(ctx: NegotiationLeverContext) -> Decimal:
    """Recalculate rate at current CPM for reduced deliverables.

    Uses our_current_rate as the base -- the actual CPM stays the same,
    but the rate may be adjusted proportionally in future iterations.
    For now, we keep the current rate as the adjusted rate since CPM
    is views-based, not deliverable-count-based.
    """
    return ctx.our_current_rate


def _usage_rights_differ(ur: "UsageRights") -> bool:
    """Check if target and minimum usage rights differ for any right type."""
    for field_name in ("paid_usage", "whitelisting", "organic_owned"):
        target_val = getattr(ur.target, field_name)
        min_val = getattr(ur.minimum, field_name)
        if target_val != min_val:
            return True
    return False


def _format_usage_rights_minimum(ur: "UsageRights") -> str:
    """Format minimum usage rights as a readable summary."""
    parts = []
    for field_name, label in [
        ("paid_usage", "paid usage"),
        ("whitelisting", "whitelisting"),
        ("organic_owned", "organic/owned"),
    ]:
        val = getattr(ur.minimum, field_name)
        if val != "not_required":
            parts.append(f"{label}: {val.replace('_', ' ')}")
    if not parts:
        return "no usage rights required"
    return ", ".join(parts)
