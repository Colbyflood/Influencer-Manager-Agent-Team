# Phase 1: Core Domain and Pricing Engine - Research

**Researched:** 2026-02-18
**Domain:** Deterministic pricing logic, negotiation state machine, platform rate cards, rate boundary enforcement
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
No locked decisions -- user opted to skip detailed discussion. The roadmap provides clear direction.

### Claude's Discretion
User opted to skip detailed discussion -- the roadmap provides clear direction. Claude has full flexibility on implementation decisions within this phase, guided by:

- **CPM rate calculation**: Agent reads pre-calculated pay ranges from Google Sheets (Phase 2), but the pricing engine in this phase should accept pay range inputs and calculate rates per deliverable type within the $20-$30 CPM range
- **Negotiation state machine**: States defined in requirements (initial_offer, awaiting_reply, counter_received, counter_sent, agreed, rejected, escalated, stale) with invalid transitions rejected
- **Platform rate cards**: Support Instagram (post, story, reel), TikTok (video, story), YouTube (dedicated video, integration, short) with platform-aware pricing
- **Rate boundary enforcement**: Escalate when CPM exceeds $30 threshold; flag unusually low rates (possible misunderstanding)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| NEG-02 | Agent uses pre-calculated pay range to guide negotiation (starting at $20 CPM floor, moving toward $30 CPM ceiling) | Pricing engine architecture with Decimal arithmetic, CPM calculation functions, rate interpolation logic |
| NEG-03 | Agent supports platform-specific deliverable pricing for Instagram (post, story, reel), TikTok (video, story), and YouTube (dedicated video, integration, short) | Platform/deliverable type enums, rate card data model, platform-aware pricing functions |
| NEG-04 | Agent tracks negotiation state across multi-turn email conversations (states: initial_offer, awaiting_reply, counter_received, counter_sent, agreed, rejected, escalated, stale) | Hand-rolled state machine with enum states, transition validation, Pydantic models for state persistence |
| NEG-07 | Agent enforces rate boundaries -- escalates when influencer demands exceed $30 CPM threshold | Boundary enforcement functions, escalation trigger types, low-rate flagging logic |
</phase_requirements>

## Summary

Phase 1 builds the foundational business logic modules for the influencer negotiation agent: a deterministic pricing engine, a negotiation state machine, platform-specific rate cards, and rate boundary enforcement. These are pure Python modules with zero external service dependencies (no email, no Slack, no Google Sheets). They accept structured inputs and produce structured outputs, making them fully unit-testable in isolation. Every downstream phase depends on these modules being correct and thoroughly tested.

The technical challenge is moderate but the correctness bar is high. The pricing engine performs monetary calculations where floating-point errors are unacceptable -- the `Decimal` type from Python's standard library is mandatory. The state machine must enforce that only valid transitions occur and reject all others, since invalid state transitions in a negotiation context could mean sending a counter-offer after an agreement or proposing rates after escalation. The rate card system must distinguish between platforms and deliverable types because the same CPM range should not apply uniformly (though for v1, the $20-$30 range applies to all types per project spec, with the architecture supporting per-type ranges for future use).

This phase establishes the Python project structure, tooling (uv, ruff, mypy, pytest), and domain model that all subsequent phases build upon. Getting the project skeleton right now avoids restructuring later.

**Primary recommendation:** Build all pricing logic with `Decimal` arithmetic, implement the state machine as a hand-rolled Python class using `StrEnum` for states and events (no library dependency needed for 8 states), and use Pydantic v2 models for all domain types with strict validation.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12+ | Primary language | AI/ML ecosystem is Python-first; matches project-level stack decision from research |
| Pydantic | 2.12.x | Domain models, data validation, serialization | Industry standard for Python data validation; Rust-powered core (pydantic-core) for speed; strict mode prevents silent type coercion |
| decimal (stdlib) | stdlib | Monetary/pricing arithmetic | Python standard library; exact decimal representation avoids float errors in CPM calculations |
| enum (stdlib) | stdlib | State and deliverable type enumerations | StrEnum (Python 3.11+) provides type-safe string enums for states, platforms, deliverable types |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.x | Unit and integration testing | All test files; required for this phase's heavy testing emphasis |
| pytest-cov | latest | Test coverage reporting | Coverage measurement; target 95%+ for pricing and state machine modules |
| ruff | 0.15.x | Linting and formatting | All Python files; replaces flake8 + black + isort |
| mypy | 1.19.x | Static type checking | All modules; catches type errors in pricing calculations before runtime |
| uv | 0.10.x | Package and project management | Project initialization, dependency management, virtual environment |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled state machine | python-statemachine 2.6.x | Library adds dependency for ~100 lines of code; our 8-state machine is simple enough to hand-roll; hand-rolled integrates more cleanly with Pydantic models and database serialization; library is better for complex statecharts with 20+ states |
| Hand-rolled state machine | transitions library | Same tradeoff as above; transitions is heavier and designed for more complex use cases |
| Pydantic models | dataclasses + manual validation | Pydantic provides serialization, JSON schema, strict validation, and computed fields out of the box; dataclasses would require hand-rolling all of this |
| Decimal | float | Float causes rounding errors in monetary calculations (0.1 + 0.1 + 0.1 != 0.3); Decimal is exact; there is no acceptable use of float for pricing |
| Decimal | integer cents | Storing as integer cents (2000 = $20.00) is also valid but less readable for CPM calculations where we divide by 1000; Decimal with quantize() is cleaner |

**Installation:**
```bash
# Initialize project
uv init influencer-negotiation-agent
cd influencer-negotiation-agent

# Set Python version
echo "3.12" > .python-version

# Core dependencies (Phase 1 only needs Pydantic for domain models)
uv add pydantic

# Dev dependencies
uv add --dev pytest pytest-cov ruff mypy
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── negotiation/              # Top-level package
│   ├── __init__.py
│   ├── domain/               # Core domain types and enums
│   │   ├── __init__.py
│   │   ├── types.py          # Platform, DeliverableType, NegotiationState enums
│   │   ├── models.py         # Pydantic models: PayRange, Deliverable, RateCard, NegotiationContext
│   │   └── errors.py         # Domain-specific exceptions
│   ├── pricing/              # Pricing engine (deterministic)
│   │   ├── __init__.py
│   │   ├── engine.py         # CPM calculation, rate computation per deliverable
│   │   ├── rate_cards.py     # Platform-specific rate card definitions and lookup
│   │   └── boundaries.py    # Rate boundary enforcement, escalation triggers
│   └── state_machine/        # Negotiation state tracking
│       ├── __init__.py
│       ├── machine.py        # NegotiationStateMachine class with transition validation
│       └── transitions.py    # Transition definitions, guards, allowed transitions map
tests/
├── __init__.py
├── conftest.py               # Shared fixtures (sample influencers, deliverables, rate cards)
├── domain/
│   ├── test_types.py         # Enum and model validation tests
│   └── test_models.py        # Pydantic model serialization/validation tests
├── pricing/
│   ├── test_engine.py        # CPM calculation tests (many edge cases)
│   ├── test_rate_cards.py    # Rate card lookup tests per platform/deliverable
│   └── test_boundaries.py   # Boundary enforcement and escalation trigger tests
└── state_machine/
    ├── test_machine.py       # State transition tests (valid and invalid)
    └── test_transitions.py   # Transition guard tests
pyproject.toml                # Project config with ruff, mypy, pytest settings
```

### Pattern 1: Enum-Based Domain Types with StrEnum
**What:** Define all domain constants (platforms, deliverable types, negotiation states) as `StrEnum` members. This provides type safety, serialization to/from strings (for database/JSON), IDE autocompletion, and exhaustive match/case handling.
**When to use:** Every domain constant in the system.
**Example:**
```python
# Source: Python 3.12 stdlib enum module
from enum import StrEnum

class Platform(StrEnum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"

class DeliverableType(StrEnum):
    # Instagram
    INSTAGRAM_POST = "instagram_post"
    INSTAGRAM_STORY = "instagram_story"
    INSTAGRAM_REEL = "instagram_reel"
    # TikTok
    TIKTOK_VIDEO = "tiktok_video"
    TIKTOK_STORY = "tiktok_story"
    # YouTube
    YOUTUBE_DEDICATED = "youtube_dedicated"
    YOUTUBE_INTEGRATION = "youtube_integration"
    YOUTUBE_SHORT = "youtube_short"

class NegotiationState(StrEnum):
    INITIAL_OFFER = "initial_offer"
    AWAITING_REPLY = "awaiting_reply"
    COUNTER_RECEIVED = "counter_received"
    COUNTER_SENT = "counter_sent"
    AGREED = "agreed"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    STALE = "stale"
```

### Pattern 2: Pydantic v2 Models with Strict Validation
**What:** All domain data structures are Pydantic `BaseModel` subclasses with type annotations, validators, and computed properties. Use `model_config = ConfigDict(frozen=True)` for immutable value objects (like rate calculations). Use strict mode for fields where type coercion would hide bugs.
**When to use:** Every data structure that crosses a module boundary.
**Example:**
```python
# Source: Pydantic v2 docs (https://docs.pydantic.dev/latest/concepts/models/)
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_validator

class PayRange(BaseModel):
    """Pre-calculated pay range from Google Sheet (Phase 2 provides this)."""
    model_config = ConfigDict(frozen=True)

    min_rate: Decimal  # Dollar amount at $20 CPM floor
    max_rate: Decimal  # Dollar amount at $30 CPM ceiling
    average_views: int  # Average views (outliers already excluded)

    @field_validator("min_rate", "max_rate", mode="before")
    @classmethod
    def coerce_to_decimal(cls, v: object) -> Decimal:
        if isinstance(v, float):
            raise ValueError("Use Decimal or string, not float, for monetary values")
        return Decimal(str(v))

    @field_validator("average_views")
    @classmethod
    def views_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("average_views must be positive")
        return v
```

### Pattern 3: Hand-Rolled State Machine with Transition Map
**What:** A simple state machine class that holds current state, defines valid transitions as a dict mapping `(from_state, event) -> to_state`, and raises on invalid transitions. No external library needed for 8 states.
**When to use:** For the negotiation lifecycle tracking.
**Example:**
```python
# Source: Standard finite state machine pattern
from negotiation.domain.types import NegotiationState

class InvalidTransitionError(Exception):
    def __init__(self, current_state: NegotiationState, event: str):
        self.current_state = current_state
        self.event = event
        super().__init__(
            f"Cannot apply event '{event}' in state '{current_state}'"
        )

# Valid transitions: (from_state, event) -> to_state
TRANSITIONS: dict[tuple[NegotiationState, str], NegotiationState] = {
    (NegotiationState.INITIAL_OFFER, "send_offer"): NegotiationState.AWAITING_REPLY,
    (NegotiationState.AWAITING_REPLY, "receive_reply"): NegotiationState.COUNTER_RECEIVED,
    (NegotiationState.AWAITING_REPLY, "timeout"): NegotiationState.STALE,
    (NegotiationState.COUNTER_RECEIVED, "send_counter"): NegotiationState.COUNTER_SENT,
    (NegotiationState.COUNTER_RECEIVED, "accept"): NegotiationState.AGREED,
    (NegotiationState.COUNTER_RECEIVED, "reject"): NegotiationState.REJECTED,
    (NegotiationState.COUNTER_RECEIVED, "escalate"): NegotiationState.ESCALATED,
    (NegotiationState.COUNTER_SENT, "receive_reply"): NegotiationState.COUNTER_RECEIVED,
    (NegotiationState.COUNTER_SENT, "timeout"): NegotiationState.STALE,
    (NegotiationState.ESCALATED, "resume_counter"): NegotiationState.COUNTER_SENT,
    (NegotiationState.ESCALATED, "reject"): NegotiationState.REJECTED,
    (NegotiationState.STALE, "receive_reply"): NegotiationState.COUNTER_RECEIVED,
    (NegotiationState.STALE, "reject"): NegotiationState.REJECTED,
}

class NegotiationStateMachine:
    def __init__(self, initial_state: NegotiationState = NegotiationState.INITIAL_OFFER):
        self._state = initial_state
        self._history: list[tuple[NegotiationState, str, NegotiationState]] = []

    @property
    def state(self) -> NegotiationState:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in {
            NegotiationState.AGREED,
            NegotiationState.REJECTED,
        }

    def trigger(self, event: str) -> NegotiationState:
        if self.is_terminal:
            raise InvalidTransitionError(self._state, event)
        key = (self._state, event)
        if key not in TRANSITIONS:
            raise InvalidTransitionError(self._state, event)
        old_state = self._state
        self._state = TRANSITIONS[key]
        self._history.append((old_state, event, self._state))
        return self._state

    def get_valid_events(self) -> list[str]:
        return [event for (state, event) in TRANSITIONS if state == self._state]
```

### Pattern 4: Decimal-Based Pricing Engine
**What:** All monetary calculations use Python's `Decimal` type with explicit rounding via `quantize()`. The CPM formula is: `rate = (average_views / 1000) * cpm`. The pricing engine accepts a pay range and deliverable type, and returns a calculated rate.
**When to use:** Every pricing calculation in the system.
**Example:**
```python
# Source: Python stdlib decimal module (https://docs.python.org/3/library/decimal.html)
from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")
CPM_FLOOR = Decimal("20")
CPM_CEILING = Decimal("30")

def calculate_rate(average_views: int, cpm: Decimal) -> Decimal:
    """Calculate rate from views and CPM. Returns dollar amount."""
    views_in_thousands = Decimal(average_views) / Decimal("1000")
    rate = (views_in_thousands * cpm).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return rate

def calculate_initial_offer(average_views: int) -> Decimal:
    """Calculate initial offer at CPM floor ($20)."""
    return calculate_rate(average_views, CPM_FLOOR)

def calculate_cpm_from_rate(rate: Decimal, average_views: int) -> Decimal:
    """Back-calculate CPM from a proposed rate. Used to evaluate counter-offers."""
    if average_views <= 0:
        raise ValueError("average_views must be positive")
    views_in_thousands = Decimal(average_views) / Decimal("1000")
    cpm = (rate / views_in_thousands).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return cpm
```

### Anti-Patterns to Avoid
- **Using float for monetary values:** `0.1 + 0.1 + 0.1` produces `0.30000000000000004` in float. Use `Decimal("0.1")` which produces exact `Decimal("0.3")`. This is not optional -- float arithmetic in pricing is a correctness bug.
- **Allowing arbitrary state transitions:** Never allow `state = new_state` assignment. All transitions must go through the state machine's `trigger()` method which validates against the transition map. Direct assignment bypasses guards and breaks auditability.
- **Hardcoding CPM values in multiple places:** Define `CPM_FLOOR` and `CPM_CEILING` as module-level constants or Pydantic settings in one place. Never scatter `20` and `30` as magic numbers through the codebase.
- **Making domain models mutable when they should be immutable:** Rate calculations, pay ranges, and deliverable specs are value objects. Use `frozen=True` in Pydantic config so they cannot be accidentally mutated after creation.
- **Mixing domain logic with I/O:** This phase has ZERO external dependencies. No imports from email, Slack, database, or HTTP libraries. Domain modules accept structured inputs and return structured outputs. I/O wiring happens in later phases.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Data validation and serialization | Custom validation decorators or type checking | Pydantic v2 BaseModel | Pydantic handles type coercion, JSON schema generation, serialization to/from dict/JSON, computed fields, and custom validators. Hand-rolling this is 500+ lines of error-prone code. |
| Python linting and formatting | flake8 + black + isort separately | ruff 0.15.x | Single tool replaces three, runs 10-100x faster (Rust-based), configurable in pyproject.toml. No reason to use the trio anymore. |
| Package management | pip + venv + requirements.txt | uv 0.10.x | 10-100x faster dependency resolution, lockfile for reproducibility, handles virtualenv automatically. The modern Python standard. |
| Type checking | Manual isinstance() checks | mypy 1.19.x | Static analysis catches type errors at development time without running tests. Critical for ensuring Decimal is used everywhere instead of float. |

**Key insight:** For this phase, the domain logic itself IS the value. The only things to hand-roll are the business-specific state machine and pricing engine. Everything else (validation, tooling, testing) should use established tools.

## Common Pitfalls

### Pitfall 1: Float Arithmetic in Pricing
**What goes wrong:** Using `float` for CPM calculations produces rounding errors. `50000 / 1000 * 25.0` might produce `1249.9999999999998` instead of `1250.00`. These errors compound across calculations and lead to incorrect rates in emails.
**Why it happens:** IEEE 754 binary floating-point cannot represent most decimal fractions exactly. This is fundamental to how computers store floats, not a Python bug.
**How to avoid:** Use `Decimal` for ALL monetary values. Initialize with strings (`Decimal("20.00")`), never floats (`Decimal(20.0)`). Apply `quantize(Decimal("0.01"))` after every division or multiplication.
**Warning signs:** Tests pass with `assertAlmostEqual` instead of exact equality. Prices end in many decimal places (e.g., `$1249.9999999`). Code uses `round()` on floats instead of `Decimal.quantize()`.

### Pitfall 2: Incomplete State Transition Coverage
**What goes wrong:** The state machine allows transitions that should be invalid, or blocks transitions that should be valid. For example: allowing `AGREED -> COUNTER_SENT` (sending a counter after agreement) or blocking `STALE -> COUNTER_RECEIVED` (influencer replies to a stale thread).
**Why it happens:** Transition maps are defined as what IS allowed, but developers forget to test what is NOT allowed. They test the happy path (offer -> reply -> counter -> agree) but miss edge cases (what happens if the influencer replies to a stale thread? what if someone tries to escalate from AGREED?).
**How to avoid:** Write tests for EVERY `(state, event)` pair -- both valid and invalid. Use parameterized tests to enumerate all combinations. For 8 states and ~6 events, that is 48 combinations; test all of them. Invalid ones should raise `InvalidTransitionError`.
**Warning signs:** State machine tests only cover the happy path. No tests for invalid transitions. No tests for terminal states (AGREED, REJECTED should reject all events).

### Pitfall 3: Not Testing Edge Cases in CPM Calculations
**What goes wrong:** CPM calculations work for "normal" view counts (50K-500K) but break at extremes: very low views (100 views = $2.00 at $20 CPM), very high views (10M views = $200,000 at $20 CPM), or zero views.
**Why it happens:** Developers test with representative middle-range values and assume the math scales. But edge cases reveal: division by zero (0 views), unrealistically small rates (sub-$1 for nano-influencers), and unrealistically large rates (six figures for mega-influencers) that should all trigger different behavior.
**How to avoid:** Test with: 0 views (should raise error), 100 views ($2.00 -- valid but flagged as unusually low), 1,000 views ($20.00), 50,000 views ($1,000), 500,000 views ($10,000), 10,000,000 views ($200,000). For each, verify the math is exactly correct to the penny and that boundary checks fire appropriately.
**Warning signs:** No test cases with views below 1,000 or above 1,000,000. No handling for 0 or negative view counts. No lower-bound sanity check on calculated rates.

### Pitfall 4: Deliverable Type / Platform Mismatch
**What goes wrong:** Code allows creating an `INSTAGRAM_REEL` deliverable on the `YOUTUBE` platform, or a `YOUTUBE_SHORT` on `INSTAGRAM`. This produces nonsensical pricing.
**Why it happens:** Platform and deliverable type are stored as independent enums without a validation relationship. If the code does not enforce which deliverable types belong to which platform, invalid combinations slip through.
**How to avoid:** Define a mapping of `Platform -> set[DeliverableType]` and validate at model creation time. Use a Pydantic `model_validator` that checks the deliverable type is valid for the given platform.
**Warning signs:** No validation linking platform to deliverable type. Tests create deliverables with arbitrary platform/type combinations. Code treats deliverable type as platform-independent.

### Pitfall 5: Forgetting the Low-Rate Flag
**What goes wrong:** The system focuses on the $30 CPM ceiling for escalation but ignores unusually low rates. An influencer accepting $5 CPM might indicate a misunderstanding (wrong deliverable, wrong scope), not a great deal.
**Why it happens:** The requirements emphasize the upper boundary ($30 CPM escalation). The lower boundary is mentioned in CONTEXT.md ("flag unusually low rates") but is easy to overlook.
**How to avoid:** Implement a lower-bound check that flags (not blocks) rates significantly below the CPM floor. If an influencer proposes or accepts a rate that implies sub-$15 CPM, return a warning in the pricing result indicating potential misunderstanding. The threshold should be configurable.
**Warning signs:** Tests only check the upper boundary. No test for an influencer accepting a rate below $20 CPM. No warning mechanism for suspiciously low rates.

## Code Examples

Verified patterns from official sources:

### CPM Rate Calculation with Boundary Checking
```python
# Source: Domain logic derived from project requirements (NEG-02, NEG-07)
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from pydantic import BaseModel, ConfigDict

TWO_PLACES = Decimal("0.01")

class BoundaryResult(StrEnum):
    WITHIN_RANGE = "within_range"
    EXCEEDS_CEILING = "exceeds_ceiling"
    BELOW_FLOOR = "below_floor"
    SUSPICIOUSLY_LOW = "suspiciously_low"

class PricingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rate: Decimal             # Calculated dollar amount
    cpm: Decimal              # CPM used or back-calculated
    boundary: BoundaryResult  # Whether rate is within acceptable range
    should_escalate: bool     # True if rate exceeds ceiling
    warning: str | None = None  # Human-readable warning if applicable

def evaluate_proposed_rate(
    proposed_rate: Decimal,
    average_views: int,
    cpm_floor: Decimal = Decimal("20"),
    cpm_ceiling: Decimal = Decimal("30"),
    low_rate_threshold: Decimal = Decimal("15"),
) -> PricingResult:
    """Evaluate a proposed rate against CPM boundaries."""
    views_in_thousands = Decimal(average_views) / Decimal("1000")
    implied_cpm = (proposed_rate / views_in_thousands).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    if implied_cpm > cpm_ceiling:
        return PricingResult(
            rate=proposed_rate,
            cpm=implied_cpm,
            boundary=BoundaryResult.EXCEEDS_CEILING,
            should_escalate=True,
            warning=f"Proposed rate implies ${implied_cpm} CPM, exceeds ${cpm_ceiling} ceiling",
        )
    elif implied_cpm < low_rate_threshold:
        return PricingResult(
            rate=proposed_rate,
            cpm=implied_cpm,
            boundary=BoundaryResult.SUSPICIOUSLY_LOW,
            should_escalate=False,
            warning=f"Proposed rate implies ${implied_cpm} CPM, unusually low -- possible misunderstanding",
        )
    elif implied_cpm < cpm_floor:
        return PricingResult(
            rate=proposed_rate,
            cpm=implied_cpm,
            boundary=BoundaryResult.BELOW_FLOOR,
            should_escalate=False,
            warning=None,
        )
    else:
        return PricingResult(
            rate=proposed_rate,
            cpm=implied_cpm,
            boundary=BoundaryResult.WITHIN_RANGE,
            should_escalate=False,
            warning=None,
        )
```

### Platform-Aware Rate Card
```python
# Source: Domain logic derived from project requirements (NEG-03)
from decimal import Decimal
from negotiation.domain.types import Platform, DeliverableType

# Which deliverable types belong to which platform
PLATFORM_DELIVERABLES: dict[Platform, set[DeliverableType]] = {
    Platform.INSTAGRAM: {
        DeliverableType.INSTAGRAM_POST,
        DeliverableType.INSTAGRAM_STORY,
        DeliverableType.INSTAGRAM_REEL,
    },
    Platform.TIKTOK: {
        DeliverableType.TIKTOK_VIDEO,
        DeliverableType.TIKTOK_STORY,
    },
    Platform.YOUTUBE: {
        DeliverableType.YOUTUBE_DEDICATED,
        DeliverableType.YOUTUBE_INTEGRATION,
        DeliverableType.YOUTUBE_SHORT,
    },
}

def get_platform_for_deliverable(deliverable_type: DeliverableType) -> Platform:
    """Look up which platform a deliverable type belongs to."""
    for platform, types in PLATFORM_DELIVERABLES.items():
        if deliverable_type in types:
            return platform
    raise ValueError(f"Unknown deliverable type: {deliverable_type}")

def validate_platform_deliverable(
    platform: Platform, deliverable_type: DeliverableType
) -> None:
    """Raise ValueError if deliverable type is invalid for the given platform."""
    valid_types = PLATFORM_DELIVERABLES.get(platform, set())
    if deliverable_type not in valid_types:
        raise ValueError(
            f"{deliverable_type} is not valid for {platform}. "
            f"Valid types: {', '.join(sorted(valid_types))}"
        )
```

### Parameterized State Machine Tests
```python
# Source: pytest parameterization pattern (https://docs.pytest.org/)
import pytest
from negotiation.domain.types import NegotiationState
from negotiation.state_machine.machine import NegotiationStateMachine, InvalidTransitionError

# All valid transitions -- test each produces the correct target state
VALID_TRANSITIONS = [
    (NegotiationState.INITIAL_OFFER, "send_offer", NegotiationState.AWAITING_REPLY),
    (NegotiationState.AWAITING_REPLY, "receive_reply", NegotiationState.COUNTER_RECEIVED),
    (NegotiationState.AWAITING_REPLY, "timeout", NegotiationState.STALE),
    (NegotiationState.COUNTER_RECEIVED, "send_counter", NegotiationState.COUNTER_SENT),
    (NegotiationState.COUNTER_RECEIVED, "accept", NegotiationState.AGREED),
    (NegotiationState.COUNTER_RECEIVED, "reject", NegotiationState.REJECTED),
    (NegotiationState.COUNTER_RECEIVED, "escalate", NegotiationState.ESCALATED),
    (NegotiationState.COUNTER_SENT, "receive_reply", NegotiationState.COUNTER_RECEIVED),
    (NegotiationState.COUNTER_SENT, "timeout", NegotiationState.STALE),
    (NegotiationState.ESCALATED, "resume_counter", NegotiationState.COUNTER_SENT),
    (NegotiationState.ESCALATED, "reject", NegotiationState.REJECTED),
    (NegotiationState.STALE, "receive_reply", NegotiationState.COUNTER_RECEIVED),
    (NegotiationState.STALE, "reject", NegotiationState.REJECTED),
]

@pytest.mark.parametrize("from_state,event,expected_to", VALID_TRANSITIONS)
def test_valid_transition(from_state, event, expected_to):
    sm = NegotiationStateMachine(initial_state=from_state)
    result = sm.trigger(event)
    assert result == expected_to
    assert sm.state == expected_to

# Terminal states reject ALL events
TERMINAL_STATES = [NegotiationState.AGREED, NegotiationState.REJECTED]
ALL_EVENTS = ["send_offer", "receive_reply", "timeout", "send_counter",
              "accept", "reject", "escalate", "resume_counter"]

@pytest.mark.parametrize("terminal_state", TERMINAL_STATES)
@pytest.mark.parametrize("event", ALL_EVENTS)
def test_terminal_states_reject_all_events(terminal_state, event):
    sm = NegotiationStateMachine(initial_state=terminal_state)
    with pytest.raises(InvalidTransitionError):
        sm.trigger(event)
```

### pyproject.toml Configuration
```toml
# Source: uv docs (https://docs.astral.sh/uv/), ruff docs (https://docs.astral.sh/ruff/)
[project]
name = "influencer-negotiation-agent"
version = "0.1.0"
description = "AI-powered influencer rate negotiation agent"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.12,<3",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0,<10",
    "pytest-cov>=6.0",
    "ruff>=0.15",
    "mypy>=1.19",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-v --tb=short"

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "RUF"]

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pip + venv + requirements.txt | uv 0.10.x with lockfile | 2024-2025 | 10-100x faster dep resolution; single tool for everything; lockfile ensures reproducibility |
| flake8 + black + isort (3 tools) | ruff 0.15.x (1 tool) | 2023-2024 | Single Rust-based tool replaces all three; dramatically faster; unified config |
| Pydantic v1 | Pydantic v2.12.x | 2023 | Rust-powered core (pydantic-core); 5-50x faster validation; strict mode; new validator API |
| Custom data classes + manual validation | Pydantic v2 BaseModel | 2023+ | Eliminates hundreds of lines of validation boilerplate; JSON schema, serialization included |
| String-based states | StrEnum (Python 3.11+) | Python 3.11 (2022) | Type-safe string enums; works with match/case; serializes to/from strings cleanly |
| float for money | Decimal (always was correct) | N/A | Float was always wrong for money; Decimal was always the right choice |

**Deprecated/outdated:**
- **Pydantic v1 syntax:** `@validator` is replaced by `@field_validator`; `Config` inner class is replaced by `model_config = ConfigDict(...)`. Do NOT use v1 patterns.
- **setup.py / setup.cfg:** Use `pyproject.toml` exclusively. PEP 621 standardized this.
- **pip freeze > requirements.txt:** Use `uv lock` for deterministic lockfiles.

## Open Questions

1. **Should the state machine support "undo" or state correction?**
   - What we know: The state machine currently only moves forward. If a state is set incorrectly (e.g., marked AGREED when the influencer actually said "let me think about it"), there is no rollback mechanism.
   - What's unclear: Whether Phase 2+ will need the ability to correct state machine errors, or if manual database correction is acceptable for v1.
   - Recommendation: For v1, do NOT build undo. Keep the state machine simple and forward-only. If a state needs correction, it can be handled by creating a new state machine instance with the corrected state. Log all transitions for audit purposes so corrections are traceable.

2. **Should rate cards be configurable per campaign or global?**
   - What we know: The $20-$30 CPM range is currently global. The CONTEXT.md says "CPM range is $20-$30" without per-campaign variation.
   - What's unclear: Whether different campaigns will have different CPM ranges. The project mentions a future "strategist" agent for campaign-level CPM management.
   - Recommendation: For Phase 1, make the CPM floor/ceiling configurable parameters (not hardcoded constants) that are passed into the pricing engine, but default to $20/$30. This allows per-campaign ranges in the future without code changes. Do NOT build a full campaign-rate-card configuration system -- that is future scope.

3. **How to handle multi-deliverable negotiations?**
   - What we know: An influencer might negotiate for a package (e.g., "1 Reel + 3 Stories for $3,000"). The pricing engine needs to evaluate each deliverable separately.
   - What's unclear: Whether Phase 1 should support package pricing or just individual deliverable pricing.
   - Recommendation: Phase 1 should support pricing individual deliverables. Multi-deliverable package negotiation is Phase 3+ territory (LLM pipeline will decompose package proposals). Build the pricing engine so it can price each deliverable type independently, and a higher-level function can sum them for package evaluation. Do NOT build package bundling/unbundling logic in Phase 1.

## Sources

### Primary (HIGH confidence)
- Python 3.12 `decimal` module documentation (https://docs.python.org/3/library/decimal.html) -- Decimal arithmetic patterns, quantize(), ROUND_HALF_UP
- Python 3.12 `enum` module documentation (https://docs.python.org/3/library/enum.html) -- StrEnum, enum patterns
- Pydantic v2 documentation (https://docs.pydantic.dev/latest/concepts/models/) -- BaseModel, field_validator, ConfigDict, frozen models
- PyPI: pydantic 2.12.5 (https://pypi.org/project/pydantic/) -- current version, Python >=3.9
- PyPI: pytest 9.0.2 (https://pypi.org/project/pytest/) -- current version, Python >=3.10
- PyPI: ruff 0.15.1 (https://pypi.org/project/ruff/) -- current version
- PyPI: mypy 1.19.1 (https://pypi.org/project/mypy/) -- current version
- PyPI: uv 0.10.4 (https://pypi.org/project/uv/) -- current version
- Ruff configuration docs (https://docs.astral.sh/ruff/configuration/) -- pyproject.toml setup
- uv project setup (https://docs.astral.sh/uv/) -- project initialization, dependency management

### Secondary (MEDIUM confidence)
- PyPI: python-statemachine 2.6.0 (https://pypi.org/project/python-statemachine/) -- evaluated but not recommended for this simple use case
- Influencer marketing CPM formula and benchmarks (https://influencermarketinghub.com/how-to-calculate-influencer-costs/) -- CPM = (Cost / Impressions) * 1000
- Platform-specific CPM benchmarks (https://pageoneformula.com/influencer-marketing-cost-cpm-benchmarks-2024-2025/) -- industry rate ranges by platform

### Tertiary (LOW confidence)
- Platform-specific CPM market rates -- market rates fluctuate; the $20-$30 range is per project requirements, not independently validated as market-appropriate for all platforms and deliverable types. Instagram Story CPM and YouTube long-form CPM are quite different in practice.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All library versions verified against PyPI as of 2026-02-18. Python, Pydantic, pytest, ruff, mypy, and uv are mature, stable technologies with clear documentation.
- Architecture: HIGH -- State machine, pricing engine, and enum patterns are fundamental CS/software engineering patterns. No novel technical challenges. The specific design (hand-rolled FSM, Decimal arithmetic, Pydantic models) is straightforward and well-supported.
- Pitfalls: HIGH -- Float arithmetic errors in pricing, incomplete state transition coverage, and platform/deliverable mismatches are well-documented categories of bugs. Prevention strategies are concrete and testable.

**Research date:** 2026-02-18
**Valid until:** 2026-04-18 (60 days -- this phase uses stable, slow-moving technologies)
