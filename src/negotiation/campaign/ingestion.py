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

from negotiation.campaign.models import (
    BudgetConstraints,
    Campaign,
    CampaignBackground,
    CampaignCPMRange,
    CampaignGoals,
    CampaignInfluencer,
    CampaignRequirements,
    DeliverableScenarios,
    DistributionInfo,
    OptimizeFor,
    ProductLeverage,
    UsageRights,
    UsageRightsDuration,
    UsageRightsSet,
)
from negotiation.domain.types import Platform
from negotiation.resilience.retry import resilient_api_call

logger = structlog.get_logger()

# Default config path relative to project root
_DEFAULT_CONFIG_PATH = Path("config/campaign_fields.yaml")


def load_field_mapping(
    config_path: Path | None = None,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Load the ClickUp custom field to Campaign model field mapping and types.

    Reads the YAML configuration that maps ClickUp form field names to
    Campaign model attribute names. Also returns field type hints for
    type-aware parsing.

    Args:
        config_path: Path to the YAML config file. Defaults to
            ``config/campaign_fields.yaml``.

    Returns:
        A tuple of (field_mapping, field_types) where field_mapping maps
        ClickUp field names to model field names, and field_types maps
        type categories to lists of ClickUp field names.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    path = config_path or _DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Campaign fields config not found: {path}")

    with path.open() as f:
        config = yaml.safe_load(f)

    field_mapping = dict(config.get("field_mapping", {}))
    field_types: dict[str, list[str]] = dict(config.get("field_types", {}))
    return field_mapping, field_types


# Mapping from ClickUp select label to UsageRightsDuration enum
_DURATION_LABEL_MAP: dict[str, UsageRightsDuration] = {
    "30 Days": UsageRightsDuration.days_30,
    "60 Days": UsageRightsDuration.days_60,
    "90 Days": UsageRightsDuration.days_90,
    "6 Months": UsageRightsDuration.months_6,
    "1 Year": UsageRightsDuration.year_1,
    "Perpetual": UsageRightsDuration.perpetual,
    "Not required": UsageRightsDuration.not_required,
}


def parse_boolean(value: Any) -> bool:
    """Convert ClickUp Yes/No and boolean representations to Python bool.

    Handles: True/False booleans, "Yes"/"No" strings (case-insensitive),
    and ClickUp select objects with ``{"name": "Yes"}``.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        value = value.get("name", "")
    if isinstance(value, str):
        return value.strip().lower() in ("yes", "true", "1")
    return bool(value)


def parse_duration_select(value: Any) -> UsageRightsDuration:
    """Map a ClickUp select value to a UsageRightsDuration enum.

    Handles both string labels and ClickUp select objects
    ``{"name": "90 Days", "id": "..."}``.
    """
    label = value.get("name", "") if isinstance(value, dict) else str(value)
    return _DURATION_LABEL_MAP.get(label, UsageRightsDuration.not_required)


def parse_select(value: Any) -> str:
    """Extract the selected option name from a ClickUp select/dropdown field.

    ClickUp select fields return ``{"name": "Option", "id": "123"}``
    or sometimes an integer index.
    """
    if isinstance(value, dict):
        return str(value.get("name", ""))
    return str(value)


def parse_multi_select(value: Any) -> list[str]:
    """Extract option names from a ClickUp multi-select/labels field.

    ClickUp multi-select fields return ``[{"name": "A"}, {"name": "B"}]``.
    """
    if isinstance(value, list):
        return [
            str(item.get("name", "")) if isinstance(item, dict) else str(item) for item in value
        ]
    return [str(value)]


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
    field_types: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Extract custom field values from ClickUp task data.

    Iterates over the task's ``custom_fields`` list and matches each field
    by name against the provided mapping. Handles ClickUp type quirks per
    research pitfall 3: numbers may arrive as strings, dates as Unix
    milliseconds.

    Uses ``field_types`` from the YAML config to apply type-specific parsing
    for select, multi_select, boolean, date_range, and duration_select fields.

    Args:
        task_data: The full task dict from the ClickUp API.
        field_mapping: Mapping of ClickUp field names to model field names.
        field_types: Optional mapping of type categories to lists of ClickUp
            field names. Used for type-aware parsing of select, multi_select,
            boolean, date_range, and duration_select fields.

    Returns:
        A dict mapping Campaign model field names to their extracted values.
        Fields not found in the task data are omitted (not set to None).
    """
    if field_types is None:
        field_types = {}

    custom_fields: list[dict[str, Any]] = task_data.get("custom_fields", [])
    parsed: dict[str, Any] = {}

    # Build reverse lookup: ClickUp field name -> type category
    type_lookup: dict[str, str] = {}
    for type_category, field_names in field_types.items():
        for fname in field_names:
            type_lookup[fname] = type_category

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

        # Determine the type category from config or fall back to ClickUp type
        config_type = type_lookup.get(clickup_name, "")
        field_type = field_data.get("type", "")

        # Type-aware casting based on config field_types
        if config_type == "duration_select":
            value = parse_duration_select(value)
        elif config_type == "select":
            # Check if this is a boolean-like select (Yes/No fields)
            select_name = parse_select(value)
            value = parse_boolean(value) if select_name.lower() in ("yes", "no") else select_name
        elif config_type == "multi_select":
            value = parse_multi_select(value)
        elif config_type == "number":
            if isinstance(value, str):
                with contextlib.suppress(ValueError):
                    value = float(value)
        elif config_type == "date_range":
            # ClickUp date range: {start: unix_ms, end: unix_ms} or single date
            if isinstance(value, dict):
                start_ms = value.get("start")
                end_ms = value.get("end")
                parts = []
                for ms in (start_ms, end_ms):
                    if ms is not None:
                        with contextlib.suppress(ValueError, OverflowError):
                            parts.append(datetime.fromtimestamp(int(ms) / 1000, tz=UTC).isoformat())
                value = " to ".join(parts) if parts else str(value)
            elif isinstance(value, (int, str)):
                try:
                    ts_ms = int(value)
                    value = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).isoformat()
                except (ValueError, OverflowError):
                    pass
        else:
            # Fallback to original ClickUp type-based parsing
            if field_type == "number" and isinstance(value, str):
                with contextlib.suppress(ValueError):
                    value = float(value)
            elif field_type == "date" and isinstance(value, (int, str)):
                try:
                    ts_ms = int(value)
                    value = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).isoformat()
                except (ValueError, OverflowError):
                    pass

        parsed[model_name] = value

    return parsed


def _resolve_dot_paths(flat: dict[str, Any]) -> dict[str, Any]:
    """Resolve dot-separated keys in a flat dict into a nested dict structure.

    Given ``{"goals.primary_goal": "X", "budget_constraints.cpm_target": 25}``,
    produces ``{"goals": {"primary_goal": "X"}, "budget_constraints": {"cpm_target": 25}}``.

    Keys without dots are kept at the top level.

    Args:
        flat: A flat dict potentially containing dot-separated keys.

    Returns:
        A nested dict with dot paths resolved.
    """
    nested: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        target = nested
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
    return nested


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


def _clean_numeric_string(value: str) -> str:
    """Strip currency symbols, commas, and percent signs from numeric strings."""
    return value.replace("$", "").replace(",", "").replace("%", "").strip()


def _decimal_from_field(value: Any, default: str = "0") -> Decimal:
    """Convert a parsed field value to Decimal via string to avoid float rejection."""
    if value is None:
        return Decimal(default)
    cleaned = _clean_numeric_string(str(value))
    if not cleaned:
        return Decimal(default)
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal(default)


def _build_usage_rights(nested: dict[str, Any]) -> UsageRights | None:
    """Build UsageRights from nested dict with target/minimum sub-dicts."""
    ur_data = nested.get("usage_rights")
    if not ur_data or not isinstance(ur_data, dict):
        return None

    target_data = ur_data.get("target", {})
    minimum_data = ur_data.get("minimum", {})

    # If no actual duration values, skip
    if not target_data and not minimum_data:
        return None

    target = UsageRightsSet(**target_data)
    minimum = UsageRightsSet(**minimum_data)
    return UsageRights(target=target, minimum=minimum)


def _build_budget_constraints(nested: dict[str, Any]) -> BudgetConstraints | None:
    """Build BudgetConstraints from nested dict, converting Decimal fields."""
    bc_data = nested.get("budget_constraints")
    if not bc_data or not isinstance(bc_data, dict):
        return None

    # Convert monetary fields to Decimal via string
    decimal_fields = (
        "campaign_budget",
        "min_cost_per_influencer",
        "max_cost_without_approval",
        "cpm_target",
        "cpm_leniency_pct",
    )
    converted = dict(bc_data)
    for field_name in decimal_fields:
        if field_name in converted and converted[field_name] is not None:
            converted[field_name] = _decimal_from_field(converted[field_name])

    # Convert target_influencer_count to int
    if "target_influencer_count" in converted and converted["target_influencer_count"] is not None:
        try:
            converted["target_influencer_count"] = int(
                float(str(converted["target_influencer_count"]))
            )
        except (ValueError, TypeError):
            converted["target_influencer_count"] = None

    # campaign_budget is required; use top-level budget as fallback
    if "campaign_budget" not in converted:
        top_budget = nested.get("budget", "0")
        converted["campaign_budget"] = _decimal_from_field(top_budget)

    return BudgetConstraints(**converted)


def _build_product_leverage(nested: dict[str, Any]) -> ProductLeverage | None:
    """Build ProductLeverage from nested dict."""
    pl_data = nested.get("product_leverage")
    if not pl_data or not isinstance(pl_data, dict):
        return None
    converted = dict(pl_data)
    if "product_monetary_value" in converted and converted["product_monetary_value"] is not None:
        converted["product_monetary_value"] = _decimal_from_field(
            converted["product_monetary_value"]
        )
    return ProductLeverage(**converted)


def _build_deliverable_scenarios(
    nested: dict[str, Any],
    target_deliverables_str: str,
) -> DeliverableScenarios | None:
    """Build DeliverableScenarios from nested dict."""
    ds_data = nested.get("deliverables")
    if not ds_data or not isinstance(ds_data, dict):
        return None
    converted = dict(ds_data)

    # target_deliverables comes as a top-level field (list or string)
    td = nested.get("target_deliverables", target_deliverables_str)
    if isinstance(td, list):
        converted["target_deliverables"] = td
    elif isinstance(td, str):
        converted["target_deliverables"] = [s.strip() for s in td.split(",") if s.strip()]
    else:
        converted["target_deliverables"] = [str(td)]

    return DeliverableScenarios(**converted)


def _build_campaign_goals(nested: dict[str, Any]) -> CampaignGoals | None:
    """Build CampaignGoals from nested dict."""
    goals_data = nested.get("goals")
    if not goals_data or not isinstance(goals_data, dict):
        return None
    if "primary_goal" not in goals_data:
        return None
    converted = dict(goals_data)
    # Map optimize_for string to enum
    if "optimize_for" in converted and isinstance(converted["optimize_for"], str):
        opt_str = converted["optimize_for"].lower().replace(" ", "_")
        try:
            converted["optimize_for"] = OptimizeFor(opt_str)
        except ValueError:
            converted["optimize_for"] = OptimizeFor.balance
    return CampaignGoals(**converted)


def _build_requirements(nested: dict[str, Any]) -> CampaignRequirements | None:
    """Build CampaignRequirements from nested dict."""
    req_data = nested.get("requirements")
    if not req_data or not isinstance(req_data, dict):
        return None
    converted = dict(req_data)
    # Convert revision_rounds to int
    if "revision_rounds" in converted and converted["revision_rounds"] is not None:
        converted["revision_rounds"] = int(converted["revision_rounds"])
    return CampaignRequirements(**converted)


def _derive_timeline(nested: dict[str, Any]) -> str:
    """Derive a timeline string from content delivery/publish date fields."""
    req = nested.get("requirements", {})
    if not isinstance(req, dict):
        return "TBD"
    parts = []
    delivery = req.get("content_delivery_date")
    publish = req.get("content_publish_date")
    if delivery:
        parts.append(f"Delivery: {delivery}")
    if publish:
        parts.append(f"Publish: {publish}")
    return "; ".join(parts) if parts else "TBD"


def build_campaign(task_id: str, parsed_fields: dict[str, Any]) -> Campaign:
    """Construct a Campaign model from parsed ClickUp custom fields.

    Resolves dot-path keys into nested dicts, then constructs all sub-models.
    Converts budget/CPM values to Decimal (string path to avoid float
    rejection). Builds CampaignInfluencer list from parsed influencer names
    with the campaign's platform.

    Backward compatible: if only the original 8 fields are provided,
    all sub-model fields default to None.

    Args:
        task_id: The ClickUp task ID (becomes campaign_id).
        parsed_fields: The parsed custom fields dict from ``parse_custom_fields``.

    Returns:
        A validated Campaign Pydantic model.
    """
    # Resolve dot-path keys into nested structure
    nested = _resolve_dot_paths(parsed_fields)

    # Influencers come from Google Sheet, not ClickUp form
    influencers: list[CampaignInfluencer] = []

    # Derive platform from distribution field (pick highest percentage)
    platform = Platform.INSTAGRAM  # default
    dist_str = str(
        nested.get("distribution", {}).get("platform_distribution", "")
        if isinstance(nested.get("distribution"), dict)
        else ""
    )
    if dist_str:
        dist_lower = dist_str.lower()
        for p in (Platform.YOUTUBE, Platform.TIKTOK, Platform.INSTAGRAM):
            if p.value in dist_lower:
                platform = p
                break

    # Convert monetary values to Decimal via string to avoid float rejection
    budget = _decimal_from_field(nested.get("budget"))
    cpm_min = _decimal_from_field(nested.get("cpm_min"))
    cpm_max = _decimal_from_field(nested.get("cpm_max"))

    # Determine target_deliverables (may be list from multi_select or string)
    td_raw = nested.get("target_deliverables", "TBD")
    target_deliverables_str = ", ".join(td_raw) if isinstance(td_raw, list) else str(td_raw)

    # Client name may be nested under background or at top level
    client_name = str(nested.get("client_name", "Unknown"))

    # Build sub-models (all return None if data insufficient)
    background_data = nested.get("background")
    background = (
        CampaignBackground(**background_data)
        if isinstance(background_data, dict) and background_data
        else None
    )

    goals = _build_campaign_goals(nested)
    deliverables = _build_deliverable_scenarios(nested, target_deliverables_str)
    usage_rights = _build_usage_rights(nested)
    budget_constraints = _build_budget_constraints(nested)
    product_leverage = _build_product_leverage(nested)
    requirements = _build_requirements(nested)

    distribution_data = nested.get("distribution")
    distribution = (
        DistributionInfo(**distribution_data)
        if isinstance(distribution_data, dict) and distribution_data
        else None
    )

    # Per-campaign sheet routing fields (empty strings become None)
    raw_tab = nested.get("influencer_sheet_tab")
    influencer_sheet_tab = raw_tab.strip() or None if isinstance(raw_tab, str) else raw_tab
    raw_sheet_id = nested.get("influencer_sheet_id")
    influencer_sheet_id = (
        raw_sheet_id.strip() or None if isinstance(raw_sheet_id, str) else raw_sheet_id
    )

    return Campaign(
        campaign_id=task_id,
        client_name=client_name,
        budget=budget,
        target_deliverables=target_deliverables_str,
        influencers=influencers,
        cpm_range=CampaignCPMRange(min_cpm=cpm_min, max_cpm=cpm_max),
        platform=platform,
        timeline=_derive_timeline(nested),
        created_at=datetime.now(tz=UTC).isoformat(),
        background=background,
        goals=goals,
        deliverables=deliverables,
        usage_rights=usage_rights,
        budget_constraints=budget_constraints,
        product_leverage=product_leverage,
        requirements=requirements,
        distribution=distribution,
        influencer_sheet_tab=influencer_sheet_tab or None,
        influencer_sheet_id=influencer_sheet_id or None,
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

    # Step 1: Load field mapping and field types
    field_mapping, field_types = load_field_mapping(config_path)

    # Step 2: Fetch full task from ClickUp API
    task_data = await fetch_clickup_task(task_id, api_token)

    # Step 3: Parse custom fields with type-aware casting
    parsed_fields = parse_custom_fields(task_data, field_mapping, field_types)

    # Step 4: Build Campaign model
    campaign = build_campaign(task_id, parsed_fields)

    # Step 5: Look up each influencer in Google Sheet
    found_influencers: list[dict[str, Any]] = []
    missing_influencers: list[str] = []

    # Per-campaign sheet routing: use campaign overrides or defaults
    worksheet_name = campaign.influencer_sheet_tab or "Sheet1"
    spreadsheet_key_override = campaign.influencer_sheet_id or None
    logger.info(
        "Influencer lookup config",
        tab=worksheet_name,
        sheet_override=bool(spreadsheet_key_override),
    )

    # Read ALL influencers from the sheet tab (not from ClickUp form)
    try:
        all_influencers = sheets_client.get_all_influencers(
            worksheet_name=worksheet_name,
            spreadsheet_key_override=spreadsheet_key_override,
        )
        for row in all_influencers:
            found_influencers.append(
                {
                    "name": row.name,
                    "sheet_data": row,
                }
            )
    except (ValueError, Exception) as exc:
        logger.error(
            "Failed to read influencers from sheet",
            tab=worksheet_name,
            error=str(exc),
        )

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
