# Pitfalls Research

**Domain:** Production readiness for existing FastAPI influencer negotiation agent
**Researched:** 2026-02-19
**Confidence:** HIGH (codebase read directly; pitfalls grounded in specific code patterns observed in `src/negotiation/`)

> **Scope note:** This document supersedes the prior PITFALLS.md (2026-02-18), which covered the agent's negotiation domain pitfalls. This revision focuses exclusively on the production readiness milestone: Dockerizing, migrating state, CI/CD, monitoring, and external API resilience for the *existing* 6,799 LOC FastAPI app.

---

## Critical Pitfalls

### Pitfall 1: OAuth2 `token.json` Baked Into Docker Image or Lost on Container Restart

**What goes wrong:**
The Gmail OAuth2 flow writes `token.json` (and potentially `credentials.json`) to the filesystem. In Docker, if these files are not on a named volume, every container restart requires re-running the interactive OAuth flow (`flow.run_local_server(port=0)`) — which opens a browser, cannot run headlessly, and will hard-crash the container on startup. Alternatively, if `token.json` is `COPY`d into the image at build time, it is baked into the layer history and visible to anyone with image pull access, exposing the refresh token.

**Why it happens:**
`get_gmail_credentials()` in `src/negotiation/auth/credentials.py` reads `token.json` from a path defaulting to the current working directory. Local development works fine because the file is already present. Docker containers start from a clean filesystem, so the file is absent unless explicitly mounted or injected.

**How to avoid:**
- Mount `token.json` from a Docker named volume or bind mount on the host, set via the `GMAIL_TOKEN_PATH` env var the app already reads.
- For CI and production: serialize the token JSON into a single environment variable (`GMAIL_TOKEN_JSON`) and write it to a temp file on container startup via an entrypoint script — never bake it into the image.
- Alternatively, use a Docker secret (for Swarm) or a secret manager (GCP Secret Manager, Vault) that writes the file to `/run/secrets/gmail_token` at container start.
- Add a startup health check that verifies `GMAIL_TOKEN_PATH` exists and the credentials are valid before the app signals readiness.

**Warning signs:**
- App starts but `GmailClient` is silently disabled on every restart (log line: `"GMAIL_TOKEN_PATH not set, GmailClient disabled"` despite the path being set — means the file doesn't exist at that path).
- `InstalledAppFlow.run_local_server()` raises `OSError` or hangs at container startup.
- Docker image size is larger than expected (token baked in).

**Phase to address:**
Containerization phase — before any cloud deployment. Must be the first thing solved when writing the Dockerfile, not an afterthought.

---

### Pitfall 2: Google Sheets Service Account JSON Injected as a File Mount with Wrong Permissions

**What goes wrong:**
`get_sheets_client()` calls `gspread.service_account(filename=...)` which reads a JSON file from disk. In Docker, if this file is bind-mounted from the host with root ownership but the container runs as a non-root user (correct production practice), the file is unreadable. `gspread` raises a `FileNotFoundError` or `PermissionError` that the app catches silently (the `try/except` in `initialize_services()` logs a warning and continues), leaving `SheetsClient` as `None` — meaning campaign ingestion silently fails to find any influencers.

**Why it happens:**
Linux file permission mismatches between host UID and container UID are invisible during development (both run as root or same user). They appear only in hardened production containers running as UID 1000+.

**How to avoid:**
- Use Docker `--user` matching the host file owner, OR
- Pass the entire service account JSON content as an environment variable (`SHEETS_SERVICE_ACCOUNT_JSON`) and write it to a temp file at startup.
- Add a startup validation: if `SHEETS_SERVICE_ACCOUNT_PATH` is set but `SheetsClient` initializes as `None`, treat it as a startup failure (raise an exception), not a graceful degradation. Silent `None` for Sheets means zero campaign processing.
- Test the non-root container locally: `docker run --user 1000:1000 ...`.

**Warning signs:**
- Log shows `"Failed to initialize SheetsClient"` in production but SheetsClient worked fine in development.
- Campaign webhooks arrive but no influencers are found (ingestion runs but Sheets lookup returns empty).
- `docker inspect` shows the secret file exists in the container but `ls -la` shows it's owned by root.

**Phase to address:**
Containerization phase, simultaneously with Pitfall 1.

---

### Pitfall 3: `negotiation_states` In-Memory Dict Lost on Any Container Restart

**What goes wrong:**
`negotiation_states: dict[str, dict[str, Any]] = {}` in `initialize_services()` holds all live negotiation state (state machine, context, round count). A container restart — from a deploy, OOM kill, crash, or host reboot — wipes this dict. All in-flight negotiations are orphaned: the agent sent emails that are in the influencer's inbox, replies will arrive via Gmail Pub/Sub, but the thread_id-to-state lookup returns `None` and the agent logs `"No active negotiation for thread, ignoring"`. From the influencer's perspective, the agent ghosted them mid-negotiation.

**Why it happens:**
The in-memory dict is appropriate for local development but is never persisted. There is no "load state from DB on startup" path. This is a known architectural gap the production readiness milestone is supposed to close — but the pitfall is doing the migration incorrectly.

**How to avoid:**
- Persist `negotiation_states` to SQLite at every state transition (not just on shutdown). The existing SQLite audit DB is already on a named volume — add a `negotiations` table to the same DB.
- On startup, load all negotiations with non-terminal states into memory, restoring the `negotiation_states` dict.
- The `NegotiationStateMachine` object is not directly serializable. Persist its current state string, not the object. Reconstruct the machine from that state string on load.
- Never rely on `finally` blocks or shutdown hooks to persist state — containers can be killed with `SIGKILL` which skips all cleanup.

**Warning signs:**
- After any restart, `negotiation_states` dict has zero entries but the audit log shows negotiations that were in `COUNTER_SENT` state.
- Influencers reply but receive no response after a deployment.
- Round count resets to 0 for active negotiations after restart.

**Phase to address:**
State persistence phase — must happen before any production deployment. The migration must be tested by simulating a mid-negotiation restart in a dev environment.

---

### Pitfall 4: SQLite WAL Mode Data Loss on Named Volume with Networked or VM Filesystem

**What goes wrong:**
`init_audit_db()` enables WAL mode (`PRAGMA journal_mode=WAL`). WAL mode creates three files: `audit.db`, `audit.db-wal`, and `audit.db-shm`. If the Docker named volume maps to a network filesystem (NFS, GlusterFS, EBS via NFS) or a VM shared folder, WAL mode may corrupt the database or cause data loss. The `-wal` file holds uncommitted transactions — if the container dies without checkpointing, the WAL file contains recent audit entries that the main `.db` file does not. If only `audit.db` is backed up (a common mistake), those entries are lost.

**Why it happens:**
WAL mode uses OS-level file locking that is not reliable across network boundaries. Docker named volumes backed by cloud block storage (EBS, GCE Persistent Disk) are usually safe, but any NFS-backed volume or `--mount type=bind` to a VM shared folder is risky. Developers test with local volumes and don't discover the issue until the first cloud deployment.

**How to avoid:**
- Use a Docker named volume backed by local block storage (not NFS). Verify this explicitly for the target VM.
- Back up all three files: `audit.db`, `audit.db-wal`, and `audit.db-shm` — or run a `PRAGMA wal_checkpoint(FULL)` before backup to consolidate WAL into the main file.
- Validate WAL compatibility at startup: after `PRAGMA journal_mode=WAL`, check the result equals `"wal"`. If the filesystem returns `"delete"` instead, WAL is unsupported — log a fatal error and refuse to start.
- For the migrations moving `negotiation_states` into SQLite, test the full restart cycle on the actual target VM filesystem, not just local Docker Desktop.

**Warning signs:**
- `sqlite3.OperationalError: database is locked` in logs during normal operation (concurrent write contention, which WAL should prevent but networked FS breaks).
- `audit.db-wal` file grows unboundedly and never shrinks (WAL checkpoint not completing).
- Audit entries disappear after container restarts.

**Phase to address:**
Containerization phase (volume configuration) and state persistence phase (backup strategy). Validate on the actual deployment VM before going live.

---

### Pitfall 5: Gmail Pub/Sub Watch Expires After 7 Days Without Renewal

**What goes wrong:**
`GmailClient.setup_watch()` registers a Pub/Sub watch on the INBOX. Gmail watches expire after exactly 7 days. `renew_gmail_watch_periodically()` runs as an asyncio task alongside the main server and renews every 6 days — but this task runs only in the same process. If the container restarts on day 5, the `asyncio.sleep(6 * 24 * 3600)` countdown resets to 0, the watch is renewed at restart, and the next renewal is scheduled for day 11 from restart — but the watch expires on day 12 from the *previous* renewal. This creates a 1-day window where the watch is valid but renewal isn't scheduled. Over multiple restarts, the gap closes and eventually the watch expires between renewals, and all inbound email notifications are silently dropped.

**Why it happens:**
The renewal interval is relative to the last process startup, not to when the watch was last established. Multiple restarts skew the relationship between the renewal schedule and the actual watch expiry time stored at Google.

**How to avoid:**
- Persist the watch `expiration` timestamp (returned by Gmail API in the watch response) to the SQLite DB.
- On startup, read the persisted expiration. If it expires within 24 hours, renew immediately instead of waiting 6 days.
- Set the `renew_gmail_watch_periodically` interval based on the actual expiration timestamp, not a fixed 6-day timer.
- Add a monitoring alert: if `historyId` hasn't been updated in > 1 hour during business hours, the watch may have expired.

**Warning signs:**
- Pub/Sub push notifications stop arriving (silence from Pub/Sub for > 30 minutes during active negotiation periods).
- Gmail API `users.watch()` returns a new `historyId` on startup but the next notification never fires.
- Influencer replies sit unanswered for exactly 7 days after a deployment.

**Phase to address:**
Containerization and monitoring phases. The watch expiration timestamp must be stored before the first container restart occurs.

---

### Pitfall 6: GitHub Actions CI Tests Hit Real SQLite Files or Leak State Between Runs

**What goes wrong:**
The 691 tests use `init_audit_db()` which writes to `data/audit.db` by default (relative path from `AUDIT_DB_PATH` env var). In CI, if the `data/` directory persists between test runs (GitHub Actions runners reuse workspace), tests that expect an empty database will find stale entries from previous runs, causing false failures. Worse, if tests run in parallel (using `pytest-xdist`), multiple workers write to the same SQLite file simultaneously — WAL mode helps but concurrent writes to the same file from multiple processes still cause `database is locked` errors that flake tests nondeterministically.

**Why it happens:**
`initialize_services()` uses `Path(os.environ.get("AUDIT_DB_PATH", "data/audit.db"))` — a fixed path. Tests that call `initialize_services()` all write to the same file unless the test explicitly overrides the env var. The current test suite uses mocks heavily, but any future integration test that exercises the full `initialize_services()` path will hit this immediately.

**How to avoid:**
- In CI, set `AUDIT_DB_PATH` to a `tmp_path`-scoped directory: each test gets a fresh temp directory via pytest's `tmp_path` fixture.
- Add a `conftest.py` fixture that sets `AUDIT_DB_PATH` to a unique temp path for any test that exercises the audit store.
- For full integration tests, use `pytest-xdist` with `--dist worksteal` and ensure each worker gets its own temp DB path via the worker ID.
- Add a CI step that validates the test suite runs clean on a fresh GitHub Actions runner (no state leakage from previous runs): add `rm -rf data/` to the CI workflow before running tests.

**Warning signs:**
- Tests pass locally but fail in CI with `sqlite3.OperationalError: database is locked`.
- Test results differ between the first and second CI run on the same branch (state leakage).
- `test_store.py` tests fail when run after `test_app.py` tests in the same session.

**Phase to address:**
CI/CD setup phase, before enabling branch protection rules.

---

### Pitfall 7: Anthropic API 529 `overloaded_error` Not Retried Separately from Rate Limits

**What goes wrong:**
The existing `resilient_api_call` decorator retries 3 times on any exception with exponential backoff. However, Anthropic returns two distinct error types that require different retry strategies:
- **429 `rate_limit_error`**: Has a `retry-after` header. The correct wait is `retry-after` seconds, not exponential backoff from the tenacity config. Ignoring the header and using fixed backoff means retrying too early (wasting quota) or too late.
- **529 `overloaded_error`**: Server-side capacity issue. Should retry, but 3 attempts may not be enough during extended outages. The backoff ceiling of 30 seconds means after 3 attempts (roughly 1 + 4 + 30 = ~35 seconds total), the decorator re-raises. If Anthropic is overloaded for 5 minutes, the negotiation email never gets sent.

**Why it happens:**
The current retry decorator uses `reraise=True` and catches all exceptions uniformly. The Anthropic Python SDK raises `anthropic.RateLimitError` (429) and `anthropic.APIStatusError` (529) as distinct exception types, but the decorator doesn't distinguish between them. Tenacity's `retry_error_callback` fires only on the final failure, not per-attempt, so there's no per-attempt logic to inspect the response headers.

**How to avoid:**
- Separate retry handling for 429 vs 529: for 429, inspect `e.response.headers.get("retry-after")` and sleep that exact duration before retrying. For 529, use longer backoff with more attempts (5-7) since these are transient infrastructure issues.
- Add `retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError))` to the tenacity decorator so only retryable errors are retried, and non-retryable errors (400 `invalid_request_error`, 401 `authentication_error`) fail fast.
- Queue negotiation processing: rather than retrying synchronously in the webhook path, put failed LLM calls on a deferred queue so the webhook returns quickly and the retry happens asynchronously.

**Warning signs:**
- Slack `#errors` channel floods with "API call failed after all retries" during Anthropic outages (correct behavior — the alerting works — but the issue is all in-flight negotiations fail simultaneously).
- 400-class errors (bad API key, malformed request) are retried 3 times and delay failure detection by 35 seconds.
- During rate limiting, the app retries immediately and burns through quota faster than the rate limit window resets.

**Phase to address:**
Error handling and retry logic phase.

---

### Pitfall 8: Slack Bolt Socket Mode Deadlock in `asyncio.to_thread`

**What goes wrong:**
`run_slack_bot()` wraps the synchronous `start_slack_app()` (which calls `SocketModeHandler.handler.start()`) in `asyncio.to_thread()`. The Slack Bolt synchronous Socket Mode handler uses `threading.Lock` internally. When a Slack slash command arrives, the handler dispatches it on a thread it manages. If that command's handler calls back into async code (e.g., via `asyncio.ensure_future`), it can deadlock: the threading lock is held by the Bolt handler thread, and the async code tries to acquire the same event loop that's blocked waiting on the thread.

Additionally, `SocketModeHandler.start()` is a blocking infinite loop. If it throws a `WebSocketConnectionClosedException` (documented in Slack Bolt Issues #445 for Kubernetes/Docker environments), `asyncio.to_thread()` re-raises the exception, the `run_slack_bot()` coroutine exits, and `asyncio.gather()` in `main()` cancels the entire process. The app dies because of a transient WebSocket disconnect.

**Why it happens:**
Mixing synchronous Bolt SDK with async FastAPI event loop is the documented rough edge of Slack Bolt Python. The `asyncio.to_thread()` approach is correct, but the interaction with Bolt's internal threading makes it fragile in containers (where WebSocket connections are less stable due to NAT timeouts and container networking).

**How to avoid:**
- Switch to `slack_bolt.async_app.AsyncApp` with an async Socket Mode handler (`AsyncSocketModeHandler` from `slack_bolt.adapter.socket_mode.aiohttp`). This eliminates the sync/async boundary entirely.
- Add reconnection logic: wrap `start_slack_app` in a retry loop so a WebSocket disconnect triggers a reconnect instead of process death. Alternatively, use `handler.connect()` (non-blocking) instead of `handler.start()` (blocking).
- Add a health check that verifies the Slack WebSocket connection is alive and restarts the Bolt handler if not, without killing the FastAPI server.

**Warning signs:**
- Slash commands (`/audit`, `/claim`, `/resume`) stop responding without any error logs.
- Container exits with `WebSocketConnectionClosedException` after several hours of uptime.
- `asyncio.to_thread` thread pool grows without bound (threads stuck waiting on Bolt locks).

**Phase to address:**
Containerization and monitoring phases. The async migration should happen as part of the Dockerization work before production deployment.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `token.json` on bind-mounted host directory | No secrets manager needed | Token exposed on host filesystem; breaks on cloud VMs that don't have the file; manual rotation | Dev/staging only; never in production |
| Using `data/audit.db` default path (no `AUDIT_DB_PATH` override) | Zero config in dev | CI tests write to shared path; Docker container has no persistent volume for this path | Dev only; CI and production must always set `AUDIT_DB_PATH` |
| Synchronous `SocketModeHandler` in `asyncio.to_thread` | Avoids async Bolt migration | Deadlock risk; process-death-on-disconnect; harder to test | Only during initial migration sprint; replace with async Bolt before production |
| Single container with both FastAPI + Slack Bolt | Simpler deployment | One crash kills both; can't scale them independently; Bolt reconnects interrupt FastAPI liveness | Acceptable for v1 single-VM deployment; revisit if load requires scaling |
| `negotiation_states` restored from DB into memory on startup | Simpler than real-time persistence | Window of data loss between state transitions if container killed mid-operation | Acceptable for v1; full durability requires writing to DB at every transition |
| No `AUDIT_DB_PATH` in Docker healthcheck | Simpler healthcheck | Healthcheck passes even if DB is unwritable; first failed write surfaces only in logs | Never -- healthcheck must validate DB writability |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Gmail OAuth2 | OAuth consent screen left in "Testing" mode | Publishing status must be "In production" in Google API Console. Testing mode silently invalidates refresh tokens after 7 days, causing the app to fail mid-week. |
| Gmail OAuth2 | 100 live refresh token limit per OAuth client | Each OAuth flow creates a new refresh token. If developers run the auth flow repeatedly (e.g., in CI or on new machines), old tokens are silently invalidated by Google when the 100-token limit is exceeded. |
| Gmail Pub/Sub | Pub/Sub push endpoint not publicly reachable | The `GMAIL_PUBSUB_TOPIC` Pub/Sub subscription must push to a URL reachable from Google's servers. Local dev and VMs behind NAT require a reverse proxy (ngrok, Cloudflare Tunnel) or public IP. |
| Google Sheets | `SpreadsheetNotFound` despite correct key | The service account email address must be explicitly added as a Viewer (or Editor) on the spreadsheet. The service account has no implicit access even with valid credentials. |
| Anthropic SDK | Catching all exceptions uniformly | Use `anthropic.RateLimitError`, `anthropic.APIStatusError`, `anthropic.APIConnectionError` for specific handling. Generic `except Exception` swallows permanent errors (bad API key, malformed request) and retries them unnecessarily. |
| Slack Bolt | `SLACK_BOT_TOKEN` format validation | Slack bot tokens start with `xoxb-`. App tokens for Socket Mode start with `xapp-`. Mixing them raises a cryptic auth error. Validate token prefixes at startup. |
| Slack Bolt | Rate limit on slash command responses | Slash commands must respond within 3 seconds or Slack shows "This app did not respond." For `/audit` (which queries SQLite), this is usually fine, but if SQLite is on a slow volume, add a deferred response. |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| SQLite single-writer lock with concurrent background tasks | `database is locked` errors when multiple `asyncio.ensure_future` tasks write to audit DB simultaneously | Enable WAL mode (already done). Ensure all DB writes go through a single async queue or use `check_same_thread=False` with explicit locking | At 5+ simultaneous inbound email processing tasks |
| Unbounded `background_tasks` set in `services` | Memory grows if background tasks are created faster than they complete (e.g., flood of Pub/Sub notifications) | Add a max concurrency semaphore (`asyncio.Semaphore(10)`) gating email processing tasks | At 20+ simultaneous inbound Pub/Sub messages |
| `asyncio.to_thread` for every Gmail API call | Thread pool exhausted under concurrent email processing; `asyncio.to_thread` defaults to `ThreadPoolExecutor` with `min(32, os.cpu_count() + 4)` threads | Use a dedicated executor with controlled max_workers: `loop.run_in_executor(bounded_executor, ...)` | At 32+ concurrent Gmail API calls (unlikely but possible during catch-up after Pub/Sub backlog) |
| Audit DB `conn.commit()` on every insert | Excessive fsync under high write load; each `insert_audit_entry` call commits immediately | Batch commits: commit every N entries or every N seconds using a write buffer | At 100+ audit entries per minute (concurrent negotiations) |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging `email_body` to structured logs in production | Full email contents (including influencer PII, rates, and negotiation strategy) appear in log aggregators accessible to anyone with log read access | In production, log metadata only: `message_id`, `thread_id`, `from_email` (domain only, not full address), `body_length`. Store full body only in the audit DB which is access-controlled. |
| `ANTHROPIC_API_KEY` in Docker `ENV` instruction | API key visible in `docker inspect` and image layer history | Use Docker secrets, runtime env injection (not build-time `ENV`), or a secret manager. Never use `ENV ANTHROPIC_API_KEY=...` in Dockerfile. |
| ClickUp webhook endpoint (`/webhooks/clickup`) with no signature verification | Any party can POST fake campaign tasks, triggering outreach to arbitrary influencers | ClickUp webhook payloads include an HMAC signature header. Verify `X-Signature` against `HMAC-SHA256(secret, body)` before processing. |
| Gmail Pub/Sub push endpoint (`/webhooks/gmail`) with no token validation | Any party can POST fake Pub/Sub messages, causing the agent to process arbitrary message IDs | Validate the Google-signed JWT in the `Authorization: Bearer` header on all Pub/Sub push requests. |
| Service account JSON key stored in source control | Permanent credential exposure; key cannot be rotated without regenerating | Add `*.json` (or specifically `service_account.json`, `credentials.json`) to `.gitignore`. Rotate immediately if committed. |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Dockerized app starts:** Often missing -- OAuth credentials. The container starts, FastAPI is healthy, but `GmailClient` and `SheetsClient` are both `None` because the credential files aren't mounted. Verify by checking that both clients initialized in the startup logs, not just that the port is open.
- [ ] **CI pipeline passes:** Often missing -- secrets not configured. The 691 tests may all pass with mocked external clients, but CI fails on first real deployment because `ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`, etc. are not in GitHub Secrets. Verify secrets are populated and the Docker image can be built and run in CI.
- [ ] **Health check passes:** Often missing -- only checks HTTP port, not service dependencies. A `/health` endpoint that returns 200 when `GmailClient is None` is not a real health check. Verify the health check validates all required services initialized successfully.
- [ ] **State migration is complete:** Often missing -- existing negotiations from before the migration. If the app was running in dev/staging with in-memory state during testing, there are no negotiations to migrate. But the migration code path (load from DB on startup) must be tested by: (1) start app, (2) create a negotiation, (3) stop the container, (4) restart, (5) verify the negotiation state was restored.
- [ ] **Pub/Sub push endpoint is reachable:** Often missing -- the Gmail watch is registered, the app logs success, but Pub/Sub cannot reach the endpoint because the VM is behind NAT or the firewall blocks port 8000. Verify by checking Pub/Sub delivery metrics in Google Cloud Console and confirming at least one push delivery succeeded.
- [ ] **Gmail watch renewal survives restarts:** Often missing -- the renewal countdown resets on restart (see Pitfall 5). Verify by checking the `expiration` field from `setup_watch()` is persisted to the DB, and that after a restart the renewal is scheduled based on the stored expiration, not a fresh 6-day timer.
- [ ] **Retry logic handles 529 separately from 429:** Often missing -- a single test for retry behavior covers only one error code. Verify by testing `resilient_api_call` against a mock that raises `anthropic.APIStatusError(529)` and confirming the `retry-after` header is respected for 429.
- [ ] **Slack slash commands work after Bolt reconnect:** Often missing -- commands work at startup but fail after a WebSocket disconnect/reconnect cycle. Verify by simulating a network interruption and confirming `/audit` still responds.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| `token.json` lost / OAuth flow required on headless container | MEDIUM | 1. Run OAuth flow locally. 2. Copy generated `token.json` to the volume mount path on the VM. 3. Restart container. 4. Prevent recurrence: persist to secrets manager. |
| `negotiation_states` wiped (container restart mid-negotiation) | HIGH | 1. Query audit DB for all negotiations with sent emails but no reply yet. 2. Reconstruct state manually and insert into the new `negotiations` table. 3. Send a brief human-written "checking in" email to affected influencers to restart the thread. 4. Deploy the state persistence fix before restarting the agent. |
| Gmail watch expired (Pub/Sub silent) | LOW | 1. Restart the container (the lifespan startup handler calls `setup_watch` on every start). 2. Verify Pub/Sub push delivery in Google Cloud Console. 3. Implement Pitfall 5 fix to prevent recurrence. |
| SQLite data corruption (WAL on networked FS) | HIGH | 1. Stop all writes immediately (bring down the container). 2. Run `sqlite3 audit.db ".recover"` to attempt recovery. 3. Restore from last backup of all three files (`audit.db`, `audit.db-wal`, `audit.db-shm`). 4. Move to local block storage volume before restarting. |
| Anthropic API down during active negotiations | MEDIUM | 1. The retry decorator already posts to Slack `#errors`. 2. Queue all incoming emails in a processing backlog (Pub/Sub messages are retained for 7 days by default). 3. When Anthropic recovers, replay the backlog. 4. Consider a graceful degradation mode: auto-escalate all negotiations to human when LLM is unavailable > 15 minutes. |
| Slack Bolt Socket Mode process-death loop | MEDIUM | 1. Restart the container. 2. If disconnect happens within minutes, the VM network has WebSocket stability issues. 3. Add a keep-alive or use Slack HTTP mode (requires a public HTTPS endpoint) instead of Socket Mode. |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| OAuth2 `token.json` in Docker | Containerization | Start a fresh container with no pre-existing credential files. Verify startup logs show `GmailClient initialized` using only the mounted path or injected secret. |
| Sheets service account file permissions | Containerization | Run container as non-root user (`--user 1000`). Verify `SheetsClient initialized` in logs. |
| `negotiation_states` lost on restart | State persistence migration | Start app, create negotiation, kill container (`docker kill`), restart, verify negotiation state is present in `negotiation_states`. |
| SQLite WAL on networked FS | Containerization + volume configuration | Run `PRAGMA journal_mode` after container start; assert result is `"wal"`. Write 1000 rows, kill container, restart, verify all 1000 rows present. |
| Gmail watch expiry after restart | Monitoring + watch persistence | Persist `expiration` to DB. Simulate restart. Verify renewal is scheduled at `expiration - 24h`, not `now + 6d`. |
| CI test state leakage | CI/CD setup | Run test suite twice in sequence in a clean GitHub Actions environment. Assert test count and pass rate are identical on both runs. |
| Anthropic 529 vs 429 retry distinction | Error handling + retry logic | Unit test: mock `anthropic.RateLimitError` with `retry-after: 60` header. Assert retry waits 60 seconds. Mock `anthropic.APIStatusError(529)`. Assert 5+ retry attempts before final failure. |
| Slack Bolt deadlock / process death | Containerization | Load test: send 10 concurrent slash commands while processing 5 inbound emails. Assert no deadlock and no container exit within 60 seconds. |
| ClickUp webhook signature missing | Security phase | POST to `/webhooks/clickup` with invalid signature. Assert 403 response. |
| Gmail Pub/Sub JWT not validated | Security phase | POST to `/webhooks/gmail` with missing `Authorization` header. Assert 401 response. |

---

## Sources

- Google OAuth2 refresh token invalidation conditions: [Google OAuth 2.0 documentation](https://developers.google.com/identity/protocols/oauth2), [OAuth consent screen testing vs. production](https://nango.dev/blog/google-oauth-invalid-grant-token-has-been-expired-or-revoked) — HIGH confidence (official docs).
- SQLite WAL mode in Docker with networked filesystems: [SQLite forum: WAL mode and VM volumes](https://sqlite.org/forum/forumpost/292a68c5e4), [Data loss in containers with SQLite WAL](https://bkiran.com/blog/sqlite-containers-data-loss) — HIGH confidence (documented SQLite limitation).
- Slack Bolt Socket Mode WebSocket disconnect in containers: [bolt-python Issue #445](https://github.com/slackapi/bolt-python/issues/445), [threading.Lock deadlock in asyncio](https://github.com/slackapi/bolt-python/issues/994) — HIGH confidence (official issue tracker).
- Anthropic 529 overloaded error and retry strategies: [Anthropic errors documentation](https://docs.anthropic.com/en/api/errors), [529 overloaded fix guide 2025](https://www.cursor-ide.com/blog/claude-code-api-error-529-overloaded) — MEDIUM confidence (official docs confirm error codes; retry strategy is engineering inference).
- Docker secrets management (non-Swarm): [Docker secrets docs](https://docs.docker.com/engine/swarm/secrets/), [GitGuardian Docker secrets guide](https://blog.gitguardian.com/how-to-handle-secrets-in-docker/) — HIGH confidence.
- FastAPI asyncio.to_thread blocking patterns: [FastAPI concurrency docs](https://fastapi.tiangolo.com/async/), [Async pitfalls in FastAPI](https://shiladityamajumder.medium.com/async-apis-with-fastapi-patterns-pitfalls-best-practices-2d72b2b66f25) — HIGH confidence.
- pytest CI test isolation with SQLite: [Parallel pytest and SQLite concurrent writes](https://github.com/joedougherty/sqlite3_concurrent_writes_test_suite) — MEDIUM confidence (general pattern, not this specific codebase).
- gspread service account authentication: [gspread auth docs](https://docs.gspread.org/en/master/oauth2.html) — HIGH confidence (official docs).
- Code-specific pitfalls (Pitfalls 1-3, 5, 6, 8): directly observed in `src/negotiation/app.py`, `src/negotiation/auth/credentials.py`, `src/negotiation/resilience/retry.py`, `src/negotiation/slack/app.py` — HIGH confidence.

---
*Pitfalls research for: Production readiness — FastAPI influencer negotiation agent*
*Researched: 2026-02-19*
*Scope: Production readiness milestone only (Dockerization, state migration, CI/CD, monitoring, retry logic, integration testing)*
