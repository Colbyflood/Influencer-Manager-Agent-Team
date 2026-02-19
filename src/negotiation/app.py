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
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, Request

from negotiation.audit.logger import AuditLogger
from negotiation.audit.slack_commands import register_audit_command
from negotiation.audit.store import close_audit_db, init_audit_db
from negotiation.audit.wiring import wire_audit_to_campaign_ingestion
from negotiation.campaign.ingestion import ingest_campaign
from negotiation.campaign.webhook import router as webhook_router
from negotiation.campaign.webhook import set_campaign_processor
from negotiation.resilience.retry import configure_error_notifier
from negotiation.slack.app import create_slack_app, start_slack_app
from negotiation.slack.commands import register_commands
from negotiation.slack.takeover import ThreadStateManager

logger = structlog.get_logger()


def configure_logging(production: bool = False) -> None:
    """Configure structlog for production (JSON) or development (console).

    Production mode (``PRODUCTION`` env var set or *production=True*): JSON
    rendering at INFO level. Development mode: colored console rendering at
    DEBUG level.

    Args:
        production: Force production mode if ``True``. Otherwise checks
            the ``PRODUCTION`` environment variable.
    """
    is_production = production or os.environ.get("PRODUCTION", "").lower() in (
        "1",
        "true",
        "yes",
    )

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


def initialize_services() -> dict[str, Any]:
    """Set up all shared services for the application.

    Creates the audit database, AuditLogger, SlackNotifier (if credentials
    available), error notifier, SheetsClient (if credentials available),
    GmailClient (if token available), Anthropic client (if API key available),
    SlackDispatcher (if Slack available), registers slash commands, and wires
    audit logging into pipeline functions.

    Returns:
        A dict of initialized service instances keyed by name.
    """
    services: dict[str, Any] = {}

    # a. Initialize SQLite audit database
    audit_db_path = Path(os.environ.get("AUDIT_DB_PATH", "data/audit.db"))
    audit_db_path.parent.mkdir(parents=True, exist_ok=True)
    audit_conn = init_audit_db(audit_db_path)
    services["audit_conn"] = audit_conn

    # b. Create AuditLogger
    audit_logger = AuditLogger(audit_conn)
    services["audit_logger"] = audit_logger

    # c. Create SlackNotifier (if SLACK_BOT_TOKEN available)
    slack_notifier = None
    slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
    if slack_bot_token:
        try:
            from negotiation.slack.client import SlackNotifier

            escalation_channel = os.environ.get("SLACK_ESCALATION_CHANNEL", "")
            agreement_channel = os.environ.get("SLACK_AGREEMENT_CHANNEL", "")
            slack_notifier = SlackNotifier(
                escalation_channel=escalation_channel,
                agreement_channel=agreement_channel,
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
    sheets_key = os.environ.get("GOOGLE_SHEETS_KEY")
    if sheets_key:
        try:
            from negotiation.auth.credentials import get_sheets_client
            from negotiation.sheets.client import SheetsClient

            gc = get_sheets_client()
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

    # g. GmailClient (if GMAIL_TOKEN_PATH is set)
    gmail_client = None
    gmail_token = os.environ.get("GMAIL_TOKEN_PATH")
    if gmail_token:
        try:
            from negotiation.auth.credentials import get_gmail_service
            from negotiation.email.client import GmailClient

            service = get_gmail_service()
            agent_email = os.environ.get("AGENT_EMAIL", "")
            gmail_client = GmailClient(service, agent_email)
            logger.info("GmailClient initialized")
        except Exception:
            logger.warning("Failed to initialize GmailClient", exc_info=True)
    else:
        logger.info("GMAIL_TOKEN_PATH not set, GmailClient disabled")
    services["gmail_client"] = gmail_client

    # h. Anthropic client (if ANTHROPIC_API_KEY is set)
    anthropic_client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
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
            agent_email = os.environ.get("AGENT_EMAIL", "")
            slack_dispatcher = SlackDispatcher(
                notifier=slack_notifier,
                thread_state_manager=thread_state_manager,
                triggers_config=triggers_config,
                agent_email=agent_email,
            )
            logger.info("SlackDispatcher initialized")
        except Exception:
            logger.warning("Failed to initialize SlackDispatcher", exc_info=True)
    else:
        logger.info(
            "SlackNotifier or ThreadStateManager unavailable, SlackDispatcher disabled"
        )
    services["slack_dispatcher"] = slack_dispatcher

    # j. In-memory negotiation state store
    negotiation_states: dict[str, dict[str, Any]] = {}
    services["negotiation_states"] = negotiation_states

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

    audited_process_reply = create_audited_process_reply(
        process_influencer_reply, audit_logger
    )
    services["audited_process_reply"] = audited_process_reply

    # n. Wire audit logging into campaign ingestion
    audited_ingest = wire_audit_to_campaign_ingestion(ingest_campaign, audit_logger)
    services["audited_ingest"] = audited_ingest

    # Wire campaign processor callback for webhook
    clickup_token = os.environ.get("CLICKUP_API_TOKEN", "")
    # Track background tasks to prevent garbage collection (per RUF006)
    background_tasks: set[asyncio.Task[Any]] = set()
    services["background_tasks"] = background_tasks

    def campaign_processor(task_id: str) -> None:
        """Process a campaign task from webhook, running the async ingest."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.ensure_future(
                    audited_ingest(
                        task_id,
                        clickup_token,
                        sheets_client,
                        slack_notifier,
                    )
                )
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
            else:
                loop.run_until_complete(
                    audited_ingest(
                        task_id,
                        clickup_token,
                        sheets_client,
                        slack_notifier,
                    )
                )
        except Exception:
            logger.exception("Campaign processing failed", task_id=task_id)

    set_campaign_processor(campaign_processor)
    logger.info("Campaign processor wired to webhook")

    return services


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
        topic = os.environ.get("GMAIL_PUBSUB_TOPIC", "")
        if topic:
            try:
                watch_result = await asyncio.to_thread(gmail_client.setup_watch, topic)
                async with services["history_lock"]:
                    services["history_id"] = str(watch_result.get("historyId", ""))
                logger.info(
                    "Gmail watch registered", history_id=services["history_id"]
                )
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
    fastapi_app.include_router(webhook_router)

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
        logger.info(
            "Gmail notification received", history_id=notification_history_id
        )

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

        # Step 3: Run pre-check gates (if SlackDispatcher available)
        if dispatcher is not None:
            pre_check_result = dispatcher.pre_check(
                email_body=inbound.body_text,
                thread_id=inbound.thread_id,
                influencer_email=inbound.from_email,
                proposed_cpm=0.0,
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

        # Step 6: If action is "send", send the reply
        if result["action"] == "send":
            await asyncio.to_thread(
                gmail_client.send_reply,
                inbound.thread_id,
                result["email_body"],
            )
            thread_state["round_count"] += 1
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
    topic = os.environ.get("GMAIL_PUBSUB_TOPIC", "")

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

    app_token = os.environ.get("SLACK_APP_TOKEN")
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
    is_production = os.environ.get("PRODUCTION", "").lower() in ("1", "true", "yes")
    configure_logging(production=is_production)
    logger.info("Application starting")

    services = initialize_services()

    fastapi_app = create_app(services)

    port = int(os.environ.get("WEBHOOK_PORT", "8000"))
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
        gmail_topic = os.environ.get("GMAIL_PUBSUB_TOPIC", "")
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
