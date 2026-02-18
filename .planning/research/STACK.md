# Stack Research

**Domain:** AI-powered email negotiation agent (influencer marketing)
**Researched:** 2026-02-18
**Confidence:** MEDIUM (training data only -- unable to verify current versions via live docs due to tool restrictions)

## Confidence Disclaimer

All version numbers and library recommendations below are based on training data with a cutoff of May 2025. I was unable to access Context7, WebSearch, WebFetch, or Bash during this research session due to permission restrictions. **Verify all version numbers against current documentation before locking in.** Architectural patterns and library choices are well-established and HIGH confidence; exact versions are MEDIUM confidence.

---

## Recommended Stack

### Language: Python 3.12+

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12+ | Primary language | The AI/ML ecosystem is Python-first. LangChain, LangGraph, OpenAI SDK, Anthropic SDK -- all are Python-native with the best documentation and community support. TypeScript alternatives exist but lag behind in maturity for agent orchestration. The team's use case (email negotiation agent) is backend-only with no frontend, making Python's async capabilities sufficient. |

**Why not TypeScript/Node.js:** While Node.js handles async I/O well, the AI agent framework ecosystem (LangGraph, LangChain) has Python as the primary target. TypeScript ports exist but receive updates later, have fewer examples, and have smaller communities. For a backend agent with no UI, Python is the clear choice.

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| LangGraph | ~0.2.x | Agent orchestration framework | Purpose-built for stateful, multi-step AI agent workflows with human-in-the-loop support. Unlike raw LangChain chains, LangGraph provides explicit state machines, conditional branching, and persistence -- exactly what a negotiation agent needs for tracking conversation state across email rounds. It handles the "hybrid mode" requirement natively with interrupt/resume patterns. |
| LangChain Core | ~0.3.x | LLM abstraction layer | Provides model-agnostic LLM interface, prompt templates, and output parsing. Used underneath LangGraph, not as a standalone framework. Keeps the door open to swap between Claude, GPT-4, etc. without rewriting agent logic. |
| Anthropic Python SDK | ~0.39.x | Claude API access | Direct access to Claude models. Claude Sonnet 3.5/4 is the recommended LLM for this agent -- strong at following complex negotiation instructions, excellent at structured output, and cost-effective for high-volume email processing. |
| FastAPI | ~0.115.x | HTTP API framework | Exposes webhook endpoints for incoming emails (Gmail push notifications), ClickUp webhooks, and Slack interactivity. Async-native, auto-generates OpenAPI docs, and has excellent typing support. Lightweight enough for an agent backend. |
| Pydantic | v2.x | Data validation and schemas | Core dependency of FastAPI. Use for all data models: campaign data, influencer metrics, negotiation state, API request/response schemas. Pydantic v2 is significantly faster than v1. |

### Database

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| PostgreSQL | 16+ | Primary data store | Stores campaign data, influencer profiles, negotiation history, and agent state. JSONB support handles semi-structured data (varying deliverable types per platform). Relational model fits the structured nature of campaigns, influencers, and negotiations. Rock-solid reliability. |
| SQLAlchemy | 2.0.x | ORM / database toolkit | Python's standard ORM. Version 2.0 has modern async support via `asyncio`. Type-safe query building. Pairs with Alembic for migrations. Widely understood by Python developers. |
| Alembic | 1.13.x | Database migrations | SQLAlchemy's migration tool. Auto-generates migration scripts from model changes. Essential for evolving the schema as new deliverable types or platforms are added. |
| Redis | 7.x | Caching, rate limiting, task queue backend | Cache frequently-accessed influencer metrics, enforce rate limits on email sending, and serve as Celery's message broker. In-memory speed prevents bottlenecks during negotiation processing. |

### Email Integration

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| google-api-python-client | ~2.x | Gmail API access | Official Google API client. Handles OAuth2 flow, sending/receiving emails, managing threads, and push notification setup. The Gmail API (not IMAP/SMTP) is required for reliable thread tracking, label management, and push notifications for incoming replies. |
| google-auth-oauthlib | ~1.x | Gmail OAuth2 authentication | Handles the OAuth2 consent flow and token refresh for Gmail API access. Service account or user-delegated auth depending on setup. |
| google-auth-httplib2 | ~0.2.x | HTTP transport for Google auth | Required dependency for google-api-python-client. |

### Slack Integration

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| slack-bolt | ~1.20.x | Slack app framework | Official Slack SDK for building apps. Handles incoming events (slash commands, button clicks for escalation approvals), outgoing messages (negotiation alerts), and interactive components (approve/reject buttons on escalation messages). The Bolt framework is Slack's recommended approach over raw API calls. |
| slack-sdk | ~3.33.x | Slack Web API client | Lower-level SDK used by Bolt internally. Use directly for sending rich Block Kit messages with formatted negotiation summaries. |

### ClickUp Integration

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| httpx | ~0.27.x | HTTP client for ClickUp API | ClickUp does not have an official Python SDK. Use httpx (async-native HTTP client) to call the ClickUp API v2 directly. httpx is preferred over requests because it supports async natively, matching FastAPI's async architecture. |

### AI/LLM Layer

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Claude Sonnet (3.5 or 4) | latest | Primary LLM for negotiation | Best balance of instruction-following, cost, and speed for this use case. Claude excels at structured negotiation tasks: following CPM pricing rules, maintaining professional tone, knowing when to escalate. Sonnet tier keeps costs manageable for high-volume email processing. |
| langchain-anthropic | ~0.3.x | LangChain/LangGraph Anthropic integration | Provides the `ChatAnthropic` class that plugs Claude into LangGraph workflows. Handles streaming, tool calling, and structured output. |

### Task Queue / Background Processing

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Celery | ~5.4.x | Async task queue | Email sending, Slack notifications, and ClickUp syncing should be async background tasks. Celery with Redis broker handles retries, rate limiting, and dead letter queues. Prevents the main agent loop from blocking on I/O. |
| celery[redis] | ~5.4.x | Redis transport for Celery | Redis as message broker is simpler than RabbitMQ for this scale. One fewer service to manage. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | ~1.0.x | Environment variable management | Loading API keys, OAuth credentials, database URLs from .env files during development |
| structlog | ~24.x | Structured logging | All application logging. JSON-formatted logs with context (negotiation_id, influencer_id, campaign_id) for easy filtering and debugging |
| tenacity | ~9.x | Retry logic | Wrapping external API calls (Gmail, Slack, ClickUp, LLM) with exponential backoff and circuit breakers |
| jinja2 | ~3.1.x | Email template rendering | Generating negotiation email bodies from templates. Separates email copy from agent logic. Allows non-developers to adjust email wording |
| pytest | ~8.x | Testing framework | Unit and integration tests |
| pytest-asyncio | ~0.24.x | Async test support | Testing async FastAPI endpoints and LangGraph workflows |
| ruff | ~0.7.x | Linter and formatter | Replaces flake8 + black + isort in a single tool. Extremely fast (written in Rust). The modern Python linting standard. |
| mypy | ~1.13.x | Type checking | Static type analysis for catching bugs at development time. Critical for complex agent state objects. |
| langgraph-checkpoint-postgres | ~2.x | LangGraph state persistence | Persists LangGraph agent state to PostgreSQL. Enables the agent to resume interrupted negotiations, survive restarts, and maintain conversation history across email rounds. This is critical for the hybrid mode -- when a human takes over, the agent state must be recoverable. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Python package manager | 10-100x faster than pip. Modern replacement for pip + virtualenv + pip-tools. Use `uv init`, `uv add`, `uv sync`. Generates lockfile for reproducible builds. |
| Docker + Docker Compose | Local development environment | Run PostgreSQL, Redis, and the agent together locally. Compose file defines the full stack. |
| pre-commit | Git hook management | Run ruff, mypy on every commit. Prevents broken code from entering the repo. |

## Installation

```bash
# Initialize project with uv
uv init influencer-negotiation-agent
cd influencer-negotiation-agent

# Core dependencies
uv add langgraph langchain-core langchain-anthropic
uv add fastapi uvicorn[standard] pydantic
uv add sqlalchemy[asyncio] alembic asyncpg
uv add celery[redis] redis
uv add google-api-python-client google-auth-oauthlib google-auth-httplib2
uv add slack-bolt slack-sdk
uv add httpx
uv add python-dotenv structlog tenacity jinja2
uv add langgraph-checkpoint-postgres

# Dev dependencies
uv add --dev pytest pytest-asyncio pytest-cov
uv add --dev ruff mypy pre-commit
uv add --dev types-redis  # mypy stubs
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| Agent Framework | LangGraph | CrewAI | CrewAI is designed for multi-agent teams, not single-agent workflows. It adds unnecessary abstraction for v1. LangGraph gives finer control over state machines and human-in-the-loop, which is exactly what negotiation needs. When the multi-agent team grows, evaluate CrewAI then -- but LangGraph can handle multi-agent too. |
| Agent Framework | LangGraph | AutoGen (Microsoft) | AutoGen focuses on conversational multi-agent patterns (agents talking to each other). This project needs a single agent with structured state transitions, not agent-to-agent chat. AutoGen's programming model is a poor fit for email-based negotiation. |
| Agent Framework | LangGraph | Raw Anthropic SDK | Building agent loops from scratch with the Anthropic SDK is possible but means reimplementing state management, persistence, human-in-the-loop interrupts, and retry logic. LangGraph provides all of this out of the box. Only go raw SDK if LangGraph proves too limiting (unlikely for this use case). |
| Agent Framework | LangGraph | OpenAI Agents SDK | OpenAI's newer Agents SDK is OpenAI-model-only and locks you into their ecosystem. LangGraph is model-agnostic and works with Claude, GPT, Gemini, and open-source models. |
| LLM | Claude Sonnet | GPT-4o | Both are excellent. Claude Sonnet edges ahead for instruction-following in structured negotiation scenarios and has better pricing at high volume. GPT-4o is a valid alternative if the team prefers OpenAI. LangGraph makes swapping trivial. |
| LLM | Claude Sonnet | Open-source (Llama, Mixtral) | Not recommended for v1. Negotiation requires nuanced professional email composition and complex pricing logic. Open-source models need fine-tuning to match Claude/GPT-4 quality here. Revisit when open-source catches up. |
| Database | PostgreSQL | SQLite | SQLite is single-writer and cannot handle concurrent agent operations. Even for v1, multiple negotiations may be active simultaneously. PostgreSQL from day one avoids a painful migration later. |
| Database | PostgreSQL | MongoDB | The data model (campaigns, influencers, deliverables, negotiations) is relational. MongoDB adds complexity without benefit. JSONB in PostgreSQL handles the semi-structured parts (platform-specific metrics). |
| ORM | SQLAlchemy 2.0 | Prisma (Python) | Prisma's Python client is not yet mature. SQLAlchemy 2.0 is the established standard with excellent async support. |
| HTTP Framework | FastAPI | Flask | Flask lacks native async support and auto-generated OpenAPI docs. FastAPI is the modern standard for Python APIs. |
| HTTP Framework | FastAPI | Django | Django is a full MVC framework -- massive overkill for an agent backend. No templates, no admin panel needed. FastAPI is purpose-fit. |
| Task Queue | Celery | Dramatiq | Celery has a much larger ecosystem and more documentation. Dramatiq is simpler but has fewer integrations. For a project that needs Redis broker + retries + rate limiting, Celery's maturity wins. |
| Task Queue | Celery | arq | arq is lightweight and async-native, which is appealing. However, it lacks Celery's monitoring tools (Flower), periodic task support, and battle-tested reliability. Consider arq if Celery proves too heavy. |
| Package Manager | uv | pip + venv | uv is dramatically faster and handles virtual environments, locking, and dependency resolution in one tool. pip + venv is the old way. uv is the future. |
| Package Manager | uv | Poetry | Poetry is established but slower than uv and has occasional dependency resolution issues. uv is backed by Astral (creators of ruff) and is rapidly becoming the standard. |
| Linter | ruff | flake8 + black + isort | ruff replaces all three in a single tool, runs 10-100x faster (Rust-based), and is the clear community direction. No reason to use the old trio anymore. |
| Email | Gmail API | SMTP/IMAP | SMTP/IMAP cannot reliably track email threads, manage labels, or receive push notifications. Gmail API provides thread-level operations, which are essential for following negotiation conversations. |
| Email | Gmail API | SendGrid/Mailgun | Transactional email services are for one-way sending. This agent needs to READ incoming replies and maintain thread context. Gmail API handles both directions. |
| Slack SDK | slack-bolt | Raw Slack API calls | Bolt handles event verification, retries, and rate limiting. Raw API calls mean reimplementing all of this. |
| ClickUp | httpx (direct API) | pyclickup | pyclickup is community-maintained and may lag behind ClickUp API changes. httpx direct calls with Pydantic models for request/response validation is more maintainable and transparent. |
| Logging | structlog | Python logging | structlog produces structured JSON logs with bound context (negotiation_id, campaign_id). Standard logging produces flat strings that are hard to parse and filter in production. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| LangChain's AgentExecutor | Deprecated in favor of LangGraph. AgentExecutor was the old way to build agents in LangChain. It lacks proper state management, has poor human-in-the-loop support, and is no longer recommended by the LangChain team. | LangGraph |
| SMTP/IMAP for email | Cannot track email threads reliably. No push notifications. No label management. Requires constant polling. | Gmail API |
| requests library | Synchronous HTTP client. Blocks the event loop in async FastAPI application. | httpx (async-native) |
| Flask | No native async, no auto-generated API docs. | FastAPI |
| SQLite | Single-writer, no concurrency. Will cause issues as soon as multiple negotiations run simultaneously. | PostgreSQL |
| pip + requirements.txt | Slow dependency resolution, no lockfile by default, no virtual environment management. | uv |
| flake8 + black + isort (separately) | Three tools doing what one tool (ruff) does faster and better. | ruff |
| print() for logging | No structure, no log levels, no context, no production-readiness. | structlog |
| Storing agent state in memory | Agent state is lost on restart. Negotiations span hours/days across email rounds. State must survive process restarts. | langgraph-checkpoint-postgres |
| MongoDB | The data model is relational. MongoDB adds complexity and loses referential integrity for no benefit. | PostgreSQL with JSONB |
| Django REST Framework | Massive framework for a simple agent API. Too much ceremony, too many abstractions. | FastAPI |

## Stack Patterns by Variant

**If adding more agents later (multi-agent team):**
- Keep LangGraph. It supports multi-agent orchestration via subgraphs.
- Each agent becomes a LangGraph subgraph that can be composed into a supervisor graph.
- Do NOT switch to CrewAI later -- LangGraph's multi-agent patterns are more flexible.

**If email volume exceeds ~1000/day:**
- Add a dedicated email processing queue (Celery task per incoming email).
- Consider Gmail API batch operations for sending.
- Add email send rate limiting (Gmail has a 2000 emails/day limit for workspace accounts).

**If the team wants a dashboard later:**
- FastAPI already serves the API layer. Add a React/Next.js frontend that consumes the same API.
- The FastAPI + PostgreSQL backend is dashboard-ready without architectural changes.

**If cost is a primary concern for LLM usage:**
- Use Claude Haiku for simple classification tasks (is this a counter-offer? is this an acceptance?).
- Use Claude Sonnet only for composing negotiation emails.
- This tiered approach can reduce LLM costs by 60-80%.

**If the team prefers TypeScript:**
- LangGraph has a TypeScript version (langgraph.js). The API is similar but documentation is thinner.
- Use Node.js + Express/Fastify instead of FastAPI.
- Use Prisma instead of SQLAlchemy.
- Use Bull/BullMQ instead of Celery for task queues.
- This is a valid path but expect less community support for agent-specific patterns.

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| LangGraph ~0.2.x | langchain-core ~0.3.x | LangGraph depends on langchain-core but NOT on the full langchain package. Install langchain-core, not langchain. |
| langchain-anthropic ~0.3.x | anthropic ~0.39.x | The langchain-anthropic package wraps the anthropic SDK. Both must be compatible. |
| FastAPI ~0.115.x | Pydantic v2.x | FastAPI requires Pydantic v2. Do NOT install Pydantic v1 -- many old tutorials reference v1 syntax. |
| SQLAlchemy 2.0.x | asyncpg ~0.30.x | asyncpg is the async PostgreSQL driver for SQLAlchemy 2.0. Do NOT use psycopg2 for async. |
| Celery ~5.4.x | Redis 7.x, redis-py ~5.x | Celery's Redis broker requires redis-py (the Python client). |
| langgraph-checkpoint-postgres ~2.x | LangGraph ~0.2.x, asyncpg | Checkpoint persistence must match LangGraph version. |

## Environment Variables Required

```bash
# LLM
ANTHROPIC_API_KEY=sk-ant-...

# Gmail
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REFRESH_TOKEN=...
GMAIL_USER_EMAIL=negotiation@company.com

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_CHANNEL_ID=C...  # Channel for negotiation alerts

# ClickUp
CLICKUP_API_TOKEN=pk_...
CLICKUP_WORKSPACE_ID=...

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/negotiation_agent

# Redis
REDIS_URL=redis://localhost:6379/0

# Application
APP_ENV=development
LOG_LEVEL=INFO
CPM_MIN=20.0
CPM_MAX=30.0
ESCALATION_CPM_THRESHOLD=30.0
```

## Sources

- **LangGraph architecture and human-in-the-loop patterns:** Training data knowledge (LangChain/LangGraph documentation and blog posts through May 2025). Confidence: MEDIUM -- verify current API against https://langchain-ai.github.io/langgraph/
- **Gmail API capabilities:** Training data knowledge (Google API documentation). Confidence: HIGH -- Gmail API is stable and well-established.
- **Slack Bolt framework:** Training data knowledge (Slack developer documentation). Confidence: HIGH -- Bolt is Slack's established framework.
- **FastAPI + SQLAlchemy + PostgreSQL patterns:** Training data knowledge. Confidence: HIGH -- these are mature, stable technologies.
- **ClickUp API v2:** Training data knowledge. Confidence: MEDIUM -- verify current API version and capabilities at https://clickup.com/api
- **uv package manager:** Training data knowledge. Confidence: MEDIUM -- verify current version and commands at https://docs.astral.sh/uv/
- **Version numbers throughout:** Training data only. Confidence: LOW-MEDIUM -- these should all be verified against current releases before locking in.

---
*Stack research for: AI-powered influencer negotiation agent*
*Researched: 2026-02-18*
*Note: All findings based on training data (cutoff May 2025). Live documentation verification was not possible during this session. Verify versions before implementation.*
