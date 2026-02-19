# Phase 2: Email and Data Integration - Research

**Researched:** 2026-02-18
**Domain:** Gmail API, Google Sheets API, MIME email parsing, Google Cloud Pub/Sub
**Confidence:** MEDIUM-HIGH

## Summary

Phase 2 adds two external integration capabilities to the existing negotiation agent: (1) sending and receiving emails via the Gmail API with proper threading, and (2) reading influencer data from Google Sheets. Both rely on Google Cloud Platform authentication and the `google-api-python-client` library ecosystem.

The Gmail integration is the more complex half. Sending threaded emails requires correctly setting `threadId`, `References`, `In-Reply-To`, and `Subject` headers on RFC 2822 MIME messages. Receiving replies requires either Gmail API push notifications via Google Cloud Pub/Sub (real-time) or polling via `history.list()` (simpler). Parsing reply content from multipart MIME messages, inline replies, and forwarded messages requires a dedicated reply-parsing library to avoid hand-rolling fragile heuristics.

The Google Sheets integration is comparatively straightforward. The `gspread` library provides a clean Python API over Google Sheets API v4, supporting service account authentication and simple row lookup. The agent needs to locate an influencer row by name/handle and extract their pre-calculated pay range (min/max based on $20-$30 CPM and average views).

**Primary recommendation:** Use `google-api-python-client` for Gmail API, `gspread` for Google Sheets, `mail-parser-reply` for email reply parsing, and start with Pub/Sub pull subscription for receiving notifications (defer push webhooks to a later phase if not immediately needed).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EMAIL-01 | Agent can send emails via Gmail API on behalf of the team | Gmail API `messages.send` with OAuth2 credentials, `gmail.send` scope, base64url-encoded MIME messages. See [Sending Email](#pattern-1-sending-an-email-via-gmail-api) and [Authentication](#authentication-architecture). |
| EMAIL-02 | Agent can receive and process inbound emails via Gmail API with push notifications | Gmail API `users.watch()` + Cloud Pub/Sub topic + `history.list()` to fetch new messages. See [Receiving Emails](#pattern-2-receiving-emails-via-pubsub-notifications) and [Pub/Sub Setup](#pubsub-setup). |
| EMAIL-03 | Agent maintains email thread context so influencers see a coherent conversation history | Set `threadId`, `References`, `In-Reply-To` headers, match `Subject`. See [Email Threading](#pattern-3-replying-within-an-email-thread). |
| EMAIL-04 | Agent can parse influencer reply content from email threads (handle MIME, inline replies, forwarding) | `mail-parser-reply` library for reply extraction + Python `email` stdlib for MIME parsing. See [MIME Parsing](#pattern-4-parsing-mime-email-content-and-extracting-reply-text). |
| NEG-01 | Agent reads influencer data from a Google Sheet, locates the row for the influencer being negotiated with, and pulls the proposed pay range based on $20-$30 CPM | `gspread` `get_all_records()` + Python filtering to locate row, construct `PayRange` from sheet data. See [Reading Influencer Data](#pattern-5-reading-influencer-data-from-google-sheets). |
| DATA-02 | Agent connects to a Google Sheet to read influencer outreach data (name, contact info, platform, metrics, pre-calculated pay range) | `gspread` with service account auth, `open_by_key()` to connect, `get_all_records()` for structured data. See [Google Sheets Integration](#google-sheets-integration). |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `google-api-python-client` | >=2.190 | Gmail API v1 client (send, receive, threads) | Official Google client library, discovery-based, supports all Gmail endpoints |
| `google-auth` | >=2.0 | OAuth2 authentication and credential management | Official Google auth library, handles token refresh |
| `google-auth-oauthlib` | >=1.0 | OAuth2 flow for desktop/installed apps | Official integration between google-auth and oauthlib |
| `google-auth-httplib2` | >=0.2 | Transport adapter for google-api-python-client | Required by google-api-python-client |
| `gspread` | >=6.2 | Google Sheets API v4 Python wrapper | De facto standard for Sheets in Python (6k+ GitHub stars), clean API, handles auth |
| `mail-parser-reply` | >=1.36 | Extract latest reply from email threads | Actively maintained (Dec 2025), supports 13 languages, handles inline/forwarded/quoted content |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `google-cloud-pubsub` | >=2.0 | Pub/Sub client for Gmail push notifications | When implementing EMAIL-02 (receiving email notifications) |
| `google-api-python-client-stubs` | >=1.29 | Type stubs for mypy strict mode | Dev dependency -- provides type annotations for `build()` return types |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `gspread` | Raw `google-api-python-client` Sheets v4 | gspread is a much simpler API for read-only access; raw client needed only for complex write operations |
| `mail-parser-reply` | `email-reply-parser` (Zapier) | Original is unmaintained since ~2020; `mail-parser-reply` is actively maintained with multi-language support |
| `mail-parser-reply` | Hand-rolled regex parsing | Email reply parsing is deceptively complex (see Don't Hand-Roll section) |
| Pub/Sub pull subscription | Pub/Sub push (webhook) | Pull is simpler for dev/testing -- no public HTTPS endpoint needed; push is better for production latency |
| Pub/Sub notifications | Polling `messages.list` | Polling wastes API quota and adds latency; Pub/Sub is Google's recommended approach |
| OAuth2 user credentials | Service account + domain-wide delegation | Domain-wide delegation requires Google Workspace admin; OAuth2 works with any Gmail account |

**Installation:**
```bash
uv add google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2 gspread mail-parser-reply google-cloud-pubsub
uv add --group dev google-api-python-client-stubs
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── negotiation/
│   ├── domain/          # (Phase 1 -- exists) models, types, errors
│   ├── pricing/         # (Phase 1 -- exists) rate calculation, boundaries
│   ├── state_machine/   # (Phase 1 -- exists) negotiation lifecycle
│   ├── email/           # (Phase 2 -- NEW) Gmail API integration
│   │   ├── __init__.py
│   │   ├── client.py       # Gmail API client wrapper (send, read, watch)
│   │   ├── threading.py    # Thread management (headers, threadId tracking)
│   │   ├── parser.py       # MIME parsing and reply extraction
│   │   └── models.py       # Email-related Pydantic models (EmailMessage, ThreadContext)
│   ├── sheets/          # (Phase 2 -- NEW) Google Sheets integration
│   │   ├── __init__.py
│   │   ├── client.py       # gspread client wrapper (read influencer data)
│   │   └── models.py       # Sheet-related Pydantic models (InfluencerRow)
│   └── auth/            # (Phase 2 -- NEW) Shared Google API authentication
│       ├── __init__.py
│       └── credentials.py  # OAuth2/service account credential management
```

### Authentication Architecture

**Decision: OAuth2 user credentials for Gmail, service account for Sheets.**

Rationale:
- Gmail API requires user consent or Google Workspace domain-wide delegation. OAuth2 user credentials work with any Gmail account (including free accounts). Domain-wide delegation only works with Google Workspace and requires admin configuration.
- Google Sheets can use a service account (share the sheet with the service account email). This is simpler for read-only, automated access.
- Both can share the same GCP project.

**Credential flow:**
1. On first run, OAuth2 flow opens browser for Gmail consent
2. Token stored in `token.json` (gitignored)
3. `google-auth` handles automatic token refresh via refresh_token
4. Service account credentials loaded from JSON file for Sheets

**Scopes needed:**
- Gmail: `gmail.send` (sensitive) + `gmail.readonly` (restricted) -- or `gmail.modify` (restricted) which covers both
- Sheets: `https://www.googleapis.com/auth/spreadsheets.readonly` (via gspread)

**Confidence:** MEDIUM -- The OAuth2 vs service account split is well-established, but the specific scope combination needs validation. Using `gmail.modify` instead of separate `gmail.send` + `gmail.readonly` simplifies to one scope but is broader than strictly necessary. The project may need to go through Google's OAuth verification process for restricted scopes, which adds friction.

### Pattern 1: Sending an Email via Gmail API

**What:** Compose and send an RFC 2822 MIME email through the Gmail API
**When to use:** EMAIL-01, initial outreach or replies to influencers

**Example:**
```python
# Source: https://developers.google.com/gmail/api/guides/sending
import base64
from email.message import EmailMessage
from googleapiclient.discovery import build

def send_email(
    service,  # Gmail API service object
    to: str,
    subject: str,
    body: str,
    from_email: str,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> dict:
    """Send an email, optionally within an existing thread."""
    message = EmailMessage()
    message.set_content(body)
    message["To"] = to
    message["From"] = from_email
    message["Subject"] = subject

    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    if references:
        message["References"] = references

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body_payload: dict = {"raw": encoded}
    if thread_id:
        body_payload["threadId"] = thread_id

    return service.users().messages().send(
        userId="me", body=body_payload
    ).execute()
```

### Pattern 2: Receiving Emails via Pub/Sub Notifications

**What:** Set up Gmail watch + Pub/Sub to get notified of new emails
**When to use:** EMAIL-02, detecting influencer replies

**Example:**
```python
# Source: https://developers.google.com/gmail/api/guides/push
# Step 1: Set up watch (call on startup + daily renewal)
def setup_watch(service, topic_name: str) -> dict:
    """Register Gmail to push notifications to Pub/Sub topic."""
    request = {
        "labelIds": ["INBOX"],
        "topicName": topic_name,  # e.g., "projects/my-project/topics/gmail-notifications"
        "labelFilterBehavior": "INCLUDE",
    }
    return service.users().watch(userId="me", body=request).execute()
    # Returns: {"historyId": "12345", "expiration": "1234567890000"}

# Step 2: Process notification (Pub/Sub callback)
import json
def process_notification(message_data: bytes, last_history_id: str, service):
    """Handle a Pub/Sub notification about mailbox changes."""
    data = json.loads(base64.urlsafe_b64decode(message_data))
    new_history_id = data["historyId"]

    # Step 3: Fetch changes since last known historyId
    history = service.users().history().list(
        userId="me",
        startHistoryId=last_history_id,
        historyTypes=["messageAdded"],
    ).execute()

    new_message_ids = []
    for record in history.get("history", []):
        for msg_added in record.get("messagesAdded", []):
            new_message_ids.append(msg_added["message"]["id"])

    return new_message_ids, new_history_id
```

### Pattern 3: Replying Within an Email Thread

**What:** Send a reply that appears in the same Gmail thread as the original conversation
**When to use:** EMAIL-03, maintaining negotiation conversation continuity

**Threading requirements (all three must be met):**
1. `threadId` must be set on the outgoing message
2. `References` and `In-Reply-To` headers must reference the original `Message-ID`
3. `Subject` must match (typically "Re: " + original subject)

**Example:**
```python
# Source: https://developers.google.com/gmail/api/guides/threads
def get_thread_context(service, thread_id: str) -> dict:
    """Extract threading headers from the latest message in a thread."""
    thread = service.users().threads().get(
        userId="me", id=thread_id, format="metadata",
        metadataHeaders=["Message-ID", "Subject", "From"],
    ).execute()

    latest_msg = thread["messages"][-1]
    headers = {h["name"]: h["value"] for h in latest_msg["payload"]["headers"]}

    return {
        "thread_id": thread_id,
        "message_id": headers.get("Message-ID", ""),
        "subject": headers.get("Subject", ""),
        "reply_to": headers.get("From", ""),
    }

def send_reply(service, thread_ctx: dict, body: str, from_email: str) -> dict:
    """Send a reply within an existing thread."""
    subject = thread_ctx["subject"]
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    return send_email(
        service=service,
        to=thread_ctx["reply_to"],
        subject=subject,
        body=body,
        from_email=from_email,
        thread_id=thread_ctx["thread_id"],
        in_reply_to=thread_ctx["message_id"],
        references=thread_ctx["message_id"],
    )
```

### Pattern 4: Parsing MIME Email Content and Extracting Reply Text

**What:** Read a Gmail message, decode its MIME structure, and extract just the new reply content
**When to use:** EMAIL-04, processing influencer responses

**Example:**
```python
import base64
from email import message_from_bytes
from mailparser_reply import EmailReplyParser

def get_message_content(service, message_id: str) -> str:
    """Fetch a message and extract its text content."""
    msg = service.users().messages().get(
        userId="me", id=message_id, format="raw"
    ).execute()

    raw_bytes = base64.urlsafe_b64decode(msg["raw"])
    email_msg = message_from_bytes(raw_bytes)

    # Extract text/plain body from MIME structure
    body = ""
    if email_msg.is_multipart():
        for part in email_msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
                    break
    else:
        payload = email_msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="replace")

    return body

def extract_latest_reply(full_body: str) -> str:
    """Extract only the latest reply from an email thread body."""
    parsed = EmailReplyParser(languages=["en"]).parse_reply(text=full_body)
    return parsed
```

### Pattern 5: Reading Influencer Data from Google Sheets

**What:** Connect to a Google Sheet and retrieve an influencer's row by name/handle
**When to use:** NEG-01, DATA-02, looking up pay ranges before negotiation

**Example:**
```python
# Source: https://docs.gspread.org/en/latest/user-guide.html
import gspread
from decimal import Decimal
from negotiation.domain.models import PayRange

def get_influencer_data(spreadsheet_key: str, influencer_name: str) -> dict:
    """Look up an influencer's data from the Google Sheet."""
    gc = gspread.service_account()  # Uses ~/.config/gspread/service_account.json
    sh = gc.open_by_key(spreadsheet_key)
    worksheet = sh.sheet1  # Or sh.worksheet("Influencers")

    # Fetch all records (header row becomes dict keys)
    records = worksheet.get_all_records()

    # Find the matching influencer row
    row = next(
        (r for r in records if r["Name"].strip().lower() == influencer_name.strip().lower()),
        None,
    )
    if row is None:
        raise ValueError(f"Influencer '{influencer_name}' not found in sheet")

    return row

def build_pay_range_from_sheet(row: dict) -> PayRange:
    """Construct a PayRange from sheet row data."""
    return PayRange(
        min_rate=Decimal(str(row["Min Rate"])),
        max_rate=Decimal(str(row["Max Rate"])),
        average_views=int(row["Average Views"]),
    )
```

### Anti-Patterns to Avoid
- **Storing credentials in code or version control:** Always gitignore `credentials.json`, `token.json`, `service_account.json`. Use environment variables or secure file paths.
- **Using `gmail.modify` when you only need `gmail.send` + `gmail.readonly`:** Request minimum scopes. Broader scopes require more stringent Google OAuth verification.
- **Polling Gmail for new messages:** Use Pub/Sub `watch()` + `history.list()` instead. Polling wastes quota (250 units/user/second limit) and adds latency.
- **Parsing email replies with regex:** Email formatting varies wildly across clients (Gmail, Outlook, Apple Mail, mobile). Use `mail-parser-reply` instead.
- **Fetching Sheet data row-by-row:** Use `get_all_records()` in one call, then filter in Python. Individual cell reads hit the 300 requests/60 seconds API limit quickly.
- **Using `float` for monetary values from Sheets:** Always convert to `Decimal(str(value))` to match the existing codebase pattern. Google Sheets returns numbers as `int` or `float`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Email reply extraction | Regex-based reply parser | `mail-parser-reply` | Email clients use different quoting styles (">" prefix, "On ... wrote:", "------Original Message------", etc). 13+ language variants. Multi-line signature detection. |
| MIME message construction | Manual string concatenation of headers/body | Python `email.message.EmailMessage` | RFC 2822 compliance, proper encoding, multipart handling, header folding |
| OAuth2 token refresh | Manual HTTP token refresh | `google-auth` credentials with `refresh()` | Token expiry, refresh token rotation, error handling, thread safety |
| Google Sheets cell formatting | Manual value type coercion | `gspread` `get_all_records()` | Header mapping, empty cell handling, type coercion, pagination |
| Base64url encoding | Custom base64 + URL-safe replacement | `base64.urlsafe_b64encode` / `urlsafe_b64decode` | Standard library, handles padding correctly |

**Key insight:** Email handling is one of the most deceptive "looks simple, is actually complex" domains in software. The MIME standard has decades of edge cases, email clients behave inconsistently, and reply parsing is effectively an unsolved problem that libraries approximate through heuristics.

## Common Pitfalls

### Pitfall 1: Email Threading Breaks Silently
**What goes wrong:** Emails sent via the API appear as separate conversations instead of threaded replies in the recipient's inbox.
**Why it happens:** Missing or incorrect `In-Reply-To`/`References` headers, or mismatched `Subject` line. Gmail requires ALL THREE: threadId, RFC 2822 headers, and matching subject.
**How to avoid:** Always extract `Message-ID` from the last message in the thread and set it as both `In-Reply-To` and `References`. Prefix subject with "Re: " only if not already present.
**Warning signs:** Test emails appear as separate conversations in Gmail. Check outgoing message headers with `messages.get(format="raw")`.

### Pitfall 2: Pub/Sub Watch Expires After 7 Days
**What goes wrong:** The agent stops receiving email notifications silently after 7 days.
**Why it happens:** Gmail `watch()` has a hard 7-day expiration. The official docs recommend calling `watch()` daily.
**How to avoid:** Implement a daily renewal mechanism (cron job, scheduled task, or check-on-startup). Store the `expiration` timestamp from the watch response and renew before it expires.
**Warning signs:** Sudden silence from the notification system. No errors -- just no notifications.

### Pitfall 3: historyId Becomes Invalid
**What goes wrong:** `history.list()` returns HTTP 404, causing the agent to miss messages.
**Why it happens:** historyIds are typically valid for at least a week but can expire in hours in rare cases. If the stored historyId becomes invalid, incremental sync breaks.
**How to avoid:** On 404 from `history.list()`, fall back to a full sync: list recent messages, process any unprocessed ones, and store the new historyId. Always handle 404 as a recoverable error, not a crash.
**Warning signs:** HTTP 404 responses from `history.list()`.

### Pitfall 4: Google Sheets API Rate Limiting (429)
**What goes wrong:** `gspread` throws `APIError 429 RESOURCE_EXHAUSTED` during data reads.
**Why it happens:** Google Sheets API allows 300 requests per 60 seconds per project, 60 per user. Fetching data cell-by-cell in a loop burns through this quickly.
**How to avoid:** Use `get_all_records()` to fetch entire sheet in one call. Cache results if the agent reads the same sheet multiple times in a session. Use `batch_get()` for multiple ranges.
**Warning signs:** Intermittent 429 errors, especially during testing when running many tests against real Sheets.

### Pitfall 5: Float Precision in Sheet Data
**What goes wrong:** Pay ranges have rounding errors (e.g., $1000.00 becomes $999.9999999999998).
**Why it happens:** Google Sheets returns numeric values as Python `float`. The existing codebase rejects `float` inputs for monetary fields (see `PayRange.reject_float_inputs`).
**How to avoid:** Always convert Sheet numeric values through `str()` first: `Decimal(str(row["Min Rate"]))`. Never pass raw float from Sheets to Pydantic models.
**Warning signs:** `ValueError: Use Decimal or string, not float, for monetary values` from PayRange validation.

### Pitfall 6: MIME Parsing Misses HTML-Only Emails
**What goes wrong:** `get_message_content()` returns empty string for some emails.
**Why it happens:** Some email clients send HTML-only messages (no `text/plain` part). The parser only looks for `text/plain`.
**How to avoid:** Fall back to `text/html` part and strip HTML tags. Check both content types. Consider using `email.message.EmailMessage.get_body(preferencelist=("plain", "html"))`.
**Warning signs:** Empty reply content for messages that clearly have content when viewed in Gmail.

### Pitfall 7: OAuth2 Token Expiry in Long-Running Processes
**What goes wrong:** API calls fail with 401 Unauthorized after ~1 hour.
**Why it happens:** OAuth2 access tokens expire after 1 hour. If the credential object isn't properly configured with a refresh token, it won't auto-refresh.
**How to avoid:** Always use `Credentials` with `refresh_token` set. The `google-auth` library auto-refreshes when using `AuthorizedHttp` or `AuthorizedSession`. Persist refreshed tokens back to `token.json`.
**Warning signs:** 401 errors appearing exactly ~1 hour after startup.

## Code Examples

### Credential Management (Shared by Gmail and Sheets)

```python
# Source: https://developers.google.com/gmail/api/quickstart/python
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

def get_gmail_credentials(
    token_path: str = "token.json",
    credentials_path: str = "credentials.json",
) -> Credentials:
    """Load or create OAuth2 credentials for Gmail API."""
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Persist credentials for next run
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return creds
```

### Gmail Service Construction

```python
from googleapiclient.discovery import build

def get_gmail_service(creds: Credentials):
    """Build an authenticated Gmail API service."""
    return build("gmail", "v1", credentials=creds)
```

### Pydantic Models for Email Domain

```python
from pydantic import BaseModel, ConfigDict

class EmailThreadContext(BaseModel):
    """Context needed to maintain email thread continuity."""
    model_config = ConfigDict(frozen=True)

    thread_id: str
    last_message_id: str  # Message-ID header for In-Reply-To/References
    subject: str
    influencer_email: str

class InboundEmail(BaseModel):
    """Parsed inbound email from an influencer."""
    model_config = ConfigDict(frozen=True)

    gmail_message_id: str  # Gmail's internal message ID
    thread_id: str
    message_id_header: str  # RFC 2822 Message-ID
    from_email: str
    subject: str
    body_text: str  # Extracted latest reply text only
    received_at: str  # ISO 8601 timestamp
```

### Google Sheets InfluencerRow Model

```python
from decimal import Decimal
from pydantic import BaseModel, field_validator
from negotiation.domain.types import Platform

class InfluencerRow(BaseModel):
    """Row from the influencer outreach Google Sheet.

    Maps to: DATA-02 requirements (name, contact info, platform, metrics, pay range).
    """
    name: str
    email: str
    platform: Platform
    handle: str
    average_views: int
    min_rate: Decimal  # Pre-calculated at $20 CPM
    max_rate: Decimal  # Pre-calculated at $30 CPM

    @field_validator("min_rate", "max_rate", mode="before")
    @classmethod
    def coerce_from_sheet_float(cls, v: object) -> object:
        """Convert float values from Google Sheets to string for Decimal parsing."""
        if isinstance(v, float):
            return str(v)
        return v
```

## Pub/Sub Setup

### GCP Configuration Required (Before Code)

1. **Create a GCP project** (or use existing one from OAuth setup)
2. **Enable APIs:** Gmail API, Google Sheets API, Cloud Pub/Sub API
3. **Create Pub/Sub topic:** e.g., `projects/{project-id}/topics/gmail-notifications`
4. **Grant publish rights:** Add `gmail-api-push@system.gserviceaccount.com` as a publisher on the topic
5. **Create Pub/Sub subscription:** Pull subscription on the topic (simplest for dev)
6. **OAuth consent screen:** Configure with required scopes, add test users

**Confidence:** HIGH -- This setup is well-documented in official Google docs and hasn't changed significantly.

### Pull vs Push Subscription

| Aspect | Pull Subscription | Push Subscription |
|--------|-------------------|-------------------|
| Setup complexity | Low -- no public endpoint needed | High -- needs HTTPS endpoint with valid cert |
| Latency | Slight delay (polling interval) | Near-instant |
| Dev/testing | Easy -- works locally | Hard -- needs public URL (ngrok, etc.) |
| Production | Adequate for low volume | Better for high volume / low latency |
| Recommendation | **Use for Phase 2** | Defer to later phase |

## Google Sheets Integration

### Expected Sheet Structure

Based on the DATA-02 and NEG-01 requirements, the sheet should have columns like:

| Name | Email | Platform | Handle | Average Views | Min Rate | Max Rate |
|------|-------|----------|--------|---------------|----------|----------|
| Creator A | creator@email.com | instagram | @creatora | 50000 | 1000 | 1500 |

- **Min Rate** = average_views / 1000 * $20 CPM
- **Max Rate** = average_views / 1000 * $30 CPM
- These are pre-calculated in the sheet (requirement says "pre-calculated pay range")

### Key gspread Operations Needed

```python
# Open by spreadsheet key (from URL)
gc = gspread.service_account()
sh = gc.open_by_key("1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms")

# Get all data as list of dicts (one API call)
records = sh.sheet1.get_all_records()

# Find specific influencer
cell = sh.sheet1.find("Creator A")  # Returns Cell object with row/col
row_values = sh.sheet1.row_values(cell.row)  # Get full row
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| IMAP/SMTP for email | Gmail API REST | 2014+ (API v1) | Structured access, threading support, labels, no socket management |
| Polling for new emails | Pub/Sub push notifications | 2015+ | Eliminates polling overhead, near-instant notification |
| `email.MIMEText` for composing | `email.message.EmailMessage` | Python 3.6+ | Modern API, better header handling, content manager |
| google-api-python-client v1 | v2 (current: 2.190) | 2021 | Python 3 only, improved auth integration |
| gspread v5 | v6 (current: 6.2.1) | 2024 | Modern auth patterns, better type hints, Python 3.8+ |

**Deprecated/outdated:**
- `email.MIMEText` / `email.MIMEMultipart`: Still works but `email.message.EmailMessage` is the modern replacement (Python 3.6+)
- `oauth2client`: Deprecated in favor of `google-auth` / `google-auth-oauthlib`
- `httplib2` transport: Still used by google-api-python-client internally, but `google-auth-httplib2` bridges it

## Open Questions

1. **Which Gmail account sends on behalf of the team?**
   - What we know: The agent needs to send "on behalf of the team" (EMAIL-01). OAuth2 flow authenticates a specific Gmail user.
   - What's unclear: Is there a shared team Gmail account? Or does the agent use a personal account? This affects OAuth setup and "From" header.
   - Recommendation: Configure a dedicated team Gmail account (e.g., `partnerships@company.com`). Document the account in environment config.

2. **Google OAuth verification for restricted scopes**
   - What we know: `gmail.readonly` is a restricted scope. Google requires OAuth verification (including security assessment) for apps using restricted scopes in production.
   - What's unclear: Is this an internal-only tool (no verification needed if GCP project is set to "Internal" user type) or will it be used by external users?
   - Recommendation: Set OAuth consent screen to "Internal" if using Google Workspace. If using free Gmail, limit to "Testing" mode with explicitly added test users (max 100). This avoids the verification requirement.

3. **Pub/Sub pull vs push for production**
   - What we know: Pull subscription is simpler and works locally without a public endpoint. Push requires HTTPS webhook.
   - What's unclear: What's the production deployment model? Serverless (Cloud Functions), always-on server, or local script?
   - Recommendation: Start with pull subscription. The architecture should abstract the notification source so switching to push later is a configuration change, not a code rewrite.

4. **Google Sheet schema and ownership**
   - What we know: The sheet contains influencer data with pre-calculated pay ranges.
   - What's unclear: Who maintains the sheet? Is the schema fixed or evolving? Are there multiple worksheets (tabs)?
   - Recommendation: Define an expected schema as a Pydantic model (`InfluencerRow`). Validate sheet data on read and raise clear errors for schema mismatches. This makes schema changes detectable.

5. **Error handling strategy for external API failures**
   - What we know: Gmail and Sheets APIs can fail (rate limits, network errors, auth expiry).
   - What's unclear: Should the agent retry silently, queue for later, or escalate to a human?
   - Recommendation: Implement exponential backoff with jitter for transient errors (429, 5xx). For auth failures (401, 403), log and halt -- don't retry in a loop. Surface errors to the operator, not the influencer.

## Sources

### Primary (HIGH confidence)
- [Gmail API Sending Guide](https://developers.google.com/gmail/api/guides/sending) -- email composition, MIME requirements
- [Gmail API Threading Guide](https://developers.google.com/gmail/api/guides/threads) -- threadId, References, In-Reply-To requirements
- [Gmail API Push Notifications](https://developers.google.com/workspace/gmail/api/guides/push) -- Pub/Sub setup, watch(), notification format, 7-day expiry
- [Gmail API Scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) -- all 14 scopes with sensitivity classification
- [Gmail API Message Resource](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages) -- message structure, payload, headers
- [Gmail API Python Quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) -- OAuth setup, token storage
- [gspread Documentation](https://docs.gspread.org/en/latest/user-guide.html) -- reading data, authentication, finding rows
- [gspread Authentication](https://docs.gspread.org/en/v6.1.2/oauth2.html) -- service account setup, OAuth methods, scopes
- [Python email.message docs](https://docs.python.org/3/library/email.message.html) -- EmailMessage API
- [Python email.parser docs](https://docs.python.org/3/library/email.parser.html) -- MIME parsing

### Secondary (MEDIUM confidence)
- [mail-parser-reply PyPI](https://pypi.org/project/mail-parser-reply/) -- v1.36, Dec 2025, 13 languages, active maintenance
- [google-api-python-client PyPI](https://pypi.org/project/google-api-python-client/) -- v2.190, weekly releases
- [gspread PyPI](https://pypi.org/project/gspread/) -- v6.2.1, May 2025
- [google-api-python-client-stubs PyPI](https://pypi.org/project/google-api-python-client-stubs/) -- v1.29, type stubs for mypy
- [Gmail API Usage Limits](https://developers.google.com/workspace/gmail/api/reference/quota) -- 1B units/day, 250/user/sec
- [Google OAuth2 Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices) -- token storage, scope minimization
- [Pub/Sub Pull Subscription](https://docs.cloud.google.com/pubsub/docs/pull-messages) -- streaming pull, acknowledge, nack

### Tertiary (LOW confidence)
- [email-reply-parser (Zapier)](https://github.com/zapier/email-reply-parser) -- appears unmaintained, ~2020 last activity. Included for reference; `mail-parser-reply` is recommended instead.
- [Gmail API Pub/Sub bugs (Hiver)](https://medium.com/hiver-engineering/gmail-apis-push-notifications-bug-and-how-we-worked-around-it-at-hiver-a0a114df47b4) -- documents edge cases with duplicate/missing notifications. Needs validation against current API.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries are official Google clients or well-established community packages with recent releases
- Architecture: MEDIUM-HIGH -- Patterns follow official docs and established conventions; auth split (OAuth2 for Gmail, service account for Sheets) is standard but the specific scope combination needs runtime validation
- Pitfalls: HIGH -- Documented from official sources (7-day watch expiry, historyId invalidation) and known community issues (threading header requirements, MIME parsing edge cases)
- Pub/Sub integration: MEDIUM -- Well-documented but complex GCP setup; pull subscription simplifies Phase 2 but push may be needed for production

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (30 days -- Google APIs are stable, libraries update weekly but APIs are versioned)
