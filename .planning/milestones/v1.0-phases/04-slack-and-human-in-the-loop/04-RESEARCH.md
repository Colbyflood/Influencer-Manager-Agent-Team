# Phase 4: Slack and Human-in-the-Loop - Research

**Researched:** 2026-02-18
**Domain:** Slack integration (notifications, slash commands, Block Kit), escalation trigger rules, human takeover detection via Gmail API, configuration management
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Escalation Message Format
- Summary format with link to full details -- not everything inline
- Always include: influencer name, influencer email address, client name, escalation reason, key numbers (proposed vs target rate)
- Include suggested specific actions (e.g., "Reply with counter at $X" or "Approve this rate")
- No urgency indicators (no time-since-reply, no round count)
- Single dedicated Slack channel for all escalations
- Specific reason with evidence -- name the exact trigger and quote relevant text from the email

#### Agreement Alert Content
- Deal summary + next steps (e.g., "Send contract", "Confirm deliverables")
- Always include: influencer name, influencer email address, client name, agreed rate, platform, deliverables, CPM achieved
- Separate dedicated Slack channel for agreements (not same as escalations)
- Configurable per-campaign tagging -- campaign data specifies who to @ mention

#### Human Takeover Flow
- Support both methods: detect human email reply in thread AND Slack command to claim thread
- Silent handoff -- no Slack notification when human takes over, agent just stops
- Re-enable via Slack command (e.g., '/resume @influencer') -- human can hand thread back to agent
- Human detection method: Claude's discretion (based on Gmail API capabilities from Phase 2)

#### Escalation Trigger Rules
- All triggers active by default: CPM over threshold, ambiguous intent, hostile tone, legal/contract language, unusual deliverable requests
- Team can disable specific triggers if too noisy
- Triggers defined in a config file (YAML/JSON) that team can edit without code changes -- add keywords, change thresholds
- Tone-based triggers (hostile tone, legal language) use LLM-based detection, not keyword matching
- Escalation reason is specific with evidence -- quote the triggering text

### Claude's Discretion
- Human reply detection method in email threads
- Config file format for escalation triggers (YAML vs JSON)
- Slack message formatting and Block Kit structure
- Link format for "full details" in escalation messages

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HUMAN-01 | Agent escalates edge cases to designated Slack channel with full context (conversation history, influencer metrics, proposed vs target rate, reason for escalation) | Slack SDK `WebClient.chat_postMessage` with Block Kit sections for structured escalation messages. EscalationPayload from Phase 3 provides the data; this phase adds the Slack delivery layer. See [Slack Client Architecture](#pattern-1-slack-notification-client) and [Escalation Message Block Kit](#escalation-message-block-kit-structure). |
| HUMAN-02 | Agent escalates based on configurable trigger rules (CPM over threshold, ambiguous intent, hostile tone, legal/contract language, unusual deliverable requests) | YAML config file loaded by Pydantic model with per-trigger enable/disable flags and thresholds. LLM-based triggers use Claude structured outputs for tone/legal classification. See [Escalation Trigger Engine](#pattern-3-escalation-trigger-engine) and [Config File Format Recommendation](#config-file-format-recommendation). |
| HUMAN-03 | Agent detects agreement in influencer replies and sends actionable Slack alert (influencer name, agreed rate, platform, deliverables, CPM achieved, next steps) | Agreement detection already exists in Phase 3 negotiation loop (`action: "accept"`). This phase adds `AgreementPayload` model and Slack delivery to the agreements channel. See [Agreement Alert Architecture](#pattern-2-agreement-alert). |
| HUMAN-04 | Agent supports human takeover -- when a human responds in a thread, agent stops autonomous handling of that thread | Gmail API `threads.get()` to inspect all message senders in a thread; compare `From` headers against agent's email to detect human replies. Slack `/claim` and `/resume` commands via Bolt. See [Human Takeover Detection](#pattern-4-human-takeover-detection) and [Slash Command Handlers](#pattern-5-slack-slash-commands). |
</phase_requirements>

## Summary

Phase 4 bridges the autonomous negotiation pipeline (Phases 1-3) to the human team via Slack. The core challenge is four-fold: (1) delivering rich, actionable Slack notifications for escalations and agreements using Block Kit formatting, (2) implementing a configurable escalation trigger engine that combines deterministic rules (CPM threshold, max rounds) with LLM-based triggers (hostile tone, legal language), (3) detecting when a human team member replies directly in a Gmail negotiation thread so the agent can silently stop, and (4) providing Slack slash commands (`/claim`, `/resume`) for explicit human takeover and handback.

The Slack integration uses `slack-sdk` (v3.40.0) directly with `WebClient.chat_postMessage` for sending Block Kit messages. Bolt for Python (v1.27.0) is used for slash command handling with Socket Mode (no public HTTP endpoint required). This is a deliberate split: the notification side (posting messages) needs only the lightweight `slack-sdk`, while the command-listening side (slash commands) needs the Bolt framework. Socket Mode is preferred because it avoids requiring a publicly accessible server -- the app connects to Slack via WebSocket, which is ideal for a system that may run behind a firewall or on a developer's machine.

The escalation trigger engine uses a YAML config file (recommendation below) validated by a Pydantic model. Deterministic triggers (CPM over threshold, max rounds exceeded, ambiguous intent) fire based on data already available from Phase 3. LLM-based triggers (hostile tone, legal/contract language, unusual deliverable requests) use a separate Claude Haiku call with structured outputs to classify the email text before the main negotiation loop processes it. The trigger engine runs as a pre-processing step: classify triggers first, then proceed with the existing negotiation loop or escalate immediately.

**Primary recommendation:** Use `slack-sdk` WebClient for posting Block Kit messages to Slack channels, `slack-bolt` with Socket Mode for slash command handling, YAML for the escalation trigger config file, and Gmail API `threads.get()` with `From` header comparison for human reply detection.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `slack-sdk` | >=3.40.0 | Slack WebClient for posting messages to channels | Official Slack Python SDK; `chat_postMessage` with `blocks` parameter for Block Kit; actively maintained (released Feb 2026) |
| `slack-bolt` | >=1.27.0 | Slack app framework for slash commands and Socket Mode | Official Slack app framework; handles command registration, acknowledgment, Socket Mode WebSocket connection; built on top of `slack-sdk` |
| `pyyaml` | >=6.0.2 | YAML config file parsing for escalation trigger rules | Standard Python YAML library; `safe_load` for secure parsing; used with Pydantic for validation |
| `anthropic` | >=0.82.0 | Claude API for LLM-based tone/legal triggers | Already in project; used for hostile tone and legal language detection via structured outputs |
| `pydantic` | >=2.12,<3 | Escalation trigger config validation, payload models | Already in project; validates YAML config against schema, defines AgreementPayload and extended EscalationPayload |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | >=9.0,<10 | Testing Slack integration, trigger engine, human detection | Already in project dev dependencies |
| `pytest-mock` | >=3.15.1 | Mocking Slack WebClient and Gmail API in tests | Already in project dev dependencies |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `slack-bolt` for slash commands | `slack-sdk` only (manual WebSocket handling) | Bolt provides clean command registration, automatic ack(), and Socket Mode handler. Using sdk-only means reimplementing these patterns manually. Bolt is the official recommended approach. |
| Socket Mode | HTTP mode (public endpoint) | HTTP mode requires a publicly accessible server and ngrok/tunnel for development. Socket Mode works behind firewalls and on developer machines without configuration. Socket Mode is simpler for this use case since the app only needs to listen for slash commands, not high-volume events. |
| YAML config file | JSON config file | See [Config File Format Recommendation](#config-file-format-recommendation) below. YAML wins for human editability (comments, cleaner syntax), JSON wins for programmatic generation. YAML is better for a file team members edit by hand. |
| `pyyaml` | `ruamel.yaml` | ruamel.yaml preserves comments on round-trip but adds dependency complexity. PyYAML is simpler and sufficient since we only read the config (no programmatic writes that need comment preservation). |
| Incoming webhooks | Bot token + WebClient | Incoming webhooks are simpler (just HTTP POST) but cannot read channels, handle commands, or support interactive elements. Bot token approach supports the full feature set needed (posting + slash commands + future interactivity). |

**Installation:**
```bash
uv add slack-sdk slack-bolt pyyaml
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── negotiation/
│   ├── domain/          # (Phase 1 -- exists)
│   ├── pricing/         # (Phase 1 -- exists)
│   ├── state_machine/   # (Phase 1 -- exists)
│   ├── email/           # (Phase 2 -- exists)
│   ├── sheets/          # (Phase 2 -- exists)
│   ├── auth/            # (Phase 2 -- exists)
│   ├── llm/             # (Phase 3 -- exists)
│   │   └── models.py    # Extended: add AgreementPayload, extend EscalationPayload
│   └── slack/           # (Phase 4 -- NEW)
│       ├── __init__.py
│       ├── client.py          # SlackNotifier: wraps WebClient, posts to escalation/agreement channels
│       ├── blocks.py          # Block Kit message builders (escalation blocks, agreement blocks)
│       ├── commands.py        # Slash command handlers (/claim, /resume)
│       ├── app.py             # Bolt App initialization, Socket Mode setup
│       ├── models.py          # Slack-specific config models (channel IDs, etc.)
│       └── triggers.py        # Escalation trigger engine (config loading, trigger evaluation)
├── negotiation/
│   └── slack/
│       └── config/            # OR top-level config location
│           └── triggers.yaml  # Escalation trigger rules (team-editable)
config/                        # (Phase 4 -- NEW) Top-level, outside src/
└── escalation_triggers.yaml   # Escalation trigger rules (team-editable, like knowledge_base/)
tests/
├── slack/                     # (Phase 4 -- NEW)
│   ├── __init__.py
│   ├── test_client.py         # SlackNotifier tests (mocked WebClient)
│   ├── test_blocks.py         # Block Kit builder tests (pure data, no mocks)
│   ├── test_commands.py       # Slash command handler tests
│   ├── test_triggers.py       # Trigger engine tests (config loading, evaluation)
│   └── test_human_detection.py # Human takeover detection tests
```

### Pattern 1: Slack Notification Client

**What:** A thin wrapper around `slack_sdk.WebClient` that posts structured Block Kit messages to designated channels. Separates message building (blocks.py) from message delivery (client.py).
**When to use:** HUMAN-01 (escalations), HUMAN-03 (agreements).

**Example:**
```python
# Source: https://docs.slack.dev/tools/python-slack-sdk/web/
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackNotifier:
    """Posts structured notifications to Slack channels.

    Uses the Slack WebClient with Block Kit messages for rich formatting.
    Requires SLACK_BOT_TOKEN environment variable.
    """

    def __init__(
        self,
        escalation_channel: str,
        agreement_channel: str,
        bot_token: str | None = None,
    ) -> None:
        token = bot_token or os.environ["SLACK_BOT_TOKEN"]
        self._client = WebClient(token=token)
        self._escalation_channel = escalation_channel
        self._agreement_channel = agreement_channel

    def post_escalation(self, blocks: list[dict], fallback_text: str) -> str:
        """Post an escalation message to the escalation channel.

        Args:
            blocks: Block Kit blocks for the message.
            fallback_text: Plain-text fallback for notifications.

        Returns:
            The Slack message timestamp (ts) for reference.
        """
        response = self._client.chat_postMessage(
            channel=self._escalation_channel,
            blocks=blocks,
            text=fallback_text,  # Shown in notifications/unfurls
        )
        return response["ts"]

    def post_agreement(self, blocks: list[dict], fallback_text: str) -> str:
        """Post an agreement alert to the agreement channel."""
        response = self._client.chat_postMessage(
            channel=self._agreement_channel,
            blocks=blocks,
            text=fallback_text,
        )
        return response["ts"]
```

### Escalation Message Block Kit Structure

**Claude's Discretion: Slack message formatting and Block Kit structure.**

**Recommendation:** Use a compact summary layout with header, key details in fields, evidence in a quote block, and suggested actions as context. Do not use interactive buttons (actions block) in v1 -- keep it informational with suggested text actions the human can copy. This avoids the complexity of handling button callbacks while still being actionable.

```python
def build_escalation_blocks(
    influencer_name: str,
    influencer_email: str,
    client_name: str,
    escalation_reason: str,
    evidence_quote: str,
    proposed_rate: str | None,
    our_rate: str | None,
    suggested_actions: list[str],
    details_link: str,
) -> list[dict]:
    """Build Block Kit blocks for an escalation message.

    Returns a list of Block Kit block dicts ready for chat_postMessage.
    """
    blocks: list[dict] = [
        # Header
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Escalation: {influencer_name}"},
        },
        # Key details as fields
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Influencer:*\n{influencer_name}"},
                {"type": "mrkdwn", "text": f"*Email:*\n{influencer_email}"},
                {"type": "mrkdwn", "text": f"*Client:*\n{client_name}"},
                {"type": "mrkdwn", "text": f"*Reason:*\n{escalation_reason}"},
            ],
        },
    ]

    # Rate comparison (only if rates available)
    if proposed_rate or our_rate:
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Their Rate:*\n${proposed_rate or 'N/A'}"},
                {"type": "mrkdwn", "text": f"*Our Rate:*\n${our_rate or 'N/A'}"},
            ],
        })

    # Evidence quote
    if evidence_quote:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Evidence:*\n>{evidence_quote}",
            },
        })

    # Suggested actions
    if suggested_actions:
        actions_text = "\n".join(f"- {action}" for action in suggested_actions)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Suggested Actions:*\n{actions_text}",
            },
        })

    # Link to full details
    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"<{details_link}|View full conversation details>"},
        ],
    })

    return blocks
```

**Design rationale:**
- **Header block** provides instant visual identification in Slack.
- **Section with fields** shows 2-per-row key/value pairs (max 10 fields per section, we use 4).
- **Blockquote** (using `>` in mrkdwn) visually distinguishes the evidence quote from metadata.
- **Context block** for the details link keeps it visually secondary to the main content.
- No actions block (buttons) in v1 -- actions are text-based ("Reply with counter at $X"). This avoids needing to handle interactive callbacks in the Bolt app.

### Link Format for Full Details

**Claude's Discretion: Link format for "full details" in escalation messages.**

**Recommendation:** Use a Gmail thread permalink. The format is `https://mail.google.com/mail/u/0/#inbox/{thread_id}`. This is simple, requires no additional infrastructure, and takes the team member directly to the email thread. The `thread_id` is already available in the EscalationPayload from Phase 3.

For internal details (negotiation state, pricing calculations), consider a future admin dashboard (out of scope for v1). For v1, the Gmail link plus the inline summary provides sufficient context.

### Pattern 2: Agreement Alert

**What:** When the negotiation loop returns `action: "accept"`, build and post an agreement notification to the agreements Slack channel.
**When to use:** HUMAN-03, every time agreement is detected.

**Example:**
```python
from decimal import Decimal


def build_agreement_blocks(
    influencer_name: str,
    influencer_email: str,
    client_name: str,
    agreed_rate: Decimal,
    platform: str,
    deliverables: str,
    cpm_achieved: Decimal,
    next_steps: list[str],
    mention_users: list[str] | None = None,
) -> list[dict]:
    """Build Block Kit blocks for an agreement alert."""
    # Build mention string if users specified
    mention_text = ""
    if mention_users:
        mention_text = " ".join(f"<@{uid}>" for uid in mention_users) + "\n"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Deal Agreed: {influencer_name}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Influencer:*\n{influencer_name}"},
                {"type": "mrkdwn", "text": f"*Email:*\n{influencer_email}"},
                {"type": "mrkdwn", "text": f"*Client:*\n{client_name}"},
                {"type": "mrkdwn", "text": f"*Platform:*\n{platform.title()}"},
            ],
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Agreed Rate:*\n${agreed_rate:,.2f}"},
                {"type": "mrkdwn", "text": f"*CPM Achieved:*\n${cpm_achieved:,.2f}"},
                {"type": "mrkdwn", "text": f"*Deliverables:*\n{deliverables}"},
            ],
        },
    ]

    # Next steps
    if next_steps:
        steps_text = "\n".join(f"- {step}" for step in next_steps)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Next Steps:*\n{steps_text}",
            },
        })

    # Campaign mentions
    if mention_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": mention_text.strip()},
        })

    return blocks
```

**Key design decisions:**
- `mention_users` takes Slack user IDs (e.g., `U024BE7LH`), not display names. The `<@USER_ID>` syntax triggers a real Slack mention notification.
- Per-campaign tagging (who to @mention) is configurable per the locked decision. In v1, this can be stored in the campaign data or a config file. Since campaign data ingestion is Phase 5 (out of scope), v1 can use a default mention list from the Slack config or the trigger config.
- CPM achieved is calculated from the agreed rate and average views using the pricing engine already built in Phase 1.

### Pattern 3: Escalation Trigger Engine

**What:** A pre-processing step that evaluates all configured escalation triggers against an influencer email before the main negotiation loop. Combines deterministic triggers (CPM threshold, etc.) with LLM-based triggers (hostile tone, legal language).
**When to use:** HUMAN-02, before every negotiation loop iteration.

The trigger engine is separate from the negotiation loop's own escalation logic (which handles max rounds, low confidence, validation failure). The trigger engine adds the additional configurable triggers specified in HUMAN-02.

**Example:**
```python
from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from anthropic import Anthropic
from pydantic import BaseModel, Field

from negotiation.llm.client import INTENT_MODEL


class TriggerType(StrEnum):
    """Types of escalation triggers."""
    CPM_OVER_THRESHOLD = "cpm_over_threshold"
    AMBIGUOUS_INTENT = "ambiguous_intent"
    HOSTILE_TONE = "hostile_tone"
    LEGAL_LANGUAGE = "legal_language"
    UNUSUAL_DELIVERABLES = "unusual_deliverables"


class TriggerConfig(BaseModel):
    """Configuration for a single escalation trigger."""
    enabled: bool = True
    # For CPM trigger
    cpm_threshold: float | None = None
    # For LLM-based triggers: optional keywords that always trigger (bypass LLM)
    always_trigger_keywords: list[str] = Field(default_factory=list)


class EscalationTriggersConfig(BaseModel):
    """Root configuration for all escalation triggers.

    Loaded from YAML config file and validated by Pydantic.
    """
    cpm_over_threshold: TriggerConfig = Field(
        default_factory=lambda: TriggerConfig(cpm_threshold=30.0)
    )
    ambiguous_intent: TriggerConfig = Field(default_factory=TriggerConfig)
    hostile_tone: TriggerConfig = Field(default_factory=TriggerConfig)
    legal_language: TriggerConfig = Field(default_factory=TriggerConfig)
    unusual_deliverables: TriggerConfig = Field(default_factory=TriggerConfig)


class TriggerResult(BaseModel):
    """Result of evaluating a single trigger."""
    trigger_type: TriggerType
    fired: bool
    reason: str = ""
    evidence: str = ""


DEFAULT_TRIGGERS_PATH = Path(__file__).resolve().parents[3] / "config" / "escalation_triggers.yaml"


def load_triggers_config(
    path: Path = DEFAULT_TRIGGERS_PATH,
) -> EscalationTriggersConfig:
    """Load and validate escalation trigger config from YAML file."""
    if not path.exists():
        return EscalationTriggersConfig()  # All defaults (all enabled)

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return EscalationTriggersConfig()

    return EscalationTriggersConfig.model_validate(raw)
```

### Config File Format Recommendation

**Claude's Discretion: Config file format for escalation triggers (YAML vs JSON).**

**Recommendation: YAML.** Rationale:

1. **Human editability.** The locked decision says "team can edit without code changes." YAML supports inline comments explaining each trigger, which is critical for non-developer editors. JSON does not support comments.
2. **Readability.** YAML's indentation-based structure reads more naturally than JSON's braces/brackets. For a config file with nested settings, YAML is significantly cleaner.
3. **Consistency with knowledge base philosophy.** Phase 3 chose Markdown for the knowledge base because non-technical editors need to update it. The same principle applies here: YAML is the natural config counterpart to Markdown content.
4. **PyYAML is well-established.** PyYAML (v6.0.2) with `safe_load` is the standard Python YAML parser. Adding it is a single lightweight dependency.

**Example `config/escalation_triggers.yaml`:**
```yaml
# Escalation Trigger Configuration
# Edit this file to enable/disable triggers or change thresholds.
# All triggers are enabled by default.

# Fires when influencer's proposed CPM exceeds this threshold
cpm_over_threshold:
  enabled: true
  cpm_threshold: 30.0   # dollars per thousand views

# Fires when intent classification confidence is below threshold
# (Note: this also triggers in the negotiation loop itself)
ambiguous_intent:
  enabled: true

# Fires when email tone is hostile, aggressive, or threatening
# Uses LLM-based detection (not keyword matching)
hostile_tone:
  enabled: true
  # These keywords always trigger escalation immediately (bypass LLM):
  always_trigger_keywords: []

# Fires when email contains legal or contract-related language
# Uses LLM-based detection (not keyword matching)
legal_language:
  enabled: true
  always_trigger_keywords: []

# Fires when influencer requests unusual or non-standard deliverables
# Uses LLM-based detection
unusual_deliverables:
  enabled: true
```

### LLM-Based Trigger Classification

**What:** For hostile tone, legal/contract language, and unusual deliverable requests, use a lightweight Claude Haiku call with structured outputs to classify the email text.
**When to use:** HUMAN-02 triggers that require semantic understanding.

```python
class TriggerClassification(BaseModel):
    """Structured output for LLM-based trigger detection."""
    hostile_tone_detected: bool = Field(
        description="True if the email contains hostile, aggressive, or threatening language"
    )
    hostile_evidence: str = Field(
        default="",
        description="Quote from the email that demonstrates hostile tone. Empty if not detected."
    )
    legal_language_detected: bool = Field(
        description="True if the email contains legal or contract-related language"
    )
    legal_evidence: str = Field(
        default="",
        description="Quote from the email demonstrating legal/contract language. Empty if not detected."
    )
    unusual_deliverables_detected: bool = Field(
        description="True if the email requests unusual or non-standard deliverables"
    )
    unusual_evidence: str = Field(
        default="",
        description="Quote describing the unusual deliverable request. Empty if not detected."
    )


def classify_triggers(
    email_body: str,
    client: Anthropic,
    model: str = INTENT_MODEL,
) -> TriggerClassification:
    """Classify an email for tone, legal, and deliverable triggers.

    Uses Claude Haiku structured outputs for fast, cheap classification.
    This runs BEFORE the main intent classification to catch escalation
    triggers early.
    """
    response = client.messages.parse(
        model=model,
        max_tokens=512,
        system="""Analyze this influencer email for three escalation triggers:

1. HOSTILE TONE: Aggressive, threatening, condescending, or hostile language.
   Examples: threats to go public, demands with ultimatums, insults, passive-aggressive remarks.
   NOT hostile: firm negotiation, simple disagreement, declining an offer politely.

2. LEGAL/CONTRACT LANGUAGE: References to contracts, lawyers, legal action, terms and conditions,
   NDAs, exclusivity clauses, intellectual property, licensing, or legal representatives.
   NOT legal: casual mention of "deal" or "agreement" in normal negotiation context.

3. UNUSUAL DELIVERABLES: Requests for deliverables outside standard platform content
   (posts, stories, reels, videos, shorts). Examples: event appearances, product design
   input, long-term ambassadorship, content licensing, whitelisting/paid ads with their content.
   NOT unusual: standard platform deliverables even if quantity is high.

For each trigger, quote the SPECIFIC text from the email that triggered the detection.
If not detected, leave evidence empty.""",
        messages=[
            {"role": "user", "content": f"Analyze this email:\n\n{email_body}"},
        ],
        output_format=TriggerClassification,
    )

    parsed = response.parsed_output
    if parsed is None:
        raise RuntimeError("Trigger classification returned None")
    return parsed
```

**Key design decisions:**
- Uses Haiku (same as intent classification) for speed and cost. This call is ~300 input tokens + ~100 output tokens = ~$0.0008 per email.
- Combines all three LLM-based triggers into a single API call to minimize latency and cost.
- Returns evidence quotes for each trigger, enabling the "specific reason with evidence" locked decision.
- Runs before the main negotiation loop as a gate -- if any trigger fires, the email is escalated before reaching intent classification.

### Pattern 4: Human Takeover Detection

**Claude's Discretion: Human reply detection method in email threads.**

**Recommendation: Gmail API `threads.get()` with `From` header comparison.**

**How it works:** The agent knows its own sending email address (the `from_email` configured in `GmailClient`). When checking a thread for human replies, fetch all messages in the thread via `threads.get(format="metadata")`, extract the `From` header from each message, and check if any message was sent from an address that is:
1. Not the influencer's email, AND
2. Not the agent's email

If such a message exists AND it was sent after the agent's last message, a human team member has replied in the thread.

**Why this approach:**
- Uses existing Gmail API capabilities (Phase 2's `get_thread_context` already fetches thread metadata).
- No additional infrastructure or webhooks needed.
- Deterministic check -- no LLM required.
- The agent's email and the influencer's email are known quantities; any third sender must be a human team member.

**Example:**
```python
from typing import Any


def detect_human_reply(
    service: Any,
    thread_id: str,
    agent_email: str,
    influencer_email: str,
) -> bool:
    """Check if a human team member has replied in a negotiation thread.

    Fetches all messages in the thread and checks if any message was sent
    by someone other than the agent or the influencer.

    Args:
        service: Gmail API service resource.
        thread_id: The Gmail thread ID.
        agent_email: The email address the agent sends from.
        influencer_email: The influencer's email address.

    Returns:
        True if a human team member has replied in the thread.
    """
    thread = (
        service.users()
        .threads()
        .get(
            userId="me",
            id=thread_id,
            format="metadata",
            metadataHeaders=["From"],
        )
        .execute()
    )

    known_senders = {agent_email.lower(), influencer_email.lower()}

    for message in thread.get("messages", []):
        headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}
        from_header = headers.get("From", "").lower()

        # Extract just the email address from "Name <email>" format
        if "<" in from_header and ">" in from_header:
            from_email = from_header.split("<")[1].split(">")[0]
        else:
            from_email = from_header.strip()

        if from_email not in known_senders:
            return True

    return False
```

**Edge cases handled:**
- `From` header format varies: sometimes `"John <john@company.com>"`, sometimes just `"john@company.com"`. The parser handles both.
- Multiple team members could reply -- any non-agent, non-influencer sender triggers detection.
- Check is called before each negotiation loop iteration (not as a real-time webhook).

### Pattern 5: Slack Slash Commands

**What:** Bolt for Python handles `/claim` and `/resume` slash commands for human takeover and handback.
**When to use:** HUMAN-04 (human takeover).

**Example:**
```python
import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


# Initialize Bolt app
app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.command("/claim")
def handle_claim(ack, respond, command):
    """Handle /claim command to take over a negotiation thread.

    Usage: /claim @influencer_name_or_email
    Effect: Marks the thread as human-managed, agent stops processing.
    """
    ack()
    identifier = command["text"].strip()
    if not identifier:
        respond("Usage: `/claim @influencer_name_or_email`")
        return

    # Look up thread by influencer identifier
    # (Implementation depends on thread storage -- see Open Questions)
    # mark_thread_as_human_managed(identifier)

    respond(f"Thread claimed for {identifier}. Agent will stop processing this negotiation.")


@app.command("/resume")
def handle_resume(ack, respond, command):
    """Handle /resume command to hand a thread back to the agent.

    Usage: /resume @influencer_name_or_email
    Effect: Removes human-managed flag, agent resumes processing.
    """
    ack()
    identifier = command["text"].strip()
    if not identifier:
        respond("Usage: `/resume @influencer_name_or_email`")
        return

    # mark_thread_as_agent_managed(identifier)

    respond(f"Thread resumed for {identifier}. Agent will handle this negotiation again.")


def start_slack_app():
    """Start the Bolt app in Socket Mode."""
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
```

**Slack App Setup Requirements:**
1. Create a Slack app at https://api.slack.com/apps
2. Enable Socket Mode under "Socket Mode" settings
3. Generate an App-Level Token with `connections:write` scope (this is `SLACK_APP_TOKEN`)
4. Add Bot Token Scopes: `chat:write`, `commands`
5. Create slash commands: `/claim` and `/resume`
6. Install to workspace -- generates `SLACK_BOT_TOKEN` (xoxb- prefix)

**Environment variables needed:**
- `SLACK_BOT_TOKEN` -- Bot token (xoxb-...) for posting messages
- `SLACK_APP_TOKEN` -- App-level token (xapp-...) for Socket Mode connection

### Anti-Patterns to Avoid

- **Putting Block Kit JSON inline in the client module:** Separate block-building (blocks.py) from posting (client.py). Block builders are pure functions that return dicts -- easy to test, easy to modify. The client just sends what it receives.
- **Hardcoding channel IDs in source code:** Channel IDs should be in configuration (environment variables or config file). Channels change; code should not need to change when they do.
- **Using incoming webhooks for the whole integration:** Webhooks are fire-and-forget for a single channel. They cannot support slash commands, interactive elements, or posting to multiple channels. Use a proper bot token.
- **Polling Gmail for human replies:** Do not set up a polling loop to check threads. Instead, check for human replies opportunistically -- when a new message arrives in a thread and the agent is about to process it, check first. This avoids unnecessary API calls.
- **Mixing Slack concerns into the negotiation loop:** The negotiation loop (Phase 3) should remain Slack-agnostic. It returns action dicts. A new orchestration layer in Phase 4 takes those action dicts and dispatches to Slack. This keeps the negotiation logic testable without Slack dependencies.
- **Using the same LLM model for trigger classification and email composition:** Trigger classification needs speed, not quality. Use Haiku, not Sonnet.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Slack message formatting | Manual JSON dict construction for every message | Block Kit builder functions (blocks.py) with reusable patterns | Block Kit has specific JSON schema rules (max fields, text type requirements). Centralizing builders prevents invalid block structures. |
| WebSocket connection to Slack | Custom WebSocket client for receiving commands | Bolt `SocketModeHandler` | Handles reconnection, heartbeats, error recovery, message acknowledgment. The protocol is non-trivial. |
| YAML config validation | Manual dict key checking after yaml.safe_load | Pydantic model with `model_validate()` | Pydantic provides type coercion, default values, validation errors with field paths. Manual checking is fragile and verbose. |
| Email address parsing from "From" header | Manual string splitting for "Name <email>" | Python `email.utils.parseaddr()` (stdlib) | Handles edge cases: quoted names, multiple addresses, malformed headers. |
| Slash command argument parsing | Manual string.split() on command text | Simple pattern matching or regex | Bolt provides the command text as a string. For `/claim email@example.com`, parsing is trivial. For future complex args, consider `shlex.split()`. |

**Key insight:** Phase 4 is an integration phase -- it connects existing systems (Phase 3 negotiation loop, Phase 2 Gmail client) to a new system (Slack). The value is in clean wiring, not complex logic. Keep each module small and focused.

## Common Pitfalls

### Pitfall 1: Slack Rate Limiting
**What goes wrong:** The app posts too many messages in rapid succession and gets rate-limited (HTTP 429). Escalation messages are silently dropped.
**Why it happens:** Slack's Web API rate limit is approximately 1 message per second per channel. During batch operations or testing, this limit is easily hit.
**How to avoid:** (1) The `slack-sdk` WebClient has built-in retry handling for 429 responses with exponential backoff. (2) For v1, negotiation volume is low enough that rate limiting is unlikely. (3) If scaling, add a message queue between the trigger engine and the Slack client.
**Warning signs:** `SlackApiError` with `response['error'] == 'ratelimited'` in logs.

### Pitfall 2: Stale Slash Command Acknowledgment
**What goes wrong:** The `/claim` command takes longer than 3 seconds to process, and Slack shows "This slash command experienced an error" to the user.
**Why it happens:** Slack requires slash commands to be acknowledged (`ack()`) within 3 seconds. If the handler does database lookups or API calls before acknowledging, it can time out.
**How to avoid:** Always call `ack()` immediately at the start of the handler function, before any processing. Use `respond()` (which works for up to 30 minutes after the command) for the actual response after processing completes.
**Warning signs:** Users reporting "error" messages when using slash commands, but the action actually completes.

### Pitfall 3: Block Kit Field Limits
**What goes wrong:** A section block with more than 10 fields throws an `invalid_blocks` error. Or a text field exceeding 3000 characters is silently truncated.
**Why it happens:** Block Kit has strict limits: max 10 fields per section, max 3000 chars for mrkdwn text, max 50 blocks per message.
**How to avoid:** (1) The escalation and agreement block builders should enforce these limits. (2) For long evidence quotes, truncate with "..." and include the full text in the details link. (3) Test with realistic data that approaches these limits.
**Warning signs:** `invalid_blocks` errors from `chat_postMessage`. Messages that look truncated.

### Pitfall 4: Human Detection False Positives
**What goes wrong:** An automated system (e.g., a calendar invite, an email forwarding rule, or an out-of-office reply) triggers human detection, causing the agent to stop processing a thread.
**Why it happens:** Any email in the thread from a non-agent, non-influencer address triggers detection. Automated systems send emails too.
**How to avoid:** (1) Check the `From` header against a known list of team member emails in addition to the basic agent/influencer check. (2) Alternatively, only consider messages that are direct replies (have `In-Reply-To` header matching a message in the thread), not auto-forwarded or auto-generated messages. (3) For v1, accept this edge case -- the `/resume` command provides recovery.
**Warning signs:** Agent stops processing threads that no human has actually replied to.

### Pitfall 5: Missing Channel Configuration
**What goes wrong:** The app starts but crashes when trying to post because `SLACK_BOT_TOKEN` or channel IDs are not configured.
**Why it happens:** Environment variables not set in deployment, or channel IDs changed after a Slack workspace reorganization.
**How to avoid:** (1) Validate all required environment variables at startup, fail fast with clear error messages. (2) Store channel IDs in configuration (not hardcoded). (3) Test the Slack connection at startup by calling `auth.test` to verify the token works.
**Warning signs:** `SlackApiError` with `channel_not_found` or `invalid_auth`.

### Pitfall 6: Trigger Config File Missing or Invalid
**What goes wrong:** Someone edits the YAML config and introduces a syntax error (e.g., wrong indentation). The trigger engine crashes or uses unexpected defaults.
**Why it happens:** YAML is sensitive to indentation. Non-technical editors may not realize a misplaced space breaks the file.
**How to avoid:** (1) Pydantic validation catches structural errors and provides clear messages. (2) Fall back to all-defaults if the file is missing or unparseable (log a warning but don't crash). (3) Include a comment header in the YAML file explaining the format. (4) Consider adding a simple CLI command to validate the config: `python -m negotiation.slack.triggers validate`.
**Warning signs:** All triggers suddenly disabled. Unexpected escalation behavior after a config edit.

## Code Examples

### Slack App Startup with Validation

```python
# Source: https://docs.slack.dev/tools/python-slack-sdk/web/
import os
import sys

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def validate_slack_config() -> dict[str, str]:
    """Validate all required Slack environment variables at startup.

    Returns:
        Dict with validated config values.

    Raises:
        SystemExit: If required variables are missing.
    """
    required = {
        "SLACK_BOT_TOKEN": os.environ.get("SLACK_BOT_TOKEN"),
        "SLACK_APP_TOKEN": os.environ.get("SLACK_APP_TOKEN"),
        "SLACK_ESCALATION_CHANNEL": os.environ.get("SLACK_ESCALATION_CHANNEL"),
        "SLACK_AGREEMENT_CHANNEL": os.environ.get("SLACK_AGREEMENT_CHANNEL"),
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Verify bot token works
    client = WebClient(token=required["SLACK_BOT_TOKEN"])
    try:
        auth_response = client.auth_test()
        print(f"Slack connected as: {auth_response['user']}")
    except SlackApiError as e:
        print(f"Slack auth failed: {e.response['error']}")
        sys.exit(1)

    return {k: v for k, v in required.items() if v is not None}
```

### Testing Block Kit Builders (No Mocks Needed)

```python
from negotiation.slack.blocks import build_escalation_blocks


def test_escalation_blocks_contain_required_fields():
    """Block builders are pure functions -- test without mocks."""
    blocks = build_escalation_blocks(
        influencer_name="Jane Creator",
        influencer_email="jane@example.com",
        client_name="Acme Brand",
        escalation_reason="CPM over threshold ($35 vs $30 limit)",
        evidence_quote="I typically charge $3,500 for this kind of content",
        proposed_rate="3500",
        our_rate="2500",
        suggested_actions=["Reply with counter at $3,000", "Approve $3,500 rate"],
        details_link="https://mail.google.com/mail/u/0/#inbox/abc123",
    )

    # Verify structure
    assert blocks[0]["type"] == "header"
    assert "Jane Creator" in blocks[0]["text"]["text"]

    # Verify all required fields present in the message
    full_text = str(blocks)
    assert "jane@example.com" in full_text
    assert "Acme Brand" in full_text
    assert "CPM over threshold" in full_text
    assert "$3,500" in full_text or "3500" in full_text
```

### Testing SlackNotifier with Mocked WebClient

```python
from unittest.mock import MagicMock

from negotiation.slack.client import SlackNotifier


def test_post_escalation_calls_correct_channel():
    """Test that escalation messages go to the escalation channel."""
    mock_client = MagicMock()
    mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}

    notifier = SlackNotifier(
        escalation_channel="C_ESCALATION",
        agreement_channel="C_AGREEMENTS",
        bot_token="xoxb-test-token",
    )
    # Inject mock
    notifier._client = mock_client

    ts = notifier.post_escalation(
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}],
        fallback_text="Escalation: Test",
    )

    mock_client.chat_postMessage.assert_called_once_with(
        channel="C_ESCALATION",
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Test"}}],
        text="Escalation: Test",
    )
    assert ts == "1234567890.123456"
```

### Extending EscalationPayload for Phase 4

The existing `EscalationPayload` from Phase 3 needs additional fields for the Slack message requirements:

```python
# Extension to existing EscalationPayload in llm/models.py
class EscalationPayload(BaseModel):
    """Data structure for human escalation.

    Phase 3 fields: reason, email_draft, validation_failures,
    influencer_name, thread_id, proposed_rate, our_rate.

    Phase 4 additions: influencer_email, client_name, evidence_quote,
    suggested_actions, trigger_type.
    """
    reason: str
    email_draft: str
    validation_failures: list[ValidationFailure] = Field(default_factory=list)
    influencer_name: str
    thread_id: str
    proposed_rate: Decimal | None = None
    our_rate: Decimal | None = None
    # Phase 4 additions
    influencer_email: str = ""
    client_name: str = ""
    evidence_quote: str = ""
    suggested_actions: list[str] = Field(default_factory=list)
    trigger_type: str = ""
```

New fields have defaults so existing Phase 3 code continues to work without changes.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Incoming webhooks for Slack notifications | Bot tokens with `WebClient.chat_postMessage` and Block Kit | 2020+ | Full API access, multiple channels, interactive elements, slash commands |
| HTTP mode for Slack apps | Socket Mode (WebSocket-based) | 2021+ | No public server needed, simpler development, works behind firewalls |
| Legacy bot tokens (single `bot` scope) | Granular bot token scopes (`chat:write`, `commands`, etc.) | 2020+ | Fine-grained permissions, better security |
| `slackclient` package | `slack-sdk` package (v3+) | 2021 | New package name, better async support, Block Kit models |
| Custom message formatting | Block Kit (sections, fields, actions) | 2019+ | Standardized rich message layouts, visual consistency |

**Deprecated/outdated:**
- **`slackclient` package:** Replaced by `slack-sdk` (v3+). The old package is unmaintained.
- **Legacy bot tokens (umbrella `bot` scope):** Replaced by granular scopes. New apps must use granular scopes.
- **RTM (Real Time Messaging) API:** Deprecated in favor of Events API + Socket Mode. Do not use RTM for new apps.
- **Message attachments:** While still supported, Slack recommends Block Kit for all new message formatting. Attachments are legacy.

## Model Extensions Required

### AgreementPayload (New Model)

The negotiation loop currently returns `{"action": "accept", "classification": classification}` but does not include all the data required for the agreement Slack alert. A new `AgreementPayload` model is needed:

```python
class AgreementPayload(BaseModel):
    """Data for agreement Slack notifications (HUMAN-03)."""
    influencer_name: str
    influencer_email: str
    client_name: str
    agreed_rate: Decimal
    platform: str
    deliverables: str
    cpm_achieved: Decimal
    thread_id: str
    next_steps: list[str] = Field(default_factory=list)
    mention_users: list[str] = Field(default_factory=list)
```

This model is constructed by the Phase 4 orchestration layer (not inside the negotiation loop) by combining data from the IntentClassification, the negotiation context dict, and the pricing engine.

### Thread Management State

Human takeover requires tracking which threads are human-managed. For v1, a simple in-memory dict is sufficient (the agent is a single process):

```python
# thread_id -> {"managed_by": "human" | "agent", "claimed_by": "user_id" | None}
_thread_state: dict[str, dict[str, str | None]] = {}
```

For persistence across restarts, this could be stored in a JSON file or a future database. Phase 5 (audit trail) may introduce proper persistence.

## Open Questions

1. **Thread state persistence across restarts**
   - What we know: The `/claim` and `/resume` commands need to track which threads are human-managed. The human detection check also needs to record its findings.
   - What's unclear: Is the agent a long-running process or invoked per-event? If long-running, in-memory state works. If per-event, state must be persisted.
   - Recommendation: Start with in-memory dict. Add file-based persistence (JSON file in a `state/` directory) if restarts are frequent. Phase 5's audit trail may provide a proper persistence solution.

2. **Client name availability**
   - What we know: The locked decision requires "client name" in both escalation and agreement messages. The current `negotiation_context` dict and `InfluencerRow` model do not include a client/brand name.
   - What's unclear: Where does the client name come from? The Google Sheet (Phase 2)? Campaign data (Phase 5)?
   - Recommendation: Add `client_name` to the negotiation context dict. For v1, it can be a config value (one client) or a column in the Google Sheet. Campaign data ingestion (Phase 5) will provide proper per-campaign client names.

3. **Per-campaign mention users**
   - What we know: The locked decision says "configurable per-campaign tagging -- campaign data specifies who to @ mention."
   - What's unclear: Campaign data ingestion is Phase 5 (out of scope). How do we support per-campaign mentions in v1?
   - Recommendation: For v1, store default mention user IDs in the trigger config YAML or a separate Slack config. When Phase 5 adds campaign data, the mention list can be sourced from there instead.

4. **Concurrent thread processing**
   - What we know: Multiple negotiation threads may be active simultaneously. The agent needs to check human takeover before processing each thread.
   - What's unclear: Does the agent process threads sequentially or in parallel? If parallel, the in-memory thread state needs thread safety.
   - Recommendation: Process threads sequentially for v1. The volume is low enough that parallelism is not needed. If parallelism is added later, use a threading lock on the state dict.

5. **Slack app deployment model**
   - What we know: The Bolt app needs to be running continuously to receive slash commands via Socket Mode.
   - What's unclear: Does the Slack app run as a separate process from the negotiation agent? Or is it integrated into the same process?
   - Recommendation: Run as a single process. The Bolt `SocketModeHandler.start()` blocks the main thread. The negotiation loop (triggered by Gmail push notifications) can run in a separate thread or be event-driven. For v1, a simple architecture is: Bolt app runs in main thread, Gmail push notification handler runs the negotiation loop in response to events.

## Sources

### Primary (HIGH confidence)
- [Slack SDK for Python (PyPI)](https://pypi.org/project/slack-sdk/) -- v3.40.0, released Feb 2026, actively maintained
- [Slack Bolt for Python (PyPI)](https://pypi.org/project/slack-bolt/) -- v1.27.0, official Slack app framework
- [Bolt for Python - Commands](https://docs.slack.dev/tools/bolt-python/concepts/commands) -- Slash command handling with ack/respond pattern
- [Bolt for Python - Socket Mode](https://docs.slack.dev/tools/bolt-python/concepts/socket-mode/) -- WebSocket-based connection, no public endpoint needed
- [Slack WebClient Documentation](https://docs.slack.dev/tools/python-slack-sdk/web/) -- chat_postMessage with blocks parameter, Block Kit integration
- [Block Kit Documentation](https://docs.slack.dev/block-kit/) -- Block types, field limits, mrkdwn formatting
- [Gmail API - threads.get](https://developers.google.com/gmail/api/reference/rest/v1/users.threads/get) -- Thread metadata retrieval with format="metadata"

### Secondary (MEDIUM confidence)
- [Slack Block Kit Builder Guide (MagicBell)](https://www.magicbell.com/blog/slack-blocks) -- Practical examples of section blocks, fields, actions
- [Block Kit Deep Dive (Knock)](https://knock.app/blog/taking-a-deep-dive-into-slack-block-kit) -- Block limits, best practices for rich messages
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) -- safe_load usage, YAML parsing
- [Pydantic Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) -- BaseSettings pattern, YAML integration approaches

### Tertiary (LOW confidence)
- [Structuring LLM Outputs for Legal Prompt Engineering](https://studio.netdocuments.com/post/structuring-llm-outputs) -- Patterns for legal text classification. Used to inform the trigger classification prompt design. Needs validation with real influencer emails.
- [LLM Contract Smell Detection (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2666827025000222) -- Academic research on LLM-based contract language detection. Relevant for the legal_language trigger design but not directly actionable.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- `slack-sdk` and `slack-bolt` are the official Slack Python libraries, actively maintained, with clear documentation. PyYAML is the standard Python YAML parser. All verified against PyPI and official docs.
- Architecture: HIGH -- Block Kit message building, WebClient posting, and Socket Mode slash commands follow established patterns documented in official Slack guides. The separation of blocks (pure functions) from client (I/O) is a standard testability pattern.
- Triggers: HIGH (deterministic triggers) / MEDIUM (LLM-based triggers) -- Deterministic triggers are straightforward config-driven checks. LLM-based tone/legal detection works well with Claude structured outputs (proven in Phase 3 intent classification), but the specific prompt for hostile tone and legal language needs validation with real influencer emails.
- Human detection: HIGH -- Gmail API thread metadata retrieval and `From` header comparison is deterministic and well-documented. Edge cases (auto-replies, forwarded messages) are identified with mitigations.
- Pitfalls: HIGH -- Rate limiting, ack timeouts, Block Kit limits, and configuration validation are all well-documented in Slack's official troubleshooting guides.

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (30 days -- Slack SDK updates monthly, API is stable; Gmail API is stable)
