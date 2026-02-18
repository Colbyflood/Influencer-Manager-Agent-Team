# Testing Patterns

**Analysis Date:** 2026-02-18

## Project Status

This codebase is in **early development**. No test framework, test files, or testing configuration have been established yet. This document provides guidance for implementing testing practices as the project develops.

## Test Framework Selection

**Current State:**
- Not yet selected

**Recommendations by Technology Choice:**

**For JavaScript/TypeScript:**
- **Jest** - Excellent default choice. Built-in coverage, snapshot testing, mocking
  - Config file: `jest.config.js` or `jest.config.ts`
  - Good for unit, integration, and some E2E testing

- **Vitest** - Faster alternative, Vite-native, excellent DX
  - Config file: `vitest.config.ts`
  - Growing ecosystem, good for modern tooling

- **Playwright** - For browser automation and E2E testing
  - Config file: `playwright.config.ts`
  - Good for full-stack testing

**For Python:**
- **pytest** - Industry standard, great fixture system
  - Config file: `pyproject.toml` or `pytest.ini`
  - Recommended for data analysis components

- **unittest** - Python standard library alternative
  - Built-in, no external dependencies

**Assertion Library:**
- **Jest/Vitest:** Built-in expect() API
- **Chai.js:** Popular alternative for Node.js projects
- **Pytest:** Built-in assert statements with smart comparison

## Test File Organization

**Recommended Location Patterns:**

```
Project Structure Options:

# Option 1: Co-located (Preferred for maintainability)
src/
├── services/
│   ├── user-service.ts
│   ├── user-service.test.ts
│   ├── influencer-service.ts
│   └── influencer-service.test.ts
└── utils/
    ├── metrics.ts
    └── metrics.test.ts

# Option 2: Separate test directory
src/
├── services/
│   ├── user-service.ts
│   └── influencer-service.ts
└── utils/
    └── metrics.ts
tests/
├── unit/
│   ├── services/
│   │   ├── user-service.test.ts
│   │   └── influencer-service.test.ts
│   └── utils/
│       └── metrics.test.ts
├── integration/
│   └── api.test.ts
└── e2e/
    └── campaigns.test.ts
```

**Naming Convention:**
- `*.test.ts` - Unit and integration tests (preferred)
- `*.spec.ts` - Specification-style tests (alternative)
- E2E tests may use `*.e2e.ts` or keep in separate directory

**Recommendation:** Use co-located pattern for easier navigation and updates.

## Run Commands

**Establish Once Framework Selected:**

```bash
# Unit tests only (when established)
npm test                    # or: pytest tests/ --ignore=tests/integration

# Watch mode for TDD
npm test -- --watch        # or: pytest-watch

# Coverage report
npm test -- --coverage     # or: pytest --cov=src tests/

# E2E tests
npm run test:e2e           # or: playwright test

# All tests including integration
npm test:all               # or: pytest
```

## Test Structure and Patterns

**Recommended Test Suite Organization:**

```typescript
// Standard pattern for TypeScript/JavaScript tests
describe('UserService', () => {
  describe('getUserById', () => {
    it('should return user when ID exists', async () => {
      // Arrange
      const userId = '123';
      const expectedUser = { id: '123', name: 'John Doe' };

      // Act
      const result = await userService.getUserById(userId);

      // Assert
      expect(result).toEqual(expectedUser);
    });

    it('should throw NotFoundError when user does not exist', async () => {
      // Arrange
      const userId = 'nonexistent';

      // Act & Assert
      await expect(userService.getUserById(userId))
        .rejects.toThrow(NotFoundError);
    });
  });
});
```

**Setup and Teardown:**
```typescript
describe('Database Operations', () => {
  beforeEach(() => {
    // Setup before each test
    // Example: Clear test database, reset mocks
  });

  afterEach(() => {
    // Cleanup after each test
    // Example: Close connections, restore mocks
  });

  beforeAll(() => {
    // Setup once before all tests in suite
    // Example: Start test database
  });

  afterAll(() => {
    // Cleanup once after all tests in suite
    // Example: Stop test database, close connections
  });
});
```

**Best Practices:**
- One logical assertion focus per test
- Use descriptive test names that explain both scenario and expected outcome
- Follow Arrange-Act-Assert pattern
- Keep tests independent - avoid test interdependencies
- Clean up side effects in afterEach/afterAll hooks

## Mocking

**Framework Selection:**
- **Jest:** Built-in mocking with `jest.mock()` and `jest.spyOn()`
- **Vitest:** Same API as Jest, excellent mocking support
- **Python pytest:** Use `unittest.mock` or `pytest-mock` fixture

**Mocking Patterns:**

```typescript
// Module mocking
jest.mock('../services/external-api', () => ({
  fetchInfluencerData: jest.fn().mockResolvedValue({
    id: '123',
    followers: 50000,
    engagement: 0.05
  })
}));

// Function spying
const getUserSpy = jest.spyOn(userService, 'getUser');

// Partial mocking with jest.spyOn
const calculateSpy = jest.spyOn(metricsService, 'calculateEngagementRate')
  .mockReturnValue(0.08);

// Reset mocks
afterEach(() => {
  jest.clearAllMocks();
});
```

**Mocking Guidelines:**

**What to Mock:**
- External API calls (network requests)
- Database operations (use test databases instead when possible)
- File I/O operations
- Heavy computations
- Date/time (for consistent test results)
- Random number generation
- Third-party services (Stripe, email, etc.)

**What NOT to Mock:**
- Core business logic - test the real implementation
- Data transformation functions - test actual behavior
- Validation logic - verify it works correctly
- Internal service methods unless they're expensive

## Fixtures and Test Data

**Recommended Approach:**

```typescript
// fixtures/user.fixture.ts
export const createTestUser = (overrides?: Partial<User>): User => ({
  id: 'test-user-123',
  name: 'Test User',
  email: 'test@example.com',
  createdAt: new Date('2026-01-01'),
  ...overrides
});

export const createTestInfluencer = (overrides?: Partial<Influencer>): Influencer => ({
  id: 'inf-123',
  handle: '@testinfluencer',
  followers: 100000,
  engagementRate: 0.05,
  ...overrides
});

// Usage in tests
it('should calculate campaign budget for influencer', () => {
  const influencer = createTestInfluencer({ followers: 50000 });
  const budget = calculateCampaignBudget(influencer);
  expect(budget).toBe(expectedAmount);
});
```

**Test Data Location:**
- Place in `tests/fixtures/` or `src/__fixtures__/` directory
- Organize by domain: `fixtures/user.fixture.ts`, `fixtures/campaign.fixture.ts`
- Use factory functions for flexibility and consistent data

## Coverage

**Establish Targets When Testing Framework Selected:**

```bash
# Default coverage configuration (jest.config.js)
coverageThreshold: {
  global: {
    branches: 80,
    functions: 80,
    lines: 80,
    statements: 80
  }
}
```

**Coverage Interpretation:**
- **Line Coverage:** Percentage of code lines executed
- **Branch Coverage:** Percentage of conditional paths (if/else) covered
- **Function Coverage:** Percentage of functions called
- **Statement Coverage:** Percentage of statements executed

**Recommended Approach:**
- Aim for 80% coverage minimum for business logic
- Aim for 90%+ for critical paths (authentication, payments, core calculations)
- Don't obsess over 100% - focus on meaningful tests
- Use coverage reports to identify untested areas

**View Coverage:**
```bash
npm test -- --coverage                    # Generate coverage report
npm test -- --coverage --coverageReporters=html  # HTML report
open coverage/index.html                  # View in browser
```

## Test Types

**Unit Tests:**
- **Scope:** Single function or class in isolation
- **Approach:** Mock external dependencies
- **Location:** Co-located with source files (e.g., `user-service.test.ts`)
- **Examples:**
  - Test `calculateEngagementRate()` with various metrics
  - Test `validateCampaignBudget()` with valid/invalid inputs
  - Test `parseInfluencerProfile()` with different data formats

**Integration Tests:**
- **Scope:** Multiple components working together, but not the full system
- **Approach:** Use real database (test instance), mock external APIs only
- **Location:** `tests/integration/` directory
- **Examples:**
  - Test user creation through service -> repository -> database
  - Test influencer search across service layers
  - Test campaign creation with related entities

**E2E Tests:**
- **Scope:** Full user workflows end-to-end
- **Framework:** Playwright or Cypress (when web UI exists)
- **Location:** `tests/e2e/` directory
- **Examples:**
  - User creates campaign and sends outreach to influencer
  - Admin reviews campaign metrics and exports report
  - Influencer accepts collaboration offer

## Common Testing Patterns

**Async Testing:**
```typescript
// Promise-based
it('should fetch user data', async () => {
  const user = await userService.getUser('123');
  expect(user.name).toBe('John Doe');
});

// Handling rejections
it('should handle fetch errors', async () => {
  jest.spyOn(httpClient, 'get').mockRejectedValue(new Error('Network error'));

  await expect(userService.getUser('123'))
    .rejects.toThrow('Network error');
});

// Timeout handling
it('should timeout on slow requests', async () => {
  jest.setTimeout(5000); // 5 second timeout
  // test code
});
```

**Error Testing:**
```typescript
it('should throw ValidationError for invalid budget', () => {
  const invalidBudget = -100;

  expect(() => {
    validateCampaignBudget(invalidBudget);
  }).toThrow(ValidationError);
});

it('should throw with specific message', () => {
  expect(() => {
    validateCampaignBudget(-100);
  }).toThrow('Budget must be positive');
});

it('should not throw for valid budget', () => {
  expect(() => {
    validateCampaignBudget(1000);
  }).not.toThrow();
});
```

**Testing Array Operations:**
```typescript
it('should filter influencers by minimum followers', () => {
  const influencers = [
    { handle: '@small', followers: 5000 },
    { handle: '@medium', followers: 50000 },
    { handle: '@large', followers: 500000 }
  ];

  const filtered = filterByMinimumFollowers(influencers, 10000);

  expect(filtered).toHaveLength(2);
  expect(filtered).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ followers: 50000 }),
      expect.objectContaining({ followers: 500000 })
    ])
  );
});
```

## CI/CD Integration

**When Framework Selected, Establish:**
- Run all tests on every pull request
- Fail build if coverage falls below threshold
- Run tests in parallel for speed
- Separate fast unit tests from slower integration tests
- Run E2E tests on staging environment before production deployment

---

*Testing analysis: 2026-02-18*
