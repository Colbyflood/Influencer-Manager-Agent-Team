"""Application entry point combining FastAPI webhooks and Slack Bolt Socket Mode.

Runs both the ClickUp webhook server (FastAPI on HTTP) and the Slack Bolt
handler (Socket Mode WebSocket) concurrently in a single long-running process.

Configures:
- **structlog** with JSON rendering (production) or colored console (development)
- **Audit logging** wired into all pipeline operations via wrapper functions
- **Retry logic** for all external APIs with Slack #errors notification
- **Slash commands** (/audit, /claim, /resume) on the Slack Bolt app
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI

from negotiation.audit.logger import AuditLogger
from negotiation.audit.slack_commands import register_audit_command
from negotiation.audit.store import close_audit_db, init_audit_db
from negotiation.audit.wiring import wire_audit_to_campaign_ingestion
from negotiation.campaign.ingestion import ingest_campaign
from negotiation.campaign.webhook import app as webhook_app
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
    registers slash commands, and wires audit logging into pipeline functions.

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

    if bolt_app is not None:
        # f. Register audit command
        register_audit_command(bolt_app, audit_conn)
        logger.info("Registered /audit slash command")

        # g. Register /claim and /resume commands
        thread_state_manager = ThreadStateManager()
        services["thread_state_manager"] = thread_state_manager
        register_commands(bolt_app, thread_state_manager)
        logger.info("Registered /claim and /resume slash commands")

    # h. Wire audit logging into pipeline functions
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


def create_app(services: dict[str, Any]) -> FastAPI:
    """Get the FastAPI app from campaign.webhook module.

    Adds startup/shutdown event handlers for audit DB connection management.

    Args:
        services: The initialized services dict from ``initialize_services``.

    Returns:
        The configured FastAPI application.
    """
    fastapi_app = webhook_app

    @fastapi_app.on_event("startup")
    async def on_startup() -> None:
        logger.info("FastAPI application starting")

    @fastapi_app.on_event("shutdown")
    async def on_shutdown() -> None:
        audit_conn = services.get("audit_conn")
        if audit_conn is not None:
            close_audit_db(audit_conn)
            logger.info("Audit database connection closed")

    return fastapi_app


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
    4. Run uvicorn + Slack Bolt with asyncio.gather
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
        await asyncio.gather(
            server.serve(),
            run_slack_bot(services),
        )
    finally:
        audit_conn = services.get("audit_conn")
        if audit_conn is not None:
            close_audit_db(audit_conn)
            logger.info("Audit database connection closed on shutdown")


if __name__ == "__main__":
    asyncio.run(main())
