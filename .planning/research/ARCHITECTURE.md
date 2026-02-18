# Architecture Research

**Domain:** AI-powered email negotiation agent (influencer marketing)
**Researched:** 2026-02-18
**Confidence:** MEDIUM (training data only -- WebSearch/WebFetch unavailable for verification)

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SERVICES                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │
│  │ Gmail    │  │ Slack    │  │ ClickUp  │  │ LLM API  │                     │
│  │ API      │  │ API      │  │ Webhooks │  │ (Claude) │                     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                     │
│       │              │             │              │                          │
├───────┴──────────────┴─────────────┴──────────────┴──────────────────────────┤
│                        INTEGRATION LAYER                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │
│  │ Email    │  │ Slack    │  │ Campaign │  │ LLM      │                     │
│  │ Gateway  │  │ Gateway  │  │ Ingester │  │ Client   │                     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘                     │
│       │              │             │              │                          │
├───────┴──────────────┴─────────────┴──────────────┴──────────────────────────┤
│                        AGENT CORE                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐     │
│  │                    Negotiation Agent                                 │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │     │
│  │  │ Thread   │  │ Pricing  │  │ Response │  │ Escala-  │            │     │
│  │  │ Manager  │  │ Engine   │  │ Composer │  │ tion     │            │     │
│  │  │          │  │          │  │          │  │ Router   │            │     │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │     │
│  └──────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐     │
│  │                    Agent Orchestrator                                │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                          │     │
│  │  │ Event    │  │ State    │  │ Agent    │                          │     │
│  │  │ Router   │  │ Machine  │  │ Registry │                          │     │
│  │  └──────────┘  └──────────┘  └──────────┘                          │     │
│  └──────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                        DATA LAYER                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │
│  │ Negotia- │  │ Campaign │  │ Thread   │  │ Audit    │                     │
│  │ tion     │  │ Store    │  │ History  │  │ Log      │                     │
│  │ State    │  │          │  │          │  │          │                     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Email Gateway** | Send/receive emails, manage threading, poll for new replies, handle OAuth tokens | Gmail API client with pub/sub or polling, thread ID tracking |
| **Slack Gateway** | Send escalation messages, receive human responses, format rich notifications | Slack Web API + Bolt framework for interactive messages |
| **Campaign Ingester** | Accept campaign data from ClickUp, normalize into internal format, validate completeness | ClickUp webhook receiver or API poller |
| **LLM Client** | Manage prompts, call LLM API, handle retries, enforce token limits, parse structured output | Anthropic SDK with structured output, retry wrapper |
| **Thread Manager** | Track conversation state per influencer, maintain full email thread context, detect conversation stage | State machine per thread with stage tracking |
| **Pricing Engine** | Calculate CPM-based rates, exclude outlier posts, determine offer/counter ranges, check thresholds | Pure business logic module, no external dependencies |
| **Response Composer** | Generate negotiation emails using LLM, inject pricing context, maintain tone consistency | Prompt template + LLM call + output validation |
| **Escalation Router** | Determine when to escalate, package context for human review, route to Slack with actionable buttons | Rules engine evaluating escalation conditions |
| **Event Router** | Route incoming events (new email, campaign created, human response) to appropriate handler | Event bus pattern, maps event types to handlers |
| **State Machine** | Track negotiation lifecycle (initial_offer -> counter -> accepted/rejected/escalated) | Finite state machine per negotiation thread |
| **Agent Registry** | Register available agents (negotiation, future outreach, future strategist), route work to correct agent | Plugin-style registration, future extensibility point |

## Recommended Project Structure

```
src/
├── agents/                    # Agent definitions and logic
│   ├── negotiation/           # The negotiation agent (v1 focus)
│   │   ├── agent.ts           # Agent entry point and lifecycle
│   │   ├── pricing-engine.ts  # CPM calculation, threshold logic
│   │   ├── thread-manager.ts  # Conversation state tracking
│   │   ├── response-composer.ts # Email generation via LLM
│   │   ├── escalation-router.ts # Escalation decision logic
│   │   └── prompts/           # LLM prompt templates
│   │       ├── initial-offer.ts
│   │       ├── counter-offer.ts
│   │       ├── acceptance.ts
│   │       └── system.ts      # System prompt for negotiation persona
│   └── registry.ts            # Agent registry for multi-agent future
│
├── gateways/                  # External service integrations
│   ├── email/                 # Email send/receive abstraction
│   │   ├── gmail-client.ts    # Gmail API implementation
│   │   ├── email-gateway.ts   # Abstract email interface
│   │   └── types.ts           # Email message types
│   ├── slack/                 # Slack notifications and escalation
│   │   ├── slack-client.ts    # Slack Web API wrapper
│   │   ├── message-builder.ts # Rich message formatting
│   │   └── interaction-handler.ts # Handle button clicks from Slack
│   ├── clickup/               # Campaign data ingestion
│   │   ├── clickup-client.ts  # ClickUp API wrapper
│   │   ├── webhook-handler.ts # Incoming webhook processing
│   │   └── campaign-mapper.ts # ClickUp data -> internal format
│   └── llm/                   # LLM provider abstraction
│       ├── llm-client.ts      # Anthropic SDK wrapper
│       ├── prompt-manager.ts  # Template rendering, token counting
│       └── types.ts           # LLM request/response types
│
├── core/                      # Core domain logic (no external deps)
│   ├── state-machine.ts       # Negotiation state transitions
│   ├── event-router.ts        # Event dispatching to handlers
│   ├── types.ts               # Core domain types (Negotiation, Campaign, Influencer)
│   └── errors.ts              # Domain-specific error types
│
├── data/                      # Data access layer
│   ├── repositories/          # Data access abstractions
│   │   ├── negotiation-repo.ts
│   │   ├── campaign-repo.ts
│   │   └── thread-repo.ts
│   ├── models/                # Database models/schemas
│   │   ├── negotiation.ts
│   │   ├── campaign.ts
│   │   ├── influencer.ts
│   │   └── audit-log.ts
│   └── migrations/            # Database migrations
│
├── server/                    # HTTP server for webhooks
│   ├── app.ts                 # Express/Fastify app setup
│   ├── routes/                # Webhook endpoints
│   │   ├── clickup-webhook.ts
│   │   ├── gmail-webhook.ts   # Gmail push notification receiver
│   │   └── slack-interaction.ts
│   └── middleware/            # Auth, logging, error handling
│
├── jobs/                      # Background jobs and scheduling
│   ├── email-poller.ts        # Poll Gmail for new replies
│   ├── stale-thread-checker.ts # Detect stalled negotiations
│   └── scheduler.ts           # Job scheduling setup
│
├── config/                    # Configuration management
│   ├── index.ts               # Config loader
│   ├── schema.ts              # Config validation (zod)
│   └── defaults.ts            # Default values
│
└── index.ts                   # Application entry point
```

### Structure Rationale

- **agents/:** Isolated agent logic. Each agent is a self-contained module with its own prompts, business logic, and lifecycle. The registry enables future agents to be added without modifying existing code. This is the most critical architectural decision for multi-agent extensibility.
- **gateways/:** All external service integrations are behind abstract interfaces. The Gmail client implements an email gateway interface, so a future Instantly integration or other email provider swaps in without touching agent code. Same pattern for Slack (could swap to Teams) or ClickUp (could swap to another PM tool).
- **core/:** Pure domain logic with zero external dependencies. The state machine, event routing, and domain types live here. This is the most testable layer -- all unit tests for negotiation logic target this layer.
- **data/:** Repository pattern abstracts database access. Agents and core logic never import database drivers directly. Enables swapping SQLite (dev) to PostgreSQL (prod) without code changes.
- **server/:** Thin HTTP layer only for receiving webhooks. Not a full REST API -- the system is event-driven, not request-response. Keeps the server layer minimal.
- **jobs/:** Background processes separated from request handlers. Email polling, stale negotiation detection, and scheduled tasks live here. Clear separation from webhook-triggered flows.

## Architectural Patterns

### Pattern 1: Event-Driven Agent Pipeline

**What:** All system activity flows through events. An incoming email creates a `new_reply` event. A ClickUp webhook creates a `campaign_created` event. The event router dispatches to the appropriate handler (agent). This decouples triggers from logic.

**When to use:** Always -- this is the primary system pattern. Every external stimulus becomes an event before reaching agent logic.

**Trade-offs:**
- Pro: Clean separation, easy to add new event sources, testable in isolation
- Pro: Natural fit for async email processing -- events can be queued and retried
- Con: Slight indirection overhead; harder to trace execution in simple cases
- Con: Must be careful with event ordering for same-thread events

**Example:**
```typescript
// core/event-router.ts
interface NegotiationEvent {
  type: 'new_reply' | 'campaign_created' | 'human_response' | 'escalation_timeout';
  threadId: string;
  payload: Record<string, unknown>;
  timestamp: Date;
}

class EventRouter {
  private handlers: Map<string, EventHandler[]> = new Map();

  register(eventType: string, handler: EventHandler): void {
    const existing = this.handlers.get(eventType) || [];
    this.handlers.set(eventType, [...existing, handler]);
  }

  async dispatch(event: NegotiationEvent): Promise<void> {
    const handlers = this.handlers.get(event.type) || [];
    for (const handler of handlers) {
      await handler.handle(event);
    }
  }
}
```

### Pattern 2: Finite State Machine per Negotiation Thread

**What:** Each negotiation thread has an explicit state machine tracking its lifecycle. States include: `awaiting_reply`, `analyzing_reply`, `composing_response`, `awaiting_human`, `agreed`, `rejected`, `stalled`. Transitions are guarded by conditions (e.g., can only move to `agreed` from `analyzing_reply` if rate is within threshold).

**When to use:** Always for tracking negotiation lifecycle. This prevents impossible states (like sending an offer while already escalated) and makes the system auditable.

**Trade-offs:**
- Pro: Prevents invalid state transitions, provides clear audit trail
- Pro: Easy to visualize and debug negotiation flow
- Pro: Natural fit for the negotiation domain (offers, counters, acceptance are discrete states)
- Con: Requires careful upfront design of all states and transitions
- Con: Adding new states later requires migration of existing records

**Example:**
```typescript
// core/state-machine.ts
type NegotiationState =
  | 'pending_campaign'     // Campaign data received, awaiting first email
  | 'initial_offer_sent'   // First offer email sent to influencer
  | 'awaiting_reply'       // Waiting for influencer to respond
  | 'analyzing_reply'      // Processing incoming reply
  | 'composing_response'   // LLM generating counter/acceptance
  | 'escalated_to_human'   // Sent to Slack, awaiting human decision
  | 'agreed'               // Both parties accepted terms
  | 'rejected'             // Influencer declined or negotiation failed
  | 'stalled';             // No response after timeout threshold

type NegotiationTransition =
  | { from: 'initial_offer_sent'; to: 'awaiting_reply'; trigger: 'email_sent' }
  | { from: 'awaiting_reply'; to: 'analyzing_reply'; trigger: 'reply_received' }
  | { from: 'analyzing_reply'; to: 'composing_response'; trigger: 'within_threshold' }
  | { from: 'analyzing_reply'; to: 'escalated_to_human'; trigger: 'exceeds_threshold' }
  | { from: 'composing_response'; to: 'awaiting_reply'; trigger: 'counter_sent' }
  | { from: 'composing_response'; to: 'agreed'; trigger: 'terms_accepted' }
  | { from: 'escalated_to_human'; to: 'composing_response'; trigger: 'human_approved' }
  | { from: 'escalated_to_human'; to: 'rejected'; trigger: 'human_rejected' }
  | { from: 'awaiting_reply'; to: 'stalled'; trigger: 'timeout' };

class NegotiationStateMachine {
  private state: NegotiationState;
  private transitions: NegotiationTransition[];

  transition(trigger: string): NegotiationState {
    const valid = this.transitions.find(
      t => t.from === this.state && t.trigger === trigger
    );
    if (!valid) {
      throw new InvalidTransitionError(this.state, trigger);
    }
    this.state = valid.to;
    return this.state;
  }
}
```

### Pattern 3: Gateway Abstraction (Ports & Adapters)

**What:** External services are accessed through abstract interfaces (ports). Concrete implementations (adapters) handle the API-specific details. The negotiation agent depends on `EmailGateway`, not `GmailClient`. This is the classic hexagonal architecture pattern applied specifically to the integration layer.

**When to use:** For every external service integration. Critical for testability (mock gateways in tests) and future flexibility (swap Gmail for Instantly, swap Slack for Teams).

**Trade-offs:**
- Pro: Agents are fully testable without real API calls
- Pro: Swapping integrations requires only a new adapter, not agent rewrites
- Pro: Clear contract between agent logic and external world
- Con: More files/interfaces upfront
- Con: Over-abstraction risk if gateway interface is too generic

**Example:**
```typescript
// gateways/email/email-gateway.ts
interface EmailGateway {
  getNewReplies(since: Date): Promise<EmailThread[]>;
  sendReply(threadId: string, message: EmailMessage): Promise<void>;
  getThread(threadId: string): Promise<EmailThread>;
}

// gateways/email/gmail-client.ts
class GmailEmailGateway implements EmailGateway {
  constructor(private gmail: gmail_v1.Gmail) {}

  async getNewReplies(since: Date): Promise<EmailThread[]> {
    const response = await this.gmail.users.messages.list({
      userId: 'me',
      q: `after:${Math.floor(since.getTime() / 1000)}`,
    });
    // Transform Gmail-specific format to domain EmailThread
    return this.transformThreads(response.data.messages);
  }
  // ...
}

// For testing
class MockEmailGateway implements EmailGateway {
  private threads: EmailThread[] = [];
  async getNewReplies(): Promise<EmailThread[]> {
    return this.threads;
  }
  // ...
}
```

### Pattern 4: LLM Prompt Pipeline with Structured Output

**What:** LLM calls follow a strict pipeline: (1) build context from thread history + campaign data + pricing info, (2) render prompt template with context, (3) call LLM with structured output schema, (4) validate output against schema, (5) apply business rules to LLM output. The LLM never directly controls system actions -- its output is always validated and gated.

**When to use:** Every LLM interaction in the system. The negotiation agent uses LLM for analyzing replies (intent classification), composing responses (email drafting), and edge case detection (should this escalate?).

**Trade-offs:**
- Pro: LLM hallucinations are caught by validation layer before reaching email
- Pro: Structured output ensures predictable downstream processing
- Pro: Prompt templates are versioned and reviewable
- Con: Requires careful schema design upfront
- Con: Structured output adds latency vs freeform generation

**Example:**
```typescript
// agents/negotiation/response-composer.ts
interface NegotiationAnalysis {
  intent: 'accept' | 'counter' | 'reject' | 'question' | 'unclear';
  proposedRate: number | null;
  proposedDeliverables: string[];
  sentiment: 'positive' | 'neutral' | 'negative';
  escalationReasons: string[];
  confidence: number;  // 0-1 how confident the LLM is in this analysis
}

async function analyzeReply(
  thread: EmailThread,
  campaign: Campaign,
  llmClient: LLMClient
): Promise<NegotiationAnalysis> {
  const prompt = renderTemplate('analyze-reply', {
    threadHistory: thread.messages,
    campaignContext: campaign,
    currentOffer: thread.lastOffer,
  });

  const analysis = await llmClient.generateStructured<NegotiationAnalysis>(
    prompt,
    negotiationAnalysisSchema  // Zod schema for validation
  );

  // Business rule gate: low confidence -> escalate
  if (analysis.confidence < 0.7) {
    analysis.escalationReasons.push('low_confidence_analysis');
  }

  return analysis;
}
```

### Pattern 5: Human-in-the-Loop Escalation Circuit

**What:** The escalation path is a first-class architectural concern, not an afterthought. When the agent encounters an edge case (rate exceeds $30 CPM, unusual request, low confidence analysis), it packages full context into a Slack message with actionable buttons. The human response routes back through the event system and resumes the negotiation state machine. A timeout mechanism ensures stalled escalations are surfaced.

**When to use:** Whenever the agent's confidence is below threshold OR business rules require human judgment. This is not an error path -- it is a normal operating mode for hybrid agents.

**Trade-offs:**
- Pro: Builds trust gradually -- humans see every edge case
- Pro: Creates training data for future full-autonomy mode
- Pro: Slack is where the team already works -- no new tools
- Con: Human response latency adds hours/days to negotiation cycle
- Con: Must handle partial context if human responds much later

**Example:**
```typescript
// agents/negotiation/escalation-router.ts
interface EscalationContext {
  negotiationId: string;
  influencer: { name: string; platform: string; avgViews: number };
  threadSummary: string;        // LLM-generated thread summary
  currentOffer: number;
  influencerAsk: number;
  cpmAtAsk: number;
  maxCpm: number;
  suggestedResponse: string;    // What the agent would say if autonomous
  escalationReason: string;
  fullThread: EmailMessage[];   // Complete email history
}

function shouldEscalate(
  analysis: NegotiationAnalysis,
  campaign: Campaign,
  pricing: PricingResult
): EscalationDecision {
  const reasons: string[] = [];

  if (pricing.cpm > campaign.maxCpm) reasons.push('exceeds_cpm_threshold');
  if (analysis.confidence < 0.7) reasons.push('low_confidence');
  if (analysis.intent === 'unclear') reasons.push('unclear_intent');
  if (analysis.proposedDeliverables.some(d => !campaign.allowedDeliverables.includes(d))) {
    reasons.push('unexpected_deliverable_type');
  }
  // Custom negotiation tactics the agent should not handle
  if (analysis.proposedRate && analysis.proposedRate > pricing.walkAwayPrice * 2) {
    reasons.push('extreme_counter');
  }

  return {
    shouldEscalate: reasons.length > 0,
    reasons,
    urgency: reasons.includes('exceeds_cpm_threshold') ? 'high' : 'medium',
  };
}
```

## Data Flow

### Primary Flow: Inbound Email -> Agent Response

```
[Gmail Inbox]
    │ (Gmail push notification or polling)
    ▼
[Email Gateway] ── parse, extract thread ID, get full thread
    │
    ▼
[Event Router] ── creates 'new_reply' event
    │
    ▼
[Thread Manager] ── loads negotiation state, validates state transition
    │
    ▼
[Pricing Engine] ── calculates CPM from influencer metrics
    │              ── determines acceptable range
    │              ── excludes viral outlier posts from avg
    │
    ▼
[Response Composer] ── calls LLM to analyze reply intent
    │                ── calls LLM to draft response
    │                ── validates output against schema
    │
    ├── [within threshold] ──▶ [Email Gateway] ── sends counter/acceptance
    │                              │
    │                              ▼
    │                         [Thread Manager] ── updates state
    │                              │
    │                              ▼
    │                         [Audit Log] ── records action + reasoning
    │
    └── [exceeds threshold] ──▶ [Escalation Router]
                                    │
                                    ▼
                               [Slack Gateway] ── sends rich message with context
                                    │
                                    ▼
                               [Thread Manager] ── state = 'escalated_to_human'
```

### Secondary Flow: Human Escalation Response

```
[Slack Button Click]
    │ (Slack interaction payload)
    ▼
[Slack Interaction Handler] ── validates signature, extracts action
    │
    ▼
[Event Router] ── creates 'human_response' event
    │
    ▼
[Thread Manager] ── loads escalated negotiation, validates 'escalated_to_human' state
    │
    ├── [human approves suggested response] ──▶ [Email Gateway] ── sends agent's draft
    │
    ├── [human modifies response] ──▶ [Response Composer] ── adjusts based on feedback
    │                                     │
    │                                     ▼
    │                                [Email Gateway] ── sends modified response
    │
    └── [human rejects / takes over] ──▶ [Thread Manager] ── state = 'human_takeover'
                                             │
                                             ▼
                                        [Audit Log] ── records handoff
```

### Tertiary Flow: Campaign Data Ingestion

```
[ClickUp Form Submission]
    │ (webhook or API poll)
    ▼
[Campaign Ingester] ── validates required fields
    │                ── normalizes influencer metrics
    │                ── creates Campaign record
    │
    ▼
[Event Router] ── creates 'campaign_created' event
    │
    ▼
[Negotiation Agent] ── creates negotiation records per influencer
    │                ── calculates initial offer per influencer using Pricing Engine
    │                ── queues initial outreach (or waits for existing thread)
    │
    ▼
[Thread Manager] ── state = 'pending_campaign' or 'initial_offer_sent'
```

### Agreement Flow: Notification on Success

```
[Response Composer] ── detects acceptance in influencer reply
    │
    ▼
[Thread Manager] ── state = 'agreed'
    │
    ▼
[Slack Gateway] ── sends rich agreement notification
    │              ── includes: influencer name, platform, agreed rate,
    │                 deliverables, CPM achieved, next steps
    │
    ▼
[Audit Log] ── records full negotiation history + outcome
```

### Key Data Flows

1. **Email thread context accumulation:** Every email in a thread is stored and passed to the LLM as conversation history. The Thread Manager maintains a running context window that includes all previous messages, offers, and counters. This is critical -- the LLM needs full history to negotiate coherently.

2. **Pricing context injection:** The Pricing Engine's output (target rate, acceptable range, current CPM, max CPM) is injected into every LLM prompt as structured context. The LLM does not calculate pricing -- it uses the Pricing Engine's numbers to frame its negotiation language.

3. **Escalation context packaging:** When escalating, the system creates a comprehensive context package: thread summary (LLM-generated), all raw emails, pricing calculations, the agent's suggested response, and the specific reason for escalation. This is sent to Slack so the human has everything needed to make a decision without leaving Slack.

4. **Audit trail:** Every action (email sent, reply analyzed, escalation triggered, human response) is logged with timestamp, reasoning, and the LLM's analysis. This serves both compliance (proving the agent acted within policy) and training (identifying patterns for future autonomy improvements).

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 campaigns (MVP) | Single process, SQLite database, polling-based email checks every 2-5 minutes, synchronous LLM calls. No queue needed. |
| 10-100 campaigns | PostgreSQL for concurrent access, add job queue (BullMQ) for email processing, parallel LLM calls. Still single server. |
| 100-1000 campaigns | Message queue (Redis-backed BullMQ) for event processing, connection pooling for Gmail API, rate limiting for LLM calls, horizontal scaling with multiple worker processes. |

### Scaling Priorities

1. **First bottleneck: LLM API rate limits.** Each negotiation reply requires 2-3 LLM calls (analyze intent, compose response, optionally summarize for escalation). At ~2 seconds per call, 100 simultaneous negotiations could overwhelm API limits. **Mitigation:** Queue LLM calls with backpressure; batch processing during off-hours; cache analysis results for retries.

2. **Second bottleneck: Gmail API quotas.** Gmail API has per-user quotas (~250 quota units/second for the project). Polling many threads frequently will hit limits. **Mitigation:** Use Gmail push notifications (pub/sub) instead of polling for production; batch thread fetches; cache thread data locally.

3. **Third bottleneck: Human escalation latency.** As volume grows, humans become the bottleneck. Escalations pile up in Slack. **Mitigation:** Add escalation priority scoring, auto-resolve low-risk escalations after timeout, build toward higher autonomy thresholds.

## Anti-Patterns

### Anti-Pattern 1: LLM as Decision Engine

**What people do:** Let the LLM decide pricing, thresholds, and whether to escalate. "Here's the thread, what should we do?" with no guardrails.

**Why it's wrong:** LLMs hallucinate numbers, ignore business rules inconsistently, and cannot be audited. A $50 CPM deal approved by "the AI decided it was fine" is an indefensible business outcome.

**Do this instead:** LLM handles language tasks (analyzing intent, composing responses). Deterministic code handles business logic (pricing calculations, threshold checks, escalation rules). The LLM operates within a sandbox defined by the Pricing Engine and Escalation Router.

### Anti-Pattern 2: Monolithic Email Processing

**What people do:** Process emails synchronously in the webhook handler. Gmail push notification arrives -> analyze -> compose -> send reply, all in one request handler.

**Why it's wrong:** LLM calls take 2-10 seconds. Webhook handlers should respond in <3 seconds to avoid retries. Long-running processing in webhook handlers causes timeout failures and duplicate processing.

**Do this instead:** Webhook handler acknowledges receipt immediately (200 OK), enqueues an event, and returns. A background worker picks up the event, processes it asynchronously, and handles retries independently.

### Anti-Pattern 3: Hardcoded Single-Agent Architecture

**What people do:** Build the negotiation agent as a tightly coupled monolith with Gmail, Slack, and ClickUp wired directly into agent logic. "We'll refactor for multi-agent later."

**Why it's wrong:** "Later" means "rewrite." If the outreach agent needs email access, it has to duplicate the Gmail integration or create circular dependencies. The agent registry and gateway abstractions cost minimal effort now but save weeks of refactoring later.

**Do this instead:** Build the gateway abstraction from day one. The negotiation agent gets an `EmailGateway` injected, not a `GmailClient`. The agent registry exists from the start even with only one agent registered. When the outreach agent arrives, it registers itself and gets its own gateway instances.

### Anti-Pattern 4: Storing Only Latest State

**What people do:** Store the current negotiation state (latest offer, current status) without preserving the full history of state transitions and reasoning.

**Why it's wrong:** Debugging why a negotiation went sideways requires knowing what the agent analyzed at each step, what the LLM returned, and why specific decisions were made. Without history, you cannot audit, learn, or improve.

**Do this instead:** Event-source the negotiation history. Every state transition is an immutable event with timestamp, trigger, LLM analysis, and resulting action. The current state is derived from replaying events. This provides a complete audit trail and enables analysis of agent performance.

### Anti-Pattern 5: Shared Prompts Across Negotiation Stages

**What people do:** Use one mega-prompt for all negotiation scenarios. "You are a negotiator. Here's a thread. Respond appropriately."

**Why it's wrong:** Different negotiation stages require different LLM behaviors. An initial offer needs confident, anchoring language. A counter-offer needs flexibility signals. Acceptance detection needs precision, not creativity. One prompt cannot optimize for all of these.

**Do this instead:** Separate prompts per negotiation stage (initial offer, counter-offer, acceptance detection, escalation summary). Each prompt is tuned for its specific task with appropriate examples, tone guidance, and output schema.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Gmail API** | OAuth 2.0 + REST API. Use service account or user OAuth for server-to-server. Push notifications via Google Cloud Pub/Sub for real-time, with polling fallback. | Token refresh handling is critical. Gmail thread IDs are the primary key for conversation tracking. Must handle label management, message formatting (MIME), and reply threading (In-Reply-To headers). |
| **Slack API** | Web API for sending messages, Bolt framework for receiving interactions (button clicks). App installed to workspace. | Use Block Kit for rich message formatting. Interactive messages require a public webhook URL. Message timestamps (`ts`) are needed for updating escalation messages after human responds. |
| **ClickUp API** | Webhook for form submission events, REST API for reading task details. | Webhook signature verification required. Map ClickUp custom fields to campaign data schema. Handle webhook delivery failures (ClickUp retries for up to 48 hours). |
| **Anthropic API (Claude)** | Official TypeScript SDK. Structured output via tool_use for predictable response parsing. | Use streaming for long responses to avoid timeouts. Implement exponential backoff for rate limits. Monitor token usage per negotiation for cost control. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Agent Core <-> Gateways | Dependency injection via interfaces | Agents never import gateway implementations directly. Container/factory provides concrete instances. |
| Agent Core <-> Data Layer | Repository pattern | Agent calls `negotiationRepo.getByThreadId()`, never raw SQL. Repository handles connection management. |
| Event Router <-> All Handlers | Typed events via EventEmitter or simple dispatch | Events are the primary communication pattern. Handlers are registered at startup. |
| Server (webhooks) <-> Agent Core | Via Event Router | Webhook endpoints parse incoming payload, create domain event, dispatch to router. Never call agent logic directly from HTTP handler. |
| Background Jobs <-> Agent Core | Via Event Router | Poller creates events for new emails. Scheduler creates timeout events for stalled threads. Same dispatch pattern as webhooks. |

## Build Order (Dependencies)

The architecture has clear dependency layers that dictate build order:

```
Phase 1: Foundation (no external dependencies)
  ├── core/types.ts          -- Domain types first, everything depends on these
  ├── core/state-machine.ts  -- Negotiation lifecycle, pure logic
  ├── core/event-router.ts   -- Event dispatch, pure logic
  ├── core/errors.ts         -- Error types
  └── config/                -- Configuration management

Phase 2: Business Logic (depends on Phase 1)
  ├── agents/negotiation/pricing-engine.ts  -- CPM calculations, pure logic
  ├── agents/negotiation/escalation-router.ts  -- Escalation rules, pure logic
  └── data/models/           -- Database schema definitions

Phase 3: Integration Layer (depends on Phase 1 types)
  ├── gateways/email/        -- Gmail API client
  ├── gateways/slack/        -- Slack API client
  ├── gateways/llm/          -- Anthropic SDK wrapper
  ├── gateways/clickup/      -- ClickUp API client
  └── data/repositories/     -- Database access

Phase 4: Agent Assembly (depends on Phase 2 + 3)
  ├── agents/negotiation/response-composer.ts  -- LLM + pricing + templates
  ├── agents/negotiation/thread-manager.ts     -- State + email + data access
  ├── agents/negotiation/agent.ts              -- Wires everything together
  └── agents/registry.ts                       -- Agent registration

Phase 5: Server + Jobs (depends on Phase 3 + 4)
  ├── server/                -- Webhook endpoints
  ├── jobs/                  -- Background processing
  └── index.ts               -- Application bootstrap
```

**Why this order:**
- Phase 1 has zero dependencies and can be fully unit tested
- Phase 2 depends only on types and can be tested with simple assertions
- Phase 3 can be tested with mocks for external services
- Phase 4 wires phases 2+3 together; integration tests here
- Phase 5 is the thinnest layer, mostly configuration and routing

## Sources

- Anthropic Claude API documentation (tool use, structured output) -- MEDIUM confidence (training data, not verified against current docs)
- Gmail API documentation (thread management, push notifications, OAuth) -- MEDIUM confidence (training data, well-established API)
- Slack API documentation (Block Kit, interactive messages, Bolt framework) -- MEDIUM confidence (training data, well-established API)
- Hexagonal architecture / ports and adapters pattern -- HIGH confidence (well-established pattern, not API-version-dependent)
- Finite state machine patterns for multi-turn conversation agents -- HIGH confidence (fundamental CS pattern, domain-appropriate)
- Event-driven architecture for async email processing -- HIGH confidence (well-established pattern)

**Limitations:** WebSearch and WebFetch were unavailable during this research session. All specific API details (Gmail push notification setup, Slack Bolt framework, Anthropic SDK structured output) are based on training data and should be verified against current documentation during implementation phases. Core architectural patterns (event-driven, state machine, ports/adapters, prompt pipeline) are pattern-level recommendations that are not version-dependent and carry HIGH confidence.

---
*Architecture research for: AI Email Negotiation Agent*
*Researched: 2026-02-18*
