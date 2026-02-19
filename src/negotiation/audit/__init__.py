"""Audit trail: models, storage, logger, CLI, Slack command, and wiring for event tracking."""

from negotiation.audit.cli import build_parser
from negotiation.audit.logger import AuditLogger
from negotiation.audit.models import AuditEntry, EventType
from negotiation.audit.slack_commands import (
    format_audit_blocks,
    parse_audit_query,
    register_audit_command,
)
from negotiation.audit.store import (
    close_audit_db,
    init_audit_db,
    insert_audit_entry,
    query_audit_trail,
)
from negotiation.audit.wiring import (
    create_audited_email_receive,
    create_audited_email_send,
    create_audited_process_reply,
    wire_audit_to_campaign_ingestion,
    wire_audit_to_dispatcher,
)

__all__ = [
    "AuditEntry",
    "AuditLogger",
    "EventType",
    "build_parser",
    "close_audit_db",
    "create_audited_email_receive",
    "create_audited_email_send",
    "create_audited_process_reply",
    "format_audit_blocks",
    "init_audit_db",
    "insert_audit_entry",
    "parse_audit_query",
    "query_audit_trail",
    "register_audit_command",
    "wire_audit_to_campaign_ingestion",
    "wire_audit_to_dispatcher",
]
