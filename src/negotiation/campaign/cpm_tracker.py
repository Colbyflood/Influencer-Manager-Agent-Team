"""Campaign CPM tracker with engagement-quality-weighted flexibility.

Tracks agreed CPMs across a campaign and calculates per-influencer flexibility
considering both the running campaign average AND engagement quality.

Per locked decision: Flexibility must consider engagement quality, NOT just
campaign averaging alone.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CPMFlexibility:
    """Result of a CPM flexibility calculation.

    Attributes:
        target_cpm: The base target CPM for this influencer.
        max_allowed_cpm: The maximum CPM we can offer, including any premium.
        reason: Human-readable explanation of the flexibility decision.
    """

    target_cpm: Decimal
    max_allowed_cpm: Decimal
    reason: str


class CampaignCPMTracker:
    """Tracks CPM agreements across a campaign and calculates flexibility.

    Flexibility rules:
    - High engagement (>5%): up to 15% CPM premium
    - Moderate engagement (>3%): up to 8% CPM premium
    - No/low engagement data: no premium
    - Hard cap: never exceed 120% of target max CPM
    - Running average influences base flexibility (under budget = more room)
    """

    def __init__(
        self,
        campaign_id: str,
        target_min_cpm: Decimal,
        target_max_cpm: Decimal,
        total_influencers: int,
    ) -> None:
        """Initialize the CPM tracker.

        Args:
            campaign_id: The campaign identifier.
            target_min_cpm: The minimum target CPM for the campaign.
            target_max_cpm: The maximum target CPM for the campaign.
            total_influencers: Total number of influencers in the campaign.
        """
        self.campaign_id = campaign_id
        self.target_min_cpm = target_min_cpm
        self.target_max_cpm = target_max_cpm
        self.total_influencers = total_influencers
        self._agreements: list[tuple[Decimal, float | None]] = []

    def record_agreement(
        self, cpm: Decimal, engagement_rate: float | None = None,
    ) -> None:
        """Record a CPM agreement for an influencer.

        Args:
            cpm: The agreed CPM value.
            engagement_rate: The influencer's engagement rate (optional).
        """
        self._agreements.append((cpm, engagement_rate))

    @property
    def running_average_cpm(self) -> Decimal | None:
        """Calculate the running average CPM across all agreements.

        Returns:
            The average CPM as Decimal, or None if no agreements yet.
        """
        if not self._agreements:
            return None
        total = sum((cpm for cpm, _ in self._agreements), Decimal("0"))
        return total / len(self._agreements)

    def get_flexibility(
        self, influencer_engagement_rate: float | None = None,
    ) -> CPMFlexibility:
        """Calculate CPM flexibility for an influencer.

        Considers running campaign average and engagement quality to determine
        how much above target CPM we can go.

        Args:
            influencer_engagement_rate: The influencer's engagement rate (optional).

        Returns:
            CPMFlexibility with target CPM, max allowed CPM, and reasoning.
        """
        # Start with target max as the base
        base_cpm = self.target_max_cpm

        # Calculate budget flexibility from running average
        budget_premium = Decimal("0")
        avg = self.running_average_cpm
        if avg is not None and avg < self.target_max_cpm:
            # Running average is below target -- we have room
            savings = self.target_max_cpm - avg
            remaining = self.total_influencers - len(self._agreements)
            if remaining > 0:
                # Distribute savings across remaining influencers
                budget_premium = savings * Decimal(str(len(self._agreements))) / Decimal(
                    str(remaining)
                )

        # Calculate engagement premium
        engagement_premium = Decimal("0")
        engagement_desc = "no engagement data"
        if influencer_engagement_rate is not None:
            if influencer_engagement_rate > 5.0:
                engagement_premium = self.target_max_cpm * Decimal("0.15")
                engagement_desc = f"high engagement ({influencer_engagement_rate}% > 5%): +15%"
            elif influencer_engagement_rate > 3.0:
                engagement_premium = self.target_max_cpm * Decimal("0.08")
                engagement_desc = (
                    f"moderate engagement ({influencer_engagement_rate}% > 3%): +8%"
                )
            else:
                engagement_desc = f"low engagement ({influencer_engagement_rate}%): no premium"

        # Combine premiums
        max_allowed = base_cpm + budget_premium + engagement_premium

        # Hard cap: never exceed 120% of target max
        hard_cap = self.target_max_cpm * Decimal("1.20")
        if max_allowed > hard_cap:
            max_allowed = hard_cap

        reason = self._build_reason(
            budget_premium=budget_premium,
            engagement_premium=engagement_premium,
            engagement_desc=engagement_desc,
            max_allowed=max_allowed,
            hard_cap=hard_cap,
            capped=max_allowed == hard_cap and (budget_premium + engagement_premium) > Decimal("0"),
        )

        return CPMFlexibility(
            target_cpm=self.target_max_cpm,
            max_allowed_cpm=max_allowed,
            reason=reason,
        )

    @staticmethod
    def _build_reason(
        *,
        budget_premium: Decimal,
        engagement_premium: Decimal,
        engagement_desc: str,
        max_allowed: Decimal,
        hard_cap: Decimal,
        capped: bool,
    ) -> str:
        """Build a human-readable explanation of the flexibility decision.

        Args:
            budget_premium: Extra CPM from budget savings.
            engagement_premium: Extra CPM from engagement quality.
            engagement_desc: Description of engagement tier.
            max_allowed: Final max allowed CPM.
            hard_cap: The 120% hard cap value.
            capped: Whether the hard cap was applied.

        Returns:
            A clear explanation string for audit trail and team transparency.
        """
        parts: list[str] = []

        if budget_premium > 0:
            parts.append(f"budget savings: +${budget_premium:.2f}")

        parts.append(engagement_desc)

        if capped:
            parts.append(f"capped at 120% of target max (${hard_cap:.2f})")

        parts.append(f"max allowed: ${max_allowed:.2f}")

        return "; ".join(parts)
