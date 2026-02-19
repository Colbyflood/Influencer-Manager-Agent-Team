"""Application entry point combining FastAPI webhooks and Slack Bolt Socket Mode.

Runs both the ClickUp webhook server (FastAPI on HTTP) and the Slack Bolt
handler (Socket Mode WebSocket) concurrently in a single long-running process.

Configures:
- **structlog** with JSON rendering (production) or colored console (development)
- **Audit logging** wired into all pipeline operations via wrapper functions
- **Retry logic** for all external APIs with Slack #errors notification
- **Slash commands** (/audit, /claim, /resume) on the Slack Bolt app
- **Gmail Pub/Sub** push notifications for inbound email processing
- **SlackDispatcher** for pre-check gates and negotiation result dispatch
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, Request

from negotiation.audit.logger import AuditLogger
from negotiation.audit.slack_commands import register_audit_command
from negotiation.audit.store import close_audit_db, init_audit_db
from negotiation.audit.wiring import wire_audit_to_campaign_ingestion
from negotiation.campaign.ingestion import ingest_campaign
from negotiation.campaign.models import Campaign
from negotiation.campaign.webhook import router as webhook_router
from negotiation.campaign.webhook import set_campaign_processor
from negotiation.config import Settings, get_settings, validate_credentials
from negotiation.domain.types import NegotiationState
from negotiation.health import register_health_routes
from negotiation.resilience.retry import configure_error_notifier
from negotiation.slack.app import create_slack_app, start_slack_app
from negotiation.slack.commands import register_commands
from negotiation.slack.takeover import ThreadStateManager
from negotiation.state.schema import init_negotiation_state_table
from negotiation.state.serializers import (
    deserialize_context,
    deserialize_cpm_tracker,
    serialize_cpm_tracker,
)
from negotiation.state.store import NegotiationStateStore
from negotiation.state_machine import NegotiationStateMachine

logger = structlog.get_logger()


def configure_logging(production: bool = False) -> None:
    """Configure structlog for production (JSON) or development (console).

    Production mode (*production=True*): JSON rendering at INFO level.
    Development mode: colored console rendering at DEBUG level.

    Args:
        production: Enable production mode if ``True``.
    """
    is_production = production

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
        log_level = logging.INFO
    else:
        renderer = structlog.dev.ConsoleRenderer()
        log_level = logging.DEBUG

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.bind_contextvars(service="negotiation-agent")


def initialize_services(settings: Settings | None = None) -> dict[str, Any]:
    """Set up all shared services for the application.

    Creates the audit database, AuditLogger, SlackNotifier (if credentials
    available), error notifier, SheetsClient (if credentials available),
    GmailClient (if token available), Anthropic client (if API key available),
    SlackDispatcher (if Slack available), registers slash commands, and wires
    audit logging into pipeline functions.

    Args:
        settings: Application settings.  If ``None``, ``get_settings()`` is used.

    Returns:
        A dict of initialized service instances keyed by name.
    """
    if settings is None:
        settings = get_settings()

    services: dict[str, Any] = {}

    # a. Initialize SQLite audit database
    audit_db_path = settings.audit_db_path
    audit_db_path.parent.mkdir(parents=True, exist_ok=True)
    audit_conn = init_audit_db(audit_db_path)
    services["audit_conn"] = audit_conn

    # Initialize negotiation state table on same audit DB connection
    init_negotiation_state_table(audit_conn)
    state_store = NegotiationStateStore(audit_conn)
    services["state_store"] = state_store

    # b. Create AuditLogger
    audit_logger = AuditLogger(audit_conn)
    services["audit_logger"] = audit_logger

    # c. Create SlackNotifier (if slack_bot_token available)
    slack_notifier = None
    slack_bot_token = settings.slack_bot_token.get_secret_value() or None
    if slack_bot_token:
        try:
            from negotiation.slack.client import SlackNotifier

            slack_notifier = SlackNotifier(
                escalation_channel=settings.slack_escalation_channel,
                agreement_channel=settings.slack_agreement_channel,
                bot_token=slack_bot_token,
            )
            logger.info("SlackNotifier initialized")
        except Exception:
            logger.warning("Failed to initialize SlackNotifier", exc_info=True)
    else:
        logger.info("SLACK_BOT_TOKEN not set, SlackNotifier disabled")
    services["slack_notifier"] = slack_notifier

    # d. Configure resilience error notifier
    if slack_notifier is not None:
        configure_error_notifier(slack_notifier)
        logger.info("Error notifier configured for retry exhaustion alerts")

    # e. Create SheetsClient (if credentials available)
    sheets_client = None
    sheets_key = settings.google_sheets_key or None
    if sheets_key:
        try:
            from negotiation.auth.credentials import get_sheets_client
            from negotiation.sheets.client import SheetsClient

            gc = get_sheets_client(
                service_account_path=settings.sheets_service_account_path,
            )
            sheets_client = SheetsClient(gc, sheets_key)
            logger.info("SheetsClient initialized")
        except Exception:
            logger.warning("Failed to initialize SheetsClient", exc_info=True)
    else:
        logger.info("GOOGLE_SHEETS_KEY not set, SheetsClient disabled")
    services["sheets_client"] = sheets_client

    # f. Create Slack Bolt app and register commands
    bolt_app = None
    if slack_bot_token:
        try:
            bolt_app = create_slack_app(bot_token=slack_bot_token)
            logger.info("Slack Bolt app created")
        except Exception:
            logger.warning("Failed to create Slack Bolt app", exc_info=True)
    services["bolt_app"] = bolt_app

    # Create ThreadStateManager before SlackDispatcher (used independently of Bolt)
    thread_state_manager = ThreadStateManager()
    services["thread_state_manager"] = thread_state_manager

    if bolt_app is not None:
        # Register audit command
        register_audit_command(bolt_app, audit_conn)
        logger.info("Registered /audit slash command")

        # Register /claim and /resume commands
        register_commands(bolt_app, thread_state_manager)
        logger.info("Registered /claim and /resume slash commands")

    # g. GmailClient (if gmail token file exists)
    gmail_client = None
    if settings.gmail_token_path.exists():
        try:
            from negotiation.auth.credentials import get_gmail_service
            from negotiation.email.client import GmailClient

            service = get_gmail_service()
            gmail_client = GmailClient(service, settings.agent_email)
            logger.info("GmailClient initialized")
        except Exception:
            logger.warning("Failed to initialize GmailClient", exc_info=True)
    else:
        logger.info("Gmail token file not found, GmailClient disabled")
    services["gmail_client"] = gmail_client

    # h. Anthropic client (if anthropic_api_key is set)
    anthropic_client = None
    if settings.anthropic_api_key.get_secret_value():
        try:
            from negotiation.llm.client import get_anthropic_client

            anthropic_client = get_anthropic_client()
            logger.info("Anthropic client initialized")
        except Exception:
            logger.warning("Failed to initialize Anthropic client", exc_info=True)
    else:
        logger.info("ANTHROPIC_API_KEY not set, Anthropic client disabled")
    services["anthropic_client"] = anthropic_client

    # i. SlackDispatcher (if slack_notifier AND thread_state_manager available)
    slack_dispatcher = None
    if slack_notifier is not None and thread_state_manager is not None:
        try:
            from negotiation.slack.dispatcher import SlackDispatcher
            from negotiation.slack.triggers import load_triggers_config

            triggers_config = load_triggers_config()
            slack_dispatcher = SlackDispatcher(
                notifier=slack_notifier,
                thread_state_manager=thread_state_manager,
                triggers_config=triggers_config,
                agent_email=settings.agent_email,
            )
            logger.info("SlackDispatcher initialized")
        except Exception:
            logger.warning("Failed to initialize SlackDispatcher", exc_info=True)
    else:
        logger.info("SlackNotifier or ThreadStateManager unavailable, SlackDispatcher disabled")
    services["slack_dispatcher"] = slack_dispatcher

    # j. In-memory negotiation state store
    negotiation_states: dict[str, dict[str, Any]] = {}
    services["negotiation_states"] = negotiation_states

    # Startup recovery: load non-terminal negotiations from SQLite
    active_rows = state_store.load_active()
    for row in active_rows:
        thread_id = row["thread_id"]
        # Reconstruct history as list of (NegotiationState, str, NegotiationState) tuples
        history_raw = json.loads(row["history_json"])
        history_tuples: list[tuple[NegotiationState, str, NegotiationState]] = [
            (NegotiationState(h[0]), h[1], NegotiationState(h[2])) for h in history_raw
        ]
        state_machine = NegotiationStateMachine.from_snapshot(
            NegotiationState(row["state"]),
            history_tuples,
        )
        context = deserialize_context(row["context_json"])
        campaign_obj = Campaign.model_validate_json(row["campaign_json"])
        cpm_tracker = deserialize_cpm_tracker(json.loads(row["cpm_tracker_json"]))

        negotiation_states[thread_id] = {
            "state_machine": state_machine,
            "context": context,
            "round_count": row["round_count"],
            "campaign": campaign_obj,
            "cpm_tracker": cpm_tracker,
        }
    if active_rows:
        logger.info("Negotiation state recovery complete", recovered=len(active_rows))

    # k. History ID lock for thread-safe history ID updates
    services["history_lock"] = asyncio.Lock()
    services["history_id"] = ""

    # l. Wire audit to dispatcher (if both available)
    if slack_dispatcher is not None:
        from negotiation.audit.wiring import wire_audit_to_dispatcher

        wire_audit_to_dispatcher(slack_dispatcher, audit_logger)
        logger.info("Audit logging wired to SlackDispatcher")

    # m. Wire audited process_reply
    from negotiation.audit.wiring import create_audited_process_reply
    from negotiation.llm.negotiation_loop import process_influencer_reply

    audited_process_reply = create_audited_process_reply(process_influencer_reply, audit_logger)
    services["audited_process_reply"] = audited_process_reply

    # n. Wire audit logging into campaign ingestion
    audited_ingest = wire_audit_to_campaign_ingestion(ingest_campaign, audit_logger)
    services["audited_ingest"] = audited_ingest

    # Store config values needed by other functions via services dict
    services["_settings"] = settings
    services["gmail_pubsub_topic"] = settings.gmail_pubsub_topic
    services["slack_app_token"] = settings.slack_app_token.get_secret_value()

    # Wire campaign processor callback for webhook
    clickup_token = settings.clickup_api_token
    # Track background tasks to prevent garbage collection (per RUF006)
    background_tasks: set[asyncio.Task[Any]] = set()
    services["background_tasks"] = background_tasks

    def campaign_processor(task_id: str) -> None:
        """Process a campaign task from webhook.

        Runs the async ingest and starts negotiations for found influencers.
        """

        async def _process() -> None:
            result = await audited_ingest(
                task_id,
                clickup_token,
                sheets_client,
                slack_notifier,
            )
            # After ingestion, start negotiations for found influencers
            found_influencers = result.get("found_influencers", [])
            campaign = result.get("campaign")
            if found_influencers and campaign and services.get("gmail_client"):
                await start_negotiations_for_campaign(
                    found_influencers=found_influencers,
                    campaign=campaign,
                    services=services,
                )
                logger.info(
                    "Negotiations started for campaign",
                    campaign=campaign.client_name,
                    influencer_count=len(found_influencers),
                )
            elif not found_influencers:
                logger.info("No influencers found for campaign, no negotiations to start")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.ensure_future(_process())
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
            else:
                loop.run_until_complete(_process())
        except Exception:
            logger.exception("Campaign processing failed", task_id=task_id)

    set_campaign_processor(campaign_processor)
    logger.info("Campaign processor wired to webhook")

    return services


def build_negotiation_context(
    influencer_name: str,
    influencer_email: str,
    sheet_data: Any,  # InfluencerRow
    campaign: Any,  # Campaign model
    thread_id: str,
    cpm_tracker: Any | None = None,
) -> dict[str, Any]:
    """Assemble the negotiation_context dict that process_influencer_reply expects.

    Args:
        influencer_name: The influencer's name.
        influencer_email: The influencer's email address.
        sheet_data: InfluencerRow from Sheets lookup.
        campaign: The Campaign model from ingestion.
        thread_id: The Gmail thread ID for this conversation.
        cpm_tracker: Optional CampaignCPMTracker for flexibility guidance.

    Returns:
        A dict matching process_influencer_reply's expected negotiation_context keys.
    """
    # Determine target CPM -- use tracker flexibility if available, else campaign floor
    next_cpm = campaign.cpm_range.min_cpm
    if cpm_tracker is not None:
        engagement_rate = getattr(sheet_data, "engagement_rate", None)
        flexibility = cpm_tracker.get_flexibility(
            influencer_engagement_rate=engagement_rate,
        )
        next_cpm = flexibility.target_cpm

    # Build deliverable types from campaign target_deliverables
    deliverable_types = [campaign.target_deliverables]

    return {
        "influencer_name": influencer_name,
        "influencer_email": influencer_email,
        "thread_id": thread_id,
        "platform": str(sheet_data.platform)
        if hasattr(sheet_data, "platform")
        else str(campaign.platform),
        "average_views": int(sheet_data.average_views),
        "deliverables_summary": campaign.target_deliverables,
        "deliverable_types": deliverable_types,
        "next_cpm": next_cpm,
        "client_name": campaign.client_name,
        "campaign_id": campaign.campaign_id,
        "history": "",
    }


async def start_negotiations_for_campaign(
    found_influencers: list[dict[str, Any]],
    campaign: Any,
    services: dict[str, Any],
) -> None:
    """Start negotiations for each found influencer from campaign ingestion.

    For each influencer:
    1. Get PayRange from Sheet data
    2. Calculate initial offer using pricing engine
    3. Create NegotiationStateMachine
    4. Instantiate CampaignCPMTracker for per-influencer flexibility
    5. Compose initial outreach email using compose_counter_email with stage="initial_outreach"
    6. Send via GmailClient.send() as a new thread
    7. Store negotiation state in negotiation_states[thread_id]

    Args:
        found_influencers: List of dicts with "name" and "sheet_data" (InfluencerRow) keys.
        campaign: The Campaign model from ingestion.
        services: The services dict from initialize_services.
    """
    gmail_client = services.get("gmail_client")
    anthropic_client = services.get("anthropic_client")
    negotiation_states = services.get("negotiation_states", {})
    audit_logger = services.get("audit_logger")

    if gmail_client is None:
        logger.warning("GmailClient not available, cannot start negotiations")
        return

    if anthropic_client is None:
        logger.warning("Anthropic client not available, cannot compose outreach emails")
        return

    # Instantiate CampaignCPMTracker for this campaign
    from negotiation.campaign.cpm_tracker import CampaignCPMTracker
    from negotiation.email.models import OutboundEmail
    from negotiation.llm.composer import compose_counter_email
    from negotiation.llm.knowledge_base import load_knowledge_base
    from negotiation.pricing import calculate_initial_offer

    cpm_tracker = CampaignCPMTracker(
        campaign_id=campaign.campaign_id,
        target_min_cpm=campaign.cpm_range.min_cpm,
        target_max_cpm=campaign.cpm_range.max_cpm,
        total_influencers=len(found_influencers),
    )

    for influencer_data in found_influencers:
        name = influencer_data["name"]
        sheet_data = influencer_data["sheet_data"]  # InfluencerRow

        try:
            # Calculate initial offer
            initial_rate = calculate_initial_offer(int(sheet_data.average_views))

            # Create state machine
            state_machine = NegotiationStateMachine()

            # Compose initial outreach email
            # Reuse compose_counter_email with negotiation_stage="initial_outreach"
            kb_content = load_knowledge_base(
                str(sheet_data.platform)
                if hasattr(sheet_data, "platform")
                else str(campaign.platform)
            )

            composed = compose_counter_email(
                influencer_name=name,
                their_rate="not yet discussed",
                our_rate=str(initial_rate),
                deliverables_summary=campaign.target_deliverables,
                platform=str(sheet_data.platform)
                if hasattr(sheet_data, "platform")
                else str(campaign.platform),
                negotiation_stage="initial_outreach",
                knowledge_base_content=kb_content,
                negotiation_history="",
                client=anthropic_client,
            )

            # Send as a new email (not a reply -- new thread)
            influencer_email = str(sheet_data.email) if hasattr(sheet_data, "email") else ""
            if not influencer_email:
                logger.warning("No email for influencer, skipping", influencer=name)
                continue

            outbound = OutboundEmail(
                to=influencer_email,
                subject=f"Collaboration Opportunity - {campaign.client_name}",
                body=composed.email_body,
            )

            send_result = await asyncio.to_thread(gmail_client.send, outbound)
            thread_id = send_result.get("threadId", "")

            # Trigger state machine transition
            state_machine.trigger("send_offer")

            # Build negotiation context and store state
            context = build_negotiation_context(
                influencer_name=name,
                influencer_email=influencer_email,
                sheet_data=sheet_data,
                campaign=campaign,
                thread_id=thread_id,
                cpm_tracker=cpm_tracker,
            )

            negotiation_states[thread_id] = {
                "state_machine": state_machine,
                "context": context,
                "round_count": 0,
                "campaign": campaign,
                "cpm_tracker": cpm_tracker,
            }

            # Persist to SQLite (STATE-01: write before moving to next influencer)
            _state_store = services.get("state_store")
            if _state_store is not None:
                _state_store.save(
                    thread_id=thread_id,
                    state_machine=state_machine,
                    context=context,
                    campaign=campaign,
                    cpm_tracker_data=serialize_cpm_tracker(cpm_tracker),
                    round_count=0,
                )

            # Log to audit trail
            if audit_logger is not None:
                audit_logger.log_email_sent(
                    campaign_id=campaign.campaign_id,
                    influencer_name=name,
                    thread_id=thread_id,
                    email_body=composed.email_body,
                    negotiation_state="initial_offer",
                    rates_used=str(initial_rate),
                )

            logger.info(
                "Initial outreach sent",
                influencer=name,
                thread_id=thread_id,
                initial_rate=str(initial_rate),
                campaign=campaign.client_name,
            )

        except Exception:
            logger.exception("Failed to start negotiation for influencer", influencer=name)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan context manager for FastAPI startup and shutdown.

    On startup: registers Gmail watch if GmailClient is configured.
    On shutdown: closes the audit database connection.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control to the application.
    """
    # Startup
    services = app.state.services
    gmail_client = services.get("gmail_client")
    if gmail_client:
        topic = services.get("gmail_pubsub_topic", "")
        if topic:
            try:
                watch_result = await asyncio.to_thread(gmail_client.setup_watch, topic)
                async with services["history_lock"]:
                    services["history_id"] = str(watch_result.get("historyId", ""))
                logger.info("Gmail watch registered", history_id=services["history_id"])
            except Exception:
                logger.warning("Failed to register Gmail watch", exc_info=True)
    logger.info("FastAPI application starting")
    yield
    # Shutdown
    audit_conn = services.get("audit_conn")
    if audit_conn is not None:
        close_audit_db(audit_conn)
        logger.info("Audit database connection closed")


def create_app(services: dict[str, Any]) -> FastAPI:
    """Create the FastAPI app with lifespan, webhook router, and Gmail endpoint.

    Args:
        services: The initialized services dict from ``initialize_services``.

    Returns:
        The configured FastAPI application.
    """
    fastapi_app = FastAPI(title="Negotiation Agent Webhooks", lifespan=lifespan)
    fastapi_app.state.services = services
    fastapi_app.state.settings = services.get("_settings", get_settings())
    fastapi_app.include_router(webhook_router)
    register_health_routes(fastapi_app)

    @fastapi_app.post("/webhooks/gmail")
    async def gmail_notification(request: Request) -> dict[str, str]:
        """Handle Gmail Pub/Sub push notification."""
        svc = request.app.state.services
        gmail = svc.get("gmail_client")
        if gmail is None:
            logger.warning("Gmail notification received but GmailClient not initialized")
            return {"status": "ok"}

        body = await request.json()
        message_data = body.get("message", {}).get("data", "")
        if not message_data:
            logger.warning("Gmail notification missing message data")
            return {"status": "ok"}

        decoded = json.loads(base64.urlsafe_b64decode(message_data))
        notification_history_id = decoded.get("historyId", "")
        logger.info("Gmail notification received", history_id=notification_history_id)

        # Fetch new messages under lock to prevent race conditions
        async with svc["history_lock"]:
            current_history_id = svc.get("history_id", "")
            if not current_history_id:
                logger.warning("No history ID stored, skipping notification")
                return {"status": "ok"}

            new_ids, new_history_id = await asyncio.to_thread(
                gmail.fetch_new_messages, current_history_id
            )
            svc["history_id"] = new_history_id

        # Process each new message in background tasks
        bg_tasks = svc.get("background_tasks", set())
        for msg_id in new_ids:
            task = asyncio.ensure_future(process_inbound_email(msg_id, svc))
            bg_tasks.add(task)
            task.add_done_callback(bg_tasks.discard)

        logger.info("Gmail notification processed", new_messages=len(new_ids))
        return {"status": "ok"}

    return fastapi_app


async def process_inbound_email(message_id: str, services: dict[str, Any]) -> None:
    """Process a single inbound email through the full negotiation pipeline.

    Flow: get_message -> pre_check -> process_influencer_reply ->
    handle_result -> send_reply.  All GmailClient calls wrapped in
    ``asyncio.to_thread`` (they are synchronous).

    Args:
        message_id: The Gmail message ID to process.
        services: The initialized services dict.
    """
    gmail_client = services["gmail_client"]
    dispatcher = services.get("slack_dispatcher")
    anthropic_client = services.get("anthropic_client")
    negotiation_states = services.get("negotiation_states", {})
    audited_process_reply = services.get("audited_process_reply")

    try:
        # Step 1: Fetch and parse the email (blocking -> thread)
        inbound = await asyncio.to_thread(gmail_client.get_message, message_id)
        logger.info(
            "Processing inbound email",
            message_id=message_id,
            thread_id=inbound.thread_id,
            from_email=inbound.from_email,
        )

        # Step 2: Look up existing negotiation state by thread_id
        thread_state = negotiation_states.get(inbound.thread_id)
        if thread_state is None:
            logger.info(
                "No active negotiation for thread, ignoring",
                thread_id=inbound.thread_id,
            )
            return

        state_machine = thread_state["state_machine"]
        context = thread_state["context"]
        round_count = thread_state["round_count"]

        # Log inbound email to audit trail (DATA-03: every received email)
        audit_logger = services.get("audit_logger")
        if audit_logger is not None:
            audit_logger.log_email_received(
                campaign_id=context.get("campaign_id"),
                influencer_name=str(context.get("influencer_name", "")),
                thread_id=inbound.thread_id,
                email_body=inbound.body_text,
                negotiation_state=str(context.get("negotiation_state", "")),
                intent_classification=None,  # Not yet classified at receipt time
            )

        # Step 3: Run pre-check gates (if SlackDispatcher available)
        if dispatcher is not None:
            pre_check_result = dispatcher.pre_check(
                email_body=inbound.body_text,
                thread_id=inbound.thread_id,
                influencer_email=inbound.from_email,
                proposed_cpm=float(context.get("next_cpm", 0)),
                intent_confidence=1.0,
                gmail_service=gmail_client._service,
                anthropic_client=anthropic_client,
            )
            if pre_check_result is not None:
                logger.info(
                    "Pre-check gate fired, skipping negotiation",
                    action=pre_check_result.get("action"),
                    reason=pre_check_result.get("reason"),
                    thread_id=inbound.thread_id,
                )
                return

        # Step 4: Run negotiation loop
        if anthropic_client is None:
            logger.warning("Anthropic client unavailable, cannot process reply")
            return

        process_fn = audited_process_reply or services.get("_raw_process_reply")
        if process_fn is None:
            from negotiation.llm.negotiation_loop import (
                process_influencer_reply as _fallback_process,
            )

            process_fn = _fallback_process

        result = process_fn(
            email_body=inbound.body_text,
            negotiation_context=context,
            state_machine=state_machine,
            client=anthropic_client,
            round_count=round_count,
        )

        # Step 5: Dispatch to Slack (if dispatcher available)
        if dispatcher is not None:
            result = dispatcher.handle_negotiation_result(result, context)

        # Persist state after negotiation loop (STATE-01: write before response)
        _state_store = services.get("state_store")
        if _state_store is not None:
            _state_store.save(
                thread_id=inbound.thread_id,
                state_machine=state_machine,
                context=context,
                campaign=thread_state["campaign"],
                cpm_tracker_data=serialize_cpm_tracker(thread_state["cpm_tracker"]),
                round_count=thread_state["round_count"],
            )

        # Step 6: If action is "send", send the reply
        if result["action"] == "send":
            await asyncio.to_thread(
                gmail_client.send_reply,
                inbound.thread_id,
                result["email_body"],
            )
            thread_state["round_count"] += 1

            # Persist updated round_count after send (STATE-01)
            if _state_store is not None:
                _state_store.save(
                    thread_id=inbound.thread_id,
                    state_machine=state_machine,
                    context=context,
                    campaign=thread_state["campaign"],
                    cpm_tracker_data=serialize_cpm_tracker(thread_state["cpm_tracker"]),
                    round_count=thread_state["round_count"],
                )

            logger.info(
                "Counter-offer sent",
                thread_id=inbound.thread_id,
                round=thread_state["round_count"],
            )
        elif result["action"] == "accept":
            logger.info(
                "Deal accepted",
                thread_id=inbound.thread_id,
                influencer=context.get("influencer_name"),
            )
        elif result["action"] == "escalate":
            logger.info(
                "Escalated to human",
                thread_id=inbound.thread_id,
                reason=result.get("reason"),
            )
        elif result["action"] == "reject":
            logger.info(
                "Influencer rejected",
                thread_id=inbound.thread_id,
            )

    except Exception:
        logger.exception("Failed to process inbound email", message_id=message_id)


async def renew_gmail_watch_periodically(services: dict[str, Any]) -> None:
    """Renew Gmail watch every 6 days (watch expires at 7 days).

    Args:
        services: The initialized services dict.
    """
    interval_seconds = 6 * 24 * 3600  # 6 days
    gmail_client = services.get("gmail_client")
    topic = services.get("gmail_pubsub_topic", "")

    if not gmail_client or not topic:
        return

    while True:
        await asyncio.sleep(interval_seconds)
        try:
            result = await asyncio.to_thread(gmail_client.setup_watch, topic)
            async with services["history_lock"]:
                new_history_id = str(result.get("historyId", ""))
                if new_history_id:
                    services["history_id"] = new_history_id
            logger.info("Gmail watch renewed", history_id=services.get("history_id"))
        except Exception:
            logger.exception("Failed to renew Gmail watch")


async def run_slack_bot(services: dict[str, Any]) -> None:
    """Start Slack Bolt Socket Mode handler in a background thread.

    Uses ``asyncio.to_thread`` since Bolt Socket Mode is synchronous.

    Args:
        services: The initialized services dict.
    """
    bolt_app = services.get("bolt_app")
    if bolt_app is None:
        logger.warning("No Slack Bolt app available, skipping Socket Mode")
        return

    app_token = services.get("slack_app_token", "")
    if not app_token:
        logger.warning("SLACK_APP_TOKEN not set, skipping Socket Mode")
        return

    logger.info("Starting Slack Bolt Socket Mode handler")
    try:
        await asyncio.to_thread(start_slack_app, bolt_app, app_token)
    except Exception:
        logger.exception("Slack Bolt Socket Mode handler failed")


async def main() -> None:
    """Main entry point: run FastAPI and Slack Bolt concurrently.

    1. Configure logging
    2. Initialize services
    3. Create FastAPI app
    4. Run uvicorn + Slack Bolt + Gmail watch renewal with asyncio.gather
    5. Close audit DB on exit
    """
    settings = get_settings()
    configure_logging(production=settings.production)
    logger.info("Application starting")

    validate_credentials(settings)

    services = initialize_services(settings)

    fastapi_app = create_app(services)

    port = settings.webhook_port
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    try:
        tasks_to_run: list[Any] = [server.serve(), run_slack_bot(services)]
        # Add Gmail watch renewal if Gmail is configured
        gmail_client = services.get("gmail_client")
        gmail_topic = services.get("gmail_pubsub_topic", "")
        if gmail_client and gmail_topic:
            tasks_to_run.append(renew_gmail_watch_periodically(services))
        await asyncio.gather(*tasks_to_run)
    finally:
        audit_conn = services.get("audit_conn")
        if audit_conn is not None:
            close_audit_db(audit_conn)
            logger.info("Audit database connection closed on shutdown")


if __name__ == "__main__":
    asyncio.run(main())
