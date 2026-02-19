---
phase: 02-email-and-data-integration
plan: 02
subsystem: email
tags: [gmail-api, mime-parsing, email-threading, pubsub, mail-parser-reply]

# Dependency graph
requires:
  - phase: 02-email-and-data-integration
    plan: 01
    provides: "Gmail OAuth2 credentials, email Pydantic models (EmailThreadContext, InboundEmail, OutboundEmail)"
provides:
  - "GmailClient class wrapping all Gmail API operations (send, send_reply, setup_watch, fetch_new_messages, get_message)"
  - "Thread context extraction from Gmail API threads (get_thread_context)"
  - "RFC 2822 reply header generation (build_reply_headers)"
  - "MIME email parsing with text/plain and text/html fallback (parse_mime_message)"
  - "Reply text extraction stripping quoted content (extract_latest_reply)"
affects: [02-03, 03-llm-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [gmail-api-service-wrapper, mime-payload-type-narrowing, any-typed-gmail-service, email-reply-parser-fallback]

key-files:
  created:
    - src/negotiation/email/client.py
    - src/negotiation/email/threading.py
    - src/negotiation/email/parser.py
    - tests/email/test_client.py
    - tests/email/test_threading.py
    - tests/email/test_parser.py
  modified:
    - src/negotiation/email/__init__.py

key-decisions:
  - "Used Any type for Gmail service parameter instead of Resource to avoid mypy attr-defined errors on dynamic API methods"
  - "Used isinstance(payload, bytes) narrowing for MIME payload to satisfy mypy union-attr checks"
  - "Added type: ignore[import-untyped] for mailparser_reply (no py.typed marker)"

patterns-established:
  - "Gmail API wrapper pattern: thin class wrapping service object, methods return typed domain models"
  - "MIME parsing fallback chain: text/plain -> text/html (with tag stripping) -> empty string"
  - "Reply extraction with fallback: if parser returns empty, return original body"

requirements-completed: [EMAIL-01, EMAIL-02, EMAIL-03, EMAIL-04]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 2 Plan 2: Gmail API Integration Summary

**GmailClient wrapping send/reply/watch/fetch/parse operations with MIME parsing fallback chain and mail-parser-reply for thread content extraction**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T00:58:05Z
- **Completed:** 2026-02-19T01:02:46Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Created GmailClient class with 5 Gmail API operations: send, send_reply, setup_watch, fetch_new_messages, get_message
- Implemented email threading helpers (get_thread_context, build_reply_headers) for maintaining conversation continuity
- Built MIME parser handling plain text, multipart, and HTML-only messages with tag stripping fallback
- Integrated mail-parser-reply for extracting latest reply text from email threads
- 59 new tests (363 total), ruff clean, mypy clean, ruff format clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement email threading and MIME parser modules** - `3265af4` (feat)
2. **Task 2: Implement GmailClient class with send, receive, and watch operations** - `1dd2062` (feat)

**Plan metadata:** (pending)

## Files Created/Modified
- `src/negotiation/email/client.py` - GmailClient class: send, send_reply, setup_watch, fetch_new_messages, get_message
- `src/negotiation/email/threading.py` - get_thread_context and build_reply_headers for email thread management
- `src/negotiation/email/parser.py` - parse_mime_message and extract_latest_reply for MIME decoding and reply extraction
- `src/negotiation/email/__init__.py` - Updated to re-export all email module symbols (8 total, alphabetically sorted)
- `tests/email/test_client.py` - 26 tests for GmailClient with mocked Gmail API service
- `tests/email/test_threading.py` - 17 tests for thread context extraction and reply header building
- `tests/email/test_parser.py` - 16 tests for MIME parsing and reply extraction

## Decisions Made
- Used `Any` type for Gmail service parameter instead of `Resource` -- the google-api-python-client-stubs `Resource` type does not expose `.users()` attributes, causing mypy `attr-defined` errors on all dynamic API method chains
- Added `type: ignore[import-untyped]` for `mailparser_reply` -- library lacks `py.typed` marker, same pattern established in 02-01 for `google_auth_oauthlib`
- Used `isinstance(raw_payload, bytes)` type narrowing for MIME payload -- `get_payload(decode=True)` returns `Message | Any | bytes` union, narrowing satisfies mypy without unsafe casts

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused pytest imports in test files**
- **Found during:** Task 1 (post-implementation linting)
- **Issue:** `pytest` was imported but not used in test_threading.py and test_parser.py
- **Fix:** Removed unused imports
- **Files modified:** tests/email/test_threading.py, tests/email/test_parser.py
- **Verification:** `uv run ruff check tests/email/` -- All checks passed
- **Committed in:** 3265af4 (part of Task 1 commit)

**2. [Rule 1 - Bug] Fixed mypy type errors for MIME payload handling and Gmail service typing**
- **Found during:** Task 1 (post-implementation type checking)
- **Issue:** mypy reported 6 errors: `import-untyped` for mailparser_reply, `union-attr` on `get_payload(decode=True)` return type, `no-any-return` on EmailReplyParser result, `attr-defined` on `Resource.users()`
- **Fix:** Added `type: ignore[import-untyped]` for mailparser_reply, used `isinstance(raw_payload, bytes)` narrowing, annotated `parsed: str`, changed service parameter from `Resource` to `Any`
- **Files modified:** src/negotiation/email/parser.py, src/negotiation/email/threading.py
- **Verification:** `uv run mypy src/negotiation/email/` -- Success: no issues found in 4 source files
- **Committed in:** 3265af4 (part of Task 1 commit)

**3. [Rule 1 - Bug] Fixed ruff formatting on new files**
- **Found during:** Task 2 (post-implementation formatting check)
- **Issue:** 5 new files had formatting inconsistencies (trailing commas, line wrapping)
- **Fix:** Ran `uv run ruff format` on affected files
- **Files modified:** src/negotiation/email/client.py, src/negotiation/email/threading.py, tests/email/test_client.py, tests/email/test_parser.py, tests/email/test_threading.py
- **Verification:** `uv run ruff format --check src/negotiation/email/ tests/email/` -- All files formatted
- **Committed in:** 1dd2062 (part of Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 bugs: unused imports, mypy type errors, formatting)
**Impact on plan:** All auto-fixes were lint/type/format corrections. No scope creep.

## Issues Encountered
- Pre-existing formatting issues in src/negotiation/domain/errors.py and src/negotiation/domain/types.py (from Phase 1) -- out of scope, not fixed

## User Setup Required

None beyond what 02-01 already documented. The GmailClient requires:
- Gmail API credentials configured (see 02-01-SUMMARY.md User Setup Required)
- Pub/Sub topic created in GCP for `setup_watch` (see 02-RESEARCH.md Pub/Sub Setup section)

## Next Phase Readiness
- GmailClient ready for LLM pipeline (Phase 3) to send agent-composed emails and receive influencer replies
- Threading and parsing modules ensure the agent can maintain coherent conversations
- Plan 02-03 (Google Sheets integration) can proceed -- no dependency on this plan's outputs

## Self-Check: PASSED

All 7 created/modified files verified present. Both task commits (3265af4, 1dd2062) verified in git history.

---
*Phase: 02-email-and-data-integration*
*Completed: 2026-02-19*
