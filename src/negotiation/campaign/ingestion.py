"""Campaign ingestion pipeline bridging ClickUp form data to the negotiation system.

Fetches full task data from the ClickUp API (per research pitfall 1: webhook
payload may NOT include custom field values), parses custom fields with
type-aware casting (per pitfall 3: numbers may be strings, dates as Unix ms),
builds a ``Campaign`` model, and performs influencer lookup in the Google Sheet.

Per LOCKED DECISION: missing influencers are skipped with a Slack alert asking
the team to add them first. The team receives a Slack notification when campaign
ingestion starts (auto-start with notification).
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml  # type: ignore[import-untyped]

from negotiation.campaign.models import Campaign, CampaignCPMRange, CampaignInfluencer
from negotiation.domain.types import Platform
from negotiation.resilience.retry import resilient_api_call

logger = structlog.get_logger()

# Default config path relative to project root
_DEFAULT_CONFIG_PATH = Path("config/campaign_fields.yaml")


def load_field_mapping(config_path: Path | None = None) -> dict[str, str]:
    """Load the ClickUp custom field to Campaign model field mapping.

    Reads the YAML configuration that maps ClickUp form field names to
    Campaign model attribute names. Follows the same pattern as
    ``escalation_triggers.yaml`` loading.

    Args:
        config_path: Path to the YAML config file. Defaults to
            ``config/campaign_fields.yaml``.

    Returns:
        A dict mapping ClickUp field names to model field names.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    path = config_path or _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Campaign fields config not found: {path}")

    with path.open() as f:
        config = yaml.safe_load(f)

    return dict(config.get("field_mapping", {}))


@resilient_api_call("clickup")
async def fetch_clickup_task(task_id: str, api_token: str) -> dict[str, Any]:
    """Fetch full task data from the ClickUp API.

    Per research pitfall 1: Always follow up a webhook with a GET to fetch
    the full task including custom fields -- the webhook payload may NOT
    include custom field values.

    Args:
        task_id: The ClickUp task ID.
        api_token: The ClickUp API token for authorization.

    Returns:
        The full task data dict from the ClickUp API response.

    Raises:
        httpx.HTTPStatusError: If the API returns a non-2xx status.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.clickup.com/api/v2/task/{task_id}",
            headers={"Authorization": api_token},
            timeout=30.0,
        )
        response.raise_for_status()
        return dict(response.json())


def parse_custom_fields(
    task_data: dict[str, Any],
    field_mapping: dict[str, str],
) -> dict[str, Any]:
    """Extract custom field values from ClickUp task data.

    Iterates over the task's ``custom_fields`` list and matches each field
    by name against the provided mapping. Handles ClickUp type quirks per
    research pitfall 3: numbers may arrive as strings, dates as Unix
    milliseconds.

    Args:
        task_data: The full task dict from the ClickUp API.
        field_mapping: Mapping of ClickUp field names to model field names.

    Returns:
        A dict mapping Campaign model field names to their extracted values.
        Fields not found in the task data are omitted (not set to None).
    """
    custom_fields: list[dict[str, Any]] = task_data.get("custom_fields", [])
    parsed: dict[str, Any] = {}

    # Build a lookup from ClickUp field name -> custom field object
    field_lookup: dict[str, dict[str, Any]] = {}
    for field in custom_fields:
        name = field.get("name", "")
        if name:
            field_lookup[name] = field

    for clickup_name, model_name in field_mapping.items():
        field_data = field_lookup.get(clickup_name)
        if field_data is None:
            continue

        # ClickUp stores the value in "value" for most types
        value = field_data.get("value")
        if value is None:
            continue

        # Type-aware casting for ClickUp quirks
        field_type = field_data.get("type", "")
        if field_type == "number" and isinstance(value, str):
            # ClickUp sometimes sends numbers as strings
            with contextlib.suppress(ValueError):
                value = float(value)
        elif field_type == "date" and isinstance(value, (int, str)):
            # ClickUp dates are Unix milliseconds
            try:
                ts_ms = int(value)
                value = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).isoformat()
            except (ValueError, OverflowError):
                pass

        parsed[model_name] = value

    return parsed


def parse_influencer_list(
    raw_value: str,
    list_format: str = "comma_separated",
) -> list[str]:
    """Split influencer names from a text field.

    Supports comma-separated and newline-separated formats. Strips
    whitespace and filters empty strings.

    Args:
        raw_value: The raw text containing influencer names.
        list_format: Either ``"comma_separated"`` or ``"newline_separated"``.

    Returns:
        A list of cleaned influencer name strings.
    """
    separator = "\n" if list_format == "newline_separated" else ","

    names = raw_value.split(separator)
    return [name.strip() for name in names if name.strip()]


def build_campaign(task_id: str, parsed_fields: dict[str, Any]) -> Campaign:
    """Construct a Campaign model from parsed ClickUp custom fields.

    Converts budget/CPM values to Decimal (string path to avoid float
    rejection). Builds CampaignInfluencer list from parsed influencer names
    with the campaign's platform.

    Args:
        task_id: The ClickUp task ID (becomes campaign_id).
        parsed_fields: The parsed custom fields dict from ``parse_custom_fields``.

    Returns:
        A validated Campaign Pydantic model.
    """
    # Parse influencer names from raw text
    influencers_raw = str(parsed_fields.get("influencers_raw", ""))
    influencer_names = parse_influencer_list(influencers_raw)

    # Determine platform
    platform_str = str(parsed_fields.get("platform", "instagram")).lower()
    try:
        platform = Platform(platform_str)
    except ValueError:
        platform = Platform.INSTAGRAM

    # Build influencer list with platform
    influencers = [CampaignInfluencer(name=name, platform=platform) for name in influencer_names]

    # Convert monetary values to Decimal via string to avoid float rejection
    budget = Decimal(str(parsed_fields.get("budget", "0")))
    cpm_min = Decimal(str(parsed_fields.get("cpm_min", "0")))
    cpm_max = Decimal(str(parsed_fields.get("cpm_max", "0")))

    return Campaign(
        campaign_id=task_id,
        client_name=str(parsed_fields.get("client_name", "Unknown")),
        budget=budget,
        target_deliverables=str(parsed_fields.get("target_deliverables", "TBD")),
        influencers=influencers,
        cpm_range=CampaignCPMRange(min_cpm=cpm_min, max_cpm=cpm_max),
        platform=platform,
        timeline=str(parsed_fields.get("timeline", "TBD")),
        created_at=datetime.now(tz=UTC).isoformat(),
    )


async def ingest_campaign(
    task_id: str,
    api_token: str,
    sheets_client: Any,
    slack_notifier: Any,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Main campaign ingestion orchestration function.

    1. Load field mapping from YAML config.
    2. Fetch full task from ClickUp API.
    3. Parse custom fields with type-aware casting.
    4. Build Campaign model.
    5. Look up each influencer in Google Sheet.
    6. Post Slack notification on campaign start.
    7. Post individual Slack alerts for missing influencers.

    Note: This function does NOT start the actual negotiation loop -- that
    wiring happens in Plan 04 (app.py). This builds the ingestion pipeline
    up to having campaign + influencer data ready.

    Args:
        task_id: The ClickUp task ID from the webhook event.
        api_token: The ClickUp API token.
        sheets_client: A SheetsClient instance for influencer lookup.
        slack_notifier: A SlackNotifier instance for team notifications.
        config_path: Optional path to campaign_fields.yaml.

    Returns:
        A dict with ``campaign``, ``found_influencers``, and
        ``missing_influencers`` keys.
    """
    logger.info("Starting campaign ingestion", task_id=task_id)

    # Step 1: Load field mapping
    field_mapping = load_field_mapping(config_path)

    # Step 2: Fetch full task from ClickUp API
    task_data = await fetch_clickup_task(task_id, api_token)

    # Step 3: Parse custom fields
    parsed_fields = parse_custom_fields(task_data, field_mapping)

    # Step 4: Build Campaign model
    campaign = build_campaign(task_id, parsed_fields)

    # Step 5: Look up each influencer in Google Sheet
    found_influencers: list[dict[str, Any]] = []
    missing_influencers: list[str] = []

    for influencer in campaign.influencers:
        try:
            sheet_data = sheets_client.find_influencer(influencer.name)
            found_influencers.append(
                {
                    "name": influencer.name,
                    "sheet_data": sheet_data,
                }
            )
        except ValueError:
            missing_influencers.append(influencer.name)

    logger.info(
        "Influencer lookup complete",
        task_id=task_id,
        found=len(found_influencers),
        missing=len(missing_influencers),
    )

    # Step 6: Post Slack notification that campaign ingestion started
    if slack_notifier is not None:
        slack_notifier.post_escalation(
            blocks=[
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Campaign Ingestion Started: {campaign.client_name}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Campaign:*\n{campaign.client_name}"},
                        {"type": "mrkdwn", "text": f"*Platform:*\n{campaign.platform.value}"},
                        {
                            "type": "mrkdwn",
                            "text": (
                                f"*Influencers Found:*\n"
                                f"{len(found_influencers)}/{len(campaign.influencers)}"
                            ),
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Missing:*\n{len(missing_influencers)}",
                        },
                    ],
                },
            ],
            fallback_text=(
                f"Campaign ingestion started for {campaign.client_name}: "
                f"{len(found_influencers)} found, {len(missing_influencers)} missing"
            ),
        )

    # Step 7: Post individual Slack alerts for each missing influencer
    for name in missing_influencers:
        if slack_notifier is not None:
            slack_notifier.post_escalation(
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*Missing Influencer:* {name}\n"
                                f"*Campaign:* {campaign.client_name}\n"
                                "Please add this influencer to the Google Sheet "
                                "so negotiations can begin."
                            ),
                        },
                    },
                ],
                fallback_text=(
                    f"Missing influencer '{name}' for campaign "
                    f"'{campaign.client_name}'. Please add to Google Sheet."
                ),
            )

    return {
        "campaign": campaign,
        "found_influencers": found_influencers,
        "missing_influencers": missing_influencers,
    }
